from __future__ import annotations

from dataclasses import asdict
import json
import queue
import threading
import time
import cgi
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any
import re

from .capture import CaptureManager, TrafficCounters, list_interfaces
from .config import AppConfig, parse_config


_BASE_DIR = Path.cwd().resolve()


def set_base_dir(p: str | Path) -> None:
    """
    Définit le répertoire de travail "logique" pour l'UI:
      - samples/ est relatif à ce répertoire
      - environments/ est relatif à ce répertoire
      - save_config() (si chemin relatif) écrit relatif à ce répertoire
    """
    global _BASE_DIR
    _BASE_DIR = Path(p).resolve()


def _maybe_chown_to_sudo_user(p: Path) -> None:
    """
    Quand l'app tourne sous sudo, évite de laisser des fichiers root-owned dans le dépôt.
    Best-effort (ignore les erreurs).
    """
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


class EventBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: list[queue.Queue[dict[str, Any]]] = []

    def subscribe(self) -> queue.Queue[dict[str, Any]]:
        q: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=20)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue[dict[str, Any]]) -> None:
        with self._lock:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass

    def publish(self, event: dict[str, Any]) -> None:
        with self._lock:
            subs = list(self._subscribers)
        for q in subs:
            try:
                q.put_nowait(event)
            except queue.Full:
                try:
                    _ = q.get_nowait()
                except Exception:
                    pass
                try:
                    q.put_nowait(event)
                except Exception:
                    pass


class UiState:
    def __init__(
        self,
        *,
        config: AppConfig,
        counters: TrafficCounters,
        stop_event: threading.Event,
        capture: CaptureManager | None = None,
    ) -> None:
        self._lock = threading.Lock()
        # Merge presets from ./environments so the UI can always list/apply them.
        self._config = _merge_env_dir_into_config(config)
        self.counters = counters
        self.stop_event = stop_event
        self.bus = EventBus()
        self.capture = capture

    def get_config(self) -> AppConfig:
        with self._lock:
            return self._config

    def update_config(self, patch: dict[str, Any]) -> AppConfig:
        with self._lock:
            current = config_to_raw(self._config)
            merged = deep_merge(current, patch)
            self._config = parse_config(merged)
            return self._config

    def apply_environment(self, name: str) -> AppConfig:
        with self._lock:
            raw = config_to_raw(self._config)
            envs = raw.get("environments", {}) or {}
            if not isinstance(envs, dict) or name not in envs:
                raise ValueError(f"environment not found: {name}")
            env_raw = envs[name]
            if not isinstance(env_raw, dict):
                raise ValueError("invalid environment spec")
            raw["active_environment"] = str(name)
            if "river" in env_raw:
                raw["river"] = env_raw["river"]
            if "channels" in env_raw:
                raw["channels"] = env_raw["channels"]
            self._config = parse_config(raw)
            return self._config

    def save_environment(self, name: str, *, overwrite: bool) -> AppConfig:
        with self._lock:
            raw = config_to_raw(self._config)
            envs = raw.get("environments", {}) or {}
            if not isinstance(envs, dict):
                envs = {}
            if (name in envs) and not overwrite:
                raise ValueError(f"environment already exists: {name}")

            envs[str(name)] = {
                "river": raw.get("river", {}),
                "channels": raw.get("channels", {}),
            }
            try:
                _write_env_file(str(name), envs[str(name)])
            except Exception:
                # best-effort: still keep it in-memory
                pass
            raw["environments"] = envs
            raw["active_environment"] = str(name)
            self._config = parse_config(raw)
            return self._config

    def save_config(self, path: str | Path) -> Path:
        p = Path(path)
        if not p.is_absolute():
            p = (_BASE_DIR / p).resolve()
        raw = config_to_raw(self.get_config())
        p.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _maybe_chown_to_sudo_user(p)
        return p


def config_to_raw(cfg: AppConfig) -> dict[str, Any]:
    return {
        "sample_rate": cfg.sample_rate,
        "block_ms": cfg.block_ms,
        "bpf_filter": cfg.bpf_filter,
        "river": asdict(cfg.river),
        "channels": {k: asdict(v) for k, v in cfg.channels.items()},
        "active_environment": cfg.active_environment,
        "environments": {
            name: {
                "river": asdict(env.river),
                "channels": {k: asdict(v) for k, v in env.channels.items()},
            }
            for name, env in cfg.environments.items()
        },
    }


def deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)  # type: ignore[arg-type]
        else:
            out[k] = v
    return out


