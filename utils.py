"""
This script has some functions from the notebooks.
"""
from polygon.rest import RESTClient
from datetime import datetime, date, time, timedelta
from pytz import timezone
from functools import lru_cache
import pyarrow as pa
import pyarrow.parquet as pq
import pytz
import pandas as pd
import numpy as np
import os

POLYGON_DATA_PATH = "../data/polygon/"
SHARADAR_DATA_PATH = "../data/sharadar/"


def datetime_to_unix(dt):
    """Converts a ET-naive datetime object to msec timestamp

    Args:
        dt (datetime): datetime to convert

    Returns:
        int: Unix millisecond timestamp
    """

    if isinstance(dt, datetime):
        time_ET = timezone("US/Eastern").localize(dt)
        return int(time_ET.timestamp() * 1000)
    else:
        raise Exception("No datetime object specified.")


def download_m1_raw_data(ticker, from_, to, client, columns=['open', 'high', 'low', 'close', 'volume']):
    """Downloads raw 1-minute data from Polygon and converts to ET-time. Returns the resulting DataFrame.

    Args:
        ticker (str): _description_
        from_ (date/datetime): the starting date(time)
        to (date/datetime): end ending date(time)
        client (RESTClient): the client object
        columns (list): list of column names to keep

    Returns:
        DataFrame: the result
    """
    
    # If no time specified, fill in the start of premarket/end of postmarket
    if all(isinstance(value, date) for value in (from_, to)):
        start_unix = datetime_to_unix(dt=datetime.combine(from_, time(4)))
        end_unix = datetime_to_unix(dt=datetime.combine(to, time(20)))
    elif all(isinstance(value, datetime) for value in (from_, to)):
        start_unix = datetime_to_unix(from_)
        end_unix = datetime_to_unix(to)
    else:
        raise Exception("No datetime or date object specified.")
    
    try:
        m1 = pd.DataFrame(
            client.list_aggs(
                ticker=ticker,
                multiplier=1,
                timespan="minute",
                from_=start_unix,
                to=end_unix,
                limit=50000,
                adjusted=False,
            )
        )
    except Exception as e:
        print(ticker)
        print(e)
        return

    if not m1.empty:
        m1["timestamp"] = pd.to_datetime(
            m1["timestamp"], unit="ms"
        )  # Convert timestamp to UTC
        m1.rename(columns={"timestamp": "datetime"}, inplace=True)
        m1["datetime"] = m1["datetime"].dt.tz_localize(
            pytz.UTC
        )  # Make UTC aware (in order to convert)
        m1["datetime"] = m1["datetime"].dt.tz_convert("US/Eastern")  # Convert UTC to ET
        m1["datetime"] = m1["datetime"].dt.tz_localize(None)  # Make timezone naive
        m1.set_index("datetime", inplace=True)
        m1 = m1[columns]

        return m1

    else:
        print(
            f"There is no data for {ticker} from {from_.isoformat()} to {to.isoformat()}"
        )


@lru_cache
def get_market_calendar():
    """Retrieves the market hours

    Returns:
        DataFrame: the index contains Date objects and the columns Time objects.
    """
    market_hours = pd.read_csv(
        POLYGON_DATA_PATH + "../market/market_calendar.csv", index_col=0
    )
    market_hours.index = pd.to_datetime(market_hours.index).date
    market_hours.premarket_open = pd.to_datetime(
        market_hours.premarket_open, format="%H:%M:%S"
    ).dt.time
    market_hours.regular_open = pd.to_datetime(
        market_hours.regular_open, format="%H:%M:%S"
    ).dt.time
    market_hours.regular_close = pd.to_datetime(
        market_hours.regular_close, format="%H:%M:%S"
    ).dt.time
    market_hours.postmarket_close = pd.to_datetime(
        market_hours.postmarket_close, format="%H:%M:%S"
    ).dt.time
    return market_hours


@lru_cache
def get_market_minutes():
    trading_datetimes = pd.read_csv(POLYGON_DATA_PATH + "../market/trading_minutes.csv")
    return pd.to_datetime(trading_datetimes["datetime"])


def get_market_dates():
    """Get a list of market days from the market calendar

    Returns:
        list: list of Date objects
    """
    market_hours = get_market_calendar()
    return list(market_hours.index)



def first_trading_date_after_equal(dt):
    """Gets first trading day after or equal to input date. Return the input if out of range.

    Args:
        dt (Date): Date object to compare. Can be a non-trading date.

    Returns:
        Date: the trading date
    """
    trading_days = get_market_dates()
    if dt > trading_days[-1]:
        print("Out of range! Returning input.")
        return dt
    while dt not in trading_days:
        dt = dt + timedelta(days=1)
    return dt

def last_trading_date_before_equal(dt):
    """Gets last trading day before or equal to input date. Return the input if out of range.

    Args:
        dt (Date): Date object to compare. Can be a non-trading date.

    Returns:
        Date: the trading date
    """
    trading_days = get_market_dates()
    if dt < trading_days[-1]:
        print("Out of range! Returning input.")
        return dt
    while dt not in trading_days:
        dt = dt - timedelta(days=1)
    return dt

