import pyarrow.parquet as pq
from datetime import datetime, date, time, timedelta
from tickers import get_id
from times import get_market_calendar

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
        "volume",
        "tradeable",
        "halted",
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
