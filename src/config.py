"""Config loader for tracker settings and wallet addresses."""

import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# API
HYPERLIQUID_API_URL = os.getenv("HYPERLIQUID_API_URL", "https://api.hyperliquid.xyz")

# Wallets - can also set via .env as comma-separated list
WALLET_ADDRESSES_ENV = os.getenv("WALLET_ADDRESSES", "")
if WALLET_ADDRESSES_ENV:
    WALLET_ADDRESSES = [addr.strip() for addr in WALLET_ADDRESSES_ENV.split(",") if addr.strip()]
else:
    WALLET_ADDRESSES = [
        "0xa461db6d21568e97e040c4ab57ff38708a4f0f67",
        "0x06cecfbac34101ae41c88ebc2450f8602b3d164b",
        "0xf28e1b06e00e8774c612e31ab3ac35d5a720085f",
        "0x3fc56e944aa7b1594c85861b2d46a07f82a2c0c1",
        "0x71dfc07de32c2ebf1c4801f4b1c9e40b76d4a23d",
        "0x99b1098d9d50aa076f78bd26ab22e6abd3710729",
        "0x6859da14835424957a1e6b397d8026b1d9ff7e1e",
    ]

# Filters
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", "60"))
POSITION_THRESHOLD = float(os.getenv("POSITION_THRESHOLD", "50000"))
SIZE_CHANGE_THRESHOLD = float(os.getenv("SIZE_CHANGE_THRESHOLD", "50000"))
MAX_TRADES_PER_DAY = int(os.getenv("MAX_TRADES_PER_DAY", "500"))
MIN_TRADES_PER_DAY = int(os.getenv("MIN_TRADES_PER_DAY", "1"))
FILTER_BOTS = os.getenv("FILTER_BOTS", "true").lower() == "true"

# API settings
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "10"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY = int(os.getenv("RETRY_DELAY", "5"))

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "logs/tracker.log")
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", "52428800"))
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))
SELF_MONITORING_INTERVAL = int(os.getenv("SELF_MONITORING_INTERVAL", "300"))

# State management
STATE_FILE_PATH = os.getenv("STATE_FILE_PATH", "state/last_scan.json")


def validate_config():
    """Check required settings are present."""
    errors = []
    if not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN is not set")
    if not TELEGRAM_CHAT_ID:
        errors.append("TELEGRAM_CHAT_ID is not set")
    if not WALLET_ADDRESSES:
        errors.append("No wallet addresses configured")

    if errors:
        raise ValueError(f"Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))
    return True


def display_config():
    """Print current config with masked secrets."""
    return f"""
Configuration:
--------------
Telegram Bot Token: {'*' * 20}{TELEGRAM_BOT_TOKEN[-4:] if TELEGRAM_BOT_TOKEN else 'NOT SET'}
Telegram Chat ID: {TELEGRAM_CHAT_ID}
Hyperliquid API URL: {HYPERLIQUID_API_URL}
Wallet Addresses: {len(WALLET_ADDRESSES)} addresses configured
Scan Interval: {SCAN_INTERVAL}s
Position Threshold: ${POSITION_THRESHOLD:,.2f}
Size Change Threshold: ${SIZE_CHANGE_THRESHOLD:,.2f}
Bot Filtering: {'Enabled' if FILTER_BOTS else 'Disabled'}
Max Trades/Day: {MAX_TRADES_PER_DAY} (bot threshold)
Min Trades/Day: {MIN_TRADES_PER_DAY} (activity threshold)
API Timeout: {API_TIMEOUT}s
Max Retries: {MAX_RETRIES}
Retry Delay: {RETRY_DELAY}s
Log Level: {LOG_LEVEL}
"""