def first_trading_date_after(day):
    """Gets first trading date after the specified trading date.

    Args:
        day (date): MUST be a trading date
    
    Returns:
        date: the next trading date
    """
    trading_days = get_market_dates()
    return trading_days[trading_days.index(day) + 1]


def last_trading_date_before(day):
    """Gets last trading date before the specified trading date.

    Args:
        day (date): MUST be a trading date
    
    Returns:
        date: the previous trading date
    """
    trading_days = get_market_dates()
    return trading_days[trading_days.index(day) - 1]
    

def remove_extended_hours(bars):
    """
    Remove extended hours.
    """
    # Remove non-regular trading minutes. Only the post-market hours of early closes remain.
    bars = bars.between_time("9:30", "15:59").copy()

    # Remove early close post-market bars
    market_hours = get_market_calendar()
    early_closes = market_hours[market_hours["regular_close"] != time(15, 59)]
    for date_, early_close in early_closes.iterrows():
        bars = bars[
            ~(
                (bars.index > datetime.combine(date_, early_close["regular_close"]))
                & (bars.index <= datetime.combine(date_, time(19, 59)))
            )
        ]

    return bars


def get_tickers(v=5, cik_as_float=True):
    """
    Retrieve the ticker list. Default is 5.
    """
    tickers = pd.read_csv(
        f"../data/tickers_v{v}.csv",
        parse_dates=["start_date", "end_date"],
        index_col=0,
        keep_default_na=False,
        na_values=[
            "#N/A",
            "#N/A N/A",
            "#NA",
            "-1.#IND",
            "-1.#QNAN",
            "-NaN",
            "-nan",
            "1.#IND",
            "1.#QNAN",
            "<NA>",
            "N/A",
            "NULL",
            "NaN",
            "None",
            "n/a",
            "nan",
            "null",
        ],
    )
    tickers["start_date"] = pd.to_datetime(tickers["start_date"]).dt.date
    tickers["end_date"] = pd.to_datetime(tickers["end_date"]).dt.date
    if tickers.columns.isin(["start_data", "end_data"]).any():
        tickers["start_data"] = pd.to_datetime(tickers["start_data"]).dt.date
        tickers["end_data"] = pd.to_datetime(tickers["end_data"]).dt.date

    if cik_as_float:
        tickers["cik"] = tickers["cik"].apply(
            lambda str: float(str) if len(str) != 0 else np.nan
        )
    return tickers


def get_ticker_changes():
    ticker_changes = pd.read_csv(
        POLYGON_DATA_PATH + "../stockanalysis/ticker_changes.csv", index_col=0
    )
    ticker_changes.index = pd.to_datetime(ticker_changes.index).date
    return ticker_changes


def get_id(ticker, timeframe="daily"):
    """Get the most recent ID corresponding to the ticker

    Args:
        timeframe (int or str): 1 for 1-minute, 5 for 5-minute, else daily
        ticker (str): _description_

    Returns:
        string: the ID
    """
    if timeframe in [1, 5]:
        all_files = os.listdir(POLYGON_DATA_PATH + f"processed/m{timeframe}/")

    else:
        all_files = os.listdir(POLYGON_DATA_PATH + f"processed/d1/")

    all_IDs = [file[:-8] for file in all_files]
    IDs = [id for id in all_IDs if id[:-11] == ticker]
    return sorted(IDs)[-1]


def get_data(
    ticker_or_id,
    start=date(2000, 1, 1),
    end=date(2100, 1, 1),
    timeframe="daily",
    regular_hours_only=False,
    location="processed",
    columns=["open", "high", "low", "close", "volume", "tradeable", "halted"],
):
    """Retrieves the data from our database

    Args:
        ticker_or_id (str): the ticker or ID
        start (datetime/date, optional): the start date(time) (inclusive). Defaults to no bounds.
        end (datetime/date, optional): the end date(time) (inclusive). Defaults to no bounds.
        timeframe (str, optional): 1 for 1-minute, 5 for 5-minute. Defaults to daily bars.
        regular_hours_only (bool, optional): Whether we need to remove extended hours. Defaults to False.
        location (str): 'processed' or 'raw'. Defaults to 'processed'.
        columns (list): list of columns. Defaults to all.

    Returns:
        DataFrame: the output
    """

    # Determine if is ID or ticker
    if ticker_or_id[-1].isnumeric():
        id = ticker_or_id
    else:
        id = get_id(ticker_or_id, timeframe)

    # Read data
    if timeframe in [1, 5]:
        dataset = pq.ParquetDataset(
            POLYGON_DATA_PATH + f"{location}/m{timeframe}/{id}.parquet",
            filters=[("datetime", ">=", start), ("datetime", "<=", end)],
        )
    else:
        dataset = pq.ParquetDataset(
            POLYGON_DATA_PATH + f"{location}/d1/{id}.parquet",
            filters=[
                ("datetime", ">=", start),
                ("datetime", "<", end + timedelta(days=1)),
            ],
        )
    df = dataset.read(columns=["datetime"] + columns).to_pandas()

    # Remove extended hours if necessary
    if regular_hours_only and (timeframe in [1, 5]):
        return remove_extended_hours(df)
    else:
        return df
