"""Alert text from templates (no AI call per alert). English plus the demo language (Tagalog);
other languages fall back to English. Short and plain. Pest alerts always say the weather
*favors* a pest and ask the farmer to check the field: never a confirmed outbreak."""

from __future__ import annotations

from typing import Any

TEMPLATES: dict[str, dict[str, str]] = {
    "en": {
        "natural_event": "{event} is {distance} km from {field}. Check NASA updates and local "
                         "warnings, and protect your crops and family.",
        "natural_event_approaching": "{event} is {distance} km from {field} and moving closer. "
                                     "Follow local warnings and get ready.",
        "fire": "Active fire detected {distance} km from {field} in the last {days} day(s) "
                "(NASA FIRMS). Check your field and follow local advice.",
        "heavy_rain": "Heavy rain at {field}: about {mm} mm in the last {hours} hours, far above "
                      "normal (JAXA GSMaP). Check drainage and low spots.",
        "drought": "The soil at {field} is drier than normal: root-zone moisture is {pct}% of "
                   "the usual for {month} (NASA SMAP). Plan water and check your crops.",
        "pest_risk": "Weather at {field} favors {pest} on {crop}: {rule}. Conditions favor it; "
                     "check your field. This is not a confirmed outbreak.",
        "new_findings": "New findings for {field}: the best match is now \"{strategy}\". "
                        "Open the plan to see why.",
        "simulated": "(Simulation for the demo) ",
    },
    "tl": {
        "natural_event": "Ang {event} ay {distance} km mula sa {field}. Sundan ang balita ng "
                         "NASA at ang lokal na babala, at ingatan ang pananim at pamilya.",
        "natural_event_approaching": "Ang {event} ay {distance} km mula sa {field} at papalapit. "
                                     "Sundin ang lokal na babala at maghanda.",
        "fire": "May sunog na nakita {distance} km mula sa {field} sa nakaraang {days} araw "
                "(NASA FIRMS). Silipin ang bukid at sundin ang lokal na payo.",
        "heavy_rain": "Malakas na ulan sa {field}: mga {mm} mm sa nakaraang {hours} oras, mas "
                      "mataas kaysa karaniwan (JAXA GSMaP). Silipin ang daluyan ng tubig.",
        "drought": "Mas tuyo ang lupa sa {field} kaysa karaniwan: {pct}% lang ng karaniwang "
                   "halumigmig para sa {month} (NASA SMAP). Planuhin ang tubig.",
        "pest_risk": "Ang panahon sa {field} ay pabor sa {pest} sa {crop}: {rule}. Pabor ang "
                     "kondisyon; silipin ang bukid. Hindi ito kumpirmadong outbreak.",
        "new_findings": "Bagong resulta para sa {field}: ang pinakaangkop ngayon ay "
                        "\"{strategy}\". Buksan ang plano para makita kung bakit.",
        "simulated": "(Simulation para sa demo) ",
    },
}

TITLES: dict[str, dict[str, str]] = {
    "en": {"natural_event": "Natural event nearby", "fire": "Fire nearby",
           "heavy_rain": "Heavy rain", "drought": "Dry soil", "pest_risk": "Pest-risk weather",
           "new_findings": "New findings"},
    "tl": {"natural_event": "Kalamidad sa malapit", "fire": "Sunog sa malapit",
           "heavy_rain": "Malakas na ulan", "drought": "Tuyong lupa",
           "pest_risk": "Panahong pabor sa peste", "new_findings": "Bagong resulta"},
}


def render(kind: str, language: str, *, simulated: bool = False, **values: Any) -> str:
    table = TEMPLATES.get(language) or TEMPLATES["en"]
    text = (table.get(kind) or TEMPLATES["en"][kind]).format(**values)
    return (table["simulated"] if simulated else "") + text


def title(kind: str, language: str) -> str:
    base = kind.removesuffix("_approaching")
    return (TITLES.get(language) or TITLES["en"]).get(base) or TITLES["en"].get(base, base)
