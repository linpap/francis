"""
Francis Trading App - Main Flask Application
BankNifty Previous Day High/Low Breakout Scanner
"""

import os
from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from src.scanner import BankNiftyScanner
from src.email_alert import EmailAlertSystem

# Initialize Flask app
app = Flask(__name__)

# Initialize scanner with 15-minute interval
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL_MINUTES", "15"))
scanner = BankNiftyScanner(scan_interval_minutes=SCAN_INTERVAL)


@app.route("/")
def index():
    """Main dashboard page"""
    return render_template("index.html")


@app.route("/api/status")
def get_status():
    """Get current scanner status and market data"""
    return jsonify(scanner.get_status())


@app.route("/api/scan", methods=["POST"])
def manual_scan():
    """Trigger a manual scan"""
    signal = scanner.scan()
    if signal:
        return jsonify({
            "success": True,
            "message": f"{signal.signal_type} signal generated at {signal.price:,.2f}",
            "signal": signal.to_dict()
        })
    else:
        status = scanner.get_status()
        market = status.get("market_status", {})
        return jsonify({
            "success": True,
            "message": f"Scan complete. Status: {market.get('status', 'UNKNOWN')}. No new signal.",
            "signal": None
        })


@app.route("/api/test-email", methods=["POST"])
def test_email():
    """Send a test email"""
    email_system = EmailAlertSystem()

    if not email_system.is_configured():
        return jsonify({
            "success": False,
            "message": "Email not configured. Please set EMAIL_SENDER, EMAIL_PASSWORD, and EMAIL_RECEIVER in .env file."
        })

    success = email_system.send_test_email()
    if success:
        return jsonify({
            "success": True,
            "message": "Test email sent successfully! Check your inbox."
        })
    else:
        return jsonify({
            "success": False,
            "message": "Failed to send test email. Check your email configuration."
        })


@app.route("/api/signals")
def get_signals():
    """Get signals history"""
    status = scanner.get_status()
    return jsonify({
        "signals": status.get("signals_history", [])
    })


@app.route("/api/refresh-data", methods=["POST"])
def refresh_data():
    """Refresh previous day data"""
    scanner.refresh_previous_day_data()
    return jsonify({
        "success": True,
        "message": "Previous day data refreshed",
        "previous_day_data": scanner.signal_generator.previous_day_data
    })


@app.route("/api/set-data", methods=["POST"])
def set_manual_data():
    """Manually set previous day data and current price"""
    data = request.get_json()

    prev_high = float(data.get("previous_high", 0))
    prev_low = float(data.get("previous_low", 0))
    prev_close = float(data.get("previous_close", 0))
    current_price = data.get("current_price")

    if current_price:
        current_price = float(current_price)

    # Set data in fetcher
    scanner.data_fetcher.set_manual_data(prev_high, prev_low, prev_close, current_price)

    # Update signal generator
    from datetime import datetime
    scanner.signal_generator.set_previous_day_data(prev_high, prev_low, prev_close, datetime.now())

    # Update current price data
    if current_price:
        scanner.current_price_data = {
            "price": current_price,
            "open": prev_close,
            "high": prev_high,
            "low": prev_low,
            "change": 0,
            "timestamp": datetime.now().isoformat()
        }

    return jsonify({
        "success": True,
        "message": "Data updated successfully",
        "data": {
            "previous_high": prev_high,
            "previous_low": prev_low,
            "previous_close": prev_close,
            "current_price": current_price
        }
    })


@app.route("/api/update-price", methods=["POST"])
def update_price():
    """Update current price only"""
    data = request.get_json()
    price = float(data.get("price", 0))

    if price <= 0:
        return jsonify({"success": False, "message": "Invalid price"})

    scanner.data_fetcher.update_current_price(price)

    # Update scanner's current price data
    from datetime import datetime
    prev_data = scanner.signal_generator.previous_day_data or {}
    scanner.current_price_data = {
        "price": price,
        "open": prev_data.get("close", 0),
        "high": prev_data.get("high", 0),
        "low": prev_data.get("low", 0),
        "change": 0,
        "timestamp": datetime.now().isoformat()
    }

    # Check for signals
    signal = scanner.signal_generator.check_signal(price)
    signal_data = None
    if signal:
        signal_data = signal.to_dict()
        # Send email if configured
        if scanner.email_alert.is_configured():
            scanner.email_alert.send_signal_alert(
                signal_type=signal.signal_type,
                price=signal.price,
                trigger_level=signal.trigger_level,
                prev_high=signal.previous_day_high,
                prev_low=signal.previous_day_low
            )

    return jsonify({
        "success": True,
        "message": f"Price updated to {price:,.2f}",
        "signal": signal_data
    })


def start_scanner():
    """Start the background scanner"""
    scanner.start()


def stop_scanner():
    """Stop the background scanner"""
    scanner.stop()


if __name__ == "__main__":
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║           Francis - BankNifty Trading Scanner             ║
    ║         Previous Day High/Low Breakout Strategy           ║
    ╠═══════════════════════════════════════════════════════════╣
    ║  Scan Interval: Every 15 minutes                          ║
    ║  Strategy: BUY when price > previous day high             ║
    ║            SELL when price < previous day low             ║
    ╚═══════════════════════════════════════════════════════════╝
    """)

    # Start the scanner
    start_scanner()

    # Get port from environment (for cloud deployment) or use 5001
    port = int(os.getenv("PORT", 5001))

    # Run Flask app
    try:
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
    finally:
        stop_scanner()
