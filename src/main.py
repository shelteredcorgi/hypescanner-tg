"""
Generates trading recaps for tracked wallets and sends to Telegram.
Supports 24h, 1h, and incremental scan types.
Runs once then exits.
"""

import argparse
import logging
import sys
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone
from typing import Optional

from src import config
from src.hyperliquid_api import HyperliquidAPI, HyperliquidAPIError
from src.wallet_recap import WalletRecap
from src.recap_notifier import RecapNotifier
from src.state_manager import StateManager


def setup_logging():
    """Setup console and file logging."""
    import os
    os.makedirs("logs", exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    console_handler.setFormatter(console_format)

    file_handler = RotatingFileHandler(
        config.LOG_FILE,
        maxBytes=config.LOG_MAX_BYTES,
        backupCount=config.LOG_BACKUP_COUNT
    )
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(file_format)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger


class RecapGenerator:
    def __init__(self, scan_type: str = "24h"):
        """
        Initialize recap generator.

        Args:
            scan_type: Type of scan - "24h", "1h", or "incremental"
        """
        self.logger = logging.getLogger(__name__)
        self.api = HyperliquidAPI()
        self.notifier = RecapNotifier()
        self.scan_type = scan_type

    def generate_wallet_recap(self, wallet_address: str, start_timestamp_ms: Optional[int] = None) -> dict:
        """
        Build recap for one wallet based on scan type.

        Args:
            wallet_address: Wallet address to analyze
            start_timestamp_ms: Start timestamp for incremental scans (optional)

        Returns:
            Wallet summary dictionary or None on error
        """
        try:
            self.logger.info(f"Generating {self.scan_type} recap for {wallet_address[:8]}...")

            positions = self.api.get_positions(wallet_address)

            # Fetch trade history based on scan type
            if self.scan_type == "24h":
                fills = self.api.get_user_fills_24h(wallet_address)
            elif self.scan_type == "1h":
                fills = self.api.get_user_fills_1h(wallet_address)
            elif self.scan_type == "incremental":
                if start_timestamp_ms is None:
                    self.logger.error("Incremental scan requires start_timestamp_ms")
                    return None
                fills = self.api.get_user_fills_since(wallet_address, start_timestamp_ms)
            else:
                self.logger.error(f"Unknown scan type: {self.scan_type}")
                return None

            # Build recap with API client for asset name resolution
            recap = WalletRecap(wallet_address, positions, fills, api_client=self.api)
            summary = recap.build_summary()
            summary["scan_type"] = self.scan_type  # Add scan type to summary

            self.logger.info(
                f"  {summary['wallet_short']}: {summary['trade_count']} trades, "
                f"${summary['daily_pnl']:,.2f} daily P&L"
            )

            return summary

        except HyperliquidAPIError as e:
            self.logger.error(f"API error for {wallet_address}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error generating recap for {wallet_address}: {e}", exc_info=True)
            return None

    def run(self, state_manager: Optional[StateManager] = None) -> None:
        """
        Generate and send recaps for all wallets.

        Args:
            state_manager: Optional state manager for incremental scans
        """
        scan_label = self.scan_type.upper() if self.scan_type != "incremental" else "Incremental"
        self.logger.info("=" * 80)
        self.logger.info(f"Hyperliquid {scan_label} Recap Generator")
        self.logger.info("=" * 80)

        # Display configuration
        self.logger.info(config.display_config())

        # Validate configuration
        try:
            config.validate_config()
        except ValueError as e:
            self.logger.error(f"Configuration error: {e}")
            sys.exit(1)

        # Handle incremental scan setup
        start_timestamp_ms = None
        if self.scan_type == "incremental":
            if state_manager is None:
                self.logger.error("State manager required for incremental scans")
                sys.exit(1)

            start_timestamp_ms = state_manager.get_last_run_timestamp()
            if start_timestamp_ms is None:
                self.logger.warning(
                    "No previous run found for incremental scan. "
                    "Falling back to 24h scan for this run."
                )
                self.scan_type = "24h"
                start_timestamp_ms = None

        # Send startup notification
        self.notifier.send_startup_message(self.scan_type)

        # Process each wallet
        total_trades = 0
        successful_wallets = 0
        failed_wallets = 0
        filtered_wallets = 0
        bot_traders = []  # Collect bot trader summaries

        self.logger.info("")
        self.logger.info(f"Processing {len(config.WALLET_ADDRESSES)} wallets...")
        if self.scan_type == "incremental" and start_timestamp_ms:
            from datetime import datetime, timezone
            last_run_dt = datetime.fromtimestamp(start_timestamp_ms / 1000, tz=timezone.utc)
            self.logger.info(f"Incremental scan: fetching trades since {last_run_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        self.logger.info("")

        for wallet in config.WALLET_ADDRESSES:
            try:
                # Generate recap
                summary = self.generate_wallet_recap(wallet, start_timestamp_ms)

                if summary:
                    # Apply bot filter if enabled
                    if config.FILTER_BOTS:
                        trade_count = summary['trade_count']

                        # Collect bot traders for summary (too many trades)
                        if trade_count > config.MAX_TRADES_PER_DAY:
                            self.logger.info(f"  🤖 Bot trader: {summary['wallet_short']} ({trade_count} trades)")
                            bot_traders.append(summary)
                            filtered_wallets += 1
                            continue

                        # Filter out inactive wallets (skip completely)
                        if trade_count < config.MIN_TRADES_PER_DAY:
                            self.logger.info(f"  ⊘ Filtered {summary['wallet_short']} (inactive: {trade_count} trades)")
                            filtered_wallets += 1
                            continue

                    # Send detailed recap message for human traders
                    if self.notifier.send_wallet_recap(summary):
                        self.logger.info(f"  ✓ Recap sent for {summary['wallet_short']}")
                        successful_wallets += 1
                        total_trades += summary['trade_count']
                    else:
                        self.logger.warning(f"  ✗ Failed to send recap for {summary['wallet_short']}")
                        failed_wallets += 1
                else:
                    failed_wallets += 1

            except Exception as e:
                self.logger.error(f"Failed to process {wallet}: {e}")
                failed_wallets += 1

        # Send bot traders summary if any
        if bot_traders:
            self.logger.info("")
            self.logger.info(f"Sending bot traders summary ({len(bot_traders)} wallets)...")
            if self.notifier.send_bot_summary(bot_traders):
                self.logger.info("  ✓ Bot summary sent")
            else:
                self.logger.warning("  ✗ Failed to send bot summary")

        # Send completion summary
        self.logger.info("")
        self.logger.info("=" * 80)
        self.logger.info(f"Recap generation complete!")
        self.logger.info(f"Success: {successful_wallets} | Failed: {failed_wallets} | Filtered: {filtered_wallets}")
        self.logger.info(f"  Bot traders: {len(bot_traders)} (sent as summary)")
        self.logger.info(f"Total trades processed: {total_trades}")
        self.logger.info("=" * 80)

        self.notifier.send_completion_message(successful_wallets, total_trades)

        # Update state after successful completion
        if state_manager is not None:
            state_manager.update_state(self.scan_type)


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Hyperliquid wallet recap generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.main           # 24-hour scan (default)
  python -m src.main --1h       # 1-hour scan
  python -m src.main --incremental  # Incremental scan since last run
        """
    )

    # Mutually exclusive group for scan types
    scan_group = parser.add_mutually_exclusive_group()
    scan_group.add_argument(
        '--1h',
        action='store_const',
        const='1h',
        dest='scan_type',
        help='Run 1-hour scan'
    )
    scan_group.add_argument(
        '--incremental',
        action='store_const',
        const='incremental',
        dest='scan_type',
        help='Run incremental scan since last run'
    )

    args = parser.parse_args()
    scan_type = args.scan_type or "24h"  # Default to 24h

    return scan_type


def main():
    """Main entry point."""
    # Setup logging
    logger = setup_logging()

    try:
        # Parse command-line arguments
        scan_type = parse_arguments()

        # Initialize state manager (needed for incremental scans and state updates)
        state_manager = StateManager()

        # Create and run recap generator
        generator = RecapGenerator(scan_type=scan_type)
        generator.run(state_manager=state_manager)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
