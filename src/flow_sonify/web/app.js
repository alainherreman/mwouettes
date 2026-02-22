const els = (id) => document.getElementById(id);

let config = null;
let lastCounts = {};
let blockMs = 100;
let audio = null;
let samples = [];
let interfaces = [];
let currentIface = null;
let captureBackend = null;
let captureRunning = false;
let captureError = null;
let isRecording = false;
let lang = "fr";

const I18N = {
  fr: {
    "page.title": "mwouettes",
    "header.title": "mwouettes",
    "header.subtitle": "Réglage live: paquets → sons (continu/discret)",
    "ui.language": "Langue",

    "btn.audio_start": "Démarrer audio",
    "btn.audio_stop": "Arrêter audio",
    "btn.panic": "Panic (mute)",

    "title.audio_toggle": "Démarre/arrête l’audio Web. Le navigateur exige une interaction utilisateur pour jouer du son.",
    "title.panic": "Coupe le son très brièvement (utile si ça devient trop fort).",
    "title.refresh_interfaces": "Rafraîchit la liste des interfaces.",

    "section.state": "État",
    "label.connection": "Connexion",
    "label.interface": "Interface",
    "label.block": "Bloc",
    "label.total_pps": "Total (pps)",
    "label.inout_pps": "In/Out (pps)",

    "tip.interface": "Choisis l’interface réseau à écouter (ex: wlan0, enp…). Le changement est appliqué immédiatement. Si tu es sous VPN, l’interface peut être tailscale0/tun0.",
    "tip.block": "Taille d’un “pas de temps” pour calculer les pps et mettre à jour l’audio. Plus petit = plus réactif mais plus nerveux.",
    "tip.pps": "pps = paquets par seconde (estimation sur le dernier bloc).",
    "tip.inout": "In = entrant (vers ta machine), Out = sortant (depuis ta machine).",

    "section.environment": "Environnement",
    "label.preset": "Preset",
    "label.name": "Nom",
    "ph.env_name": "ex: mon-jardin",
    "btn.save": "Sauver",
    "label.overwrite": "écraser si existe",
    "title.save_preset": "Sauve la config courante comme preset sous ce nom.",
    "title.overwrite": "Si coché, remplace un preset existant portant le même nom.",
    "tip.preset": "Un preset (environnement) = un ensemble de réglages (fond + canaux). La sélection applique le preset immédiatement. “Sauver” enregistre la config courante comme preset (dans la mémoire du serveur + environments/), et “Sauver config” écrit tout dans le fichier JSON.",
    "hint.preset_apply": "Sélectionner un preset le copie dans la config courante. “Sauver” enregistre la config courante comme preset.",

    "section.import_sounds": "Importer des sons",
    "btn.import": "Importer",
    "title.choose_audio": "Choisis un fichier audio (.wav recommandé). Il sera copié dans le dossier samples/.",
    "title.import_sound": "Importe le fichier sélectionné dans samples/ et met à jour les listes “son”.",
    "title.refresh_sounds": "Rafraîchit la liste des sons depuis le dossier samples/.",
    "hint.imported_stored": "Les fichiers importés sont stockés dans `samples/` et apparaissent dans les listes “son”.",
    "label.listen_sounds": "Écouter les sons :",

    "section.charts": "Courbes",
    "label.pps": "pps",
    "label.top_channels": "top canaux",
    "title.toggle_pps": "Affiche/masque la courbe pps.",
    "title.toggle_top": "Affiche/masque le graphe en bâtons (top canaux).",
    "chart.pps_title": "pps (total / in / out)",
    "chart.top_title": "Top canaux (pps instantané)",
    "legend.total": "total",
    "legend.in": "in",
    "legend.out": "out",
    "title.chart_pps": "Évolution des pps sur les derniers instants (fenêtre glissante).",
    "title.chart_top_in": "Top des canaux entrants (in.*) sur le dernier bloc.",
    "title.chart_top_out": "Top des canaux sortants (out.*) sur le dernier bloc.",

    "section.recording": "Enregistrement",
    "btn.record_start": "Enregistrer",
    "btn.record_stop": "Arrêter",
    "title.record": "Enregistre la sortie audio du navigateur (ce que tu entends). Clique à nouveau pour arrêter.",
    "link.download": "télécharger",
    "tip.recording": "L’enregistrement se fait côté navigateur (WebAudio). Le fichier sera en général en .webm (Opus) selon les capacités du navigateur.",
    "status.recording": "● enregistrement…",
    "status.file_ready": "fichier prêt",

    "section.background": "Fond (continu)",
    "bg.sound": "Son",
    "bg.volume": "Volume",
    "bg.rate": "Débit (paquets/s)",
    "bg.gamma": "Gamma",
    "bg.cutoff": "Cutoff Hz",
    "btn.save_config": "Sauver config",
    "tip.bg.sound": "Fond sonore joué en continu (boucle) et modulé par l’activité réseau. Ex: ruisseau/vent/vagues. Choisis un fichier dans samples/, un son interne (@noise), ou “sans fond”.",
    "tip.bg.volume": "Volume max du fond (il est ensuite modulé selon le trafic).",
    "tip.bg.rate": "Débit de référence (paquets/s) : quand le trafic ≈ cette valeur, on atteint ~le volume max (selon Gamma).",
    "tip.bg.gamma": "Courbe de réponse: plus petit = monte vite; plus grand = plus progressif (moins sensible aux petites variations).",
    "tip.bg.cutoff": "Filtre passe-bas du bruit: bas = plus ‘grave’/doux; haut = plus ‘brillant’/sifflant.",

    "section.channels": "Canaux (par type + direction)",
    "hint.mode_explain_html": "Mode <span class=\"pill\">loop</span> = continu (boucle, volume modulé). Mode <span class=\"pill\">one-shot</span> = discret (événements).",
    "footer.hint_audio": "Astuce: si tu n’entends rien, clique “Démarrer audio” (WebAudio nécessite une interaction utilisateur).",

    "th.active": "actif",
    "th.key": "Clé",
    "th.pps": "pps",
    "th.hint": "conseil",
    "th.mode": "mode",
    "th.sound": "son",
    "th.freq": "freq",
    "th.dur": "dur",
    "th.volume": "volume",
    "th.rate": "débit",
    "th.gamma": "gamma",
    "th.listen": "écoute",
    "tip.th.active": "Active/désactive ce canal (persisté dans la config).",
    "tip.th.key": "Type + direction (in.=entrant, out.=sortant). Survole une clé pour une définition + exemples.",
    "tip.th.pps": "pps = paquets par seconde (estimé sur le dernier bloc).",
    "tip.th.hint": "Indication ‘plutôt continu’ vs ‘plutôt discret’. C’est un point de départ: ajuste selon ton oreille et ton trafic.",
    "tip.th.mode": "one-shot = joue des événements discrets. loop = joue un son en boucle dont le volume suit le débit.",
    "tip.th.sound": "Choisis un fichier dans samples/ OU un son interne (@chirp/@drone/@noise).",
    "tip.th.freq": "Fréquence (Hz) utilisée uniquement pour les sons internes (@chirp/@drone).",
    "tip.th.dur": "Durée (ms) utilisée uniquement pour @chirp.",
    "tip.th.volume": "Volume max du canal (ensuite modulé selon le débit et Gamma).",
    "tip.th.rate": "Débit de référence (paquets/s): quand pps≈débit, on atteint ~le volume max (selon Gamma).",
    "tip.th.gamma": "Courbe de réponse: plus petit = monte vite; plus grand = plus progressif.",
    "tip.th.listen": "Couper un canal (M), n’entendre que lui (S), ou jouer un test (▶).",

    "opt.none": "(aucune)",
    "opt.current": "(courant)",
    "status.capture": "capture: {{name}}{{backend}}",
    "status.capture_stopped": "capture: arrêtée",
    "status.capture_not_running": "capture non active",
    "status.presets_loaded": "Presets chargés: {{n}}",
    "status.presets_none": "Aucun preset chargé (regarde le dossier environments/).",

    "hint.reco.cont": "continu",
    "hint.reco.disc": "discret",
    "hint.reco.na": "—",

    "title.ch.enabled": "Active/désactive ce canal (persisté).",
    "title.ch.mode": "Mode: one-shot (événements) ou loop (continu).",
    "title.ch.sound": "Choisis un fichier depuis samples/ ou un son interne (@chirp/@drone/@noise).",
    "title.ch.freq": "Fréquence (Hz) utilisée pour les sons internes (@chirp/@drone).",
    "title.ch.dur": "Durée (ms) utilisée uniquement pour @chirp (one-shot).",
    "title.ch.vol": "Volume max du canal (puis modulé selon le débit).",
    "title.ch.ref": "Débit de référence (paquets/s): quand pps≈débit, on atteint ~le volume max (selon gamma).",
    "title.ch.gamma": "Courbe de réponse: plus petit = monte vite; plus grand = plus progressif.",
    "title.ch.mute_on": "Réactiver ce canal (mute)",
    "title.ch.mute_off": "Couper ce canal (mute)",
    "title.ch.solo_on": "Désactiver le solo",
    "title.ch.solo_off": "N’entendre que ce canal (solo)",

    "alert.start_audio_first": "Clique d’abord sur “Démarrer audio”.",
    "alert.record_failed": "Enregistrement impossible: {{msg}}",
    "title.sample_play_once": "Écouter une fois",
    "title.sample_loop_toggle": "Boucler / arrêter",
    "msg.ok": "OK",
    "msg.loading": "…",
    "msg.saved": "sauvé",
    "msg.loaded": "chargé",
    "msg.error_prefix": "Erreur: {{msg}}",
    "msg.ok_to": "OK → {{path}}",
    "msg.max_pps": "max {{v}} pps",
    "msg.no_samples": "Aucun son (importe un fichier ou télécharge via le script).",
    "msg.download_with_size": "télécharger ({{mb}} MB)",
    "conn.connecting": "connect…",
    "conn.ok": "ok",
    "conn.offline": "offline",
    "conn.error": "error",
    "err.choose_preset": "choisir un preset",
    "err.name_required": "nom requis",
    "err.choose_file": "choisir un fichier",

    "builtin.none": "sans fond",
    "builtin.noise": "@noise (interne: bruit)",
    "builtin.chirp": "@chirp (interne: cri)",
    "builtin.drone": "@drone (interne: continu)",
  },
  en: {
    "page.title": "mwouettes",
    "header.title": "mwouettes",
    "header.subtitle": "Live tuning: packets → sounds (continuous/discrete)",
    "ui.language": "Language",

    "btn.audio_start": "Start audio",
    "btn.audio_stop": "Stop audio",
    "btn.panic": "Panic (mute)",

    "title.audio_toggle": "Start/stop WebAudio. Browsers require a user gesture to play audio.",
    "title.panic": "Briefly mutes audio (useful if it gets too loud).",
    "title.refresh_interfaces": "Refresh interface list.",

    "section.state": "Status",
    "label.connection": "Connection",
    "label.interface": "Interface",
    "label.block": "Block",
    "label.total_pps": "Total (pps)",
    "label.inout_pps": "In/Out (pps)",

    "tip.interface": "Choose the network interface to listen on (e.g. wlan0, enp…). Changes apply immediately. Under VPN, this can be tailscale0/tun0.",
    "tip.block": "Time step used to compute pps and update audio. Smaller = more reactive but more jittery.",
    "tip.pps": "pps = packets per second (estimated over the last block).",
    "tip.inout": "In = incoming (to your machine), Out = outgoing (from your machine).",

    "section.environment": "Environment",
    "label.preset": "Preset",
    "label.name": "Name",
    "ph.env_name": "e.g. my-garden",
    "btn.save": "Save",
    "label.overwrite": "overwrite if exists",
    "title.save_preset": "Save the current settings as a preset with this name.",
    "title.overwrite": "If checked, replaces an existing preset with the same name.",
    "tip.preset": "A preset (environment) is a bundle of settings (background + channels). Selecting it applies immediately. “Save” stores the current settings as a preset (in memory + environments/), and “Save config” writes everything to the JSON file.",
    "hint.preset_apply": "Selecting a preset copies it into the current config. “Save” stores the current config as a preset.",

    "section.import_sounds": "Import sounds",
    "btn.import": "Import",
    "title.choose_audio": "Choose an audio file (.wav recommended). It will be copied into samples/.",
    "title.import_sound": "Imports the selected file into samples/ and refreshes sound lists.",
    "title.refresh_sounds": "Refresh sound list from samples/.",
    "hint.imported_stored": "Imported files are stored in `samples/` and show up in “sound” lists.",
    "label.listen_sounds": "Preview sounds:",

    "section.charts": "Charts",
    "label.pps": "pps",
    "label.top_channels": "top channels",
    "title.toggle_pps": "Show/hide the pps curve.",
    "title.toggle_top": "Show/hide the bar chart (top channels).",
    "chart.pps_title": "pps (total / in / out)",
    "chart.top_title": "Top channels (instant pps)",
    "legend.total": "total",
    "legend.in": "in",
    "legend.out": "out",
    "title.chart_pps": "pps over the last moments (sliding window).",
    "title.chart_top_in": "Top incoming channels (in.*) for the last block.",
    "title.chart_top_out": "Top outgoing channels (out.*) for the last block.",

    "section.recording": "Recording",
    "btn.record_start": "Record",
    "btn.record_stop": "Stop",
    "title.record": "Records the browser audio output (what you hear). Click again to stop.",
    "link.download": "download",
    "tip.recording": "Recording is done in the browser (WebAudio). The file is usually .webm (Opus), depending on browser support.",
    "status.recording": "● recording…",
    "status.file_ready": "file ready",

    "section.background": "Background (continuous)",
    "bg.sound": "Sound",
    "bg.volume": "Volume",
    "bg.rate": "Rate (packets/s)",
    "bg.gamma": "Gamma",
    "bg.cutoff": "Cutoff Hz",
    "btn.save_config": "Save config",
    "tip.bg.sound": "Continuous background loop whose volume follows total network activity. Example: stream/wind/waves. Pick a file from samples/, a builtin (@noise), or “no background”.",
    "tip.bg.volume": "Maximum background volume (then modulated by traffic).",
    "tip.bg.rate": "Reference rate (packets/s): when traffic is around this value, volume reaches ~max (depending on Gamma).",
    "tip.bg.gamma": "Response curve: smaller = rises fast; larger = more progressive (less sensitive to small variations).",
    "tip.bg.cutoff": "Noise low-pass filter: low = darker/softer; high = brighter/hissier.",

    "section.channels": "Channels (by type + direction)",
    "hint.mode_explain_html": "Mode <span class=\"pill\">loop</span> = continuous (loop, volume follows rate). Mode <span class=\"pill\">one-shot</span> = discrete events.",
    "footer.hint_audio": "Tip: if you hear nothing, click “Start audio” (WebAudio requires a user gesture).",

    "th.active": "on",
    "th.key": "Key",
    "th.pps": "pps",
    "th.hint": "hint",
    "th.mode": "mode",
    "th.sound": "sound",
    "th.freq": "freq",
    "th.dur": "dur",
    "th.volume": "volume",
    "th.rate": "rate",
    "th.gamma": "gamma",
    "th.listen": "listen",
    "tip.th.active": "Enable/disable this channel (persisted in the config).",
    "tip.th.key": "Type + direction (in.=incoming, out.=outgoing). Hover a key for a short definition + examples.",
    "tip.th.pps": "pps = packets per second (estimated over the last block).",
    "tip.th.hint": "Suggested “continuous” vs “discrete”. It’s just a starting point: tune based on your traffic.",
    "tip.th.mode": "one-shot plays discrete events. loop plays a continuous sound whose volume follows the rate.",
    "tip.th.sound": "Pick a file in samples/ OR a builtin sound (@chirp/@drone/@noise).",
    "tip.th.freq": "Frequency (Hz) used only for builtin sounds (@chirp/@drone).",
    "tip.th.dur": "Duration (ms) used only for @chirp.",
    "tip.th.volume": "Maximum channel volume (then modulated by rate and Gamma).",
    "tip.th.rate": "Reference rate (packets/s): when pps≈rate, volume reaches ~max (depending on Gamma).",
    "tip.th.gamma": "Response curve: smaller = rises fast; larger = more progressive.",
    "tip.th.listen": "Mute a channel (M), solo it (S), or play a test sound (▶).",

    "opt.none": "(none)",
    "opt.current": "(current)",
    "status.capture": "capture: {{name}}{{backend}}",
    "status.capture_stopped": "capture: stopped",
    "status.capture_not_running": "capture not running",
    "status.presets_loaded": "Presets loaded: {{n}}",
    "status.presets_none": "No presets loaded (check the environments/ folder).",

    "hint.reco.cont": "continuous",
    "hint.reco.disc": "discrete",
    "hint.reco.na": "—",

    "title.ch.enabled": "Enable/disable this channel (persisted).",
    "title.ch.mode": "Mode: one-shot (events) or loop (continuous).",
    "title.ch.sound": "Pick a file from samples/ or a builtin (@chirp/@drone/@noise).",
    "title.ch.freq": "Frequency (Hz) used by builtin sounds (@chirp/@drone).",
    "title.ch.dur": "Duration (ms) used only for @chirp (one-shot).",
    "title.ch.vol": "Maximum channel volume (then modulated by rate).",
    "title.ch.ref": "Reference rate (packets/s): when pps≈rate, volume reaches ~max (depending on gamma).",
    "title.ch.gamma": "Response curve: smaller = rises fast; larger = more progressive.",
    "title.ch.mute_on": "Unmute this channel",
    "title.ch.mute_off": "Mute this channel",
    "title.ch.solo_on": "Disable solo",
    "title.ch.solo_off": "Solo this channel",

    "alert.start_audio_first": "Click “Start audio” first.",
    "alert.record_failed": "Recording failed: {{msg}}",
    "title.sample_play_once": "Play once",
    "title.sample_loop_toggle": "Loop / stop",
    "msg.ok": "OK",
    "msg.loading": "…",
    "msg.saved": "saved",
    "msg.loaded": "loaded",
    "msg.error_prefix": "Error: {{msg}}",
    "msg.ok_to": "OK → {{path}}",
    "msg.max_pps": "max {{v}} pps",
    "msg.no_samples": "No sounds yet (import a file or download via the script).",
    "msg.download_with_size": "download ({{mb}} MB)",
    "conn.connecting": "connecting…",
    "conn.ok": "ok",
    "conn.offline": "offline",
    "conn.error": "error",
    "err.choose_preset": "choose a preset",
    "err.name_required": "name required",
    "err.choose_file": "choose a file",

    "builtin.none": "no background",
    "builtin.noise": "@noise (builtin: noise)",
    "builtin.chirp": "@chirp (builtin: chirp)",
    "builtin.drone": "@drone (builtin: drone)",
  },
};

