#!/usr/bin/env python3
"""go2web - HTTP over raw TCP sockets."""
from __future__ import annotations

import argparse
import sys

from html_render import html_to_text
from http_client import fetch


HELP_TEXT = """go2web - HTTP over TCP sockets

Usage:
  go2web -u <URL>          make an HTTP request to the specified URL and print the response
  go2web -s <search-term>  make an HTTP request to search the term and print top 10 results
  go2web -h                show this help
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="go2web", add_help=False)
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument("-u", "--url", metavar="URL")
    parser.add_argument("-s", "--search", nargs="+", metavar="TERM")
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


def cmd_search(terms: list[str]) -> int:
    print(f"[not implemented yet] would search: {' '.join(terms)}")
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
        return cmd_url(args.url)

    return cmd_search(args.search)


if __name__ == "__main__":
    sys.exit(main())
