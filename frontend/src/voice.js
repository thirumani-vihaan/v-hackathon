// Smart text-to-speech: prefer high-quality neural/online voices when the browser
// exposes them (Edge "Natural"/"Online", Chrome "Google"), otherwise fall back to the
// best matching offline system voice. Works with zero API keys and offline.

const LOCALE = {
  English: "en-IN", Hindi: "hi-IN", Telugu: "te-IN", Tamil: "ta-IN", Marathi: "mr-IN",
  Kannada: "kn-IN", Punjabi: "pa-IN", Gujarati: "gu-IN", Bengali: "bn-IN", Odia: "or-IN",
};

let _voices = [];
function loadVoices() {
  _voices = window.speechSynthesis ? window.speechSynthesis.getVoices() : [];
}
if (typeof window !== "undefined" && window.speechSynthesis) {
  loadVoices();
  window.speechSynthesis.onvoiceschanged = loadVoices;
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

export function voiceInfo(langName) {
  const v = pickVoice(LOCALE[langName] || "en-IN");
  return v ? `${v.name}` : "system default";
}

export function speak(text, langName) {
  if (!window.speechSynthesis) return false;
  const locale = LOCALE[langName] || "en-IN";
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  const v = pickVoice(locale);
  if (v) u.voice = v;
  u.lang = v ? v.lang : locale;
  u.rate = 0.98;
  u.pitch = 1.0;
  window.speechSynthesis.speak(u);
  return true;
}

export function stopSpeaking() {
  if (window.speechSynthesis) window.speechSynthesis.cancel();
}
