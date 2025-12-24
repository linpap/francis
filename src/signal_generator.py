"""
Signal Generator - Generates BUY/SELL signals based on previous day high/low breakout
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
    previous_day_high: float
    previous_day_low: float
    previous_day_close: float

    def to_dict(self):
        return {
            "signal_type": self.signal_type,
            "price": self.price,
            "trigger_level": self.trigger_level,
            "timestamp": self.timestamp.isoformat(),
            "previous_day_high": self.previous_day_high,
            "previous_day_low": self.previous_day_low,
            "previous_day_close": self.previous_day_close
        }


class SignalGenerator:
    """
    Generates trading signals based on previous day high/low breakout strategy.

    Strategy:
    - BUY signal: When current price breaks above previous day's HIGH
    - SELL signal: When current price breaks below previous day's LOW
    """

    def __init__(self):
        self.signals_history: List[Signal] = []
        self.last_signal: Optional[Signal] = None
        self.previous_day_data: Optional[dict] = None

    def set_previous_day_data(self, high: float, low: float, close: float, date: datetime):
        """Set the previous day's OHLC data for signal generation"""
        self.previous_day_data = {
            "high": high,
            "low": low,
            "close": close,
            "date": date
        }

    def update_from_dataframe(self, df: pd.DataFrame):
        """Update previous day data from a DataFrame"""
        if df is None or df.empty or len(df) < 2:
            return False

        # Get the last complete day (second to last row if we have today's data)
        # Or last row if we only have historical data
        df = df.sort_values("Date").reset_index(drop=True)

        # Use the most recent complete day
        prev_day = df.iloc[-1]

        self.previous_day_data = {
            "high": float(prev_day["High"]),
            "low": float(prev_day["Low"]),
            "close": float(prev_day["Close"]),
            "date": prev_day["Date"]
        }
        return True

    def check_signal(self, current_price: float) -> Optional[Signal]:
        """
        Check if current price triggers a BUY or SELL signal.

        Args:
            current_price: Current BankNifty price

        Returns:
            Signal object if a signal is triggered, None otherwise
        """
        if self.previous_day_data is None:
            return None

        prev_high = self.previous_day_data["high"]
        prev_low = self.previous_day_data["low"]
        prev_close = self.previous_day_data["close"]

        signal = None

        # BUY Signal: Price breaks above previous day's high
        if current_price > prev_high:
            # Check if we already signaled a buy at this level
            if self.last_signal is None or self.last_signal.signal_type != "BUY":
                signal = Signal(
                    signal_type="BUY",
                    price=current_price,
                    trigger_level=prev_high,
                    timestamp=datetime.now(),
                    previous_day_high=prev_high,
                    previous_day_low=prev_low,
                    previous_day_close=prev_close
                )

        # SELL Signal: Price breaks below previous day's low
        elif current_price < prev_low:
            # Check if we already signaled a sell at this level
            if self.last_signal is None or self.last_signal.signal_type != "SELL":
                signal = Signal(
                    signal_type="SELL",
                    price=current_price,
                    trigger_level=prev_low,
                    timestamp=datetime.now(),
                    previous_day_high=prev_high,
                    previous_day_low=prev_low,
                    previous_day_close=prev_close
                )

        if signal:
            self.last_signal = signal
            self.signals_history.append(signal)

        return signal

    def get_market_status(self, current_price: float) -> dict:
        """Get current market status relative to previous day levels"""
        if self.previous_day_data is None:
            return {"status": "NO_DATA"}

        prev_high = self.previous_day_data["high"]
        prev_low = self.previous_day_data["low"]

        if current_price > prev_high:
            status = "ABOVE_PREVIOUS_HIGH"
            signal_active = "BUY"
        elif current_price < prev_low:
            status = "BELOW_PREVIOUS_LOW"
            signal_active = "SELL"
        else:
            status = "WITHIN_RANGE"
            signal_active = "NEUTRAL"

        return {
            "status": status,
            "signal_active": signal_active,
            "current_price": current_price,
            "previous_high": prev_high,
            "previous_low": prev_low,
            "distance_to_high": prev_high - current_price,
            "distance_to_low": current_price - prev_low,
            "previous_day_date": self.previous_day_data["date"].strftime("%Y-%m-%d") if hasattr(self.previous_day_data["date"], "strftime") else str(self.previous_day_data["date"])
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
    generator = SignalGenerator()

    # Simulate previous day data
    generator.set_previous_day_data(
        high=52000,
        low=51500,
        close=51800,
        date=datetime.now()
    )

    # Test signals
    print("Testing BUY signal (price > prev high):")
    signal = generator.check_signal(52100)
    if signal:
        print(f"  {signal}")

    print("\nTesting SELL signal (price < prev low):")
    generator.last_signal = None  # Reset for testing
    signal = generator.check_signal(51400)
    if signal:
        print(f"  {signal}")

    print("\nTesting NEUTRAL (price within range):")
    generator.last_signal = None
    signal = generator.check_signal(51700)
    print(f"  Signal: {signal}")

    print("\nMarket Status:")
    print(generator.get_market_status(51700))
