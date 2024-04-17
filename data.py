import pyarrow.parquet as pq
from datetime import datetime, date, time, timedelta
from tickers import get_id
from times import get_market_calendar
import pandas as pd
import pytz
from pytz import timezone

POLYGON_DATA_PATH = "../data/polygon/"


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


def get_data(
    ticker_or_id,
    start_date=date(2000, 1, 1),
    end_date=date(2100, 1, 1),
    timeframe="daily",
    extended_hours=False,
    location="processed",
    columns=[
        "open",
        "high",
        "low",
        "close",
        "close_original",
        "turnover",
        "tradeable",
    ],
):
    """Retrieves the data from our database

    Args:
        ticker_or_id (str): the ticker or ID
        start_date (date, optional): the start date (inclusive). Defaults to no bounds.
        end_date (date, optional): the end date (inclusive). Defaults to no bounds.
        timeframe (str, optional): 1 for 1-minute, 5 for 5-minute. Defaults to daily bars.
        extended_hours (bool, optional): Whether we need to include extended hours (not applicable to daily timeframes). Defaults to True.
        location (str): 'processed' or 'raw'. Defaults to 'processed'.
        columns (list): list of columns. Defaults to all.

    Returns:
        DataFrame: the output
    """
    if not (isinstance(timeframe, int) or timeframe == "daily"):
        raise ValueError("The input must be an integer or 'daily'!")

    # Determine if is ID or ticker
    if ticker_or_id[-1].isnumeric():
        id = ticker_or_id
    else:
        id = get_id(ticker_or_id, timeframe)

    # Read data
    if timeframe in [1, 5]:
        dataset = pq.ParquetDataset(
            POLYGON_DATA_PATH + f"{location}/m{timeframe}/{id}.parquet",
            filters=[
                ("datetime", ">=", datetime.combine(start_date, time(4))),
                ("datetime", "<=", datetime.combine(end_date, time(20))),
            ],
        )
    else:
        dataset = pq.ParquetDataset(
            POLYGON_DATA_PATH + f"{location}/d1/{id}.parquet",
            filters=[
                ("datetime", ">=", start_date),
                ("datetime", "<", end_date + timedelta(days=1)),
            ],
        )
    df = dataset.read(columns=["datetime"] + columns).to_pandas()

    # Remove extended hours if necessary
    if not extended_hours and (timeframe in [1, 5]):
        return remove_extended_hours(df)
    else:
        return df

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


def download_m1_raw_data(
    ticker, from_, to, client, columns=["open", "high", "low", "close", "volume"]
):
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

def get_latest_value(dictionary, day):
    """Get the value corresponding to the latest key before <day> in a dictionary"""
    dates = [date.fromisoformat(day) for day in dictionary.keys()]
    try:
        key = max(filter(lambda x: x < day, dates))
    except ValueError:
        # If there is no universe before <day>, simply pick the first one.
        key = dates[0]
    return dictionary[key.isoformat()]