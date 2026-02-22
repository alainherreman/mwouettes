#!/usr/bin/env bash
set -euo pipefail

# Télécharge quelques sons libres depuis Wikimedia Commons dans ./samples
# (utilise des URLs stables Special:FilePath qui redirigent vers le fichier).
#
# Sons installés (noms locaux):
#   - samples/river.ogg  (ruisseau/rivière)
#   - samples/river_noise.ogg  (rivière — variante)
#   - samples/river_noise2.ogg (rivière — variante)
#   - samples/wind.ogg   (vent)
#   - samples/wind_forest.ogg (vent — forêt)
#   - samples/wind_coast.ogg  (vent — côte)
#   - samples/waves.ogg  (vagues)
#   - samples/waves_crushing.ogg (vagues — déferlantes)
#   - samples/waves_rocks.ogg    (vagues — rochers)
#   - samples/birds.ogg  (chant d'oiseau)
#   - samples/great_tit.ogg (mésange charbonnière)
#   - samples/starling.ogg (étourneau)
#   - samples/house_sparrow.ogg (moineau)
#   - samples/blackbird.ogg (merle noir)
#   - samples/robin.ogg (rougegorge)
#   - samples/gulls.ogg  (mouette)
#   - samples/drops.ogg  (gouttes d'eau)
#   - samples/rain.ogg   (pluie)
#   - samples/wood_creak.ogg (craquement bois)
#   - samples/hull_lapping.ogg (mer/eau contre coque / structure)
#   - samples/lightning.ogg (éclair)
#   - samples/thunder.ogg (tonnerre)
#   - samples/owl.ogg    (hibou)
#   - samples/crow.ogg   (corneille — 1 croassement)
#   - samples/raven.ogg  (corbeau)
#   - samples/frog.oga   (grenouille — 1 croassement)
#   - samples/cricket.ogg (grillon)
#   - samples/dog.ogg    (chien)
#   - samples/nightingale.ogg (rossignol) (long)
#   - samples/meow.ogg   (chat)
#   - samples/sheep.ogg  (mouton)
#   - samples/cow_moo.ogg (vache)
#   - samples/rooster.ogg (coq)
#   - samples/woodpecker_drum.ogg (pic-vert / tambourinage)
#   - samples/owl_call.ogg (hibou/chouette)
#   - samples/storm.ogg  (pluie + tonnerre)
#   - samples/foghorn.ogg (corne de brume)
#   - samples/foghorn_diaphone.ogg (corne de brume — diaphone)
#   - samples/ship_horn_port.ogg (klaxon de navire (port))
#   - samples/boat_hull_lap.ogg (coque qui tape / bateau au quai + clapot)
#   - samples/rigging_clank.ogg (haubants/cordages qui claquent contre un mât)
#   - samples/sonar_ping.ogg (sonar)
#   - samples/whale.ogg  (baleine)
#   - samples/whale_song.ogg  (chant des baleines)
#   - samples/sputnik_beep.ogg (bip satellite)
#   - samples/reactor.ogg (réacteur / accélération)
#   - samples/sonic_boom.ogg (bang supersonique / “étoile filante”)
#   - samples/bike_bell.ogg (sonnette)
#   - samples/car_horn.wav (klaxon)
#
# Note: vérifie toujours la licence sur la page Commons si tu redistribues.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
mkdir -p samples

if command -v curl >/dev/null 2>&1; then
  DL() { curl -fsSL -L --retry 8 --retry-delay 2 --retry-all-errors --retry-max-time 180 -o "$2" "$1"; }
elif command -v wget >/dev/null 2>&1; then
  DL() { wget -q -O "$2" "$1"; }
else
  echo "Erreur: installe curl ou wget." >&2
  exit 2
fi

BASE="https://commons.wikimedia.org/wiki/Special:FilePath"

