"""PocketLedger financial certificate PDF."""

import os
import re
from pathlib import Path
from typing import Any

from fpdf import FPDF

from health_score import COMPONENT_LABELS, HEALTH_CONFIG, STATUS_NOTES
from ledger_core import _money, _plain

# Built-in PDF fonts (Helvetica) only cover Latin-1. Map common Unicode punctuation so the
# certificate never crashes on Linux hosts without Arial (e.g. Streamlit Community Cloud).
_LATIN1_REPLACEMENTS = {
    "\u2014": "-", "\u2013": "-", "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2026": "...", "\u2022": "\u00b7", "\u2212": "-", "\u00a0": " ",
}

_LINUX_FONT_DIRS = (Path("/usr/share/fonts/truetype/dejavu"), Path("/usr/share/fonts/dejavu"))

PDF_DISCLAIMER = (
    "AI-assisted indexing only. Totals are recalculated from extracted line items. "
    "This is not an IT audit, tax audit, or certified financial report, and it is not a loan decision."
)


class CertificatePDF(FPDF):
    """FPDF with a safe text fallback and a footer on every page that shows a health score."""

    footer_text = ""

    def normalize_text(self, text: str) -> str:
        if not self.is_ttf_font:
            for char, replacement in _LATIN1_REPLACEMENTS.items():
                text = text.replace(char, replacement)
            text = text.encode("latin-1", errors="replace").decode("latin-1")
        return super().normalize_text(text)

    def footer(self) -> None:
        self.set_y(-14)
        self.set_font(self.font_family or "Helvetica", "", 7)
        self.set_text_color(120, 124, 140)
        if self.footer_text:
            self.multi_cell(0, 3.5, self.footer_text, align="C", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 3.5, f"Page {self.page_no()}", align="C")


def _register_pdf_font(pdf: FPDF) -> str:
    win_fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    regular = win_fonts / "arial.ttf"
    bold = win_fonts / "arialbd.ttf"
    if regular.exists():
        pdf.add_font("AppSans", "", str(regular))
        pdf.add_font("AppSans", "B", str(bold if bold.exists() else regular))
        return "AppSans"
    for folder in _LINUX_FONT_DIRS:
        regular = folder / "DejaVuSans.ttf"
        bold = folder / "DejaVuSans-Bold.ttf"
        if regular.exists():
            pdf.add_font("AppSans", "", str(regular))
            pdf.add_font("AppSans", "B", str(bold if bold.exists() else regular))
            return "AppSans"
    return "Helvetica"


