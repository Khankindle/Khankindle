# PocketLedger — Product & Technical Specification

Status: **Draft v2** (post-hackathon) · Replaces `project.md` (hackathon-day master document, kept on tag `hackathon-submission-2026-09-19` in `fabber04/czi-hackathon`).

This spec covers what PocketLedger does **today** (§1–§6) and the **Business Health Score** (§7). The scoring engine is implemented in `health_score.py` with tests in `tests/test_health_score.py`; showing it in the UI, PDF, and API (§7.7) is still to do. The health score design is based on research into how Moniepoint judges small businesses for working-capital loans (§11).

---

## 1. Problem and users

- **Problem.** Informal traders in Zimbabwe record daily sales and *chikwereti* (customer credit) in paper notebooks. Without organised records they cannot show their cash flow to a micro-lender.
- **Primary user.** Market vendors, tuckshop operators, fresh-produce sellers and similar micro-entrepreneurs, who often speak English, ChiShona, IsiNdebele, or a mix.
- **Secondary user (read-only).** A micro-finance officer who receives the PDF certificate from the trader.
- **Outcome.** A trader can turn notebook pages or a spoken statement into a verified statement, a 7-day cash-flow projection, and a **financial health certificate** they can share.

## 2. Scope

| In scope (v2) | Out of scope |
| --- | --- |
| Photo and voice capture, Gemini extraction, cash/credit/expense split | Loan decisions, loan offers, or acting as a lender |
| Trader profile and saved ledger history (local JSON store) | Tax filing, IT or tax audits, certified accounts |
| 7-day projection, bilingual summaries, PDF certificate | Credit bureau checks or KYC verification |
| Android capture app via local extract API | Storing images or audio after processing |
| **Business Health Score (§7)** | Selling or sharing data with third parties |

## 3. System overview

```
Android app (mobile/) ──photo──▶ extract_server.py :8765 /api/extract ─┐
                                                                      ├─▶ ledger_core.extract_ledger ─▶ Gemini (vision/audio)
Streamlit app (app.py) ──photo / voice─────────────────────────────────┘                │
        │                                                                                ▼
        │◀──────────────── normalized JSON (totals recomputed in Python) ───────────────┘
        ├─▶ data/ store (profile + ledger history)
        ├─▶ projection.py      (7-day linear forecast)
        ├─▶ health_score.py    (§7 — deterministic, no LLM; UI wiring pending)
        └─▶ certificate.py     (PDF)
```

| Module | Responsibility |
| --- | --- |
| `ledger_core.py` | Prompt, Gemini call with model fallback on rate limits, JSON parsing, total recomputation, local-language fallback summaries |
| `app.py` | Streamlit UI: onboarding, Overview / Capture / Transactions / Certificate tabs, persistence |
| `projection.py` | Least-squares 7-day forecast of revenue, cash, and credit |
| `health_score.py` | Business Health Score (§7): pre-qualification, history gate, components, reasons, affordability guide |
| `certificate.py` | PDF certificate (fpdf2) |
| `extract_server.py` | JSON HTTP API for the Android app; the Gemini key stays on the laptop |
| `mobile/` | Flutter Android client |
| `test_gemini.py` | Checks the key, the model, and that the reply parses as JSON |

**Design rule: Gemini reads, Python counts.** Gemini only turns the notebook page or recording into line items and writes the narrative text. Python recomputes every total, ratio, and score. Values Gemini reports for totals are overwritten.

## 4. Extraction contract

### 4.1 Transaction record

| Field | Type | Notes |
| --- | --- | --- |
| `item` | string | Item or description as written/spoken |
| `quantity` | string | Free text (e.g. `"10kg"`, `"2x"`) |
| `amount_usd` | number | USD; non-numeric values coerce to `0.0` |
| `payment_type` | enum | `Cash` · `Credit` · `Expense` · **`Repayment` (new, §7.3)** |
| `debtor` | string | Customer name when `Credit` or `Repayment`, else `"N/A"` |
| `confidence` | number 0–1 | **New, optional.** How sure Gemini is that it read the line correctly. Lines below `0.5` are flagged for review and excluded from scoring (§7.2) |
| `confirmed` | bool | **New, optional.** Set by the app when the trader confirms a flagged line. A confirmed line skips the §7.2 flags (except *No amount* and *Not a sale*) |

### 4.2 Ledger record (one page or one voice note)

