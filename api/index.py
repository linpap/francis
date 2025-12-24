"""
Vercel Serverless Function - Main API endpoint
"""

from flask import Flask, render_template, jsonify, request
import yfinance as yf
from datetime import datetime, timedelta
import os

app = Flask(__name__, template_folder='../templates')

# In-memory storage (resets on cold start)
data_store = {
    "previous_high": None,
    "previous_low": None,
    "previous_close": None,
    "signals_history": []
}


def get_banknifty_data():
    """Fetch BankNifty data from Yahoo Finance"""
    try:
        ticker = yf.Ticker("^NSEBANK")
        hist = ticker.history(period="5d")

        if hist.empty:
            return None, None

        # Get previous day data (second to last row)
        if len(hist) >= 2:
            prev_day = hist.iloc[-2]
            current = hist.iloc[-1]

            prev_data = {
                "high": float(prev_day["High"]),
                "low": float(prev_day["Low"]),
                "close": float(prev_day["Close"]),
                "date": str(prev_day.name.date())
            }

            current_data = {
                "price": float(current["Close"]),
                "open": float(current["Open"]),
                "high": float(current["High"]),
                "low": float(current["Low"]),
                "change": round(((current["Close"] - prev_day["Close"]) / prev_day["Close"]) * 100, 2),
                "timestamp": datetime.now().isoformat()
            }

            return prev_data, current_data

        return None, None

    except Exception as e:
        print(f"Error fetching data: {e}")
        return None, None


def check_signal(current_price, prev_high, prev_low):
    """Check for breakout signals"""
    if current_price > prev_high:
        return "BUY", prev_high
    elif current_price < prev_low:
        return "SELL", prev_low
    return "NEUTRAL", None


@app.route('/')
def index():
    """Main dashboard"""
    return render_template('index.html')


@app.route('/api/status')
def get_status():
    """Get current market status"""
    prev_data, current_data = get_banknifty_data()

    # Use fetched data or stored manual data
    if prev_data:
        prev_high = prev_data["high"]
        prev_low = prev_data["low"]
        prev_close = prev_data["close"]
    elif data_store["previous_high"]:
        prev_high = data_store["previous_high"]
        prev_low = data_store["previous_low"]
        prev_close = data_store["previous_close"]
    else:
        return jsonify({
            "scanner_running": True,
            "last_scan": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "current_price": None,
            "market_status": {},
            "previous_day_data": None,
            "email_configured": False,
            "signals_history": data_store["signals_history"]
        })

    current_price = current_data["price"] if current_data else None

    market_status = {}
    if current_price:
        signal_type, trigger = check_signal(current_price, prev_high, prev_low)
        market_status = {
            "status": "ABOVE_PREVIOUS_HIGH" if signal_type == "BUY" else "BELOW_PREVIOUS_LOW" if signal_type == "SELL" else "WITHIN_RANGE",
            "signal_active": signal_type,
            "current_price": current_price,
            "previous_high": prev_high,
            "previous_low": prev_low,
            "distance_to_high": prev_high - current_price,
            "distance_to_low": current_price - prev_low,
            "previous_day_date": prev_data["date"] if prev_data else "manual"
        }

    return jsonify({
        "scanner_running": True,
        "last_scan": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "current_price": current_data,
        "market_status": market_status,
        "previous_day_data": {
            "high": prev_high,
            "low": prev_low,
            "close": prev_close
        },
        "email_configured": bool(os.getenv("EMAIL_SENDER")),
        "signals_history": data_store["signals_history"][-20:]
    })


@app.route('/api/scan', methods=['POST'])
def manual_scan():
    """Trigger a manual scan"""
    prev_data, current_data = get_banknifty_data()

    if not current_data:
        return jsonify({"success": False, "message": "Could not fetch data"})

    prev_high = prev_data["high"] if prev_data else data_store.get("previous_high", 0)
    prev_low = prev_data["low"] if prev_data else data_store.get("previous_low", 0)

    signal_type, trigger = check_signal(current_data["price"], prev_high, prev_low)

    if signal_type != "NEUTRAL":
        signal = {
            "signal_type": signal_type,
            "price": current_data["price"],
            "trigger_level": trigger,
            "timestamp": datetime.now().isoformat()
        }
        data_store["signals_history"].append(signal)
        return jsonify({
            "success": True,
            "message": f"{signal_type} signal at {current_data['price']:,.2f}",
            "signal": signal
        })

    return jsonify({
        "success": True,
        "message": f"No signal. Price {current_data['price']:,.2f} within range.",
        "signal": None
    })


@app.route('/api/set-data', methods=['POST'])
def set_data():
    """Manually set previous day data"""
    data = request.get_json()

    data_store["previous_high"] = float(data.get("previous_high", 0))
    data_store["previous_low"] = float(data.get("previous_low", 0))
    data_store["previous_close"] = float(data.get("previous_close", 0))

    return jsonify({
        "success": True,
        "message": "Data updated successfully",
        "data": data_store
    })


@app.route('/api/test-email', methods=['POST'])
def test_email():
    """Test email configuration"""
    return jsonify({
        "success": False,
        "message": "Email not configured. Set EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVER in Vercel environment variables."
    })


# Vercel serverless handler
def handler(request):
    return app(request)
