#!/bin/bash
# Start script for Hyperliquid Whale Position Tracker

# Change to script directory
cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the tracker
python -m src.main
