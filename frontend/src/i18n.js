import { createContext, useContext } from "react";

// UI translations for the app shell. Technical data/output stays in English (the
// standard for OISD/Factory Act/DGMS safety terminology); the navigation and section
// titles localise so operators can work in their language. Unlisted strings and
// languages fall back to English.
const DICT = {
  Hindi: {
    "Zero-Harm Command Center": "ज़ीरो-हार्म कमांड सेंटर",
    Dashboard: "डैशबोर्ड", "Zone Map": "ज़ोन मानचित्र", Vision: "विज़न",
    Knowledge: "ज्ञान", Emergency: "आपातकाल", "Safety Tools": "सुरक्षा उपकरण",
    Intelligence: "इंटेलिजेंस", Benchmark: "बेंचमार्क",
    "BACKEND LIVE": "बैकएंड लाइव", "BACKEND DOWN": "बैकएंड बंद",
    "offline · deterministic": "ऑफ़लाइन · नियतात्मक",
    "Sensor & Permit Controls": "सेंसर और परमिट नियंत्रण",
    "Compound Risk": "संयुक्त जोखिम",
    "Risk Contribution Breakdown": "जोखिम योगदान विवरण",
    "Compound vs Single-Sensor": "संयुक्त बनाम एकल-सेंसर",
    "Assessment Confidence": "आकलन विश्वास",
    "Recommended Interventions": "अनुशंसित उपाय",
    "Live Predictive Stream": "लाइव पूर्वानुमान स्ट्रीम",
  },
  Telugu: {
    "Zero-Harm Command Center": "జీరో-హార్మ్ కమాండ్ సెంటర్",
    Dashboard: "డాష్‌బోర్డ్", "Zone Map": "జోన్ మ్యాప్", Vision: "విజన్",
    Knowledge: "నాలెడ్జ్", Emergency: "అత్యవసరం", "Safety Tools": "సేఫ్టీ టూల్స్",
    Intelligence: "ఇంటెలిజెన్స్", Benchmark: "బెంచ్‌మార్క్",
    "BACKEND LIVE": "బ్యాకెండ్ లైవ్", "BACKEND DOWN": "బ్యాకెండ్ డౌన్",
    "offline · deterministic": "ఆఫ్‌లైన్ · నిర్ధారితం",
    "Sensor & Permit Controls": "సెన్సార్ & పర్మిట్ నియంత్రణలు",
    "Compound Risk": "సమ్మిళిత ప్రమాదం",
    "Risk Contribution Breakdown": "ప్రమాద కారకాల విభజన",
    "Compound vs Single-Sensor": "సమ్మిళిత vs సింగిల్-సెన్సార్",
    "Assessment Confidence": "అంచనా విశ్వాసం",
    "Recommended Interventions": "సిఫార్సు చర్యలు",
    "Live Predictive Stream": "లైవ్ ప్రిడిక్టివ్ స్ట్రీమ్",
  },
};

export const UI_LANGS = ["English", "Hindi", "Telugu"];

export function makeT(lang) {
  const table = DICT[lang];
  return (s) => (table && table[s]) || s;
}

export const I18n = createContext({ lang: "English", t: (s) => s });
export function useT() { return useContext(I18n); }
