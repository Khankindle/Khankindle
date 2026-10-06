"""PocketLedger Business Health Score (SPEC.md §7).

A deterministic, explainable, rule-based index (0-100) computed from a trader's
saved ledgers. It is NOT a machine-learning model, NOT a probability of default,
and NOT a loan decision. No network or LLM calls happen here.

Usage::

    from health_score import compute
    health = compute(ledgers, profile={"trading_days_per_week": 6}, as_of=date.today())

`ledgers` is the list saved by ``app.persist_ledger`` (each item has ``date``,
``processed_at`` and ``transactions``).
"""

from __future__ import annotations

import re
from bisect import insort
from datetime import date, datetime, timedelta
from statistics import median, pstdev
from typing import Any, Iterable

SCORE_VERSION = "hs-1.0"

HEALTH_CONFIG: dict[str, Any] = {
    "window_days": 56,
    "default_trading_days_per_week": 6,
    # History gate (§7.4)
    "min_days_for_score": 5,
    "established_min_days": 14,
    "established_min_span_days": 42,
    # Pre-qualification (§7.2)
    "outlier_line_multiple": 5.0,
    "outlier_daily_multiple": 2.0,
    "outlier_min_prior_lines": 10,
    "repeat_entry_threshold": 3,
    "min_confidence": 0.5,
    # Component weights (§7.5) — must sum to 100
    "weights": {
        "recording_consistency": 25,
        "sales_stability": 15,
        "cash_conversion": 20,
        "credit_health": 25,
        "expense_coverage": 10,
        "growth_trend": 5,
    },
    # Anchor points: (metric value, points). Interpolated linearly, clamped at the ends.
    "anchors": {
        "recording_consistency": [(0.20, 0), (0.50, 50), (0.85, 100)],
        "sales_stability": [(0.25, 100), (0.60, 50), (1.20, 0)],
        "cash_conversion": [(0.40, 0), (0.70, 50), (0.90, 100)],
        "expense_coverage": [(1.0, 0), (1.5, 50), (3.0, 100)],
        "growth_trend": [(-0.15, 0), (0.0, 50), (0.10, 100)],
        "credit_exposure": [(0.15, 100), (0.50, 50), (1.50, 0)],
        "credit_ageing": [(0.0, 100), (0.20, 50), (0.50, 0)],
        "credit_collection": [(0.20, 0), (0.50, 50), (0.80, 100)],
        "credit_concentration": [(0.20, 100), (0.40, 50), (0.70, 0)],
    },
    "credit_sub_weights": {"exposure": 0.40, "ageing": 0.30, "collection": 0.20, "concentration": 0.10},
    "credit_aged_after_days": 30,
    "concentration_min_outstanding_usd": 5.0,
    "growth_min_full_weeks": 3,
    # Only components below this are listed as "what is lowering your score", so neutral
    # defaults (e.g. no credit given, too little history for a trend) don't produce advice.
    "reason_max_component": 75,
    "same_day_capture_share": 0.80,
    # Affordability guide (§7.6)
    "affordability_share_of_net_cash": 0.20,
    "affordability_min_score": 50,
    "affordability_horizon_days": 30,
    # Bands (§7.6) — ChiShona / IsiNdebele pending native-speaker review
    "bands": [
        (80, "Strong", "Rakasimba", "Liqinile"),
        (65, "Good", "Rakanaka", "Lihle"),
        (50, "Fair", "Riri pakati", "Liphakathi"),
        (0, "Building", "Richiri kuvaka", "Lisakhela"),
    ],
}

NON_BUSINESS_PAYMENT_TYPES = ("personal", "transfer", "loan received", "owner", "top-up by owner")

DISCLAIMER = "Guide only — not a loan offer. A lender will do its own checks."


# --------------------------------------------------------------------------- helpers


