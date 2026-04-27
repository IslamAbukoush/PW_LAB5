"""DuckDuckGo HTML search, parsed from raw HTML — no third-party HTTP libs."""
from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from html.parser import HTMLParser

from http_client import fetch


SEARCH_URL = "https://html.duckduckgo.com/html/?q={query}"
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""


class _ResultsParser(HTMLParser):
    """Extract top results from html.duckduckgo.com markup."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[SearchResult] = []
        self._title_href: str | None = None
        self._title_buf: list[str] = []
        self._snippet_buf: list[str] = []
        self._mode: str | None = None  # "title" | "snippet" | None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attrs_d = {k.lower(): (v or "") for k, v in attrs}
        cls = attrs_d.get("class", "").split()
        if "result__a" in cls:
            self._flush_pending()
            self._mode = "title"
            self._title_href = attrs_d.get("href", "")
            self._title_buf = []
        elif "result__snippet" in cls:
            self._mode = "snippet"
            self._snippet_buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._mode == "title":
            self._mode = None
        elif tag == "a" and self._mode == "snippet":
            self._finalize_with_snippet()

    def handle_data(self, data: str) -> None:
        if self._mode == "title":
            self._title_buf.append(data)
        elif self._mode == "snippet":
            self._snippet_buf.append(data)

    def _flush_pending(self) -> None:
        # Title encountered with no snippet that follows — still keep the result.
        if self._title_href is not None and self._title_buf:
            title = "".join(self._title_buf).strip()
            url = _clean_url(self._title_href)
            if title and url:
                self.results.append(SearchResult(title=title, url=url))
        self._title_href = None
        self._title_buf = []
        self._snippet_buf = []

    def _finalize_with_snippet(self) -> None:
        if self._title_href is None or not self._title_buf:
            self._mode = None
            return
        title = "".join(self._title_buf).strip()
        url = _clean_url(self._title_href)
        snippet = " ".join("".join(self._snippet_buf).split())
        if title and url:
            self.results.append(SearchResult(title=title, url=url, snippet=snippet))
        self._title_href = None
        self._title_buf = []
        self._snippet_buf = []
        self._mode = None

    def close(self) -> None:  # type: ignore[override]
        super().close()
        self._flush_pending()


def _clean_url(href: str) -> str:
    if not href:
        return ""
    if href.startswith("//"):
        href = "https:" + href
    parsed = urllib.parse.urlparse(href)
    # DDG wraps outbound links: https://duckduckgo.com/l/?uddg=<encoded-target>
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.rstrip("/") in ("/l", "/y.js"):
        qs = urllib.parse.parse_qs(parsed.query)
        for key in ("uddg", "u"):
            if key in qs and qs[key]:
                return urllib.parse.unquote(qs[key][0])
    return href


def search(terms: list[str], *, limit: int = 10) -> list[SearchResult]:
    query = urllib.parse.quote_plus(" ".join(terms))
    url = SEARCH_URL.format(query=query)
    response = fetch(
        url,
        headers={
            "User-Agent": BROWSER_UA,
            "Accept": "text/html",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    parser = _ResultsParser()
    parser.feed(response.text())
    parser.close()

    seen: set[str] = set()
    unique: list[SearchResult] = []
    for r in parser.results:
        if r.url in seen:
            continue
        seen.add(r.url)
        unique.append(r)
        if len(unique) >= limit:
            break
    return unique
