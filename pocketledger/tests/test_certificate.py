"""Health score block in the PDF certificate (SPEC.md §7.7, acceptance criterion 5)."""

from datetime import date

import pytest

pypdf = pytest.importorskip("pypdf")

import certificate  # noqa: E402
from certificate import build_statement_pdf  # noqa: E402
from health_score import compute  # noqa: E402
from test_health_score import steady_history, tx  # noqa: E402

RESULT = {
    "business_name": "Mai Rudo Tuckshop",
    "date": "19 Sept 2026",
    "business_category": "Tuckshop / grocery",
    "total_revenue_usd": 25.5,
    "total_cash_usd": 15.5,
    "total_credit_outstanding_usd": 10.0,
    # Missing quantity renders as an em dash, which used to crash Helvetica.
    "transactions": [tx("Cooking oil", 8.5), tx("Bread", 4.8, quantity=""), tx("Rent", 12, "Expense")],
    "business_health_summary": "Steady cash sales — follow up debtors.",
    "summary_shona": "Bhizinesi rako rakawana $25.50 nhasi.",
    "summary_ndebele": "Ibizinisi lakho lithole $25.50 namhlanje.",
}


def _pages_text(pdf_bytes):
    import io

    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    return [page.extract_text() for page in reader.pages]


def _established_health():
    pages = steady_history(44, extra=lambda i, d: [tx("Maize", 6.5, "Credit", "Mai Tinashe")] if i % 4 == 0 else [])
    pages[0]["transactions"].append(tx("Bulk sugar", 40.0, "Credit", "Baba John"))
    return compute(pages)


@pytest.fixture(params=["unicode-font", "helvetica"])
def font_mode(request, monkeypatch):
    if request.param == "helvetica":
        # Simulate a host with no Arial and no DejaVu (built-in Latin-1 font only).
        monkeypatch.setattr(certificate, "_LINUX_FONT_DIRS", ())
        monkeypatch.setenv("WINDIR", "/nonexistent")
    return request.param


def test_certificate_with_score(font_mode):
    health = _established_health()
    text = _pages_text(build_statement_pdf(RESULT, health))
    full = "\n".join(text)
    assert "Business health score" in full
    assert f"{health['score']}/100" in full
    assert health["band"] in full
    assert "Baba John" in full  # overdue debtor named in the action
    assert "Affordability guide" in full
    assert "not a loan" in full.lower()


def test_score_version_and_disclaimer_on_every_page(font_mode):
    health = _established_health()
    result = dict(RESULT, transactions=[tx(f"Item {n}", 1.0) for n in range(60)])  # forces several pages
    pages = _pages_text(build_statement_pdf(result, health))
    assert len(pages) >= 2
    for page in pages:
        flat = " ".join(page.split())
        assert health["score_version"] in flat
        assert "not a loan decision" in flat


def test_not_enough_data_block():
    health = compute(steady_history(3))
    full = "\n".join(_pages_text(build_statement_pdf(RESULT, health)))
    assert "Record 2 more trading day(s)" in full
    assert "/100" not in full


def test_provisional_hides_affordability():
    health = compute(steady_history(10))
    full = " ".join("\n".join(_pages_text(build_statement_pdf(RESULT, health))).split())
    assert "Provisional" in full
    assert "Affordability guide not shown" in full


def test_certificate_without_health_still_builds(font_mode):
    full = "\n".join(_pages_text(build_statement_pdf(RESULT)))
    assert "PocketLedger financial certificate" in full
    assert "Business health score" not in full
