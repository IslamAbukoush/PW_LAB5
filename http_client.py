"""HTTP/1.1 client built directly on TCP sockets (no http.client / urllib / requests)."""
from __future__ import annotations

import socket
import ssl
from dataclasses import dataclass, field


DEFAULT_USER_AGENT = "go2web/0.1 (+https://example.invalid)"
DEFAULT_TIMEOUT = 15.0
MAX_RESPONSE_BYTES = 5 * 1024 * 1024


@dataclass
class ParsedURL:
    scheme: str
    host: str
    port: int
    path: str

    @property
    def is_tls(self) -> bool:
        return self.scheme == "https"


@dataclass
class HttpResponse:
    status: int
    reason: str
    headers: list[tuple[str, str]] = field(default_factory=list)
    body: bytes = b""
    url: str = ""

    def header(self, name: str) -> str | None:
        target = name.lower()
        for key, value in self.headers:
            if key.lower() == target:
                return value
        return None

    def content_type(self) -> tuple[str, str | None]:
        raw = self.header("Content-Type") or ""
        if not raw:
            return "", None
        parts = [p.strip() for p in raw.split(";")]
        mime = parts[0].lower()
        charset: str | None = None
        for p in parts[1:]:
            if p.lower().startswith("charset="):
                charset = p.split("=", 1)[1].strip().strip('"')
                break
        return mime, charset

    def text(self) -> str:
        _, charset = self.content_type()
        for enc in (charset, "utf-8", "latin-1"):
            if not enc:
                continue
            try:
                return self.body.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue
        return self.body.decode("utf-8", errors="replace")


def parse_url(url: str) -> ParsedURL:
    if "://" not in url:
        url = "http://" + url
    scheme, rest = url.split("://", 1)
    scheme = scheme.lower()
    if scheme not in ("http", "https"):
        raise ValueError(f"unsupported scheme: {scheme}")

    host_part, _, path = rest.partition("/")
    path = "/" + path if path else "/"

    if "@" in host_part:
        host_part = host_part.split("@", 1)[1]

    if host_part.startswith("["):
        # IPv6 literal: [::1]:8080
        end = host_part.find("]")
        host = host_part[1:end]
        after = host_part[end + 1 :]
        port_str = after[1:] if after.startswith(":") else ""
    elif ":" in host_part:
        host, port_str = host_part.rsplit(":", 1)
    else:
        host, port_str = host_part, ""

    port = int(port_str) if port_str else (443 if scheme == "https" else 80)
    return ParsedURL(scheme=scheme, host=host, port=port, path=path)


def _open_socket(target: ParsedURL, timeout: float) -> socket.socket:
    sock = socket.create_connection((target.host, target.port), timeout=timeout)
    if target.is_tls:
        ctx = ssl.create_default_context()
        sock = ctx.wrap_socket(sock, server_hostname=target.host)
    return sock


def _build_request(target: ParsedURL, headers: dict[str, str]) -> bytes:
    base_headers = {
        "Host": target.host if target.port in (80, 443) else f"{target.host}:{target.port}",
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "*/*",
        "Accept-Encoding": "identity",
        "Connection": "close",
    }
    base_headers.update(headers or {})
    lines = [f"GET {target.path} HTTP/1.1"]
    for k, v in base_headers.items():
        lines.append(f"{k}: {v}")
    return ("\r\n".join(lines) + "\r\n\r\n").encode("ascii")


def _recv_all(sock: socket.socket, limit: int) -> bytes:
    chunks: list[bytes] = []
    received = 0
    while received < limit:
        try:
            data = sock.recv(8192)
        except (socket.timeout, TimeoutError):
            break
        if not data:
            break
        chunks.append(data)
        received += len(data)
    return b"".join(chunks)


def _split_head_body(raw: bytes) -> tuple[bytes, bytes]:
    sep = raw.find(b"\r\n\r\n")
    if sep == -1:
        return raw, b""
    return raw[:sep], raw[sep + 4 :]


def _parse_status(line: str) -> tuple[int, str]:
    parts = line.split(" ", 2)
    if len(parts) < 2:
        raise ValueError(f"malformed status line: {line!r}")
    return int(parts[1]), (parts[2] if len(parts) > 2 else "")


def _parse_headers(head: bytes) -> tuple[int, str, list[tuple[str, str]]]:
    text = head.decode("iso-8859-1")
    lines = text.split("\r\n")
    status, reason = _parse_status(lines[0])
    headers: list[tuple[str, str]] = []
    for line in lines[1:]:
        if not line or ":" not in line:
            continue
        k, v = line.split(":", 1)
        headers.append((k.strip(), v.strip()))
    return status, reason, headers


def _decode_chunked(body: bytes) -> bytes:
    out = bytearray()
    i = 0
    n = len(body)
    while i < n:
        eol = body.find(b"\r\n", i)
        if eol == -1:
            break
        size_line = body[i:eol].split(b";", 1)[0].strip()
        try:
            size = int(size_line, 16)
        except ValueError:
            break
        i = eol + 2
        if size == 0:
            break
        out.extend(body[i : i + size])
        i += size + 2
    return bytes(out)


def fetch(url: str, *, headers: dict[str, str] | None = None, timeout: float = DEFAULT_TIMEOUT) -> HttpResponse:
    target = parse_url(url)
    request = _build_request(target, headers or {})

    sock = _open_socket(target, timeout)
    try:
        sock.sendall(request)
        raw = _recv_all(sock, MAX_RESPONSE_BYTES)
    finally:
        try:
            sock.close()
        except OSError:
            pass

    head, body = _split_head_body(raw)
    status, reason, hdrs = _parse_headers(head)

    transfer_encoding = ""
    content_length: int | None = None
    for k, v in hdrs:
        kl = k.lower()
        if kl == "transfer-encoding":
            transfer_encoding = v.lower()
        elif kl == "content-length":
            try:
                content_length = int(v)
            except ValueError:
                content_length = None

    if "chunked" in transfer_encoding:
        body = _decode_chunked(body)
    elif content_length is not None:
        body = body[:content_length]

    return HttpResponse(status=status, reason=reason, headers=hdrs, body=body, url=url)