fails=()
POLITE_DELAY_S="${POLITE_DELAY_S:-0.7}"
ONE_SHOT_S="${ONE_SHOT_S:-1.2}"
HORN_S="${HORN_S:-6.0}"
SHIP_HORN_S="${SHIP_HORN_S:-2.2}"
SHIP_HORN_SS="${SHIP_HORN_SS:-5.0}"
SHIP_HORN_SILENCE_DB="${SHIP_HORN_SILENCE_DB:--40dB}"
BOAT_HULL_LAP_S="${BOAT_HULL_LAP_S:-6.0}"
BOAT_HULL_LAP_SS="${BOAT_HULL_LAP_SS:-12.0}"
HULL_LAP_S="${HULL_LAP_S:-12.0}"
WIND_COAST_S="${WIND_COAST_S:-16.0}"
WIND_COAST_STEP="${WIND_COAST_STEP:-3.0}"
DROPS_S="${DROPS_S:-0.6}"
DROPS_STEP="${DROPS_STEP:-0.1}"
CRICKET_S="${CRICKET_S:-1.2}"
CRICKET_STEP="${CRICKET_STEP:-0.2}"
REACTOR_STEP="${REACTOR_STEP:-1.5}"
FOGHORN_S="${FOGHORN_S:-5.0}"
FOGHORN_STEP="${FOGHORN_STEP:-2.0}"
SONAR_S="${SONAR_S:-0.9}"
WHALE_S="${WHALE_S:-2.8}"
REACTOR_S="${REACTOR_S:-2.8}"
WHALE_SONG_S="${WHALE_SONG_S:-28.0}"
FORCE="${FORCE:-0}"

validate_magic() {
  local dest="$1"
  local ext="${dest##*.}"
  local magic=""
  magic="$(head -c 4 "$dest" 2>/dev/null || true)"
  case "${ext,,}" in
    ogg|oga)
      [[ "$magic" == "OggS" ]]
      ;;
    wav)
      [[ "$magic" == "RIFF" ]]
      ;;
    *)
      return 0
      ;;
  esac
}

try_dl() {
  local url="$1"
  local dest="$2"
  if [[ -f "$dest" && "$FORCE" != "1" ]]; then
    echo "[skip] $dest"
    return 0
  fi
  echo "[get]  $dest <= $url"
  local ext="${dest##*.}"
  local tmp="${dest%.*}.tmp.$$.$ext"
  local ok="0"
  for attempt in 1 2 3 4 5; do
    rm -f "$tmp" >/dev/null 2>&1 || true
    if DL "$url" "$tmp"; then
      ok="1"
      break
    fi
    # Backoff (helps with Commons 429 rate-limit).
    sleep "$((attempt * attempt))" || true
  done
  if [[ "$ok" == "1" ]]; then
    if ! validate_magic "$tmp"; then
      rm -f "$tmp" >/dev/null 2>&1 || true
      echo "[FAIL] invalid audio (bad header): $url" >&2
      fails+=("$dest")
    else
      mv -f "$tmp" "$dest"
    fi
  else
    rm -f "$tmp" >/dev/null 2>&1 || true
    echo "[FAIL] $url" >&2
    fails+=("$dest")
  fi
  # Be polite: reduce the chance of 429.
  sleep "$POLITE_DELAY_S" || true
  return 0
}

try_dl_any() {
  # try_dl_any dest url1 url2 ...
  local dest="$1"
  shift || true
  if [[ -f "$dest" && "$FORCE" != "1" ]]; then
    echo "[skip] $dest"
    return 0
  fi
  local url=""
  for url in "$@"; do
    try_dl "$url" "$dest"
    if [[ -f "$dest" ]]; then
      return 0
    fi
  done
  return 0
}

ffmpeg_bin="$(command -v ffmpeg || true)"
ffprobe_bin="$(command -v ffprobe || true)"
python3_bin="$(command -v python3 || true)"

