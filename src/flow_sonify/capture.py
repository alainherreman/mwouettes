from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import ipaddress
import json
import os
import re
import shutil
import subprocess
import threading
import time
from typing import Iterable


@dataclass(frozen=True)
class PacketEvent:
    key: str


class TrafficCounters:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counter: Counter[str] = Counter()

    def incr_many(self, keys: Iterable[str]) -> None:
        with self._lock:
            for k in keys:
                self._counter[k] += 1

    def snapshot_and_reset(self) -> Counter[str]:
        with self._lock:
            snap = self._counter
            self._counter = Counter()
            return snap


def find_exe(name: str) -> str | None:
    p = shutil.which(name)
    if p:
        return p
    for cand in (f"/usr/sbin/{name}", f"/usr/bin/{name}", f"/sbin/{name}", f"/bin/{name}"):
        try:
            if os.path.isfile(cand) and os.access(cand, os.X_OK):
                return cand
        except Exception:
            continue
    return None


def list_interfaces() -> list[str]:
    """
    Liste les interfaces disponibles.
    - Linux: /sys/class/net
    - Fallback: `ip link show`
    """
    try:
        from pathlib import Path

        net_dir = Path("/sys/class/net")
        if net_dir.is_dir():
            names = sorted(p.name for p in net_dir.iterdir() if p.name)
            if names:
                return names
    except Exception:
        pass

    ip_bin = find_exe("ip")
    if ip_bin is not None:
        try:
            out = subprocess.check_output([ip_bin, "-o", "link", "show"], text=True, stderr=subprocess.STDOUT)
            names: list[str] = []
            for line in out.splitlines():
                parts = line.split(":", 2)
                if len(parts) >= 2:
                    name = parts[1].strip().split("@", 1)[0]
                    if name:
                        names.append(name)
            return sorted(set(names))
        except Exception:
            pass

    return []


def _normalize_ip(value: str) -> str:
    try:
        return str(ipaddress.ip_address(value))
    except Exception:
        return value


def classify_packet(packet: object, local_ips: set[str]) -> list[str]:
    """
    Retourne des clés d'événements du type:
      - in.tcp / out.tcp
      - in.udp / out.udp
      - in.icmp / out.icmp
      - in.dns / out.dns
      - in.total / out.total
    """
    keys_set: set[str] = set()

    # Import scapy de façon lazy pour permettre --dry-run sans dépendance.
    try:
        from scapy.layers.inet import ICMP, IP, TCP, UDP
        from scapy.layers.inet6 import IPv6
    except Exception:
        return keys

    direction = "unknown"
    src_ip = None
    dst_ip = None

    if packet.haslayer(IP):  # type: ignore[attr-defined]
        ip = packet.getlayer(IP)  # type: ignore[attr-defined]
        src_ip = _normalize_ip(str(ip.src))
        dst_ip = _normalize_ip(str(ip.dst))
    elif packet.haslayer(IPv6):  # type: ignore[attr-defined]
        ip6 = packet.getlayer(IPv6)  # type: ignore[attr-defined]
        src_ip = _normalize_ip(str(ip6.src))
        dst_ip = _normalize_ip(str(ip6.dst))

    if src_ip is not None and src_ip in local_ips:
        direction = "out"
    elif dst_ip is not None and dst_ip in local_ips:
        direction = "in"

    if direction in ("in", "out"):
        keys_set.add(f"{direction}.total")
    # Toujours compter un total, même si la direction est inconnue (ex: local_ips vide).
    keys_set.add("net.total")

    proto = None
    sport = None
    dport = None

    if packet.haslayer(TCP):  # type: ignore[attr-defined]
        proto = "tcp"
        tcp = packet.getlayer(TCP)  # type: ignore[attr-defined]
        sport = int(tcp.sport)
        dport = int(tcp.dport)
    elif packet.haslayer(UDP):  # type: ignore[attr-defined]
        proto = "udp"
        udp = packet.getlayer(UDP)  # type: ignore[attr-defined]
        sport = int(udp.sport)
        dport = int(udp.dport)
    elif packet.haslayer(ICMP):  # type: ignore[attr-defined]
        proto = "icmp"

    if proto is not None:
        keys_set.add(f"{proto}.total")
        if direction in ("in", "out"):
            keys_set.add(f"{direction}.{proto}")

    # Services (simple heuristique par port)
    if proto in ("tcp", "udp") and (sport is not None and dport is not None):
        if sport == 53 or dport == 53:
            keys_set.add("dns.total")
            if direction in ("in", "out"):
                keys_set.add(f"{direction}.dns")

    return sorted(keys_set)


