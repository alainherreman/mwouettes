from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

from .ip_tracks import compile_ip_tracks


@dataclass(frozen=True)
class RiverConfig:
    # filename under ./samples or builtin (@noise, @none)
    sample: str = "river.ogg"
    gain: float = 0.18
    ref_pps: float = 250.0
    gamma: float = 0.65
    cutoff_hz: float = 900.0


@dataclass(frozen=True)
class ChannelConfig:
    """
    enabled: active ou muet
    mode:
      - one-shot : évènements discrets
      - loop     : son continu en boucle (volume modulé)

    sample:
      - fichier dans ./samples
      - builtin: @chirp, @drone, @noise
    """

    enabled: bool = True
    mode: str = "one-shot"
    freq_hz: float = 1000.0
    duration_ms: int = 80  # utilisé pour chirp
    sample: str = "birds.ogg"
    gain: float = 0.12
    ref_pps: float = 50.0
    gamma: float = 0.75


@dataclass(frozen=True)
class EnvironmentConfig:
    river: RiverConfig = RiverConfig()
    channels: dict[str, ChannelConfig] = field(default_factory=lambda: default_channels())
    ip_tracks: dict[str, list[str]] = field(default_factory=dict)  # {"in":[...], "out":[...]} (canonical strings)


def default_channels() -> dict[str, "ChannelConfig"]:
    return {
        "in.tcp": ChannelConfig(mode="one-shot", sample="owl.ogg", freq_hz=1250.0, duration_ms=70, gain=0.14, ref_pps=60.0, gamma=0.70),
        "out.tcp": ChannelConfig(mode="one-shot", sample="crow.ogg", freq_hz=1050.0, duration_ms=70, gain=0.12, ref_pps=60.0, gamma=0.70),
        "in.udp": ChannelConfig(mode="one-shot", sample="cricket.ogg", freq_hz=750.0, duration_ms=90, gain=0.13, ref_pps=50.0, gamma=0.75),
        "out.udp": ChannelConfig(mode="one-shot", sample="frog.oga", freq_hz=650.0, duration_ms=90, gain=0.12, ref_pps=50.0, gamma=0.75),
        "in.icmp": ChannelConfig(mode="one-shot", sample="raven.ogg", freq_hz=1700.0, duration_ms=140, gain=0.16, ref_pps=10.0, gamma=0.80),
        "out.icmp": ChannelConfig(mode="one-shot", sample="crow.ogg", freq_hz=1500.0, duration_ms=140, gain=0.14, ref_pps=10.0, gamma=0.80),
        "in.dns": ChannelConfig(mode="one-shot", sample="birds.ogg", freq_hz=2100.0, duration_ms=60, gain=0.16, ref_pps=25.0, gamma=0.75),
        "out.dns": ChannelConfig(mode="one-shot", sample="birds.ogg", freq_hz=1950.0, duration_ms=60, gain=0.14, ref_pps=25.0, gamma=0.75),

        # Totaux direction-indépendants (évite de doubler un loop sur in.* et out.*).
        "net.total": ChannelConfig(enabled=False, mode="loop", sample="river.ogg", freq_hz=0.0, duration_ms=0, gain=0.0, ref_pps=250.0, gamma=0.65),
        "tcp.total": ChannelConfig(enabled=False, mode="loop", sample="wind.ogg", freq_hz=220.0, duration_ms=0, gain=0.0, ref_pps=120.0, gamma=0.70),
        "udp.total": ChannelConfig(enabled=False, mode="loop", sample="waves.ogg", freq_hz=180.0, duration_ms=0, gain=0.0, ref_pps=100.0, gamma=0.75),
        "icmp.total": ChannelConfig(enabled=False, mode="one-shot", sample="crow.ogg", freq_hz=1600.0, duration_ms=120, gain=0.0, ref_pps=10.0, gamma=0.80),
        "dns.total": ChannelConfig(enabled=False, mode="one-shot", sample="birds.ogg", freq_hz=2100.0, duration_ms=60, gain=0.0, ref_pps=25.0, gamma=0.75),
    }


def _with_missing_defaults(channels: dict[str, ChannelConfig]) -> dict[str, ChannelConfig]:
    """
    Garantit que la config contient *toutes* les clés standard (in/out + totaux).
    Utile pour l'UI: même si un preset ne définit que quelques canaux, on veut
    pouvoir activer/régler les autres sans les recréer.
    """
    out = dict(channels)
    for k, v in default_channels().items():
        if k not in out:
            out[k] = v
    return out


