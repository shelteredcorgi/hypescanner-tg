"""
Hyperliquid API client for fetching position data.
Uses the official hyperliquid-python-sdk with retry logic and error handling.
"""

import time
import logging
from typing import Dict, List, Optional
from hyperliquid.info import Info
from hyperliquid.utils import constants
from src import config

logger = logging.getLogger(__name__)


class HyperliquidAPIError(Exception):
    """Custom exception for Hyperliquid API errors."""
    pass


class HyperliquidAPI:
    """Client for interacting with Hyperliquid API using official SDK."""

    def __init__(self):
        self.max_retries = config.MAX_RETRIES
        self.retry_delay = config.RETRY_DELAY

        # Determine if using mainnet or testnet
        self.base_url = config.HYPERLIQUID_API_URL
        if "testnet" in self.base_url.lower():
            api_url = constants.TESTNET_API_URL
        else:
            api_url = constants.MAINNET_API_URL

        # Initialize the SDK Info client (read-only, no websocket needed)
        self.info = Info(api_url, skip_ws=True)
        logger.info(f"Initialized Hyperliquid SDK with {api_url}")

        # Cache for asset metadata mapping
        self._asset_name_cache = None

    def _retry_wrapper(self, func, *args, **kwargs):
        """
        Wrapper to add retry logic to SDK calls.

        Args:
            func: Function to call
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            HyperliquidAPIError: If all retries fail
        """
        last_error = None

        for retry_count in range(self.max_retries + 1):
            try:
                result = func(*args, **kwargs)
                return result

            except Exception as e:
                last_error = e
                logger.warning(f"API call failed: {e}")

                if retry_count < self.max_retries:
                    wait_time = self.retry_delay * (2 ** retry_count)  # Exponential backoff
                    logger.info(f"Retrying in {wait_time}s (attempt {retry_count + 1}/{self.max_retries})...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Max retries reached")

        raise HyperliquidAPIError(f"Request failed after {self.max_retries} retries: {last_error}")

    def get_user_state(self, wallet_address: str) -> Optional[Dict]:
        """
        Fetch user state including positions for a wallet address.

        Args:
            wallet_address: Ethereum address to query

        Returns:
            User state data or None if error

        Uses SDK: info.user_state(address)
        """
        try:
            logger.debug(f"Fetching user state for {wallet_address}")
            user_state = self._retry_wrapper(self.info.user_state, wallet_address)
            logger.debug(f"Received user state: {user_state}")
            return user_state
        except HyperliquidAPIError as e:
            logger.error(f"Failed to fetch user state for {wallet_address}: {e}")
            return None

    def get_meta_info(self) -> Optional[Dict]:
        """
        Fetch meta information including all available trading pairs.

        Returns:
            Meta information or None if error

        Uses SDK: info.meta()
        """
        try:
            logger.debug("Fetching meta info")
            meta = self._retry_wrapper(self.info.meta)
            logger.debug(f"Received meta info")
            return meta
        except HyperliquidAPIError as e:
            logger.error(f"Failed to fetch meta info: {e}")
            return None

    def parse_positions(self, user_state: Dict, wallet_address: str) -> List[Dict]:
        """
        Parse user state response into structured position data.

        Args:
            user_state: Raw API response from get_user_state
            wallet_address: Address being queried

        Returns:
            List of position dictionaries with all required fields
        """
        if not user_state or "assetPositions" not in user_state:
            logger.debug(f"No positions found for {wallet_address}")
            return []

        positions = []
        asset_positions = user_state.get("assetPositions", [])

        for pos in asset_positions:
            try:
                position_data = pos.get("position", {})

                # Skip if no position size
                szi = float(position_data.get("szi", 0))
                if szi == 0:
                    continue

                # Extract position data
                coin = position_data.get("coin", "UNKNOWN")
                entry_px = float(position_data.get("entryPx", 0))
                position_value = float(position_data.get("positionValue", 0))
                unrealized_pnl = float(position_data.get("unrealizedPnl", 0))
                liquidation_px = position_data.get("liquidationPx")
                margin_used = float(position_data.get("marginUsed", 0))

                # Determine position type
                position_type = "LONG" if szi > 0 else "SHORT"

                # Get current/mark price (approximation from position value and size)
                current_price = abs(position_value / szi) if szi != 0 else entry_px

                # Calculate PnL percentage
                pnl_percentage = (unrealized_pnl / abs(position_value)) * 100 if position_value != 0 else 0

                position = {
                    "wallet": wallet_address,
                    "asset": coin,
                    "type": position_type,
                    "size": abs(szi),
                    "position_value": abs(position_value),
                    "entry_price": entry_px,
                    "current_price": current_price,
                    "liquidation_price": liquidation_px,
                    "unrealized_pnl": unrealized_pnl,
                    "pnl_percentage": pnl_percentage,
                    "margin_used": margin_used,
                    "funding_rate": 0.0,  # Can be enhanced with funding rate data
                }

                positions.append(position)
                logger.debug(f"Parsed position: {coin} {position_type} ${abs(position_value):,.2f}")

            except (KeyError, ValueError, TypeError) as e:
                logger.error(f"Error parsing position for {wallet_address}: {e}")
                logger.debug(f"Problematic position data: {pos}")
                continue

        return positions

    def get_positions(self, wallet_address: str) -> List[Dict]:
        """
        Fetch and parse positions for a wallet address.

        Args:
            wallet_address: Ethereum address to query

        Returns:
            List of parsed position dictionaries
        """
        logger.debug(f"Fetching positions for {wallet_address}")
        user_state = self.get_user_state(wallet_address)

        if not user_state:
            return []

        positions = self.parse_positions(user_state, wallet_address)
        logger.info(f"Fetched {len(positions)} positions from {self._format_address(wallet_address)}")
        return positions

    def get_user_fills_24h(self, wallet_address: str) -> List[Dict]:
        """
        Fetch user trade fills from the last 24 hours.

        Args:
            wallet_address: Ethereum address to query

        Returns:
            List of fill (trade) dictionaries
        """
        try:
            from datetime import datetime, timezone, timedelta

            # Calculate 24 hours ago in milliseconds
            now = datetime.now(timezone.utc)
            start_time = int((now - timedelta(hours=24)).timestamp() * 1000)

            logger.debug(f"Fetching fills for {wallet_address} from last 24h")
            fills = self._retry_wrapper(
                self.info.user_fills_by_time,
                wallet_address,
                start_time,
                aggregate_by_time=True
            )

            logger.info(f"Fetched {len(fills) if fills else 0} fills for {self._format_address(wallet_address)}")
            return fills or []

        except HyperliquidAPIError as e:
            logger.error(f"Failed to fetch fills for {wallet_address}: {e}")
            return []

    def get_user_portfolio(self, wallet_address: str) -> Optional[Dict]:
        """
        Fetch user portfolio performance data including historical P&L.

        Args:
            wallet_address: Ethereum address to query

        Returns:
            Portfolio data with performance across multiple timeframes
        """
        try:
            import requests

            url = "https://api.hyperliquid.xyz/info"
            payload = {
                "type": "portfolio",
                "user": wallet_address
            }

            logger.debug(f"Fetching portfolio for {wallet_address}")
            response = requests.post(url, json=payload, timeout=self.max_retries * 10)

            if response.status_code == 200:
                data = response.json()
                logger.debug(f"Received portfolio data for {self._format_address(wallet_address)}")
                return data
            else:
                logger.error(f"Failed to fetch portfolio: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Failed to fetch portfolio for {wallet_address}: {e}")
            return None

    def get_account_value(self, wallet_address: str) -> Optional[float]:
        """
        Get total account value (equity) for a wallet.

        Args:
            wallet_address: Ethereum address to query

        Returns:
            Account value in USD or None if error
        """
        try:
            user_state = self.get_user_state(wallet_address)

            if not user_state:
                return None

            # Extract account value from marginSummary
            margin_summary = user_state.get("marginSummary", {})
            account_value = float(margin_summary.get("accountValue", 0))

            logger.debug(f"Account value for {self._format_address(wallet_address)}: ${account_value:,.2f}")
            return account_value

        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Failed to get account value for {wallet_address}: {e}")
            return None

    def get_asset_name_mapping(self) -> Dict[str, str]:
        """
        Build mapping from asset indices to ticker names.
        Caches the result to avoid repeated API calls.

        Returns:
            Dictionary mapping "@123" style indices to ticker names
        """
        if self._asset_name_cache is not None:
            return self._asset_name_cache

        try:
            meta = self.get_meta_info()
            if not meta or "universe" not in meta:
                logger.warning("Failed to fetch asset metadata")
                return {}

            # Build mapping from index to name
            mapping = {}
            for i, asset in enumerate(meta["universe"]):
                name = asset.get("name", f"@{i}")
                mapping[f"@{i}"] = name
                logger.debug(f"Asset mapping: @{i} -> {name}")

            self._asset_name_cache = mapping
            logger.info(f"Cached {len(mapping)} asset name mappings")
            return mapping

        except Exception as e:
            logger.error(f"Failed to build asset name mapping: {e}")
            return {}

    def resolve_asset_name(self, asset_id: str) -> str:
        """
        Convert asset ID (e.g., "@107") to proper ticker name.

        Args:
            asset_id: Asset identifier (may be "@123" or already a ticker)

        Returns:
            Proper ticker name or original if not found
        """
        if not asset_id.startswith("@"):
            return asset_id

        mapping = self.get_asset_name_mapping()
        return mapping.get(asset_id, asset_id)

    @staticmethod
    def _format_address(address: str) -> str:
        """Format wallet address for display (0x1a2b...7x8y)."""
        if len(address) > 10:
            return f"{address[:6]}...{address[-6:]}"
        return address
