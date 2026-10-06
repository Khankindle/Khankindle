"""Generate lined-notebook ledger images with several Windows handwriting fonts."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

OUT = Path(__file__).resolve().parent / "ledgers"
WIN = Path(r"C:\Windows\Fonts")

SAMPLES = [
    {
        "id": "chipo-inkfree",
        "font": "Inkfree.ttf",
        "size": 22,
        "title_size": 24,
        "ink": (28, 52, 120),
        "jitter": 1,
        "title": "GOGO CHIPO FRESH PRODUCE — 19 Sept 2026",
        "lines": [
            "1. 3 crates Tomatoes $12.00 (Cash)",
            "2. 2 bags Onions $8.00 (Cash)",
            "3. 5kg Potatoes $4.50 (Credit - Sekuru Peter)",
            "4. 1 bunch Spinach $1.00 (Cash)",
            "5. 4kg Bananas $6.00 (Credit - Amai Rudo)",
            "Stall fee: $5.00",
        ],
        "expected": {
            "business_name": "Gogo Chipo Fresh Produce",
            "date": "19 Sept 2026",
            "total_cash_usd": 21.0,
            "total_credit_outstanding_usd": 10.5,
            "total_revenue_usd": 31.5,
        },
    },
    {
        "id": "rudo-segoe-print",
        "font": "segoepr.ttf",
        "size": 20,
        "title_size": 22,
        "ink": (20, 20, 20),
        "jitter": 2,
        "title": "MAI RUDO TUCKSHOP — 19 Sept 2026",
        "lines": [
            "1. 2x Cooking oil $8.50 (Cash)",
            "2. 4 loaves Bread $4.80 (Cash)",
            "3. 10kg Maize meal $7.00 (Credit - Baba Tawanda)",
            "4. 1kg Sugar $2.20 (Cash)",
            "5. 3x Soap $3.00 (Credit - Mai Tendai)",
            "Paid rent: $12.00",
        ],
        "expected": {
            "business_name": "Mai Rudo Tuckshop",
            "date": "19 Sept 2026",
            "total_cash_usd": 15.5,
            "total_credit_outstanding_usd": 10.0,
            "total_revenue_usd": 25.5,
        },
    },
    {
        "id": "taku-lucida",
        "font": "LHANDW.TTF",
        "size": 21,
        "title_size": 23,
        "ink": (40, 28, 16),
        "jitter": 3,
        "title": "BABA TAKU KITCHEN — 19 Sept 2026",
        "lines": [
            "1. 5 plates sadza & stew $15.00 (Cash)",
            "2. 2x chips $3.00 (Cash)",
            "3. 3x maheu $2.40 (Cash)",
            "4. 4 plates chicken $16.00 (Credit - Amai Lindiwe)",
            "Oil stock: $6.00 (Expense)",
        ],
        "expected": {
            "business_name": "Baba Taku Kitchen",
            "date": "19 Sept 2026",
            "total_cash_usd": 20.4,
            "total_credit_outstanding_usd": 16.0,
            "total_revenue_usd": 36.4,
        },
    },
    {
        "id": "noma-comic",
        "font": "comic.ttf",
        "size": 20,
        "title_size": 22,
        "ink": (16, 48, 96),
        "jitter": 0,
        "title": "AMAI NOMA FASHIONS — 19 Sept 2026",
        "lines": [
            "1. 2 wrap dresses $18.00 (Cash)",
            "2. 1 mens shirt $6.50 (Cash)",
            "3. 3 headwraps $9.00 (Credit - Mai Chipo)",
            "4. 1 pair sandals $5.00 (Cash)",
            "5. Alteration $2.00 (Cash)",
            "Kombi transport: $3.50 (Expense)",
        ],
        "expected": {
            "business_name": "Amai Noma Fashions",
            "date": "19 Sept 2026",
            "total_cash_usd": 31.5,
            "total_credit_outstanding_usd": 9.0,
            "total_revenue_usd": 40.5,
        },
    },
    {
        "id": "farai-script",
        "font": "SCRIPTBL.TTF",
        "size": 26,
        "title_size": 28,
        "ink": (72, 16, 16),
        "jitter": 2,
        "title": "BABA FARAI AIRTIME — 19 Sept 2026",
        "lines": [
            "1. EcoCash float top-up $20.00 (Cash)",
            "2. 5x $2 airtime $10.00 (Cash)",
            "3. Phone charger $4.00 (Credit - Tino)",
            "4. SIM swap $1.50 (Cash)",
            "Shop light tokens: $3.00 (Expense)",
        ],
        "expected": {
            "business_name": "Baba Farai Airtime",
            "date": "19 Sept 2026",
            "total_cash_usd": 31.5,
            "total_credit_outstanding_usd": 4.0,
            "total_revenue_usd": 35.5,
        },
    },
]


def load_font(name: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = WIN / name
    try:
        return ImageFont.truetype(str(path), size)
    except OSError:
        return ImageFont.load_default()


def draw_page(sample: dict) -> Image.Image:
    width, height = 900, 640
    img = Image.new("RGB", (width, height), color=(255, 248, 230))
    draw = ImageDraw.Draw(img)
    for y in range(88, height - 24, 36):
        draw.line([(36, y), (width - 28, y)], fill=(214, 196, 164), width=1)
    draw.line([(72, 72), (72, height - 28)], fill=(188, 84, 84), width=2)

    title_font = load_font(sample["font"], sample["title_size"])
    body_font = load_font(sample["font"], sample["size"])
    draw.text((88, 28), sample["title"], fill=sample["ink"], font=title_font)
    y = 100
    for i, line in enumerate(sample["lines"]):
        x = 88 + ((i % 3) - 1) * sample["jitter"]
        draw.text((x, y + sample["jitter"] * (i % 2)), line, fill=sample["ink"], font=body_font)
        y += 36

    img = ImageEnhance.Contrast(img).enhance(1.05)
    img = img.filter(ImageFilter.SMOOTH)
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for sample in SAMPLES:
        path = OUT / f"{sample['id']}.png"
        draw_page(sample).save(path, "PNG")
        manifest.append(
            {
                "file": path.name,
                "handwriting_font": sample["font"],
                "title": sample["title"],
                "lines": sample["lines"],
                "expected_totals": sample["expected"],
            }
        )
        print(f"Wrote {path}")
    (OUT / "ground_truth.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {OUT / 'ground_truth.json'}")


if __name__ == "__main__":
    main()
