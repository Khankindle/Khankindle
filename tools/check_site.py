#!/usr/bin/env python3
"""Static checks for the site: tag balance, internal links, assets, CSS hygiene."""

import os
import re
import sys
from html.parser import HTMLParser

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = ["index.html", "research.html", "contact.html", "careers.html", "leak-audit.html"]

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr"}
OPTIONAL = {"li", "p", "td", "th", "tr", "tbody", "thead", "option", "dt", "dd"}


class Checker(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.errors = []
        self.ids = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key == "id":
                if value in self.ids:
                    self.errors.append(f"duplicate id: {value}")
                self.ids.append(value)
        if tag in VOID:
            return
        self.stack.append((tag, self.getpos()))

    def handle_startendtag(self, tag, attrs):
        for key, value in attrs:
            if key == "id":
                if value in self.ids:
                    self.errors.append(f"duplicate id: {value}")
                self.ids.append(value)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack:
            self.errors.append(f"stray </{tag}> at {self.getpos()}")
            return
        if self.stack[-1][0] == tag:
            self.stack.pop()
            return
        # tolerate omitted optional end tags
        if tag in OPTIONAL:
            while self.stack and self.stack[-1][0] in OPTIONAL and self.stack[-1][0] != tag:
                self.stack.pop()
            if self.stack and self.stack[-1][0] == tag:
                self.stack.pop()
                return
        self.errors.append(f"expected </{self.stack[-1][0]}> but found </{tag}> at {self.getpos}")

    def finish(self):
        for tag, pos in self.stack:
            if tag not in OPTIONAL:
                self.errors.append(f"unclosed <{tag}> opened at {pos}")


def check_page(page):
    path = os.path.join(ROOT, page)
    html = open(path, encoding="utf-8").read()
    parser = Checker()
    parser.feed(html)
    parser.close()
    parser.finish()

    problems = list(parser.errors)

    # internal links and assets
    for attr, value in re.findall(r'(href|src)="([^"]+)"', html):
        if value.startswith(("http", "mailto:", "data:", "#")):
            continue
        clean = value.split("#")[0]
        if not clean:
            continue
        target = os.path.normpath(os.path.join(ROOT, clean))
        if not os.path.exists(target):
            problems.append(f"missing target: {value}")

    # anchors must exist on the target page
    for value in re.findall(r'href="(index\.html#[^"]+|#[^"]+)"', html):
        anchor = value.split("#")[1]
        if not anchor:
            continue
        host = page if value.startswith("#") else "index.html"
        host_html = open(os.path.join(ROOT, host), encoding="utf-8").read()
        if f'id="{anchor}"' not in host_html:
            problems.append(f"missing anchor: {value}")

    # intrinsic size attributes must match the file, or the browser mis-reserves space
    for tag in re.findall(r"<img\b[^>]*>", html):
        src = re.search(r'src="([^"]+)"', tag)
        if not src or src.group(1).startswith(("http", "data:")):
            continue
        path = os.path.join(ROOT, src.group(1))
        if not os.path.exists(path):
            continue
        with Image.open(path) as im:
            real = im.size
        declared = re.search(r'width="(\d+)"[^>]*height="(\d+)"', tag)
        if declared and (int(declared.group(1)), int(declared.group(2))) != real:
            problems.append(f"{src.group(1)}: declared {declared.group(1)}x{declared.group(2)}, file is {real[0]}x{real[1]}")
        srcset = re.search(r'srcset="([^"]+)"', tag)
        if srcset:
            for candidate in srcset.group(1).split(","):
                candidate_path = candidate.strip().split(" ")[0]
                if not os.path.exists(os.path.join(ROOT, candidate_path)):
                    problems.append(f"srcset target missing: {candidate_path}")

    if "<h1" in html and html.count("<h1") > 1:
        problems.append("more than one h1")

    for label, pattern in (
        ("images without alt", r'<img(?![^>]*\balt=)[^>]*>'),
        ("buttons without type", r'<button(?![^>]*\btype=)[^>]*>'),
    ):
        hits = re.findall(pattern, html)
        if hits:
            problems.append(f"{label}: {len(hits)}")

    return problems


def check_css():
    css = open(os.path.join(ROOT, "assets/css/site.css"), encoding="utf-8").read()
    problems = []
    if css.count("{") != css.count("}"):
        problems.append(f"braces unbalanced: {css.count('{')} open, {css.count('}')} close")
    defined = set(re.findall(r"(--[a-z0-9-]+)\s*:", css))
    used = set(re.findall(r"var\((--[a-z0-9-]+)", css))
    unknown = sorted(used - defined - {"--btn-bg", "--btn-fg"})
    if unknown:
        problems.append("undefined custom properties: " + ", ".join(unknown))
    if re.search(r";;", css):
        problems.append("double semicolons present")
    return problems


if __name__ == "__main__":
    failures = 0
    for page in PAGES:
        issues = check_page(page)
        if issues:
            failures += 1
            print(f"\n{page}")
            for issue in issues:
                print("  -", issue)
        else:
            print(f"{page}: ok")
    css_issues = check_css()
    if css_issues:
        failures += 1
        print("\nsite.css")
        for issue in css_issues:
            print("  -", issue)
    else:
        print("site.css: ok")

    # explicit requirement: no Google Drive anywhere
    for name in sorted(os.listdir(ROOT)):
        if name.endswith(".html"):
            body = open(os.path.join(ROOT, name), encoding="utf-8").read().lower()
            if "drive.google" in body:
                failures += 1
                print(f"Google Drive link found in {name}")
    print("\nall checks passed" if not failures else f"\n{failures} file(s) with issues")
    sys.exit(1 if failures else 0)
