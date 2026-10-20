"""Small editorial PDF layout engine on top of reportlab.

Built for CloudyAI research papers: a cream page, Times for reading,
Helvetica for labels, clay rules, and a photographic cover. Deliberately
plain - it should look like a printed report, not a generated document.
"""

import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import Color, HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth

PAGE_W, PAGE_H = A4
M = 62                      # left / right margin
TOP = PAGE_H - 74           # first baseline of body text
BOTTOM = 66                 # last usable baseline

INK = HexColor("#191510")
INK_SOFT = HexColor("#4A4237")
MUTED = HexColor("#7A6E5C")
PAPER = HexColor("#FBF7EE")
PAPER_DEEP = HexColor("#F2EBDD")
CLAY = HexColor("#A8431F")
OLIVE = HexColor("#4E5A45")
RULE = HexColor("#D8CDBA")
GOLD = HexColor("#B8862F")

SERIF = "Times-Roman"
SERIF_B = "Times-Bold"
SERIF_I = "Times-Italic"
SANS = "Helvetica"
SANS_B = "Helvetica-Bold"
SANS_O = "Helvetica-Oblique"

CONTENT_W = PAGE_W - 2 * M
TEXT_W = 432          # comfortable measure, ~72 characters


def tracked(c, x, y, text, font=SANS_B, size=7.2, tracking=1.6, color=MUTED):
    c.setFont(font, size)
    c.setFillColor(color)
    for ch in text:
        c.drawString(x, y, ch)
        x += stringWidth(ch, font, size) + tracking
    return x


def tracked_width(text, font=SANS_B, size=7.2, tracking=1.6):
    w = sum(stringWidth(ch, font, size) for ch in text)
    return w + tracking * max(len(text) - 1, 0)


def wrap(text, font, size, width):
    words = text.split()
    lines, line = [], ""
    for word in words:
        trial = (line + " " + word).strip()
        if stringWidth(trial, font, size) <= width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def clean(text):
    """Keep the text inside WinAnsi so the base-14 fonts render every glyph."""
    return (text.replace("\u2192", "to").replace("\u2265", ">=")
                .replace("\u2264", "<=").replace("\u2713", "ok")
                .replace("\u2011", "-"))


