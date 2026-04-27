"""File-backed HTTP response cache.

Implements a small subset of RFC 7234:
- freshness via Cache-Control: max-age and Expires
- conditional revalidation via ETag (If-None-Match) and Last-Modified (If-Modified-Since)
- skips entries marked no-store or private
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from pathlib import Path

from http_client import HttpResponse


CACHE_DIR = Path(os.environ.get("GO2WEB_CACHE_DIR", ".go2web-cache"))


@dataclass
class CacheEntry:
    response: HttpResponse
    stored_at: float

    def is_fresh(self, now: float | None = None) -> bool:
        ts = time.time() if now is None else now
        max_age = _max_age(self.response)
        if max_age is not None:
            return (ts - self.stored_at) < max_age
        expires = self.response.header("Expires")
        if expires:
            try:
                expires_ts = parsedate_to_datetime(expires).timestamp()
                return ts < expires_ts
            except (TypeError, ValueError):
                return False
        return False

    def validators(self) -> dict[str, str]:
        out: dict[str, str] = {}
        etag = self.response.header("ETag")
        if etag:
            out["If-None-Match"] = etag
        last_mod = self.response.header("Last-Modified")
        if last_mod:
            out["If-Modified-Since"] = last_mod
        return out


def _max_age(response: HttpResponse) -> int | None:
    cc = response.header("Cache-Control") or ""
    for directive in cc.split(","):
        d = directive.strip().lower()
        if d.startswith("max-age="):
            try:
                return int(d.split("=", 1)[1])
            except ValueError:
                return None
    return None


def _is_cacheable(response: HttpResponse) -> bool:
    if response.status not in (200, 203, 300, 301, 410):
        return False
    cc = (response.header("Cache-Control") or "").lower()
    if "no-store" in cc or "private" in cc:
        return False
    return True


def _path_for(url: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{digest}.json"


def load(url: str) -> CacheEntry | None:
    path = _path_for(url)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    response = HttpResponse(
        status=data["status"],
        reason=data["reason"],
        headers=[tuple(h) for h in data["headers"]],
        body=base64.b64decode(data["body_b64"]),
        url=data["url"],
    )
    return CacheEntry(response=response, stored_at=data["stored_at"])


def store(response: HttpResponse) -> None:
    if not _is_cacheable(response):
        return
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "url": response.url,
        "status": response.status,
        "reason": response.reason,
        "headers": response.headers,
        "body_b64": base64.b64encode(response.body).decode("ascii"),
        "stored_at": time.time(),
    }
    _path_for(response.url).write_text(json.dumps(record), encoding="utf-8")


def refresh_after_304(entry: CacheEntry, fresh_headers: list[tuple[str, str]]) -> HttpResponse:
    merged: dict[str, str] = {k: v for k, v in entry.response.headers}
    for k, v in fresh_headers:
        merged[k] = v
    refreshed = HttpResponse(
        status=200,
        reason="OK (revalidated)",
        headers=list(merged.items()),
        body=entry.response.body,
        url=entry.response.url,
    )
    store(refreshed)
    return refreshed
