"""PocketLedger financial certificate PDF."""

import os
import re
from pathlib import Path
from typing import Any

from fpdf import FPDF

from ledger_core import _money, _plain


def _register_pdf_font(pdf: FPDF) -> str:
    win_fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    regular = win_fonts / "arial.ttf"
    bold = win_fonts / "arialbd.ttf"
    if regular.exists():
        pdf.add_font("AppSans", "", str(regular))
        pdf.add_font("AppSans", "B", str(bold if bold.exists() else regular))
        return "AppSans"
    return "Helvetica"


def build_statement_pdf(result: dict[str, Any]) -> bytes:
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    font_name = _register_pdf_font(pdf)
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
    pdf.multi_cell(
        0,
        5,
        "AI-assisted indexing only. Totals are recalculated from extracted line items. "
        "This is not an IT audit, tax audit, or certified financial report, and it is not a loan decision.",
    )
    return bytes(pdf.output())


def statement_pdf_filename(result: dict[str, Any]) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", _plain(result.get("business_name")).lower()).strip("_")
    return f"pocketledger_{slug or 'statement'}.pdf"
