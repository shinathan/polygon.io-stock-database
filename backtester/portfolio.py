from datetime import datetime, time
import pandas as pd


class Portfolio:
    def __init__(self, start_date, initial_capital=10000.0):

        # Positions only change with a fill. Positions = amount of assets.
        self.current_cash = initial_capital
        self.current_positions = {}  # {'AAPL': 10, 'NFLX': -5, ...}

        # Holdings = value of positions. However, we only update this when we want to.
        self._current_positions_value = 0
        self._current_equity = initial_capital

        # Log of positions and holdings.
        self.portfolio_log = []  # list(dict(date, equity, cash, pos. value, positions))
        self.portfolio_log.append(
            {
                "datetime": start_date,
                "equity": self.current_cash,
                "cash": self.current_cash,
                "positions_value": 0,
                "positions": {},
            }
        )

        # Log of the fills
        self.fills_log = []  # list(dict(date, symbol, side, qty, fill, comm.))

    def update_from_fill(self, dt, side, symbol, fill_quantity, fill_price, fees):
        """Updates portfolio from fill.
        side = "BUY" or "SELL"
        fill_quantity, fill_price and fees should always be positive.
        """
        if fill_quantity < 0 or fill_price < 0 or fees < 0:
            raise Exception(
                "fill_quantity, fill_price and fees should always be positive."
            )

        direction = 1 if side == "BUY" else -1

        # Update cash
        self.current_cash -= fill_price * fill_quantity * direction
        self.current_cash -= fees

        # Update positions
        if symbol in self.current_positions.keys():
            self.current_positions[symbol] += direction * fill_quantity
        else:
            self.current_positions[symbol] = direction * fill_quantity

        # Log transaction
        self.fills_log.append(
            {
                "datetime": dt,
                "symbol": symbol,
                "side": side,
                "quantity": fill_quantity,
                "fill_price": fill_price,
                "fees": fees,
            }
        )

    def _update_holdings_from_market(self, dt, data):
        # Update holdings if we have positions (and data)
        if data and self.current_positions:
            position_values = {
                symbol: position * (data[symbol].loc[dt, "close"])
                for (symbol, position) in self.current_positions.items()
                if position != 0
            }
            self._current_positions_value = sum(position_values.values())
        else:
            self._current_positions_value = 0

        # Update equity
        self._current_equity = self.current_cash + self._current_positions_value

    def append_portfolio_log(self, dt, data):
        # Update holdings and append portfolio log
        self._update_holdings_from_market(dt, data)

        self.portfolio_log.append(
            {
                "datetime": dt,
                "equity": self._current_equity,
                "cash": self.current_cash,
                "positions_value": self._current_positions_value,
                "positions": self.current_positions.copy(),
            }
        )

    ### These functions should only be executed after the backtest
    def get_df_from_holdings_log(self):
        """Creates a DataFrame from portfolio_log. Percentages are base 100 for readability."""
        df = pd.DataFrame(self.portfolio_log)
        df.set_index("datetime", inplace=True)
        df["return"] = df["equity"].pct_change()
        df["return_cum"] = (1.0 + df["return"]).cumprod() - 1

        df["return"] = df["return"] * 100
        df["return_cum"] = df["return_cum"] * 100
        df = df.fillna(value=0)

        df[["equity", "cash", "positions_value", "return", "return_cum"]] = round(
            df[["equity", "cash", "positions_value", "return", "return_cum"]], 3
        )
        return df

    def get_df_from_fills_log(self):
        df = pd.DataFrame(self.fills_log)
        return df.set_index("datetime")
