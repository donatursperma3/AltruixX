# verification_recurring.py
import time
from datetime import datetime, timedelta

def calculate_wait_seconds(mode, h=0, m=0, sh=0, now=None):
    if now is None:
        now = datetime.now()
        
    if mode == "interval":
        wait_seconds = (h * 3600) + (m * 60)
        if wait_seconds < 10: wait_seconds = 10
        return wait_seconds, now + timedelta(seconds=wait_seconds)
    else: # mode == "time"
        target_time = now.replace(hour=sh, minute=0, second=0, microsecond=0)
        if target_time <= now:
            target_time += timedelta(days=1)
        wait_seconds = int((target_time - now).total_seconds())
        return wait_seconds, target_time

# Test Cases
now = datetime(2026, 3, 12, 21, 0, 0) # 9 PM

print(f"Current time: {now}")

# 1. Interval 2h 30m
w, next_run = calculate_wait_seconds("interval", h=2, m=30, now=now)
print(f"Interval 2h30m: wait={w}s, next={next_run}")
assert w == 2.5 * 3600

# 2. Specific time 10 PM (same day)
w, next_run = calculate_wait_seconds("time", sh=22, now=now)
print(f"Specific time 22:00 (Today): wait={w}s, next={next_run}")
assert w == 3600

# 3. Specific time 8 AM (tomorrow)
w, next_run = calculate_wait_seconds("time", sh=8, now=now)
print(f"Specific time 08:00 (Tomorrow): wait={w}s, next={next_run}")
assert w == 11 * 3600

print("\nLogic verification SUCCESS.")
