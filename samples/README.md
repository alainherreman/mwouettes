Dépose ici tes sons (samples) pour l’UI.

- Formats supportés: `.wav` (recommandé), `.mp3`, `.ogg`, `.oga`
- L’UI les liste via `GET /api/samples` et les sert via `GET /samples/<nom>`

Exemples d’usage:
- `river.sample="river.wav"` pour une rivière en continu (boucle)
- `channels["dns.total"].mode="one-shot"` + `sample="bird1.wav"` pour un cri discret
- `channels["tcp.total"].mode="loop"` + `sample="wind.ogg"` pour un fond continu

Astuce : pour un usage "one-shot", préfère des fichiers courts (0.2–2s). Si un fichier est trop long, tu peux le couper avec ffmpeg :

```bash
ffmpeg -y -i samples/nightingale.ogg -t 1.2 -c:a libvorbis -q:a 6 samples/nightingale_short.ogg
```

## Télécharger des sons libres (option)

Un script est fourni pour récupérer quelques sons depuis Wikimedia Commons :

```bash
./scripts/download_commons_samples.sh
```

Note : Wikimedia Commons peut limiter le débit (erreur HTTP 429). Le script fait des retries + une petite pause entre les fichiers ; tu peux aussi simplement le relancer plus tard (il skippe les fichiers déjà présents).

Il installe par défaut:
- `samples/river.ogg`, `samples/river_noise.ogg`, `samples/river_noise2.ogg`
- `samples/wind.ogg`, `samples/wind_forest.ogg`, `samples/wind_coast.ogg`
- `samples/waves.ogg`, `samples/waves_crushing.ogg`, `samples/waves_rocks.ogg`
- `samples/birds.ogg`, `samples/gulls.ogg`
- `samples/great_tit.ogg`, `samples/starling.ogg`, `samples/house_sparrow.ogg`, `samples/blackbird.ogg`, `samples/robin.ogg`
- `samples/drops.ogg`, `samples/rain.ogg`, `samples/wood_creak.ogg`, `samples/hull_lapping.ogg`, `samples/lightning.ogg`, `samples/thunder.ogg`, `samples/storm.ogg`
- `samples/owl.ogg`, `samples/owl_call.ogg`, `samples/crow.ogg`, `samples/raven.ogg`, `samples/frog.oga`, `samples/cricket.ogg`, `samples/dog.ogg`, `samples/nightingale.ogg`
- `samples/meow.ogg`, `samples/sheep.ogg`, `samples/cow_moo.ogg`, `samples/rooster.ogg`, `samples/woodpecker_drum.ogg`
- `samples/foghorn.ogg`, `samples/ship_horn_port.ogg`, `samples/boat_hull_lap.ogg`, `samples/rigging_clank.ogg`, `samples/bike_bell.ogg`, `samples/car_horn.wav`
- `samples/sonar_ping.ogg`, `samples/whale.ogg`, `samples/sputnik_beep.ogg`, `samples/reactor.ogg`, `samples/sonic_boom.ogg`
