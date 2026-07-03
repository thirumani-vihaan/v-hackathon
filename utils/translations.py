"""Evacuation-message translations. Static core phrases + optional live Gemini.

Used by the Emergency Dispatch tab. Falls back to a static dictionary so it
works offline and deterministically in tests.
"""
import os

LANGUAGES = {
    "English": "en",
    "Hindi": "hi",
    "Telugu": "te",
    "Tamil": "ta",
    "Marathi": "mr",
}

# Core evacuation phrase per language (used offline and as Gemini fallback).
_EVAC = {
    "en": "EMERGENCY: Evacuate {zone} immediately. Toxic gas / explosion risk. "
          "Proceed to the nearest muster point. Incident ref {request_id}.",
    "hi": "आपातकाल: {zone} को तुरंत खाली करें। जहरीली गैस / विस्फोट का खतरा। "
          "निकटतम सुरक्षित स्थान पर जाएं। घटना संदर्भ {request_id}।",
    "te": "అత్యవసరం: {zone} ను వెంటనే ఖాళీ చేయండి. విషవాయువు / పేలుడు ప్రమాదం. "
          "సమీప సురక్షిత ప్రదేశానికి వెళ్లండి. సంఘటన సూచన {request_id}.",
    "ta": "அவசரம்: {zone} ஐ உடனடியாக காலி செய்யவும். நச்சு வாயு / வெடிப்பு அபாயம். "
          "அருகிலுள்ள பாதுகாப்பு இடத்திற்கு செல்லவும். சம்பவ குறிப்பு {request_id}.",
    "mr": "आणीबाणी: {zone} त्वरित रिकामे करा. विषारी वायू / स्फोटाचा धोका. "
          "जवळच्या सुरक्षित ठिकाणी जा. घटना संदर्भ {request_id}.",
}


def static_message(lang_code: str, zone: str, request_id: str) -> str:
    tmpl = _EVAC.get(lang_code, _EVAC["en"])
    return tmpl.format(zone=zone, request_id=request_id)


def translate_evac(lang_name: str, zone: str, request_id: str,
                   use_gemini: bool = True) -> tuple:
    """Return (message, source). source is 'static' or 'gemini'.

    English always uses the static template. Other languages try Gemini live
    translation of the English core (if a key is present), else fall back to the
    static localized phrase. Never raises; never prints the API key.
    """
    code = LANGUAGES.get(lang_name, "en")
    english = static_message("en", zone, request_id)
    if code == "en":
        return english, "static"

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if use_gemini and api_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            from utils.gemini_vision import MODELS
            prompt = (f"Translate this industrial evacuation alert into "
                      f"{lang_name}. Keep the incident reference id unchanged. "
                      f"Return only the translated text:\n\n{english}")
            for model_name in MODELS:
                try:
                    model = genai.GenerativeModel(model_name)
                    resp = model.generate_content(prompt)
                    text = getattr(resp, "text", "").strip()
                    if text:
                        return text, "gemini"
                except Exception:
                    continue
        except Exception:
            pass
    return static_message(code, zone, request_id), "static"


if __name__ == "__main__":
    print(translate_evac("Telugu", "Zone-B-Process", "req-123", use_gemini=False))
