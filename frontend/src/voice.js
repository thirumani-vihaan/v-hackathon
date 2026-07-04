// Robust text-to-speech: prefers high-quality neural/online voices, keeps long
// utterances alive (Chrome/Edge pause bug), stops reliably, and reports whether a
// voice for the requested language actually exists so the caller can fall back.

const LOCALE = {
  English: "en-IN", Hindi: "hi-IN", Telugu: "te-IN", Tamil: "ta-IN", Marathi: "mr-IN",
  Kannada: "kn-IN", Punjabi: "pa-IN", Gujarati: "gu-IN", Bengali: "bn-IN", Odia: "or-IN",
};

let _voices = [];
function loadVoices() { _voices = window.speechSynthesis ? window.speechSynthesis.getVoices() : []; }
if (typeof window !== "undefined" && window.speechSynthesis) {
  loadVoices();
  window.speechSynthesis.onvoiceschanged = loadVoices;
  // some browsers populate voices lazily
  setTimeout(loadVoices, 300);
  setTimeout(loadVoices, 1200);
}

function pickVoice(locale) {
  if (!_voices.length) loadVoices();
  const lang = locale.split("-")[0];
  const byLocale = _voices.filter((v) => v.lang && v.lang.toLowerCase().startsWith(locale.toLowerCase()));
  const byLang = _voices.filter((v) => v.lang && v.lang.toLowerCase().startsWith(lang));
  const pool = byLocale.length ? byLocale : byLang;
  const quality = /natural|online|neural|google|premium/i;
  return pool.find((v) => quality.test(v.name)) || pool[0] || null;
}

export function hasVoice(langName) {
  return !!pickVoice(LOCALE[langName] || "en-IN");
}

export function voiceInfo(langName) {
  const v = pickVoice(LOCALE[langName] || "en-IN");
  return v ? v.name : "no voice installed for this language";
}

let _keepAlive = null;
function startKeepAlive() {
  if (_keepAlive) return;
  _keepAlive = setInterval(() => {
    const ss = window.speechSynthesis;
    if (ss && ss.speaking) { ss.pause(); ss.resume(); } else { stopKeepAlive(); }
  }, 5000);
}
function stopKeepAlive() { if (_keepAlive) { clearInterval(_keepAlive); _keepAlive = null; } }

// Returns true if a matching voice was found and speech started, else false.
export function speak(text, langName, onDone) {
  const ss = window.speechSynthesis;
  if (!ss || !text) return false;
  stopSpeaking();
  const locale = LOCALE[langName] || "en-IN";
  const v = pickVoice(locale);
  if (!v) { if (onDone) onDone(); return false; }
  const u = new SpeechSynthesisUtterance(text);
  u.voice = v; u.lang = v.lang; u.rate = 0.98; u.pitch = 1.0;
  u.onend = () => { stopKeepAlive(); if (onDone) onDone(); };
  u.onerror = () => { stopKeepAlive(); if (onDone) onDone(); };
  // let the cancel() settle before speaking (avoids the "stuck" state)
  setTimeout(() => { ss.speak(u); startKeepAlive(); }, 60);
  return true;
}

export function stopSpeaking() {
  stopKeepAlive();
  const ss = window.speechSynthesis;
  if (!ss) return;
  try { ss.cancel(); } catch {}
  // second cancel clears an occasionally-stuck queued utterance
  setTimeout(() => { try { ss.cancel(); } catch {} }, 30);
}
