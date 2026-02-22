from __future__ import annotations

from dataclasses import dataclass
import math
import os
from pathlib import Path
import random
import shutil
import subprocess
import time
import wave
from typing import Mapping

from .config import ChannelConfig


@dataclass
class Ema:
    value: float = 0.0

    def update(self, x: float, alpha: float) -> float:
        self.value = alpha * x + (1.0 - alpha) * self.value
        return self.value


@dataclass
class _LoopState:
    buf: "object"
    pos: int = 0


@dataclass
class _OneShotVoice:
    buf: "object"
    pos: int = 0
    delay: int = 0
    gain: float = 1.0


def _gain_from_rate(rate_pps: float, ref_pps: float, gamma: float, base_gain: float) -> float:
    if ref_pps <= 0:
        return 0.0
    x = max(0.0, rate_pps) / ref_pps
    return base_gain * (min(1.0, x) ** gamma)


def _maybe_chown_to_sudo_user(p: Path) -> None:
    try:
        if os.geteuid() != 0:
            return
        uid_s = os.environ.get("SUDO_UID")
        gid_s = os.environ.get("SUDO_GID")
        if not uid_s or not gid_s:
            return
        os.chown(p, int(uid_s), int(gid_s))
    except Exception:
        return


class AudioEngine:
    """
    Génère un mix:
      - "river": son continu (bruit filtré ou sample bouclé) modulé par trafic total
      - "channels":
         - mode=loop: son continu (drone/bruit ou sample bouclé) modulé par le débit du canal
         - mode=one-shot: évènements discrets (chirp/drone/noise ou sample joué 1x)
    """

    def __init__(
        self,
        *,
        sample_rate: int,
        block_ms: int,
        river_sample: str = "@noise",
        river_gain: float,
        river_ref_pps: float,
        river_gamma: float,
        river_cutoff_hz: float,
        channels: Mapping[str, ChannelConfig],
        samples_dir: str | Path = "samples",
        record_path: str | Path | None = None,
        dry_run: bool,
        audio_backend: str = "auto",
        device: str | None = None,
    ) -> None:
        self.sample_rate = int(sample_rate)
        self.block_ms = int(block_ms)
        self.block_frames = int(self.sample_rate * (self.block_ms / 1000.0))
        self.block_s = self.block_frames / self.sample_rate

        self.river_sample = str(river_sample or "@noise")
        self.river_gain = float(river_gain)
        self.river_ref_pps = float(river_ref_pps)
        self.river_gamma = float(river_gamma)
        self.river_cutoff_hz = float(river_cutoff_hz)

        self.channels = channels
        self.samples_dir = Path(samples_dir)
        self.record_path = Path(record_path) if record_path else None
        self.dry_run = dry_run
        self.audio_backend = audio_backend
        self.device = device

        self._emas: dict[str, Ema] = {}
        self._river_ema = Ema()
        self._river_lp_state = 0.0
        self._drone_phase: dict[str, float] = {}
        self._loop_states: dict[str, _LoopState] = {}
        self._voices: list[_OneShotVoice] = []
        self._sample_cache: dict[str, "object"] = {}
        self._warned: set[str] = set()

        # Import lazy: numpy/sounddevice optionnels tant qu'on ne lance pas l'audio.
        self._np = None
        self._sd = None

    def _lazy_import_numpy(self) -> None:
        if self._np is None:
            import numpy as np

            self._np = np

    def _lazy_import_sounddevice(self) -> None:
        if self._sd is None:
            import sounddevice as sd

            self._sd = sd

    def _warn_once(self, key: str, msg: str) -> None:
        if key in self._warned:
            return
        self._warned.add(key)
        print(f"[flow-sonify] {msg}")

    def _decode_sample(self, name: str) -> "object | None":
        """
        Retourne un buffer float32 mono à sample_rate, ou None si impossible.
        name: nom de fichier dans samples_dir (pas de builtin).
        """
        np = self._np
        name = str(name)
        if not name or name.startswith("@"):
            return None

        if name in self._sample_cache:
            return self._sample_cache[name]

        path = (self.samples_dir / name).resolve()
        if not path.exists():
            self._warn_once(f"missing:{name}", f"sample introuvable: {path}")
            self._sample_cache[name] = None
            return None

        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            self._warn_once("no-ffmpeg", "ffmpeg introuvable: impossible de décoder des samples (fallback sur sons internes).")
            self._sample_cache[name] = None
            return None

        cmd = [
            ffmpeg,
            "-v",
            "error",
            "-i",
            str(path),
            "-f",
            "f32le",
            "-ac",
            "1",
            "-ar",
            str(self.sample_rate),
            "pipe:1",
        ]

        # Limite de charge mémoire: 3 minutes max par sample (mono float32).
        max_frames = int(self.sample_rate * 180)
        max_bytes = max_frames * 4
        data = bytearray()
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            assert proc.stdout is not None
            truncated = False
            while True:
                chunk = proc.stdout.read(65536)
                if not chunk:
                    break
                data.extend(chunk)
                if len(data) >= max_bytes:
                    truncated = True
                    break

            if truncated and proc.poll() is None:
                try:
                    proc.terminate()
                except Exception:
                    pass
            try:
                proc.wait(timeout=2.0)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
                try:
                    proc.wait(timeout=2.0)
                except Exception:
                    pass

            if proc.returncode not in (0, None) and not data:
                err = b""
                try:
                    err = proc.stderr.read() if proc.stderr is not None else b""
                except Exception:
                    pass
                self._warn_once(f"decode-rc:{name}", f"ffmpeg a échoué pour {name}: {err.decode('utf-8', 'ignore').strip()}")
                self._sample_cache[name] = None
                return None
            if not data:
                self._warn_once(f"decode-empty:{name}", f"impossible de décoder le sample: {name}")
                self._sample_cache[name] = None
                return None
            if truncated:
                self._warn_once(f"decode-trunc:{name}", f"sample tronqué à 180s pour limiter la mémoire: {name}")
        except Exception as e:
            self._warn_once(f"decode-fail:{name}", f"erreur de décodage ffmpeg pour {name}: {e}")
            self._sample_cache[name] = None
            return None

        arr = np.frombuffer(bytes(data[: (len(data) // 4) * 4]), dtype="<f4").astype(np.float32, copy=False)
        if arr.size <= 0:
            self._sample_cache[name] = None
            return None
        # Avoid pathological DC offset.
        arr = (arr - np.mean(arr)).astype(np.float32)
        self._sample_cache[name] = arr
        return arr

    def _chirp(self, freq_hz: float, duration_ms: int, gain: float) -> "object":
        np = self._np
        frames = max(1, int(self.sample_rate * (duration_ms / 1000.0)))
        t = np.arange(frames, dtype=np.float32) / np.float32(self.sample_rate)
        # Légère modulation pour différencier les sons (animal-like sans samples).
        mod = 1.0 + 0.02 * np.sin(2.0 * math.pi * 6.0 * t)
        phase = 2.0 * math.pi * np.float32(freq_hz) * t * mod
        wave = np.sin(phase).astype(np.float32)

        # Envelope attaque/relâche (évite les clics)
        a = max(1, int(0.01 * frames))
        r = max(1, int(0.25 * frames))
        env = np.ones(frames, dtype=np.float32)
        env[:a] = np.linspace(0.0, 1.0, a, dtype=np.float32)
        env[-r:] = np.linspace(1.0, 0.0, r, dtype=np.float32)
        return (gain * wave * env).astype(np.float32)

    def _burst(self, kind: str, key: str, gain: float, duration_ms: int, freq_hz: float) -> "object":
        np = self._np
        frames = max(1, int(self.sample_rate * (duration_ms / 1000.0)))
        t = np.arange(frames, dtype=np.float32) / np.float32(self.sample_rate)

        if kind == "drone":
            wave = np.sin(2.0 * math.pi * np.float32(freq_hz) * t).astype(np.float32)
        else:
            wave = np.random.uniform(-1.0, 1.0, size=frames).astype(np.float32)

        a = max(1, int(0.01 * frames))
        r = max(1, int(0.35 * frames))
        env = np.ones(frames, dtype=np.float32)
        env[:a] = np.linspace(0.0, 1.0, a, dtype=np.float32)
        env[-r:] = np.linspace(1.0, 0.0, r, dtype=np.float32)
        return (gain * wave * env).astype(np.float32)

    def _drone(self, key: str, freq_hz: float, gain: float) -> "object":
        np = self._np
        phase = float(self._drone_phase.get(key, 0.0))
        t = (np.arange(self.block_frames, dtype=np.float32) / np.float32(self.sample_rate)).astype(np.float32)
        # phase in radians
        omega = 2.0 * math.pi * float(freq_hz)
        phases = phase + omega * t
        wave = np.sin(phases).astype(np.float32)
        phase_end = float(phases[-1] + (omega / self.sample_rate))
        self._drone_phase[key] = float(phase_end % (2.0 * math.pi))
        # small slow AM for "alive" feeling
        am = (0.85 + 0.15 * np.sin(2.0 * math.pi * 0.5 * t)).astype(np.float32)
        return (gain * wave * am).astype(np.float32)

    def _river(self, gain: float) -> "object":
        np = self._np
        # One-pole low-pass: y[n]=y[n-1]+a(x[n]-y[n-1])
        cutoff = max(10.0, self.river_cutoff_hz)
        dt = 1.0 / self.sample_rate
        rc = 1.0 / (2.0 * math.pi * cutoff)
        a = dt / (rc + dt)

        x = np.random.uniform(-1.0, 1.0, size=self.block_frames).astype(np.float32)
        y = np.empty_like(x)
        state = float(self._river_lp_state)
        for i in range(self.block_frames):
            state = state + a * (float(x[i]) - state)
            y[i] = state
        self._river_lp_state = state
        return (gain * y).astype(np.float32)

    def _loop_sample_block(self, key: str, sample_name: str) -> "object | None":
        np = self._np
        buf = self._decode_sample(sample_name)
        if buf is None:
            return None
        if buf.shape[0] < 8:
            return None

        st = self._loop_states.get(key)
        if st is None or st.buf is not buf:
            st = _LoopState(buf=buf, pos=0)
            self._loop_states[key] = st

        out = np.empty(self.block_frames, dtype=np.float32)
        pos = int(st.pos)
        n = int(buf.shape[0])
        i = 0
        while i < self.block_frames:
            take = min(self.block_frames - i, n - pos)
            out[i : i + take] = buf[pos : pos + take]
            i += take
            pos += take
            if pos >= n:
                pos = 0
        st.pos = pos
        return out

    def _spawn_sample_voice(self, sample_name: str, gain: float, *, delay_frames: int) -> None:
        buf = self._decode_sample(sample_name)
        if buf is None:
            return
        if buf.shape[0] < 8:
            return
        self._voices.append(_OneShotVoice(buf=buf, pos=0, delay=max(0, int(delay_frames)), gain=float(gain)))

    def _mix_voices(self, audio: "object") -> None:
        np = self._np
        if not self._voices:
            return

        alive: list[_OneShotVoice] = []
        for v in self._voices:
            delay = int(v.delay)
            if delay >= self.block_frames:
                v.delay = delay - self.block_frames
                alive.append(v)
                continue

            start = max(0, delay)
            v.delay = 0
            remaining = self.block_frames - start
            buf = v.buf
            pos = int(v.pos)
            end = min(int(buf.shape[0]), pos + remaining)
            seg = buf[pos:end]
            if seg.shape[0] > 0:
                audio[start : start + seg.shape[0]] += (v.gain * seg).astype(np.float32, copy=False)
            v.pos = end
            if v.pos < int(buf.shape[0]):
                alive.append(v)
        # Avoid unbounded growth (e.g., if very chatty + long samples).
        self._voices = alive[-64:]

    def _mix_block(self, counts: Mapping[str, int]) -> tuple["object", dict[str, float]]:
        """
        Retourne (audio_block, debug_levels).
        """
        np = self._np
        audio = np.zeros(self.block_frames, dtype=np.float32)

        total = int(counts.get("net.total", 0) or (counts.get("in.total", 0) + counts.get("out.total", 0)))
        total_pps = total / self.block_s
        total_smoothed = self._river_ema.update(total_pps, alpha=0.25)
        river_level = _gain_from_rate(total_smoothed, self.river_ref_pps, self.river_gamma, self.river_gain)
        river_sample = (self.river_sample or "@noise").strip()
        if river_sample == "@none":
            river_level = 0.0
        elif river_sample == "@noise" or river_sample.startswith("@"):
            audio += self._river(river_level)
        else:
            blk = self._loop_sample_block("__river__", river_sample)
            if blk is None:
                self._warn_once("river-fallback", f"river.sample={river_sample} non lisible => fallback @noise")
                audio += self._river(river_level)
            else:
                audio += (river_level * blk).astype(np.float32)

        debug_levels: dict[str, float] = {"river": float(river_level)}

        # One-shots: capped
        max_events_per_key = 6
        for key, spec in self.channels.items():
            count = int(counts.get(key, 0))
            if not bool(getattr(spec, "enabled", True)):
                debug_levels[key] = 0.0
                continue

            mode = (spec.mode or "one-shot").lower()
            sample = (spec.sample or "@chirp").strip()
            if sample == "@none":
                debug_levels[key] = 0.0
                continue

            ema = self._emas.setdefault(key, Ema())
            rate = (count / self.block_s) if count > 0 else 0.0
            smoothed = ema.update(rate, alpha=0.35)
            gain = _gain_from_rate(smoothed, spec.ref_pps, spec.gamma, spec.gain)
            debug_levels[key] = float(gain)

            if mode == "loop":
                if gain <= 0.0:
                    # Keep phase/position moving even at 0 gain for continuity.
                    if sample and not sample.startswith("@"):
                        _ = self._loop_sample_block(key, sample)
                    continue

                if sample == "@drone" or sample == "@chirp":
                    audio += self._drone(key, spec.freq_hz, gain)
                elif sample == "@noise":
                    # Reuse river noise (simple, consistent).
                    audio += self._river(gain)
                elif sample.startswith("@"):
                    audio += self._drone(key, spec.freq_hz, gain)
                else:
                    blk = self._loop_sample_block(key, sample)
                    if blk is None:
                        self._warn_once(f"loop-fallback:{sample}", f"sample loop illisible: {sample} (canal {key})")
                    else:
                        audio += (gain * blk).astype(np.float32)
                continue

            # one-shot
            if count <= 0 or gain <= 0.0:
                continue

            n_events = min(max_events_per_key, max(1, int(count)))
            if sample == "@chirp" or sample == "":
                wave = self._chirp(spec.freq_hz, spec.duration_ms, gain)
                wlen = int(wave.shape[0])
                for _ in range(n_events):
                    start = int(np.random.randint(0, max(1, self.block_frames)))
                    end = min(self.block_frames, start + wlen)
                    seg_len = end - start
                    if seg_len > 0:
                        audio[start:end] += wave[:seg_len]
            elif sample == "@drone":
                wave = self._burst("drone", key, gain, max(40, int(spec.duration_ms or 90)), float(spec.freq_hz or 220.0))
                wlen = int(wave.shape[0])
                for _ in range(min(2, n_events)):
                    start = int(np.random.randint(0, max(1, self.block_frames)))
                    end = min(self.block_frames, start + wlen)
                    seg_len = end - start
                    if seg_len > 0:
                        audio[start:end] += wave[:seg_len]
            elif sample == "@noise":
                wave = self._burst("noise", key, gain, max(40, int(spec.duration_ms or 90)), 0.0)
                wlen = int(wave.shape[0])
                for _ in range(min(2, n_events)):
                    start = int(np.random.randint(0, max(1, self.block_frames)))
                    end = min(self.block_frames, start + wlen)
                    seg_len = end - start
                    if seg_len > 0:
                        audio[start:end] += wave[:seg_len]
            elif sample.startswith("@"):
                wave = self._chirp(spec.freq_hz, spec.duration_ms, gain)
                wlen = int(wave.shape[0])
                for _ in range(n_events):
                    start = int(np.random.randint(0, max(1, self.block_frames)))
                    end = min(self.block_frames, start + wlen)
                    seg_len = end - start
                    if seg_len > 0:
                        audio[start:end] += wave[:seg_len]
            else:
                for _ in range(min(3, n_events)):
                    self._spawn_sample_voice(sample, gain, delay_frames=random.randint(0, max(0, self.block_frames - 1)))

        self._mix_voices(audio)

        # Soft clip
        audio = np.tanh(audio).astype(np.float32)
        return audio, debug_levels

    def run(self, *, counts_provider, stop_event) -> None:
        """
        counts_provider: callable() -> Mapping[str,int]
          (doit renvoyer un snapshot et reset des compteurs)
        """
        if self.dry_run:
            self._run_dry(counts_provider=counts_provider, stop_event=stop_event)
            return

        backend = self._resolve_backend(self.audio_backend)
        self._lazy_import_numpy()
        np = self._np

        wav: wave.Wave_write | None = None
        if self.record_path is not None:
            self.record_path.parent.mkdir(parents=True, exist_ok=True)
            wav = wave.open(str(self.record_path), "wb")
            wav.setnchannels(1)
            wav.setsampwidth(2)  # int16
            wav.setframerate(self.sample_rate)
            _maybe_chown_to_sudo_user(self.record_path.parent)

        if backend == "sounddevice":
            self._lazy_import_sounddevice()
            sd = self._sd
            try:
                with sd.OutputStream(
                    samplerate=self.sample_rate,
                    channels=1,
                    dtype="float32",
                    blocksize=self.block_frames,
                    device=self.device,
                ) as stream:
                    while not stop_event.is_set():
                        t0 = time.monotonic()
                        counts = counts_provider()
                        block, _levels = self._mix_block(counts)
                        stream.write(block.reshape(-1, 1))
                        if wav is not None:
                            pcm16 = (np.clip(block, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
                            wav.writeframes(pcm16)
                        self._pace(t0)
                return
            finally:
                if wav is not None:
                    wav.close()
                    if self.record_path is not None:
                        _maybe_chown_to_sudo_user(self.record_path)

        if backend == "aplay":
            aplay = shutil.which("aplay")
            if aplay is None:
                raise RuntimeError("backend aplay demandé mais `aplay` introuvable")

            cmd = [
                aplay,
                "-q",
                "-t",
                "raw",
                "-f",
                "S16_LE",
                "-c",
                "1",
                "-r",
                str(self.sample_rate),
            ]
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
            assert proc.stdin is not None
            try:
                while not stop_event.is_set():
                    t0 = time.monotonic()
                    counts = counts_provider()
                    block, _levels = self._mix_block(counts)
                    pcm16 = (np.clip(block, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
                    try:
                        proc.stdin.write(pcm16)
                        proc.stdin.flush()
                    except BrokenPipeError:
                        stop_event.set()
                        break
                    if wav is not None:
                        wav.writeframes(pcm16)
                    self._pace(t0)
            finally:
                try:
                    proc.stdin.close()
                except Exception:
                    pass
                try:
                    proc.terminate()
                except Exception:
                    pass
                if wav is not None:
                    wav.close()
                    if self.record_path is not None:
                        _maybe_chown_to_sudo_user(self.record_path)
            return

        if wav is not None:
            wav.close()
            if self.record_path is not None:
                _maybe_chown_to_sudo_user(self.record_path)
        raise RuntimeError(f"backend audio inconnu: {backend}")

    def _pace(self, t0: float) -> None:
        elapsed = time.monotonic() - t0
        slack = self.block_s - elapsed
        if slack > 0.0:
            time.sleep(min(0.010, slack))

    def _resolve_backend(self, backend: str) -> str:
        b = (backend or "auto").lower()
        if b in ("sounddevice", "aplay"):
            return b
        if b not in ("auto",):
            return b

        # auto: prefer sounddevice if available, else aplay
        try:
            import sounddevice  # noqa: F401

            return "sounddevice"
        except Exception:
            pass

        if shutil.which("aplay") is not None:
            return "aplay"
        return "aplay"

    def _run_dry(self, *, counts_provider, stop_event) -> None:
        while not stop_event.is_set():
            counts = counts_provider()
            if counts:
                total = int(counts.get("in.total", 0) + counts.get("out.total", 0))
                top = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()) if v)
                print(f"block {self.block_ms}ms: total={total} :: {top}")
            time.sleep(self.block_s)