function _getLangDict(code) {
  return I18N[code] || I18N.fr;
}

function t(key, vars = null) {
  const dict = _getLangDict(lang);
  let s = (dict && dict[key]) ?? (I18N.fr[key] ?? key);
  if (vars && typeof s === "string") {
    for (const [k, v] of Object.entries(vars)) {
      s = s.replaceAll(`{{${k}}}`, String(v));
    }
  }
  return s;
}

function applyI18n() {
  try { document.documentElement.lang = lang; } catch {}

  for (const el of document.querySelectorAll("[data-i18n]")) {
    const k = el.getAttribute("data-i18n");
    if (!k) continue;
    el.textContent = t(k);
  }
  for (const el of document.querySelectorAll("[data-i18n-html]")) {
    const k = el.getAttribute("data-i18n-html");
    if (!k) continue;
    el.innerHTML = t(k);
  }
  for (const el of document.querySelectorAll("[data-i18n-title]")) {
    const k = el.getAttribute("data-i18n-title");
    if (!k) continue;
    el.setAttribute("title", t(k));
  }
  for (const el of document.querySelectorAll("[data-i18n-tip]")) {
    const k = el.getAttribute("data-i18n-tip");
    if (!k) continue;
    el.setAttribute("data-tip", t(k));
  }
  for (const el of document.querySelectorAll("[data-i18n-placeholder]")) {
    const k = el.getAttribute("data-i18n-placeholder");
    if (!k) continue;
    el.setAttribute("placeholder", t(k));
  }

  const titleEl = document.querySelector("title[data-i18n]");
  if (titleEl) titleEl.textContent = t(titleEl.getAttribute("data-i18n"));

  updateAudioButtonUi();
  refreshRecordingUi();
}

