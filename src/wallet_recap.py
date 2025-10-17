"""
Wallet recap builder for 24-hour trading summaries.
Calculates P&L, trade counts, and formats trade history.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class WalletRecap:
    """Builds comprehensive 24-hour trading recap for a wallet."""

    def __init__(self, wallet_address: str, positions: List[Dict], fills: List[Dict], api_client=None):
        """
        Initialize recap builder.

        Args:
            wallet_address: Wallet being analyzed
            positions: Current open positions
            fills: Trade fills from last 24 hours
            api_client: Optional HyperliquidAPI instance for asset name resolution
        """
        self.wallet = wallet_address
        self.positions = positions
        self.fills = fills
        self.api_client = api_client

    def build_summary(self) -> Dict:
        """
        Build comprehensive wallet summary.

        Returns:
            Dictionary with:
                - wallet: address
                - overall_pnl: total unrealized P&L across all open positions
                - daily_pnl: realized + unrealized P&L from last 24h trades
                - trade_count: number of trades in last 24h
                - trades: list of formatted trade dictionaries
                - has_activity: boolean if any trades in 24h
        """
        overall_pnl = self._calculate_overall_pnl()
        daily_pnl = self._calculate_daily_pnl()
        trade_count = len(self.fills)
        trades = self._format_trades()

        summary = {
            "wallet": self.wallet,
            "wallet_short": self._format_address(self.wallet),
            "overall_pnl": overall_pnl,
            "daily_pnl": daily_pnl,
            "trade_count": trade_count,
            "trades": trades,
            "has_activity": trade_count > 0,
            "position_count": len(self.positions)
        }

        logger.debug(f"Built summary for {self.wallet}: {trade_count} trades, ${daily_pnl:,.2f} daily P&L")
        return summary

    def _calculate_overall_pnl(self) -> float:
        """Calculate total unrealized P&L from all open positions."""
        total_pnl = 0.0
        for pos in self.positions:
            total_pnl += pos.get("unrealized_pnl", 0.0)
        return total_pnl

    def _calculate_daily_pnl(self) -> float:
        """
        Calculate P&L from last 24h trades.
        Sum of closedPnl from all fills.
        """
        daily_pnl = 0.0
        for fill in self.fills:
            # closedPnl is the realized P&L from this trade
            closed_pnl = float(fill.get("closedPnl", 0))
            daily_pnl += closed_pnl

        return daily_pnl

    def _format_trades(self) -> List[Dict]:
        """
        Format fills into readable trade summaries.

        Returns:
            List of trade dictionaries with formatted fields
        """
        formatted_trades = []

        for fill in self.fills:
            try:
                # Parse fill data
                coin = fill.get("coin", "UNKNOWN")

                # Resolve asset name if it's an ID like "@107"
                if self.api_client and coin.startswith("@"):
                    coin = self.api_client.resolve_asset_name(coin)

                direction = fill.get("dir", "")  # e.g., "Open Long", "Close Short"
                price = float(fill.get("px", 0))
                size = float(fill.get("sz", 0))
                side = fill.get("side", "")  # "B" for buy, "A" for ask/sell
                closed_pnl = float(fill.get("closedPnl", 0))
                timestamp = fill.get("time", 0)
                start_position = float(fill.get("startPosition", 0))

                # Determine trade type
                trade_type = self._determine_trade_type(direction, start_position, size)

                # Format timestamp
                dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
                time_str = dt.strftime("%H:%M UTC")

                # Calculate trade value
                value = price * abs(size)

                trade = {
                    "asset": coin,
                    "type": trade_type,
                    "direction": direction,
                    "side": side,
                    "price": price,
                    "size": abs(size),
                    "value": value,
                    "pnl": closed_pnl,
                    "time": time_str,
                    "timestamp": timestamp,
                    "raw_direction": direction
                }

                formatted_trades.append(trade)

            except (ValueError, KeyError) as e:
                logger.error(f"Error formatting trade: {e}")
                continue

        # Sort by timestamp (most recent first)
        formatted_trades.sort(key=lambda x: x["timestamp"], reverse=True)

        return formatted_trades

    def _determine_trade_type(self, direction: str, start_position: float, size: float) -> str:
        """
        Determine trade type from direction and position changes.

        Args:
            direction: Trade direction (e.g., "Open Long", "Close Short")
            start_position: Position size before trade
            size: Trade size (can be negative)

        Returns:
            Trade type: OPEN, CLOSE, INCREASE, REDUCE
        """
        direction_lower = direction.lower()

        if "open" in direction_lower:
            return "OPEN"
        elif "close" in direction_lower:
            return "CLOSE"
        else:
            # Determine from position changes
            if start_position == 0:
                return "OPEN"
            elif abs(start_position + size) < abs(start_position):
                return "REDUCE"
            elif abs(start_position + size) > abs(start_position):
                return "INCREASE"
            else:
                return "CLOSE"

    @staticmethod
    def _format_address(address: str) -> str:
        """Format wallet address for display."""
        if len(address) > 10:
            return f"{address[:6]}...{address[-4:]}"
        return address
