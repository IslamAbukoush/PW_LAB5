#!/usr/bin/env python3
"""go2web - HTTP over raw TCP sockets."""
from __future__ import annotations

import argparse
import json as json_mod
import sys

from html_render import html_to_text
from http_client import fetch
from search import search


ACCEPT_PRESETS = {
    "html": "text/html, application/xhtml+xml",
    "json": "application/json",
    "auto": "text/html, application/xhtml+xml, application/json;q=0.9, */*;q=0.8",
}


HELP_TEXT = """go2web - HTTP over TCP sockets

Usage:
  go2web -u <URL>                       make an HTTP request to the specified URL
  go2web -s <search-term>               search the term and print top 10 results
  go2web -s <search-term> --open <N>    fetch the Nth result from a search
  go2web -h                             show this help

Options:
  --accept {auto,html,json}   negotiate the response Content-Type (default: auto)
  --no-cache                  bypass the on-disk HTTP cache for this request
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="go2web", add_help=False)
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument("-u", "--url", metavar="URL")
    parser.add_argument("-s", "--search", nargs="+", metavar="TERM")
    parser.add_argument("--open", dest="open_index", type=int, metavar="N",
                        help="with -s: fetch the Nth result instead of listing")
    parser.add_argument("--accept", choices=ACCEPT_PRESETS.keys(), default="auto",
                        help="content negotiation preset")
    parser.add_argument("--no-cache", dest="no_cache", action="store_true",
                        help="bypass the on-disk HTTP cache")
    return parser


def _render(response_text: str, mime: str) -> str:
    if "json" in mime:
        try:
            parsed = json_mod.loads(response_text)
            return json_mod.dumps(parsed, indent=2, ensure_ascii=False) + "\n"
        except json_mod.JSONDecodeError:
            return response_text
    if mime in ("text/html", "application/xhtml+xml"):
        return html_to_text(response_text)
    return response_text


def cmd_url(url: str, *, accept: str = "auto", use_cache: bool = True) -> int:
    headers = {"Accept": ACCEPT_PRESETS[accept]}
    try:
        response = fetch(url, headers=headers, use_cache=use_cache)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if response.url != url:
        print(f"(redirected to {response.url})", file=sys.stderr)
    print(f"HTTP/{response.status} {response.reason}", file=sys.stderr)

    mime, _ = response.content_type()
    rendered = _render(response.text(), mime)

    sys.stdout.write(rendered)
    if not rendered.endswith("\n"):
        sys.stdout.write("\n")
    return 0


def cmd_search(terms: list[str], *, open_index: int | None = None,
               accept: str = "auto", use_cache: bool = True) -> int:
    try:
        results = search(terms)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not results:
        print("no results", file=sys.stderr)
        return 1

    if open_index is not None:
        if open_index < 1 or open_index > len(results):
            print(f"error: --open must be between 1 and {len(results)}", file=sys.stderr)
            return 2
        chosen = results[open_index - 1]
        print(f"(opening #{open_index}: {chosen.url})", file=sys.stderr)
        return cmd_url(chosen.url, accept=accept, use_cache=use_cache)

    width = len(str(len(results)))
    for i, r in enumerate(results, start=1):
        print(f"{str(i).rjust(width)}. {r.title}")
        print(f"{' ' * (width + 2)}{r.url}")
        if r.snippet:
            print(f"{' ' * (width + 2)}{r.snippet}")
        print()
    print(f"tip: re-run with --open <N> to fetch a result, e.g. go2web -s {' '.join(terms)} --open 1",
          file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.help or (args.url is None and args.search is None):
        sys.stdout.write(HELP_TEXT)
        return 0

    if args.url is not None and args.search is not None:
        print("error: -u and -s cannot be used together", file=sys.stderr)
        return 2

    if args.url is not None:
        if args.open_index is not None:
            print("error: --open only applies to -s", file=sys.stderr)
            return 2
        return cmd_url(args.url, accept=args.accept, use_cache=not args.no_cache)

    return cmd_search(
        args.search,
        open_index=args.open_index,
        accept=args.accept,
        use_cache=not args.no_cache,
    )


if __name__ == "__main__":
    sys.exit(main())
