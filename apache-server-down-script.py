#!/usr/bin/env python3
import subprocess
import time
import signal
import sys
from datetime import datetime, timezone, timedelta

# Healthy window: Apache should be **up** from 03:00 (inclusive) to 04:00 (exclusive) UTC.
WINDOW_START_HOUR = 3
WINDOW_END_HOUR = 4

CHECK_INTERVAL = 30  # seconds; wake-up interval when waiting for the next transition

def run_systemctl(action: str) -> None:
    """Start/stop apache2 via systemctl, but swallow benign failures."""
    cmd = ["systemctl", action, "apache2"]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"{datetime.now(timezone.utc).isoformat()} [+] apache2 {action}")
    except subprocess.CalledProcessError as e:
        # If trying to start and it's already active or stop when already inactive, ignore
        print(f"{datetime.now(timezone.utc).isoformat()} [!] systemctl {action} apache2 failed: {e}")

def apache_should_be_up(now: datetime) -> bool:
    h = now.hour
    return WINDOW_START_HOUR <= h < WINDOW_END_HOUR

def is_apache_active() -> bool:
    try:
        out = subprocess.check_output(["systemctl", "is-active", "apache2"], text=True).strip()
        return out == "active"
    except subprocess.CalledProcessError:
        return False

def main():
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    print("=== Apache UTC window controller started (Ctrl-C to stop) ===")
    while True:
        now = datetime.now(timezone.utc)
        should_up = apache_should_be_up(now)
        currently_up = is_apache_active()

        if should_up:
            if not currently_up:
                run_systemctl("start")
            # Sleep until window end (04:00 UTC)
            next_transition = now.replace(hour=WINDOW_END_HOUR, minute=0, second=0, microsecond=0)
            if next_transition <= now:
                # edge case, fallback
                time.sleep(CHECK_INTERVAL)
                continue
            delta = (next_transition - now).total_seconds()
            print(f"{datetime.now(timezone.utc).isoformat()} [+] In uptime window; sleeping {int(delta)}s until {WINDOW_END_HOUR}:00 UTC")
            time.sleep(delta + 1)
        else:
            if currently_up:
                run_systemctl("stop")
            # Compute next window start (03:00 UTC)
            next_start = now.replace(hour=WINDOW_START_HOUR, minute=0, second=0, microsecond=0)
            if next_start <= now:
                next_start += timedelta(days=1)
            delta = (next_start - now).total_seconds()
            sleep_duration = min(delta, CHECK_INTERVAL)
            print(f"{datetime.now(timezone.utc).isoformat()} [-] Outside window; sleeping {int(sleep_duration)}s before re-evaluating")
            time.sleep(sleep_duration)

if __name__ == "__main__":
    main()
