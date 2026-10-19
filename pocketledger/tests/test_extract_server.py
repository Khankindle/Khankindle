"""Extract API returns the health score and shares history with the Streamlit app."""

import json
import threading
import urllib.request
from datetime import date, timedelta
from http.server import ThreadingHTTPServer

import pytest

pytest.importorskip("google.genai")

import extract_server  # noqa: E402
import ledger_store  # noqa: E402
from test_health_score import tx  # noqa: E402

TODAY = date(2026, 10, 6)
NAME, CATEGORY = "Gogo Chipo fresh produce", "Fresh produce / market stall"


@pytest.fixture(autouse=True)
def temp_store(tmp_path, monkeypatch):
    monkeypatch.setenv("POCKETLEDGER_DATA_DIR", str(tmp_path))
    return tmp_path


def fake_extractor(day):
    """Stands in for Gemini: returns a normalized page dated `day`, with a score claim to strip."""

    def extract(*, source, mime_type, data_b64, business_name, category):
        return {
            "business_name": business_name,
            "business_category": category,
            "date": day.strftime("%d %b %Y"),
            "capture_source": source,
            "transactions": [tx("Tomatoes", 12.0), tx("Onions", 8.0), tx("Potatoes", 4.5, "Credit", "Sekuru Peter"),
                             tx("Stall fee", 5.0, "Expense")],
            "total_revenue_usd": 24.5,
            "total_cash_usd": 20.0,
            "total_credit_outstanding_usd": 4.5,
            "business_health_summary": "Good cash day. Your score is 99/100.",
            "summary_shona": "Zuva rakanaka.",
            "summary_ndebele": "Usuku oluhle.",
        }

    return extract


def _payload(**extra):
    return {"source": "image", "mime_type": "image/jpeg", "data": "", "business_name": NAME, "category": CATEGORY, **extra}


def _capture_days(n):
    days, d = [], TODAY
    while len(days) < n:
        if d.weekday() != 6:
            days.append(d)
        d -= timedelta(days=1)
    return sorted(days)


def test_first_capture_saves_and_asks_for_more_days():
    body = extract_server.handle_extract(_payload(), fake_extractor(TODAY), today=TODAY)
    assert body["saved"] is True and body["saved_statements"] == 1
    assert body["health"]["status"] == "Not enough data"
    assert body["health"]["record_more_days"] == 4
    assert "99/100" not in body["business_health_summary"]
    assert "record 4 more trading day(s)" in body["business_health_summary"]


def test_history_builds_to_an_established_score():
    for day in _capture_days(44):
        body = extract_server.handle_extract(_payload(), fake_extractor(day), today=TODAY)
    health = body["health"]
    assert health["status"] == "Established"
    assert f"{health['score']}/100" in body["business_health_summary"]
    assert f"{health['score']}/100" in body["summary_shona"]
    assert f"{health['score']}/100" in body["summary_ndebele"]
    assert body["saved_statements"] == 44


def test_save_false_scores_without_storing():
    body = extract_server.handle_extract(_payload(save=False), fake_extractor(TODAY), today=TODAY)
    assert body["saved"] is False and body["saved_statements"] == 0
    assert body["health"]["window"]["trading_days"] == 1
    assert ledger_store.get_ledgers(body["trader_id"]) == []


def test_phone_history_is_the_streamlit_history():
    body = extract_server.handle_extract(_payload(), fake_extractor(TODAY), today=TODAY)
    app_user_id = ledger_store.user_id_for(NAME, CATEGORY)  # what the app computes at onboarding
    assert body["trader_id"] == app_user_id
    assert len(ledger_store.get_ledgers(app_user_id)) == 1
    # A phone capture must not switch which trader the Streamlit app opens with.
    assert ledger_store.load_store().get("last_user_id") is None


def test_handle_health_without_capture():
    for day in _capture_days(6):
        extract_server.handle_extract(_payload(), fake_extractor(day), today=TODAY)
    body = extract_server.handle_health({"business_name": NAME, "category": CATEGORY}, today=TODAY)
    assert body["saved_statements"] == 6
    assert body["health"]["status"] == "Provisional"
    unknown = extract_server.handle_health({"business_name": "Nobody", "category": "Other"}, today=TODAY)
    assert unknown["saved_statements"] == 0 and unknown["health"]["score"] is None


def test_http_round_trip(monkeypatch):
    monkeypatch.setattr(extract_server.Handler, "extractor", staticmethod(fake_extractor(date.today())))
    server = ThreadingHTTPServer(("127.0.0.1", 0), extract_server.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        request = urllib.request.Request(
            f"{base}/api/extract", data=json.dumps(_payload()).encode(), headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            body = json.load(response)
        assert body["health"]["status"] == "Not enough data"
        query = urllib.parse.urlencode({"business_name": NAME, "category": CATEGORY})
        with urllib.request.urlopen(f"{base}/api/health?{query}", timeout=10) as response:
            health_body = json.load(response)
        assert health_body["saved_statements"] == 1
        with pytest.raises(urllib.error.HTTPError) as missing:
            urllib.request.urlopen(f"{base}/api/nothing", timeout=10)
        assert missing.value.code == 404
    finally:
        server.shutdown()