def build_statement_pdf(result: dict[str, Any], health: dict[str, Any] | None = None) -> bytes:
    """Build the certificate PDF. `health` is the output of ``health_score.compute`` (optional)."""
    pdf = CertificatePDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=22)
    if health and health.get("score") is not None:
        pdf.footer_text = (
            f"Business health score {health['score']}/100 ({health.get('band')}), method {health.get('score_version')}. "
            + PDF_DISCLAIMER
        )
    font_name = _register_pdf_font(pdf)
    pdf.add_page()
    navy = (28, 32, 80)
    muted = (90, 95, 120)

    pdf.set_text_color(*navy)
    pdf.set_font(font_name, "B", 18)
    pdf.cell(0, 10, "PocketLedger financial certificate", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(font_name, "", 11)
    pdf.set_text_color(*muted)
    pdf.cell(0, 6, "AI-assisted cash versus credit statement", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    business = _plain(result.get("business_name", "Unspecified")) or "Unspecified"
    date = _plain(result.get("date", "Unspecified")) or "Unspecified"
    category = _plain(result.get("business_category"))
    pdf.set_text_color(*navy)
    pdf.set_font(font_name, "B", 14)
    pdf.cell(0, 8, f"{business}  ·  {date}", new_x="LMARGIN", new_y="NEXT")
    if category:
        pdf.set_font(font_name, "", 11)
        pdf.set_text_color(*muted)
        pdf.cell(0, 6, f"Category: {category}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    pdf.set_text_color(*navy)
    pdf.set_font(font_name, "", 11)
    for label, key in (
        ("Total recorded revenue", "total_revenue_usd"),
        ("Cash received", "total_cash_usd"),
        ("Outstanding credit (chikwereti)", "total_credit_outstanding_usd"),
    ):
        pdf.set_font(font_name, "B", 11)
        pdf.cell(88, 7, label)
        pdf.set_font(font_name, "", 11)
        pdf.cell(0, 7, _money(result.get(key)), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    if health:
        _health_block(pdf, font_name, health, navy, muted)

    pdf.set_text_color(*navy)
    pdf.set_font(font_name, "B", 13)
    pdf.cell(0, 8, "Extracted transactions", new_x="LMARGIN", new_y="NEXT")
    transactions = result.get("transactions") or []
    if not transactions:
        pdf.set_font(font_name, "", 11)
        pdf.cell(0, 7, "No line items extracted.", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_font(font_name, "", 9)
        with pdf.table(col_widths=(52, 22, 28, 38, 40), text_align=("LEFT", "CENTER", "RIGHT", "LEFT", "LEFT")) as table:
            header = table.row()
            for title in ("Item", "Qty", "Amount (USD)", "Payment type", "Debtor"):
                header.cell(title)
            for row in transactions:
                cells = table.row()
                cells.cell(_plain(row.get("item")) or "—")
                cells.cell(_plain(row.get("quantity")) or "—")
                cells.cell(_money(row.get("amount_usd")))
                cells.cell(_plain(row.get("payment_type")) or "—")
                cells.cell(_plain(row.get("debtor")) or "N/A")

    pdf.ln(6)
    pdf.set_font(font_name, "B", 13)
    pdf.set_text_color(*navy)
    pdf.cell(0, 8, "Financial health certificate", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(font_name, "", 11)
    summary = _plain(result.get("business_health_summary")) or "Summary unavailable."
    pdf.multi_cell(0, 6, summary)
    pdf.ln(3)
    pdf.set_font(font_name, "B", 12)
    pdf.cell(0, 7, "ChiShona", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(font_name, "", 11)
    pdf.multi_cell(0, 6, _plain(result.get("summary_shona")) or "Hapana pfupiso.")
    pdf.ln(2)
    pdf.set_font(font_name, "B", 12)
    pdf.cell(0, 7, "IsiNdebele", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(font_name, "", 11)
    pdf.multi_cell(0, 6, _plain(result.get("summary_ndebele")) or "Asikho isifinyezo.")
    pdf.ln(4)
    pdf.set_font(font_name, "", 9)
    pdf.set_text_color(*muted)
    pdf.multi_cell(0, 5, PDF_DISCLAIMER)
    return bytes(pdf.output())


def _para(pdf: FPDF, text: str, height: float = 5.5) -> None:
    """Full-width paragraph that leaves the cursor at the left margin on the next line."""
    pdf.multi_cell(0, height, text, new_x="LMARGIN", new_y="NEXT")


def _health_block(pdf: FPDF, font_name: str, health: dict[str, Any], navy, muted) -> None:
    """Business health score section (SPEC.md §7.7)."""
    green = (11, 110, 79)
    pdf.set_text_color(*navy)
    pdf.set_font(font_name, "B", 13)
    pdf.cell(0, 8, "Business health score", new_x="LMARGIN", new_y="NEXT")

    window = health.get("window") or {}
    status = health.get("status") or "Not enough data"
    score = health.get("score")
    if score is None:
        pdf.set_font(font_name, "", 11)
        _para(
            pdf,
            f"Not enough history yet: {window.get('trading_days', 0)} trading day(s) recorded. "
            f"Record {health.get('record_more_days', 0)} more trading day(s) to get a score.",
            6,
        )
        pdf.ln(4)
        return

    band_local = health.get("band_local") or {}
    pdf.set_text_color(*green)
    pdf.set_font(font_name, "B", 22)
    pdf.cell(32, 11, f"{score}/100")
    pdf.set_font(font_name, "B", 14)
    pdf.cell(
        0, 11,
        f"{health.get('band')}  ·  {band_local.get('ChiShona', '')}  ·  {band_local.get('IsiNdebele', '')}",
        new_x="LMARGIN", new_y="NEXT",
    )

    pdf.set_text_color(*muted)
    pdf.set_font(font_name, "", 9)
    _para(
        pdf,
        f"{status} · Evidence: {health.get('evidence_level')} · "
        f"Window {window.get('start')} to {window.get('end')} · {window.get('trading_days')} trading days. "
        f"{STATUS_NOTES.get(status, '')} Based on all saved pages for this business, not only the page above.",
        5,
    )
    pdf.ln(1)

    pdf.set_text_color(*navy)
    pdf.set_font(font_name, "", 9)
    components = health.get("components") or {}
    with pdf.table(col_widths=(90, 30, 30), text_align=("LEFT", "RIGHT", "RIGHT"), width=150, align="LEFT") as table:
        header = table.row()
        for title in ("Component", "Weight", "Score (0-100)"):
            header.cell(title)
        for key, weight in HEALTH_CONFIG["weights"].items():
            row = table.row()
            row.cell(COMPONENT_LABELS.get(key, key))
            row.cell(f"{weight}%")
            row.cell(str(components.get(key, "-")))
    pdf.ln(2)

    pdf.set_font(font_name, "", 10)
    book = health.get("credit_book") or {}
    if book:
        _para(
            pdf,
            f"Outstanding credit across saved pages: {_money(book.get('outstanding_usd'))}, "
            f"of which {_money(book.get('aged_over_30_days_usd'))} is older than 30 days.",
        )
    strength = health.get("strength")
    if strength:
        _para(pdf, f"Strength: {COMPONENT_LABELS.get(strength, strength)}.")
    actions = health.get("actions") or []
    if actions:
        pdf.set_font(font_name, "B", 10)
        pdf.cell(0, 6, "What is lowering the score", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font(font_name, "", 10)
        for action in actions:
            label = COMPONENT_LABELS.get(action.get("component"), action.get("component"))
            _para(pdf, f"·  {label}: {action.get('English')}")
    excluded = health.get("excluded") or []
    if excluded:
        reasons: dict[str, int] = {}
        for entry in excluded:
            reasons[entry.get("reason")] = reasons.get(entry.get("reason"), 0) + 1
        detail = "; ".join(f"{reason} ({count})" for reason, count in sorted(reasons.items()))
        _para(pdf, f"Excluded entries: {len(excluded)}. {detail}.")

    affordability = health.get("affordability")
    pdf.ln(1)
    if affordability:
        pdf.set_font(font_name, "B", 10)
        pdf.cell(0, 6, "Affordability guide", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font(font_name, "", 10)
        _para(
            pdf,
            f"Typical daily net cash {_money(affordability.get('typical_net_cash_usd'))}. "
            f"Safe daily repayment up to {_money(affordability.get('safe_daily_repayment_usd'))}; "
            f"indicative 30-day total repayment up to {_money(affordability.get('indicative_amount_30d_usd'))}. "
            f"{affordability.get('note', '')}",
        )
    else:
        pdf.set_text_color(*muted)
        pdf.set_font(font_name, "", 9)
        _para(
            pdf,
            "Affordability guide not shown: it needs an Established status, a score of 50 or more, "
            "and positive daily net cash.",
            5,
        )
    pdf.set_text_color(*muted)
    pdf.set_font(font_name, "", 8)
    _para(
        pdf,
        f"Method {health.get('score_version')}: a published, rule-based health score computed from the trader's own "
        "records. It is not a credit score, not a probability of default, and not a loan decision.",
        4.5,
    )
    pdf.ln(4)


def statement_pdf_filename(result: dict[str, Any]) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", _plain(result.get("business_name")).lower()).strip("_")
    return f"pocketledger_{slug or 'statement'}.pdf"
