# Hyperliquid 24-Hour Whale Recap

Automated daily recap system for tracking whale trader activity on Hyperliquid DEX.

## 📊 What It Does

Generates **24-hour trading recaps** for manually curated whale wallets and sends beautiful Telegram messages with:

- 🟢 **Overall P&L** - Total unrealized P&L across all open positions
- 📈 **24H P&L** - Realized P&L from trades in the last 24 hours
- 📝 **Trade Count** - Number of trades executed
- 📊 **Position Count** - Number of open positions
- 💼 **Trade List** - Up to 20 most recent trades with clean emoji formatting

## ✨ Features

- ✅ **One-time execution** - Run once, get recap, exit (perfect for cron jobs)
- ✅ **Per-wallet messages** - Each tracked wallet gets its own Telegram message
- ✅ **Bot filtering** - Automatically excludes wallets with >500 trades/day
- ✅ **Beautiful formatting** - Clean, emoji-rich messages with trade details
- ✅ **24-hour lookback** - Always analyzes exactly the last 24 hours

## 🚀 Quick Start

### 1. Install Dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in:

```bash
cp .env.example .env
nano .env
```

Required values:
```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

### 3. Add Wallet Addresses

Edit `src/config.py` and add the whale wallets you want to track:

```python
WALLET_ADDRESSES = [
    "0x8bff50aad8b4e06c5e148eaeb9d7aef69e26cdc3",
    "0x9263c1bd29aa87a118242f3fbba4517037f8cc7a",
    # Add more wallets here...
]
```

### 4. Run the Recap

```bash
source venv/bin/activate
python -m src.main
```

## 📱 Sample Telegram Output

```
📊 24H Recap: 0x8bff...cdc3
Oct 17, 15:30 UTC

🟢 Overall P&L: +$45,230.50
📈 24H P&L: +$12,450.25
📝 Trades: 156 | Positions: 8

━━━ LATEST 20 TRADES ━━━

🟢 BTC OPEN LONG
   $125,000 @ $95,234.50
   14:32 UTC

✅ ETH CLOSE LONG
   $45,000 @ $3,456.78 | P&L: +$2,340.00
   12:15 UTC

📈 SOL ADD LONG
   $30,000 @ $142.50
   10:25 UTC

... and 17 more trades
```

## ⚙️ Configuration

### Bot Filtering (Recommended)

By default, the system filters out:
- **Bot traders:** Wallets with >500 trades in 24 hours
- **Inactive wallets:** Wallets with 0 trades

Configure in `.env`:
```env
FILTER_BOTS=true                # Enable/disable filtering
MAX_TRADES_PER_DAY=500         # Bot threshold
MIN_TRADES_PER_DAY=1           # Activity threshold
```

### Other Settings

```env
HYPERLIQUID_API_URL=https://api.hyperliquid.xyz
API_TIMEOUT=10
MAX_RETRIES=3
RETRY_DELAY=5
LOG_LEVEL=INFO
```

## 🤖 Automation with Cron

Run daily recaps automatically:

```bash
# Edit crontab
crontab -e

# Add this line (runs every day at 8 AM)
0 8 * * * cd /path/to/hypescanner && source venv/bin/activate && python -m src.main >> logs/cron.log 2>&1
```

Or run every 12 hours:
```bash
0 8,20 * * * cd /path/to/hypescanner && source venv/bin/activate && python -m src.main
```

## 📂 Project Structure

```
hypescanner/
├── src/
│   ├── config.py              # Configuration & wallet addresses
│   ├── hyperliquid_api.py     # API client for Hyperliquid
│   ├── wallet_recap.py        # Recap builder & calculator
│   ├── recap_notifier.py      # Telegram message formatter
│   └── main.py                # Main execution script
├── .env                       # Environment variables (create from .env.example)
├── requirements.txt           # Python dependencies
├── run.sh                     # Quick run script
└── README.md                  # This file
```

## 🔧 Troubleshooting

### No trades found
- Check that wallet addresses are valid Ethereum addresses (42 characters starting with 0x)
- Verify wallets have recent trading activity on Hyperliquid

### Telegram errors
- Verify `TELEGRAM_BOT_TOKEN` is correct
- Verify `TELEGRAM_CHAT_ID` is correct (use `/getUpdates` to find it)
- Check bot has permission to send messages to chat

### All wallets filtered
- Lower `MAX_TRADES_PER_DAY` if you want to include high-frequency traders
- Set `FILTER_BOTS=false` to disable all filtering
- Add more wallet addresses to `src/config.py`

### API rate limiting
- Default settings include retry logic with exponential backoff
- Increase `RETRY_DELAY` in `.env` if needed

## 📊 Understanding the Output

### Trade Action Emojis

- 🟢 **OPEN LONG** - New long position opened
- 🔴 **OPEN SHORT** - New short position opened
- ✅ **CLOSE LONG** - Long position closed
- ❌ **CLOSE SHORT** - Short position closed
- 📈 **ADD LONG** - Increased long position
- 📉 **ADD SHORT** - Increased short position
- 📊 **REDUCE** - Partially closed position

### P&L Colors

- 🟢 Green - Positive P&L
- 🔴 Red - Negative P&L

## 🎯 Finding Whale Wallets to Track

Manually discover whale traders from:

1. **Hyperliquid Leaderboard**: https://app.hyperliquid.xyz/leaderboard
   - Copy wallet addresses of top performers
   - Look for consistent profitability

2. **Community Sources**:
   - Discord whale alert channels
   - Twitter/X whale watchers
   - Trading community recommendations

3. **Criteria to Look For**:
   - Large account sizes (>$1M)
   - Moderate trade frequency (50-400 trades/day)
   - Consistent profitability
   - Good win rates

## 📖 API Reference

The system uses the official Hyperliquid Python SDK:
- **User State API** - Gets current positions and account value
- **User Fills API** - Retrieves trade history for last 24 hours
- **Portfolio API** - Fetches performance metrics

## 🛡️ Security

- Never commit `.env` file (already in `.gitignore`)
- Keep your Telegram bot token private
- Wallet addresses are public on-chain data

## 📝 License

MIT License - Feel free to use and modify

## 🤝 Contributing

This is a personal project, but feel free to fork and customize for your needs.

## 💡 Tips

- Start with 5-10 quality whale wallets
- Run daily to monitor performance trends
- Remove underperforming wallets periodically
- Add new whales as you discover them

---

**Made for tracking Hyperliquid whale traders** 🐋
