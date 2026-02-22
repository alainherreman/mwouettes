from __future__ import annotations

from dataclasses import dataclass
import ipaddress
from typing import Iterable


@dataclass(frozen=True)
class CompiledIpTrack:
    direction: str  # "in" | "out"
    spec: str  # user/canonical string (stored)
    network: ipaddress.IPv4Network | ipaddress.IPv6Network
    key: str  # channel key to increment (must match config.channels)
    prefixlen: int  # for precedence (higher = more specific)
    exact: bool


def _parse_ipv4_partial(value: str) -> ipaddress.IPv4Network | None:
    s = (value or "").strip()
    if not s:
        return None
    s = s.rstrip(".")
    if not s:
        return None
    parts = s.split(".")
    if not (1 <= len(parts) <= 4):
        return None
    nums: list[int] = []
    for p in parts:
        if p == "":
            return None
        if not p.isdigit():
            return None
        n = int(p, 10)
        if n < 0 or n > 255:
            return None
        nums.append(n)
    if len(nums) == 4:
        ip = ipaddress.IPv4Address(".".join(str(x) for x in nums))
        return ipaddress.IPv4Network(f"{ip}/32", strict=False)
    # partial => network
    padded = nums + [0] * (4 - len(nums))
    ip = ipaddress.IPv4Address(".".join(str(x) for x in padded))
    prefix = 8 * len(nums)
    return ipaddress.IPv4Network(f"{ip}/{prefix}", strict=False)


def parse_ip_spec(spec: str) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, str, bool]:
    """
    Parse a user spec into (network, canonical_str, exact).

    Accepted forms:
      - Exact IP: "8.8.8.8", "2001:db8::1"
      - CIDR: "151.101.0.0/16", "2001:db8::/32"
      - IPv4 partial (with or without trailing dot): "151", "151.", "151.101", "151.101.", "151.101.64"

    For exact IPs, canonical_str is the ip string (no /32).
    For networks, canonical_str is the network string (with /prefix).
    """
    s = (spec or "").strip()
    if not s:
        raise ValueError("spec vide")

    if "/" in s:
        try:
            net = ipaddress.ip_network(s, strict=False)
        except Exception as e:
            raise ValueError(f"CIDR invalide: {spec}") from e
        exact = net.prefixlen in (32, 128) and str(net.network_address) == str(getattr(net, "network_address", ""))
        # For /32,/128 we still treat as network; users probably meant exact.
        if net.prefixlen in (32, 128):
            ip = ipaddress.ip_address(str(net.network_address))
            return ipaddress.ip_network(f"{ip}/{net.max_prefixlen}", strict=False), str(ip), True
        return net, str(net), False

    # IPv6 exact
    if ":" in s:
        try:
            ip = ipaddress.ip_address(s)
        except Exception as e:
            raise ValueError(f"IPv6 invalide: {spec}") from e
        net = ipaddress.ip_network(f"{ip}/{ip.max_prefixlen}", strict=False)
        return net, str(ip), True

    # IPv4 exact or partial
    net4 = _parse_ipv4_partial(s)
    if net4 is None:
        raise ValueError(f"IPv4 invalide: {spec}")
    if net4.prefixlen == 32:
        ip = ipaddress.IPv4Address(str(net4.network_address))
        return ipaddress.ip_network(f"{ip}/32", strict=False), str(ip), True
    return net4, str(net4), False


def ip_track_key(direction: str, canonical: str) -> str:
    d = (direction or "").strip().lower()
    if d not in ("in", "out"):
        raise ValueError("direction invalide")
    # Use a stable, human-readable key. Avoid creating unbounded variants; caller should pass canonical.
    return f"{d}.ip.{canonical}"


def compile_ip_tracks(direction: str, specs: Iterable[str]) -> list[CompiledIpTrack]:
    compiled: dict[str, CompiledIpTrack] = {}
    d = (direction or "").strip().lower()
    if d not in ("in", "out"):
        return []

    for raw in specs or []:
        if raw is None:
            continue
        s = str(raw).strip()
        if not s:
            continue
        net, canonical, exact = parse_ip_spec(s)
        key = ip_track_key(d, canonical)
        rule = CompiledIpTrack(direction=d, spec=canonical, network=net, key=key, prefixlen=int(net.prefixlen), exact=exact)
        # Deduplicate by key; keep the most specific (should be identical anyway).
        prev = compiled.get(key)
        if prev is None or rule.prefixlen > prev.prefixlen:
            compiled[key] = rule

    return sorted(compiled.values(), key=lambda r: (-r.prefixlen, r.key))


def best_match_key(compiled: list[CompiledIpTrack], ip_value: str) -> str | None:
    """
    Returns the most specific matching track key for this ip (or None).
    """
    try:
        ip = ipaddress.ip_address(str(ip_value))
    except Exception:
        return None
    best: CompiledIpTrack | None = None
    for r in compiled or []:
        # Skip version mismatch quickly.
        if getattr(r.network, "version", None) != getattr(ip, "version", None):
            continue
        try:
            if ip in r.network:
                if best is None or r.prefixlen > best.prefixlen:
                    best = r
        except Exception:
            continue
    return best.key if best else None

