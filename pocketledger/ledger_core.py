import json
import os
from typing import Any

from google import genai

MODEL_NAME = "gemini-3.6-flash"
FALLBACK_MODELS = (
    "gemini-3.5-flash",
    "gemini-2.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash-lite",
)


def extraction_prompt(business_name: str, category: str, source: str = "image") -> str:
    context_lines = []
    if category:
        context_lines.append(f"The trader selected this business category: {category}.")
    if business_name:
        context_lines.append(
            f"The onboarded business name is: {business_name}. "
            "Use it unless the recording or page clearly shows a different name."
        )
    context = " ".join(context_lines)
    if source == "audio":
        analyze = (
            "Listen to the trader dictating their day's sales, cash, chikwereti (credit), "
            "and expenses. They may speak English, ChiShona, IsiNdebele, or a mix."
        )
        invent_rule = (
            "- Do not invent line items that were not spoken. "
            "If an amount is unclear, omit that line rather than guessing."
        )
        transcript_key = '  "transcript": "Near-verbatim transcription of the spoken statement",\n'
    else:
        analyze = "Analyze the provided image of a handwritten ledger or receipt page."
        invent_rule = "- Do not invent line items that are not visible."
        transcript_key = ""
    return f"""
You are PocketLedger AI, a financial indexing assistant for informal market traders in Zimbabwe.
{context}
{analyze}
Extract the financial data and return a strictly structured JSON object with the following keys:
{{
  "business_name": "Name of business or 'Unspecified'",
  "date": "Date of entry or 'Unspecified'",
{transcript_key}  "transactions": [
    {{"item": "item name", "quantity": "qty", "amount_usd": 0.00, "payment_type": "Cash or Credit", "debtor": "person name if credit or N/A"}}
  ],
  "total_revenue_usd": 0.00,
  "total_cash_usd": 0.00,
  "total_credit_outstanding_usd": 0.00,
  "business_health_summary": "2-sentence summary of cash flow and credit risk, considering the business category.",
  "summary_shona": "2 short sentences in simple everyday ChiShona. Use words like mari, cash, chikwereti. Include the USD amounts.",
  "summary_ndebele": "2 short sentences in simple everyday IsiNdebele. Use words like imali, cash, isikwelete. Include the USD amounts."
}}
Rules:
- Treat Credit / chikwereti / named debtors as outstanding credit, not cash.
- Amounts are in USD.
- Paid rent and similar operating costs are expenses, not sales. Put them in transactions with payment_type "Expense" so they are excluded from cash and credit sales totals.
- Interpret items in the context of the selected business category.
- Write summary_shona and summary_ndebele in spoken market language, not formal or literary style.
{invent_rule}
- Do not include markdown code fences. Return pure JSON text only.
"""


