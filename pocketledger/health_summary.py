"""Put the Business Health Score into the trader-facing summaries (SPEC.md §7.7).

Rule: Gemini reads, Python counts. Gemini is asked not to state any score, and anything that looks
like one is stripped from its text. Python then adds the official score sentence in English,
ChiShona, and IsiNdebele, so every surface (app, PDF, phone) quotes the same number.

ChiShona and IsiNdebele templates are pending native-speaker review.
"""

from __future__ import annotations

import re
from typing import Any

from health_score import COMPONENT_LABELS

SUMMARY_KEYS = {
    "English": "business_health_summary",
    "ChiShona": "summary_shona",
    "IsiNdebele": "summary_ndebele",
}

FALLBACKS = {"English": "Summary unavailable.", "ChiShona": "Hapana pfupiso.", "IsiNdebele": "Asikho isifinyezo."}

# Sentences that claim a score, rating, grade, or loan amount. Gemini must not produce these.
_SCORE_CLAIM = re.compile(
    r"\b(score|rating|rated|grade|credit\s*worth\w*|loan\s+(?:amount|limit|of)|eligible)\b"
    r"|\d+\s*/\s*100|\bout of (?:10|100)\b|\d+\s*(?:points|pts)\b",
    re.IGNORECASE,
)
_SENTENCE = re.compile(r"[^.!?]+[.!?]*\s*")

# Every official block starts with one of these, so it can be removed before re-adding (idempotent).
_OFFICIAL_PREFIXES = (
    "Business health score:",
    "No health score yet:",
    "Health score yebhizinesi rako",
    "Hapana health score parizvino:",
    "I-health score yebhizinisi lakho",
    "Akukabi khona i-health score:",
)


def _remove_official_block(text: str) -> str:
    cut = min((i for i in (text.find(p) for p in _OFFICIAL_PREFIXES) if i >= 0), default=-1)
    return text[:cut].rstrip() if cut >= 0 else text


def strip_score_claims(text: Any) -> str:
    """Remove whole sentences that state a score or loan figure."""
    if not text:
        return ""
    value = str(text).strip()
    kept = [s for s in _SENTENCE.findall(value) if not _SCORE_CLAIM.search(s)]
    return "".join(kept).strip()


def score_sentences(health: dict[str, Any] | None) -> dict[str, str]:
    """The official health score sentence in each language ('' when there is no history)."""
    if not health or not health.get("window"):
        return {lang: "" for lang in SUMMARY_KEYS}
    status = health.get("status")
    score = health.get("score")
    if score is None:
        n = health.get("record_more_days", 0)
        return {
            "English": f"No health score yet: record {n} more trading day(s).",
            "ChiShona": f"Hapana health score parizvino: nyora mamwe mazuva {n} ekutengesa.",
            "IsiNdebele": f"Akukabi khona i-health score: bhala ezinye izinsuku ezi-{n} zokuthengisa.",
        }
    days = (health.get("window") or {}).get("trading_days", 0)
    bands = health.get("band_local") or {}
    english = f"Business health score: {score}/100 ({health.get('band')}), from {days} trading days."
    shona = f"Health score yebhizinesi rako ndeye {score}/100 ({bands.get('ChiShona', health.get('band'))}), kubva pamazuva {days} ekutengesa."
    ndebele = f"I-health score yebhizinisi lakho ngu {score}/100 ({bands.get('IsiNdebele', health.get('band'))}), kusukela ezinsukwini ezi-{days} zokuthengisa."
    if status == "Provisional":
        english += " It is provisional until you have 6 weeks of records."
        shona += " Ichiri yekutanga kusvika wava nemavhiki 6 ezvinyorwa."
        ndebele += " Iseyokuqala kuze kube lamaviki ayi-6 okubhala."
    actions = health.get("actions") or []
    if actions:
        first = actions[0]
        english += f" To improve: {first.get('English')}"
    elif health.get("strength"):
        english += f" Strength: {COMPONENT_LABELS.get(health['strength'], health['strength'])}."
    return {"English": english, "ChiShona": shona, "IsiNdebele": ndebele}


def summaries_with_health(result: dict[str, Any] | None, health: dict[str, Any] | None) -> dict[str, str]:
    """Gemini's narrative (score claims removed) followed by the official score sentence."""
    result = result or {}
    sentences = score_sentences(health)
    out = {}
    for lang, key in SUMMARY_KEYS.items():
        narrative = strip_score_claims(_remove_official_block(str(result.get(key) or "")))
        parts = [p for p in (narrative, sentences[lang]) if p]
        out[lang] = " ".join(parts) if parts else FALLBACKS[lang]
    return out


def attach_health(result: dict[str, Any], health: dict[str, Any] | None) -> dict[str, Any]:
    """Return a copy of `result` with `health` and score-bearing summaries (used by the extract API)."""
    merged = dict(result)
    summaries = summaries_with_health(result, health)
    for lang, key in SUMMARY_KEYS.items():
        merged[key] = summaries[lang]
    merged["health"] = health
    return merged
