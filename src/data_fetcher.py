"""
BankNifty Data Fetcher - Fetches daily OHLC data from NSE India with yfinance fallback
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import os
import json

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False


class NSEDataFetcher:
    """Fetches BankNifty data from NSE India website with yfinance fallback"""

    BASE_URL = "https://www.nseindia.com"
    BANKNIFTY_SYMBOL = "^NSEBANK"  # Yahoo Finance symbol for BankNifty
    DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "banknifty_data.json")

    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.nseindia.com/",
            "Connection": "keep-alive",
        }
        self.session.headers.update(self.headers)
        self._cached_data = None
        self._cache_time = None
        self._manual_data = None
        self._load_saved_data()

    def _load_saved_data(self):
        """Load saved data from file"""
        try:
            if os.path.exists(self.DATA_FILE):
                with open(self.DATA_FILE, "r") as f:
                    self._manual_data = json.load(f)
        except Exception as e:
            print(f"Error loading saved data: {e}")

    def _save_data(self, data):
        """Save data to file"""
        try:
            os.makedirs(os.path.dirname(self.DATA_FILE), exist_ok=True)
            with open(self.DATA_FILE, "w") as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Error saving data: {e}")

    def set_manual_data(self, prev_high: float, prev_low: float, prev_close: float,
                        current_price: float = None):
        """Manually set previous day's data and optionally current price"""
        self._manual_data = {
            "previous_high": prev_high,
            "previous_low": prev_low,
            "previous_close": prev_close,
            "current_price": current_price,
            "updated_at": datetime.now().isoformat()
        }
        self._save_data(self._manual_data)
        return self._manual_data

    def update_current_price(self, price: float):
        """Update just the current price"""
        if self._manual_data is None:
            self._manual_data = {}
        self._manual_data["current_price"] = price
        self._manual_data["price_updated_at"] = datetime.now().isoformat()
        self._save_data(self._manual_data)

    def get_banknifty_data(self, days=30):
        """
        Fetch BankNifty historical daily data
        Returns DataFrame with Date, Open, High, Low, Close columns
        """
        # Check if we have manual data
        if self._manual_data and "previous_high" in self._manual_data:
            yesterday = datetime.now() - timedelta(days=1)
            df = pd.DataFrame([{
                "Date": yesterday,
                "Open": self._manual_data.get("previous_close", 0),
                "High": self._manual_data["previous_high"],
                "Low": self._manual_data["previous_low"],
                "Close": self._manual_data.get("previous_close", 0)
            }])
            return df

        # Try yfinance first (more reliable)
        if YFINANCE_AVAILABLE:
            df = self._fetch_yfinance(days)
            if df is not None and not df.empty:
                return df

        # Fallback to NSE direct
        return self._fetch_nse(days)

    def _fetch_yfinance(self, days=30):
        """Fetch data using yfinance"""
        try:
            ticker = yf.Ticker(self.BANKNIFTY_SYMBOL)
            df = ticker.history(period=f"{days}d")

            if df.empty:
                return None

            df = df.reset_index()
            df = df.rename(columns={
                "Date": "Date",
                "Open": "Open",
                "High": "High",
                "Low": "Low",
                "Close": "Close"
            })

            # Handle timezone-aware datetime
            if df["Date"].dt.tz is not None:
                df["Date"] = df["Date"].dt.tz_localize(None)

            df = df[["Date", "Open", "High", "Low", "Close"]]
            df = df.sort_values("Date").reset_index(drop=True)

            # Cache the data
            self._cached_data = df
            self._cache_time = datetime.now()

            return df

        except Exception as e:
            print(f"yfinance fetch error: {e}")
            return None

    def _fetch_nse(self, days=30):
        """Fetch data from NSE India directly"""
        try:
            # Initialize session
            self.session.get(self.BASE_URL, timeout=10)
            time.sleep(1)

            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            hist_url = f"{self.BASE_URL}/api/historical/indicesHistory"
            params = {
                "indexType": "NIFTY BANK",
                "from": start_date.strftime("%d-%m-%Y"),
                "to": end_date.strftime("%d-%m-%Y")
            }

            response = self.session.get(hist_url, params=params, timeout=15)

            if response.status_code == 200:
                data = response.json()
                if "data" in data and "indexCloseOnlineRecords" in data["data"]:
                    records = data["data"]["indexCloseOnlineRecords"]
                    df = pd.DataFrame(records)

                    df = df.rename(columns={
                        "EOD_TIMESTAMP": "Date",
                        "EOD_OPEN_INDEX_VAL": "Open",
                        "EOD_HIGH_INDEX_VAL": "High",
                        "EOD_LOW_INDEX_VAL": "Low",
                        "EOD_CLOSE_INDEX_VAL": "Close"
                    })

                    df = df[["Date", "Open", "High", "Low", "Close"]]
                    df["Date"] = pd.to_datetime(df["Date"], format="%d-%b-%Y")
                    df = df.sort_values("Date").reset_index(drop=True)

                    for col in ["Open", "High", "Low", "Close"]:
                        df[col] = pd.to_numeric(df[col], errors="coerce")

                    return df

            return pd.DataFrame()

        except Exception as e:
            print(f"NSE fetch error: {e}")
            return pd.DataFrame()

    def get_current_price(self):
        """Get current BankNifty price"""
        # Check manual data first
        if self._manual_data and self._manual_data.get("current_price"):
            return {
                "price": self._manual_data["current_price"],
                "open": self._manual_data.get("previous_close", 0),
                "high": self._manual_data.get("previous_high", 0),
                "low": self._manual_data.get("previous_low", 0),
                "change": 0,
                "timestamp": datetime.now().isoformat(),
                "source": "manual"
            }

        # Try yfinance first
        if YFINANCE_AVAILABLE:
            price_data = self._get_price_yfinance()
            if price_data:
                return price_data

        # Fallback to NSE
        return self._get_price_nse()

    def _get_price_yfinance(self):
        """Get current price using yfinance"""
        try:
            ticker = yf.Ticker(self.BANKNIFTY_SYMBOL)

            # Get today's data
            hist = ticker.history(period="2d")

            if hist.empty:
                return None

            # Get latest data
            latest = hist.iloc[-1]

            # Calculate change from previous close if we have 2 days
            if len(hist) >= 2:
                prev_close = hist.iloc[-2]["Close"]
                change = ((latest["Close"] - prev_close) / prev_close) * 100
            else:
                change = 0

            return {
                "price": float(latest["Close"]),
                "open": float(latest["Open"]),
                "high": float(latest["High"]),
                "low": float(latest["Low"]),
                "change": round(change, 2),
                "timestamp": datetime.now().isoformat(),
                "source": "yfinance"
            }

        except Exception as e:
            print(f"yfinance price error: {e}")
            return None

    def _get_price_nse(self):
        """Get current price from NSE"""
        try:
            self.session.get(self.BASE_URL, timeout=10)
            time.sleep(0.5)

            url = f"{self.BASE_URL}/api/allIndices"
            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                data = response.json()
                for index in data.get("data", []):
                    if index.get("index") == "NIFTY BANK":
                        return {
                            "price": index.get("last", 0),
                            "open": index.get("open", 0),
                            "high": index.get("high", 0),
                            "low": index.get("low", 0),
                            "change": index.get("percentChange", 0),
                            "timestamp": datetime.now().isoformat(),
                            "source": "nse"
                        }
            return None

        except Exception as e:
            print(f"NSE price error: {e}")
            return None


# For testing
if __name__ == "__main__":
    fetcher = NSEDataFetcher()
    print("Fetching BankNifty data...")
    df = fetcher.get_banknifty_data(days=10)
    print(df)
    print("\nCurrent Price:")
    print(fetcher.get_current_price())