def get_local_ips_for_iface(interface: str) -> set[str]:
    """
    Obtient les IPs locales associées à l'interface.

    Priorité:
      1) `ip -j addr show dev <iface>` (Linux)
      2) scapy (si installé)
    """
    ips: set[str] = set()

    ip_bin = find_exe("ip")
    if ip_bin is not None:
        try:
            out = subprocess.check_output([ip_bin, "-j", "addr", "show", "dev", interface], text=True)
            data = json.loads(out)
            for link in data if isinstance(data, list) else []:
                for addr in link.get("addr_info", []) or []:
                    local = addr.get("local")
                    if isinstance(local, str) and local:
                        if local != "0.0.0.0":
                            ips.add(_normalize_ip(local))
        except Exception:
            # Fallback non-JSON (plus portable).
            try:
                out4 = subprocess.check_output([ip_bin, "-o", "-4", "addr", "show", "dev", interface], text=True)
                for line in out4.splitlines():
                    m = re.search(r"\binet\s+(\S+?)(?:/\d+)?\b", line)
                    if m:
                        ips.add(_normalize_ip(m.group(1).split("/", 1)[0]))
            except Exception:
                pass
            try:
                out6 = subprocess.check_output([ip_bin, "-o", "-6", "addr", "show", "dev", interface], text=True)
                for line in out6.splitlines():
                    m = re.search(r"\binet6\s+(\S+?)(?:/\d+)?\b", line)
                    if m:
                        ips.add(_normalize_ip(m.group(1).split("/", 1)[0]))
            except Exception:
                pass

    if ips:
        return ips

    try:
        from scapy.all import get_if_addr, get_if_addr6
    except Exception:
        return ips

    try:
        v4 = get_if_addr(interface)
        if v4 and v4 != "0.0.0.0":
            ips.add(_normalize_ip(v4))
    except Exception:
        pass

    try:
        v6s = get_if_addr6(interface)
        if isinstance(v6s, (list, tuple)):
            for item in v6s:
                if isinstance(item, (list, tuple)) and item:
                    ips.add(_normalize_ip(str(item[0])))
                elif isinstance(item, str):
                    ips.add(_normalize_ip(item))
        elif isinstance(v6s, str):
            ips.add(_normalize_ip(v6s))
    except Exception:
        pass

    return ips


class PcapSniffer(threading.Thread):
    def __init__(
        self,
        *,
        interface: str,
        counters: TrafficCounters,
        stop_event: threading.Event,
        bpf_filter: str = "",
    ) -> None:
        super().__init__(daemon=True)
        self.interface = interface
        self.counters = counters
        self.stop_event = stop_event
        self.bpf_filter = bpf_filter

        self.local_ips = get_local_ips_for_iface(interface)

    def run(self) -> None:
        try:
            from scapy.all import sniff
        except Exception:
            return

        def on_packet(pkt: object) -> None:
            if self.stop_event.is_set():
                return
            keys = classify_packet(pkt, self.local_ips)
            if keys:
                self.counters.incr_many(keys)

        kwargs = {
            "iface": self.interface,
            "store": False,
            "prn": on_packet,
            "stop_filter": lambda _pkt: self.stop_event.is_set(),
        }
        if self.bpf_filter:
            kwargs["filter"] = self.bpf_filter

        try:
            sniff(**kwargs)
        except Exception as e:
            # Typiquement: permissions (CAP_NET_RAW), interface invalide, libpcap manquant…
            import sys

            print(f"[flow-sonify] capture error: {e}", file=sys.stderr)
            self.stop_event.set()


_TCPDUMP_RE = re.compile(r"\b(IP6?)\b\s+(\S+)\s+>\s+(\S+):\s+(.*)$")


def _split_endpoint(ep: str) -> tuple[str | None, int | None]:
    """
    tcpdump utilise souvent `ip.port` (IPv4/IPv6). Retourne (ip, port?).
    """
    if ep.endswith(","):
        ep = ep[:-1]
    if ":" in ep:
        # IPv6: port après le dernier '.'
        m = re.match(r"^(?P<ip>.+)\.(?P<port>\d+)$", ep)
        if m:
            return _normalize_ip(m.group("ip")), int(m.group("port"))
        return _normalize_ip(ep), None

    parts = ep.split(".")
    if len(parts) == 5 and parts[-1].isdigit():
        return _normalize_ip(".".join(parts[:4])), int(parts[4])
    return _normalize_ip(ep), None


def _proto_from_tail(tail: str) -> str | None:
    t = tail.upper()
    if "UDP" in t:
        return "udp"
    if "ICMP" in t:
        return "icmp"
    if "FLAGS" in t or "SEQ" in t or "ACK" in t:
        return "tcp"
    return None


def classify_tcpdump_line(line: str, local_ips: set[str]) -> list[str]:
    m = _TCPDUMP_RE.search(line)
    if not m:
        return []

    _ip_kind, src_ep, dst_ep, tail = m.groups()
    src_ip, src_port = _split_endpoint(src_ep)
    dst_ip, dst_port = _split_endpoint(dst_ep)

    direction = "unknown"
    if src_ip is not None and src_ip in local_ips:
        direction = "out"
    elif dst_ip is not None and dst_ip in local_ips:
        direction = "in"

    keys_set: set[str] = set()
    if direction in ("in", "out"):
        keys_set.add(f"{direction}.total")
    keys_set.add("net.total")

    proto = _proto_from_tail(tail)
    if proto is not None:
        keys_set.add(f"{proto}.total")
        if direction in ("in", "out"):
            keys_set.add(f"{direction}.{proto}")

    if direction in ("in", "out") and proto in ("tcp", "udp"):
        if src_port == 53 or dst_port == 53:
            keys_set.add(f"{direction}.dns")
            keys_set.add("dns.total")
    elif proto in ("tcp", "udp") and (src_port == 53 or dst_port == 53):
        keys_set.add("dns.total")

    return sorted(keys_set)


