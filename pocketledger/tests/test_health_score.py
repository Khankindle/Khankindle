"""Tests for health_score.py — acceptance criteria in SPEC.md §7.8."""

import copy
import json
import re
from datetime import date, timedelta
from pathlib import Path

import pytest

import health_score as hs
from health_score import compute, interpolate, parse_date

START = date(2026, 8, 10)  # a Monday
SAMPLES = Path(__file__).resolve().parent.parent / "samples" / "ledgers" / "ground_truth.json"


# --------------------------------------------------------------------------- fixtures / builders


def trading_dates(n_days, start=START, days_per_week=6):
    """The first `n_days` trading dates from `start`, skipping Sundays when 6 days a week."""
    out, d = [], start
    while len(out) < n_days:
        if days_per_week == 7 or d.weekday() != 6:
            out.append(d)
        d += timedelta(days=1)
    return out


def tx(item, amount, payment="Cash", debtor="N/A", **extra):
    row = {"item": item, "quantity": "1", "amount_usd": amount, "payment_type": payment, "debtor": debtor}
    row.update(extra)
    return row


def ledger(day, transactions, same_day=True):
    processed = day if same_day else day + timedelta(days=5)
    return {
        "date": day.strftime("%d %b %Y"),
        "processed_at": f"{processed.isoformat()}T18:00:00",
        "transactions": transactions,
    }


