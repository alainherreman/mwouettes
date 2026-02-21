#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ ! -x ".venv/bin/python" ]]; then
  python3 -m venv --system-site-packages .venv
fi

# Editable install without build isolation (utile si pip n'a pas accès réseau).
if command -v flock >/dev/null 2>&1; then
  exec 9> ".venv/.mwouettes-install.lock"
  flock 9
fi
.venv/bin/python -m pip install -e . --no-build-isolation >/dev/null

exec .venv/bin/mwouettes "$@"
