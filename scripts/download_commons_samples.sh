#!/usr/bin/env bash
set -euo pipefail

# Télécharge quelques sons libres depuis Wikimedia Commons dans ./samples
# (utilise des URLs stables Special:FilePath qui redirigent vers le fichier).
#
# Sons installés (noms locaux):
#   - samples/river.ogg  (ruisseau/rivière)
#   - samples/wind.ogg   (vent)
#   - samples/waves.ogg  (vagues)
#   - samples/birds.ogg  (chant d'oiseau)
#   - samples/gulls.ogg  (mouette)
#   - samples/drops.ogg  (gouttes d'eau)
#   - samples/rain.ogg   (pluie)
#   - samples/wood_creak.ogg (craquement bois)
#   - samples/hull_lapping.ogg (mer/eau contre coque / structure)
#   - samples/lightning.ogg (éclair / choc électrique)
#   - samples/thunder.ogg (tonnerre)
#   - samples/owl.ogg    (hibou)
#   - samples/crow.ogg   (corneille/corbeau)
#   - samples/raven.ogg  (corbeau)
#   - samples/frog.oga   (grenouille)
#   - samples/cricket.ogg (grillon)
#   - samples/dog.ogg    (chien)
#   - samples/nightingale.ogg (rossignol) (long)
#   - samples/bike_bell.ogg (sonnette)
#   - samples/car_horn.wav (klaxon)
#
# Note: vérifie toujours la licence sur la page Commons si tu redistribues.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
mkdir -p samples

if command -v curl >/dev/null 2>&1; then
  DL() { curl -fsSL -L -o "$2" "$1"; }
elif command -v wget >/dev/null 2>&1; then
  DL() { wget -q -O "$2" "$1"; }
else
  echo "Erreur: installe curl ou wget." >&2
  exit 2
fi

BASE="https://commons.wikimedia.org/wiki/Special:FilePath"

fails=()

try_dl() {
  local url="$1"
  local dest="$2"
  if [[ -f "$dest" ]]; then
    echo "[skip] $dest"
    return 0
  fi
  echo "[get]  $dest"
  if DL "$url" "$dest"; then
    return 0
  fi
  rm -f "$dest" >/dev/null 2>&1 || true
  echo "[FAIL] $url" >&2
  fails+=("$dest")
  return 0
}

try_dl "$BASE/Shallow_small_river_with_stony_riverbed.ogg" "samples/river.ogg"
try_dl "$BASE/Howling_wind.ogg" "samples/wind.ogg"
try_dl "$BASE/Waves.ogg" "samples/waves.ogg"
try_dl "$BASE/Bird_singing.ogg" "samples/birds.ogg"
try_dl "$BASE/Gull_1.ogg" "samples/gulls.ogg"

# Pluie / eau / orage
try_dl "$BASE/Water_drops_dripping.ogg" "samples/drops.ogg"
try_dl "$BASE/Rain.ogg" "samples/rain.ogg"
try_dl "$BASE/Creaky_wooden_casket.ogg" "samples/wood_creak.ogg"
try_dl "$BASE/Squeaks_and_twangs_of_greenwich_pier.ogg" "samples/hull_lapping.ogg"
try_dl "$BASE/Electric_Shock.ogg" "samples/lightning.ogg"
try_dl "$BASE/Thunder_01.ogg" "samples/thunder.ogg"

# Animaux (plutôt "one-shot")
try_dl "$BASE/Tawny_Owl_(Strix_aluco).ogg" "samples/owl.ogg"
try_dl "$BASE/Corvus_cornix.ogg" "samples/crow.ogg"
try_dl "$BASE/Forest_Raven_Call.ogg" "samples/raven.ogg"
try_dl "$BASE/Single_Frog_Croak.oga" "samples/frog.oga"
try_dl "$BASE/Field_cricket_Gryllus_pennsylvanicus.ogg" "samples/cricket.ogg"
try_dl "$BASE/Barking_of_a_dog.ogg" "samples/dog.ogg"
try_dl "$BASE/Luscinia_megarhynchos_-_Common_Nightingale_XC131581.ogg" "samples/nightingale.ogg"

# Ville (plutôt "one-shot")
try_dl "$BASE/Ding_Dong_Bicycle_Bell_A.ogg" "samples/bike_bell.ogg"
try_dl "$BASE/Car_Horn.wav" "samples/car_horn.wav"

if ((${#fails[@]})); then
  echo "[mwouettes] Attention: certains téléchargements ont échoué:" >&2
  printf ' - %s\n' "${fails[@]}" >&2
  echo "[mwouettes] Tu peux relancer le script (il skippe les fichiers déjà présents)." >&2
fi

echo "OK: contenu de ./samples :"
ls -la samples | sed -n '1,120p'
