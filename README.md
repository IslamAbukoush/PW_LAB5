# go2web

PR Lab 5 — HTTP over raw TCP sockets. A small CLI that fetches URLs and runs web searches without using any HTTP/HTTPS library: TCP + TLS only.

## Usage

```
go2web -u <URL>          make an HTTP request to the specified URL and print the response
go2web -s <search-term>  make an HTTP request to search the term and print top 10 results
go2web -h                show this help
```

## Running

- Windows: `go2web.bat -h` (or just `go2web -h` from `cmd`)
- Unix:    `./go2web -h`

Both are thin wrappers around `go2web.py` and require Python 3.10+ on `PATH`.
