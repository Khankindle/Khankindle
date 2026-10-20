#!/usr/bin/env python3
"""Regenerate the web thumbnails used on the research cards.

    .venv/bin/python tools/make_covers.py

Needs: pip install pymupdf pillow
"""

import io
import os

import pymupdf
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets", "research")
OUT = os.path.join(SRC, "covers")

os.makedirs(OUT, exist_ok=True)
for name in sorted(os.listdir(SRC)):
    if not name.endswith(".pdf"):
        continue
    doc = pymupdf.open(os.path.join(SRC, name))
    pix = doc[0].get_pixmap(dpi=120)
    im = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    im.thumbnail((760, 1000), Image.LANCZOS)
    target = os.path.join(OUT, os.path.splitext(name)[0] + ".webp")
    im.save(target, "WEBP", quality=84, method=6)
    print("wrote", os.path.relpath(target, ROOT), "%.0f KB" % (os.path.getsize(target) / 1024))