function loadLang() {
  let saved = null;
  try { saved = localStorage.getItem("flowSonify.lang"); } catch {}
  if (saved === "fr" || saved === "en") {
    lang = saved;
  } else {
    const n = (navigator.language || "").toLowerCase();
    lang = n.startsWith("fr") ? "fr" : "en";
  }
  const sel = els("langSelect");
  if (sel) sel.value = lang;
}

function setLang(code) {
  if (code !== "fr" && code !== "en") return;
  lang = code;
  try { localStorage.setItem("flowSonify.lang", lang); } catch {}
  applyI18n();
  renderConfig();
  renderSamplesList();
}

function initLangSelect() {
  const sel = els("langSelect");
  if (!sel) return;
  sel.value = lang;
  sel.addEventListener("change", () => setLang(sel.value));
}

const HIST_LEN = 180;
const hist = { total: [], in: [], out: [] };
const uiState = {
  showChartPps: true,
  showChartTop: true,
  mutedKeys: new Set(),
  soloKey: null,
};

const COLORS = {
  total: "rgba(90,166,255,0.95)",
  in: "rgba(73,211,139,0.85)",
  out: "rgba(255,90,111,0.85)",
  barTcp: "rgba(90,166,255,0.35)",
  barUdp: "rgba(73,211,139,0.35)",
  barDns: "rgba(255,205,77,0.40)",
  barIcmp: "rgba(255,90,111,0.35)",
  barOther: "rgba(165,178,207,0.25)",
};

function fmt(n) {
  if (!isFinite(n)) return "—";
  return n.toFixed(1);
}

function updateAudioButtonUi() {
  const b = els("audioToggle");
  if (!b) return;
  if (audio) {
    b.textContent = t("btn.audio_stop");
    b.classList.remove("primary");
    b.classList.add("danger");
  } else {
    b.textContent = t("btn.audio_start");
    b.classList.add("primary");
    b.classList.remove("danger");
  }
}

function loadUiState() {
  try {
    const raw = JSON.parse(localStorage.getItem("flowSonify.ui") || "{}");
    uiState.showChartPps = raw.showChartPps !== false;
    uiState.showChartTop = raw.showChartTop !== false;
    uiState.soloKey = raw.soloKey || null;
    uiState.mutedKeys = new Set(Array.isArray(raw.mutedKeys) ? raw.mutedKeys : []);
  } catch {
    // ignore
  }
}

function saveUiState() {
  try {
    localStorage.setItem("flowSonify.ui", JSON.stringify({
      showChartPps: uiState.showChartPps,
      showChartTop: uiState.showChartTop,
      soloKey: uiState.soloKey,
      mutedKeys: Array.from(uiState.mutedKeys),
    }));
  } catch {
    // ignore
  }
}

async function fetchConfig() {
  const r = await fetch("/api/config");
  config = await r.json();
  blockMs = config.block_ms || 100;
  renderConfig();
}

async function fetchSamples() {
  try {
    const r = await fetch("/api/samples");
    const out = await r.json();
    samples = (out.samples || []).slice();
  } catch {
    samples = [];
  }
}

async function fetchInterfaces() {
  try {
    const r = await fetch("/api/interfaces");
    const out = await r.json();
    interfaces = (out.interfaces || []).slice();
  } catch {
    interfaces = [];
  }
}

async function fetchInterfaceStatus() {
  try {
    const r = await fetch("/api/interface");
    const out = await r.json();
    currentIface = out.interface || null;
    captureBackend = out.backend || null;
    captureRunning = !!out.running;
    captureError = out.error || null;
  } catch {
    currentIface = null;
    captureBackend = null;
    captureRunning = false;
    captureError = null;
  }
}

async function setInterface(name) {
  const r = await fetch("/api/interface", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ interface: name }),
  });
  const out = await r.json();
  if (out.error) throw new Error(out.error);
  currentIface = out.interface || null;
  captureBackend = out.backend || null;
  captureRunning = ("running" in out) ? !!out.running : captureRunning;
  captureError = out.error || null;
}

async function envApply(name) {
  const r = await fetch("/api/env/apply", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  const out = await r.json();
  if (out.error) throw new Error(out.error);
  config = out;
  blockMs = config.block_ms || blockMs;
  renderConfig();
}

async function envSave(name, overwrite) {
  const r = await fetch("/api/env/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, overwrite: !!overwrite }),
  });
  const out = await r.json();
  if (out.error) throw new Error(out.error);
  config = out;
  blockMs = config.block_ms || blockMs;
  renderConfig();
}

async function uploadSample(file) {
  const fd = new FormData();
  fd.append("file", file, file.name);
  const r = await fetch("/api/upload", { method: "POST", body: fd });
  const out = await r.json();
  if (out.error) throw new Error(out.error);
  samples = (out.samples || []).slice();
  renderConfig();
  renderSamplesList();
  return out.saved;
}

