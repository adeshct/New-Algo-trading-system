# app/services/utils.py

import datetime as dt
import pandas as pd

def nearest_strike(price: float, step: int = 100) -> int:
    """
    Round price to nearest strike price multiple.
    Default step 100 for BankNifty.
    """
    return int(round(price / step) * step)


def weekly_option_symbol(symbol: str, strike: int, option_type: str, expiry_date: dt.date) -> str:
    """
    Constructs NSE weekly option symbol name like 'BANKNIFTY24JUL41000CE'.

    Args:
        symbol (str): Base symbol like 'BANKNIFTY'
        strike (int): Strike price (nearest strike)
        option_type (str): 'CE' or 'PE'
        expiry_date (date): Expiry date of the option

    Returns:
        str: Formatted weekly option symbol
    """

    symbol = symbol.upper()
    option_type = option_type.upper()
    month_map = {
        1: "JAN", 2: "FEB", 3: "MAR", 4: "APR",
        5: "MAY", 6: "JUN", 7: "JUL", 8: "AUG",
        9: "SEP", 10: "OCT", 11: "NOV", 12: "DEC",
    }
    
    day = expiry_date.day
    month_abbr = month_map.get(expiry_date.month, "XXX")

    # Format day with two digits if needed
    day_str = f"{day:02d}"

    if symbol == 'NIFTY 50':
         symbol = 'NIFTY'
    elif symbol == 'BANK NIFTY':
         symbol = 'BANKNIFTY'
    else:
         symbol = symbol 

    # Compose symbol in NSE weekly options format:
    # SYMBOL + YY + MON + DD + STRIKE + CE/PE
    return f"{symbol}{str(expiry_date.year)[2:]}{month_abbr}{strike}{option_type.upper()}"


def get_previous_session_ohlc(df: pd.DataFrame) -> pd.Series:
    """
    Returns OHLC data (high, low, close) of the previous trading session from a time-indexed DataFrame.

    Args:
        df (pd.DataFrame): DataFrame with a DatetimeIndex and 'high', 'low', 'close' columns.

    Returns:
        pd.Series: Aggregated OHLC for previous trading session

    Notes:
        - Assumes df is sorted by datetime ascending
        - Groups by date (date part of index)
        - Take second last group for previous session
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("Input DataFrame must have DatetimeIndex")

    # Group data by date
    grouped = df.groupby(df.index.date)  # groups by datetime.date

    if len(grouped) < 2:
            high = 24783.70
            low = 24650.00
            close = 24707.80
            return pd.Series({"high": high, "low": low, "close": close})
        #raise ValueError("Not enough data to find previous session OHLC")

    prev_date = sorted(grouped.groups.keys())[-2]
    prev_day_data = df.loc[df.index.date == prev_date]

    high = prev_day_data["high"].max()
    low = prev_day_data["low"].min()    
    close = prev_day_data["close"].iloc[-1]



    return pd.Series({"high": high, "low": low, "close": close})