def _load_asset(name: str) -> tuple[bytes, str]:
    # assets live in package flow_sonify.web
    pkg = "flow_sonify.web"
    if name.endswith(".html"):
        ctype = "text/html; charset=utf-8"
    elif name.endswith(".js"):
        ctype = "text/javascript; charset=utf-8"
    elif name.endswith(".css"):
        ctype = "text/css; charset=utf-8"
    else:
        ctype = "application/octet-stream"
    data = resources.files(pkg).joinpath(name).read_bytes()
    return data, ctype


def _samples_dir() -> Path:
    return (_BASE_DIR / "samples").resolve()


def _environments_dir() -> Path:
    return (_BASE_DIR / "environments").resolve()


def _recordings_dir() -> Path:
    return (_BASE_DIR / "recordings").resolve()


def _safe_env_file_stem(name: str) -> str:
    stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", (name or "").strip()).strip("_")
    return stem or "environment"


def _load_env_files() -> dict[str, dict[str, Any]]:
    """
    Charge les presets depuis ./environments/*.json.
    Format d'un fichier:
      {"name": "...", "river": {...}, "channels": {...}}
    (le champ "name" est optionnel; sinon le stem du fichier est utilisé)
    """
    d = _environments_dir()
    if not d.exists() or not d.is_dir():
        return {}
    out: dict[str, dict[str, Any]] = {}
    for p in sorted(d.glob("*.json")):
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name") or p.stem)
            env_raw = {
                "river": raw.get("river", {}) or {},
                "channels": raw.get("channels", {}) or {},
            }
            if not isinstance(env_raw["river"], dict) or not isinstance(env_raw["channels"], dict):
                continue
            out[name] = env_raw
        except Exception:
            continue
    return out


def _write_env_file(name: str, env_raw: dict[str, Any]) -> Path:
    d = _environments_dir()
    d.mkdir(parents=True, exist_ok=True)
    stem = _safe_env_file_stem(name)
    p = (d / f"{stem}.json").resolve()
    # avoid clobbering an unrelated env if names collide
    if p.exists():
        try:
            existing = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(existing, dict) and str(existing.get("name") or stem) != name:
                i = 2
                while True:
                    cand = (d / f"{stem}_{i}.json").resolve()
                    if not cand.exists():
                        p = cand
                        break
                    i += 1
        except Exception:
            pass
    payload = {"name": name, "river": env_raw.get("river", {}) or {}, "channels": env_raw.get("channels", {}) or {}}
    p.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _maybe_chown_to_sudo_user(p)
    return p


def _merge_env_dir_into_config(cfg: AppConfig) -> AppConfig:
    raw = config_to_raw(cfg)
    envs = raw.get("environments", {}) or {}
    if not isinstance(envs, dict):
        envs = {}
    loaded = _load_env_files()
    if loaded:
        envs.update(loaded)
        raw["environments"] = envs
    return parse_config(raw)


def list_samples() -> list[str]:
    d = _samples_dir()
    if not d.exists() or not d.is_dir():
        return []
    out: list[str] = []
    for p in d.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() not in (".wav", ".mp3", ".ogg", ".oga"):
            continue
        name = p.name
        low = name.lower()
        # Hide intermediate/script-generated sources (keeps UI clean).
        if low.endswith(("_full.ogg", "_full.oga", "_full.wav", "_full.mp3")):
            continue
        if ".tmp." in low:
            continue
        out.append(name)
    return sorted(out)


def _safe_sample_path(name: str) -> Path | None:
    if name.startswith("@"):
        return None
    if "/" in name or "\\" in name:
        return None
    d = _samples_dir()
    p = (d / name).resolve()
    try:
        p.relative_to(d)
    except Exception:
        return None
    if not p.is_file():
        return None
    if p.suffix.lower() not in (".wav", ".mp3", ".ogg", ".oga"):
        return None
    return p


