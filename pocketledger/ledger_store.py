"""Trader profiles and saved ledgers, shared by the Streamlit app and the extract API.

Both processes read and write the same JSON file, so a statement captured on the phone shows up
in the Streamlit app (and its health score) for the same business name and category.
"""

from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from ledger_core import to_float

_LOCK = threading.Lock()


def data_dir() -> Path:
    return Path(os.environ.get("POCKETLEDGER_DATA_DIR") or Path(__file__).resolve().parent / "data")


def store_path() -> Path:
    return data_dir() / "ledger_store.json"


def user_id_for(name: str, category: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", f"{name}_{category}".lower()).strip("_")
    return slug or "unnamed_trader"


def load_store() -> dict[str, Any]:
    path = store_path()
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {"users": {}, "last_user_id": None}


def save_store(store: dict[str, Any]) -> None:
    """Write atomically so a reader in the other process never sees a half-written file."""
    path = store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(store, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def ledger_snapshot(result: dict[str, Any], processed_at: str | None = None) -> dict[str, Any]:
    return {
        "processed_at": processed_at or datetime.now().isoformat(timespec="seconds"),
        "business_name": result.get("business_name"),
        "business_category": result.get("business_category"),
        "date": result.get("date"),
        "capture_source": result.get("capture_source"),
        "transcript": result.get("transcript"),
        "total_revenue_usd": round(to_float(result.get("total_revenue_usd")), 2),
        "total_cash_usd": round(to_float(result.get("total_cash_usd")), 2),
        "total_credit_outstanding_usd": round(to_float(result.get("total_credit_outstanding_usd")), 2),
        "transactions": result.get("transactions") or [],
        "business_health_summary": result.get("business_health_summary"),
        "summary_shona": result.get("summary_shona"),
        "summary_ndebele": result.get("summary_ndebele"),
    }


def get_profile(user_id: str) -> dict[str, Any] | None:
    return (load_store().get("users") or {}).get(user_id)


def get_ledgers(user_id: str) -> list[dict[str, Any]]:
    profile = get_profile(user_id) or {}
    return list(profile.get("ledgers") or [])


def save_profile(user_id: str, business_name: str, category: str) -> None:
    with _LOCK:
        store = load_store()
        profile = store.setdefault("users", {}).setdefault(user_id, {"ledgers": []})
        profile["business_name"] = business_name
        profile["business_category"] = category
        store["last_user_id"] = user_id
        save_store(store)


def append_ledger(
    user_id: str, business_name: str, category: str, result: dict[str, Any], *, set_last_user: bool = True
) -> list[dict[str, Any]]:
    """Save one statement and return the trader's full ledger list."""
    with _LOCK:
        store = load_store()
        profile = store.setdefault("users", {}).setdefault(
            user_id, {"business_name": business_name, "business_category": category, "ledgers": []}
        )
        profile.setdefault("business_name", business_name)
        profile.setdefault("business_category", category)
        profile.setdefault("ledgers", []).append(ledger_snapshot(result))
        if set_last_user:
            store["last_user_id"] = user_id
        save_store(store)
        return list(profile["ledgers"])
