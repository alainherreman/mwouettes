# mwouettes (flow-sonify)

Application (MVP) qui **sonorise le trafic Internet entrant/sortant** : un “bruit de rivière” continu dont l’intensité suit le volume global, plus des “cris” (chirps) différents selon le type de paquets (TCP/UDP/ICMP, DNS…).

## Installation (1x)

Dans ce dépôt (plusieurs options) :

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e . --no-build-isolation
```

Remarques :
- Par défaut le MVP marche avec `tcpdump` (capture) + `aplay` (audio) sans dépendances Python de capture/audio, **sauf** `numpy` pour la synthèse.
- Si vous n’avez pas `numpy` dans votre environnement Python, installez l’extra: `pip install -e ".[aplay]"`.
- Pour utiliser scapy: `pip install -e ".[pcap]"`.
- Pour utiliser sounddevice: `pip install -e ".[audio]"` (nécessite PortAudio).
- La capture nécessite souvent des privilèges (ex: `sudo`) selon votre OS/config.

## Démarrer (recommandé)

Le plus simple (crée/maintient `.venv`, installe en editable, puis lance la commande) :

```bash
./mwouettes
```

Par défaut ça lance l’UI (`--ui`). Le script utilise `sudo` automatiquement pour la capture (désactivable avec `./mwouettes --no-sudo`).

Lister les interfaces :

```bash
./mwouettes --list-interfaces
```

Lister les périphériques audio :

```bash
./mwouettes --list-audio-devices
```

Astuce (si tu exécutes des commandes “une par une” dans un runner qui ne conserve pas l’environnement) :

```bash
./run.sh --list-interfaces
```

## UI (réglage live)

Lancer une UI Web locale (audio joué par le navigateur, idéal pour régler rapidement) :

```bash
./mwouettes --ui
```

Puis ouvrir l’URL affichée et cliquer **“Démarrer audio”**.

L’UI permet aussi **d’enregistrer la sortie audio** (bouton “Enregistrer”) et de télécharger le fichier.

Note : si `flow_sonify_default.json` est présent dans le dossier courant, il est chargé automatiquement (presets `sous-bois` / `bord-de-mer`). Sinon, passe `--config flow_sonify_default.json`.
Les presets peuvent aussi être stockés en fichiers séparés dans `environments/` (un `.json` par preset) : l’UI les charge automatiquement.

## Sons (samples)

Pour utiliser une vraie rivière / oiseaux, dépose des fichiers audio dans `samples/` (ex: `samples/river.wav`, `samples/bird1.wav`), puis dans l’UI :
- choisir le son du **ruisseau** via `river.sample` (joué en continu et modulé par l’activité réseau)
- pour chaque **canal**, choisir :
  - `mode = one-shot` (événements discrets) ou `mode = loop` (son continu modulé)
  - `sample` = fichier dans `samples/` **ou** son interne (`@chirp`, `@drone`, `@noise`)

Tu peux aussi importer directement via l’UI (“Importer des sons”) : les fichiers sont ajoutés à `samples/` et apparaissent dans les listes.

Option: télécharger quelques sons libres depuis Wikimedia Commons :

```bash
./scripts/download_commons_samples.sh
```

## Environnements (presets)

Deux presets sont fournis dans `flow_sonify_default.json` :
- `sous-bois` (rivière + vent + oiseaux)
- `bord-de-mer` (vagues + vent + mouettes)

Dans l’UI, tu peux “Charger” un preset, le modifier, puis “Sauver” pour l’écraser ou le dupliquer sous un nouveau nom.

Lancer (exemple sur `wlan0`) :

```bash
./mwouettes --interface wlan0
```

Mode sans audio (debug) :

```bash
./mwouettes --interface wlan0 --dry-run
```

Enregistrer la sortie audio (WAV, mono 16-bit) :

```bash
./mwouettes --interface wlan0 --record out.wav
```

## Configuration

Vous pouvez fournir un fichier JSON :

```bash
./mwouettes --interface wlan0 --config flow_sonify_default.json
```

La config permet notamment d’ajuster :
- `block_ms` (latence/“granularité”)
- `river.*` (gain, courbe, filtre)
- `channels.*` :
  - `enabled` (active/muet)
  - `mode` (`one-shot` ou `loop`)
  - `sample` (fichier dans `samples/` ou `@chirp/@drone/@noise`)
  - `freq_hz`/`duration_ms` (utilisés uniquement pour les sons internes)

## Catégories détectées (par défaut)

- `in.tcp`, `out.tcp`
- `in.udp`, `out.udp`
- `in.icmp`, `out.icmp`
- `in.dns`, `out.dns` (UDP/TCP port 53)
- `tcp.total`, `udp.total`, `icmp.total`, `dns.total` (total in+out)
- `net.total` (total réseau in+out)

## Idées d’évolution

- Ajouter plus de presets + une bibliothèque de sons libres (rivière/vent/vagues/oiseaux…).
- Détection L7 (HTTP(S), QUIC, SSH…) via ports + heuristiques.
- Capture eBPF (Linux) pour plus de précision et moins d’overhead.
