"""Minimal HTML-to-text renderer using only the stdlib html.parser."""
from __future__ import annotations

import re
from html.parser import HTMLParser


SKIP_TAGS = {"script", "style", "noscript", "template", "svg", "head"}
BLOCK_TAGS = {
    "p", "div", "section", "article", "header", "footer", "main", "nav",
    "ul", "ol", "li", "tr", "table", "thead", "tbody", "form", "blockquote",
    "pre", "hr", "figure", "figcaption", "aside",
}
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0
        self._in_a: list[str | None] = []  # stack of href values

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "br":
            self._parts.append("\n")
        elif tag == "li":
            self._parts.append("\n  - ")
        elif tag in HEADING_TAGS:
            self._parts.append("\n\n")
        elif tag in BLOCK_TAGS:
            self._parts.append("\n\n")
        elif tag == "a":
            href = next((v for k, v in attrs if k.lower() == "href"), None)
            self._in_a.append(href)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in SKIP_TAGS:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in HEADING_TAGS or tag in BLOCK_TAGS:
            self._parts.append("\n\n")
        elif tag == "a" and self._in_a:
            href = self._in_a.pop()
            if href and not href.startswith(("javascript:", "#")):
                self._parts.append(f" <{href}>")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        self._parts.append(data)

    def text(self) -> str:
        joined = "".join(self._parts)
        joined = re.sub(r"[ \t\f\v]+", " ", joined)
        joined = re.sub(r" *\n *", "\n", joined)
        joined = re.sub(r"\n{3,}", "\n\n", joined)
        return joined.strip() + "\n"


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        # html.parser is permissive; if it ever throws, fall back to whatever was captured
        pass
    return parser.text()