_best_ss() {
  # _best_ss input dur step metric(mean|max)
  local in="$1"
  local seg_dur="$2"
  local step="$3"
  local metric="${4:-mean}"

  if [[ -z "$ffmpeg_bin" || -z "$ffprobe_bin" || -z "$python3_bin" ]]; then
    echo "0"
    return 0
  fi

  "$python3_bin" - "$in" "$seg_dur" "$step" "$metric" <<'PY'
import math
import re
import subprocess
import sys

in_path = sys.argv[1]
seg_dur = float(sys.argv[2])
step = float(sys.argv[3])
metric = sys.argv[4]

def get_duration(path: str) -> float:
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path],
        capture_output=True,
        text=True,
    )
    try:
        return float((p.stdout or "").strip() or "0")
    except Exception:
        return 0.0

dur = get_duration(in_path)
max_ss = max(0.0, dur - seg_dur)
if step <= 0:
    step = max(0.2, seg_dur / 3.0)

pat_mean = re.compile(r"mean_volume:\\s*([\\-0-9.]+)\\s*dB")
pat_max = re.compile(r"max_volume:\\s*([\\-0-9.]+)\\s*dB")

best_val = -1e9
best_ss = 0.0

ss = 0.0
iters = 0
max_iters = 260
if max_ss > 0 and step > 0:
    max_iters = min(max_iters, int(math.ceil(max_ss / step)) + 1)

while ss <= max_ss + 1e-6 and iters < max_iters:
    iters += 1
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-v",
        "info",
        "-ss",
        f"{ss:.3f}",
        "-t",
        f"{seg_dur:.3f}",
        "-i",
        in_path,
        "-af",
        "volumedetect",
        "-f",
        "null",
        "-",
    ]
    p = subprocess.run(cmd, capture_output=True, text=True)
    err = p.stderr or ""
    m_mean = pat_mean.search(err)
    m_max = pat_max.search(err)
    val = None
    if metric == "max" and m_max:
        val = float(m_max.group(1))
    elif metric == "mean" and m_mean:
        val = float(m_mean.group(1))
    elif m_mean:
        val = float(m_mean.group(1))
    elif m_max:
        val = float(m_max.group(1))
    if val is not None and val > best_val:
        best_val = val
        best_ss = ss
    ss += step

print(f\"{best_ss:.3f}\")
PY
}

trim_audio() {
  # trim_audio input output duration_seconds [start_seconds]
  local in="$1"
  local out="$2"
  local dur="$3"
  local ss="${4:-0}"
  if [[ -f "$out" && "$FORCE" != "1" ]]; then
    echo "[skip] $out"
    return 0
  fi
  if [[ ! -f "$in" ]]; then
    return 0
  fi
  if [[ -z "$ffmpeg_bin" ]]; then
    # No ffmpeg: best-effort, keep the original as-is.
    cp -f "$in" "$out"
    return 0
  fi
  echo "[make] $out"
  local ext="${out##*.}"
  local tmp="${out%.*}.tmp.${ext}"
  rm -f "$tmp" >/dev/null 2>&1 || true
  "$ffmpeg_bin" -v error -y -ss "$ss" -t "$dur" -i "$in" -vn -ac 1 -c:a libvorbis -q:a 6 -f ogg "$tmp"
  mv -f "$tmp" "$out"
  if ! validate_magic "$out"; then
    rm -f "$out" >/dev/null 2>&1 || true
    echo "[FAIL] invalid trimmed audio: $out" >&2
    fails+=("$out")
  fi
}

