"""Time parsing and sleep utilities for ghact."""

import re
import sys
import time
from datetime import datetime, timedelta


def parse_at(time_str):
    """Parse --at value into a target datetime (today, or tomorrow if already past).

    Accepted formats:
      0300        24-hour HHMM, no colon
      14:30       24-hour HH:MM
      2:30am      12-hour with am/pm
      3pm         12-hour whole hour
    """
    s = time_str.strip().lower()

    # HHMM (e.g. 0300, 1430)
    m = re.fullmatch(r'(\d{1,2})(\d{2})', s)
    if m:
        return _future(int(m.group(1)), int(m.group(2)))

    # HH:MM (e.g. 14:30, 2:30)
    m = re.fullmatch(r'(\d{1,2}):(\d{2})', s)
    if m:
        return _future(int(m.group(1)), int(m.group(2)))

    # H:MMam/pm  or  HH:MMam/pm  (e.g. 2:30am, 11:30pm)
    m = re.fullmatch(r'(\d{1,2}):(\d{2})(am|pm)', s)
    if m:
        return _future(_to24(int(m.group(1)), m.group(3)), int(m.group(2)))

    # Ham/pm  or  HHam/pm  (e.g. 3am, 11pm)
    m = re.fullmatch(r'(\d{1,2})(am|pm)', s)
    if m:
        return _future(_to24(int(m.group(1)), m.group(2)), 0)

    raise ValueError(
        f"Cannot parse time {time_str!r}. "
        "Expected formats: 0300, 14:30, 2:30am, 3pm"
    )


def parse_after(duration_str):
    """Parse --after value into a timedelta.

    Accepted formats: 2h, 90m, 30s, 1h30m, 1h30m20s
    """
    s = duration_str.strip().lower()
    m = re.fullmatch(r'(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?', s)
    if not m or not any(m.groups()):
        raise ValueError(
            f"Cannot parse duration {duration_str!r}. "
            "Expected formats: 2h, 90m, 1h30m"
        )
    hours   = int(m.group(1) or 0)
    minutes = int(m.group(2) or 0)
    seconds = int(m.group(3) or 0)
    if hours == minutes == seconds == 0:
        raise ValueError(f"Cannot parse duration {duration_str!r}")
    return timedelta(hours=hours, minutes=minutes, seconds=seconds)


def sleep_until(target, verbose=False):
    """Sleep until target datetime, optionally printing a status message."""
    delta = (target - datetime.now()).total_seconds()
    if delta <= 0:
        return
    if verbose:
        print(
            f"Sleeping until {target.strftime('%Y-%m-%d %H:%M:%S')} "
            f"({delta / 60:.1f} min from now)...",
            file=sys.stderr,
        )
    while True:
        delta = (target - datetime.now()).total_seconds()
        if delta <= 0:
            return
        time.sleep(delta)


# ── helpers ──────────────────────────────────────────────────────────────────

def _to24(hour, ampm):
    """Convert 12-hour clock to 24-hour."""
    if ampm == 'am':
        return 0 if hour == 12 else hour
    else:  # pm
        return hour if hour == 12 else hour + 12


def _future(hour, minute):
    """Return the next datetime with the given hour and minute (today or tomorrow)."""
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target
