"""7-day cash-flow projection from saved PocketLedger statements."""

from typing import Any

from ledger_core import _money, _plain, to_float


def linear_forecast(values: list[float], steps: int) -> list[float]:
    count = len(values)
    if steps <= 0:
        return []
    if count == 0:
        return [0.0] * steps
    if count == 1:
        return [max(0.0, values[0])] * steps
    xs = list(range(count))
    mean_x = sum(xs) / count
    mean_y = sum(values) / count
    var_x = sum((x - mean_x) ** 2 for x in xs)
    slope = 0.0 if var_x == 0 else sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values)) / var_x
    intercept = mean_y - slope * mean_x
    return [round(max(0.0, intercept + slope * (count - 1 + step)), 2) for step in range(1, steps + 1)]


def project_ledger_history(ledgers: list[dict[str, Any]], horizon: int = 7) -> list[dict[str, Any]]:
    labels: list[str] = []
    revenues: list[float] = []
    cash: list[float] = []
    credit: list[float] = []
    kinds: list[str] = []
    for index, ledger in enumerate(ledgers, start=1):
        date_label = _plain(ledger.get("date")) or _plain(ledger.get("processed_at"))[:10] or f"Ledger {index}"
        labels.append(f"{index}. {date_label}")
        revenues.append(to_float(ledger.get("total_revenue_usd")))
        cash.append(to_float(ledger.get("total_cash_usd")))
        credit.append(to_float(ledger.get("total_credit_outstanding_usd")))
        kinds.append("Recorded")
    forecast = zip(
        linear_forecast(revenues, horizon),
        linear_forecast(cash, horizon),
        linear_forecast(credit, horizon),
    )
    for step, (rev, cas, cred) in enumerate(forecast, start=1):
        labels.append(f"Day +{step}")
        revenues.append(rev)
        cash.append(cas)
        credit.append(cred)
        kinds.append("Projected")
    return [
        {"Period": label, "Revenue": rev, "Cash": cas, "Credit": cred, "Kind": kind}
        for label, rev, cas, cred, kind in zip(labels, revenues, cash, credit, kinds)
    ]


def projection_headline(rows: list[dict[str, Any]]) -> tuple[float, float, float]:
    projected = [row for row in rows if row.get("Kind") == "Projected"]
    week_revenue = sum(float(row["Revenue"]) for row in projected)
    week_cash = sum(float(row["Cash"]) for row in projected)
    next_credit = float(projected[0]["Credit"]) if projected else 0.0
    return week_revenue, week_cash, next_credit


def projection_local_summaries(week_revenue: float, week_cash: float, next_credit: float) -> dict[str, str]:
    return {
        "English": (
            f"If this pattern continues, the next 7 days may bring about {_money(week_revenue)} in sales "
            f"and {_money(week_cash)} in cash. Outstanding credit could sit near {_money(next_credit)}."
        ),
        "ChiShona": (
            f"Kana zikaramba zvakadai, mazuva manomwe anotevera unogona kuwana mari yekutengesa inosvika {_money(week_revenue)} "
            f"uye cash inosvika {_money(week_cash)}. Chikwereti chingasara chiri pedyo ne {_money(next_credit)}."
        ),
        "IsiNdebele": (
            f"Uma kuqhubeka kanje, ezinsukwini eziyisikhombisa ezizayo ungathola imali yokuthengisa efika ku {_money(week_revenue)} "
            f"kanye nemali ekhokhiwe efika ku {_money(week_cash)}. Isikwelete singahlala eduze kwe {_money(next_credit)}."
        ),
    }
