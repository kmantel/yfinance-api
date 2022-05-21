import argparse
import datetime
import os
import re

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


option_ticker_regex = re.compile(r'\.?([A-Za-z]+)(\d+)([CcPp])(\d+)')
option_chain_index = {
    'C': 0,
    'P': 1
}

yfi_tickers = {}


def parse_option_ticker(ticker: str):
    """Parses **ticker** into options info if applicable

    Args:
        ticker (str)

    Returns:
        - (underlying asset ticker, expiration date, C/P, strike price)
        if **ticker** is an option
        - None if not
    """
    try:
        ticker, option_expiration, option_type, strike = option_ticker_regex.match(ticker).groups()
    except AttributeError:
        return None
    else:
        date_fmts = ['%y%m%d', '%Y%m%d']
        for fmt in date_fmts:
            try:
                option_expiration = datetime.datetime.strptime(option_expiration, fmt)
                break
            except (AttributeError, ValueError):
                pass
        else:
            return {'error': 'Invalid expiration date'}

        return ticker, option_expiration, option_type, strike


async def get_api_key(api_key_header: str = Security(api_key_query)):
    if api_key_header not in set(
        [k for k in os.environ[API_KEY_ENV_VAR].split(":") if len(k) > 0]
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )


@cache(expire=args.cache_ttl)
async def _update_yfinance_object(ticker: str):
    yfi_tickers[ticker] = yfinance.Ticker(ticker)


@yfi_app.get("/quote/{ticker}", dependencies=[Security(get_api_key)])
@cache(expire=args.cache_ttl)
async def quote(ticker: str):
    try:
        ticker, option_expiration, option_type, strike = parse_option_ticker(ticker)
    except TypeError:
        # is standard stock
        await _update_yfinance_object(ticker)
        return yfi_tickers[ticker].info["regularMarketPrice"]
    else:
        option_code = f'{ticker}{option_expiration.strftime("%y%m%d")}{option_type.upper()}{strike}'

        await _update_yfinance_object(ticker)
        try:
            chain = yfi_tickers[ticker].option_chain(option_expiration.strftime('%Y-%m-%d'))[option_chain_index[option_type]]
        except ValueError as e:
            return {'error': str(e)}
        try:
            return chain.loc[chain['contractSymbol'] == option_code]['lastPrice'].iloc[0]
        except IndexError:
            return {'error': 'Option does not exist'}


@yfi_app.get("/info/{ticker}", dependencies=[Security(get_api_key)])
@cache(expire=args.cache_ttl)
async def info(ticker: str):
    try:
        ticker, _, _, _ = parse_option_ticker(ticker)
    except TypeError:
        pass

    await _update_yfinance_object(ticker)
    return yfi_tickers[ticker].info


@yfi_app.on_event("startup")
async def startup():
    FastAPICache.init(InMemoryBackend())


if __name__ == "__main__":
    uvicorn.run("server:yfi_app", host="0.0.0.0", port=args.port)