`business_name`, `date`, `transcript` (audio only), `transactions[]`, `total_revenue_usd`, `total_cash_usd`, `total_credit_outstanding_usd`, `business_health_summary`, `summary_shona`, `summary_ndebele`, plus app-set fields `business_category`, `capture_source` (`image` | `audio`), `processed_at`.

### 4.3 Totals (current behaviour, `recompute_totals`)

- `Expense` lines (and anything containing "rent") are excluded from sales.
- `Credit` / *chikwereti* lines count as outstanding credit; all other non-expense lines count as cash.
- `revenue = cash + credit`.
- `Repayment` lines are **not** counted in page sales totals. `health_score.py` counts them as **cash received** and uses them to **reduce** that debtor's outstanding balance, oldest credit first (FIFO). The Gemini prompt asks for `Repayment` when a customer pays back chikwereti.

## 5. Projection (current)

`projection.py` fits a least-squares line through the saved ledgers' revenue, cash, and credit, then extends it 7 steps. Forecasts are floored at 0. The headline shows 7-day revenue and cash, plus next-day credit. Known limitation: ledgers are indexed by position, not by calendar date, so gaps between trading days are ignored. §7.4 fixes this for scoring.

## 6. Certificate (current)

The PDF contains: business, date, category, the three totals, a transaction table, the English health summary, ChiShona and IsiNdebele summaries, and the disclaimer. §7.7 adds the health score block.

---

## 7. Business Health Score (new)

### 7.1 Goals and principles

Taken from how Moniepoint scores merchants (§11), adapted for paper-ledger data:

1. **Cash-flow based, not collateral based.** The score uses only what the trader records: sales, cash, credit, expenses, and repayments.
2. **Clean the data before scoring.** Moniepoint separates a business's real transactions from one-off or personal ones and drops outliers before judging business health. PocketLedger does the same (§7.2).
3. **Require enough history.** Moniepoint needs weeks of steady account use before offering credit. PocketLedger shows a *Provisional* score until there is enough history (§7.4).
4. **Size credit to the business, not to the request.** Moniepoint caps limits to avoid over-leveraging a business. PocketLedger's affordability guide follows the same rule (§7.6).
5. **Deterministic and explainable.** The score is a published, rule-based weighted index computed in Python. It is **not** a machine-learning model and **not** a probability of default. Each score shows its top reasons and next steps in the trader's language.
6. **Honest about evidence.** Moniepoint scores transactions its own systems captured. PocketLedger reads self-reported notebooks, so every certificate states how strong its evidence is (§7.5).

### 7.2 Step 1 — Pre-qualification (data cleaning)

Run over all saved ledgers in the scoring window (default **last 56 days**). Excluded lines stay visible on the Transactions tab with a reason, and are counted in the certificate's *Excluded entries* line.

| Rule | Flag when | Reason shown |
| --- | --- | --- |
| Outlier sale | A single line > **5×** the trader's median line amount **and** > **2×** their median daily revenue (needs ≥ 10 prior lines) | "Unusually large sale" |
| Repeated entry | Same item, amount, and debtor appears **≥ 3 times** on one page | "Possible duplicate" |
| Duplicate capture | Same page/voice note captured twice (same date and identical transaction set) | "Already saved" |
| Low confidence | `confidence < 0.5` | "Hard to read — please confirm" |
| Zero / missing amount | `amount_usd <= 0` | "No amount" |
| Non-business | Personal transfers, loans received, owner top-ups | "Not a sale" |

When the trader confirms a flagged line on the Transactions tab (`confirmed: true`), it is counted again.

Implementation notes: rules run in date order over **all** saved history, so the outlier medians only use earlier data. For *Repeated entry* the first occurrence is kept and the rest are excluded. Pages with no readable date and no `processed_at` are excluded with the reason "No date on this page".

### 7.3 Inputs derived per trading day

For each calendar date *d* in the window (several ledgers on the same date are merged):

- `sales_d = cash_sales_d + credit_sales_d`
- `cash_in_d = cash_sales_d + repayments_d`
- `expenses_d`
- `net_cash_d = cash_in_d − expenses_d`
- `credit_book` = running outstanding credit per debtor (new credit − repayments). Each open balance keeps the date it started, for ageing.

### 7.4 Step 2 — History gate