@dataclass(frozen=True)
class AppConfig:
    sample_rate: int = 48_000
    block_ms: int = 100
    bpf_filter: str = ""
    river: RiverConfig = RiverConfig()
    channels: dict[str, ChannelConfig] = field(default_factory=default_channels)

    environments: dict[str, EnvironmentConfig] = field(default_factory=dict)
    active_environment: str = ""
    ip_tracks: dict[str, list[str]] = field(default_factory=dict)  # {"in":[...], "out":[...]} (canonical strings)


def load_config(path: str | Path | None) -> AppConfig:
    if path is None:
        # Defaults should include predefined environments even without a config file.
        # This keeps the UI usable out-of-the-box (presets available immediately).
        return parse_config(_default_config_raw())

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    cfg = parse_config(raw)
    # Backward-compat / usability: if a legacy config has no environments, keep defaults.
    if not cfg.environments:
        defaults = parse_config(_default_config_raw())
        cfg = AppConfig(
            sample_rate=cfg.sample_rate,
            block_ms=cfg.block_ms,
            bpf_filter=cfg.bpf_filter,
            river=cfg.river,
            channels=cfg.channels,
            environments=defaults.environments,
            active_environment=cfg.active_environment,
        )
    return cfg


def _default_config_raw() -> dict[str, Any]:
    """
    Valeurs par défaut "prêtes à l'emploi", incluant des environnements prédéfinis.
    Les fichiers audio référencés peuvent ne pas être présents: l'UI permet de les importer
    et le moteur audio retombe sur @noise si nécessaire.
    """
    return {
        "sample_rate": 48_000,
        "block_ms": 100,
        "bpf_filter": "",
        "river": {
            "sample": "@noise",
            "gain": 0.18,
            "ref_pps": 250.0,
            "gamma": 0.65,
            "cutoff_hz": 900.0,
        },
        "active_environment": "sous-bois",
        "environments": {
            "sous-bois": {
                "river": {"sample": "river.ogg", "gain": 0.22, "ref_pps": 250.0, "gamma": 0.65, "cutoff_hz": 900.0},
                "ip_tracks": {"in": [], "out": []},
                "channels": {
                    "net.total": {"enabled": False, "mode": "loop", "sample": "river.ogg", "freq_hz": 0.0, "duration_ms": 0, "gain": 0.0, "ref_pps": 250.0, "gamma": 0.65},
                    "tcp.total": {"enabled": True, "mode": "loop", "sample": "wind.ogg", "freq_hz": 220.0, "duration_ms": 0, "gain": 0.12, "ref_pps": 140.0, "gamma": 0.70},
                    "udp.total": {"enabled": False, "mode": "loop", "sample": "waves.ogg", "freq_hz": 180.0, "duration_ms": 0, "gain": 0.0, "ref_pps": 100.0, "gamma": 0.75},
                    "dns.total": {"enabled": True, "mode": "one-shot", "sample": "birds.ogg", "freq_hz": 2100.0, "duration_ms": 60, "gain": 0.28, "ref_pps": 20.0, "gamma": 0.85},
                    "icmp.total": {"enabled": False, "mode": "one-shot", "sample": "crow.ogg", "freq_hz": 1600.0, "duration_ms": 120, "gain": 0.0, "ref_pps": 10.0, "gamma": 0.80},
                },
            },
            "bord-de-mer": {
                "river": {"sample": "waves.ogg", "gain": 0.24, "ref_pps": 250.0, "gamma": 0.65, "cutoff_hz": 900.0},
                "ip_tracks": {"in": [], "out": []},
                "channels": {
                    "net.total": {"enabled": False, "mode": "loop", "sample": "waves.ogg", "freq_hz": 0.0, "duration_ms": 0, "gain": 0.0, "ref_pps": 250.0, "gamma": 0.65},
                    "tcp.total": {"enabled": True, "mode": "loop", "sample": "wind.ogg", "freq_hz": 220.0, "duration_ms": 0, "gain": 0.12, "ref_pps": 140.0, "gamma": 0.70},
                    "udp.total": {"enabled": False, "mode": "loop", "sample": "wind.ogg", "freq_hz": 180.0, "duration_ms": 0, "gain": 0.0, "ref_pps": 100.0, "gamma": 0.75},
                    "dns.total": {"enabled": True, "mode": "one-shot", "sample": "gulls.ogg", "freq_hz": 2100.0, "duration_ms": 60, "gain": 0.30, "ref_pps": 16.0, "gamma": 0.85},
                    "icmp.total": {"enabled": False, "mode": "one-shot", "sample": "crow.ogg", "freq_hz": 1600.0, "duration_ms": 120, "gain": 0.0, "ref_pps": 10.0, "gamma": 0.80},
                },
            },
        },
        # channels is intentionally left empty: active_environment applies its channels.
        "channels": {},
    }


