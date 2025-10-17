"""
Generates 24-hour trading recaps for tracked wallets and sends to Telegram.
Runs once then exits.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone

from src import config
from src.hyperliquid_api import HyperliquidAPI, HyperliquidAPIError
from src.wallet_recap import WalletRecap
from src.recap_notifier import RecapNotifier


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
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api = HyperliquidAPI()
        self.notifier = RecapNotifier()

    def generate_wallet_recap(self, wallet_address: str) -> dict:
        """Build 24h recap for one wallet."""
        try:
            self.logger.info(f"Generating recap for {wallet_address[:8]}...")

            positions = self.api.get_positions(wallet_address)

            # Fetch 24h trade history
            fills = self.api.get_user_fills_24h(wallet_address)

            # Build recap with API client for asset name resolution
            recap = WalletRecap(wallet_address, positions, fills, api_client=self.api)
            summary = recap.build_summary()

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

    def run(self) -> None:
        """Generate and send recaps for all wallets."""
        self.logger.info("=" * 80)
        self.logger.info("Hyperliquid 24-Hour Recap Generator")
        self.logger.info("=" * 80)

        # Display configuration
        self.logger.info(config.display_config())

        # Validate configuration
        try:
            config.validate_config()
        except ValueError as e:
            self.logger.error(f"Configuration error: {e}")
            sys.exit(1)

        # Send startup notification
        self.notifier.send_startup_message()

        # Process each wallet
        total_trades = 0
        successful_wallets = 0
        failed_wallets = 0
        filtered_wallets = 0
        bot_traders = []  # Collect bot trader summaries

        self.logger.info("")
        self.logger.info(f"Processing {len(config.WALLET_ADDRESSES)} wallets...")
        self.logger.info("")

        for wallet in config.WALLET_ADDRESSES:
            try:
                # Generate recap
                summary = self.generate_wallet_recap(wallet)

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


def main():
    """Main entry point."""
    # Setup logging
    logger = setup_logging()

    try:
        # Create and run recap generator
        generator = RecapGenerator()
        generator.run()

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