async function patchConfig(patch) {
  const r = await fetch("/api/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  const out = await r.json();
  if (out && out.error) throw new Error(out.error);
  config = out;
  blockMs = config.block_ms || blockMs;
}

async function saveConfig() {
  const path = els("savePath").value || "flow_sonify_default.json";
  const r = await fetch("/api/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  });
  const out = await r.json();
  if (out.error) throw new Error(out.error);
  return out.saved;
}

function renderConfig() {
  if (!config) return;
  els("block").textContent = `${blockMs} ms`;

  // interface selector
  const sel = els("ifaceSelect");
  if (sel) {
    sel.innerHTML = "";
    const o0 = document.createElement("option");
    o0.value = "";
    o0.textContent = t("opt.none");
    sel.appendChild(o0);
    for (const name of interfaces) {
      const o = document.createElement("option");
      o.value = name;
      o.textContent = name;
      sel.appendChild(o);
    }
    sel.value = currentIface || "";
  }
  const st = els("ifaceStatus");
  if (st) {
    if (currentIface) {
      const base = t("status.capture", { name: currentIface, backend: captureBackend ? ` (${captureBackend})` : "" });
      if (captureError) st.textContent = `${base} — ${t("msg.error_prefix", { msg: captureError })}`;
      else if (captureRunning === false) st.textContent = `${base} — ${t("status.capture_not_running")}`;
      else st.textContent = base;
    } else {
      st.textContent = t("status.capture_stopped");
    }
  }

  // environments
  const envs = config.environments || {};
  const envSelect = els("envSelect");
  envSelect.innerHTML = "";
  const optC = document.createElement("option");
  optC.value = "";
  optC.textContent = t("opt.current");
  envSelect.appendChild(optC);
  for (const name of Object.keys(envs).sort()) {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    envSelect.appendChild(opt);
  }
  envSelect.value = config.active_environment || "";
  els("envName").value = config.active_environment || "";
  const envHint = els("envHint");
  if (envHint) {
    const n = Object.keys(envs).length;
    envHint.textContent = n
      ? t("status.presets_loaded", { n })
      : t("status.presets_none");
  }

  const river = config.river || {};
  els("riverGain").value = river.gain ?? 0.18;
  els("riverRef").value = river.ref_pps ?? 250;
  els("riverGamma").value = river.gamma ?? 0.65;
  els("riverCutoff").value = river.cutoff_hz ?? 900;

  const riverSample = els("riverSample");
  riverSample.innerHTML = "";
  for (const s of ["@none", ...samples]) {
    const opt = document.createElement("option");
    opt.value = s;
    opt.textContent = sampleLabel(s);
    riverSample.appendChild(opt);
  }
  riverSample.value = river.sample ?? "@noise";

  const tbody = els("channels").querySelector("tbody");
  tbody.innerHTML = "";
  const channels = config.channels || {};
  const keys = Object.keys(channels).sort();
  for (const key of keys) {
    const ch = channels[key] || {};
    const tr = document.createElement("tr");

    const tdOn = document.createElement("td");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = (ch.enabled ?? true);
    cb.title = t("title.ch.enabled");
    cb.addEventListener("change", async () => {
      await patchConfig({ channels: { [key]: { enabled: !!cb.checked } } });
    });
    tdOn.appendChild(cb);
    tr.appendChild(tdOn);

    const tdKey = document.createElement("td");
    tdKey.textContent = key;
    tdKey.className = "key";
    const info = keyInfo(key);
    if (info) tdKey.title = info;
    tr.appendChild(tdKey);

    const tdPps = document.createElement("td");
    tdPps.className = "num";
    tdPps.textContent = fmt(0.0);
    tdPps.dataset.key = key;
    tr.appendChild(tdPps);

    const tdHint = document.createElement("td");
    tdHint.className = "hint";
    tdHint.textContent = recommendedHint(key);
    tr.appendChild(tdHint);

    const tdMode = document.createElement("td");
    const sel = document.createElement("select");
    for (const m of ["one-shot", "loop"]) {
      const opt = document.createElement("option");
      opt.value = m;
      opt.textContent = m;
      sel.appendChild(opt);
    }
    sel.value = (ch.mode || "one-shot");
    sel.title = t("title.ch.mode");
    sel.addEventListener("change", async () => {
      await patchConfig({ channels: { [key]: { mode: sel.value } } });
    });
    tdMode.appendChild(sel);
    tr.appendChild(tdMode);

    const tdSample = document.createElement("td");
    const selS = document.createElement("select");
    for (const s of samples) {
      const opt = document.createElement("option");
      opt.value = s;
      opt.textContent = sampleLabel(s);
      selS.appendChild(opt);
    }
    selS.value = ch.sample ?? "@chirp";
    selS.title = t("title.ch.sound");
    const setSynthControls = () => {
      const builtin = isBuiltin(selS.value);
      inFreq.disabled = !builtin || selS.value === "@noise";
      inDur.disabled = !builtin || selS.value !== "@chirp";
    };
    selS.addEventListener("change", async () => {
      await patchConfig({ channels: { [key]: { sample: selS.value } } });
      setSynthControls();
    });
    tdSample.appendChild(selS);
    tr.appendChild(tdSample);

    const tdFreq = document.createElement("td");
    const inFreq = document.createElement("input");
    inFreq.type = "number";
    inFreq.min = "40";
    inFreq.max = "8000";
    inFreq.step = "1";
    inFreq.value = ch.freq_hz ?? 1000;
    inFreq.title = t("title.ch.freq");
    inFreq.addEventListener("change", async () => {
      await patchConfig({ channels: { [key]: { freq_hz: parseFloat(inFreq.value) } } });
    });
    tdFreq.appendChild(inFreq);
    tr.appendChild(tdFreq);

    const tdDur = document.createElement("td");
    const inDur = document.createElement("input");
    inDur.type = "number";
    inDur.min = "10";
    inDur.max = "600";
    inDur.step = "1";
    inDur.value = ch.duration_ms ?? 80;
    inDur.title = t("title.ch.dur");
    inDur.addEventListener("change", async () => {
      await patchConfig({ channels: { [key]: { duration_ms: parseInt(inDur.value, 10) } } });
    });
    tdDur.appendChild(inDur);
    tr.appendChild(tdDur);

    const tdGain = document.createElement("td");
    const inGain = document.createElement("input");
    inGain.type = "number";
    inGain.min = "0";
    inGain.max = "1.0";
    inGain.step = "0.005";
    inGain.value = ch.gain ?? 0.12;
    inGain.title = t("title.ch.vol");
    inGain.addEventListener("change", async () => {
      await patchConfig({ channels: { [key]: { gain: parseFloat(inGain.value) } } });
    });
    tdGain.appendChild(inGain);
    tr.appendChild(tdGain);

    const tdRef = document.createElement("td");
    const inRef = document.createElement("input");
    inRef.type = "number";
    inRef.min = "1";
    inRef.max = "50000";
    inRef.step = "1";
    inRef.value = ch.ref_pps ?? 50;
    inRef.title = t("title.ch.ref");
    inRef.addEventListener("change", async () => {
      await patchConfig({ channels: { [key]: { ref_pps: parseFloat(inRef.value) } } });
    });
    tdRef.appendChild(inRef);
    tr.appendChild(tdRef);

    const tdGamma = document.createElement("td");
    const inGamma = document.createElement("input");
    inGamma.type = "number";
    inGamma.min = "0.1";
    inGamma.max = "3";
    inGamma.step = "0.05";
    inGamma.value = ch.gamma ?? 0.75;
    inGamma.title = t("title.ch.gamma");
    inGamma.addEventListener("change", async () => {
      await patchConfig({ channels: { [key]: { gamma: parseFloat(inGamma.value) } } });
    });
    tdGamma.appendChild(inGamma);
    tr.appendChild(tdGamma);

    const tdTest = document.createElement("td");
    tdTest.className = "listen";
    const m = document.createElement("button");
    m.className = "mini";
    m.textContent = uiState.mutedKeys.has(key) ? "M" : "M";
    m.title = uiState.mutedKeys.has(key) ? t("title.ch.mute_on") : t("title.ch.mute_off");
    if (uiState.mutedKeys.has(key)) m.classList.add("danger");
    m.addEventListener("click", () => {
      if (uiState.mutedKeys.has(key)) uiState.mutedKeys.delete(key);
      else uiState.mutedKeys.add(key);
      saveUiState();
      if (audio) audio.setOverrides(uiState);
      renderConfig();
    });

    const s = document.createElement("button");
    s.className = "mini";
    s.textContent = "S";
    const isSolo = uiState.soloKey === key;
    s.title = isSolo ? t("title.ch.solo_on") : t("title.ch.solo_off");
    if (isSolo) s.classList.add("primary");
    s.addEventListener("click", () => {
      uiState.soloKey = (uiState.soloKey === key) ? null : key;
      saveUiState();
      if (audio) audio.setOverrides(uiState);
      renderConfig();
    });

    const b = document.createElement("button");
    b.className = "mini";
    b.textContent = "▶";
    b.addEventListener("click", () => {
      if (!audio) return;
      audio.playTest(key);
    });
    tdTest.appendChild(m);
    tdTest.appendChild(s);
    tdTest.appendChild(b);
    tr.appendChild(tdTest);

    // init enable/disable synth-only controls
    setSynthControls();

    tbody.appendChild(tr);
  }
}

function isBuiltin(name) {
  return typeof name === "string" && name.startsWith("@");
}

function sampleLabel(name) {
  if (name === "@none") return t("builtin.none");
  if (name === "@noise") return t("builtin.noise");
  if (name === "@chirp") return t("builtin.chirp");
  if (name === "@drone") return t("builtin.drone");
  return name;
}

function keyInfo(key) {
  const dir = key.startsWith("in.") ? "in" : key.startsWith("out.") ? "out" : null;
  const suffix = key.includes(".") ? key.split(".").slice(1).join(".") : key;
  const isTotalAnyDir = key.endsWith(".total") && !dir;
  const baseProto = isTotalAnyDir ? key.split(".", 1)[0] : suffix;

  const pack = {
    fr: {
      dir: {
        in: "Direction: entrant (vers ta machine)",
        out: "Direction: sortant (depuis ta machine)",
        total: "Direction: total (entrant+sortant)",
      },
      proto: {
        net: [
          "Total réseau: tous les paquets observés sur l’interface (entrant+sortant).",
          "Exemples: toute activité réseau.",
        ],
        tcp: [
          "TCP: protocole fiable orienté connexion (la majorité du Web/HTTPS, SSH, SMTP, etc.).",
          "Exemples: ouvrir un site, télécharger, faire un `git pull`, envoyer un mail via SMTP, se connecter en SSH.",
        ],
        udp: [
          "UDP: datagrammes sans connexion (rapide, peu de garanties).",
          "Exemples: DNS, QUIC/HTTP3, jeux en ligne, VoIP, streaming, découverte réseau.",
        ],
        dns: [
          "DNS: résout un nom (ex: example.com) en IP.",
          "Exemples: ouvrir un site, lancer une appli, mises à jour, client mail, telemetry/captive-portal.",
        ],
        icmp: [
          "ICMP: messages de contrôle/erreur IP (ping, unreachable, fragmentation/PMTU…).",
          "Exemples: `ping`, `traceroute`, problèmes réseau/MTU, hôte injoignable.",
        ],
        total: [
          "Total: tout paquet classé entrant/sortant (toutes catégories confondues).",
          "Exemples: toute activité réseau.",
        ],
      },
    },
    en: {
      dir: {
        in: "Direction: incoming (to your machine)",
        out: "Direction: outgoing (from your machine)",
        total: "Direction: total (incoming+outgoing)",
      },
      proto: {
        net: [
          "Network total: all packets observed on the interface (incoming+outgoing).",
          "Examples: any network activity.",
        ],
        tcp: [
          "TCP: reliable connection-oriented protocol (most of the Web/HTTPS, SSH, SMTP, etc.).",
          "Examples: open a website, download, `git pull`, send mail via SMTP, SSH login.",
        ],
        udp: [
          "UDP: connectionless datagrams (fast, fewer guarantees).",
          "Examples: DNS, QUIC/HTTP3, online games, VoIP, streaming, network discovery.",
        ],
        dns: [
          "DNS: resolves a name (e.g. example.com) to an IP address.",
          "Examples: open a website, start an app, updates, mail client, telemetry/captive-portal.",
        ],
        icmp: [
          "ICMP: IP control/error messages (ping, unreachable, fragmentation/PMTU…).",
          "Examples: `ping`, `traceroute`, MTU issues, unreachable host.",
        ],
        total: [
          "Total: all packets classified as in/out (all categories combined).",
          "Examples: any network activity.",
        ],
      },
    },
  }[lang] || null;

  if (!pack) return null;
  const base = pack.proto[baseProto] || null;
  if (!base) return null;
  const prefixTxt = isTotalAnyDir ? pack.dir.total : (dir ? pack.dir[dir] : pack.dir.total);
  return [prefixTxt, "", ...base].join("\n");
}

function recommendedHint(key) {
  if (key === "net.total") return t("hint.reco.cont");
  if (key.startsWith("tcp.") || key.endsWith(".tcp")) return t("hint.reco.cont");
  if (key.startsWith("udp.") || key.endsWith(".udp")) return t("hint.reco.cont");
  if (key.startsWith("dns.") || key.endsWith(".dns")) return t("hint.reco.disc");
  if (key.startsWith("icmp.") || key.endsWith(".icmp")) return t("hint.reco.disc");
  if (key.endsWith(".total")) return t("hint.reco.cont");
  return t("hint.reco.na");
}

function ppsFromCounts(key, counts, blockMs) {
  const c = counts[key] || 0;
  return c / (blockMs / 1000.0);
}

function gainFromPps(pps, ref, gamma, baseGain) {
  const x = Math.max(0, pps) / Math.max(1e-6, ref);
  const y = Math.pow(Math.min(1.0, x), gamma);
  return baseGain * y;
}

class WebAudioEngine {
  constructor() {
    this.ctx = new (window.AudioContext || window.webkitAudioContext)();
    this.master = this.ctx.createGain();
    this.master.gain.value = 0.9;
    this.master.connect(this.ctx.destination);
    this.recDest = this.ctx.createMediaStreamDestination();
    this.master.connect(this.recDest);
    this.recorder = null;
    this.recChunks = [];
    this.recMime = null;

    this.riverBus = this.ctx.createGain();
    this.riverBus.gain.value = 0.0;
    this.riverFilter = this.ctx.createBiquadFilter();
    this.riverFilter.type = "lowpass";
    this.riverFilter.frequency.value = 900;
    this.riverBus.connect(this.riverFilter);
    this.riverFilter.connect(this.master);

    this.riverNoiseGain = this.ctx.createGain();
    this.riverNoiseGain.gain.value = 1.0;
    this.riverNoiseGain.connect(this.riverBus);

    this.riverSampleGain = this.ctx.createGain();
    this.riverSampleGain.gain.value = 0.0;
    this.riverSampleGain.connect(this.riverBus);

    this.riverSrc = this._makeNoise();
    this.riverSrc.connect(this.riverNoiseGain);
    this.riverSrc.start();

    this.drones = new Map(); // key -> {osc, gain}
    this.noises = new Map(); // key -> {src, gain, filter}
    this.buffers = new Map(); // name -> AudioBuffer
    this.loading = new Map(); // name -> Promise<AudioBuffer>
    this.loopSamples = new Map(); // key -> {src, gain, name}
    this.riverLoop = null; // {src, name} | null
    this.muted = false;

    this.mutedKeys = new Set();
    this.soloKey = null;
    this.previewLoop = null; // {src, name} | null
  }

  _pickMime() {
    const candidates = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/ogg;codecs=opus",
      "audio/ogg",
    ];
    for (const c of candidates) {
      try {
        if (window.MediaRecorder && MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(c)) return c;
      } catch {}
    }
    return "";
  }

  startRecording() {
    if (!window.MediaRecorder) throw new Error("MediaRecorder indisponible dans ce navigateur");
    if (this.recorder && this.recorder.state !== "inactive") return;

    this.recChunks = [];
    const mimeType = this._pickMime();
    this.recMime = mimeType || null;
    const opts = mimeType ? { mimeType } : undefined;
    const rec = new MediaRecorder(this.recDest.stream, opts);
    rec.ondataavailable = (ev) => {
      if (ev.data && ev.data.size > 0) this.recChunks.push(ev.data);
    };
    rec.start(250);
    this.recorder = rec;
  }

  stopRecording() {
    const rec = this.recorder;
    if (!rec) return Promise.resolve(null);
    if (rec.state === "inactive") return Promise.resolve(null);
    return new Promise((resolve) => {
      rec.onstop = () => {
        const mime = this.recMime || (this.recChunks[0] ? this.recChunks[0].type : "") || "audio/webm";
        const blob = new Blob(this.recChunks, { type: mime });
        this.recorder = null;
        this.recChunks = [];
        this.recMime = null;
        resolve(blob);
      };
      try { rec.stop(); } catch { resolve(null); }
    });
  }

  _makeNoise() {
    const bufferSize = 2 * this.ctx.sampleRate;
    const buffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < bufferSize; i++) data[i] = Math.random() * 2 - 1;
    const src = this.ctx.createBufferSource();
    src.buffer = buffer;
    src.loop = true;
    return src;
  }

  setMuted(m) {
    this.muted = !!m;
    this.master.gain.value = this.muted ? 0.0 : 0.9;
  }

  ensureDrone(key, freqHz) {
    if (this.drones.has(key)) return this.drones.get(key);
    const osc = this.ctx.createOscillator();
    osc.type = "sine";
    osc.frequency.value = freqHz;
    const g = this.ctx.createGain();
    g.gain.value = 0.0;
    osc.connect(g);
    g.connect(this.master);
    osc.start();
    const node = { osc, gain: g };
    this.drones.set(key, node);
    return node;
  }

  ensureNoise(key, cutoffHz) {
    if (this.noises.has(key)) return this.noises.get(key);
    const src = this._makeNoise();
    const g = this.ctx.createGain();
    g.gain.value = 0.0;
    const f = this.ctx.createBiquadFilter();
    f.type = "lowpass";
    f.frequency.value = cutoffHz || 800;
    src.connect(g);
    g.connect(f);
    f.connect(this.master);
    src.start();
    const node = { src, gain: g, filter: f };
    this.noises.set(key, node);
    return node;
  }

  setRiver(level, cutoffHz) {
    this.riverFilter.frequency.setTargetAtTime(cutoffHz, this.ctx.currentTime, 0.05);
    this.riverBus.gain.setTargetAtTime(level, this.ctx.currentTime, 0.08);
  }

  playChirp(freqHz, durMs, level) {
    const t0 = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    osc.type = "triangle";
    osc.frequency.value = freqHz;
    osc.detune.value = (Math.random() * 20 - 10);
    const g = this.ctx.createGain();
    g.gain.value = 0.0;
    osc.connect(g);
    g.connect(this.master);

    const dur = Math.max(0.02, durMs / 1000.0);
    const a = Math.min(0.02, dur * 0.15);
    const r = Math.min(0.08, dur * 0.5);

    g.gain.setValueAtTime(0.0, t0);
    g.gain.linearRampToValueAtTime(level, t0 + a);
    g.gain.setTargetAtTime(0.0, t0 + dur - r, r / 3);

    osc.start(t0);
    osc.stop(t0 + dur + 0.02);
  }

  playTest(key) {
    const ch = (config.channels || {})[key] || {};
    const level = Math.min(0.25, ch.gain ?? 0.12);
    const sample = ch.sample || "@chirp";
    if (sample === "@drone") {
      const node = this.ensureDrone(key, ch.freq_hz ?? 220);
      node.osc.frequency.setTargetAtTime(ch.freq_hz ?? 220, this.ctx.currentTime, 0.02);
      node.gain.gain.setTargetAtTime(level, this.ctx.currentTime, 0.03);
      node.gain.gain.setTargetAtTime(0.0, this.ctx.currentTime + 0.5, 0.10);
      return;
    }
    if (sample === "@noise") {
      const node = this.ensureNoise(key, 900);
      node.filter.frequency.setTargetAtTime(900, this.ctx.currentTime, 0.03);
      node.gain.gain.setTargetAtTime(level, this.ctx.currentTime, 0.05);
      node.gain.gain.setTargetAtTime(0.0, this.ctx.currentTime + 0.6, 0.15);
      return;
    }
    if (sample === "@chirp") {
      this.playChirp(ch.freq_hz ?? 1000, ch.duration_ms ?? 90, level);
      return;
    }
    this._playSample(sample, level);
  }

  tick(counts, blockMs) {
    const river = config.river || {};
    const total = (counts["net.total"] ?? ((counts["in.total"] || 0) + (counts["out.total"] || 0)));
    const totalPps = total / (blockMs / 1000.0);
    const riverLevel = gainFromPps(totalPps, river.ref_pps ?? 250, river.gamma ?? 0.65, river.gain ?? 0.18);
    this.setRiver(riverLevel, river.cutoff_hz ?? 900);
    this._setRiverSound(river.sample || "@noise");

    const activeLoopKeys = new Set();

    const channels = config.channels || {};
    for (const [key, ch] of Object.entries(channels)) {
      if (this.mutedKeys.has(key)) continue;
      if (this.soloKey && key !== this.soloKey) continue;
      if (ch.enabled === false) continue;

      const mode = (ch.mode || "one-shot");
      const sample = (ch.sample || "@chirp");
      const pps = ppsFromCounts(key, counts, blockMs);
      const level = gainFromPps(pps, ch.ref_pps ?? 50, ch.gamma ?? 0.75, ch.gain ?? 0.12);
      if (mode === "loop") {
        activeLoopKeys.add(key);
        if (sample === "@drone") {
          const node = this.ensureDrone(key, ch.freq_hz ?? 220);
          node.osc.frequency.setTargetAtTime(ch.freq_hz ?? 220, this.ctx.currentTime, 0.03);
          node.gain.gain.setTargetAtTime(level, this.ctx.currentTime, 0.08);
        } else if (sample === "@noise") {
          const node = this.ensureNoise(key, 900);
          node.filter.frequency.setTargetAtTime(900, this.ctx.currentTime, 0.05);
          node.gain.gain.setTargetAtTime(level, this.ctx.currentTime, 0.10);
        } else {
          this._setLoopSample(key, sample, level);
        }
        continue;
      }

      // one-shot
      const count = counts[key] || 0;
      const n = Math.min(count, 4);
      if (n <= 0) continue;
      if (sample === "@chirp") {
        for (let i = 0; i < n; i++) this.playChirp(ch.freq_hz ?? 1000, ch.duration_ms ?? 80, level);
      } else if (sample === "@drone") {
        // fallback: short drone burst
        const node = this.ensureDrone(`oneshot.${key}`, ch.freq_hz ?? 220);
        node.osc.frequency.setTargetAtTime(ch.freq_hz ?? 220, this.ctx.currentTime, 0.02);
        node.gain.gain.setTargetAtTime(Math.min(0.35, level), this.ctx.currentTime, 0.03);
        node.gain.gain.setTargetAtTime(0.0, this.ctx.currentTime + 0.25, 0.08);
      } else if (sample === "@noise") {
        const node = this.ensureNoise(`oneshot.${key}`, 900);
        node.gain.gain.setTargetAtTime(Math.min(0.35, level), this.ctx.currentTime, 0.05);
        node.gain.gain.setTargetAtTime(0.0, this.ctx.currentTime + 0.25, 0.10);
      } else {
        for (let i = 0; i < Math.min(n, 2); i++) this._playSample(sample, level);
      }
    }

    // Fade down loop sources that are currently running but not active (mute/solo/disabled)
    for (const [k, node] of this.loopSamples.entries()) {
      if (!activeLoopKeys.has(k)) node.gain.gain.setTargetAtTime(0.0, this.ctx.currentTime, 0.15);
    }
    for (const [k, node] of this.drones.entries()) {
      if (!activeLoopKeys.has(k) && !k.startsWith("oneshot.")) node.gain.gain.setTargetAtTime(0.0, this.ctx.currentTime, 0.15);
    }
    for (const [k, node] of this.noises.entries()) {
      if (!activeLoopKeys.has(k) && !k.startsWith("oneshot.")) node.gain.gain.setTargetAtTime(0.0, this.ctx.currentTime, 0.20);
    }
  }

  setOverrides(state) {
    this.mutedKeys = new Set(state?.mutedKeys ? Array.from(state.mutedKeys) : []);
    this.soloKey = state?.soloKey || null;
  }

  async _loadBuffer(name) {
    if (isBuiltin(name)) throw new Error("builtin sound");
    if (this.buffers.has(name)) return this.buffers.get(name);
    if (this.loading.has(name)) return await this.loading.get(name);
    const p = (async () => {
      const r = await fetch(`/samples/${encodeURIComponent(name)}`);
      const ab = await r.arrayBuffer();
      const buf = await this.ctx.decodeAudioData(ab);
      this.buffers.set(name, buf);
      this.loading.delete(name);
      return buf;
    })().catch((e) => {
      this.loading.delete(name);
      throw e;
    });
    this.loading.set(name, p);
    return await p;
  }

  async _playSample(name, level) {
    try {
      const buf = await this._loadBuffer(name);
      const src = this.ctx.createBufferSource();
      src.buffer = buf;
      const g = this.ctx.createGain();
      g.gain.value = Math.min(0.6, level);
      src.connect(g);
      g.connect(this.master);
      src.start();
      src.stop(this.ctx.currentTime + Math.min(2.5, buf.duration + 0.02));
    } catch {
      // ignore
    }
  }

  async _setLoopSample(key, name, level) {
    const cur = this.loopSamples.get(key);
    if (cur && cur.name === name) {
      cur.gain.gain.setTargetAtTime(level, this.ctx.currentTime, 0.08);
      return;
    }
    if (cur) {
      try { cur.src.stop(); } catch {}
      this.loopSamples.delete(key);
    }
    try {
      const buf = await this._loadBuffer(name);
      const src = this.ctx.createBufferSource();
      src.buffer = buf;
      src.loop = true;
      const g = this.ctx.createGain();
      g.gain.value = 0.0;
      src.connect(g);
      g.connect(this.master);
      src.start();
      g.gain.setTargetAtTime(level, this.ctx.currentTime, 0.12);
      this.loopSamples.set(key, { src, gain: g, name });
    } catch {
      // ignore
    }
  }

  async _setRiverSound(sampleName) {
    const name = sampleName || "@noise";
    if (name === "@none") {
      this.riverNoiseGain.gain.setTargetAtTime(0.0, this.ctx.currentTime, 0.15);
      this.riverSampleGain.gain.setTargetAtTime(0.0, this.ctx.currentTime, 0.15);
      if (this.riverLoop) {
        try { this.riverLoop.src.stop(); } catch {}
        this.riverLoop = null;
      }
      return;
    }
    if (!isBuiltin(name) && name) {
      if (this.riverLoop && this.riverLoop.name === name) return;
      if (this.riverLoop) {
        try { this.riverLoop.src.stop(); } catch {}
        this.riverLoop = null;
      }
      try {
        const buf = await this._loadBuffer(name);
        const src = this.ctx.createBufferSource();
        src.buffer = buf;
        src.loop = true;
        src.connect(this.riverSampleGain);
        src.start();
        this.riverLoop = { src, name };

        // Only switch to sample once it is ready (avoid silence if load fails).
        this.riverNoiseGain.gain.setTargetAtTime(0.0, this.ctx.currentTime, 0.15);
        this.riverSampleGain.gain.setTargetAtTime(1.0, this.ctx.currentTime, 0.15);
      } catch {
        // keep noise if sample can't be loaded
        this.riverNoiseGain.gain.setTargetAtTime(1.0, this.ctx.currentTime, 0.15);
        this.riverSampleGain.gain.setTargetAtTime(0.0, this.ctx.currentTime, 0.15);
      }
      return;
    }

    this.riverNoiseGain.gain.setTargetAtTime(1.0, this.ctx.currentTime, 0.15);
    this.riverSampleGain.gain.setTargetAtTime(0.0, this.ctx.currentTime, 0.15);
    if (this.riverLoop) {
      try { this.riverLoop.src.stop(); } catch {}
      this.riverLoop = null;
    }
  }

  async previewOnce(name) {
    await this._playSample(name, 0.25);
  }

  async togglePreviewLoop(name) {
    if (this.previewLoop && this.previewLoop.name === name) {
      try { this.previewLoop.src.stop(); } catch {}
      this.previewLoop = null;
      return false;
    }
    if (this.previewLoop) {
      try { this.previewLoop.src.stop(); } catch {}
      this.previewLoop = null;
    }
    try {
      const buf = await this._loadBuffer(name);
      const src = this.ctx.createBufferSource();
      src.buffer = buf;
      src.loop = true;
      const g = this.ctx.createGain();
      g.gain.value = 0.18;
      src.connect(g);
      g.connect(this.master);
      src.start();
      this.previewLoop = { src, name };
      return true;
    } catch {
      return false;
    }
  }
}