class Doc:
    # NOTE: reportlab y coordinates are measured from the bottom of the page.
    def __init__(self, path, title, subtitle, series, cover_image=None,
                 author="CloudyAI Research", date="October 2026", doc_id="",
                 contents=None):
        self.path = path
        self.title = title
        self.subtitle = subtitle
        self.series = series
        self.cover_image = cover_image
        self.author = author
        self.date = date
        self.doc_id = doc_id
        self.contents = contents or []
        self.c = canvas.Canvas(path, pagesize=A4)
        self.c.setTitle(title)
        self.c.setAuthor(author)
        self.c.setSubject(subtitle)
        self.c.setCreator("CloudyAI Research")
        self.page = 0
        self.y = TOP
        self._cover()

    # ------------------------------------------------------------------ pages
    def _background(self, fill=PAPER):
        c = self.c
        c.setFillColor(fill)
        c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)

    def _chrome(self):
        c = self.c
        c.setStrokeColor(RULE)
        c.setLineWidth(0.6)
        c.line(M, PAGE_H - 46, PAGE_W - M, PAGE_H - 46)
        tracked(c, M, PAGE_H - 38, "CLOUDYAI RESEARCH", size=6.6, tracking=1.5)
        label = self.series.upper()
        w = tracked_width(label, size=6.6, tracking=1.5)
        tracked(c, PAGE_W - M - w, PAGE_H - 38, label, size=6.6, tracking=1.5)
        # footer
        c.line(M, 46, PAGE_W - M, 46)
        tracked(c, M, 34, "cloudyai.co.zw", size=6.6, tracking=1.2, color=MUTED)
        num = str(self.page)
        c.setFont(SANS, 7)
        c.setFillColor(MUTED)
        c.drawRightString(PAGE_W - M, 34, num)

    def _cover(self):
        c = self.c
        self.page = 1
        self._background(PAPER)
        band_h = PAGE_H * 0.50
        img = None
        if self.cover_image and os.path.exists(self.cover_image):
            try:
                img = ImageReader(self.cover_image)
            except Exception:
                img = None
        if img:
            c.drawImage(img, 0, PAGE_H - band_h, width=PAGE_W, height=band_h,
                        preserveAspectRatio=False, mask=None)
            # warm wash so the photography reads as print, not screenshot
            c.setFillColor(Color(0.106, 0.082, 0.063, alpha=0.30))
            c.rect(0, PAGE_H - band_h, PAGE_W, band_h, stroke=0, fill=1)
            c.setFillColor(Color(0.984, 0.968, 0.933, alpha=0.14))
            c.rect(0, PAGE_H - band_h, PAGE_W, band_h, stroke=0, fill=1)
            steps = 60
            band = 120.0
            for i in range(steps):
                a = 0.52 * (i / float(steps)) ** 2.0
                c.setFillColor(Color(0.05, 0.04, 0.03, alpha=a))
                c.rect(0, PAGE_H - band + i * (band / steps), PAGE_W,
                       band / steps + 0.5, stroke=0, fill=1)
        else:
            c.setFillColor(PAPER_DEEP)
            c.rect(0, PAGE_H - band_h, PAGE_W, band_h, stroke=0, fill=1)

        # masthead inside the photo
        tracked(c, M, PAGE_H - 46, "CLOUDYAI", size=9, tracking=3.2,
                color=Color(1, 1, 1, alpha=0.92))
        tracked(c, M, PAGE_H - 62, "RESEARCH", size=6.4,
                tracking=1.7, color=Color(1, 1, 1, alpha=0.72))
        right = self.doc_id
        rw = tracked_width(right, size=6.4, tracking=1.7)
        tracked(c, PAGE_W - M - rw, PAGE_H - 62, right, size=6.4, tracking=1.7,
                color=Color(1, 1, 1, alpha=0.72))

        # title block on paper
        y = PAGE_H - band_h - 54
        tracked(c, M, y, self.series.upper(), size=7.4, tracking=2.0, color=CLAY)
        y -= 30
        c.setFillColor(INK)
        for line in wrap(clean(self.title), SERIF_B, 27.5, CONTENT_W):
            c.setFont(SERIF_B, 27.5)
            c.drawString(M, y, line)
            y -= 30
        y -= 6
        c.setStrokeColor(CLAY)
        c.setLineWidth(1.4)
        c.line(M, y, M + 46, y)
        y -= 22
        c.setFillColor(INK_SOFT)
        for line in wrap(clean(self.subtitle), SERIF_I, 12.5, CONTENT_W - 20):
            c.setFont(SERIF_I, 12.5)
            c.drawString(M, y, line)
            y -= 17

        # contents, set as a plain two-column index
        if self.contents and (y - 46 - (19 + 15 * min(5, len(self.contents)))) > 118:
            y_c = y - 46
            tracked(c, M, y_c, "IN THIS PAPER", size=6.6, tracking=1.8, color=MUTED)
            y_c -= 19
            for i, item in enumerate(self.contents[:5], 1):
                c.setFillColor(CLAY)
                c.setFont(SANS_B, 7.0)
                c.drawString(M, y_c, "%02d" % i)
                c.setFillColor(INK_SOFT)
                c.setFont(SERIF, 9.6)
                c.drawString(M + 24, y_c, clean(item))
                y_c -= 15

        # foot of cover
        c.setStrokeColor(RULE)
        c.setLineWidth(0.6)
        c.line(M, 108, PAGE_W - M, 108)
        c.setFont(SANS, 8)
        c.setFillColor(INK_SOFT)
        c.drawString(M, 90, self.date)
        c.drawString(M + 92, 90, self.author)
        c.setFont(SANS, 8)
        c.setFillColor(MUTED)
        c.drawRightString(PAGE_W - M, 90, "Free to download - no email required")
        c.showPage()

    def start_body(self):
        """Begin page 2 without emitting an empty page after the cover."""
        self.page += 1
        self._background(PAPER)
        self._chrome()
        self.y = TOP

    def new_page(self):
        self.c.showPage()
        self.page += 1
        self._background(PAPER)
        self._chrome()
        self.y = TOP

    def ensure(self, needed):
        if self.y - needed < BOTTOM:
            self.new_page()

    # --------------------------------------------------------------- elements
    def space(self, h=10):
        self.y -= h

    def rule(self, color=RULE, weight=0.6, width=None):
        self.c.setStrokeColor(color)
        self.c.setLineWidth(weight)
        self.c.line(M, self.y, M + (width or CONTENT_W), self.y)
        self.y -= 16

    def eyebrow(self, text, color=CLAY):
        self.ensure(30)
        tracked(self.c, M, self.y, clean(text).upper(), size=7.2, tracking=1.9, color=color)
        self.y -= 14

    def h1(self, text):
        self.ensure(120)
        self.y -= 6
        self.c.setFillColor(INK)
        self.c.setFont(SERIF_B, 17)
        for line in wrap(clean(text), SERIF_B, 17, TEXT_W):
            self.c.drawString(M, self.y, line)
            self.y -= 21
        self.y -= 6

    def h2(self, text):
        self.ensure(70)
        self.y -= 4
        self.c.setFillColor(INK)
        self.c.setFont(SERIF_B, 11.6)
        for line in wrap(clean(text), SERIF_B, 11.6, TEXT_W):
            self.c.drawString(M, self.y, line)
            self.y -= 15
        self.y -= 3

    def p(self, text, size=10.3, leading=15.6, color=INK_SOFT, indent=0,
          font=SERIF, space_after=9):
        lines = wrap(clean(text), font, size, TEXT_W - indent)
        for line in lines:
            self.ensure(leading)
            self.c.setFont(font, size)
            self.c.setFillColor(color)
            self.c.drawString(M + indent, self.y, line)
            self.y -= leading
        self.y -= space_after

    def bullets(self, items, size=10.2, leading=15.0, color=INK_SOFT, marker="\u2014"):
        for item in items:
            lines = wrap(clean(item), SERIF, size, TEXT_W - 16)
            self.ensure(leading)
            self.c.setFont(SERIF, size)
            self.c.setFillColor(CLAY)
            self.c.drawString(M, self.y, marker)
            for i, line in enumerate(lines):
                if i:
                    self.ensure(leading)
                self.c.setFont(SERIF, size)
                self.c.setFillColor(color)
                self.c.drawString(M + 16, self.y, line)
                self.y -= leading
            self.y -= 3
        self.y -= 7

    def numbered(self, items, size=10.2, leading=15.0, color=INK_SOFT):
        for i, item in enumerate(items, 1):
            lines = wrap(clean(item), SERIF, size, TEXT_W - 22)
            self.ensure(leading)
            self.c.setFont(SANS_B, 7.6)
            self.c.setFillColor(CLAY)
            self.c.drawString(M, self.y, "%02d" % i)
            for j, line in enumerate(lines):
                if j:
                    self.ensure(leading)
                self.c.setFont(SERIF, size)
                self.c.setFillColor(color)
                self.c.drawString(M + 22, self.y, line)
                self.y -= leading
            self.y -= 4
        self.y -= 7

    def callout(self, heading, text, fill=PAPER_DEEP, bar=CLAY):
        pad = 13
        inner_w = TEXT_W - pad * 2 - 8
        head_lines = wrap(clean(heading), SANS_B, 8.0, inner_w)
        body_lines = wrap(clean(text), SERIF, 9.9, inner_w)
        height = 14 + len(head_lines) * 11 + 4 + len(body_lines) * 14 + 12
        self.ensure(height + 8)
        top = self.y + 4
        self.c.setFillColor(fill)
        self.c.rect(M, top - height, TEXT_W, height, stroke=0, fill=1)
        self.c.setFillColor(bar)
        self.c.rect(M, top - height, 3, height, stroke=0, fill=1)
        y = top - 16
        self.c.setFillColor(bar)
        for line in head_lines:
            self.c.setFont(SANS_B, 8.0)
            self.c.drawString(M + pad + 4, y, line)
            y -= 11
        y -= 4
        self.c.setFillColor(INK)
        for line in body_lines:
            self.c.setFont(SERIF, 9.9)
            self.c.drawString(M + pad + 4, y, line)
            y -= 14
        self.y = top - height - 16

    def quote(self, text, source=""):
        size, leading = 12.4, 18
        lines = wrap(clean(text), SERIF_I, size, TEXT_W - 40)
        height = len(lines) * leading + (18 if source else 0) + 10
        self.ensure(height + 10)
        self.c.setStrokeColor(GOLD)
        self.c.setLineWidth(1.2)
        top = self.y + 4
        self.c.line(M + 12, top, M + 12, top - height + 6)
        y = top - 12
        self.c.setFillColor(INK)
        for line in lines:
            self.c.setFont(SERIF_I, size)
            self.c.drawString(M + 30, y, line)
            y -= leading
        if source:
            y -= 2
            tracked(self.c, M + 30, y, clean(source).upper(), size=6.8, tracking=1.4, color=MUTED)
        self.y = top - height - 8

    def table(self, headers, rows, widths=None, size=9.2):
        cols = len(headers)
        if widths is None:
            widths = [CONTENT_W / cols] * cols
        pad = 8
        # estimate the whole table; keep it on one page when it can fit there
        est = 26
        for row in rows:
            wrapped = [wrap(clean(str(cell)), SERIF, size, w - pad * 2)
                       for cell, w in zip(row, widths)]
            est += max(len(c) for c in wrapped) * 12.4 + 10
        if est < (TOP - BOTTOM - 40) and self.y - est < BOTTOM:
            self.new_page()
        # header
        self.ensure(40)
        self.c.setFillColor(PAPER_DEEP)
        head_h = 0
        wrapped_head = [wrap(clean(h), SANS_B, 7.6, w - pad * 2) for h, w in zip(headers, widths)]
        head_h = max(len(h) for h in wrapped_head) * 10 + 14
        self.c.rect(M, self.y - head_h + 8, CONTENT_W, head_h, stroke=0, fill=1)
        y = self.y
        for w, lines in zip(widths, wrapped_head):
            yy = y - 3
            for line in lines:
                self.c.setFont(SANS_B, 7.6)
                self.c.setFillColor(INK)
                self.c.drawString(self._col_x(w, widths) + pad, yy, line)
                yy -= 10
        self.y -= head_h
        for row in rows:
            wrapped = [wrap(clean(str(cell)), SERIF, size, w - pad * 2)
                       for cell, w in zip(row, widths)]
            row_h = max(len(c) for c in wrapped) * 12.4 + 10
            self.ensure(row_h + 2)
            self.c.setStrokeColor(RULE)
            self.c.setLineWidth(0.5)
            self.c.line(M, self.y + 6, PAGE_W - M, self.y + 6)
            yy = self.y - 4
            for w, lines in zip(widths, wrapped):
                yyy = yy
                for line in lines:
                    self.c.setFont(SERIF, size)
                    self.c.setFillColor(INK_SOFT)
                    self.c.drawString(self._col_x(w, widths) + pad, yyy, line)
                    yyy -= 12.4
            self.y -= row_h
        self.c.setStrokeColor(RULE)
        self.c.line(M, self.y + 6, PAGE_W - M, self.y + 6)
        self.y -= 16

    def _col_x(self, w, widths):
        x = M
        for other in widths:
            if other is w:
                break
            x += other
        return x

    def figure(self, image_path, caption, max_h=190):
        if not os.path.exists(image_path):
            return
        img = ImageReader(image_path)
        iw, ih = img.getSize()
        w = CONTENT_W
        h = w * ih / iw
        if h > max_h:
            h = max_h
            w = h * iw / ih
        self.ensure(h + 30)
        self.c.drawImage(img, M, self.y - h, width=w, height=h)
        self.y -= h + 12
        self.c.setFillColor(MUTED)
        self.c.setFont(SANS_O, 7.6)
        self.c.drawString(M, self.y, clean(caption))
        self.y -= 18

    def finish(self):
        self.c.save()
