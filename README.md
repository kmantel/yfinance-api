# yfinance API

A (very) minimal wrapper around the [yfinance library](https://github.com/ranaroussi/yfinance/) for use as a self-hosted API, using [FastAPI](https://github.com/tiangolo/fastapi). Currently, only querying the current market price is supported.

Basic request authentication consists of api key verification, where api keys are listed, delimited by ':' in the environment variable `YFI_API_KEY` on server startup.

## Example

Server startup:

```bash
YFI_API_KEY='foo:bar' python server.py --cache-ttl 60
```

Query:

```bash
$ curl http://127.0.0.1:8080/quote/vti?token=foo
223.88
```
