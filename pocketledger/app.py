import base64
import io
import json
import os
import re
from datetime import date as calendar_date
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from google import genai
from PIL import Image, ImageDraw, ImageOps

from certificate import build_statement_pdf, statement_pdf_filename
from ledger_core import (
    _money,
    _plain,
    attach_local_summaries,
    extraction_prompt,
    friendly_gemini_error,
    is_rate_limit_error,
    normalize_extraction,
    run_gemini_extraction,
    to_float,
)
from health_score import COMPONENT_LABELS, HEALTH_CONFIG, STATUS_NOTES
from health_score import compute as compute_health
from projection import project_ledger_history, projection_headline, projection_local_summaries

load_dotenv()

BUSINESS_CATEGORIES = [
    "Tuckshop / grocery",
    "Fresh produce / market stall",
    "Clothing and textiles",
    "Fast food / kitchen",
    "Hair and beauty",
    "Airtime, phones, and electronics",
    "Hardware and building supplies",
    "Agriculture and livestock",
    "Transport and logistics",
    "Repairs and other services",
    "Cross-border trading",
    "Other",
]


MAX_LEDGER_SIDE = 1024
JPEG_QUALITY = 70


def format_bytes(size: int) -> str:
    if size < 1024 * 1024:
        return f"{max(1, round(size / 1024))} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def prepare_ledger_image(image: Image.Image) -> Image.Image:
    rgb = ImageOps.exif_transpose(image).convert("RGB")
    width, height = rgb.size
    longest = max(width, height)
    if longest <= MAX_LEDGER_SIDE:
        return rgb
    scale = MAX_LEDGER_SIDE / longest
    return rgb.resize(
        (max(1, int(width * scale)), max(1, int(height * scale))),
        Image.Resampling.LANCZOS,
    )


def encode_ledger_jpeg(image: Image.Image, quality: int = JPEG_QUALITY) -> bytes:
    buffer = io.BytesIO()
    prepare_ledger_image(image).save(
        buffer, format="JPEG", quality=quality, optimize=True
    )
    return buffer.getvalue()


def bytes_to_b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def audio_mime_for(filename: str, reported: str | None) -> str:
    reported = (reported or "").lower()
    name = (filename or "").lower()
    if "mpeg" in reported or name.endswith(".mp3"):
        return "audio/mp3"
    if "m4a" in reported or name.endswith(".m4a") or "mp4" in reported:
        return "audio/m4a"
    if "webm" in reported or name.endswith(".webm"):
        return "audio/webm"
    if "ogg" in reported or name.endswith(".ogg"):
        return "audio/ogg"
    return "audio/wav"


def apply_extraction_result(data: dict[str, Any], capture_source: str) -> dict[str, Any]:
    return normalize_extraction(
        data,
        capture_source,
        st.session_state.business_name,
        st.session_state.business_category,
    )


def extract_structured_ledger(
    client: Any,
    prompt: str,
    media: dict[str, Any],
    *,
    spinner: str,
    capture_source: str,
) -> None:
    with st.spinner(spinner):
        try:
            data = run_gemini_extraction(client, prompt, media)
            st.session_state.result = apply_extraction_result(data, capture_source)
            persist_ledger(st.session_state.result)
            st.session_state.processed_capture_id = (
                st.session_state.ledger_audio_id
                if capture_source == "audio"
                else st.session_state.ledger_file_id
            )
            st.toast("Ledger saved to this trader's history.", icon=":material/check_circle:")
        except Exception as error:
            message = friendly_gemini_error(error)
            if is_rate_limit_error(error) or "quota" in message.lower():
                st.error(message)
            elif "503" in message or "overloaded" in message.lower():
                st.error(message)
            else:
                st.error(f"Error processing the statement: {message}")



DATA_DIR = Path(os.environ.get("POCKETLEDGER_DATA_DIR") or Path(__file__).resolve().parent / "data")
STORE_PATH = DATA_DIR / "ledger_store.json"


