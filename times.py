from datetime import datetime, date, time, timedelta
from functools import lru_cache
import pandas as pd

POLYGON_DATA_PATH = "../data/polygon/"


@lru_cache
def get_market_calendar(format="time", timeframe=1):
    """Retrieves the market hours

    Args:
        format (string): "time" or "datetime". If datetime, the columns are datetime objects. Else time objects.
        timeframe (int): the timeframe of the bars in minutes. Defaults to 1.

    Returns:
        DataFrame: the index contains Date objects and the columns Time objects.
    """
    market_hours = pd.read_csv(
        POLYGON_DATA_PATH + "market/market_calendar.csv", index_col=0
    )
    market_hours.index = pd.to_datetime(market_hours.index).date

    # Get datetime objects from the date and time
    for col in market_hours.columns:
        market_hours[col] = pd.to_datetime(
            market_hours.index.astype(str) + " " + market_hours[col].astype(str)
        )

    # # Round down if timeframe is not 1 minute
    market_hours["regular_close"] = market_hours["regular_close"].dt.floor(
        f"{timeframe}min"
    )
    market_hours["postmarket_close"] = market_hours["postmarket_close"].dt.floor(
        f"{timeframe}min"
    )

    # Return time only if specified
    if format == "datetime":
        return market_hours
    elif format == "time":
        for col in market_hours.columns:
            market_hours[col] = market_hours[col].dt.time
        return market_hours

@lru_cache
def get_market_dates(start_date=date(2000, 1, 1), end_date=date(2100, 1, 1)):
    """Get a list of market days from the market calendar

    Args:
        start_date (Date): the start date
        end_date (Date): the end date

    Returns:
        list: list of Date objects
    """
    market_hours = get_market_calendar().index
    market_hours = market_hours[
        (market_hours >= start_date) & (market_hours <= end_date)
    ]
    return list(market_hours)


@lru_cache
def get_market_minutes(start_date, end_date, extended_hours=True, timeframe=1):
    """Get a DatetimeIndex of trading minutes

    Args:
        start_date (Date): the start date
        end_date (Date): the end date
        extended_hours (bool, optional): whether to include extended hours. Defaults to True.
        timeframe (int): the length in minutes of the bars. Defaults to 1.
    Returns:
        DatetimeIndex: the result
    """
    trading_datetimes = pd.read_parquet(
        POLYGON_DATA_PATH + "market/trading_minutes.parquet"
    )
    trading_datetimes = pd.to_datetime(trading_datetimes.index)
    trading_datetimes = pd.DataFrame(index=trading_datetimes)

    # Filter for start to end date
    trading_datetimes = trading_datetimes[
        (trading_datetimes.index >= datetime.combine(start_date, time(4)))
        & (trading_datetimes.index <= datetime.combine(end_date, time(19, 59)))
    ]

    # Remove extended hours if necessary
    if not extended_hours:
        from data import remove_extended_hours  # Avoid circular import

        trading_datetimes = remove_extended_hours(trading_datetimes)

    # Resample if necessary. The reason we do not use .resample() is because it also fills gaps with missing data.
    return (
        trading_datetimes.groupby(trading_datetimes.index.floor(f"{timeframe}Min"))
        .last()
        .index
    )


def first_trading_date_after_equal(dt):
    """Gets first trading day after or equal to input date. Return the input if out of range.

    Args:
        dt (Date): Date object to compare. Can be a non-trading date.

    Returns:
        Date: the trading date
    """
    trading_days = get_market_dates()
    if dt < trading_days[0] or dt >= trading_days[-1]:
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
    if dt <= trading_days[0] or dt > trading_days[-1]:
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

