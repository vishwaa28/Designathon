"""Traveler message templates and personalisation."""
from __future__ import annotations

import os

from app.core.utils import parse_dt
from app.data import reference as ref
from app.data.store import is_priority, store


def _portal_base() -> str:
    if explicit := os.getenv("PORTAL_BASE_URL"):
        return explicit.rstrip("/")
    if os.getenv("VERCEL_ENV") == "production" and os.getenv("VERCEL_PROJECT_PRODUCTION_URL"):
        return f"https://{os.environ['VERCEL_PROJECT_PRODUCTION_URL']}"
    if os.getenv("VERCEL_URL"):
        return f"https://{os.environ['VERCEL_URL']}"
    return "http://localhost:5173"


PORTAL_BASE = _portal_base()

OUTCOME_TYPES = ["DELAYED", "REBOOKED", "ALT_MODE", "BUS_BRIDGE", "DIVERTED", "UNACCOMMODATED"]
PLACEHOLDERS = "{name} {trip} {route} {delay} {new_trip} {new_time} {new_arr} {via} {link}"
PLACEHOLDER_NOTES = "{delay} already includes its unit (e.g. '45 min'); {new_time} and {new_arr} are HH:MM clock times"

MINUTE_UNIT = {
    "en": "min", "hi": "मिनट", "mr": "मिनिटे", "gu": "મિનિટ", "kn": "ನಿಮಿಷ",
    "ta": "நிமிடம்", "te": "నిమిషాలు", "bn": "মিনিট", "ml": "മിനിറ്റ്",
}

REASONS = {
    "en": {
        "AIRPORT_CLOSURE": "severe weather at {loc}",
        "CORRIDOR_BLOCK": "a signalling / track failure between {loc}",
        "VEHICLE_GROUNDED": "an unscheduled technical inspection of the aircraft",
    },
    "hi": {
        "AIRPORT_CLOSURE": "{loc} में खराब मौसम",
        "CORRIDOR_BLOCK": "{loc} के बीच सिग्नल / ट्रैक खराबी",
        "VEHICLE_GROUNDED": "विमान की अनिर्धारित तकनीकी जाँच",
    },
}

FALLBACK_TEMPLATES = {
    "en": {
        "DELAYED": "Dear {name}, {trip} ({route}) is running {delay} late due to {reason}. Expected arrival: {new_arr}. Manage your trip: {link}",
        "REBOOKED": "Dear {name}, due to {reason} your booking on {trip} has been moved to {new_trip}, departing {new_time}. No action is needed. To choose another option: {link}",
        "ALT_MODE": "Dear {name}, due to {reason} we have moved you from {trip} to {new_trip}, departing {new_time}. Transfer assistance is included. Review or change: {link}",
        "BUS_BRIDGE": "Dear {name}, {trip} will be short-terminated due to {reason}. A connecting coach will carry you over the affected section (about {delay} extra). Details: {link}",
        "DIVERTED": "Dear {name}, {trip} is diverting to {via} due to {reason}. A coach transfer to your destination is arranged, adding about {delay}. Updates: {link}",
        "UNACCOMMODATED": "Dear {name}, we are sorry: {trip} is cancelled due to {reason} and no seats are available within 18 hours. Choose a full refund or next-day travel: {link}",
        "PRIORITY": "A priority assistance agent will contact you shortly.",
    },
    "hi": {
        "DELAYED": "प्रिय {name}, {reason} के कारण {trip} ({route}) {delay} देरी से चल रही है। अनुमानित आगमन: {new_arr}। अपनी यात्रा प्रबंधित करें: {link}",
        "REBOOKED": "प्रिय {name}, {reason} के कारण आपकी बुकिंग {trip} से {new_trip} में बदल दी गई है, प्रस्थान {new_time}। कोई कार्रवाई आवश्यक नहीं। अन्य विकल्प चुनें: {link}",
        "ALT_MODE": "प्रिय {name}, {reason} के कारण आपको {trip} से {new_trip} में स्थानांतरित किया गया है, प्रस्थान {new_time}। ट्रांसफर सहायता शामिल है। देखें या बदलें: {link}",
        "BUS_BRIDGE": "प्रिय {name}, {reason} के कारण {trip} बीच में समाप्त होगी। प्रभावित खंड के लिए बस की व्यवस्था की गई है (लगभग {delay} अतिरिक्त)। विवरण: {link}",
        "DIVERTED": "प्रिय {name}, {reason} के कारण {trip} को {via} की ओर मोड़ा जा रहा है। गंतव्य तक बस ट्रांसफर की व्यवस्था है, लगभग {delay} अतिरिक्त। अपडेट: {link}",
        "UNACCOMMODATED": "प्रिय {name}, खेद है: {reason} के कारण {trip} रद्द है और 18 घंटे के भीतर सीटें उपलब्ध नहीं हैं। पूर्ण रिफंड या अगले दिन की यात्रा चुनें: {link}",
        "PRIORITY": "प्राथमिकता सहायता एजेंट शीघ्र ही आपसे संपर्क करेगा।",
    },
}

SUBJECTS = {
    "DELAYED": "Schedule change", "REBOOKED": "You have been rebooked", "ALT_MODE": "New travel arrangement",
    "BUS_BRIDGE": "Coach connection arranged", "DIVERTED": "Diversion update", "UNACCOMMODATED": "Cancellation: choose refund or new date",
}


def portal_link(pnr: str, last_name: str) -> str:
    return f"{PORTAL_BASE}/traveler?pnr={pnr}&name={last_name}"


def _fmt_time(dt) -> str:
    return parse_dt(dt).strftime("%H:%M")


def render(template: str, pax: dict, outcome: dict, reason: str, lang: str = "en") -> str:
    leg = store.trips[outcome["leg"]] if outcome.get("leg") else None
    new = store.trips[outcome["new_trip"]] if outcome.get("new_trip") else None
    current = new or leg
    new_time = _fmt_time(store.est_dep(current)) if current else "-"
    new_arr = _fmt_time(store.est_arr(current)) if current else "-"
    values = {
        "name": pax["first_name"],
        "trip": leg["number"] if leg else "your trip",
        "route": f"{ref.display_code(leg['origin'])}-{ref.display_code(leg['destination'])}" if leg else "",
        "delay": f"{outcome.get('delay_min', 0)} {MINUTE_UNIT.get(lang, 'min')}",
        "new_trip": new["number"] if new else "",
        "new_time": new_time,
        "new_arr": new_arr,
        "via": ref.display_code(outcome["via"]) if outcome.get("via") else "",
        "link": portal_link(pax["pnr"], pax["last_name"]),
        "reason": reason,
    }
    try:
        return template.format(**values)
    except (KeyError, IndexError, ValueError):
        values["delay"] = f"{outcome.get('delay_min', 0)} min"
        return FALLBACK_TEMPLATES["en"][outcome["type"]].format(**values)


ASSISTANCE_SSR = ("WCHR", "UMNR", "MEDA")


def needs_agent_call(pax: dict) -> bool:
    return is_priority(pax) and pax["ssr"] in ASSISTANCE_SSR


class _Blank(dict):
    def __missing__(self, key):
        return ""


def priority_line(pax: dict, templates: dict) -> str:
    if not needs_agent_call(pax):
        return ""
    line = templates.get("PRIORITY") or FALLBACK_TEMPLATES["en"]["PRIORITY"]
    try:
        line = line.format_map(_Blank(name=pax["first_name"], link=portal_link(pax["pnr"], pax["last_name"])))
    except (IndexError, ValueError):
        line = FALLBACK_TEMPLATES["en"]["PRIORITY"]
    return " " + line.strip()