trim_audio_no_leading_silence() {
  # trim_audio_no_leading_silence input output duration_seconds [silence_threshold_db]
  local in="$1"
  local out="$2"
  local dur="$3"
  local thr="${4:--40dB}"
  if [[ -f "$out" && "$FORCE" != "1" ]]; then
    echo "[skip] $out"
    return 0
  fi
  if [[ ! -f "$in" ]]; then
    return 0
  fi
  if [[ -z "$ffmpeg_bin" ]]; then
    cp -f "$in" "$out"
    return 0
  fi
  echo "[make] $out"
  local ext="${out##*.}"
  local tmp="${out%.*}.tmp.${ext}"
  rm -f "$tmp" >/dev/null 2>&1 || true
  "$ffmpeg_bin" -v error -y -i "$in" -vn -af "silenceremove=start_periods=1:start_duration=0:start_threshold=${thr}" -t "$dur" -ac 1 -c:a libvorbis -q:a 6 -f ogg "$tmp"
  mv -f "$tmp" "$out"
  if ! validate_magic "$out"; then
    rm -f "$out" >/dev/null 2>&1 || true
    echo "[FAIL] invalid trimmed audio: $out" >&2
    fails+=("$out")
  fi
}

trim_loudest() {
  # trim_loudest input output duration_seconds metric(mean|max) step_seconds
  local in="$1"
  local out="$2"
  local dur="$3"
  local metric="${4:-mean}"
  local step="${5:-1.0}"
  if [[ -f "$out" && "$FORCE" != "1" ]]; then
    echo "[skip] $out"
    return 0
  fi
  if [[ ! -f "$in" ]]; then
    return 0
  fi
  local ss="0"
  ss="$(_best_ss "$in" "$dur" "$step" "$metric" 2>/dev/null || echo "0")"
  trim_audio "$in" "$out" "$dur" "$ss"
}

transcode_audio() {
  # transcode_audio input output [duration_seconds] [start_seconds]
  local in="$1"
  local out="$2"
  local dur="${3:-}"
  local ss="${4:-0}"
  if [[ -f "$out" && "$FORCE" != "1" ]]; then
    echo "[skip] $out"
    return 0
  fi
  if [[ ! -f "$in" ]]; then
    return 0
  fi
  if [[ -z "$ffmpeg_bin" ]]; then
    cp -f "$in" "$out"
    return 0
  fi
  echo "[make] $out"
  local ext="${out##*.}"
  local tmp="${out%.*}.tmp.${ext}"
  rm -f "$tmp" >/dev/null 2>&1 || true
  if [[ -n "$dur" ]]; then
    "$ffmpeg_bin" -v error -y -ss "$ss" -t "$dur" -i "$in" -vn -ac 1 -c:a libvorbis -q:a 6 -f ogg "$tmp"
  else
    "$ffmpeg_bin" -v error -y -i "$in" -vn -ac 1 -c:a libvorbis -q:a 6 -f ogg "$tmp"
  fi
  mv -f "$tmp" "$out"
  if ! validate_magic "$out"; then
    rm -f "$out" >/dev/null 2>&1 || true
    echo "[FAIL] invalid transcoded audio: $out" >&2
    fails+=("$out")
  fi
}

