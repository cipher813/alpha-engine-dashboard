"""
trading_calendar.py — NYSE trading day check with holiday awareness.

Lightweight implementation that doesn't require exchange_calendars or
pandas_market_calendars. Maintains a static list of NYSE holidays through 2030.

Usage:
    python trading_calendar.py              # check today
    python trading_calendar.py 2026-04-03   # check specific date

Exit codes:
    Always exits 0 — Step Function checks stdout markers, not exit code.

Stdout markers:
    "TRADING DAY"  = NYSE is open (proceed with pipeline)
    "MARKET_CLOSED" = weekend or holiday (skip pipeline)
"""

from __future__ import annotations

import sys
from datetime import date, timedelta

# NYSE observed holidays through 2030.
# Source: https://www.nyse.com/markets/hours-calendars
# Updated annually — add new years as they're published.
NYSE_HOLIDAYS: set[date] = {
    # 2025
    date(2025, 1, 1),    # New Year's Day
    date(2025, 1, 20),   # MLK Day
    date(2025, 2, 17),   # Presidents' Day
    date(2025, 4, 18),   # Good Friday
    date(2025, 5, 26),   # Memorial Day
    date(2025, 6, 19),   # Juneteenth
    date(2025, 7, 4),    # Independence Day
    date(2025, 9, 1),    # Labor Day
    date(2025, 11, 27),  # Thanksgiving
    date(2025, 12, 25),  # Christmas
    # 2026
    date(2026, 1, 1),    # New Year's Day
    date(2026, 1, 19),   # MLK Day
    date(2026, 2, 16),   # Presidents' Day
    date(2026, 4, 3),    # Good Friday
    date(2026, 5, 25),   # Memorial Day
    date(2026, 6, 19),   # Juneteenth
    date(2026, 7, 3),    # Independence Day (observed, July 4 is Saturday)
    date(2026, 9, 7),    # Labor Day
    date(2026, 11, 26),  # Thanksgiving
    date(2026, 12, 25),  # Christmas
    # 2027
    date(2027, 1, 1),    # New Year's Day
    date(2027, 1, 18),   # MLK Day
    date(2027, 2, 15),   # Presidents' Day
    date(2027, 3, 26),   # Good Friday
    date(2027, 5, 31),   # Memorial Day
    date(2027, 6, 18),   # Juneteenth (observed, June 19 is Saturday)
    date(2027, 7, 5),    # Independence Day (observed, July 4 is Sunday)
    date(2027, 9, 6),    # Labor Day
    date(2027, 11, 25),  # Thanksgiving
    date(2027, 12, 24),  # Christmas (observed, Dec 25 is Saturday)
    # 2028
    date(2028, 1, 17),   # MLK Day
    date(2028, 2, 21),   # Presidents' Day
    date(2028, 4, 14),   # Good Friday
    date(2028, 5, 29),   # Memorial Day
    date(2028, 6, 19),   # Juneteenth
    date(2028, 7, 4),    # Independence Day
    date(2028, 9, 4),    # Labor Day
    date(2028, 11, 23),  # Thanksgiving
    date(2028, 12, 25),  # Christmas
    # 2029
    date(2029, 1, 1),    # New Year's Day
    date(2029, 1, 15),   # MLK Day
    date(2029, 2, 19),   # Presidents' Day
    date(2029, 3, 30),   # Good Friday
    date(2029, 5, 28),   # Memorial Day
    date(2029, 6, 19),   # Juneteenth
    date(2029, 7, 4),    # Independence Day
    date(2029, 9, 3),    # Labor Day
    date(2029, 11, 22),  # Thanksgiving
    date(2029, 12, 25),  # Christmas
    # 2030
    date(2030, 1, 1),    # New Year's Day
    date(2030, 1, 21),   # MLK Day
    date(2030, 2, 18),   # Presidents' Day
    date(2030, 4, 19),   # Good Friday
    date(2030, 5, 27),   # Memorial Day
    date(2030, 6, 19),   # Juneteenth
    date(2030, 7, 4),    # Independence Day
    date(2030, 9, 2),    # Labor Day
    date(2030, 11, 28),  # Thanksgiving
    date(2030, 12, 25),  # Christmas
}


def is_trading_day(d: date | None = None) -> bool:
    """Return True if the given date is an NYSE trading day."""
    if d is None:
        d = date.today()
    if d.weekday() > 4:  # Saturday=5, Sunday=6
        return False
    if d in NYSE_HOLIDAYS:
        return False
    return True


def next_trading_day(d: date | None = None) -> date:
    """Return the next NYSE trading day after the given date."""
    if d is None:
        d = date.today()
    d = d + timedelta(days=1)
    while not is_trading_day(d):
        d = d + timedelta(days=1)
    return d


if __name__ == "__main__":
    check_date = date.today()
    if len(sys.argv) > 1:
        check_date = date.fromisoformat(sys.argv[1])

    trading = is_trading_day(check_date)
    day_name = check_date.strftime("%A")

    if trading:
        print(f"{check_date} ({day_name}): TRADING DAY")
        sys.exit(0)
    else:
        reason = "weekend" if check_date.weekday() > 4 else "NYSE holiday"
        nxt = next_trading_day(check_date)
        print(f"{check_date} ({day_name}): MARKET_CLOSED ({reason}) — next trading day: {nxt}")
        # Exit 0 so SSM reports Success — Step Function checks stdout marker
        # instead of exit code to distinguish holidays from script crashes.
        sys.exit(0)
