#!/usr/bin/env bash
set -euo pipefail

# Installe une commande `mwouettes` accessible dans le shell, sans devoir être
# dans le dossier du projet ni activer la venv.
#
# Méthode: crée un symlink ~/.local/bin/mwouettes -> <repo>/mwouettes
#
# Pré-requis:
# - ~/.local/bin dans le PATH (souvent déjà le cas sur Linux)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="$ROOT_DIR/mwouettes"
BIN_DIR="${HOME}/.local/bin"
LINK="$BIN_DIR/mwouettes"

if [[ ! -x "$TARGET" ]]; then
  echo "Erreur: $TARGET introuvable ou non exécutable." >&2
  exit 2
fi

mkdir -p "$BIN_DIR"
ln -sfn "$TARGET" "$LINK"

echo "OK: commande installée -> $LINK"
if ! command -v mwouettes >/dev/null 2>&1; then
  echo "Note: ajoute ~/.local/bin à ton PATH puis relance ton shell."
  echo "Ex (bash): echo 'export PATH=\"$HOME/.local/bin:$PATH\"' >> ~/.bashrc"
fi