try_dl "$BASE/Shallow_small_river_with_stony_riverbed.ogg" "samples/river.ogg"
try_dl "$BASE/Rivernoise3.ogg" "samples/river_noise.ogg"
try_dl "$BASE/Rivernoise.ogg" "samples/river_noise2_full.ogg"
trim_audio "samples/river_noise2_full.ogg" "samples/river_noise2.ogg" "12.0" "0"
try_dl "$BASE/Howling_wind.ogg" "samples/wind.ogg"
try_dl "$BASE/Wind_in_Swedish_pine_forest_at_25_mps.ogg" "samples/wind_forest_full.ogg"
trim_audio "samples/wind_forest_full.ogg" "samples/wind_forest.ogg" "16.0" "0"
try_dl "$BASE/Vento_fisterra.ogg" "samples/wind_coast_full.ogg"
trim_loudest "samples/wind_coast_full.ogg" "samples/wind_coast.ogg" "$WIND_COAST_S" "mean" "$WIND_COAST_STEP"
try_dl "$BASE/Waves.ogg" "samples/waves.ogg"
try_dl "$BASE/Oceanwavescrushing.ogg" "samples/waves_crushing_full.ogg"
trim_audio "samples/waves_crushing_full.ogg" "samples/waves_crushing.ogg" "18.0" "0"
try_dl "$BASE/Water_on_Rocks.ogg" "samples/waves_rocks_full.ogg"
trim_audio "samples/waves_rocks_full.ogg" "samples/waves_rocks.ogg" "18.0" "0"
try_dl "$BASE/Bird_singing.ogg" "samples/birds_full.ogg"
trim_audio "samples/birds_full.ogg" "samples/birds.ogg" "$ONE_SHOT_S" "0"
try_dl "$BASE/Parus_major.ogg" "samples/great_tit.ogg"
try_dl "$BASE/Sturnus_vulgaris.ogg" "samples/starling_full.ogg"
trim_audio "samples/starling_full.ogg" "samples/starling.ogg" "$ONE_SHOT_S" "0"
try_dl "$BASE/Passer_domesticus.ogg" "samples/house_sparrow_full.ogg"
trim_audio "samples/house_sparrow_full.ogg" "samples/house_sparrow.ogg" "$ONE_SHOT_S" "0"
try_dl "$BASE/Turdus_merula_-_Common_Blackbird_XC123548.ogg" "samples/blackbird_full.ogg"
trim_audio "samples/blackbird_full.ogg" "samples/blackbird.ogg" "$ONE_SHOT_S" "0"
try_dl "$BASE/Erithacus_rubecula.ogg" "samples/robin_full.ogg"
trim_audio "samples/robin_full.ogg" "samples/robin.ogg" "$ONE_SHOT_S" "0"
try_dl "$BASE/Gull_1.ogg" "samples/gulls.ogg"

# Pluie / eau / orage
try_dl "$BASE/Water_drops_dripping.ogg" "samples/drops_full.ogg"
trim_loudest "samples/drops_full.ogg" "samples/drops.ogg" "$DROPS_S" "max" "$DROPS_STEP"
try_dl "$BASE/Rain.ogg" "samples/rain.ogg"
try_dl "$BASE/Creaky_wooden_casket.ogg" "samples/wood_creak.ogg"
try_dl "$BASE/Squeaks_and_twangs_of_greenwich_pier.ogg" "samples/hull_lapping_full.ogg"
trim_loudest "samples/hull_lapping_full.ogg" "samples/hull_lapping.ogg" "$HULL_LAP_S" "mean" "2.0"
try_dl "$BASE/Lightning_Recorded_In_Groningen_2018-05-13_01.wav" "samples/lightning_full.wav"
transcode_audio "samples/lightning_full.wav" "samples/lightning.ogg" "2.5" "0"
try_dl "$BASE/Thunder_01.ogg" "samples/thunder.ogg"
try_dl "$BASE/Rain_and_thunder_%2801%29.ogg" "samples/storm.ogg"
try_dl "$BASE/Fog_signal_Bremerhaven.ogg" "samples/foghorn_full.ogg"
trim_loudest "samples/foghorn_full.ogg" "samples/foghorn.ogg" "$FOGHORN_S" "max" "$FOGHORN_STEP"
try_dl "$BASE/East_Brother_Light_Diaphone_Foghorn.oga" "samples/foghorn_diaphone_full.oga"
trim_audio "samples/foghorn_diaphone_full.oga" "samples/foghorn_diaphone.ogg" "$HORN_S" "0"
try_dl "$BASE/Cruise_ship_Albatros_ship_horn.ogg" "samples/ship_horn_port_full.ogg"
trim_audio "samples/ship_horn_port_full.ogg" "samples/ship_horn_port.ogg" "$SHIP_HORN_S" "$SHIP_HORN_SS"
try_dl "$BASE/Boat_landing_at_a_wharf.ogg" "samples/boat_hull_lap_full.ogg"
trim_loudest "samples/boat_hull_lap_full.ogg" "samples/boat_hull_lap.ogg" "$BOAT_HULL_LAP_S" "mean" "1.0"
try_dl "$BASE/Ratched_cord_sounds.ogg" "samples/rigging_clank_full.ogg"
trim_audio "samples/rigging_clank_full.ogg" "samples/rigging_clank.ogg" "2.0" "0"

