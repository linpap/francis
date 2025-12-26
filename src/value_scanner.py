"""
Value Scanner - Stock Scanner with Yahoo Finance and NSE India fallback
Scans stocks based on RSI and other technical indicators
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import json
import time
import random

# NSE India stocks list (top 15 stocks for Render free tier - 30sec timeout)
NSE_STOCKS = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR", "SBIN",
    "BHARTIARTL", "KOTAKBANK", "ITC", "LT", "AXISBANK", "TATAMOTORS", "TITAN", "WIPRO"
]


def calculate_rsi(prices, period=14):
    """Calculate RSI for a price series"""
    if len(prices) < period + 1:
        return None

    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else None


def get_yahoo_chart_data(symbol, interval="1d", range_period="6mo"):
    """Fetch data directly from Yahoo Finance chart API"""
    try:
        ticker = f"{symbol}.NS"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        params = {
            "interval": interval,
            "range": range_period,
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }

        response = requests.get(url, params=params, headers=headers, timeout=5)
        if response.status_code != 200:
            return None

        data = response.json()
        result = data.get("chart", {}).get("result", [])
        if not result:
            return None

        result = result[0]
        timestamps = result.get("timestamp", [])
        quote = result.get("indicators", {}).get("quote", [{}])[0]

        if not timestamps or not quote:
            return None

        df = pd.DataFrame({
            "Open": quote.get("open", []),
            "High": quote.get("high", []),
            "Low": quote.get("low", []),
            "Close": quote.get("close", []),
            "Volume": quote.get("volume", [])
        }, index=pd.to_datetime(timestamps, unit='s'))

        # Remove NaN rows
        df = df.dropna()
        return df

    except Exception as e:
        return None


def get_stock_data_yahoo(symbol, period="6mo"):
    """Fetch stock data from Yahoo Finance using direct API calls"""
    import warnings
    warnings.filterwarnings('ignore')

    try:
        # No delay - speed is critical for Render timeout

        # Get daily data
        daily_data = get_yahoo_chart_data(symbol, "1d", period)
        if daily_data is None or daily_data.empty:
            return None

        # Get weekly data for weekly RSI
        weekly_data = get_yahoo_chart_data(symbol, "1wk", "1y")

        # Get monthly data for monthly RSI
        monthly_data = get_yahoo_chart_data(symbol, "1mo", "2y")

        # Calculate RSI values
        daily_rsi = calculate_rsi(daily_data['Close'], 14)
        weekly_rsi = calculate_rsi(weekly_data['Close'], 14) if weekly_data is not None and not weekly_data.empty else None
        monthly_rsi = calculate_rsi(monthly_data['Close'], 14) if monthly_data is not None and not monthly_data.empty else None

        # Get latest price info
        latest = daily_data.iloc[-1]
        prev_close = daily_data.iloc[-2]['Close'] if len(daily_data) > 1 else latest['Close']
        change_pct = ((latest['Close'] - prev_close) / prev_close) * 100

        return {
            "symbol": symbol,
            "ltp": round(float(latest['Close']), 2),
            "open": round(float(latest['Open']), 2),
            "high": round(float(latest['High']), 2),
            "low": round(float(latest['Low']), 2),
            "volume": int(latest['Volume']) if pd.notna(latest['Volume']) else 0,
            "change": round(float(change_pct), 2),
            "dailyRsi": round(float(daily_rsi), 2) if daily_rsi and not pd.isna(daily_rsi) else None,
            "weeklyRsi": round(float(weekly_rsi), 2) if weekly_rsi and not pd.isna(weekly_rsi) else None,
            "monthlyRsi": round(float(monthly_rsi), 2) if monthly_rsi and not pd.isna(monthly_rsi) else None,
            "source": "yahoo"
        }
    except Exception as e:
        print(f"Yahoo Finance error for {symbol}: {e}")
        return None


def get_stock_data_nse(symbol):
    """Fallback: Fetch stock data from NSE India"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        }

        # NSE API endpoint
        url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"

        session = requests.Session()
        # First hit the main page to get cookies
        session.get("https://www.nseindia.com", headers=headers, timeout=5)

        response = session.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            price_info = data.get("priceInfo", {})

            return {
                "symbol": symbol,
                "ltp": price_info.get("lastPrice", 0),
                "open": price_info.get("open", 0),
                "high": price_info.get("intraDayHighLow", {}).get("max", 0),
                "low": price_info.get("intraDayHighLow", {}).get("min", 0),
                "volume": data.get("securityWiseDP", {}).get("quantityTraded", 0),
                "change": price_info.get("pChange", 0),
                "dailyRsi": None,  # NSE doesn't provide RSI
                "weeklyRsi": None,
                "monthlyRsi": None,
                "source": "nse"
            }
    except Exception as e:
        print(f"NSE error for {symbol}: {e}")

    return None


