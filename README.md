# go2web

PR Lab 5 — HTTP over raw TCP sockets. A CLI tool that fetches URLs and performs web searches without using any HTTP/HTTPS libraries. Built entirely on raw TCP sockets with TLS support.

## Overview

`go2web` is a command-line utility demonstrating low-level HTTP implementation using Python. It handles HTTP requests, TLS/SSL encryption, and HTML parsing—all implemented from scratch without relying on high-level HTTP libraries like `requests` or `urllib3`.

## Requirements

- **Python 3.10+**
- Standard library only (no external dependencies)

## Installation

1. Ensure Python 3.10+ is available on your `PATH`
2. Clone or download this repository
3. Run the appropriate script for your OS (see Usage below)

## Usage

```
go2web -u <URL>          Fetch a URL and print the HTTP response
go2web -s <search-term>  Search for a term and print the top 10 results
go2web -h                Show this help message
```

### Examples

```bash
# Fetch a website
go2web -u https://example.com

# Search the web
go2web -s "python programming"
```

## Running

Choose the appropriate command for your operating system:

- **Windows**: `go2web.bat -h` (or `go2web -h` from `cmd`)
- **Unix/Linux/macOS**: `./go2web -h`

Both scripts are thin wrappers that delegate to `go2web.py`.

## Project Structure

- **`go2web.py`** — Main CLI entry point; parses arguments and routes to appropriate functionality
- **`http_client.py`** — Raw TCP socket implementation of HTTP client with TLS support
- **`html_render.py`** — HTML parser and renderer for formatting search results
- **`search.py`** — Web search functionality; queries search engine via HTTP
- **`cache.py`** — Simple caching system to reduce redundant requests
- **`guide.md`** — Detailed implementation guide and documentation

## How It Works

1. **Raw TCP Connection**: Establishes direct socket connections to target servers
2. **TLS Handshake**: Implements or uses Python's SSL module for secure connections
3. **HTTP Protocol**: Manually constructs HTTP requests and parses responses
4. **HTML Processing**: Extracts and renders relevant data from HTML responses