# Sous-marin / espace
try_dl "$BASE/Sonar_pings.ogg" "samples/sonar_ping.ogg"
rm -f "samples/sonar_ping_full.ogg" >/dev/null 2>&1 || true
try_dl_any "samples/whale_full.ogg" \
  "$BASE/Humpback_whale_moo.ogg" \
  "$BASE/Humpbackwhale2.ogg"
trim_audio "samples/whale_full.ogg" "samples/whale.ogg" "$WHALE_S" "0"
try_dl "$BASE/Humpbackwhale2.ogg" "samples/whale_song_full.ogg"
trim_audio_no_leading_silence "samples/whale_song_full.ogg" "samples/whale_song.ogg" "$WHALE_SONG_S" "-45dB"
try_dl "$BASE/Sputnik_beep.ogg" "samples/sputnik_beep.ogg"
try_dl_any "samples/reactor_full.ogg" \
  "$BASE/WWS_SaabJ35DDrakenstartengineandtaxiing.ogg" \
  "$BASE/Start_einer_Airbus_A320_%28Air_Berlin%29.ogg" \
  "$BASE/Mus%C3%A9e_d%C3%A9fense_a%C3%A9rienne_-_GE-404_turbojet.ogg" \
  "$BASE/Mus%C3%A9e_d%C3%A9fense_a%C3%A9rienne_-_Orenda_turbojet.ogg" \
  "$BASE/Jet_airliner_overhead.ogg"
trim_loudest "samples/reactor_full.ogg" "samples/reactor.ogg" "$REACTOR_S" "mean" "$REACTOR_STEP"
try_dl_any "samples/sonic_boom_full.ogg" \
  "$BASE/Sonic-boom-massive-sound.ogg" \
  "$BASE/Sonic_boom.ogg"
trim_audio "samples/sonic_boom_full.ogg" "samples/sonic_boom.ogg" "1.2" "0"

# Animaux (plutôt "one-shot")
try_dl "$BASE/Tawny_Owl_(Strix_aluco).ogg" "samples/owl.ogg"
try_dl "$BASE/Brown_wood_owl_call.ogg" "samples/owl_call.ogg"
try_dl "$BASE/Corvus_cornix.ogg" "samples/crow_full.ogg"
trim_audio "samples/crow_full.ogg" "samples/crow.ogg" "1.0" "0"
try_dl "$BASE/Forest_Raven_Call.ogg" "samples/raven.ogg"
try_dl "$BASE/Single_Frog_Croak.oga" "samples/frog_full.oga"
trim_audio "samples/frog_full.oga" "samples/frog.oga" "1.2" "0"
try_dl "$BASE/Field_cricket_Gryllus_pennsylvanicus.ogg" "samples/cricket_full.ogg"
trim_loudest "samples/cricket_full.ogg" "samples/cricket.ogg" "$CRICKET_S" "max" "$CRICKET_STEP"
try_dl "$BASE/Barking_of_a_dog.ogg" "samples/dog.ogg"
try_dl "$BASE/Luscinia_megarhynchos_-_Common_Nightingale_XC131581.ogg" "samples/nightingale.ogg"
try_dl "$BASE/Meow.ogg" "samples/meow.ogg"
try_dl "$BASE/Sheep_bleat.ogg" "samples/sheep.ogg"
try_dl "$BASE/Single_Cow_Moo.ogg" "samples/cow_moo.ogg"
try_dl "$BASE/Rooster_crowing.ogg" "samples/rooster.ogg"
try_dl "$BASE/Woodpeckerdrum.ogg" "samples/woodpecker_drum.ogg"

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