| Status | Condition | Display |
| --- | --- | --- |
| **Not enough data** | < 5 trading days recorded | No score. Show "Record N more days to get your score." |
| **Provisional** | ≥ 5 trading days but < 14 trading days **or** span < 42 days (6 weeks) | Score shown with "Provisional" badge; affordability guide hidden |
| **Established** | ≥ 14 trading days spanning ≥ 42 days | Full score and affordability guide |

The 6-week threshold follows the minimum account-activity period widely reported for Moniepoint business loans (§11).

*Span* = days from the first recorded date in the window to `as_of`, inclusive. `as_of` defaults to the latest ledger date so the function stays pure. **The app must pass today's date** so that recent days without records count against C1.

### 7.5 Step 3 — Component scores

Each component is normalised to 0–100 using piecewise-linear interpolation between the anchor points shown. Values outside the anchors are clamped.

| # | Component | Weight | Metric | 0 pts | 50 pts | 100 pts |
| --- | --- | --- | --- | --- | --- | --- |
| C1 | **Recording consistency** | 25 | `active_ratio` = trading days recorded ÷ expected trading days (expected = 6 per week unless the trader sets otherwise) | ≤ 0.20 | 0.50 | ≥ 0.85 |
| C2 | **Sales stability** | 15 | Coefficient of variation of `sales_d` (std ÷ mean) | ≥ 1.20 | 0.60 | ≤ 0.25 |
| C3 | **Cash conversion** | 20 | `Σcash_in ÷ Σsales` | ≤ 0.40 | 0.70 | ≥ 0.90 |
| C4 | **Credit (chikwereti) health** | 25 | Sub-score, see below | — | — | — |
| C5 | **Expense coverage** | 10 | `Σcash_in ÷ Σexpenses` (100 if no expenses recorded **and** C1 ≥ 50) | ≤ 1.0 | 1.5 | ≥ 3.0 |
| C6 | **Growth trend** | 5 | Weekly sales slope ÷ mean weekly sales (least squares over the weekly totals; needs ≥ 3 weeks, else 50) | ≤ −0.15 | 0.00 | ≥ +0.10 |

**C4 Credit health** = 40% *exposure* + 30% *ageing* + 20% *collection* + 10% *concentration*:

| Sub-metric | Definition | 0 | 50 | 100 |
| --- | --- | --- | --- | --- |
| Exposure | Outstanding credit ÷ average weekly sales | ≥ 1.50 | 0.50 | ≤ 0.15 |
| Ageing | Share of outstanding credit older than 30 days | ≥ 0.50 | 0.20 | 0.00 |
| Collection | Repayments in window ÷ credit issued in window (50 if no credit issued) | ≤ 0.20 | 0.50 | ≥ 0.80 |
| Concentration | Largest single debtor's share of outstanding credit (100 if outstanding < $5) | ≥ 0.70 | 0.40 | ≤ 0.20 |

**Total:** `score = round(Σ weight_i × C_i ÷ 100)` → integer 0–100.

**Evidence level** is shown next to the score but does **not** change it:

| Level | Condition |
| --- | --- |
| Self-reported | Default |
| Captured same-day | ≥ 80% of ledgers processed within 24 h of their written date |
| Corroborated *(future)* | Totals match an uploaded mobile-money (e.g. EcoCash) or bank statement within ±10% |

### 7.6 Step 4 — Bands, reasons, and affordability guide

| Score | Band | ChiShona | IsiNdebele |
| --- | --- | --- | --- |
| 80–100 | Strong | Rakasimba | Liqinile |
| 65–79 | Good | Rakanaka | Lihle |
| 50–64 | Fair | Riri pakati | Liphakathi |
| 0–49 | Building | Richiri kuvaka | Lisakhela |

> Band names in ChiShona and IsiNdebele must be reviewed by native speakers before release.

**Reasons and next steps.** Rank components by `weight × (100 − C_i)`, which is how many points each one costs. Show the top 2 **that score below 75** as **"What is lowering your score"** with one action each, and the best component as **"Your strength"**. The 75 cut-off stops neutral defaults (no credit given → collection 50; under 3 weeks of history → growth 50) from producing advice that doesn't apply. For C4, the action targets the weakest credit sub-score; ties go to ageing, then concentration, because naming customers is the most useful advice. Example actions:

| Weak component | Action text (EN) |
| --- | --- |
| C1 | "Record every trading day, even quiet ones." |
| C3 / C4 exposure | "Collect chikwereti before giving new credit." |
| C4 ageing | "N customers owe you for more than 30 days: {names}." |
| C4 concentration | "{name} owes {pct}% of your credit. Spread your risk." |
| C5 | "Expenses are close to your cash income. Check stock costs and rent." |
| C6 | "Sales have dropped over recent weeks…" (below 50) / "Sales have been flat…" (50–74) |

