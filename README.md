# Building a stock database using Polygon.io
*Requirements: Python 3.11.4, a Polygon.io and a stockanalysis.com subscription*

The goal is to create a financial database of 1-minute OHLCV data from 2004 and beyond, delisted or listed, for common stocks and ADR common stocks. I use Polygon for price data, which is "ticker-centric". All data from Polygon is point-in-time by ticker. This means we have to take care of renamings ourselves (very annoying). Some vendors already do renamings (e.g. Tiingo). And almost all of the vendors that do renamings have a small bit of survivorship-bias, because when a ticker is re-used the old data is lost. Polygon does not have this problem.

I will also make sure that it is easy to update without redownloading everything (that is what the 'Update' paragraph in each notebook is for!). However it is *not* optimized to update daily. I only intend to update monthly. My backtesting and live trading framework will be different. E.g. for a trading system that trades daily bars, I will only download the required daily bars every day in the live system and not update the entire database for all tickers. For a day-trading system I will use screeners, which also do not require downloading all 6000+ stocks. In would be very hard to constantly stream 6000+ stocks at the same time, if not impossible.

With a previous project I tried to convert tick quote data to quotes and then merge them with bars to get a realistic bid-ask spread. I have decided to not use quote data anymore. It is simply too expensive, cumbersome or simply impossible. I would have to download all tick data for all dates for all tickers in order to get quotebars, which will be several TBs. Instead, I will just trade using 1-minute OHLC. When backtesting, I will assume a spread of 1 tick or a few cents. This is okay, because I simply will not trade HFT or systems with an average profit less than 0.3% for liquid stocks or less than 0.1% for liquid futures/CFDs. High frequency systems also won't work in Europe due to almost not having access to PFOF brokers. I also will avoid illiquid stocks. If I want a more realistic estimate, I will sample the bid-ask spread throughout the day. 

I will organize my data in the following way (only folders and important files shown):

```
├── data_import (code directory)
├── data
│   ├── market
│   │   ├── market_hours.csv
│   │   ├── trading_minutes.csv
│   ├── polygon
│   │   ├── raw
│   │   |   ├── m1
│   │   |   ├── adjustments
│   │   |   ├── tickers
│   │   ├── processed
│   │   |   ├── m1
│   │   |   ├── m5
│   │   |   ├── d1
│   │   ├── secret.txt
│   ├── stockanalysis
│   │   ├── raw
```

The <code>market</code> folder will contain the market hours. All data will be stored in the corresponding directory based on the data vendor. Polygon is for stock data. Stockanalysis is for stock renamings. Raw data is never adjusted. When updating raw data, we should be able to just append it. Processed data is always adjusted which means it is usable by the backtester. When new data comes in, all processed data will be adjusted again. The backtester should only use what is in the <code>processed</code> folders. The <code>secret.txt</code> files contain the API keys. All folders have to be created manually. 

Because the rate limit for the free Polygon plan is quite low, you need at least the starter subscription (29 USD/month). They actually have a 20% discount for students.

The most important file is <code>tickers_v{version}.csv</code> which resides in the <code>data</code> folder. This is a csv containing all tickers. This is the file which you have to loop through when filtering/backtesting. It is not an easy task to build the ticker lists. Or even handle to all other problems such as renamings, delistings, early closes, dividends and splits. I have spent quite some time on this. You *cannot* just loop through the most recent ticker list that Polygon provides. 

The series of notebooks:
1. An introduction to the problems with the Polygon ticker list.
2. Get market hours.
3. Solve the ticker problems to create a correct list of tickers.
4. Add ETPs.
5. Download adjustments.
6. Download raw prices.
7. Processing data.
8. Renamings.
9. Aggregate to higher timeframes.
10. Some extra handy functions.
11. Simulating point-in-time screening for day trading and backtesting.
12. Vectorized backtesting
13. Loop-based backtesting

*Note: a data point at 15:59 with OHLC means that the open was at 15:59:00 and close at 16:00:00.*