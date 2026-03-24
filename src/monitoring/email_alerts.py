"""
Email Alert System

Sends email alerts for trading events using free Gmail SMTP.
"""

import os
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class EmailAlerts:
    """Sends email alerts for trading events"""

    def __init__(
        self,
        enabled: Optional[bool] = None,
        from_email: Optional[str] = None,
        password: Optional[str] = None,
        to_email: Optional[str] = None,
        smtp_server: Optional[str] = None,
        smtp_port: Optional[int] = None
    ):
        """
        Initialize email alert system

        Args:
            enabled: Whether alerts are enabled (default: from env EMAIL_ENABLED)
            from_email: Sender email (default: from env EMAIL_FROM)
            password: Gmail app password (default: from env EMAIL_PASSWORD)
            to_email: Recipient email (default: from env EMAIL_TO)
            smtp_server: SMTP server (default: smtp.gmail.com)
            smtp_port: SMTP port (default: 587)
        """
        self.enabled = enabled if enabled is not None else os.getenv('EMAIL_ENABLED', 'true').lower() == 'true'
        self.from_email = from_email or os.getenv('EMAIL_FROM')
        self.password = password or os.getenv('EMAIL_PASSWORD')
        self.to_email = to_email or os.getenv('EMAIL_TO')
        self.smtp_server = smtp_server or os.getenv('EMAIL_SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = smtp_port or int(os.getenv('EMAIL_SMTP_PORT', '587'))

        # Alert thresholds
        self.loss_threshold_pct = float(os.getenv('ALERT_LOSS_THRESHOLD_PCT', '1.0'))
        self.alert_circuit_breaker = os.getenv('ALERT_CIRCUIT_BREAKER', 'true').lower() == 'true'
        self.alert_daily_summary = os.getenv('ALERT_DAILY_SUMMARY', 'true').lower() == 'true'

        if not self.enabled:
            print("📧 Email alerts disabled")
            return

        if not all([self.from_email, self.password, self.to_email]):
            print("⚠️  Email credentials not configured. Set EMAIL_FROM, EMAIL_PASSWORD, EMAIL_TO in .env")
            self.enabled = False

    def _send_email(self, subject: str, body: str, html: bool = False) -> bool:
        """
        Send email via Gmail SMTP

        Args:
            subject: Email subject
            body: Email body
            html: Whether body is HTML (default: plain text)

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            return False

        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.from_email
            msg['To'] = self.to_email
            msg['Subject'] = subject

            # Add body
            mime_type = 'html' if html else 'plain'
            msg.attach(MIMEText(body, mime_type))

            # Connect to Gmail SMTP
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.from_email, self.password)
                server.send_message(msg)

            print(f"✅ Email sent: {subject}")
            return True

        except smtplib.SMTPAuthenticationError:
            print("❌ Email authentication failed. Check EMAIL_PASSWORD (use Gmail app password, not regular password)")
            return False
        except Exception as e:
            print(f"❌ Failed to send email: {e}")
            return False

    def send_large_loss_alert(self, trade_data: Dict) -> bool:
        """
        Send alert for large loss

        Args:
            trade_data: Dictionary with trade information
        """
        loss_pct = abs(trade_data.get('pnl_percent', 0))
        if loss_pct < self.loss_threshold_pct:
            return False

        subject = f"⚠️ LARGE LOSS ALERT - {trade_data.get('symbol', 'UNKNOWN')}"

        body = f"""
LARGE LOSS ALERT
================

Trade Details:
- Symbol: {trade_data.get('symbol', 'N/A')}
- Direction: {trade_data.get('direction', 'N/A')}
- Entry Price: ${trade_data.get('entry_price', 0):.2f}
- Exit Price: ${trade_data.get('exit_price', 0):.2f}
- Loss: ${trade_data.get('pnl', 0):.2f} ({loss_pct:.2f}%)
- Exit Reason: {trade_data.get('exit_reason', 'N/A')}
- Duration: {trade_data.get('duration_minutes', 0)} minutes
- Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Action Required:
- Review recent trades
- Check if circuit breaker activated
- Consider adjusting risk parameters

---
Automated alert from AlgoTrader Bot
"""

        return self._send_email(subject, body)

    def send_circuit_breaker_alert(
        self,
        consecutive_losses: int,
        total_loss: float,
        trades: Optional[list] = None
    ) -> bool:
        """
        Send alert when circuit breaker activates

        Args:
            consecutive_losses: Number of consecutive losses
            total_loss: Total loss amount
            trades: Optional list of recent losing trades
        """
        if not self.alert_circuit_breaker:
            return False

        subject = f"🚨 CIRCUIT BREAKER ACTIVATED - {consecutive_losses} Consecutive Losses"

        body = f"""
CIRCUIT BREAKER ACTIVATED
=========================

Trading has been STOPPED automatically due to consecutive losses.

Summary:
- Consecutive Losses: {consecutive_losses}
- Total Loss: ${total_loss:.2f}
- Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

"""

        if trades:
            body += "\nRecent Losing Trades:\n"
            for i, trade in enumerate(trades[-5:], 1):  # Last 5 trades
                body += f"{i}. {trade.get('symbol')} {trade.get('direction')} - ${trade.get('pnl', 0):.2f} ({trade.get('exit_reason', 'N/A')})\n"

        body += """
Action Required:
- Review what went wrong with recent trades
- Check market conditions (trending vs choppy)
- Consider adjusting strategy parameters
- Manual reset required before resuming trading

DO NOT resume trading until you've analyzed the issue!

---
Automated alert from AlgoTrader Bot
"""

        return self._send_email(subject, body)

    def send_daily_summary(
        self,
        date: str,
        metrics: Dict
    ) -> bool:
        """
        Send daily trading summary

        Args:
            date: Date string (YYYY-MM-DD)
            metrics: Dictionary with daily metrics
        """
        if not self.alert_daily_summary:
            return False

        total_trades = metrics.get('total_trades', 0)
        winners = metrics.get('winners', 0)
        losers = metrics.get('losers', 0)
        win_rate = metrics.get('win_rate', 0)
        daily_pnl = metrics.get('daily_pnl', 0)
        daily_return = metrics.get('daily_return', 0)
        best_trade = metrics.get('best_trade', 0)
        worst_trade = metrics.get('worst_trade', 0)
        equity = metrics.get('equity', 0)
        drawdown = metrics.get('drawdown', 0)

        # Emoji based on P&L
        emoji = "📈" if daily_pnl > 0 else "📉" if daily_pnl < 0 else "➖"

        subject = f"{emoji} Daily Trading Summary - {date} (${daily_pnl:+.2f})"

        body = f"""
DAILY TRADING SUMMARY
====================
Date: {date}

Trading Activity:
- Total Trades: {total_trades}
- Winners: {winners} ({win_rate:.1f}%)
- Losers: {losers} ({100-win_rate:.1f}%)

Performance:
- Daily P&L: ${daily_pnl:+.2f} ({daily_return:+.2f}%)
- Best Trade: ${best_trade:+.2f}
- Worst Trade: ${worst_trade:.2f}

Account Status:
- Current Equity: ${equity:,.2f}
- Drawdown: {drawdown:.2f}%

"""

        # Add notes based on performance
        if daily_pnl > 0:
            body += "✅ Positive day! Keep following the strategy.\n"
        elif daily_pnl < 0:
            body += "⚠️  Negative day. Review trades and market conditions.\n"
        else:
            body += "No trading activity or break-even day.\n"

        if drawdown > 10:
            body += f"\n⚠️  WARNING: Drawdown at {drawdown:.2f}% (threshold: 10%)\n"

        body += """
---
Automated alert from AlgoTrader Bot
"""

        return self._send_email(subject, body)

    def send_system_error(
        self,
        error_type: str,
        error_message: str,
        details: Optional[Dict] = None
    ) -> bool:
        """
        Send alert for system errors

        Args:
            error_type: Type of error (e.g., "Connection", "Data", "Execution")
            error_message: Error message
            details: Optional dictionary with additional details
        """
        subject = f"❌ SYSTEM ERROR - {error_type}"

        body = f"""
SYSTEM ERROR ALERT
==================

Error Type: {error_type}
Error Message: {error_message}
Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

"""

        if details:
            body += "\nAdditional Details:\n"
            for key, value in details.items():
                body += f"- {key}: {value}\n"

        body += """
Action Required:
- Check system logs
- Verify connections (IB Gateway, network)
- Restart bot if necessary

---
Automated alert from AlgoTrader Bot
"""

        return self._send_email(subject, body)

    def send_backtest_complete(
        self,
        strategy_name: str,
        metrics: Dict
    ) -> bool:
        """
        Send backtest completion summary

        Args:
            strategy_name: Name of strategy tested
            metrics: Dictionary with backtest results
        """
        total_trades = metrics.get('total_trades', 0)
        win_rate = metrics.get('win_rate', 0)
        profit_factor = metrics.get('profit_factor', 0)
        total_return = metrics.get('total_return', 0)
        max_drawdown = metrics.get('max_drawdown', 0)
        sharpe = metrics.get('sharpe_ratio', 0)

        # Grade the strategy
        if total_return > 100 and max_drawdown < 15 and profit_factor > 2:
            grade = "🏆 EXCELLENT"
        elif total_return > 50 and max_drawdown < 20 and profit_factor > 1.5:
            grade = "✅ GOOD"
        elif total_return > 0 and max_drawdown < 30:
            grade = "⚠️  MARGINAL"
        else:
            grade = "❌ POOR"

        subject = f"📊 Backtest Complete - {strategy_name} ({grade})"

        body = f"""
BACKTEST COMPLETE
=================

Strategy: {strategy_name}
Grade: {grade}

Performance Metrics:
- Total Trades: {total_trades}
- Win Rate: {win_rate:.2f}%
- Profit Factor: {profit_factor:.2f}
- Total Return: {total_return:+.2f}%
- Max Drawdown: {max_drawdown:.2f}%
- Sharpe Ratio: {sharpe:.2f}

"""

        if grade.startswith("🏆"):
            body += "✅ Strategy looks promising! Ready for walk-forward testing.\n"
        elif grade.startswith("✅"):
            body += "Strategy shows potential. Consider further optimization.\n"
        elif grade.startswith("⚠️"):
            body += "⚠️  Strategy needs improvement. Review parameters.\n"
        else:
            body += "❌ Strategy not recommended. Consider alternative approach.\n"

        body += """
Next Steps:
- Review equity curve and trade details
- Run walk-forward validation
- Test on different time periods
- Check Grafana dashboard for visualizations

---
Automated alert from AlgoTrader Bot
"""

        return self._send_email(subject, body)

    def send_test_email(self) -> bool:
        """Send a test email to verify configuration"""
        subject = "✅ Test Email - AlgoTrader Bot"

        body = f"""
TEST EMAIL
==========

This is a test email from your AlgoTrader bot.

Configuration:
- From: {self.from_email}
- To: {self.to_email}
- SMTP Server: {self.smtp_server}:{self.smtp_port}
- Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

If you received this email, your alert system is working correctly! ✅

Alert Settings:
- Large Loss Threshold: {self.loss_threshold_pct}%
- Circuit Breaker Alerts: {self.alert_circuit_breaker}
- Daily Summary: {self.alert_daily_summary}

---
Automated alert from AlgoTrader Bot
"""

        return self._send_email(subject, body)


def test_email_alerts():
    """Test the email alert system"""
    print("\n📧 Testing Email Alert System...\n")

    try:
        # Initialize alerts
        alerts = EmailAlerts()

        if not alerts.enabled:
            print("❌ Email alerts are disabled or not configured")
            print("\nTo enable:")
            print("1. Set up Gmail app password (see MONITORING_SETUP_GUIDE.md)")
            print("2. Configure .env file with EMAIL_FROM, EMAIL_PASSWORD, EMAIL_TO")
            sys.exit(1)

        # Send test email
        print("Sending test email...")
        success = alerts.send_test_email()

        if success:
            print("\n✅ Test email sent successfully!")
            print(f"   Check inbox: {alerts.to_email}")
            print("\nYou can also test individual alert types:")
            print("- alerts.send_large_loss_alert(...)")
            print("- alerts.send_circuit_breaker_alert(...)")
            print("- alerts.send_daily_summary(...)")
        else:
            print("\n❌ Failed to send test email")
            print("   Check your .env configuration")

    except Exception as e:
        print(f"\n❌ Test failed: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Email Alert System')
    parser.add_argument('--test', action='store_true', help='Send test email')
    args = parser.parse_args()

    if args.test:
        test_email_alerts()
    else:
        print("Usage: python email_alerts.py --test")
        print("\nThis module is typically imported and used by the backtester or trading bot.")
        print("Run with --test flag to send a test email and verify configuration.")
