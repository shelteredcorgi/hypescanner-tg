"""
Telegram notification service for 24-hour wallet recaps.
Sends clean, emoji-rich summaries of wallet trading activity.
"""

import logging
from datetime import datetime, timezone
from typing import Dict
from telegram import Bot
from telegram.error import TelegramError
import asyncio
from src import config

logger = logging.getLogger(__name__)


class RecapNotifier:
    """Handles sending 24-hour recap messages to Telegram."""

    def __init__(self):
        """Initialize Telegram bot."""
        self.bot_token = config.TELEGRAM_BOT_TOKEN
        self.chat_id = config.TELEGRAM_CHAT_ID
        self.bot = None

        if self.bot_token:
            self.bot = Bot(token=self.bot_token)
            logger.info("Recap notifier initialized")
        else:
            logger.warning("Telegram bot token not configured")

    async def send_message_async(self, message: str) -> bool:
        """Send message to Telegram."""
        if not self.bot:
            logger.error("Telegram bot not initialized")
            return False

        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            logger.info("Telegram recap message sent successfully")
            return True

        except TelegramError as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    def send_message(self, message: str) -> bool:
        """Synchronous wrapper for sending messages."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.send_message_async(message))

    def send_wallet_recap(self, summary: Dict) -> bool:
        """
        Send 24-hour recap for a single wallet.

        Args:
            summary: Wallet summary dictionary from WalletRecap

        Returns:
            True if sent successfully
        """
        message = self._format_recap_message(summary)
        return self.send_message(message)

    def _format_recap_message(self, summary: Dict) -> str:
        """
        Format wallet summary into beautiful Telegram message.

        Args:
            summary: Wallet summary with trades, P&L, etc.

        Returns:
            HTML-formatted message string
        """
        wallet_short = summary["wallet_short"]
        wallet_full = summary["wallet"]
        wallet_url = f"https://hyperdash.info/trader/{wallet_full}"
        wallet_link = f"<a href='{wallet_url}'>{wallet_short}</a>"

        overall_pnl = summary["overall_pnl"]
        daily_pnl = summary["daily_pnl"]
        trade_count = summary["trade_count"]
        position_count = summary["position_count"]
        trades = summary["trades"]

        # Format P&L with colors
        overall_sign = "+" if overall_pnl >= 0 else ""
        daily_sign = "+" if daily_pnl >= 0 else ""

        overall_emoji = "🟢" if overall_pnl >= 0 else "🔴"
        daily_emoji = "📈" if daily_pnl >= 0 else "📉"

        # Build header
        now_utc = datetime.now(timezone.utc)
        timestamp = now_utc.strftime("%b %d, %H:%M UTC")

        lines = [
            f"<b>📊 24H Recap: {wallet_link}</b>",
            f"<i>{timestamp}</i>",
            "",
            f"{overall_emoji} <b>Overall P&L:</b> {overall_sign}${overall_pnl:,.2f}",
            f"{daily_emoji} <b>24H P&L:</b> {daily_sign}${daily_pnl:,.2f}",
            f"📝 <b>Trades:</b> {trade_count} | <b>Positions:</b> {position_count}",
        ]

        # Add trades section if there are any
        # Limit to 20 most recent trades to avoid message length issues
        MAX_TRADES = 20

        if trades:
            lines.append("")

            if len(trades) > MAX_TRADES:
                lines.append(f"<b>━━━ LATEST {MAX_TRADES} TRADES ━━━</b>")
                lines.append(f"<i>Showing {MAX_TRADES} of {trade_count} total</i>")
            else:
                lines.append("<b>━━━ TRADES ━━━</b>")

            lines.append("")

            # Show only first MAX_TRADES
            for trade in trades[:MAX_TRADES]:
                trade_line = self._format_trade(trade)
                lines.append(trade_line)

            # Add note if there are more trades
            if len(trades) > MAX_TRADES:
                remaining = len(trades) - MAX_TRADES
                lines.append("")
                lines.append(f"<i>... and {remaining} more trades</i>")
        else:
            lines.append("")
            lines.append("💤 <i>No trades in the last 24 hours</i>")

        return "\n".join(lines)

    def _format_trade(self, trade: Dict) -> str:
        """
        Format a single trade into a clean line.

        Args:
            trade: Trade dictionary

        Returns:
            Formatted trade string with emojis
        """
        asset = trade["asset"]
        trade_type = trade["type"]  # OPEN, CLOSE, INCREASE, REDUCE
        direction = trade["raw_direction"]  # "Open Long", "Close Short", etc.
        price = trade["price"]
        value = trade["value"]
        pnl = trade["pnl"]
        time = trade["time"]

        # Determine emoji based on trade type and direction
        is_long = "long" in direction.lower()
        is_short = "short" in direction.lower()

        if trade_type == "OPEN":
            if is_long:
                emoji = "🟢"
                action = "OPEN LONG"
            else:
                emoji = "🔴"
                action = "OPEN SHORT"
        elif trade_type == "CLOSE":
            if is_long:
                emoji = "✅"
                action = "CLOSE LONG"
            else:
                emoji = "❌"
                action = "CLOSE SHORT"
        elif trade_type == "INCREASE":
            if is_long:
                emoji = "📈"
                action = "ADD LONG"
            else:
                emoji = "📉"
                action = "ADD SHORT"
        elif trade_type == "REDUCE":
            if is_long:
                emoji = "📊"
                action = "REDUCE LONG"
            else:
                emoji = "📊"
                action = "REDUCE SHORT"
        else:
            emoji = "🔵"
            action = trade_type

        # Format P&L
        pnl_str = ""
        if pnl != 0:
            pnl_sign = "+" if pnl >= 0 else ""
            pnl_str = f" | P&L: {pnl_sign}${pnl:,.2f}"

        # Build trade line
        trade_line = (
            f"{emoji} <b>{asset}</b> {action}\n"
            f"   ${value:,.0f} @ ${price:,.2f}{pnl_str}\n"
            f"   <i>{time}</i>"
        )

        return trade_line

    def send_startup_message(self) -> bool:
        """Send startup notification."""
        now = datetime.now(timezone.utc)
        timestamp = now.strftime("%b %d, %Y %H:%M UTC")

        message = (
            f"🚀 <b>Hyperliquid 24H Tracker Started</b>\n"
            f"<i>{timestamp}</i>\n\n"
            f"Generating 24-hour recaps for tracked wallets..."
        )

        return self.send_message(message)

    def send_bot_summary(self, bot_traders: list) -> bool:
        """
        Send condensed summary for bot traders.

        Args:
            bot_traders: List of wallet summaries for bot traders

        Returns:
            True if sent successfully
        """
        if not bot_traders:
            return True

        # Build summary message
        now_utc = datetime.now(timezone.utc)
        timestamp = now_utc.strftime("%b %d, %H:%M UTC")

        lines = [
            f"<b>🤖 Bot Traders Summary</b>",
            f"<i>{timestamp}</i>",
            "",
            f"<b>{len(bot_traders)} automated trading wallets</b>",
            ""
        ]

        # Aggregate stats
        total_trades = sum(b["trade_count"] for b in bot_traders)
        total_daily_pnl = sum(b["daily_pnl"] for b in bot_traders)
        total_overall_pnl = sum(b["overall_pnl"] for b in bot_traders)

        # P&L formatting
        daily_sign = "+" if total_daily_pnl >= 0 else ""
        overall_sign = "+" if total_overall_pnl >= 0 else ""
        daily_emoji = "📈" if total_daily_pnl >= 0 else "📉"
        overall_emoji = "🟢" if total_overall_pnl >= 0 else "🔴"

        lines.extend([
            f"{overall_emoji} <b>Combined Overall P&L:</b> {overall_sign}${total_overall_pnl:,.0f}",
            f"{daily_emoji} <b>Combined 24H P&L:</b> {daily_sign}${total_daily_pnl:,.0f}",
            f"📊 <b>Total Trades:</b> {total_trades:,}",
            "",
            "<b>━━━ INDIVIDUAL BOTS ━━━</b>",
            ""
        ])

        # Sort by daily P&L (best to worst)
        sorted_bots = sorted(bot_traders, key=lambda x: x["daily_pnl"], reverse=True)

        # List each bot concisely
        for bot in sorted_bots:
            wallet_url = f"https://hyperdash.info/trader/{bot['wallet']}"
            wallet_link = f"<a href='{wallet_url}'>{bot['wallet_short']}</a>"

            pnl_sign = "+" if bot["daily_pnl"] >= 0 else ""
            pnl_emoji = "💚" if bot["daily_pnl"] >= 0 else "💔"

            line = (
                f"{pnl_emoji} {wallet_link}\n"
                f"   Trades: {bot['trade_count']:,} | "
                f"24H: {pnl_sign}${bot['daily_pnl']:,.0f}"
            )
            lines.append(line)

        message = "\n".join(lines)
        return self.send_message(message)

    def send_completion_message(self, wallet_count: int, total_trades: int) -> bool:
        """Send completion summary."""
        message = (
            f"✅ <b>Recap Complete</b>\n\n"
            f"Processed {wallet_count} wallets\n"
            f"Total trades: {total_trades}"
        )

        return self.send_message(message)