Action text is English only for now. ChiShona and IsiNdebele versions will be added after native-speaker review.

**Affordability guide** (Established status only; Gemini never writes these numbers). This follows Moniepoint's rule of sizing credit so the business is not over-leveraged, and its practice of collecting repayments from daily inflows:

- `typical_net_cash` = **median** of `net_cash_d` over the window (median resists outliers).
- `safe_daily_repayment = max(0, 0.20 × typical_net_cash)`.
- `indicative_amount_30d = safe_daily_repayment × trading_days_per_week × 30 ÷ 7`. This is the maximum total repayment (principal **plus** charges) over 30 days that the trader's cash flow appears to support.
- Hide the guide if `score < 50` or `typical_net_cash <= 0`.
- Always label it: *"Guide only — not a loan offer. A lender will do its own checks."*

All thresholds in §7.2–§7.6 live in one `HEALTH_CONFIG` dict in `health_score.py`, versioned as `score_version` (start `"hs-1.0"`), so they can be retuned once real repayment outcomes exist.

### 7.7 Output contract

```json
"health": {
  "score_version": "hs-1.0",
  "status": "Established",
  "score": 72,
  "band": "Good",
  "evidence_level": "Captured same-day",
  "window": {"start": "2026-08-11", "end": "2026-10-05", "trading_days": 31},
  "components": {
    "recording_consistency": 84, "sales_stability": 61, "cash_conversion": 77,
    "credit_health": 58, "expense_coverage": 90, "growth_trend": 55
  },
  "excluded_entries": 2,
  "reasons": ["credit_health", "sales_stability"],
  "strength": "expense_coverage",
  "affordability": {"safe_daily_repayment_usd": 3.10, "indicative_amount_30d_usd": 79.71}
}
```

The implementation also returns `band_local` (band in all three languages), `credit_sub_scores`, `credit_book` (outstanding, aged, per debtor), `excluded` (each excluded line with its reason), `actions`, `metrics` (raw ratios), `record_more_days`, and `disclaimer`.

```python
from datetime import date
from health_score import compute
health = compute(saved_ledgers, profile={"trading_days_per_week": 6}, as_of=date.today())
```

- Saved alongside the ledger history and recomputed after every new capture.
- **Overview tab:** score gauge, band, status badge, component bars, reasons.
- **Certificate tab / PDF:** new "Business health score" block above the narrative: score, band, status, evidence level, window, component table, excluded entries, affordability guide (if shown), and `score_version`.
- **Gemini summary:** `business_health_summary`, `summary_shona`, and `summary_ndebele` are given the computed `health` object as context and must quote the score and band exactly. They must never produce a different number.
- **Android:** `/api/extract` response gains `health` when the server has history for that trader (future; the server is currently stateless).

### 7.8 Acceptance criteria

Status: criteria 1–4 are covered by `tests/test_health_score.py` (run `pytest` in `pocketledger/`). Criterion 5 waits on the PDF work.

1. `health_score.compute(ledgers, profile, as_of)` is a pure function with no network or LLM calls. The same input always gives the same output.
2. Unit tests (`tests/test_health_score.py`) cover: each history-gate status; each pre-qualification rule; anchor-point interpolation; a perfect trader (score ≥ 95); a trader with 80% aged credit (C4 ≤ 30); `Repayment` lines lowering outstanding credit; affordability hidden below score 50.
3. Adding a single outlier sale never raises the score by more than 2 points.
4. The five `samples/ledgers/ground_truth.json` traders, replayed as a synthetic 6-week history, produce scores that are stable across runs.
5. The PDF shows `score_version` and the disclaimer on every page that shows a score.

---

## 8. Safeguards and responsible AI

- Disclaimer on UI, PDF, and API: *AI-assisted indexing only. Not an IT audit, tax audit, or certified financial report, and not a loan decision.*
- Health score copy must say **"health score"**, never "credit score" or "approved".
- No protected attributes (gender, ethnicity, religion, age, location below city level) are used in scoring.
- Images and audio are processed in memory and are not stored. Ledger JSON stays on the device or host running the app (`data/`, git-ignored).
- The trader sees exactly what the lender sees. There is no hidden score.
- A trader can delete their history, which deletes their score.