def _parse_ip_tracks(raw: dict[str, Any]) -> tuple[dict[str, list[str]], bool]:
    """
    Returns (ip_tracks, has_explicit_ip_tracks).
    ip_tracks format: {"in":[canonical...], "out":[canonical...]}.
    """
    if "ip_tracks" not in raw:
        return {}, False
    it = raw.get("ip_tracks")
    if it is None:
        return {}, True
    if not isinstance(it, dict):
        return {}, True
    ins = it.get("in", []) or []
    outs = it.get("out", []) or []
    in_list = [str(x).strip() for x in (ins if isinstance(ins, list) else []) if str(x).strip()]
    out_list = [str(x).strip() for x in (outs if isinstance(outs, list) else []) if str(x).strip()]
    # Canonicalize + de-duplicate via compiler (keeps stable order).
    c_in = [r.spec for r in compile_ip_tracks("in", in_list)]
    c_out = [r.spec for r in compile_ip_tracks("out", out_list)]
    return {"in": c_in, "out": c_out}, True


def _apply_ip_tracks_to_channels(channels: dict[str, ChannelConfig], ip_tracks: dict[str, list[str]]) -> dict[str, ChannelConfig]:
    compiled_in = compile_ip_tracks("in", (ip_tracks or {}).get("in", []) or [])
    compiled_out = compile_ip_tracks("out", (ip_tracks or {}).get("out", []) or [])
    wanted_keys = {r.key for r in (compiled_in + compiled_out)}

    out = dict(channels)
    # Drop stale ip.* channels that are no longer tracked.
    for k in list(out.keys()):
        if (k.startswith("in.ip.") or k.startswith("out.ip.")) and (k not in wanted_keys):
            out.pop(k, None)

    # Ensure every tracked IP has a channel entry (same UI as packets).
    for k in sorted(wanted_keys):
        if k not in out:
            out[k] = ChannelConfig(mode="one-shot", sample="birds.ogg", freq_hz=1000.0, duration_ms=80, gain=0.12, ref_pps=10.0, gamma=0.85)
    return out


def parse_config(raw: dict[str, Any]) -> AppConfig:
    sample_rate = int(raw.get("sample_rate", 48_000))
    block_ms = int(raw.get("block_ms", 100))
    bpf_filter = str(raw.get("bpf_filter", ""))

    river_raw = raw.get("river", {}) or {}
    river_sample = str(river_raw.get("sample", "@noise") or "@noise")
    # Compat ancien format river.mode=noise/sample
    legacy_river_mode = str(river_raw.get("mode", "") or "")
    if legacy_river_mode == "noise":
        river_sample = "@noise"
    elif legacy_river_mode == "sample" and (river_sample == "" or river_sample == "@noise"):
        river_sample = str(river_raw.get("sample", "") or "")

    river = RiverConfig(
        sample=river_sample or "@noise",
        gain=float(river_raw.get("gain", 0.18)),
        ref_pps=float(river_raw.get("ref_pps", 250.0)),
        gamma=float(river_raw.get("gamma", 0.65)),
        cutoff_hz=float(river_raw.get("cutoff_hz", 900.0)),
    )

    channels: dict[str, ChannelConfig] = {}

    # Nouveau format: "channels"
    channels_raw = raw.get("channels", {}) or {}
    has_explicit_channels = bool(isinstance(channels_raw, dict) and len(channels_raw) > 0)
    if isinstance(channels_raw, dict):
        for key, spec in channels_raw.items():
            if not isinstance(spec, dict):
                continue
            channels[str(key)] = _parse_channel(spec)

    # Compat: ancien format "sounds" (chirps)
    if not channels:
        sounds_raw = raw.get("sounds", {}) or {}
        if isinstance(sounds_raw, dict):
            for key, spec in sounds_raw.items():
                if not isinstance(spec, dict):
                    continue
                channels[str(key)] = ChannelConfig(
                    enabled=True,
                    mode="one-shot",
                    sample="@chirp",
                    freq_hz=float(spec.get("freq_hz", 1000.0)),
                    duration_ms=int(spec.get("duration_ms", 80)),
                    gain=float(spec.get("gain", 0.12)),
                    ref_pps=float(spec.get("ref_pps", 50.0)),
                    gamma=float(spec.get("gamma", 0.75)),
                )

    if not channels:
        channels = default_channels()
    else:
        channels = _with_missing_defaults(channels)

    environments: dict[str, EnvironmentConfig] = {}
    envs_raw = raw.get("environments", {}) or {}
    if isinstance(envs_raw, dict):
        for name, env_raw in envs_raw.items():
            if not isinstance(env_raw, dict):
                continue
            environments[str(name)] = _parse_environment(env_raw)

    active_environment = str(raw.get("active_environment", "") or "")
    ip_tracks, has_explicit_ip_tracks = _parse_ip_tracks(raw)

    # If an active environment is selected, apply it by default ONLY when no explicit
    # channel mapping was provided. In the UI, users select a preset once, then tweak
    # the current mapping; we must not re-apply the preset on every patch.
    if (not has_explicit_channels) and active_environment and active_environment in environments:
        env = environments[active_environment]
        river = env.river
        channels = env.channels
        channels = _with_missing_defaults(channels)
        if not has_explicit_ip_tracks:
            ip_tracks = env.ip_tracks or {}

    channels = _apply_ip_tracks_to_channels(channels, ip_tracks)

    return AppConfig(
        sample_rate=sample_rate,
        block_ms=block_ms,
        bpf_filter=bpf_filter,
        river=river,
        channels=channels,
        environments=environments,
        active_environment=active_environment,
        ip_tracks=ip_tracks,
    )


