"""
State management for tracking last scan run timestamps and scan types.
Persists state to JSON file for incremental scans.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional, Dict
from src import config

logger = logging.getLogger(__name__)


class StateManager:
    """Manages scan state persistence for incremental scans."""

    def __init__(self, state_file_path: Optional[str] = None):
        """
        Initialize state manager.

        Args:
            state_file_path: Path to state JSON file. Defaults to config.STATE_FILE_PATH
        """
        self.state_file_path = state_file_path or config.STATE_FILE_PATH
        self._state = None
        self._load_state()

    def _load_state(self) -> None:
        """Load state from JSON file, creating if it doesn't exist."""
        state_dir = os.path.dirname(self.state_file_path)
        if state_dir and not os.path.exists(state_dir):
            os.makedirs(state_dir, exist_ok=True)
            logger.debug(f"Created state directory: {state_dir}")

        if os.path.exists(self.state_file_path):
            try:
                with open(self.state_file_path, 'r') as f:
                    self._state = json.load(f)
                logger.debug(f"Loaded state from {self.state_file_path}")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load state file: {e}. Starting fresh.")
                self._state = {}
        else:
            self._state = {}
            logger.debug(f"State file not found, starting fresh: {self.state_file_path}")

    def _save_state(self) -> bool:
        """Save current state to JSON file."""
        try:
            state_dir = os.path.dirname(self.state_file_path)
            if state_dir and not os.path.exists(state_dir):
                os.makedirs(state_dir, exist_ok=True)

            with open(self.state_file_path, 'w') as f:
                json.dump(self._state, f, indent=2)
            logger.debug(f"Saved state to {self.state_file_path}")
            return True
        except IOError as e:
            logger.error(f"Failed to save state file: {e}")
            return False

    def get_last_run_timestamp(self) -> Optional[int]:
        """
        Get last run timestamp in milliseconds.

        Returns:
            Unix timestamp in milliseconds, or None if no previous run
        """
        timestamp = self._state.get("last_run_timestamp")
        if timestamp:
            logger.debug(f"Last run timestamp: {timestamp}")
        else:
            logger.debug("No previous run timestamp found")
        return timestamp

    def get_last_scan_type(self) -> Optional[str]:
        """
        Get last scan type.

        Returns:
            "24h", "1h", "incremental", or None if no previous run
        """
        scan_type = self._state.get("last_scan_type")
        if scan_type:
            logger.debug(f"Last scan type: {scan_type}")
        else:
            logger.debug("No previous scan type found")
        return scan_type

    def update_state(self, scan_type: str, timestamp_ms: Optional[int] = None) -> bool:
        """
        Update state with new scan information.

        Args:
            scan_type: Type of scan ("24h", "1h", or "incremental")
            timestamp_ms: Timestamp in milliseconds. If None, uses current time.

        Returns:
            True if update successful
        """
        if timestamp_ms is None:
            timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        self._state["last_run_timestamp"] = timestamp_ms
        self._state["last_scan_type"] = scan_type

        logger.info(f"Updating state: scan_type={scan_type}, timestamp={timestamp_ms}")

        return self._save_state()

    def get_state(self) -> Dict:
        """Get full state dictionary."""
        return self._state.copy()

