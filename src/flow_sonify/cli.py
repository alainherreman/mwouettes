from __future__ import annotations

import argparse
import signal
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from .audio import AudioEngine
from .capture import CaptureManager, PcapSniffer, TcpdumpSniffer, TrafficCounters, list_interfaces
from .config import AppConfig, load_config
from .ui_server import run_ui_server


def _infer_base_dir(config_path: str | None) -> Path:
    """
    Base dir = dossier qui contient samples/ + environments/ (en pratique la racine du projet).
    Important quand on lance avec sudo ou avec un config dans configs/.
    """
    candidates: list[Path] = []
    if config_path:
        p = Path(config_path).resolve()
        candidates.append(p.parent)
        candidates.append(p.parent.parent)
    candidates.append(Path.cwd().resolve())

    for c in candidates:
        try:
            if (c / "pyproject.toml").is_file() and (c / "src").is_dir():
                return c
            if (c / "samples").is_dir() or (c / "environments").is_dir():
                return c
        except Exception:
            continue
    return candidates[0] if candidates else Path.cwd().resolve()


def _parse_args(argv: list[str], *, prog: str) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog=prog, description="mwouettes — sonification temps-réel du trafic réseau (entrant/sortant).")
    p.add_argument("--list-interfaces", action="store_true", help="Liste les interfaces et sort.")
    p.add_argument("--list-audio-devices", action="store_true", help="Liste les périphériques audio (sounddevice/aplay) et sort.")
    p.add_argument("--interface", "-i", help="Interface réseau à sniffer (ex: eth0, wlan0).")
    p.add_argument("--config", help="Chemin vers un JSON de configuration (sinon valeurs par défaut).")
    p.add_argument("--bpf", help="Filtre BPF (libpcap), ex: 'ip and (tcp or udp)'.")
    p.add_argument("--device", help="Périphérique audio (nom ou index) pour sounddevice.")
    p.add_argument("--ui", action="store_true", help="Lance une UI Web locale pour régler le mapping en live (audio via navigateur).")
    p.add_argument("--ui-host", default="127.0.0.1", help="Adresse d'écoute UI (défaut: 127.0.0.1).")
    p.add_argument("--ui-port", type=int, default=8765, help="Port UI (défaut: 8765).")
    p.add_argument(
        "--capture-backend",
        default="auto",
        choices=["auto", "tcpdump", "scapy"],
        help="Backend capture paquets (auto=tcpdump si dispo, sinon scapy).",
    )
    p.add_argument(
        "--audio-backend",
        default="auto",
        choices=["auto", "aplay", "sounddevice"],
        help="Backend audio (auto=sounddevice si dispo, sinon aplay).",
    )
    p.add_argument("--record", help="Enregistre la sortie audio (mix) dans un fichier WAV (16-bit mono). Ex: --record out.wav")
    p.add_argument("--dry-run", action="store_true", help="Ne joue pas de sons; affiche les compteurs par bloc.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    prog = Path(sys.argv[0]).name or "mwouettes"
    args = _parse_args(sys.argv[1:] if argv is None else argv, prog=prog)

    if args.list_interfaces:
        names = list_interfaces()
        if names:
            print("\n".join(names))
            return 0
        print(f"[{prog}] impossible de lister les interfaces.", file=sys.stderr)
        return 2

    if args.list_audio_devices:
        try:
            import sounddevice as sd

            print(sd.query_devices())
            return 0
        except Exception:
            pass

        aplay = shutil.which("aplay")
        if aplay is not None:
            try:
                out = subprocess.check_output([aplay, "-l"], text=True, stderr=subprocess.STDOUT)
                print(out.strip())
                return 0
            except Exception as e:
                print(f"[{prog}] impossible de lister les périphériques via aplay: {e}", file=sys.stderr)
                return 2

        print(f"[{prog}] aucun backend pour lister l'audio (sounddevice/aplay).", file=sys.stderr)
        return 2

    # UX: si l'utilisateur lance juste `mwouettes` sans option, on lance l'UI.
    # Les modes CLI "record"/"dry-run" nécessitent une interface explicite.
    if not args.interface and not args.ui:
        if args.record or args.dry_run:
            print(f"[{prog}] --interface est requis (sauf avec --ui/--list-interfaces/--list-audio-devices).", file=sys.stderr)
            return 2
        args.ui = True

    if args.record and args.ui:
        print(f"[{prog}] --record n’est pas supporté en mode --ui (l’audio est côté navigateur).", file=sys.stderr)
        return 2
    if args.record and args.dry_run:
        print(f"[{prog}] --record nécessite l’audio (désactive --dry-run).", file=sys.stderr)
        return 2

    config_path = args.config
    if config_path is None:
        for default_cfg in (Path("configs/flow_sonify_default.json"), Path("flow_sonify_default.json")):
            if default_cfg.is_file():
                config_path = str(default_cfg)
                print(f"[{prog}] config: {default_cfg} (défaut)", file=sys.stderr)
                break
    base_dir = _infer_base_dir(config_path)

    cfg: AppConfig = load_config(config_path)
    if args.bpf is not None:
        cfg = AppConfig(
            sample_rate=cfg.sample_rate,
            block_ms=cfg.block_ms,
            bpf_filter=args.bpf,
            river=cfg.river,
            channels=cfg.channels,
            environments=cfg.environments,
            active_environment=cfg.active_environment,
        )
    if args.ui:
        env_names = sorted((cfg.environments or {}).keys())
        if env_names:
            print(f"[{prog}] presets: {', '.join(env_names)} (actif: {cfg.active_environment or '—'})", file=sys.stderr)
        else:
            print(f"[{prog}] presets: aucun (utilise --config flow_sonify_default.json ou mets-le dans le dossier courant).", file=sys.stderr)

    capture_backend = args.capture_backend
    if capture_backend == "auto":
        capture_backend = "tcpdump" if shutil.which("tcpdump") is not None else "scapy"

    # Préflight deps (messages plus clairs que des traces dans un thread).
    if capture_backend == "scapy":
        try:
            import scapy  # noqa: F401
        except Exception as e:
            print(
                f"[{prog}] backend scapy sélectionné mais scapy absent (installez `pip install -e '.[pcap]'`) :: {e}",
                file=sys.stderr,
            )
            return 2
    elif capture_backend == "tcpdump":
        if shutil.which("tcpdump") is None:
            print(f"[{prog}] backend tcpdump sélectionné mais `tcpdump` introuvable.", file=sys.stderr)
            return 2

    # Mode UI: audio via navigateur => pas de prérequis audio côté Python.
    if args.ui:
        audio_backend = "web"
    elif not args.dry_run:
        try:
            import numpy  # noqa: F401
        except Exception as e:
            print(f"[{prog}] numpy requis pour l'audio (installez `pip install -e '.[aplay]'`) :: {e}", file=sys.stderr)
            return 2

        audio_backend = args.audio_backend
        if audio_backend == "auto":
            try:
                import sounddevice  # noqa: F401

                audio_backend = "sounddevice"
            except Exception:
                audio_backend = "aplay"

        if audio_backend == "sounddevice":
            try:
                import sounddevice  # noqa: F401
            except Exception as e:
                print(
                    f"[{prog}] backend sounddevice sélectionné mais sounddevice absent (installez `pip install -e '.[audio]'`) :: {e}",
                    file=sys.stderr,
                )
                return 2
        elif audio_backend == "aplay":
            if shutil.which("aplay") is None:
                print(f"[{prog}] backend aplay sélectionné mais `aplay` introuvable.", file=sys.stderr)
                return 2
    else:
        audio_backend = args.audio_backend

    stop_event = threading.Event()
    counters = TrafficCounters()

    engine = AudioEngine(
        sample_rate=cfg.sample_rate,
        block_ms=cfg.block_ms,
        river_sample=cfg.river.sample,
        river_gain=cfg.river.gain,
        river_ref_pps=cfg.river.ref_pps,
        river_gamma=cfg.river.gamma,
        river_cutoff_hz=cfg.river.cutoff_hz,
        channels=cfg.channels,
        samples_dir=(base_dir / "samples"),
        record_path=args.record,
        dry_run=bool(args.dry_run),
        audio_backend=audio_backend,
        device=args.device,
    )

    def handle_sigint(_sig, _frame) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)

    try:
        if args.ui:
            url = f"http://{args.ui_host}:{int(args.ui_port)}/"
            print(f"[{prog}] UI: {url}", file=sys.stderr)
            cap = CaptureManager(
                counters=counters,
                app_stop_event=stop_event,
                capture_backend=capture_backend,
                bpf_filter=cfg.bpf_filter,
            )
            if args.interface:
                cap.set_interface(args.interface)
            run_ui_server(
                host=args.ui_host,
                port=int(args.ui_port),
                config=cfg,
                counters=counters,
                stop_event=stop_event,
                capture=cap,
                base_dir=base_dir,
            )
            cap.stop()
            return 0

        if capture_backend == "scapy":
            sniffer = PcapSniffer(interface=args.interface, counters=counters, stop_event=stop_event, bpf_filter=cfg.bpf_filter)
        else:
            sniffer = TcpdumpSniffer(interface=args.interface, counters=counters, stop_event=stop_event, bpf_filter=cfg.bpf_filter)
        sniffer.start()

        engine.run(counts_provider=counters.snapshot_and_reset, stop_event=stop_event)
    finally:
        stop_event.set()
        try:
            sniffer.join(timeout=1.0)  # type: ignore[name-defined]
        except Exception:
            pass

    return 0