def _parse_channel(spec: dict[str, Any]) -> ChannelConfig:
    enabled = bool(spec.get("enabled", True))
    mode = str(spec.get("mode", "one-shot") or "one-shot").lower()
    sample = str(spec.get("sample", "birds.ogg") or "birds.ogg")

    # Compat anciens modes
    if mode == "off":
        enabled = False
        mode = "loop"
    if mode == "chirp":
        mode = "one-shot"
        if not sample:
            sample = "@chirp"
    if mode == "drone":
        mode = "loop"
        if not sample:
            sample = "@drone"
    if mode == "sample":
        mode = "one-shot"
    if mode == "loop":
        mode = "loop"

    if mode not in ("one-shot", "loop"):
        mode = "one-shot"

    return ChannelConfig(
        enabled=enabled,
        mode=mode,
        sample=sample,
        freq_hz=float(spec.get("freq_hz", 1000.0)),
        duration_ms=int(spec.get("duration_ms", 80)),
        gain=float(spec.get("gain", 0.12)),
        ref_pps=float(spec.get("ref_pps", 50.0)),
        gamma=float(spec.get("gamma", 0.75)),
    )


def _parse_environment(raw: dict[str, Any]) -> EnvironmentConfig:
    river_raw = raw.get("river", {}) or {}
    river_sample = str(river_raw.get("sample", "@noise") or "@noise")
    legacy_river_mode = str(river_raw.get("mode", "") or "")
    if legacy_river_mode == "noise":
        river_sample = "@noise"
    elif legacy_river_mode == "sample" and (river_sample == "" or river_sample == "@noise"):
        river_sample = str(river_raw.get("sample", "") or "")

    river = RiverConfig(
        sample=river_sample or "@noise",
        gain=float(river_raw.get("gain", 0.18)),
        ref_pps=float(river_raw.get("ref_pps", 250.0)),
        gamma=float(river_raw.get("gamma", 0.65)),
        cutoff_hz=float(river_raw.get("cutoff_hz", 900.0)),
    )

    channels: dict[str, ChannelConfig] = {}
    channels_raw = raw.get("channels", {}) or {}
    if isinstance(channels_raw, dict):
        for key, spec in channels_raw.items():
            if not isinstance(spec, dict):
                continue
            channels[str(key)] = _parse_channel(spec)

    if not channels:
        channels = default_channels()
    else:
        channels = _with_missing_defaults(channels)

    ip_tracks, _has = _parse_ip_tracks({"ip_tracks": raw.get("ip_tracks")})
    return EnvironmentConfig(river=river, channels=channels, ip_tracks=ip_tracks)
