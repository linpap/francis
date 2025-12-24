# Francis - BankNifty Trading Scanner

A trading signal scanner that monitors BankNifty and generates BUY/SELL signals based on previous day's high/low breakout strategy.

## Strategy

- **BUY Signal**: When current price breaks above previous day's HIGH
- **SELL Signal**: When current price breaks below previous day's LOW

## Features

- Real-time BankNifty price monitoring from NSE India
- Automated scanning every 15 minutes
- Email alerts on signal generation
- Web-based dashboard UI
- Signal history tracking

## Setup

1. **Install dependencies:**
   ```bash
   cd /Users/soumyajitsarkar/Desktop/code/francis
   pip install -r requirements.txt
   ```

2. **Configure email alerts (optional):**
   Edit `.env` file with your email credentials:
   ```
   EMAIL_SENDER=your_email@gmail.com
   EMAIL_PASSWORD=your_app_password
   EMAIL_RECEIVER=receiver_email@gmail.com
   ```

   For Gmail, use an [App Password](https://support.google.com/accounts/answer/185833) instead of your regular password.

3. **Run the app:**
   ```bash
   python app.py
   ```

4. **Open dashboard:**
   Visit `http://localhost:5000` in your browser

## Project Structure

```
francis/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── .env                   # Configuration (email, etc.)
├── src/
│   ├── data_fetcher.py   # NSE data fetching
│   ├── signal_generator.py # Breakout signal logic
│   ├── email_alert.py    # Email notification system
│   └── scanner.py        # Scheduled scanner
└── templates/
    └── index.html        # Dashboard UI
```

## API Endpoints

- `GET /` - Dashboard UI
- `GET /api/status` - Current scanner status
- `POST /api/scan` - Trigger manual scan
- `POST /api/test-email` - Send test email
- `GET /api/signals` - Get signals history
- `POST /api/refresh-data` - Refresh previous day data
