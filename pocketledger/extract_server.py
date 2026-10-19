"""Extract API for the Android app. The Gemini key stays in this machine's .env.

Endpoints
- POST /api/extract  {source, mime_type, data, business_name, category, save?}
    Reads the page with Gemini, saves it to the trader's history (unless save is false), and
    returns the statement plus the Business Health Score over the whole history.
- GET  /api/health?business_name=...&category=...
    Returns the current Business Health Score for a trader without a new capture.

Phone captures are stored in the same ledger store as the Streamlit app, so a trader with the
same business name and category sees one history and one score everywhere.
"""

import json
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

import ledger_store
from health_score import compute as compute_health
from health_summary import attach_health
from ledger_core import extract_ledger, friendly_gemini_error, is_rate_limit_error

load_dotenv()


def _health_for(ledgers: list[dict[str, Any]], today: date | None = None) -> dict[str, Any]:
    return compute_health(ledgers, as_of=today or date.today())


def handle_extract(
    payload: dict[str, Any],
    extractor: Callable[..., dict[str, Any]] = extract_ledger,
    today: date | None = None,
) -> dict[str, Any]:
    business_name = str(payload.get("business_name") or "").strip()
    category = str(payload.get("category") or "").strip()
    result = extractor(
        source=str(payload.get("source") or "image"),
        mime_type=str(payload.get("mime_type") or "image/jpeg"),
        data_b64=str(payload.get("data") or ""),
        business_name=business_name,
        category=category,
    )
    user_id = ledger_store.user_id_for(business_name, category)
    save = payload.get("save", True) not in (False, "false", 0, "0")
    if save:
        # Phone captures don't change which trader the Streamlit app opens with.
        ledgers = ledger_store.append_ledger(user_id, business_name, category, result, set_last_user=False)
    else:
        ledgers = ledger_store.get_ledgers(user_id) + [ledger_store.ledger_snapshot(result)]
    saved_count = len(ledgers) if save else len(ledgers) - 1
    response = attach_health(result, _health_for(ledgers, today))
    response.update({"trader_id": user_id, "saved": save, "saved_statements": saved_count})
    return response


def handle_health(query: dict[str, Any], today: date | None = None) -> dict[str, Any]:
    business_name = str(query.get("business_name") or "").strip()
    category = str(query.get("category") or "").strip()
    user_id = ledger_store.user_id_for(business_name, category)
    ledgers = ledger_store.get_ledgers(user_id)
    return {"trader_id": user_id, "saved_statements": len(ledgers), "health": _health_for(ledgers, today)}


class Handler(BaseHTTPRequestHandler):
    extractor: Callable[..., dict[str, Any]] = staticmethod(extract_ledger)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/health":
            self.send_error(404, "Not found")
            return
        query = {key: values[0] for key, values in parse_qs(parsed.query).items()}
        try:
            self._send_json(200, handle_health(query))
        except Exception as error:  # pragma: no cover - defensive
            self._send_json(500, {"error": str(error)})

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/api/extract":
            self.send_error(404, "Not found")
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
            self._send_json(200, handle_extract(payload, type(self).extractor))
        except Exception as error:
            message = friendly_gemini_error(error)
            if is_rate_limit_error(error) or "quota" in message.lower():
                status = 429
            elif "503" in message or "overloaded" in message.lower():
                status = 503
            else:
                status = 500
            self._send_json(status, {"error": message})

    def _send_json(self, status: int, body: dict):
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args):
        print("[%s] %s" % (self.log_date_time_string(), format % args))


if __name__ == "__main__":
    port = 8765
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"PocketLedger API listening on http://0.0.0.0:{port} (POST /api/extract, GET /api/health)")
    server.serve_forever()
