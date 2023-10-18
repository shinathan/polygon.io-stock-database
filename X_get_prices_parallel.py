"""
Downloads 1-minute bars but parallel. Specify the amount of maximum concurrent requests in LIMIT.

Note: The DATA_PATH is different from the Jupyter notebook because a Jupyter notebook has its own kernel
and hence own location. This can be solved by using absolute paths or removing the ../../
"""

import aiohttp
import asyncio
import pandas as pd
import numpy as np
from polygon.rest import RESTClient
from datetime import datetime, time
import pytz
from utils import datetime_to_unix, get_tickers

DATA_PATH = "../data/polygon/"

with open(DATA_PATH + "secret.txt") as f:
    KEY = next(f).strip()

client = RESTClient(api_key=KEY)


async def fetch_data(session, url):
    async with session.get(url) as response:
        return await response.json()


async def download_data(id, ticker, start_date, end_date, KEY, semaphore):
    async with semaphore:
        async with aiohttp.ClientSession() as session:
            data = []
            url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/minute/{start_date}/{end_date}?adjusted=false&sort=asc&limit=50000&apiKey={KEY}"

            while url:
                response = await fetch_data(session, url)

                if "results" in response.keys():
                    data.extend(response["results"])

                if "next_url" in response.keys():
                    url = response.get("next_url") + f"&apiKey={KEY}"
                else:
                    url = False

            if len(data) > 0:
                data = pd.DataFrame(data)
                data.rename(
                    columns={
                        "t": "datetime",
                        "o": "open",
                        "h": "high",
                        "l": "low",
                        "c": "close",
                        "v": "volume",
                    },
                    inplace=True,
                )
                data["datetime"] = pd.to_datetime(data["datetime"], unit="ms")
                data["datetime"] = data["datetime"].dt.tz_localize(pytz.UTC)
                data["datetime"] = data["datetime"].dt.tz_convert("US/Eastern")
                data["datetime"] = data["datetime"].dt.tz_localize(None)
                data.set_index(data["datetime"], inplace=True)
                data = data[["open", "high", "low", "close", "volume"]]
                data.to_parquet(
                    DATA_PATH + f"raw/m2/{id}.parquet",
                    engine="pyarrow",
                    compression="brotli",
                )

                print(id)


async def main():
    LIMIT = 5  # Set your desired maximum parallel requests limit
    semaphore = asyncio.Semaphore(LIMIT)

    tasks = []
    for index, row in get_tickers(v=3).iterrows():
        id = row["ID"]
        ticker = row["ticker"]
        start_date = datetime_to_unix(datetime.combine(row["start_date"], time(4)))
        end_date = datetime_to_unix(datetime.combine(row["end_date"], time(20)))
        tasks.append(download_data(id, ticker, start_date, end_date, KEY, semaphore))

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
