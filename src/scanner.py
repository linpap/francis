"""
BankNifty Scanner - Runs at market open (9:15 AM) and close (3:25 PM) IST
"""

from datetime import datetime
from typing import Optional, Callable
import time
import pytz

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .data_fetcher import NSEDataFetcher
from .signal_generator import SignalGenerator, Signal
from .email_alert import EmailAlertSystem


class BankNiftyScanner:
    """
    Main scanner class that orchestrates data fetching, signal generation,
    and email alerts at specific times (9:15 AM and 3:25 PM IST).
    """

    def __init__(self, scan_interval_minutes: int = 15):
        self.data_fetcher = NSEDataFetcher()
        self.signal_generator = SignalGenerator()
        self.email_alert = EmailAlertSystem()

        self.scan_interval = scan_interval_minutes  # Kept for backward compatibility
        self.scheduler: Optional[BackgroundScheduler] = None
        self.is_running = False
        self.last_scan_time: Optional[datetime] = None
        self.current_price_data: Optional[dict] = None

        # India timezone
        self.ist = pytz.timezone('Asia/Kolkata')

        # Callback for signal events
        self.on_signal_callback: Optional[Callable[[Signal], None]] = None

        # Initialize with historical data
        self._initialize_previous_day_data()

    def _initialize_previous_day_data(self):
        """Fetch and set previous day's data on startup"""
        try:
            df = self.data_fetcher.get_banknifty_data(days=10)
            if df is not None and not df.empty:
                self.signal_generator.update_from_dataframe(df)
                print(f"Initialized with swing data: {self.signal_generator.swing_data}")
        except Exception as e:
            print(f"Error initializing previous day data: {e}")

    def scan(self) -> Optional[Signal]:
        """
        Perform a single scan - fetch current price and check for signals.
        Returns a Signal if one is generated, None otherwise.
        """
        try:
            self.last_scan_time = datetime.now()

            # Refresh swing data
            self._initialize_previous_day_data()

            # Get current price
            self.current_price_data = self.data_fetcher.get_current_price()

            if not self.current_price_data:
                print("Could not fetch current price")
                return None

            current_price = self.current_price_data.get("price", 0)

            if current_price <= 0:
                print("Invalid price data")
                return None

            # Check for signal
            signal = self.signal_generator.check_signal(current_price)

            if signal:
                print(f"Signal generated: {signal.signal_type} at {signal.price}")

                # Send email alert
                if self.email_alert.is_configured():
                    self.email_alert.send_signal_alert(
                        signal_type=signal.signal_type,
                        price=signal.price,
                        trigger_level=signal.trigger_level,
                        prev_high=signal.swing_high,
                        prev_low=signal.swing_low
                    )

                # Call callback if set
                if self.on_signal_callback:
                    self.on_signal_callback(signal)

            return signal

        except Exception as e:
            print(f"Scan error: {e}")
            return None

    def _scheduled_scan(self):
        """Wrapper for scheduled scans"""
        now_ist = datetime.now(self.ist)
        print(f"\n[{now_ist.strftime('%Y-%m-%d %H:%M:%S')} IST] Running scheduled scan...")
        signal = self.scan()
        if signal:
            print(f"  -> {signal.signal_type} signal at {signal.price}")
        else:
            status = self.signal_generator.get_market_status(
                self.current_price_data.get("price", 0) if self.current_price_data else 0
            )
            print(f"  -> No signal. Status: {status.get('status', 'UNKNOWN')}")

    def start(self):
        """Start the scheduled scanner"""
        if self.is_running:
            print("Scanner already running")
            return

        self.scheduler = BackgroundScheduler(timezone=self.ist)

        # Schedule at 9:15 AM IST (Market Open)
        self.scheduler.add_job(
            self._scheduled_scan,
            trigger=CronTrigger(hour=9, minute=15, timezone=self.ist),
            id='morning_scan',
            name='Morning Scan (9:15 AM IST)',
            replace_existing=True
        )

        # Schedule at 3:25 PM IST (Near Market Close)
        self.scheduler.add_job(
            self._scheduled_scan,
            trigger=CronTrigger(hour=15, minute=25, timezone=self.ist),
            id='afternoon_scan',
            name='Afternoon Scan (3:25 PM IST)',
            replace_existing=True
        )

        self.scheduler.start()
        self.is_running = True
        print("Scanner started. Scheduled scans at:")
        print("  - 9:15 AM IST (Market Open)")
        print("  - 3:25 PM IST (Near Market Close)")

        # Run initial scan
        self._scheduled_scan()

    def stop(self):
        """Stop the scheduled scanner"""
        if self.scheduler:
            self.scheduler.shutdown(wait=False)
            self.is_running = False
            print("Scanner stopped")

    def get_status(self) -> dict:
        """Get current scanner status"""
        market_status = {}
        if self.current_price_data:
            price = self.current_price_data.get("price", 0)
            market_status = self.signal_generator.get_market_status(price)

        return {
            "scanner_running": self.is_running,
            "last_scan": self.last_scan_time.strftime("%Y-%m-%d %H:%M:%S") if self.last_scan_time else None,
            "scan_interval_minutes": self.scan_interval,
            "scan_times": ["9:15 AM IST", "3:25 PM IST"],
            "current_price": self.current_price_data,
            "market_status": market_status,
            "previous_day_data": self.signal_generator.previous_day_data,
            "email_configured": self.email_alert.is_configured(),
            "signals_history": self.signal_generator.get_signals_history()
        }

    def refresh_previous_day_data(self):
        """Manually refresh previous day data"""
        self._initialize_previous_day_data()


# For testing
if __name__ == "__main__":
    scanner = BankNiftyScanner()

    def on_signal(signal):
        print(f"\n*** SIGNAL CALLBACK: {signal} ***\n")

    scanner.on_signal_callback = on_signal
    scanner.start()

    try:
        while True:
            time.sleep(60)
            print(f"Status: {scanner.get_status()}")
    except KeyboardInterrupt:
        scanner.stop()
        print("Scanner stopped by user")
