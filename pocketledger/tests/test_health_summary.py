"""Score sentences and score-claim stripping (SPEC.md §7.7: every surface quotes the same score)."""

import pytest

from health_score import compute
from health_summary import attach_health, score_sentences, strip_score_claims, summaries_with_health
from test_health_score import steady_history

RESULT = {
    "business_health_summary": "Cash sales are steady. Your credit score is 85/100 and you are eligible for a loan of $500.",
    "summary_shona": "Mari yakanaka nhasi. Score yako i 85/100.",
    "summary_ndebele": "Imali ihamba kuhle namhlanje.",
}


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Sales are steady. Your score is 80/100.", "Sales are steady."),
        ("Rated 9 out of 10. Credit is low.", "Credit is low."),
        ("You qualify: eligible for a loan amount of $300. Keep records.", "Keep records."),
        ("Good cash flow with 3 debtors.", "Good cash flow with 3 debtors."),
        ("", ""),
        (None, ""),
    ],
)
def test_strip_score_claims(text, expected):
    assert strip_score_claims(text) == expected


def test_no_history_adds_nothing():
    assert score_sentences(None) == {"English": "", "ChiShona": "", "IsiNdebele": ""}
    assert summaries_with_health({}, None)["English"] == "Summary unavailable."


def test_not_enough_data_sentence():
    sentences = score_sentences(compute(steady_history(3)))
    assert "record 2 more trading day(s)" in sentences["English"]
    assert "2" in sentences["ChiShona"] and "2" in sentences["IsiNdebele"]


def test_provisional_sentence():
    health = compute(steady_history(10))
    sentences = score_sentences(health)
    assert f"{health['score']}/100" in sentences["English"]
    assert "provisional" in sentences["English"]


def test_established_sentence_quotes_exact_score_in_every_language():
    health = compute(steady_history(42))
    sentences = score_sentences(health)
    for lang in ("English", "ChiShona", "IsiNdebele"):
        assert f"{health['score']}/100" in sentences[lang]
    assert health["band_local"]["ChiShona"] in sentences["ChiShona"]
    assert health["band_local"]["IsiNdebele"] in sentences["IsiNdebele"]


def test_gemini_score_is_replaced_by_official_score():
    health = compute(steady_history(42))
    summaries = summaries_with_health(RESULT, health)
    assert "85/100" not in " ".join(summaries.values())
    assert "$500" not in summaries["English"]
    assert summaries["English"].startswith("Cash sales are steady.")
    assert summaries["ChiShona"].startswith("Mari yakanaka nhasi.")
    for text in summaries.values():
        assert text.count("/100") == 1 and f"{health['score']}/100" in text


def test_attach_health_is_idempotent():
    health = compute(steady_history(42))
    once = attach_health(RESULT, health)
    twice = attach_health(once, health)
    assert once["business_health_summary"] == twice["business_health_summary"]
    assert twice["health"] is health
    assert RESULT["summary_ndebele"] == "Imali ihamba kuhle namhlanje."  # input not mutated
