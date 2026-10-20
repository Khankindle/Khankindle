#!/usr/bin/env python3
"""Render the CloudyAI research library into assets/research/.

Usage
-----
    python -m venv .venv && .venv/bin/pip install pillow reportlab
    .venv/bin/python tools/make_research_pdfs.py

Content lives in tools/research_content.py; layout lives in tools/pdf_lib.py.
Web covers are regenerated from page one of each PDF by tools/make_covers.py.
"""

import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image  # noqa: E402
from pdf_lib import Doc, MUTED, INK  # noqa: E402
from research_content import PAPERS  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "assets", "img")
OUT = os.path.join(ROOT, "assets", "research")

COLOPHON = (
    "CloudyAI is a Zimbabwean AI studio. We deploy computer vision on existing "
    "plant cameras, audit AI spend, and help teams respond when an AI system "
    "misbehaves. Research is published free, without an email wall."
)

CONVERTED = {}


def raster(path):
    """reportlab cannot read WebP directly; hand it a compressed JPEG instead."""
    if os.path.exists(path) and path.lower().endswith((".png", ".jpg", ".jpeg")):
        return path
    if not os.path.exists(path):
        alt = os.path.splitext(path)[0] + ".webp"
        if os.path.exists(alt):
            path = alt
        else:
            return None
    if path in CONVERTED:
        return CONVERTED[path]
    tmp = os.path.join("/tmp", "cloudyai_" + os.path.basename(path).rsplit(".", 1)[0] + ".jpg")
    im = Image.open(path).convert("RGB")
    im.thumbnail((1500, 1500), Image.LANCZOS)
    im.save(tmp, "JPEG", quality=84, optimize=True)
    CONVERTED[path] = tmp
    return tmp


def render(paper):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, paper["slug"] + ".pdf")
    doc = Doc(
        path,
        title=paper["title"],
        subtitle=paper["subtitle"],
        series=paper["series"],
        cover_image=raster(os.path.join(IMG, paper["cover"])),
        date=paper["date"],
        doc_id=paper["doc_id"],
        contents=[b[1] for b in paper["sections"] if b[0] == "h1"],
    )
    doc.start_body()

    # Standfirst on the first text page
    doc.eyebrow("Summary")
    doc.p(paper["blurb"], size=11.6, leading=17.4, color=INK, font="Times-Italic",
          space_after=16)
    doc.rule()

    figures = {
        "ppe-existing-cameras": (
            "cam-ppe.webp",
            "A fixed ceiling camera over a production walkway. A hard hat resolves "
            "at this distance; a glove does not.",
        ),
        "fill-level-inspection": (
            "cam-fill.webp",
            "Backlit fill inspection. Two underfilled containers in one frame - the "
            "case a manual spot check misses.",
        ),
        "counting-what-you-can-see": (
            "card-forklift.webp",
            "A dispatch aisle. Counting, queue length and blocked states are all "
            "visible from one fixed view.",
        ),
    }

    used_figure = False
    for block in paper["sections"]:
        kind = block[0]
        if kind == "p":
            doc.p(block[1])
        elif kind == "h1":
            doc.h1(block[1])
        elif kind == "h2":
            doc.h2(block[1])
        elif kind == "callout":
            doc.callout(block[1][0], block[1][1])
        elif kind == "bullets":
            doc.bullets(block[1])
        elif kind == "numbered":
            doc.numbered(block[1])
        elif kind == "quote":
            doc.quote(block[1], block[2] if len(block) > 2 else "")
        elif kind == "table":
            headers, rows, widths = block[1]
            doc.table(headers, rows, widths=widths)
        elif kind == "rule":
            doc.rule()
            doc.space(4)
        elif kind == "eyebrow":
            doc.eyebrow(block[1])
        elif kind == "figure":
            doc.figure(block[1], block[2])
        else:
            raise ValueError("unknown block: %s" % kind)

        # Drop a photograph into the middle of image-heavy papers, once.
        if (not used_figure and kind == "h1" and paper["slug"] in figures
                and doc.page >= 3):
            name, caption = figures[paper["slug"]]
            doc.figure(raster(os.path.join(IMG, name)), caption)
            used_figure = True

    doc.rule()
    doc.eyebrow("About this paper")
    doc.p(COLOPHON, size=9.8, leading=14.6, color=MUTED)
    doc.space(2)
    doc.p("Corrections and questions: research@cloudyai.co.zw. If you would like this "
          "method applied to your plant, the first conversation is free and the "
          "camera audit is a fixed-price week.", size=9.8, leading=14.6, color=MUTED)
    doc.finish()
    return path


if __name__ == "__main__":
    for paper in PAPERS:
        p = render(paper)
        print("wrote", os.path.relpath(p, ROOT),
              "%.0f KB" % (os.path.getsize(p) / 1024))
