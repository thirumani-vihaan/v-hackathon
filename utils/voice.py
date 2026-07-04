"""Browser-based text-to-speech (voice output) via Web Speech API.

Voice output is done client-side using the browser's built-in SpeechSynthesis
engine. This needs ZERO extra Python
dependencies, works offline, and speaks all supported languages. Returns an
HTML snippet to embed with streamlit.components.v1.html(...).
"""
import html
import json

# Map our language names to BCP-47 voice locales.
VOICE_LOCALE = {
    "English": "en-IN", "Hindi": "hi-IN", "Telugu": "te-IN", "Tamil": "ta-IN",
    "Marathi": "mr-IN", "Kannada": "kn-IN", "Punjabi": "pa-IN",
    "Gujarati": "gu-IN", "Bengali": "bn-IN", "Odia": "or-IN",
}


def speak_html(text: str, lang: str = "English", auto: bool = False,
               label: str = "🔊 Play voice alert") -> str:
    """Return an HTML/JS snippet with a button that speaks `text`."""
    locale = VOICE_LOCALE.get(lang, "en-IN")
    payload = json.dumps(text)  # safe JS string literal
    btn = html.escape(label)
    autoplay = "speak();" if auto else ""
    return f"""
<div style="font-family:sans-serif">
  <button onclick="speak()" style="background:#d32f2f;color:#fff;border:none;
     padding:8px 14px;border-radius:6px;cursor:pointer;font-size:14px">{btn}</button>
  <button onclick="window.speechSynthesis.cancel()" style="background:#555;
     color:#fff;border:none;padding:8px 14px;border-radius:6px;cursor:pointer;
     font-size:14px;margin-left:6px">⏹ Stop</button>
  <script>
    function speak() {{
      try {{
        window.speechSynthesis.cancel();
        var u = new SpeechSynthesisUtterance({payload});
        u.lang = "{locale}";
        u.rate = 0.95;
        var voices = window.speechSynthesis.getVoices();
        var v = voices.find(function(x){{return x.lang === "{locale}";}})
              || voices.find(function(x){{return x.lang.slice(0,2) === "{locale}".slice(0,2);}});
        if (v) u.voice = v;
        window.speechSynthesis.speak(u);
      }} catch (e) {{}}
    }}
    {autoplay}
  </script>
</div>
"""


if __name__ == "__main__":
    print(speak_html("Evacuate Zone B immediately.", "English")[:120])
