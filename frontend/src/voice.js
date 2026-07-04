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
  if (!pool.length) return null;
  // Prefer LOCAL voices — remote/"online (natural)" voices frequently stay silent on
  // Windows even though the engine reports "speaking", which is the muting bug.
  const local = pool.filter((v) => v.localService);
  const cand = local.length ? local : pool;
  const quality = /natural|neural|premium|google/i;
  return cand.find((v) => quality.test(v.name)) || cand[0];
}

function chunkText(text) {
  const parts = text.match(/[^.!?\n]+[.!?\n]*/g) || [text];
  const chunks = [];
  let cur = "";
  for (const p of parts) {
    if ((cur + p).length > 180) { if (cur.trim()) chunks.push(cur.trim()); cur = p; }
    else cur += p;
  }
  if (cur.trim()) chunks.push(cur.trim());
  return chunks.length ? chunks : [text];
}

export function hasVoice(langName) {
  if (pickVoice(LOCALE[langName] || "en-IN")) return true;
  return langName === "English" && _voices.length > 0;
}
export function voiceInfo(langName) {
  let v = pickVoice(LOCALE[langName] || "en-IN");
  if (!v && langName === "English" && _voices.length) v = _voices.find((x) => x.default) || _voices[0];
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
// onFail fires ONLY when no voice exists for the language; when a voice is found the
// call always succeeds (optimistic start + end safety-net), so English never falsely
// reports "no voice" just because the browser did not fire onstart.
export function speak(text, langName, cbs = {}) {
  const ss = window.speechSynthesis;
  if (!ss || !text) { cbs.onFail && cbs.onFail(); return; }
  const locale = LOCALE[langName] || "en-IN";
  ensureVoices().then(() => {
    let v = pickVoice(locale);
    // English is Latin-script: if no en voice is listed but any voice exists, use the
    // browser default so English alerts always play.
    if (!v && langName === "English" && _voices.length) {
      v = _voices.find((x) => x.default) || _voices[0];
    }
    if (!v) { cbs.onFail && cbs.onFail(); return; }   // genuinely no voice
    stopSpeaking();
    const chunks = chunkText(text);
    let started = false, finished = false;
    const markStart = () => { if (!started && !finished) { started = true; cbs.onStart && cbs.onStart(); } };
    const done = () => { if (finished) return; finished = true; stopKeepAlive(); cbs.onEnd && cbs.onEnd(); };
    setTimeout(() => {
      chunks.forEach((chunk, i) => {
        const u = new SpeechSynthesisUtterance(chunk);
        u.voice = v; u.lang = v.lang; u.rate = 0.98; u.pitch = 1.0;
        if (i === 0) u.onstart = markStart;
        if (i === chunks.length - 1) { u.onend = done; u.onerror = done; }
        ss.speak(u);
      });
      try { ss.resume(); } catch {}   // Chrome/Edge sometimes queue-starts paused
      startKeepAlive();
      setTimeout(markStart, 900);      // optimistic start if onstart doesn't fire
      const poll = setInterval(() => {
        if (finished) { clearInterval(poll); return; }
        if (started && !ss.speaking && !ss.pending) { clearInterval(poll); done(); }
      }, 400);
      setTimeout(() => { clearInterval(poll); done(); }, Math.min(120000, 3000 + text.length * 90));
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
