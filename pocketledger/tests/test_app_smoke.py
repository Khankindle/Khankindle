"""Runs the real Streamlit app headlessly with a seeded ledger store (no Gemini calls)."""

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
pytest.importorskip("google.genai")
from streamlit.testing.v1 import AppTest  # noqa: E402

from test_health_score import ledger, tx  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def _recent_ledgers(n_days, credit_every=4):
    """`n_days` trading days (Mon-Sat) ending today, so they fall inside the scoring window."""
    days, d = [], date.today()
    while len(days) < n_days:
        if d.weekday() != 6:
            days.append(d)
        d -= timedelta(days=1)
    pages = []
    for i, day in enumerate(sorted(days)):
        rows = [tx("Bread", 12.0), tx("Cooking oil", 10.5), tx("Sugar", 7.5), tx("Stall fee", 5.0, "Expense")]
        if i % credit_every == 0:
            rows.append(tx("Maize meal", 6.5, "Credit", "Mai Tinashe"))
        page = ledger(day, rows)
        page.update({"business_name": "Mai Rudo Tuckshop", "total_revenue_usd": 30.0,
                     "total_cash_usd": 30.0, "total_credit_outstanding_usd": 0.0})
        pages.append(page)
    return pages


def _run(tmp_path, monkeypatch, ledgers):
    store = {
        "last_user_id": "mai_rudo",
        "users": {"mai_rudo": {"business_name": "Mai Rudo Tuckshop",
                               "business_category": "Tuckshop / grocery", "ledgers": ledgers}},
    }
    (tmp_path / "ledger_store.json").write_text(json.dumps(store), encoding="utf-8")
    monkeypatch.setenv("POCKETLEDGER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-used")
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def test_overview_shows_established_score(tmp_path, monkeypatch):
    at = _run(tmp_path, monkeypatch, _recent_ledgers(44))
    assert "Business health score" in [s.value for s in at.subheader]
    labels = {m.label: m.value for m in at.metric}
    assert labels["Health score"].endswith("/100")
    assert "Safe daily repayment" in labels
    progress_text = " ".join(p.proto.text for p in at.get("progress"))
    assert "Recording consistency" in progress_text and "Credit (chikwereti) health" in progress_text


def test_overview_asks_for_more_days(tmp_path, monkeypatch):
    at = _run(tmp_path, monkeypatch, _recent_ledgers(3))
    assert any("Record 2 more trading day(s)" in i.value for i in at.info)
    assert "Health score" not in {m.label for m in at.metric}


def test_certificate_tab_shows_score_line(tmp_path, monkeypatch):
    at = _run(tmp_path, monkeypatch, _recent_ledgers(20))
    markdown = " ".join(m.value for m in at.markdown)
    assert "Business health score:" in markdown and "Provisional" in markdown
