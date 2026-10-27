#!/usr/bin/env python3
"""
Smart Battery AI - Windows Background Telemetry Collector
=========================================================
Runs independently from the React dashboard in the background to automatically:
- Poll physical laptop battery state (psutil) every 2-5 minutes without excessive DB writes.
- Measure aggregate user active vs. idle duration via Win32 GetLastInputInfo (privacy-conscious: no keystrokes, no screen content).
- Detect transitions:
    unplugged -> plugged  => start REAL charging session (data_source=REAL_WINDOWS)
    plugged -> unplugged  => complete REAL charging session
- Detect sleep/wake periods and long inactivity.
- Persist real sessions to local SQLite database to enable gradual ML personalization.

Usage:
  python scripts/run_windows_collector.py
  python scripts/run_windows_collector.py --poll-interval 180 --user-id 1
  python scripts/run_windows_collector.py --once
"""

import os
import sys
import time
import argparse
import logging
import signal
from datetime import datetime, timezone

# Ensure backend package is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.core.config import settings
from app.db.init_db import init_db
from app.db.session import engine, SessionLocal
from app.services.telemetry_service import WindowsTelemetryService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("windows_collector")

running = True


def handle_sigint(signum, frame):
    global running
    logger.info("Shutdown signal received (Ctrl+C). Terminating Windows telemetry collector...")
    running = False


def main():
    parser = argparse.ArgumentParser(
        description="Smart Battery AI - Windows Background Telemetry Collector",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=120,
        help="Polling interval in seconds (default 120s = 2 minutes, sensible range 60-300s)",
    )
    parser.add_argument(
        "--user-id",
        type=int,
        default=1,
        help="User ID to associate real charging sessions and telemetry with",
    )
    parser.add_argument(
        "--idle-threshold",
        type=float,
        default=60.0,
        help="Seconds of input inactivity before user is classified as idle",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single polling cycle and exit immediately (useful for testing/cron)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug-level logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)

    # Initialize database tables and schema migrations
    init_db(engine)

    # Initialize telemetry service instance
    collector = WindowsTelemetryService(
        target_user_id=args.user_id,
        poll_interval_seconds=args.poll_interval,
        idle_threshold_seconds=args.idle_threshold,
    )
    collector.collector_running = True

    signal.signal(signal.SIGINT, handle_sigint)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_sigint)

    print("=" * 70)
    print("SMART BATTERY AI - WINDOWS TELEMETRY COLLECTOR")
    print("=" * 70)
    print(f" Target User ID:     {args.user_id}")
    print(f" Polling Interval:   {args.poll_interval}s ({args.poll_interval / 60:.1f} minutes)")
    print(f" Idle Threshold:     {args.idle_threshold}s")
    print(f" Database URL:       {settings.resolved_database_url}")
    print(f" Privacy Mode:       ACTIVE (aggregate idle/active ticks only, 0 keystrokes)")
    print("=" * 70)

    if args.once:
        logger.info("Executing single polling cycle (--once)...")
        result = collector.poll_once()
        logger.info("Poll result: %s", result)
        status_info = collector.get_status()
        print("\nCurrent Telemetry Status:")
        for k, v in status_info.items():
            print(f"  {k}: {v}")
        return

    logger.info("Background collector started. Press Ctrl+C to stop.")

    cycle_count = 0
    try:
        while running:
            cycle_count += 1
            res = collector.poll_once()

            if res.get("success"):
                trans = res.get("transition_event")
                sess_id = res.get("active_session_id")
                active_str = "ACTIVE" if res.get("is_user_active") else "IDLE"
                plug_str = "PLUGGED" if res.get("is_plugged_in") else "ON BATTERY"

                log_msg = (
                    f"[Cycle {cycle_count}] SoC: {res.get('battery_percent'):.1f}% | "
                    f"State: {plug_str} | User: {active_str} "
                    f"(idle={res.get('idle_duration_seconds'):.0f}s)"
                )
                if sess_id:
                    log_msg += f" | Session #{sess_id}"
                if trans:
                    log_msg += f" | EVENT: {trans}"
                if res.get("sleep_gap_seconds", 0) > 0:
                    log_msg += f" | SLEEP GAP: {res.get('sleep_gap_seconds'):.0f}s"

                logger.info(log_msg)
            else:
                logger.warning("[Cycle %d] Poll failed: %s", cycle_count, res.get("error"))

            # Sleep in 1-second chunks for responsive Ctrl+C handling
            sleep_start = time.time()
            while running and (time.time() - sleep_start < args.poll_interval):
                time.sleep(1.0)

    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
    finally:
        collector.collector_running = False
        logger.info("Windows telemetry collector terminated safely.")


if __name__ == "__main__":
    main()
