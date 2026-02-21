#!/usr/bin/env bash
set -euo pipefail

# Crée les dossiers "configs/" et "environments/" et y déplace/écrit les presets.
#
# - Déplace les fichiers flow_sonify_*.json depuis la racine vers configs/ (si possible)
# - Exporte les environments présents dans un fichier de config vers environments/*.json
#
# Note: si certains fichiers appartiennent à root, exécute ce script avec sudo.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p configs environments

echo "[migrate] configs/ et environments/ créés."

shopt -s nullglob
for f in flow_sonify_*.json; do
  if [[ -f "$f" ]]; then
    echo "[migrate] move $f -> configs/$f"
    mv -n "$f" "configs/$f" || true
  fi
done

PYTHONPATH="src" python3 - <<'PY'
import json
from pathlib import Path

root = Path(".")
env_dir = root / "environments"
env_dir.mkdir(parents=True, exist_ok=True)

def safe_stem(name: str) -> str:
    out = []
    for ch in name.strip():
        out.append(ch if (ch.isalnum() or ch in "-_") else "_")
    stem = "".join(out).strip("_") or "environment"
    return stem

def write_env(name: str, env_raw: dict) -> None:
    stem = safe_stem(name)
    p = env_dir / f"{stem}.json"
    if p.exists():
        try:
            ex = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(ex, dict) and (ex.get("name") == name):
                return
        except Exception:
            pass
        i = 2
        while True:
            cand = env_dir / f"{stem}_{i}.json"
            if not cand.exists():
                p = cand
                break
            i += 1
    payload = {"name": name, "river": env_raw.get("river", {}) or {}, "channels": env_raw.get("channels", {}) or {}}
    p.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

# export from configs/*.json (and root just in case)
paths = list((root / "configs").glob("*.json")) + list(root.glob("flow_sonify_*.json"))
for p in paths:
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        continue
    envs = raw.get("environments")
    if not isinstance(envs, dict):
        continue
    for name, env_raw in envs.items():
        if not isinstance(env_raw, dict):
            continue
        write_env(str(name), env_raw)

print("[migrate] export presets -> environments/: ok")
PY

echo "[migrate] terminé."