## 9. Non-functional requirements

- Extraction under 30 s on the default model, with automatic fallback when rate-limited (`FALLBACK_MODELS`).
- Health score computed in under 100 ms for 1,000 ledgers.
- Works on Streamlit Community Cloud with only `GEMINI_API_KEY` set.
- Every user-facing string available in English, ChiShona, and IsiNdebele.

## 10. Open questions

1. Expected trading days per week by category (e.g. fresh produce at 7 days a week vs. a hardware stall). Add a profile setting?
2. ZiG vs. USD: should ledgers record currency per line and convert at capture time?
3. Partner lender pilot: collect repayment outcomes (with consent) so the `hs-1.x` weights can be checked against real data.
4. Should the extract server keep per-trader history so the Android app can show the score?

---

## 11. Research notes: how Moniepoint assesses business health

Moniepoint does **not** publish a health-score formula. The points below come from Moniepoint's own engineering blog and terms, plus widely repeated third-party guides (marked *third-party*). §7 uses the principles, not any proprietary model.

| Finding | Source | How PocketLedger uses it |
| --- | --- | --- |
| Credit decisions are based on a merchant's own transaction/POS data, used to judge cash flow, turnover, and ability to repay, instead of collateral | Moniepoint 2025 review coverage — [Innovation Village](https://innovation-village.com/moniepoint-disburses-%E2%82%A61t-to-70000-nigerian-businesses-in-2025/); [Vanguard, Jul 2026](https://www.vanguardngr.com/2026/07/moniepoint-reaches-20m-users-disburses-700m-in-msme-loans/) | Cash-flow-only inputs (§7.3) |
| A **pre-qualification** step separates real business transactions from one-off or personal ones to understand "the business's health and how well it's growing". Outliers (e.g. a ₦5M "sale" at a petrol station) and repeated identical payments from one person are flagged and excluded | [Moniepoint blog — *Making the dream: working capital loans* (2023)](https://moniepoint.com/blog/making-the-dream-powering-businesses-through-working-capital-loans) | Pre-qualification rules (§7.2) |
| Loans are sized to the business's scale to avoid over-leveraging, which leads to default and damages the business's credit profile | Same Moniepoint blog post | Affordability guide capped at 20% of median net cash (§7.6) |
| Eligibility combines KYC verification, credit-bureau data, and transaction history into a credit profile. Field verification uses geotagging and facial recognition | Same Moniepoint blog post | Out of scope for us. Replaced by the *evidence level* label (§7.5) |
| Moniepoint uses automated credit-risk assessment and profiling of personal, financial, account, and credit information | [Moniepoint NG Terms & Conditions](https://moniepoint.com/ng/terms-and-conditions) | Transparent, explainable rules instead of a black box (§7.1) |
| Personal loans need ≥ 6 months of consistent account use. Rejections cite credit history, outstanding loans, or **inconsistent account activity** | [Moniepoint Knowledge Base — Personal Loans](https://support.moniepoint.com/topics/personal-loans-276) | Recording consistency is the largest component (C1, 25%) |
| *Third-party:* business loans need ~6 weeks of steady business-account activity. Factors include daily transaction volume, cash flow, transfer frequency, POS usage, balance patterns, and past repayment | [Polytechnic.com.ng](https://polytechnic.com.ng/moniepoint-business-loan/); [Pulse.ng](https://www.pulse.ng/story/moniepoint-vs-carbon-2025062820012078445) | 6-week *Established* gate (§7.4); C1, C2, C5 |
| *Third-party:* repayments are deducted automatically from daily inflows, and on-time repayment raises future limits | [PosMachineNG](https://posmachineng.com/how-to-get-a-moniepoint-business-loan-in-nigeria/) | Daily-repayment framing of affordability (§7.6). Repayment history is a future component once loans exist |
| Moniebook (Moniepoint's bookkeeping/POS app) tracks credit sales with outstanding balances, due dates, and per-customer invoices | [Moniebook Register — App Store](https://apps.apple.com/gb/app/moniebook-register/id6749378354) | Per-debtor credit book with ageing (§7.3, C4) |

**Key difference.** Moniepoint's data is captured by its own systems at the moment of payment, so it is hard to fake. PocketLedger's data is self-reported on paper. That is why §7 adds duplicate and outlier checks, an evidence level, and a strict "not a loan decision" position, and why mobile-money corroboration is the most valuable next step.
