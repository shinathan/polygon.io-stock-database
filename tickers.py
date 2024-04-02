import pandas as pd
import numpy as np
import os

POLYGON_DATA_PATH = "../data/polygon/"


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
