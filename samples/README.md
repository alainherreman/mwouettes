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

Il installe par défaut:
- `samples/river.ogg`, `samples/wind.ogg`, `samples/waves.ogg`, `samples/birds.ogg`, `samples/gulls.ogg`
- `samples/drops.ogg`, `samples/rain.ogg`, `samples/wood_creak.ogg`, `samples/hull_lapping.ogg`, `samples/lightning.ogg`, `samples/thunder.ogg`
- `samples/owl.ogg`, `samples/crow.ogg`, `samples/raven.ogg`, `samples/frog.oga`, `samples/cricket.ogg`, `samples/dog.ogg`, `samples/nightingale.ogg`
- `samples/bike_bell.ogg`, `samples/car_horn.wav`