def _to_float(value: Any) -> float:
    try:
        return float(str(value).replace("$", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return 0.0


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d %b %Y",
    "%d %B %Y",
    "%d %b %y",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%b %d %Y",
    "%B %d %Y",
)


def parse_date(value: Any) -> date | None:
    """Parse the free-text dates Gemini returns (e.g. '19 Sept 2026')."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _text(value)
    if not text or text.lower() == "unspecified":
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}", text):
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            pass
    cleaned = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bSept\b", "Sep", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace(",", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def ledger_date(ledger: dict[str, Any]) -> date | None:
    return parse_date(ledger.get("date")) or parse_date(_text(ledger.get("processed_at"))[:10])


def classify(row: dict[str, Any]) -> str:
    """Return 'expense' | 'repayment' | 'credit' | 'nonbusiness' | 'cash'."""
    payment = _text(row.get("payment_type")).lower()
    if "expense" in payment or "rent" in payment:
        return "expense"
    if "repay" in payment:
        return "repayment"
    if "credit" in payment or "chikwereti" in payment or "isikwelete" in payment:
        return "credit"
    if any(token in payment for token in NON_BUSINESS_PAYMENT_TYPES):
        return "nonbusiness"
    return "cash"


def interpolate(value: float, anchors: list[tuple[float, float]]) -> float:
    """Piecewise-linear map of `value` through sorted (x, points) anchors, clamped."""
    points = sorted(anchors)
    if value <= points[0][0]:
        return float(points[0][1])
    if value >= points[-1][0]:
        return float(points[-1][1])
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= value <= x1:
            if x1 == x0:
                return float(y1)
            return y0 + (y1 - y0) * (value - x0) / (x1 - x0)
    return float(points[-1][1])  # pragma: no cover


def _debtor_key(row: dict[str, Any]) -> str:
    name = re.sub(r"\s+", " ", _text(row.get("debtor"))).lower()
    return "" if name in ("", "n/a", "na", "none", "-") else name


def _debtor_label(row: dict[str, Any]) -> str:
    return re.sub(r"\s+", " ", _text(row.get("debtor"))) or "Unknown"


def band_for(score: int, config: dict[str, Any] = HEALTH_CONFIG) -> dict[str, str]:
    for floor, en, sn, nd in config["bands"]:
        if score >= floor:
            return {"English": en, "ChiShona": sn, "IsiNdebele": nd}
    _, en, sn, nd = config["bands"][-1]
    return {"English": en, "ChiShona": sn, "IsiNdebele": nd}


# --------------------------------------------------------------------------- pre-qualification


def _flatten(ledgers: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[date]]:
    """Turn ledgers into dated lines and drop duplicate captures.

    Returns (lines, excluded, trading_dates). Lines are in chronological order
    (date, then capture order).
    """
    excluded: list[dict[str, Any]] = []
    seen_pages: set[tuple] = set()
    pages: list[tuple[date, int, dict[str, Any]]] = []
    for index, ledger in enumerate(ledgers or []):
        when = ledger_date(ledger)
        if when is None:
            for row in ledger.get("transactions") or []:
                excluded.append(_excluded_entry(None, row, "No date on this page"))
            continue
        rows = ledger.get("transactions") or []
        fingerprint = (
            when,
            tuple(
                sorted(
                    (
                        _text(r.get("item")).lower(),
                        round(_to_float(r.get("amount_usd")), 2),
                        _text(r.get("payment_type")).lower(),
                        _debtor_key(r),
                    )
                    for r in rows
                )
            ),
        )
        if rows and fingerprint in seen_pages:
            for row in rows:
                excluded.append(_excluded_entry(when, row, "Already saved"))
            continue
        seen_pages.add(fingerprint)
        pages.append((when, index, ledger))

    pages.sort(key=lambda item: (item[0], item[1]))
    lines: list[dict[str, Any]] = []
    trading_dates: set[date] = set()
    for page_no, (when, _, ledger) in enumerate(pages):
        trading_dates.add(when)
        for row in ledger.get("transactions") or []:
            lines.append(
                {
                    "date": when,
                    "page": page_no,
                    "kind": classify(row),
                    "amount": round(_to_float(row.get("amount_usd")), 2),
                    "item": _text(row.get("item")),
                    "debtor_key": _debtor_key(row),
                    "debtor": _debtor_label(row),
                    "confidence": row.get("confidence"),
                    "confirmed": bool(row.get("confirmed")),
                    "row": row,
                }
            )
    return lines, excluded, trading_dates


def _excluded_entry(when: date | None, row: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "date": when.isoformat() if when else None,
        "item": _text(row.get("item")),
        "amount_usd": round(_to_float(row.get("amount_usd")), 2),
        "reason": reason,
    }


def prequalify(
    ledgers: list[dict[str, Any]], config: dict[str, Any] = HEALTH_CONFIG
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[date]]:
    """Apply the §7.2 rules. Returns (kept_lines, excluded_entries, trading_dates)."""
    lines, excluded, trading_dates = _flatten(ledgers)
    kept: list[dict[str, Any]] = []

    # Repeated entry: count identical (item, amount, debtor) per page; keep the first.
    repeat_counts: dict[tuple, int] = {}
    for line in lines:
        key = (line["page"], line["item"].lower(), line["amount"], line["debtor_key"])
        repeat_counts[key] = repeat_counts.get(key, 0) + 1
    repeat_seen: dict[tuple, int] = {}

    # Running sorted lists so the outlier check stays O(n log n) (SPEC.md §9: < 100 ms / 1,000 ledgers).
    prior_sale_amounts: list[float] = []  # sorted kept sale amounts so far
    closed_day_totals: list[float] = []  # sorted sales totals of earlier days
    current_day: date | None = None
    current_day_total = 0.0

    for line in lines:
        when, amount, kind = line["date"], line["amount"], line["kind"]
        if when != current_day:
            if current_day is not None:
                insort(closed_day_totals, current_day_total)
            current_day, current_day_total = when, 0.0
        reason = None
        if amount <= 0:
            reason = "No amount"
        elif not line["confirmed"]:
            confidence = line["confidence"]
            key = (line["page"], line["item"].lower(), amount, line["debtor_key"])
            if confidence is not None and _to_float(confidence) < config["min_confidence"]:
                reason = "Hard to read — please confirm"
            elif kind == "nonbusiness":
                reason = "Not a sale"
            elif repeat_counts[key] >= config["repeat_entry_threshold"]:
                repeat_seen[key] = repeat_seen.get(key, 0) + 1
                if repeat_seen[key] > 1:
                    reason = "Possible duplicate"
            if reason is None and kind in ("cash", "credit"):
                if len(prior_sale_amounts) >= config["outlier_min_prior_lines"] and closed_day_totals:
                    line_median = _sorted_median(prior_sale_amounts)
                    day_median = _sorted_median(closed_day_totals)
                    if (
                        amount > config["outlier_line_multiple"] * line_median
                        and amount > config["outlier_daily_multiple"] * day_median
                    ):
                        reason = "Unusually large sale"
        elif kind == "nonbusiness":
            reason = "Not a sale"

        if reason:
            excluded.append(_excluded_entry(when, line["row"], reason))
            continue
        kept.append(line)
        if kind in ("cash", "credit"):
            insort(prior_sale_amounts, amount)
            current_day_total += amount
    return kept, excluded, trading_dates


def _sorted_median(values: list[float]) -> float:
    n = len(values)
    mid = n // 2
    return values[mid] if n % 2 else (values[mid - 1] + values[mid]) / 2


# --------------------------------------------------------------------------- credit book


def build_credit_book(lines: list[dict[str, Any]], as_of: date) -> dict[str, Any]:
    """FIFO credit lots per debtor. Repayments clear the oldest lots first."""
    lots: dict[str, list[list[Any]]] = {}
    labels: dict[str, str] = {}
    for line in lines:
        if line["date"] > as_of:
            continue
        key = line["debtor_key"] or "unknown"
        if line["kind"] == "credit":
            lots.setdefault(key, []).append([line["date"], line["amount"]])
            labels.setdefault(key, line["debtor"])
        elif line["kind"] == "repayment":
            remaining = line["amount"]
            for lot in lots.get(key, []):
                if remaining <= 0:
                    break
                paid = min(lot[1], remaining)
                lot[1] = round(lot[1] - paid, 2)
                remaining = round(remaining - paid, 2)
    balances: dict[str, float] = {}
    aged: dict[str, float] = {}
    for key, debtor_lots in lots.items():
        total = round(sum(lot[1] for lot in debtor_lots), 2)
        if total <= 0:
            continue
        balances[key] = total
        aged[key] = round(
            sum(lot[1] for lot in debtor_lots if (as_of - lot[0]).days > HEALTH_CONFIG["credit_aged_after_days"]),
            2,
        )
    return {
        "outstanding": round(sum(balances.values()), 2),
        "aged": round(sum(aged.values()), 2),
        "balances": balances,
        "aged_by_debtor": {k: v for k, v in aged.items() if v > 0},
        "labels": labels,
    }


# --------------------------------------------------------------------------- main entry point


def compute(
    ledgers: list[dict[str, Any]],
    profile: dict[str, Any] | None = None,
    as_of: date | str | None = None,
    config: dict[str, Any] = HEALTH_CONFIG,
) -> dict[str, Any]:
    """Compute the health object described in SPEC.md §7.7.

    `as_of` defaults to the latest ledger date so the function stays pure; the
    app should pass ``date.today()`` so that days without records count against
    recording consistency.
    """
    profile = profile or {}
    days_per_week = int(profile.get("trading_days_per_week") or config["default_trading_days_per_week"])
    days_per_week = max(1, min(7, days_per_week))

    kept, excluded, trading_dates_all = prequalify(ledgers, config)

    end = parse_date(as_of) if as_of is not None else (max(trading_dates_all) if trading_dates_all else None)
    base = {
        "score_version": SCORE_VERSION,
        "status": "Not enough data",
        "score": None,
        "band": None,
        "band_local": None,
        "evidence_level": None,
        "window": None,
        "components": None,
        "credit_sub_scores": None,
        "excluded_entries": 0,
        "excluded": [],
        "reasons": [],
        "strength": None,
        "actions": [],
        "affordability": None,
        "record_more_days": config["min_days_for_score"],
        "disclaimer": DISCLAIMER,
    }
    if end is None:
        base["excluded_entries"] = len(excluded)
        base["excluded"] = excluded
        return base

    start = end - timedelta(days=config["window_days"] - 1)
    in_window = lambda d: d is not None and start <= d <= end  # noqa: E731
    window_lines = [line for line in kept if in_window(line["date"])]
    window_excluded = [e for e in excluded if e["date"] is None or in_window(date.fromisoformat(e["date"]))]
    trading_dates = sorted(d for d in trading_dates_all if in_window(d))
    trading_days = len(trading_dates)

    base["excluded_entries"] = len(window_excluded)
    base["excluded"] = window_excluded
    base["window"] = {"start": start.isoformat(), "end": end.isoformat(), "trading_days": trading_days}
    base["evidence_level"] = _evidence_level(ledgers, start, end, config)

    if trading_days < config["min_days_for_score"]:
        base["record_more_days"] = config["min_days_for_score"] - trading_days
        return base

    first = trading_dates[0]
    span_days = (end - first).days + 1
    established = trading_days >= config["established_min_days"] and span_days >= config["established_min_span_days"]
    status = "Established" if established else "Provisional"

    # ---- daily inputs (§7.3)
    daily = {d: {"cash": 0.0, "credit": 0.0, "repay": 0.0, "expense": 0.0} for d in trading_dates}
    for line in window_lines:
        bucket = daily[line["date"]]
        key = {"cash": "cash", "credit": "credit", "repayment": "repay", "expense": "expense"}[line["kind"]]
        bucket[key] += line["amount"]
    sales = [v["cash"] + v["credit"] for v in daily.values()]
    cash_in = [v["cash"] + v["repay"] for v in daily.values()]
    expenses = [v["expense"] for v in daily.values()]
    net_cash = [c - e for c, e in zip(cash_in, expenses)]
    total_sales, total_cash_in, total_expenses = sum(sales), sum(cash_in), sum(expenses)
    credit_issued = sum(v["credit"] for v in daily.values())
    repayments = sum(v["repay"] for v in daily.values())

    anchors = config["anchors"]
    raw: dict[str, float] = {}

    # C1 recording consistency
    expected_days = max(1.0, days_per_week * span_days / 7)
    active_ratio = min(1.0, trading_days / expected_days)
    raw["recording_consistency"] = interpolate(active_ratio, anchors["recording_consistency"])

    # C2 sales stability (coefficient of variation)
    mean_sales = total_sales / trading_days
    cv = pstdev(sales) / mean_sales if mean_sales > 0 else None
    raw["sales_stability"] = interpolate(cv, anchors["sales_stability"]) if cv is not None else 0.0

    # C3 cash conversion
    raw["cash_conversion"] = (
        interpolate(total_cash_in / total_sales, anchors["cash_conversion"]) if total_sales > 0 else 0.0
    )

    # C4 credit health — book built from all kept history so older open credit still ages
    book = build_credit_book(kept, end)
    weekly_sales = total_sales / (span_days / 7)
    outstanding = book["outstanding"]
    if outstanding <= 0:
        exposure = ageing = concentration = 100.0
    else:
        exposure = interpolate(outstanding / weekly_sales, anchors["credit_exposure"]) if weekly_sales > 0 else 0.0
        ageing = interpolate(book["aged"] / outstanding, anchors["credit_ageing"])
        if outstanding < config["concentration_min_outstanding_usd"]:
            concentration = 100.0
        else:
            concentration = interpolate(max(book["balances"].values()) / outstanding, anchors["credit_concentration"])
    collection = interpolate(repayments / credit_issued, anchors["credit_collection"]) if credit_issued > 0 else 50.0
    sub = {"exposure": exposure, "ageing": ageing, "collection": collection, "concentration": concentration}
    raw["credit_health"] = sum(config["credit_sub_weights"][k] * v for k, v in sub.items())

    # C5 expense coverage (C1 rounded first so the "C1 >= 50" rule matches what is shown)
    if total_expenses > 0:
        raw["expense_coverage"] = interpolate(total_cash_in / total_expenses, anchors["expense_coverage"])
    else:
        raw["expense_coverage"] = 100.0 if round(raw["recording_consistency"]) >= 50 else 50.0

    # C6 growth trend over full weeks only
    raw["growth_trend"] = _growth_score(daily, first, span_days, anchors["growth_trend"], config)

    components = {name: int(round(value)) for name, value in raw.items()}
    weights = config["weights"]
    score = int(round(sum(weights[name] * components[name] for name in weights) / 100))
    band = band_for(score, config)

    # Reasons: biggest point losses first; strength: highest component (ties → heavier weight)
    costs = sorted(
        ((weights[n] * (100 - components[n]), n) for n in weights),
        key=lambda item: (-item[0], list(weights).index(item[1])),
    )
    reasons = [name for cost, name in costs if cost > 0 and components[name] < config["reason_max_component"]][:2]
    strength = max(weights, key=lambda n: (components[n], weights[n]))

    affordability = None
    typical_net_cash = median(net_cash)
    if established and score >= config["affordability_min_score"] and typical_net_cash > 0:
        safe_daily = round(config["affordability_share_of_net_cash"] * typical_net_cash, 2)
        affordability = {
            "safe_daily_repayment_usd": safe_daily,
            "indicative_amount_30d_usd": round(safe_daily * days_per_week * config["affordability_horizon_days"] / 7, 2),
            "typical_net_cash_usd": round(typical_net_cash, 2),
            "note": DISCLAIMER,
        }

    base.update(
        {
            "status": status,
            "score": score,
            "band": band["English"],
            "band_local": band,
            "components": components,
            "credit_sub_scores": {k: int(round(v)) for k, v in sub.items()},
            "credit_book": {
                "outstanding_usd": outstanding,
                "aged_over_30_days_usd": book["aged"],
                "by_debtor": {book["labels"].get(k, k): v for k, v in sorted(book["balances"].items())},
            },
            "reasons": reasons,
            "strength": strength,
            "actions": [_action_for(name, sub, book, components) for name in reasons],
            "affordability": affordability,
            "record_more_days": 0,
            "metrics": {
                "active_ratio": round(active_ratio, 3),
                "sales_cv": round(cv, 3) if cv is not None else None,
                "cash_conversion": round(total_cash_in / total_sales, 3) if total_sales > 0 else None,
                "expense_coverage": round(total_cash_in / total_expenses, 3) if total_expenses > 0 else None,
                "span_days": span_days,
            },
        }
    )
    return base


def _growth_score(daily: dict[date, dict[str, float]], first: date, span_days: int, anchors, config) -> float:
    full_weeks = span_days // 7
    if full_weeks < config["growth_min_full_weeks"]:
        return 50.0
    weekly = [0.0] * full_weeks
    for d, v in daily.items():
        week = (d - first).days // 7
        if week < full_weeks:
            weekly[week] += v["cash"] + v["credit"]
    mean_week = sum(weekly) / full_weeks
    if mean_week <= 0:
        return 50.0
    xs = range(full_weeks)
    mean_x = sum(xs) / full_weeks
    var_x = sum((x - mean_x) ** 2 for x in xs)
    slope = sum((x - mean_x) * (y - mean_week) for x, y in zip(xs, weekly)) / var_x
    return interpolate(slope / mean_week, anchors)


def _evidence_level(ledgers: list[dict[str, Any]], start: date, end: date, config: dict[str, Any]) -> str:
    timed = 0
    same_day = 0
    for ledger in ledgers or []:
        written = parse_date(ledger.get("date"))
        processed = parse_date(_text(ledger.get("processed_at"))[:10])
        if written is None or processed is None or not (start <= written <= end):
            continue
        timed += 1
        if 0 <= (processed - written).days <= 1:
            same_day += 1
    if timed and same_day / timed >= config["same_day_capture_share"]:
        return "Captured same-day"
    return "Self-reported"


def _action_for(
    name: str, sub: dict[str, float], book: dict[str, Any], components: dict[str, int]
) -> dict[str, str]:
    """English action text (§7.6). ChiShona / IsiNdebele to be added after native-speaker review."""
    if name == "recording_consistency":
        text = "Record every trading day, even quiet ones."
    elif name == "sales_stability":
        text = "Your daily sales go up and down a lot. Record all sales, including small ones."
    elif name == "cash_conversion":
        text = "Collect chikwereti before giving new credit."
    elif name == "expense_coverage":
        text = "Expenses are close to your cash income. Check stock costs and rent."
    elif name == "growth_trend":
        if components.get("growth_trend", 50) < 50:
            text = "Sales have dropped over recent weeks. Check stock levels and prices."
        else:
            text = "Sales have been flat. Try stocking items customers ask for."
    else:  # credit_health — point to the weakest credit sub-score
        # Ties go to the most actionable advice: name overdue customers, then the biggest debtor.
        weakest = min(("ageing", "concentration", "exposure", "collection"), key=lambda k: sub[k])
        labels = book["labels"]
        if weakest == "ageing" and book["aged_by_debtor"]:
            names = ", ".join(labels.get(k, k) for k in sorted(book["aged_by_debtor"]))
            count = len(book["aged_by_debtor"])
            people = "customer owes" if count == 1 else "customers owe"
            text = f"{count} {people} you for more than 30 days: {names}."
        elif weakest == "concentration" and book["balances"]:
            key = max(book["balances"], key=book["balances"].get)
            pct = round(100 * book["balances"][key] / book["outstanding"])
            text = f"{labels.get(key, key)} owes {pct}% of your credit. Spread your risk."
        else:
            text = "Collect chikwereti before giving new credit."
    return {"component": name, "English": text}
