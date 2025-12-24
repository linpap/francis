"""
Signal Generator - Generates BUY/SELL signals based on recent swing high/low breakout
"""

from datetime import datetime
from dataclasses import dataclass
from typing import Optional, List
import pandas as pd


@dataclass
class Signal:
    """Trading signal data class"""
    signal_type: str  # "BUY" or "SELL"
    price: float
    trigger_level: float  # The high/low that was broken
    timestamp: datetime
    swing_high: float
    swing_low: float
    swing_high_date: str
    swing_low_date: str

    def to_dict(self):
        return {
            "signal_type": self.signal_type,
            "price": self.price,
            "trigger_level": self.trigger_level,
            "timestamp": self.timestamp.isoformat(),
            "swing_high": self.swing_high,
            "swing_low": self.swing_low,
            "swing_high_date": self.swing_high_date,
            "swing_low_date": self.swing_low_date,
            # For backward compatibility
            "previous_day_high": self.swing_high,
            "previous_day_low": self.swing_low
        }


class SignalGenerator:
    """
    Generates trading signals based on RECENT SWING HIGH/LOW breakout strategy.

    Strategy:
    - Scans last N days (default 10) to find the most recent swing high and swing low
    - A swing high is a candle high that is higher than the candles before and after it
    - A swing low is a candle low that is lower than the candles before and after it
    - BUY signal: When current price breaks above recent swing HIGH
    - SELL signal: When current price breaks below recent swing LOW
    """

    def __init__(self, lookback_days: int = 10):
        self.lookback_days = lookback_days
        self.signals_history: List[Signal] = []
        self.last_signal: Optional[Signal] = None
        self.swing_data: Optional[dict] = None
        self.daily_data: Optional[pd.DataFrame] = None

    def set_swing_levels(self, swing_high: float, swing_low: float,
                         high_date: str = "", low_date: str = ""):
        """Manually set swing high/low levels"""
        self.swing_data = {
            "swing_high": swing_high,
            "swing_low": swing_low,
            "swing_high_date": high_date,
            "swing_low_date": low_date
        }

    def find_swing_points(self, df: pd.DataFrame) -> dict:
        """
        Find recent swing high and swing low from daily data.

        A swing high: A candle whose HIGH is higher than previous and next candle's high
        A swing low: A candle whose LOW is lower than previous and next candle's low

        Returns the most recent swing high and swing low.
        """
        if df is None or len(df) < 3:
            return None

        df = df.sort_values("Date").reset_index(drop=True)

        swing_highs = []
        swing_lows = []

        # Find all swing points (need at least 1 candle before and after)
        for i in range(1, len(df) - 1):
            current = df.iloc[i]
            prev_candle = df.iloc[i - 1]
            next_candle = df.iloc[i + 1]

            # Swing High: current high > previous high AND current high > next high
            if current["High"] > prev_candle["High"] and current["High"] > next_candle["High"]:
                swing_highs.append({
                    "price": float(current["High"]),
                    "date": current["Date"],
                    "index": i
                })

            # Swing Low: current low < previous low AND current low < next low
            if current["Low"] < prev_candle["Low"] and current["Low"] < next_candle["Low"]:
                swing_lows.append({
                    "price": float(current["Low"]),
                    "date": current["Date"],
                    "index": i
                })

        # Get the most recent swing high and low
        # If no swing points found, use the highest high and lowest low from recent data
        if swing_highs:
            recent_swing_high = swing_highs[-1]  # Most recent
        else:
            # Fallback: highest high in the lookback period (exclude today)
            recent_data = df.iloc[-self.lookback_days:-1] if len(df) > self.lookback_days else df.iloc[:-1]
            if len(recent_data) > 0:
                max_idx = recent_data["High"].idxmax()
                recent_swing_high = {
                    "price": float(recent_data.loc[max_idx, "High"]),
                    "date": recent_data.loc[max_idx, "Date"],
                    "index": max_idx
                }
            else:
                return None

        if swing_lows:
            recent_swing_low = swing_lows[-1]  # Most recent
        else:
            # Fallback: lowest low in the lookback period (exclude today)
            recent_data = df.iloc[-self.lookback_days:-1] if len(df) > self.lookback_days else df.iloc[:-1]
            if len(recent_data) > 0:
                min_idx = recent_data["Low"].idxmin()
                recent_swing_low = {
                    "price": float(recent_data.loc[min_idx, "Low"]),
                    "date": recent_data.loc[min_idx, "Date"],
                    "index": min_idx
                }
            else:
                return None

        # Format dates
        def format_date(d):
            if hasattr(d, "strftime"):
                return d.strftime("%Y-%m-%d")
            return str(d)[:10]

        return {
            "swing_high": recent_swing_high["price"],
            "swing_low": recent_swing_low["price"],
            "swing_high_date": format_date(recent_swing_high["date"]),
            "swing_low_date": format_date(recent_swing_low["date"])
        }

    def update_from_dataframe(self, df: pd.DataFrame):
        """Update swing levels from a DataFrame of daily data"""
        if df is None or df.empty:
            return False

        self.daily_data = df.copy()
        swing_points = self.find_swing_points(df)

        if swing_points:
            self.swing_data = swing_points
            print(f"Swing High: {swing_points['swing_high']} ({swing_points['swing_high_date']})")
            print(f"Swing Low: {swing_points['swing_low']} ({swing_points['swing_low_date']})")
            return True

        return False

    # Backward compatibility
    def set_previous_day_data(self, high: float, low: float, close: float, date: datetime):
        """Set swing levels (backward compatible method)"""
        date_str = date.strftime("%Y-%m-%d") if hasattr(date, "strftime") else str(date)
        self.swing_data = {
            "swing_high": high,
            "swing_low": low,
            "swing_high_date": date_str,
            "swing_low_date": date_str
        }

    @property
    def previous_day_data(self):
        """Backward compatibility property"""
        if self.swing_data:
            return {
                "high": self.swing_data["swing_high"],
                "low": self.swing_data["swing_low"],
                "close": self.swing_data.get("swing_high", 0),  # Approximate
                "date": self.swing_data["swing_high_date"]
            }
        return None

    def check_signal(self, current_price: float) -> Optional[Signal]:
        """
        Check if current price triggers a BUY or SELL signal.

        Args:
            current_price: Current BankNifty price

        Returns:
            Signal object if a signal is triggered, None otherwise
        """
        if self.swing_data is None:
            return None

        swing_high = self.swing_data["swing_high"]
        swing_low = self.swing_data["swing_low"]

        signal = None

        # BUY Signal: Price breaks above recent swing high
        if current_price > swing_high:
            if self.last_signal is None or self.last_signal.signal_type != "BUY":
                signal = Signal(
                    signal_type="BUY",
                    price=current_price,
                    trigger_level=swing_high,
                    timestamp=datetime.now(),
                    swing_high=swing_high,
                    swing_low=swing_low,
                    swing_high_date=self.swing_data["swing_high_date"],
                    swing_low_date=self.swing_data["swing_low_date"]
                )

        # SELL Signal: Price breaks below recent swing low
        elif current_price < swing_low:
            if self.last_signal is None or self.last_signal.signal_type != "SELL":
                signal = Signal(
                    signal_type="SELL",
                    price=current_price,
                    trigger_level=swing_low,
                    timestamp=datetime.now(),
                    swing_high=swing_high,
                    swing_low=swing_low,
                    swing_high_date=self.swing_data["swing_high_date"],
                    swing_low_date=self.swing_data["swing_low_date"]
                )

        if signal:
            self.last_signal = signal
            self.signals_history.append(signal)

        return signal

    def get_market_status(self, current_price: float) -> dict:
        """Get current market status relative to swing levels"""
        if self.swing_data is None:
            return {"status": "NO_DATA"}

        swing_high = self.swing_data["swing_high"]
        swing_low = self.swing_data["swing_low"]

        if current_price > swing_high:
            status = "ABOVE_SWING_HIGH"
            signal_active = "BUY"
        elif current_price < swing_low:
            status = "BELOW_SWING_LOW"
            signal_active = "SELL"
        else:
            status = "WITHIN_RANGE"
            signal_active = "NEUTRAL"

        return {
            "status": status,
            "signal_active": signal_active,
            "current_price": current_price,
            "previous_high": swing_high,  # For UI compatibility
            "previous_low": swing_low,    # For UI compatibility
            "swing_high": swing_high,
            "swing_low": swing_low,
            "swing_high_date": self.swing_data["swing_high_date"],
            "swing_low_date": self.swing_data["swing_low_date"],
            "distance_to_high": swing_high - current_price,
            "distance_to_low": current_price - swing_low,
            "previous_day_date": f"High: {self.swing_data['swing_high_date']}, Low: {self.swing_data['swing_low_date']}"
        }

    def get_signals_history(self, limit: int = 50) -> List[dict]:
        """Get recent signals history"""
        return [s.to_dict() for s in self.signals_history[-limit:]]

    def clear_history(self):
        """Clear signals history"""
        self.signals_history = []
        self.last_signal = None


# For testing
if __name__ == "__main__":
    import pandas as pd
    from datetime import timedelta

    # Create sample data
    dates = [datetime.now() - timedelta(days=i) for i in range(10, 0, -1)]
    data = {
        "Date": dates,
        "Open": [51000, 51200, 51100, 51300, 51500, 51400, 51600, 51500, 51700, 51600],
        "High": [51300, 51400, 51350, 51600, 51800, 51650, 51900, 51750, 51950, 51800],
        "Low":  [50900, 51000, 50950, 51100, 51300, 51200, 51400, 51300, 51500, 51400],
        "Close":[51200, 51300, 51200, 51500, 51700, 51500, 51800, 51600, 51900, 51700]
    }
    df = pd.DataFrame(data)

    generator = SignalGenerator(lookback_days=10)
    generator.update_from_dataframe(df)

    print("\nSwing Data:")
    print(generator.swing_data)

    print("\nTesting BUY signal (price > swing high):")
    signal = generator.check_signal(52000)
    if signal:
        print(f"  {signal.signal_type} at {signal.price}, trigger: {signal.trigger_level}")

    print("\nMarket Status at 51700:")
    print(generator.get_market_status(51700))
