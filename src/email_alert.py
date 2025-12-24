"""
Email Alert System - Sends trading signal alerts via email
"""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class EmailAlertSystem:
    """Handles sending email alerts for trading signals"""

    def __init__(self):
        self.sender_email = os.getenv("EMAIL_SENDER", "")
        self.sender_password = os.getenv("EMAIL_PASSWORD", "")
        self.receiver_email = os.getenv("EMAIL_RECEIVER", "")
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.enabled = bool(self.sender_email and self.sender_password and self.receiver_email)

    def is_configured(self) -> bool:
        """Check if email is properly configured"""
        return self.enabled

    def send_signal_alert(self, signal_type: str, price: float, trigger_level: float,
                          prev_high: float, prev_low: float) -> bool:
        """
        Send email alert for a trading signal.

        Args:
            signal_type: "BUY" or "SELL"
            price: Current price when signal triggered
            trigger_level: The high/low level that was broken
            prev_high: Previous day's high
            prev_low: Previous day's low

        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.enabled:
            print("Email not configured. Skipping alert.")
            return False

        try:
            subject = f"🚨 BankNifty {signal_type} Signal Alert!"

            # Create HTML email body
            if signal_type == "BUY":
                emoji = "🟢"
                action = "BULLISH BREAKOUT"
                color = "#28a745"
                description = f"Price broke above previous day's HIGH ({trigger_level:,.2f})"
            else:
                emoji = "🔴"
                action = "BEARISH BREAKDOWN"
                color = "#dc3545"
                description = f"Price broke below previous day's LOW ({trigger_level:,.2f})"

            html_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; border: 2px solid {color}; border-radius: 10px; padding: 20px;">
                    <h1 style="color: {color}; text-align: center;">
                        {emoji} BankNifty {signal_type} Signal {emoji}
                    </h1>

                    <div style="background-color: {color}; color: white; padding: 15px; border-radius: 5px; text-align: center; margin: 20px 0;">
                        <h2 style="margin: 0;">{action}</h2>
                    </div>

                    <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                        <tr style="background-color: #f8f9fa;">
                            <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>Current Price</strong></td>
                            <td style="padding: 10px; border: 1px solid #dee2e6; font-size: 18px; font-weight: bold;">{price:,.2f}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>Trigger Level</strong></td>
                            <td style="padding: 10px; border: 1px solid #dee2e6;">{trigger_level:,.2f}</td>
                        </tr>
                        <tr style="background-color: #f8f9fa;">
                            <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>Previous Day High</strong></td>
                            <td style="padding: 10px; border: 1px solid #dee2e6;">{prev_high:,.2f}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>Previous Day Low</strong></td>
                            <td style="padding: 10px; border: 1px solid #dee2e6;">{prev_low:,.2f}</td>
                        </tr>
                        <tr style="background-color: #f8f9fa;">
                            <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>Signal Time</strong></td>
                            <td style="padding: 10px; border: 1px solid #dee2e6;">{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</td>
                        </tr>
                    </table>

                    <p style="color: #666; text-align: center; font-size: 14px;">
                        {description}
                    </p>

                    <hr style="border: none; border-top: 1px solid #dee2e6; margin: 20px 0;">

                    <p style="color: #999; font-size: 12px; text-align: center;">
                        This is an automated alert from Francis Trading App.<br>
                        Always do your own analysis before trading.
                    </p>
                </div>
            </body>
            </html>
            """

            # Plain text fallback
            text_body = f"""
            BankNifty {signal_type} Signal Alert!
            =====================================

            {action}

            Current Price: {price:,.2f}
            Trigger Level: {trigger_level:,.2f}
            Previous Day High: {prev_high:,.2f}
            Previous Day Low: {prev_low:,.2f}
            Signal Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

            {description}

            ---
            This is an automated alert from Francis Trading App.
            Always do your own analysis before trading.
            """

            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = self.sender_email
            message["To"] = self.receiver_email

            message.attach(MIMEText(text_body, "plain"))
            message.attach(MIMEText(html_body, "html"))

            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(message)

            print(f"Email alert sent successfully for {signal_type} signal")
            return True

        except Exception as e:
            print(f"Failed to send email alert: {e}")
            return False

    def send_test_email(self) -> bool:
        """Send a test email to verify configuration"""
        if not self.enabled:
            return False

        try:
            subject = "Francis Trading App - Test Email"
            body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <h2>Email Configuration Test</h2>
                <p>If you received this email, your Francis Trading App email alerts are configured correctly!</p>
                <p>Test sent at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            </body>
            </html>
            """

            message = MIMEMultipart()
            message["Subject"] = subject
            message["From"] = self.sender_email
            message["To"] = self.receiver_email
            message.attach(MIMEText(body, "html"))

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(message)

            return True
        except Exception as e:
            print(f"Test email failed: {e}")
            return False


# For testing
if __name__ == "__main__":
    alert = EmailAlertSystem()
    print(f"Email configured: {alert.is_configured()}")

    if alert.is_configured():
        # Test sending
        alert.send_signal_alert(
            signal_type="BUY",
            price=52100,
            trigger_level=52000,
            prev_high=52000,
            prev_low=51500
        )