def parse_json_payload(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("Gemini did not return JSON.")
    return json.loads(cleaned[start : end + 1])


def to_float(value: Any) -> float:
    try:
        return float(str(value).replace("$", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return 0.0


def recompute_totals(transactions: list[dict[str, Any]]) -> tuple[float, float, float]:
    cash = 0.0
    credit = 0.0
    for row in transactions:
        amount = to_float(row.get("amount_usd"))
        payment = str(row.get("payment_type") or "").lower()
        if "expense" in payment or "rent" in payment:
            continue
        if "credit" in payment or "chikwereti" in payment:
            credit += amount
        else:
            cash += amount
    return cash + credit, cash, credit


def _plain(value: Any) -> str:
    return "" if value is None else str(value).replace("\x00", "").strip()


def _money(value: Any) -> str:
    return f"${to_float(value):,.2f}"


def local_language_summaries(result: dict[str, Any]) -> dict[str, str]:
    revenue = _money(result.get("total_revenue_usd"))
    cash = _money(result.get("total_cash_usd"))
    credit = _money(result.get("total_credit_outstanding_usd"))
    cash_val = to_float(result.get("total_cash_usd"))
    credit_val = to_float(result.get("total_credit_outstanding_usd"))

    shona = (
        f"Bhizinesi rako nhasi rakawana mari inosvika {revenue}. "
        f"Yakabhadharwa cash ndeye {cash}. "
        f"Chikwereti chakasara, vanhu vasina kubhadhara, ndeche {credit}."
    )
    if credit_val > cash_val:
        shona += " Chikwereti chakawanda kupfuura cash, saka tsvaka vanhu vabhadhare kuti bhizinesi rifambe."
    elif credit_val > 0:
        shona += " Rangarira kutevera vanhu vane chikwereti."
    else:
        shona += " Hapana chikwereti chakakura nhasi."

    ndebele = (
        f"Ibizinisi lakho namhlanje lithole imali efika ku {revenue}. "
        f"Imali ekhokhiwe ngokheshi ngu {cash}. "
        f"Isikwelete esisele, abantu abangakhokhanga, ngu {credit}."
    )
    if credit_val > cash_val:
        ndebele += " Isikwelete sikhulu kunemali ekhokhiwe, ngakho cela ukuthi bakhokhe ukuze ibhizinisi liqhubeke."
    elif credit_val > 0:
        ndebele += " Khumbula ukulandela abantu abakweletayo."
    else:
        ndebele += " Asikho isikwelete esikhulu namhlanje."

    return {"summary_shona": shona, "summary_ndebele": ndebele}


def attach_local_summaries(result: dict[str, Any]) -> dict[str, Any]:
    fallback = local_language_summaries(result)
    shona = _plain(result.get("summary_shona"))
    ndebele = _plain(result.get("summary_ndebele"))
    result["summary_shona"] = shona if len(shona) > 20 else fallback["summary_shona"]
    result["summary_ndebele"] = ndebele if len(ndebele) > 20 else fallback["summary_ndebele"]
    return result


def normalize_extraction(
    data: dict[str, Any],
    capture_source: str,
    business_name: str = "",
    category: str = "",
) -> dict[str, Any]:
    transactions = data.get("transactions") or []
    revenue, cash, credit = recompute_totals(transactions)
    data["transactions"] = transactions
    data["total_revenue_usd"] = round(revenue, 2)
    data["total_cash_usd"] = round(cash, 2)
    data["total_credit_outstanding_usd"] = round(credit, 2)
    data["business_category"] = category
    data["capture_source"] = capture_source
    extracted_name = _plain(data.get("business_name"))
    if business_name and (not extracted_name or extracted_name == "Unspecified"):
        data["business_name"] = business_name
    attach_local_summaries(data)
    data["transcript"] = _plain(data.get("transcript"))
    data["business_health_summary"] = _plain(data.get("business_health_summary"))
    return data


def gemini_client(api_key: str) -> Any:
    return genai.Client(api_key=api_key, http_options={"timeout": 180_000})


def model_candidates() -> list[str]:
    primary = (os.environ.get("GEMINI_MODEL") or MODEL_NAME).strip() or MODEL_NAME
    ordered: list[str] = []
    seen: set[str] = set()
    for name in (primary, *FALLBACK_MODELS):
        if name and name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered


def is_rate_limit_error(error: BaseException) -> bool:
    text = str(error).lower()
    return any(
        token in text
        for token in ("429", "too_many_requests", "rate limit", "resource_exhausted")
    )


def friendly_gemini_error(error: BaseException) -> str:
    if is_rate_limit_error(error):
        return (
            "Gemini Free Tier quota is used up for the models we tried "
            f"({', '.join(model_candidates())}). "
            "Wait for the daily reset, set GEMINI_MODEL in .env to a model that still "
            "has quota, or add billing at https://ai.dev/rate-limit."
        )
    text = str(error)
    if "503" in text or "overloaded" in text.lower():
        return "Gemini is experiencing high demand (503). Wait a moment and try again."
    return text


def _create_interaction(client: Any, model: str, prompt: str, media: dict[str, Any]) -> Any:
    payload = {
        "model": model,
        "input": [{"type": "text", "text": prompt}, media],
        "timeout": 180,
    }
    try:
        return client.interactions.create(
            **payload,
            generation_config={"thinking_level": "minimal"},
        )
    except Exception as error:
        if is_rate_limit_error(error):
            raise
        message = str(error).lower()
        if "thinking_level" in message or "generation_config" in message:
            return client.interactions.create(**payload)
        raise


def run_gemini_extraction(client: Any, prompt: str, media: dict[str, Any]) -> dict[str, Any]:
    last_error: BaseException | None = None
    candidates = model_candidates()
    for model in candidates:
        try:
            interaction = _create_interaction(client, model, prompt, media)
            text = interaction.output_text or ""
            if not text.strip():
                raise ValueError("Gemini returned an empty response.")
            if model != candidates[0]:
                print(f"Used fallback model {model} after a rate limit.")
            return parse_json_payload(text)
        except Exception as error:
            last_error = error
            if is_rate_limit_error(error):
                print(f"Rate limited on {model}; trying another Gemini model.")
                continue
            raise
    raise RuntimeError(friendly_gemini_error(last_error or RuntimeError("Gemini request failed.")))


def extract_ledger(
    *,
    source: str,
    mime_type: str,
    data_b64: str,
    business_name: str = "",
    category: str = "",
    api_key: str | None = None,
) -> dict[str, Any]:
    key = (api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY is missing. Add it to the .env file.")
    media_type = "audio" if source == "audio" else "image"
    media = {"type": media_type, "data": data_b64, "mime_type": mime_type}
    data = run_gemini_extraction(
        gemini_client(key),
        extraction_prompt(business_name, category, source=media_type),
        media,
    )
    return normalize_extraction(data, media_type, business_name, category)
