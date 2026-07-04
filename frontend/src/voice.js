// Robust text-to-speech with explicit lifecycle callbacks (onStart / onEnd / onFail),
// async voice loading, a keep-alive for long utterances, a stuck-utterance watchdog, and
// reliable stop. Prefers neural/online voices, falls back to the best offline voice.

const LOCALE = {
  English: "en-IN", Hindi: "hi-IN", Telugu: "te-IN", Tamil: "ta-IN", Marathi: "mr-IN",
  Kannada: "kn-IN", Punjabi: "pa-IN", Gujarati: "gu-IN", Bengali: "bn-IN", Odia: "or-IN",
};

let _voices = [];
function loadVoices() { _voices = window.speechSynthesis ? window.speechSynthesis.getVoices() : []; }
if (typeof window !== "undefined" && window.speechSynthesis) {
  loadVoices();
  window.speechSynthesis.addEventListener("voiceschanged", loadVoices);
  setTimeout(loadVoices, 300);
  setTimeout(loadVoices, 1200);
}

function ensureVoices() {
  return new Promise((resolve) => {
    loadVoices();
    if (_voices.length || !window.speechSynthesis) return resolve();
    let done = false;
    const finish = () => { if (done) return; done = true; loadVoices(); resolve(); };
    window.speechSynthesis.addEventListener("voiceschanged", finish, { once: true });
    setTimeout(finish, 900);
  });
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

export function hasVoice(langName) { return !!pickVoice(LOCALE[langName] || "en-IN"); }
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

// speak(text, langName, { onStart, onEnd, onFail }). Handles async voice loading.
export function speak(text, langName, cbs = {}) {
  const ss = window.speechSynthesis;
  if (!ss || !text) { cbs.onFail && cbs.onFail(); return; }
  const locale = LOCALE[langName] || "en-IN";
  ensureVoices().then(() => {
    const v = pickVoice(locale);
    if (!v) { cbs.onFail && cbs.onFail(); return; }
    stopSpeaking();
    const u = new SpeechSynthesisUtterance(text);
    u.voice = v; u.lang = v.lang; u.rate = 0.98; u.pitch = 1.0;
    let started = false, finished = false;
    const done = () => { if (finished) return; finished = true; stopKeepAlive(); cbs.onEnd && cbs.onEnd(); };
    u.onstart = () => { started = true; cbs.onStart && cbs.onStart(); };
    u.onend = done;
    u.onerror = () => { if (started) done(); else { stopKeepAlive(); if (!finished) { finished = true; cbs.onFail && cbs.onFail(); } } };
    setTimeout(() => {
      ss.speak(u);
      startKeepAlive();
      // watchdog: nothing started within 3.5s -> treat as failure so the UI resets
      setTimeout(() => { if (!started && !ss.speaking && !finished) { finished = true; stopKeepAlive(); cbs.onFail && cbs.onFail(); } }, 3500);
    }, 70);
  });
}

export function stopSpeaking() {
  stopKeepAlive();
  const ss = window.speechSynthesis;
  if (!ss) return;
  try { ss.cancel(); } catch {}
  setTimeout(() => { try { ss.cancel(); } catch {} }, 30);
}