function attachRiverControls() {
  const on = async () => {
    const patch = {
      river: {
        sample: els("riverSample").value,
        gain: parseFloat(els("riverGain").value),
        ref_pps: parseFloat(els("riverRef").value),
        gamma: parseFloat(els("riverGamma").value),
        cutoff_hz: parseFloat(els("riverCutoff").value),
      },
    };
    await patchConfig(patch);
  };
  for (const id of ["riverSample", "riverGain", "riverRef", "riverGamma", "riverCutoff"]) {
    els(id).addEventListener("change", on);
    els(id).addEventListener("input", id === "riverGain" ? on : () => {});
  }
}

function updateStats(counts) {
  const dt = (blockMs / 1000.0);
  const totalCount = (counts["net.total"] ?? ((counts["in.total"] || 0) + (counts["out.total"] || 0)));
  const totalPps = totalCount / dt;
  const inPps = (counts["in.total"] || 0) / dt;
  const outPps = (counts["out.total"] || 0) / dt;
  els("ppsTotal").textContent = fmt(totalPps);
  els("ppsDir").textContent = `${fmt(inPps)} / ${fmt(outPps)}`;

  const tds = document.querySelectorAll("td[data-key]");
  for (const td of tds) {
    const key = td.dataset.key;
    const pps = ppsFromCounts(key, counts, blockMs);
    td.textContent = fmt(pps);
  }
}