class TcpdumpSniffer(threading.Thread):
    def __init__(
        self,
        *,
        interface: str,
        counters: TrafficCounters,
        stop_event: threading.Event,
        bpf_filter: str = "",
    ) -> None:
        super().__init__(daemon=True)
        self.interface = interface
        self.counters = counters
        self.stop_event = stop_event
        self.bpf_filter = bpf_filter

        self.local_ips = get_local_ips_for_iface(interface)
        self._proc: subprocess.Popen[str] | None = None

    def run(self) -> None:
        import sys

        tcpdump = find_exe("tcpdump")
        if tcpdump is None:
            print("[flow-sonify] tcpdump introuvable (installez-le ou utilisez le backend scapy).", file=sys.stderr)
            self.stop_event.set()
            return

        cmd = [tcpdump, "-l", "-n", "-tt", "-q", "-i", self.interface]
        if self.bpf_filter:
            cmd.append(self.bpf_filter)

        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except Exception as e:
            print(f"[flow-sonify] tcpdump launch error: {e}", file=sys.stderr)
            self.stop_event.set()
            return

        assert self._proc.stdout is not None
        # Poll stderr occasionally for early failures.
        stderr = self._proc.stderr
        last_stderr_check = time.monotonic()

        try:
            for line in self._proc.stdout:
                if self.stop_event.is_set():
                    break
                keys = classify_tcpdump_line(line, self.local_ips)
                if keys:
                    self.counters.incr_many(keys)

                now = time.monotonic()
                if stderr is not None and now - last_stderr_check > 0.5:
                    last_stderr_check = now
                    if self._proc.poll() is not None:
                        err = stderr.read() if stderr else ""
                        if err:
                            print(f"[flow-sonify] tcpdump error: {err.strip()}", file=sys.stderr)
                        self.stop_event.set()
                        break
        finally:
            self._terminate()

    def _terminate(self) -> None:
        proc = self._proc
        if proc is None:
            return
        try:
            if proc.poll() is None:
                proc.terminate()
        except Exception:
            pass


class CaptureManager:
    def __init__(
        self,
        *,
        counters: TrafficCounters,
        app_stop_event: threading.Event,
        capture_backend: str = "auto",
        bpf_filter: str = "",
    ) -> None:
        self.counters = counters
        self.app_stop_event = app_stop_event
        self.capture_backend = capture_backend
        self.bpf_filter = bpf_filter

        self._lock = threading.Lock()
        self._sniffer: threading.Thread | None = None
        self._sniffer_stop: threading.Event | None = None
        self._interface: str | None = None
        self._backend_used: str | None = None

    @property
    def interface(self) -> str | None:
        with self._lock:
            return self._interface

    @property
    def backend_used(self) -> str | None:
        with self._lock:
            return self._backend_used

    def set_interface(self, interface: str | None) -> None:
        iface = (interface or "").strip()
        if not iface:
            self._stop_current()
            with self._lock:
                self._interface = None
                self._backend_used = None
            return

        self._stop_current()

        backend = (self.capture_backend or "auto").lower()
        if backend == "auto":
            backend = "tcpdump" if find_exe("tcpdump") is not None else "scapy"

        stop = threading.Event()
        if backend == "scapy":
            try:
                import scapy  # noqa: F401
            except Exception as e:
                raise ValueError(f"backend scapy indisponible: {e}") from e
            sniffer = PcapSniffer(interface=iface, counters=self.counters, stop_event=stop, bpf_filter=self.bpf_filter)
        else:
            if find_exe("tcpdump") is None:
                raise ValueError("backend tcpdump indisponible: `tcpdump` introuvable")
            sniffer = TcpdumpSniffer(interface=iface, counters=self.counters, stop_event=stop, bpf_filter=self.bpf_filter)

        sniffer.start()

        def stop_on_app_exit() -> None:
            self.app_stop_event.wait()
            stop.set()

        threading.Thread(target=stop_on_app_exit, daemon=True).start()

        with self._lock:
            self._sniffer = sniffer
            self._sniffer_stop = stop
            self._interface = iface
            self._backend_used = backend

    def _stop_current(self) -> None:
        sniffer: threading.Thread | None
        stopper: threading.Event | None
        with self._lock:
            sniffer = self._sniffer
            stopper = self._sniffer_stop
            self._sniffer = None
            self._sniffer_stop = None
            self._backend_used = None
            self._interface = None

        if stopper is not None:
            stopper.set()
        if sniffer is not None:
            sniffer.join(timeout=1.0)

    def stop(self) -> None:
        self._stop_current()