class UiHandler(BaseHTTPRequestHandler):
    server: "UiServer"  # type: ignore[assignment]

    def log_message(self, fmt: str, *args: object) -> None:
        # keep default noisy logs off; uncomment for debugging
        return

    def _json(self, status: int, obj: Any) -> None:
        data = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _bytes(self, status: int, data: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/" or self.path.startswith("/index.html"):
            data, ctype = _load_asset("index.html")
            self._bytes(200, data, ctype)
            return
        if self.path == "/app.js":
            data, ctype = _load_asset("app.js")
            self._bytes(200, data, ctype)
            return
        if self.path == "/style.css":
            data, ctype = _load_asset("style.css")
            self._bytes(200, data, ctype)
            return

        if self.path == "/api/config":
            cfg = self.server.state.get_config()
            self._json(200, config_to_raw(cfg))
            return

        if self.path == "/api/interfaces":
            self._json(200, {"interfaces": list_interfaces()})
            return

        if self.path == "/api/interface":
            cap = self.server.state.capture
            self._json(
                200,
                {
                    "interface": cap.interface if cap else None,
                    "backend": cap.backend_used if cap else None,
                    "running": cap.running if cap else False,
                    "error": cap.last_error if cap else None,
                },
            )
            return

        if self.path == "/api/samples":
            self._json(200, {"samples": list_samples()})
            return

        if self.path.startswith("/samples/"):
            name = self.path[len("/samples/") :]
            p = _safe_sample_path(name)
            if p is None:
                self.send_response(HTTPStatus.NOT_FOUND)
                self.end_headers()
                return
            data = p.read_bytes()
            suffix = p.suffix.lower()
            if suffix == ".wav":
                ctype = "audio/wav"
            elif suffix == ".mp3":
                ctype = "audio/mpeg"
            elif suffix in (".ogg", ".oga"):
                ctype = "audio/ogg"
            else:
                ctype = "application/octet-stream"
            self._bytes(200, data, ctype)
            return

        if self.path == "/api/events":
            self._handle_sse()
            return

        self.send_response(HTTPStatus.NOT_FOUND)
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/config":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
                patch = json.loads(raw)
                if not isinstance(patch, dict):
                    raise ValueError("patch must be an object")
                cfg = self.server.state.update_config(patch)
                self._json(200, config_to_raw(cfg))
            except Exception as e:
                self._json(400, {"error": str(e)})
            return

        if self.path == "/api/env/apply":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
                body = json.loads(raw)
                if not isinstance(body, dict) or "name" not in body:
                    raise ValueError("body must contain 'name'")
                cfg = self.server.state.apply_environment(str(body["name"]))
                self._json(200, config_to_raw(cfg))
            except Exception as e:
                self._json(400, {"error": str(e)})
            return

        if self.path == "/api/env/save":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
                body = json.loads(raw)
                if not isinstance(body, dict) or "name" not in body:
                    raise ValueError("body must contain 'name'")
                overwrite = bool(body.get("overwrite", False))
                cfg = self.server.state.save_environment(str(body["name"]), overwrite=overwrite)
                self._json(200, config_to_raw(cfg))
            except Exception as e:
                self._json(400, {"error": str(e)})
            return

        if self.path == "/api/interface":
            try:
                cap = self.server.state.capture
                if cap is None:
                    raise ValueError("capture manager not available")
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
                body = json.loads(raw)
                if not isinstance(body, dict) or "interface" not in body:
                    raise ValueError("body must contain 'interface'")
                cap.set_interface(str(body["interface"]))
                self._json(
                    200,
                    {
                        "interface": cap.interface,
                        "backend": cap.backend_used,
                        "running": cap.running,
                        "error": cap.last_error,
                    },
                )
            except Exception as e:
                self._json(400, {"error": str(e)})
            return

        if self.path == "/api/upload":
            try:
                saved = self._handle_upload()
                self._json(200, {"saved": saved, "samples": list_samples()})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return

        if self.path == "/api/recordings/save":
            try:
                saved = self._handle_save_recording()
                self._json(200, {"saved": saved})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return

        if self.path == "/api/save":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
                body = json.loads(raw)
                if not isinstance(body, dict) or "path" not in body:
                    raise ValueError("body must contain 'path'")
                path = str(body["path"])
                saved = self.server.state.save_config(path)
                self._json(200, {"saved": str(saved)})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return

        self.send_response(HTTPStatus.NOT_FOUND)
        self.end_headers()

    def _handle_upload(self) -> str:
        ctype, pdict = cgi.parse_header(self.headers.get("Content-Type", ""))
        if ctype != "multipart/form-data":
            raise ValueError("expected multipart/form-data")

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": self.headers.get("Content-Type", "")},
        )

        if "file" not in form:
            raise ValueError("missing field 'file'")
        field = form["file"]
        if not getattr(field, "filename", None):
            raise ValueError("missing filename")

        filename = Path(str(field.filename)).name
        if not filename:
            raise ValueError("invalid filename")

        ext = Path(filename).suffix.lower()
        if ext not in (".wav", ".mp3", ".ogg"):
            raise ValueError("unsupported file type (wav/mp3/ogg)")

        target_dir = _samples_dir()
        target_dir.mkdir(parents=True, exist_ok=True)
        stem = Path(filename).stem
        safe_stem = "".join(ch for ch in stem if ch.isalnum() or ch in ("-", "_", " "))
        safe_stem = safe_stem.strip().replace(" ", "_") or "sample"
        base = safe_stem + ext
        out = target_dir / base
        i = 2
        while out.exists():
            out = target_dir / f"{safe_stem}_{i}{ext}"
            i += 1

        data = field.file.read()
        out.write_bytes(data)
        _maybe_chown_to_sudo_user(out)
        return out.name

    def _handle_save_recording(self) -> str:
        ctype, pdict = cgi.parse_header(self.headers.get("Content-Type", ""))
        if ctype != "multipart/form-data":
            raise ValueError("expected multipart/form-data")

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": self.headers.get("Content-Type", "")},
        )

        if "file" not in form:
            raise ValueError("missing field 'file'")
        field = form["file"]
        if not getattr(field, "filename", None):
            raise ValueError("missing filename")

        filename = Path(str(field.filename)).name
        if not filename:
            raise ValueError("invalid filename")

        ext = Path(filename).suffix.lower()
        if ext not in (".webm", ".ogg", ".wav"):
            raise ValueError("unsupported file type (webm/ogg/wav)")

        target_dir = _recordings_dir()
        target_dir.mkdir(parents=True, exist_ok=True)

        stem = Path(filename).stem
        safe_stem = "".join(ch for ch in stem if ch.isalnum() or ch in ("-", "_", " "))
        safe_stem = safe_stem.strip().replace(" ", "_") or "mwouettes-recording"
        base = safe_stem + ext
        out = target_dir / base
        i = 2
        while out.exists():
            out = target_dir / f"{safe_stem}_{i}{ext}"
            i += 1

        data = field.file.read()
        out.write_bytes(data)
        _maybe_chown_to_sudo_user(out)
        # return a nice relative-ish path for display
        try:
            return str(out.relative_to(_BASE_DIR))
        except Exception:
            return str(out)

    def _handle_sse(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        q = self.server.state.bus.subscribe()
        try:
            # initial ping
            self.wfile.write(b"event: ready\ndata: {}\n\n")
            self.wfile.flush()

            while not self.server.state.stop_event.is_set():
                try:
                    event = q.get(timeout=0.5)
                except queue.Empty:
                    # keep-alive comment
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
                    continue

                payload = json.dumps(event).encode("utf-8")
                self.wfile.write(b"event: tick\n")
                self.wfile.write(b"data: " + payload + b"\n\n")
                self.wfile.flush()
        except Exception:
            # client disconnected
            pass
        finally:
            self.server.state.bus.unsubscribe(q)


class UiServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], state: UiState) -> None:
        super().__init__(server_address, UiHandler)
        self.state = state


