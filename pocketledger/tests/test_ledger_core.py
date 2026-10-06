"""Repayment handling in ledger_core.recompute_totals (SPEC.md §4.3)."""

import pytest

pytest.importorskip("google.genai", reason="ledger_core imports the Gemini SDK; pip install -r requirements.txt")

from ledger_core import recompute_totals  # noqa: E402


def test_repayment_is_not_a_new_sale():
    rows = [
        {"item": "Bread", "amount_usd": 5.0, "payment_type": "Cash"},
        {"item": "Maize", "amount_usd": 7.0, "payment_type": "Credit", "debtor": "Baba Tawanda"},
        {"item": "Paid back", "amount_usd": 4.0, "payment_type": "Repayment", "debtor": "Mai Tendai"},
        {"item": "Rent", "amount_usd": 12.0, "payment_type": "Expense"},
    ]
    revenue, cash, credit = recompute_totals(rows)
    assert (revenue, cash, credit) == (12.0, 5.0, 7.0)


def test_gemini_score_claims_are_stripped_at_extraction():
    from ledger_core import normalize_extraction

    data = {
        "transactions": [{"item": "Bread", "amount_usd": 5.0, "payment_type": "Cash"}],
        "business_health_summary": "Cash is steady with no credit risk. Health score: 92/100.",
        "summary_shona": "Mari yese yakabhadharwa cash nhasi, hapana chikwereti. Score 92/100.",
        "summary_ndebele": "Imali yonke ikhokhwe ngokheshi namhlanje, asikho isikwelete.",
    }
    out = normalize_extraction(data, "image", "Shop", "Other")
    assert out["business_health_summary"] == "Cash is steady with no credit risk."
    assert "92" not in out["summary_shona"]