def user_id_for(name: str, category: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", f"{name}_{category}".lower()).strip("_")
    return slug or "unnamed_trader"


def load_store() -> dict[str, Any]:
    if STORE_PATH.exists():
        try:
            return json.loads(STORE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"users": {}, "last_user_id": None}
    return {"users": {}, "last_user_id": None}


def save_store(store: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STORE_PATH.write_text(json.dumps(store, indent=2), encoding="utf-8")


def persist_user_profile() -> None:
    store = load_store()
    uid = st.session_state.user_id
    users = store.setdefault("users", {})
    profile = users.setdefault(uid, {"ledgers": []})
    profile["business_name"] = st.session_state.business_name
    profile["business_category"] = st.session_state.business_category
    store["last_user_id"] = uid
    save_store(store)


def persist_ledger(result: dict[str, Any]) -> None:
    snapshot = {
        "processed_at": datetime.now().isoformat(timespec="seconds"),
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
    store = load_store()
    uid = st.session_state.user_id
    users = store.setdefault("users", {})
    profile = users.setdefault(
        uid,
        {
            "business_name": st.session_state.business_name,
            "business_category": st.session_state.business_category,
            "ledgers": [],
        },
    )
    profile.setdefault("ledgers", []).append(snapshot)
    store["last_user_id"] = uid
    save_store(store)
    st.session_state.saved_ledgers = profile["ledgers"]


def latest_statement(ledgers: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not ledgers:
        return None
    latest = dict(ledgers[-1])
    latest["transactions"] = [dict(row) for row in (latest.get("transactions") or [])]
    return latest


def restore_last_user() -> None:
    if st.session_state.onboarded:
        return
    store = load_store()
    uid = store.get("last_user_id")
    users = store.get("users") or {}
    profile = users.get(uid) if uid else None
    if not profile:
        return
    st.session_state.onboarded = True
    st.session_state.user_id = uid
    st.session_state.business_name = profile.get("business_name") or ""
    st.session_state.business_category = profile.get("business_category") or ""
    st.session_state.saved_ledgers = profile.get("ledgers") or []
    st.session_state.result = latest_statement(st.session_state.saved_ledgers)


def payment_mix_df(transactions: list[dict[str, Any]]) -> pd.DataFrame:
    if not transactions:
        return pd.DataFrame()
    rows = pd.DataFrame(transactions)
    if "payment_type" not in rows.columns:
        rows["payment_type"] = "Unspecified"
    rows["Amount"] = rows["amount_usd"].map(to_float) if "amount_usd" in rows.columns else 0.0
    mix = (
        rows.assign(**{"Payment type": rows["payment_type"].fillna("Unspecified").astype(str)})
        .groupby("Payment type", dropna=False)["Amount"]
        .sum()
        .reset_index()
    )
    return mix[mix["Amount"] != 0]


def item_amount_df(transactions: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for row in transactions:
        amount = to_float(row.get("amount_usd"))
        if amount == 0:
            continue
        rows.append({"Item": _plain(row.get("item")) or "Unspecified", "Amount": amount})
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).groupby("Item", as_index=False)["Amount"].sum().sort_values("Amount", ascending=False)



def brand_mark() -> Image.Image:
    img = Image.new("RGBA", (192, 192), (15, 42, 61, 255))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((18, 18, 174, 174), radius=40, fill=(11, 110, 79, 255))
    draw.rectangle((50, 56, 142, 68), fill=(244, 247, 250, 255))
    draw.rectangle((50, 86, 142, 98), fill=(244, 247, 250, 210))
    draw.rectangle((50, 116, 108, 128), fill=(244, 247, 250, 170))
    return img


def current_summary_language() -> str:
    return st.session_state.get("summary_language") or "ChiShona"


st.set_page_config(
    page_title="PocketLedger",
    page_icon=":material/menu_book:",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.session_state.setdefault("ledger_image", None)
st.session_state.setdefault("ledger_jpeg", None)
st.session_state.setdefault("ledger_file_id", "")
st.session_state.setdefault("ledger_caption", "")
st.session_state.setdefault("ledger_audio", None)
st.session_state.setdefault("ledger_audio_mime", "audio/wav")
st.session_state.setdefault("ledger_audio_id", "")
st.session_state.setdefault("processed_capture_id", "")
st.session_state.setdefault("result", None)
st.session_state.setdefault("onboarded", False)
st.session_state.setdefault("business_name", "")
st.session_state.setdefault("business_category", "")
st.session_state.setdefault("user_id", "")
st.session_state.setdefault("saved_ledgers", [])
restore_last_user()


@st.cache_resource
def get_gemini_client(api_key: str):
    return genai.Client(
        api_key=api_key,
        http_options={"timeout": 180_000},
    )


def resolve_api_key() -> str:
    env_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if env_key:
        return env_key
    try:
        return str(st.secrets["GEMINI_API_KEY"]).strip()
    except Exception:
        return ""


BAND_COLORS = {"Strong": "green", "Good": "blue", "Fair": "orange", "Building": "red"}
STATUS_ICONS = {
    "Established": ":material/verified:",
    "Provisional": ":material/hourglass_top:",
    "Not enough data": ":material/pending:",
}


def current_health() -> dict[str, Any] | None:
    """Business health score over all saved ledgers (SPEC.md §7). Today's date is passed so that
    recent days without records count against recording consistency."""
    ledgers = st.session_state.saved_ledgers
    if not ledgers:
        return None
    return compute_health(
        ledgers,
        profile={"trading_days_per_week": HEALTH_CONFIG["default_trading_days_per_week"]},
        as_of=calendar_date.today(),
    )


def render_health_section(health: dict[str, Any], language: str) -> None:
    st.subheader("Business health score")
    window = health.get("window") or {}
    status = health.get("status") or "Not enough data"
    score = health.get("score")

    if score is None:
        days = window.get("trading_days", 0) if window else 0
        needed = HEALTH_CONFIG["min_days_for_score"]
        st.info(
            f"Record {health.get('record_more_days', needed)} more trading day(s) to get your score.",
            icon=":material/pending:",
        )
        st.progress(min(1.0, days / needed), text=f"{days} of {needed} trading days recorded")
        return

    band = health.get("band") or ""
    band_local = (health.get("band_local") or {}).get(language) or band
    left, middle, right = st.columns((1, 1, 2))
    left.metric("Health score", f"{score}/100", border=True)
    middle.metric("Band", band_local if language == "English" else f"{band_local} ({band})", border=True)
    with right:
        with st.container(horizontal=True):
            st.badge(status, icon=STATUS_ICONS.get(status), color="green" if status == "Established" else "orange")
            st.badge(health.get("evidence_level") or "Self-reported", icon=":material/fact_check:", color="gray")
            st.badge(band, color=BAND_COLORS.get(band, "gray"))
        st.caption(
            f"{STATUS_NOTES.get(status, '')} Window {window.get('start')} to {window.get('end')}, "
            f"{window.get('trading_days')} trading days."
        )

    components = health.get("components") or {}
    weights = HEALTH_CONFIG["weights"]
    comp_left, comp_right = st.columns(2)
    for index, (key, weight) in enumerate(weights.items()):
        value = int(components.get(key, 0))
        column = comp_left if index % 2 == 0 else comp_right
        column.progress(value / 100, text=f"{COMPONENT_LABELS[key]} · {value}/100 · weight {weight}%")

    reasons_col, guide_col = st.columns(2)
    with reasons_col:
        actions = health.get("actions") or []
        if actions:
            st.markdown("**What is lowering your score**")
            for action in actions:
                st.markdown(f"- **{COMPONENT_LABELS.get(action['component'], action['component'])}:** {action['English']}")
        strength = health.get("strength")
        if strength:
            st.markdown(f"**Your strength:** {COMPONENT_LABELS.get(strength, strength)}")
    with guide_col:
        affordability = health.get("affordability")
        st.markdown("**Affordability guide**")
        if affordability:
            g1, g2 = st.columns(2)
            g1.metric("Safe daily repayment", affordability["safe_daily_repayment_usd"], format="dollar", border=True)
            g2.metric("30-day total", affordability["indicative_amount_30d_usd"], format="dollar", border=True)
            st.caption(affordability.get("note", ""))
        else:
            st.caption(
                "Shown once the score is Established, 50 or more, and daily net cash is positive."
            )

    book = health.get("credit_book") or {}
    excluded = health.get("excluded") or []
    if book.get("by_debtor") or excluded:
        with st.expander("Credit book and excluded entries", icon=":material/receipt_long:"):
            if book.get("by_debtor"):
                st.caption(
                    f"Outstanding {_money(book.get('outstanding_usd'))}, "
                    f"of which {_money(book.get('aged_over_30_days_usd'))} is older than 30 days."
                )
                st.dataframe(
                    pd.DataFrame(
                        [{"Debtor": name, "Owes (USD)": amount} for name, amount in book["by_debtor"].items()]
                    ),
                    hide_index=True,
                    column_config={"Owes (USD)": st.column_config.NumberColumn(format="dollar")},
                )
            if excluded:
                st.caption(f"{len(excluded)} entr{'y' if len(excluded) == 1 else 'ies'} left out of the score.")
                st.dataframe(
                    pd.DataFrame(excluded).rename(
                        columns={"date": "Date", "item": "Item", "amount_usd": "Amount (USD)", "reason": "Reason"}
                    ),
                    hide_index=True,
                    column_config={"Amount (USD)": st.column_config.NumberColumn(format="dollar")},
                )
    st.caption(
        f"Rule-based health score ({health.get('score_version')}) from all saved pages. "
        "Not a credit score and not a loan decision."
    )


DISCLAIMER = (
    "PocketLedger is AI-assisted indexing of a notebook or spoken statement. "
    "It is not an IT audit, tax audit, or certified financial report, and it is not a loan decision. "
    "ChiShona: Haisi IT audit, tax audit, kana report yepamutemo. "
    "IsiNdebele: Akusiyo i-IT audit, i-tax audit, noma umbiko wezimali oqinisekisiwe."
)


st.logo(brand_mark(), size="large")
st.html(
    """
    <style>
      .stApp { background: #f8f8f7; }
      [data-testid="stHeader"] { background: #f8f8f7; }
    </style>
    """
)
with st.sidebar:
    st.header("PocketLedger")
    st.caption("Cash versus chikwereti for informal traders.")
    api_key = resolve_api_key()
    if api_key:
        st.badge("Gemini ready", icon=":material/check_circle:", color="green")
    else:
        api_key = st.text_input(
            "Gemini API key",
            type="password",
            help="Add GEMINI_API_KEY to a local .env file so you only set it once.",
        )
        st.caption("[Get an API key](https://aistudio.google.com/api-keys)")
    if st.session_state.onboarded:
        st.subheader("Business", divider="gray")
        st.markdown(f"**{st.session_state.business_name or 'Unnamed business'}**")
        st.selectbox(
            "Category",
            BUSINESS_CATEGORIES,
            placeholder="Choose a category",
            key="business_category",
            help="Used on the certificate and to give Gemini the right trade context.",
        )
        persist_user_profile()
        st.metric("Saved statements", len(st.session_state.saved_ledgers), border=True)
        st.selectbox(
            "Summary language",
            ["ChiShona", "IsiNdebele", "English"],
            key="summary_language",
            persist_state="session",
        )
        st.subheader("Chikwereti")
        credit_rows = [
            row
            for row in ((st.session_state.result or {}).get("transactions") or [])
            if "credit" in str(row.get("payment_type") or "").lower()
            and row.get("debtor") not in (None, "", "N/A")
        ]
        if credit_rows:
            for row in credit_rows:
                st.caption(f"{row.get('debtor')}  ·  {_money(row.get('amount_usd'))}")
        else:
            st.caption("No outstanding credit yet. Process a ledger to list debtors here.")
    with st.expander("Responsible AI", icon=":material/shield:"):
        st.caption(DISCLAIMER)

if not st.session_state.onboarded:
    left, mid, right = st.columns((1, 1.3, 1), gap="large")
    with mid:
        st.title("Set up your business")
        st.caption("Choose the trade that matches this ledger. That category stays on the certificate.")
        with st.form("onboarding", border=True):
            st.text_input(
                "Business name",
                placeholder="e.g. Gogo Chipo fresh produce",
                key="onboard_business_name",
            )
            st.selectbox(
                "Business category",
                BUSINESS_CATEGORIES,
                index=None,
                placeholder="Choose a category",
                key="onboard_category",
                help="This stays on the financial certificate and helps Gemini read the ledger in context.",
            )
            submitted = st.form_submit_button(
                "Continue",
                type="primary",
                icon=":material/arrow_forward:",
                width="stretch",
            )
            if submitted:
                category = st.session_state.get("onboard_category")
                name = (st.session_state.get("onboard_business_name") or "").strip()
                if not category:
                    st.error("Please choose a business category from the menu.")
                else:
                    st.session_state.business_name = name
                    st.session_state.business_category = category
                    st.session_state.user_id = user_id_for(name, category)
                    st.session_state.onboarded = True
                    store = load_store()
                    existing = (store.get("users") or {}).get(st.session_state.user_id) or {}
                    st.session_state.saved_ledgers = existing.get("ledgers") or []
                    persist_user_profile()
                    st.rerun()
    st.stop()

result = st.session_state.result
summary_lang = current_summary_language()
health = current_health()
if result:
    attach_local_summaries(result)

st.title("PocketLedger")
st.caption("Turn a handwritten notebook page or a spoken statement into a cash-versus-credit certificate.")
with st.container(horizontal=True):
    if st.session_state.business_category:
        st.badge(st.session_state.business_category, icon=":material/category:", color="orange")
    st.badge(
        f"{len(st.session_state.saved_ledgers)} saved",
        icon=":material/folder:",
        color="blue",
    )

overview_tab, capture_tab, tx_tab, cert_tab = st.tabs(
    ["Overview", "Capture", "Transactions", "Certificate"]
)

with overview_tab:
    if health:
        render_health_section(health, summary_lang)
        st.divider()
    if not result:
        st.subheader("Waiting for a ledger")
        st.caption("Charts, line items, and collections appear after Gemini extracts a photo or spoken statement.")
    else:
        business = result.get("business_name", "Unspecified")
        date = result.get("date", "Unspecified")
        st.caption(f"{business} · {date}")
        c1, c2, c3, c4 = st.columns(4)
        revenue = float(result.get("total_revenue_usd") or 0)
        cash = float(result.get("total_cash_usd") or 0)
        credit = float(result.get("total_credit_outstanding_usd") or 0)
        c1.metric("Recorded revenue", revenue, border=True, format="dollar")
        c2.metric("Cash received", cash, border=True, format="dollar")
        c3.metric("Outstanding credit", credit, border=True, format="dollar")
        c4.metric("Credit share", f"{round((credit / revenue) * 100)}%" if revenue else "—", border=True)
        mix = payment_mix_df(result.get("transactions") or [])
        items = item_amount_df(result.get("transactions") or [])
        chart_left, chart_right = st.columns(2)
        with chart_left:
            st.subheader("Cash versus credit")
            if not mix.empty:
                st.bar_chart(mix, x="Payment type", y="Amount", horizontal=True)
        with chart_right:
            st.subheader("Captured line items")
            if not items.empty:
                st.bar_chart(items.head(8), x="Item", y="Amount")
        st.subheader("Market language summary")
        summaries = {
            "English": result.get("business_health_summary") or "Summary unavailable.",
            "ChiShona": result.get("summary_shona") or "Hapana pfupiso.",
            "IsiNdebele": result.get("summary_ndebele") or "Asikho isifinyezo.",
        }
        english_col, shona_col, ndebele_col = st.columns(3)
        with english_col:
            st.markdown("**English**")
            st.markdown(summaries["English"])
        with shona_col:
            st.markdown("**ChiShona**")
            st.markdown(summaries["ChiShona"])
        with ndebele_col:
            st.markdown("**IsiNdebele**")
            st.markdown(summaries["IsiNdebele"])
        st.caption(DISCLAIMER)
    saved_ledgers = st.session_state.saved_ledgers
    if saved_ledgers:
        rows = project_ledger_history(saved_ledgers)
        trend = pd.DataFrame(rows)
        week_revenue, week_cash, next_credit = projection_headline(rows)
        st.subheader("Projection")
        st.caption(
            f"{len(saved_ledgers)} saved statement(s). "
            "This is a simple trend from recorded pages, not a credit decision."
        )
        m1, m2, m3 = st.columns(3)
        m1.metric("7-day revenue", week_revenue, border=True, format="dollar")
        m2.metric("7-day cash", week_cash, border=True, format="dollar")
        m3.metric("Projected credit", next_credit, border=True, format="dollar")
        proj_copy = projection_local_summaries(week_revenue, week_cash, next_credit)
        st.markdown(proj_copy.get(summary_lang) or proj_copy["ChiShona"])
        st.line_chart(trend, x="Period", y=["Revenue", "Cash", "Credit"])

with capture_tab:
    st.header("Capture")
    st.caption("Photograph the notebook, or speak the day's sales in English, ChiShona, or IsiNdebele.")
    upload_tab, voice_tab = st.tabs(
        [
            ":material/upload: Upload photo",
            ":material/mic: Speak statement",
        ]
    )
    with upload_tab:
        uploaded_file = st.file_uploader(
            "Handwritten ledger image",
            type=["jpg", "jpeg", "png"],
            help="Phone photos are resized to 1024px and saved as JPEG on upload.",
        )
        if uploaded_file is not None:
            file_id = f"{getattr(uploaded_file, 'file_id', uploaded_file.name)}:{uploaded_file.size}:{uploaded_file.name}"
            if st.session_state.ledger_file_id != file_id:
                original = uploaded_file.getvalue()
                jpeg = encode_ledger_jpeg(Image.open(io.BytesIO(original)))
                st.session_state.ledger_jpeg = jpeg
                st.session_state.ledger_image = Image.open(io.BytesIO(jpeg)).convert("RGB")
                st.session_state.ledger_caption = (
                    f"Compressed {format_bytes(len(original))} → {format_bytes(len(jpeg))}"
                )
                st.session_state.ledger_audio = None
                st.session_state.ledger_audio_id = ""
                st.session_state.ledger_file_id = file_id
                st.session_state.result = None
    with voice_tab:
        st.caption(
            "Say the items, amounts, cash vs *chikwereti*, and who still owes you. "
            "English, ChiShona, or IsiNdebele is fine."
        )
        spoken = st.audio_input(
            "Record your statement",
            sample_rate=16000,
            help="16 kHz recording, sent to Gemini as audio. Not stored after this session.",
        )
        if spoken is not None and st.session_state.ledger_audio_id != spoken.file_id:
            st.session_state.ledger_audio = spoken.getvalue()
            st.session_state.ledger_audio_mime = "audio/wav"
            st.session_state.ledger_audio_id = spoken.file_id
            st.session_state.ledger_image = None
            st.session_state.ledger_jpeg = None
            st.session_state.ledger_caption = "Spoken statement"
            st.session_state.result = None
        uploaded_audio = st.file_uploader(
            "Or upload a voice note",
            type=["wav", "mp3", "m4a", "ogg", "webm"],
        )
        if uploaded_audio is not None:
            audio_id = getattr(uploaded_audio, "file_id", uploaded_audio.name)
            if st.session_state.ledger_audio_id != audio_id:
                st.session_state.ledger_audio = uploaded_audio.getvalue()
                st.session_state.ledger_audio_mime = audio_mime_for(
                    uploaded_audio.name, uploaded_audio.type
                )
                st.session_state.ledger_audio_id = audio_id
                st.session_state.ledger_image = None
                st.session_state.ledger_jpeg = None
                st.session_state.ledger_caption = f"Voice note: {uploaded_audio.name}"
                st.session_state.result = None

    ledger_image = st.session_state.ledger_image
    ledger_audio = st.session_state.ledger_audio
    if ledger_image is None and ledger_audio is None:
        st.caption("Upload a photo from samples/ledgers, or record a statement to start.")
    elif ledger_audio is not None:
        preview, actions = st.columns((1.25, 1), gap="large", vertical_alignment="top")
        with preview:
            st.audio(ledger_audio, format=st.session_state.ledger_audio_mime)
            st.caption(st.session_state.ledger_caption)
        with actions:
            st.subheader("Extract with Gemini")
            already_processed = (
                bool(st.session_state.ledger_audio_id)
                and st.session_state.ledger_audio_id == st.session_state.processed_capture_id
            )
            if already_processed:
                st.caption("This statement is already saved. Reprocess only if you want Gemini to read it again.")
            if st.button(
                "Reprocess spoken statement" if already_processed else "Process spoken statement",
                type="secondary" if already_processed else "primary",
                icon=":material/replay:" if already_processed else ":material/play_arrow:",
                width="stretch",
            ):
                if not api_key:
                    st.error("Add your Gemini API key in the sidebar.")
                else:
                    extract_structured_ledger(
                        get_gemini_client(api_key),
                        extraction_prompt(
                            st.session_state.business_name,
                            st.session_state.business_category,
                            source="audio",
                        ),
                        {
                            "type": "audio",
                            "data": bytes_to_b64(ledger_audio),
                            "mime_type": st.session_state.ledger_audio_mime,
                        },
                        spinner="Listening to the statement and checking cash versus credit...",
                        capture_source="audio",
                    )
    else:
        with st.container(horizontal=True, gap="large", vertical_alignment="center"):
            with st.container(border=True, width=228, horizontal_alignment="center"):
                st.image(
                    st.session_state.ledger_jpeg or ledger_image,
                    width=196,
                    output_format="JPEG",
                )
                st.caption(st.session_state.ledger_caption)
            with st.container():
                st.subheader("Extract with Gemini")
                already_processed = (
                    bool(st.session_state.ledger_file_id)
                    and st.session_state.ledger_file_id == st.session_state.processed_capture_id
                )
                if already_processed:
                    st.caption("This photo is already saved. Reprocess only if you want Gemini to read it again.")
                if st.button(
                    "Reprocess ledger" if already_processed else "Process ledger",
                    type="secondary" if already_processed else "primary",
                    icon=":material/replay:" if already_processed else ":material/play_arrow:",
                    width="stretch",
                ):
                    if not api_key:
                        st.error("Add your Gemini API key in the sidebar.")
                    else:
                        jpeg_bytes = st.session_state.ledger_jpeg or encode_ledger_jpeg(
                            ledger_image
                        )
                        extract_structured_ledger(
                            get_gemini_client(api_key),
                            extraction_prompt(
                                st.session_state.business_name,
                                st.session_state.business_category,
                                source="image",
                            ),
                            {
                                "type": "image",
                                "data": bytes_to_b64(jpeg_bytes),
                                "mime_type": "image/jpeg",
                            },
                            spinner="Compressing the photo and reading cash versus credit...",
                            capture_source="image",
                        )

with tx_tab:
    st.header("Transactions")
    st.caption("Line items extracted from the last processed page.")
    if not result:
        st.info("Process a ledger photo or voice note first.")
    else:
        tx_df = pd.DataFrame(result.get("transactions") or [])
        if tx_df.empty:
            st.info("No line items extracted.")
        else:
            display_df = tx_df.rename(
                columns={
                    "item": "Item",
                    "quantity": "Quantity",
                    "amount_usd": "Amount (USD)",
                    "payment_type": "Payment type",
                    "debtor": "Debtor",
                }
            )
            st.dataframe(
                display_df,
                hide_index=True,
                column_config={
                    "Amount (USD)": st.column_config.NumberColumn(format="dollar"),
                },
            )
        st.caption(DISCLAIMER)

with cert_tab:
    st.header("Certificate")
    if not result:
        st.info("After Gemini reads a ledger, the financial health assessment will appear here.")
    else:
        business = result.get("business_name", "Unspecified")
        date = result.get("date", "Unspecified")
        category = result.get("business_category") or st.session_state.business_category
        st.caption(f"{business} · {date}" + (f" · {category}" if category else ""))
        if st.session_state.ledger_image is None and st.session_state.ledger_audio is None:
            st.caption("Showing the last saved statement.")
        if result.get("capture_source") == "audio":
            st.badge("Spoken statement", icon=":material/mic:", color="blue")
        transcript = _plain(result.get("transcript"))
        if transcript:
            with st.expander("Spoken transcript", icon=":material/record_voice_over:"):
                st.write(transcript)
        summaries = {
            "English": result.get("business_health_summary") or "Summary unavailable.",
            "ChiShona": result.get("summary_shona") or "Hapana pfupiso.",
            "IsiNdebele": result.get("summary_ndebele") or "Asikho isifinyezo.",
        }
        english_col, shona_col, ndebele_col = st.columns(3)
        with english_col:
            st.markdown("**English**")
            st.markdown(summaries["English"])
        with shona_col:
            st.markdown("**ChiShona**")
            st.markdown(summaries["ChiShona"])
        with ndebele_col:
            st.markdown("**IsiNdebele**")
            st.markdown(summaries["IsiNdebele"])
        if health and health.get("score") is not None:
            st.markdown(
                f"**Business health score:** {health['score']}/100 · {health.get('band')} · {health.get('status')}"
            )
        elif health:
            st.caption(f"Health score: record {health.get('record_more_days')} more trading day(s) to get a score.")
        st.download_button(
            label="Download PDF certificate",
            data=build_statement_pdf(result, health),
            file_name=statement_pdf_filename(result),
            mime="application/pdf",
            icon=":material/download:",
            type="primary",
        )
        st.caption(DISCLAIMER)