def steady_history(n_days=42, cash=30.0, expense=5.0, growth=0.0, extra=None):
    """A clean trader: same items every day, small daily expense, optional weekly growth."""
    pages = []
    for i, day in enumerate(trading_dates(n_days)):
        factor = 1 + growth * ((day - START).days // 7)
        rows = [
            tx("Bread", round(cash * 0.4 * factor, 2)),
            tx("Cooking oil", round(cash * 0.35 * factor, 2)),
            tx("Sugar", round(cash * 0.25 * factor, 2)),
            tx("Stall fee", expense, "Expense"),
        ]
        if extra:
            rows.extend(extra(i, day))
        pages.append(ledger(day, rows))
    return pages


def as_of_for(pages):
    return max(parse_date(p["date"]) for p in pages)


# --------------------------------------------------------------------------- helpers


class TestInterpolate:
    anchors = [(0.20, 0), (0.50, 50), (0.85, 100)]

    def test_anchor_points_are_exact(self):
        assert interpolate(0.20, self.anchors) == 0
        assert interpolate(0.50, self.anchors) == 50
        assert interpolate(0.85, self.anchors) == 100

    def test_between_anchors_is_linear(self):
        assert interpolate(0.35, self.anchors) == pytest.approx(25)

    def test_values_outside_are_clamped(self):
        assert interpolate(-5, self.anchors) == 0
        assert interpolate(9, self.anchors) == 100

    def test_decreasing_anchors(self):
        cv = hs.HEALTH_CONFIG["anchors"]["sales_stability"]
        assert interpolate(0.10, cv) == 100
        assert interpolate(0.60, cv) == 50
        assert interpolate(2.00, cv) == 0
        assert interpolate(0.90, cv) == pytest.approx(25)


class TestParseDate:
    @pytest.mark.parametrize(
        "text, expected",
        [
            ("19 Sept 2026", date(2026, 9, 19)),
            ("19 September 2026", date(2026, 9, 19)),
            ("2026-09-19", date(2026, 9, 19)),
            ("2026-09-19T08:00:00", date(2026, 9, 19)),
            ("19/09/2026", date(2026, 9, 19)),
            ("19th Sep 2026", date(2026, 9, 19)),
        ],
    )
    def test_formats(self, text, expected):
        assert parse_date(text) == expected

    def test_unspecified(self):
        assert parse_date("Unspecified") is None
        assert parse_date("") is None

    def test_falls_back_to_processed_at(self):
        page = {"date": "Unspecified", "processed_at": "2026-09-20T10:00:00", "transactions": []}
        assert hs.ledger_date(page) == date(2026, 9, 20)


# --------------------------------------------------------------------------- history gate (§7.4)


class TestHistoryGate:
    def test_empty(self):
        result = compute([])
        assert result["status"] == "Not enough data"
        assert result["score"] is None

    def test_not_enough_data(self):
        result = compute(steady_history(3))
        assert result["status"] == "Not enough data"
        assert result["score"] is None
        assert result["record_more_days"] == 2

    def test_provisional_by_day_count(self):
        result = compute(steady_history(10))
        assert result["status"] == "Provisional"
        assert isinstance(result["score"], int)
        assert result["affordability"] is None

    def test_provisional_when_span_is_short(self):
        # 20 trading days recorded, but only over ~3.5 weeks (< 42 days).
        result = compute(steady_history(20))
        assert result["window"]["trading_days"] == 20
        assert result["status"] == "Provisional"

    def test_established(self):
        result = compute(steady_history(42))
        assert result["status"] == "Established"
        assert result["metrics"]["span_days"] >= 42

    def test_window_only_counts_last_56_days(self):
        pages = steady_history(80)
        result = compute(pages)
        assert result["window"]["trading_days"] <= 56


# --------------------------------------------------------------------------- pre-qualification (§7.2)


def _reasons(result):
    return [entry["reason"] for entry in result["excluded"]]


class TestPrequalification:
    def test_outlier_sale_excluded(self):
        def extra(i, day):
            return [tx("Generator", 900.0)] if i == 30 else []

        result = compute(steady_history(42, extra=extra))
        assert "Unusually large sale" in _reasons(result)

    def test_outlier_needs_prior_history(self):
        # A large sale on day 1 cannot be judged an outlier yet (fewer than 10 prior lines).
        def extra(i, day):
            return [tx("Generator", 900.0)] if i == 0 else []

        result = compute(steady_history(42, extra=extra))
        assert "Unusually large sale" not in _reasons(result)

    def test_repeated_entry_keeps_first(self):
        def extra(i, day):
            return [tx("Soap", 2.0), tx("Soap", 2.0), tx("Soap", 2.0)] if i == 5 else []

        result = compute(steady_history(42, extra=extra))
        assert _reasons(result).count("Possible duplicate") == 2

    def test_two_identical_lines_are_allowed(self):
        def extra(i, day):
            return [tx("Soap", 2.0), tx("Soap", 2.0)] if i == 5 else []

        result = compute(steady_history(42, extra=extra))
        assert "Possible duplicate" not in _reasons(result)

    def test_duplicate_capture(self):
        pages = steady_history(42)
        pages.append(copy.deepcopy(pages[10]))
        result = compute(pages)
        assert _reasons(result).count("Already saved") == len(pages[10]["transactions"])
        assert result["window"]["trading_days"] == 42

    def test_low_confidence(self):
        def extra(i, day):
            return [tx("Smudged", 7.0, confidence=0.3)] if i == 3 else []

        result = compute(steady_history(42, extra=extra))
        assert "Hard to read — please confirm" in _reasons(result)

    def test_confirmed_line_is_counted_again(self):
        def extra(i, day):
            return [tx("Smudged", 7.0, confidence=0.3, confirmed=True)] if i == 3 else []

        result = compute(steady_history(42, extra=extra))
        assert "Hard to read — please confirm" not in _reasons(result)

    def test_zero_amount(self):
        def extra(i, day):
            return [tx("Mystery", 0)] if i == 3 else []

        assert "No amount" in _reasons(compute(steady_history(42, extra=extra)))

    def test_non_business(self):
        def extra(i, day):
            return [tx("From my brother", 50.0, "Personal")] if i == 3 else []

        assert "Not a sale" in _reasons(compute(steady_history(42, extra=extra)))

    def test_excluded_entries_count_matches_list(self):
        def extra(i, day):
            return [tx("Mystery", 0)] if i in (3, 4) else []

        result = compute(steady_history(42, extra=extra))
        assert result["excluded_entries"] == len(result["excluded"]) == 2


# --------------------------------------------------------------------------- scoring scenarios (§7.8)


class TestScenarios:
    def test_perfect_trader_scores_at_least_95(self):
        def extra(i, day):
            rows = []
            if i % 6 == 0:
                rows.append(tx("Maize meal", 4.0, "Credit", "Mai Tendai"))
            if i % 6 == 1 and i > 1:
                rows.append(tx("Paid back", 4.0, "Repayment", "Mai Tendai"))
            return rows

        result = compute(steady_history(48, growth=0.03, extra=extra))
        assert result["status"] == "Established"
        assert result["score"] >= 95, result["components"]
        assert result["band"] == "Strong"

    def test_mostly_aged_credit_scores_c4_at_most_30(self):
        pages = steady_history(48)
        # A big credit sale early on that is never repaid → ~80%+ of outstanding is > 30 days old.
        pages[0]["transactions"].append(tx("Bulk maize", 400.0, "Credit", "Baba John"))
        pages[-2]["transactions"].append(tx("Soap", 60.0, "Credit", "Mai Rudo"))
        result = compute(pages)
        book = result["credit_book"]
        assert book["aged_over_30_days_usd"] / book["outstanding_usd"] >= 0.8
        assert result["components"]["credit_health"] <= 30
        assert "credit_health" in result["reasons"]

    def test_repayment_lowers_outstanding_credit(self):
        base = steady_history(42)
        base[5]["transactions"].append(tx("Maize meal", 20.0, "Credit", "Mai Tendai"))
        before = compute(base)

        repaid = copy.deepcopy(base)
        repaid[10]["transactions"].append(tx("Paid back", 15.0, "Repayment", "mai tendai"))
        after = compute(repaid)

        assert before["credit_book"]["outstanding_usd"] == 20.0
        assert after["credit_book"]["outstanding_usd"] == 5.0
        assert after["credit_sub_scores"]["collection"] > before["credit_sub_scores"]["collection"]
        assert after["components"]["credit_health"] >= before["components"]["credit_health"]

    def test_repayment_is_not_counted_as_sales(self):
        base = steady_history(42)
        base[5]["transactions"].append(tx("Maize meal", 20.0, "Credit", "Mai Tendai"))
        repaid = copy.deepcopy(base)
        repaid[10]["transactions"].append(tx("Paid back", 20.0, "Repayment", "Mai Tendai"))
        # Same sales → same stability metric; only cash-in changes.
        assert compute(base)["metrics"]["sales_cv"] == compute(repaid)["metrics"]["sales_cv"]

    def test_fifo_repayment_clears_oldest_credit_first(self):
        pages = steady_history(48)
        pages[0]["transactions"].append(tx("Old debt", 10.0, "Credit", "Tino"))
        pages[-3]["transactions"].append(tx("New debt", 10.0, "Credit", "Tino"))
        pages[-1]["transactions"].append(tx("Paid back", 10.0, "Repayment", "Tino"))
        result = compute(pages)
        assert result["credit_book"]["outstanding_usd"] == 10.0
        assert result["credit_book"]["aged_over_30_days_usd"] == 0.0

    def test_gaps_in_recording_lower_consistency(self):
        full = compute(steady_history(42))
        sparse_pages = steady_history(42)[::3]  # records only every third trading day
        sparse = compute(sparse_pages, as_of=as_of_for(steady_history(42)))
        assert sparse["components"]["recording_consistency"] < full["components"]["recording_consistency"]

    def test_not_recording_recently_counts_against_trader_when_as_of_is_today(self):
        pages = steady_history(42)
        last = as_of_for(pages)
        on_time = compute(pages, as_of=last)
        stale = compute(pages, as_of=last + timedelta(days=14))
        assert stale["components"]["recording_consistency"] < on_time["components"]["recording_consistency"]

    def test_falling_sales_lower_growth(self):
        assert compute(steady_history(42, growth=-0.1))["components"]["growth_trend"] < 50
        assert compute(steady_history(42, growth=0.05))["components"]["growth_trend"] > 50

    def test_expense_heavy_trader(self):
        # Coverage 10 / 9 = 1.11 → 11 points; coverage below 1.0 → 0 points.
        assert compute(steady_history(42, cash=10.0, expense=9.0))["components"]["expense_coverage"] == 11
        result = compute(steady_history(42, cash=10.0, expense=10.5))
        assert result["components"]["expense_coverage"] == 0
        assert any(a["component"] == "expense_coverage" for a in result["actions"]) or result["reasons"]

    def test_concentration_action_names_debtor(self):
        pages = steady_history(42)
        pages[-1]["transactions"].append(tx("Bulk", 40.0, "Credit", "Baba John"))
        pages[-1]["transactions"].append(tx("Soap", 2.0, "Credit", "Tino"))
        result = compute(pages)
        assert result["credit_sub_scores"]["concentration"] < 20


class TestOutlierRobustness:
    """§7.8 (3): adding a single outlier sale never raises the score by more than 2 points."""

    @pytest.mark.parametrize("day_index", [12, 25, 40])
    @pytest.mark.parametrize("amount", [300.0, 2_000.0, 50_000.0])
    @pytest.mark.parametrize("payment", ["Cash", "Credit"])
    def test_single_outlier(self, day_index, amount, payment):
        pages = steady_history(42, extra=lambda i, d: [tx("Lunch", 3.0, "Credit", "Tino")] if i % 7 == 0 else [])
        baseline = compute(pages)
        spiked = copy.deepcopy(pages)
        spiked[day_index]["transactions"].append(tx("Big order", amount, payment, "Big buyer"))
        result = compute(spiked)
        assert result["score"] - baseline["score"] <= 2


# --------------------------------------------------------------------------- affordability (§7.6)


class TestAffordability:
    def test_formula(self):
        result = compute(steady_history(42, cash=30.0, expense=5.0))
        aff = result["affordability"]
        assert result["score"] >= 50
        assert aff["typical_net_cash_usd"] == pytest.approx(25.0)
        assert aff["safe_daily_repayment_usd"] == pytest.approx(5.0)
        assert aff["indicative_amount_30d_usd"] == pytest.approx(round(5.0 * 6 * 30 / 7, 2))
        assert "not a loan offer" in aff["note"]

    def test_hidden_below_score_50(self):
        pages = steady_history(42, cash=10.0, expense=9.5)
        for page in pages[::2]:
            page["transactions"].append(tx("Bulk", 60.0, "Credit", "One buyer"))
        result = compute(pages)
        assert result["status"] == "Established"
        assert result["score"] < 50, result["components"]
        assert result["affordability"] is None

    def test_hidden_when_provisional(self):
        assert compute(steady_history(10))["affordability"] is None

    def test_hidden_when_net_cash_not_positive(self):
        result = compute(steady_history(42, cash=10.0, expense=12.0))
        assert result["affordability"] is None


# --------------------------------------------------------------------------- contract & purity


class TestContract:
    def test_output_contract(self):
        result = compute(steady_history(42))
        for key in (
            "score_version", "status", "score", "band", "evidence_level", "window",
            "components", "excluded_entries", "reasons", "strength", "affordability",
        ):
            assert key in result
        assert result["score_version"] == hs.SCORE_VERSION
        assert set(result["components"]) == set(hs.HEALTH_CONFIG["weights"])
        assert all(0 <= v <= 100 for v in result["components"].values())
        assert set(result["window"]) == {"start", "end", "trading_days"}
        json.dumps(result)  # must be JSON-serialisable for the store and the API

    def test_weights_sum_to_100(self):
        assert sum(hs.HEALTH_CONFIG["weights"].values()) == 100
        assert sum(hs.HEALTH_CONFIG["credit_sub_weights"].values()) == pytest.approx(1.0)

    def test_score_is_weighted_sum_of_components(self):
        result = compute(steady_history(42))
        weights = hs.HEALTH_CONFIG["weights"]
        expected = round(sum(weights[k] * v for k, v in result["components"].items()) / 100)
        assert result["score"] == expected

    def test_spec_worked_example(self):
        components = {
            "recording_consistency": 84, "sales_stability": 61, "cash_conversion": 77,
            "credit_health": 58, "expense_coverage": 90, "growth_trend": 55,
        }
        weights = hs.HEALTH_CONFIG["weights"]
        assert round(sum(weights[k] * v for k, v in components.items()) / 100) == 72
        assert hs.band_for(72)["English"] == "Good"

    @pytest.mark.parametrize("score, band", [(100, "Strong"), (80, "Strong"), (79, "Good"), (65, "Good"), (64, "Fair"), (50, "Fair"), (49, "Building"), (0, "Building")])
    def test_bands(self, score, band):
        assert hs.band_for(score)["English"] == band

    def test_deterministic_and_does_not_mutate_input(self):
        pages = steady_history(42, extra=lambda i, d: [tx("Soap", 2.0, "Credit", "Tino")] if i % 5 == 0 else [])
        snapshot = copy.deepcopy(pages)
        first = compute(pages)
        second = compute(pages)
        assert first == second
        assert pages == snapshot

    def test_input_order_does_not_matter(self):
        pages = steady_history(42)
        assert compute(pages) == compute(list(reversed(pages)))

    def test_evidence_level(self):
        assert compute(steady_history(42))["evidence_level"] == "Captured same-day"
        late = [ledger(parse_date(p["date"]), p["transactions"], same_day=False) for p in steady_history(42)]
        assert compute(late)["evidence_level"] == "Self-reported"

    def test_reasons_are_biggest_point_losses(self):
        result = compute(steady_history(42, cash=10.0, expense=9.0))
        weights = hs.HEALTH_CONFIG["weights"]
        limit = hs.HEALTH_CONFIG["reason_max_component"]
        costs = {k: weights[k] * (100 - v) for k, v in result["components"].items() if v < limit}
        assert result["reasons"][0] == max(costs, key=costs.get)
        assert len(result["actions"]) == len(result["reasons"])

    def test_no_credit_advice_for_trader_who_gives_no_credit(self):
        result = compute(steady_history(42))  # cash only
        assert result["components"]["credit_health"] == 90  # collection is neutral (50)
        assert "credit_health" not in result["reasons"]
        assert not any("chikwereti" in a["English"] for a in result["actions"])

    def test_flat_sales_are_not_called_a_drop(self):
        pages = steady_history(42, cash=10.0, expense=10.5)
        result = compute(pages)
        texts = " ".join(a["English"] for a in result["actions"])
        assert "dropped" not in texts

    def test_aged_credit_action_names_debtors(self):
        pages = steady_history(48)
        pages[0]["transactions"].append(tx("Bulk maize", 400.0, "Credit", "Baba John"))
        result = compute(pages)
        credit_action = next(a for a in result["actions"] if a["component"] == "credit_health")
        assert "Baba John" in credit_action["English"]

    def test_profile_trading_days_per_week(self):
        pages = steady_history(42)  # 6 days a week
        six = compute(pages, profile={"trading_days_per_week": 6})
        seven = compute(pages, profile={"trading_days_per_week": 7})
        assert seven["components"]["recording_consistency"] <= six["components"]["recording_consistency"]


# --------------------------------------------------------------------------- ground-truth replay (§7.8 (4))

_LINE = re.compile(r"^(?:\d+\.\s*)?(?P<item>.+?)[:\s]+\$(?P<amount>[\d.]+)\s*(?:\((?P<tag>[^)]*)\))?\s*$")


def _parse_sample_lines(lines):
    rows = []
    for line in lines:
        match = _LINE.match(line.strip())
        assert match, line
        tag = (match["tag"] or "").strip()
        item = match["item"].strip()
        amount = float(match["amount"])
        if tag.lower().startswith("credit"):
            debtor = tag.split("-", 1)[1].strip() if "-" in tag else "Unknown"
            rows.append(tx(item, amount, "Credit", debtor))
        elif tag.lower() == "expense" or not tag:
            # Untagged lines in the samples are stall fees / rent → expenses.
            rows.append(tx(item, amount, "Expense"))
        else:
            rows.append(tx(item, amount, "Cash"))
    return rows


def _replay(sample, weeks=6):
    """Replay one sample page as a 6-week history with deterministic day-to-day variation.

    Each credit is repaid two trading days later so the credit book behaves like a real trader's.
    """
    template = _parse_sample_lines(sample["lines"])
    pages, owed = [], []
    for i, day in enumerate(trading_dates(weeks * 6 + 1)):
        factor = 1 + 0.1 * ((i * 7) % 5 - 2) / 2  # cycles through 0.9 .. 1.1
        rows = []
        for row in template:
            r = dict(row)
            if r["payment_type"] != "Expense":
                r["amount_usd"] = round(r["amount_usd"] * factor, 2)
            rows.append(r)
            if r["payment_type"] == "Credit":
                owed.append((i + 2, r["debtor"], r["amount_usd"]))
        rows.extend(tx("Paid back", amt, "Repayment", who) for due, who, amt in owed if due == i)
        pages.append(ledger(day, rows))
    return pages


def _samples():
    return json.loads(SAMPLES.read_text(encoding="utf-8"))


def test_sample_parser_matches_ground_truth_totals():
    for sample in _samples():
        rows = _parse_sample_lines(sample["lines"])
        cash = sum(r["amount_usd"] for r in rows if r["payment_type"] == "Cash")
        credit = sum(r["amount_usd"] for r in rows if r["payment_type"] == "Credit")
        expected = sample["expected_totals"]
        assert cash == pytest.approx(expected["total_cash_usd"]), sample["file"]
        assert credit == pytest.approx(expected["total_credit_outstanding_usd"]), sample["file"]


@pytest.mark.parametrize("sample", _samples(), ids=lambda s: s["file"])
def test_ground_truth_replay_is_stable(sample):
    pages = _replay(sample)
    first = compute(pages)
    second = compute(copy.deepcopy(pages))
    assert first == second
    assert first["status"] == "Established"
    assert 0 <= first["score"] <= 100
    # Credit is repaid within two days, so nothing should be aged.
    assert first["credit_book"]["aged_over_30_days_usd"] == 0
    assert first["excluded_entries"] == 0


def test_performance_stays_near_linear():
    """SPEC.md §9 targets < 100 ms for 1,000 ledgers. 3,000 ledgers in < 1 s catches a quadratic regression
    without being flaky on slow CI machines."""
    import time

    pages = steady_history(3000, extra=lambda i, d: [tx("Soap", 3.0, "Credit", f"D{i % 9}")] if i % 3 == 0 else [])
    started = time.perf_counter()
    compute(pages)
    assert time.perf_counter() - started < 1.0