def get_stock_data(symbol):
    """Get stock data with Yahoo Finance primary and NSE fallback"""
    data = get_stock_data_yahoo(symbol)
    if data is None:
        data = get_stock_data_nse(symbol)
    return data


def format_volume(volume):
    """Format volume to human readable format"""
    if volume >= 10000000:  # 1 Crore
        return f"{volume/10000000:.2f}Cr"
    elif volume >= 100000:  # 1 Lakh
        return f"{volume/100000:.2f}L"
    elif volume >= 1000:
        return f"{volume/1000:.1f}K"
    return str(volume)


def scan_stocks(conditions, stock_list=None, segment="cash"):
    """
    Scan stocks based on given conditions

    conditions: list of condition dicts with keys:
        - timeframe: 'Daily', 'Weekly', 'Monthly'
        - indicator: 'Rsi', 'Close', etc.
        - operator: 'Greater than equal to', 'Less than equal to', etc.
        - value: numeric value
        - active: boolean
    """
    if stock_list is None:
        stock_list = NSE_STOCKS

    results = []

    # Fetch data in parallel (increased workers for faster scanning)
    with ThreadPoolExecutor(max_workers=15) as executor:
        future_to_symbol = {executor.submit(get_stock_data, symbol): symbol for symbol in stock_list}

        for future in as_completed(future_to_symbol):
            symbol = future_to_symbol[future]
            try:
                stock_data = future.result()
                if stock_data:
                    # Check if stock passes all active conditions
                    if check_conditions(stock_data, conditions):
                        stock_data['volumeFormatted'] = format_volume(stock_data['volume'])
                        results.append(stock_data)
            except Exception as e:
                print(f"Error processing {symbol}: {e}")

    # Sort by daily RSI descending
    results.sort(key=lambda x: x.get('dailyRsi') or 0, reverse=True)

    return results


def check_conditions(stock_data, conditions):
    """Check if stock passes all active conditions"""
    for cond in conditions:
        if not cond.get('active', True):
            continue

        timeframe = cond.get('timeframe', 'Daily')
        indicator = cond.get('indicator', 'Rsi')
        operator = cond.get('operator', 'Greater than equal to')
        value = float(cond.get('value', 0))

        # Get the indicator value based on timeframe
        if indicator.lower() == 'rsi':
            if timeframe == 'Daily':
                indicator_value = stock_data.get('dailyRsi')
            elif timeframe == 'Weekly':
                indicator_value = stock_data.get('weeklyRsi')
            elif timeframe == 'Monthly':
                indicator_value = stock_data.get('monthlyRsi')
            else:
                indicator_value = stock_data.get('dailyRsi')
        elif indicator.lower() == 'close':
            indicator_value = stock_data.get('ltp')
        elif indicator.lower() == 'volume':
            indicator_value = stock_data.get('volume')
        else:
            indicator_value = None

        # If indicator value is None, condition fails
        if indicator_value is None:
            return False

        # Check the condition
        if not evaluate_condition(indicator_value, operator, value):
            return False

    return True


def evaluate_condition(indicator_value, operator, value):
    """Evaluate a single condition"""
    op = operator.lower()

    if 'greater than equal' in op or '>=' in op:
        return indicator_value >= value
    elif 'less than equal' in op or '<=' in op:
        return indicator_value <= value
    elif 'greater than' in op or '>' in op:
        return indicator_value > value
    elif 'less than' in op or '<' in op:
        return indicator_value < value
    elif 'equal' in op or '==' in op:
        return abs(indicator_value - value) < 0.01

    return True


# Quick test
if __name__ == "__main__":
    print("Testing Value Scanner...")

    # Test conditions (RSI between 40-60)
    test_conditions = [
        {"timeframe": "Daily", "indicator": "Rsi", "operator": "Greater than equal to", "value": 40, "active": True},
        {"timeframe": "Daily", "indicator": "Rsi", "operator": "Less than equal to", "value": 70, "active": True},
    ]

    # Test with just 3 stocks
    results = scan_stocks(test_conditions, ["RELIANCE", "TCS", "INFY"])

    for stock in results:
        print(f"{stock['symbol']}: LTP={stock['ltp']}, Daily RSI={stock['dailyRsi']}, Weekly RSI={stock['weeklyRsi']}")