function startEvents() {
  const es = new EventSource("/api/events");
  els("conn").textContent = t("conn.connecting");
  es.addEventListener("ready", () => {
    els("conn").textContent = t("conn.ok");
    els("conn").className = "v ok";
  });
  es.addEventListener("tick", (ev) => {
    const data = JSON.parse(ev.data);
    lastCounts = data.counts || {};
    blockMs = data.block_ms || blockMs;
    els("block").textContent = `${blockMs} ms`;
    updateStats(lastCounts);
    if (audio) audio.tick(lastCounts, blockMs);
    pushHistory(lastCounts, blockMs);
    drawCharts(lastCounts, blockMs);
  });
  es.onerror = () => {
    els("conn").textContent = t("conn.offline");
    els("conn").className = "v bad";
  };
}

function pushHistory(counts, blockMs) {
  const dt = blockMs / 1000.0;
  const total = (counts["net.total"] ?? ((counts["in.total"] || 0) + (counts["out.total"] || 0))) / dt;
  const inn = (counts["in.total"] || 0) / dt;
  const out = (counts["out.total"] || 0) / dt;
  hist.total.push(total);
  hist.in.push(inn);
  hist.out.push(out);
  for (const k of ["total", "in", "out"]) {
    if (hist[k].length > HIST_LEN) hist[k].shift();
  }
}

