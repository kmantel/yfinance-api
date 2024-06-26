import argparse
import os

import uvicorn
import yfinance
from fastapi import FastAPI, HTTPException, Security
from fastapi.security.api_key import APIKeyQuery
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.decorator import cache
from starlette import status

API_KEY_ENV_VAR = "YFI_API_KEY"

parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--port", "-p", type=int, default=8080, help="port to listen on")
parser.add_argument(
    "--cache-ttl",
    "-t",
    type=float,
    default=900,
    help="lifetime (in seconds) for cached queries",
)
args = parser.parse_args()


yfi_app = FastAPI()
api_key_query = APIKeyQuery(name="token")


async def get_api_key(api_key_header: str = Security(api_key_query)):
    if api_key_header not in set(
        [k for k in os.environ[API_KEY_ENV_VAR].split(":") if len(k) > 0]
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )


def _get_ticker_price(ticker: yfinance.Ticker):
    try:
        return round(ticker.basic_info['lastPrice'], ndigits=2)
    except (KeyError, TypeError):
        return None


@yfi_app.get("/quote/{ticker}", dependencies=[Security(get_api_key)])
@cache(expire=args.cache_ttl)
async def quote(ticker: str):
    yfi_obj = yfinance.Ticker(ticker)
    return _get_ticker_price(yfi_obj)


@yfi_app.get("/quotes/{tickers}", dependencies=[Security(get_api_key)])
@cache(expire=args.cache_ttl)
async def quotes(tickers: str):
    yfi_obj = yfinance.Tickers(tickers.split(','))
    return {
        symbol: _get_ticker_price(ticker)
        for symbol, ticker in yfi_obj.tickers.items()
    }


@yfi_app.on_event("startup")
async def startup():
    FastAPICache.init(InMemoryBackend())


if __name__ == "__main__":
    uvicorn.run("server:yfi_app", host="0.0.0.0", port=args.port)
