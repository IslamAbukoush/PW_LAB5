#!/usr/bin/env python3
"""go2web - HTTP over raw TCP sockets."""
from __future__ import annotations

import argparse
import sys

from html_render import html_to_text
from http_client import fetch
from search import search


HELP_TEXT = """go2web - HTTP over TCP sockets

Usage:
  go2web -u <URL>                       make an HTTP request to the specified URL
  go2web -s <search-term>               search the term and print top 10 results
  go2web -s <search-term> --open <N>    fetch the Nth result from a search
  go2web -h                             show this help
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="go2web", add_help=False)
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument("-u", "--url", metavar="URL")
    parser.add_argument("-s", "--search", nargs="+", metavar="TERM")
    parser.add_argument("--open", dest="open_index", type=int, metavar="N",
                        help="with -s: fetch the Nth result instead of listing")
    return parser


def cmd_url(url: str) -> int:
    try:
        response = fetch(url)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if response.url != url:
        print(f"(redirected to {response.url})", file=sys.stderr)
    print(f"HTTP/{response.status} {response.reason}", file=sys.stderr)

    mime, _ = response.content_type()
    text = response.text()
    rendered = html_to_text(text) if mime in ("text/html", "application/xhtml+xml") else text

    sys.stdout.write(rendered)
    if not rendered.endswith("\n"):
        sys.stdout.write("\n")
    return 0


def cmd_search(terms: list[str], open_index: int | None = None) -> int:
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
        return cmd_url(chosen.url)

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
        return cmd_url(args.url)

    return cmd_search(args.search, open_index=args.open_index)


if __name__ == "__main__":
    sys.exit(main())