function drawAxes(ctx, w, h) {
  ctx.strokeStyle = "rgba(34,48,77,0.8)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(0, h - 20);
  ctx.lineTo(w, h - 20);
  ctx.stroke();
}

function drawLine(ctx, arr, w, h, color, maxY) {
  if (!arr.length) return;
  const padB = 20;
  const padT = 10;
  const innerH = h - padT - padB;
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.beginPath();
  for (let i = 0; i < arr.length; i++) {
    const x = (i / Math.max(1, arr.length - 1)) * w;
    const y = padT + innerH * (1 - (arr[i] / Math.max(1e-6, maxY)));
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();
}

function drawCharts(counts, blockMs) {
  const boxPps = els("chartBoxPps");
  const boxTop = els("chartBoxTop");
  if (boxPps) boxPps.style.display = uiState.showChartPps ? "" : "none";
  if (boxTop) boxTop.style.display = uiState.showChartTop ? "" : "none";

  const dirSum = (counts["in.total"] || 0) + (counts["out.total"] || 0);
  const dirAvailable = dirSum > 0;
  const labIn = els("chartTopInLabel");
  const labOut = els("chartTopOutLabel");
  if (labIn && labOut) {
    if (dirAvailable) {
      labIn.textContent = "in.*";
      labOut.textContent = "out.*";
    } else {
      labIn.textContent = "total.* (direction inconnue)";
      labOut.textContent = "total.* (direction inconnue)";
    }
  }

  if (uiState.showChartPps) {
    const c1 = els("chartPps");
    const ctx1 = c1.getContext("2d");
    const w1 = c1.width, h1 = c1.height;
    ctx1.clearRect(0, 0, w1, h1);
    drawAxes(ctx1, w1, h1);

    const maxY = Math.max(
      10,
      ...hist.total.slice(-HIST_LEN),
      ...hist.in.slice(-HIST_LEN),
      ...hist.out.slice(-HIST_LEN)
    );
    drawLine(ctx1, hist.total, w1, h1, COLORS.total, maxY);
    drawLine(ctx1, hist.in, w1, h1, COLORS.in, maxY);
    drawLine(ctx1, hist.out, w1, h1, COLORS.out, maxY);

    ctx1.fillStyle = "rgba(165,178,207,0.9)";
    ctx1.font = "12px ui-sans-serif, system-ui";
    ctx1.fillText(t("msg.max_pps", { v: fmt(maxY) }), 8, 14);
  }

  if (uiState.showChartTop) {
    drawTypeBars("chartTopIn", counts, blockMs, "in.");
    drawTypeBars("chartTopOut", counts, blockMs, "out.");
  }
}

function drawTypeBars(canvasId, counts, blockMs, prefix) {
  const c = els(canvasId);
  if (!c) return;
  const ctx = c.getContext("2d");
  const w = c.width, h = c.height;
  ctx.clearRect(0, 0, w, h);
  drawAxes(ctx, w, h);

  const dt = blockMs / 1000.0;
  const dirSum = (counts["in.total"] || 0) + (counts["out.total"] || 0);
  const dirAvailable = dirSum > 0;
  const types = [
    { t: "tcp", color: COLORS.barTcp },
    { t: "udp", color: COLORS.barUdp },
    { t: "dns", color: COLORS.barDns },
    { t: "icmp", color: COLORS.barIcmp },
  ];
  const items = types.map(({ t, color }) => ({
    label: t,
    v: (dirAvailable ? (counts[`${prefix}${t}`] || 0) : (counts[`${t}.total`] || 0)) / dt,
    color,
  }));

  const padL = 8, padR = 8, padT = 10, padB = 20;
  const innerW = w - padL - padR;
  const innerH = h - padT - padB;
  const barW = 35;
  const gap = 24;
  const totalW = items.length * barW + (items.length - 1) * gap;
  const startX = padL + Math.max(0, (innerW - totalW) / 2);

  const maxB = Math.max(10, ...items.map((x) => x.v));

  for (let i = 0; i < items.length; i++) {
    const it = items[i];
    const bh = innerH * (it.v / maxB);
    const x = startX + i * (barW + gap);
    const y = padT + (innerH - bh);
    ctx.fillStyle = it.color;
    ctx.fillRect(x, y, barW, bh);
    ctx.fillStyle = "rgba(165,178,207,0.95)";
    ctx.font = "12px ui-sans-serif, system-ui";
    ctx.fillText(it.label, x, h - 6);
  }
  ctx.fillStyle = "rgba(165,178,207,0.9)";
  ctx.font = "12px ui-sans-serif, system-ui";
  ctx.fillText(t("msg.max_pps", { v: fmt(maxB) }), 8, 14);
}

function initAudioButtons() {
  const b = els("audioToggle");
  b.addEventListener("click", async () => {
    if (!audio) {
      audio = new WebAudioEngine();
      await audio.ctx.resume();
      audio.setOverrides(uiState);
      updateAudioButtonUi();
      refreshRecordingUi();
      return;
    }
    const a = audio;
    if (isRecording) {
      try {
        isRecording = false;
        refreshRecordingUi();
        const blob = await a.stopRecording();
        showRecordingBlob(blob);
      } catch {}
    }
    a.setMuted(true);
    audio = null;
    updateAudioButtonUi();
    refreshRecordingUi();
  });

  els("panic").addEventListener("click", () => {
    if (audio) audio.setMuted(true);
    setTimeout(() => { if (audio) audio.setMuted(false); }, 250);
  });
}

function initSaveButton() {
  els("saveConfig").addEventListener("click", async () => {
    els("saveStatus").textContent = t("msg.loading");
    try {
      const saved = await saveConfig();
      els("saveStatus").textContent = t("msg.ok_to", { path: saved });
      els("saveStatus").className = "muted ok";
    } catch (e) {
      els("saveStatus").textContent = t("msg.error_prefix", { msg: e.message });
      els("saveStatus").className = "muted bad";
    }
  });
}

function initEnvironmentControls() {
  const sel = els("envSelect");
  let busy = false;

  const setStatus = (msg, ok) => {
    const st = els("envStatus");
    if (!st) return;
    st.textContent = msg;
    st.className = ok ? "muted ok" : "muted bad";
  };

  const applyNow = async () => {
    if (busy) return;
    const name = sel.value;
    if (!name) {
      // "(courant)" => just clear active_environment without changing current river/channels
      await patchConfig({ active_environment: "" });
      setStatus("", true);
      return;
    }
    busy = true;
    sel.disabled = true;
    setStatus(t("msg.loading"), true);
    try {
      await envApply(name);
      setStatus(t("msg.loaded"), true);
    } catch (e) {
      setStatus(t("msg.error_prefix", { msg: e.message }), false);
    } finally {
      sel.disabled = false;
      busy = false;
    }
  };

  sel.addEventListener("change", applyNow);

  els("envSave").addEventListener("click", async () => {
    const name = (els("envName").value || "").trim();
    // UX: si on sauve sous le nom du preset actif, on overwrite automatiquement.
    const activeName = (config && (config.active_environment || "")) ? String(config.active_environment) : "";
    const overwrite = (name && activeName && name === activeName) ? true : els("envOverwrite").checked;
    els("envStatus").textContent = t("msg.loading");
    try {
      if (!name) throw new Error(t("err.name_required"));
      await envSave(name, overwrite);
      els("envStatus").textContent = t("msg.saved");
      els("envStatus").className = "muted ok";
    } catch (e) {
      els("envStatus").textContent = t("msg.error_prefix", { msg: e.message });
      els("envStatus").className = "muted bad";
    }
  });
}

function initUpload() {
  els("uploadBtn").addEventListener("click", async () => {
    const file = els("uploadFile").files?.[0];
    els("uploadStatus").textContent = t("msg.loading");
    try {
      if (!file) throw new Error(t("err.choose_file"));
      const saved = await uploadSample(file);
      els("uploadStatus").textContent = t("msg.ok_to", { path: saved });
      els("uploadStatus").className = "muted ok";
      els("uploadFile").value = "";
    } catch (e) {
      els("uploadStatus").textContent = t("msg.error_prefix", { msg: e.message });
      els("uploadStatus").className = "muted bad";
    }
  });
}

function initSamplesRefresh() {
  const b = els("samplesRefresh");
  if (!b) return;
  b.addEventListener("click", async () => {
    els("uploadStatus").textContent = t("msg.loading");
    try {
      await fetchSamples();
      renderConfig();
      renderSamplesList();
      els("uploadStatus").textContent = t("msg.ok");
      els("uploadStatus").className = "muted ok";
    } catch (e) {
      els("uploadStatus").textContent = t("msg.error_prefix", { msg: e?.message || e });
      els("uploadStatus").className = "muted bad";
    }
  });
}

function renderSamplesList() {
  const root = els("samplesList");
  if (!root) return;
  root.innerHTML = "";

  const wrap = document.createElement("div");
  wrap.className = "samples";

  if (!samples.length) {
    const empty = document.createElement("div");
    empty.className = "muted small";
    empty.textContent = t("msg.no_samples");
    wrap.appendChild(empty);
    root.appendChild(wrap);
    return;
  }

  const files = samples.filter((s) => !isBuiltin(s));
  for (const name of files) {
    const chip = document.createElement("div");
    chip.className = "chip";

    const label = document.createElement("span");
    label.className = "name";
    label.textContent = name;
    label.title = name;
    chip.appendChild(label);

    const bPlay = document.createElement("button");
    bPlay.textContent = "▶";
    bPlay.title = t("title.sample_play_once");
    bPlay.addEventListener("click", async () => {
      if (!audio) {
        alert(t("alert.start_audio_first"));
        return;
      }
      await audio.previewOnce(name);
    });
    chip.appendChild(bPlay);

    const bLoop = document.createElement("button");
    bLoop.textContent = "↻";
    bLoop.title = t("title.sample_loop_toggle");
    if (audio && audio.previewLoop && audio.previewLoop.name === name) bLoop.classList.add("primary");
    bLoop.addEventListener("click", async () => {
      if (!audio) {
        alert(t("alert.start_audio_first"));
        return;
      }
      await audio.togglePreviewLoop(name);
      renderSamplesList();
    });
    chip.appendChild(bLoop);

    wrap.appendChild(chip);
  }

  root.appendChild(wrap);
}

function initChartToggles() {
  const cPps = els("toggleChartPps");
  const cTop = els("toggleChartTop");
  cPps.checked = !!uiState.showChartPps;
  cTop.checked = !!uiState.showChartTop;

  const on = () => {
    uiState.showChartPps = !!cPps.checked;
    uiState.showChartTop = !!cTop.checked;
    saveUiState();
    drawCharts(lastCounts, blockMs);
  };
  cPps.addEventListener("change", on);
  cTop.addEventListener("change", on);
}

function initInterfaceControls() {
  const refresh = els("ifaceRefresh");
  const sel = els("ifaceSelect");
  let busy = false;

  const setStatus = (msg, ok) => {
    const st = els("ifaceStatus");
    if (!st) return;
    st.textContent = msg;
    st.className = ok ? "muted small ok" : "muted small bad";
  };

  const applyNow = async () => {
    if (busy) return;
    busy = true;
    sel.disabled = true;
    refresh.disabled = true;
    setStatus(t("msg.loading"), true);
    try {
      await setInterface(sel.value);
      await fetchInterfaceStatus();
      renderConfig();
      setStatus(currentIface ? t("status.capture", { name: currentIface, backend: captureBackend ? ` (${captureBackend})` : "" }) : t("status.capture_stopped"), true);
    } catch (e) {
      setStatus(t("msg.error_prefix", { msg: e.message }), false);
      // rollback UI to last known interface
      sel.value = currentIface || "";
    } finally {
      sel.disabled = false;
      refresh.disabled = false;
      busy = false;
    }
  };

  sel.addEventListener("change", applyNow);

  refresh.addEventListener("click", async () => {
    if (busy) return;
    busy = true;
    sel.disabled = true;
    refresh.disabled = true;
    setStatus(t("msg.loading"), true);
    try {
      await fetchInterfaces();
      await fetchInterfaceStatus();
      renderConfig();
      setStatus(currentIface ? t("status.capture", { name: currentIface, backend: captureBackend ? ` (${captureBackend})` : "" }) : t("status.capture_stopped"), true);
    } finally {
      sel.disabled = false;
      refresh.disabled = false;
      busy = false;
    }
  });
}

function fmtTs() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
}