class Publisher(threading.Thread):
    def __init__(self, *, state: UiState) -> None:
        super().__init__(daemon=True)
        self.state = state

    def run(self) -> None:
        while not self.state.stop_event.is_set():
            cfg = self.state.get_config()
            block_s = max(0.02, float(cfg.block_ms) / 1000.0)
            t0 = time.monotonic()

            counts = self.state.counters.snapshot_and_reset()
            event = {
                "ts": time.time(),
                "block_ms": cfg.block_ms,
                "counts": dict(counts),
                "channels": list(cfg.channels.keys()),
            }
            self.state.bus.publish(event)

            elapsed = time.monotonic() - t0
            sleep_s = block_s - elapsed
            if sleep_s > 0:
                time.sleep(min(0.2, sleep_s))


def run_ui_server(
    *,
    host: str,
    port: int,
    config: AppConfig,
    counters: TrafficCounters,
    stop_event: threading.Event,
    capture: CaptureManager | None = None,
    base_dir: str | Path | None = None,
) -> None:
    if base_dir is not None:
        set_base_dir(base_dir)
    state = UiState(config=config, counters=counters, stop_event=stop_event, capture=capture)
    publisher = Publisher(state=state)
    publisher.start()

    httpd = UiServer((host, port), state)
    watcher_stop = threading.Event()

    def watcher() -> None:
        while not stop_event.is_set() and not watcher_stop.is_set():
            time.sleep(0.1)
        try:
            httpd.shutdown()
        except Exception:
            pass

    threading.Thread(target=watcher, daemon=True).start()
    try:
        httpd.serve_forever(poll_interval=0.25)
    finally:
        watcher_stop.set()
        stop_event.set()
        try:
            httpd.shutdown()
        except Exception:
            pass