function showRecordingBlob(blob) {
  const dl = els("recordDownload");
  const status = els("recordStatus");
  if (!dl || !status) return;
  if (!blob || !blob.size) return;
  const url = URL.createObjectURL(blob);
  const ext = (blob.type || "").includes("ogg") ? "ogg" : "webm";
  dl.href = url;
  dl.download = `mwouettes-${fmtTs()}.${ext}`;
  dl.textContent = t("msg.download_with_size", { mb: (blob.size / 1024 / 1024).toFixed(1) });
  dl.style.display = "inline";
  status.textContent = t("status.file_ready");
}

function refreshRecordingUi() {
  const btn = els("recordBtn");
  const status = els("recordStatus");
  if (!btn || !status) return;
  btn.textContent = isRecording ? t("btn.record_stop") : t("btn.record_start");
  if (isRecording) {
    status.textContent = t("status.recording");
  } else if ((status.textContent || "").startsWith("●")) {
    status.textContent = "";
  }
}

function attachRecordingControls() {
  const btn = els("recordBtn");
  const status = els("recordStatus");
  const dl = els("recordDownload");
  if (!btn || !status || !dl) return;

  const setUi = () => {
    btn.textContent = isRecording ? t("btn.record_stop") : t("btn.record_start");
    status.textContent = isRecording ? t("status.recording") : "";
  };
  setUi();

  btn.addEventListener("click", async () => {
    if (!audio) {
      alert(t("alert.start_audio_first"));
      return;
    }
    dl.style.display = "none";
    dl.removeAttribute("href");
    dl.removeAttribute("download");

    if (!isRecording) {
      try {
        audio.startRecording();
        isRecording = true;
        setUi();
      } catch (e) {
        alert(t("alert.record_failed", { msg: e?.message || e }));
      }
      return;
    }

    isRecording = false;
    setUi();
    const blob = await audio.stopRecording();
    showRecordingBlob(blob);
  });
}

async function main() {
  loadLang();
  initLangSelect();
  applyI18n();
  loadUiState();
  await fetchInterfaces();
  await fetchInterfaceStatus();
  await fetchSamples();
  await fetchConfig();
  attachRiverControls();
  initAudioButtons();
  attachRecordingControls();
  initSaveButton();
  initEnvironmentControls();
  initUpload();
  initSamplesRefresh();
  renderSamplesList();
  initChartToggles();
  initInterfaceControls();
  startEvents();
}

main().catch((e) => {
  console.error(e);
  els("conn").textContent = t("conn.error");
});
