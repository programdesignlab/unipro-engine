"""NSE trading calendar helpers."""

from datetime import date, timedelta


# NSE public holidays (approximate — update annually)
NSE_HOLIDAYS_2024 = {
    date(2024, 1, 22),  # Ram Mandir Pran Pratishtha (special)
    date(2024, 1, 26),  # Republic Day
    date(2024, 3, 8),   # Mahashivratri
    date(2024, 3, 25),  # Holi
    date(2024, 3, 29),  # Good Friday
    date(2024, 4, 11),  # Id-Ul-Fitr (Ramadan)
    date(2024, 4, 14),  # Dr. Ambedkar Jayanti
    date(2024, 4, 17),  # Ram Navami
    date(2024, 4, 21),  # Mahavir Jayanti
    date(2024, 5, 1),   # Maharashtra Day
    date(2024, 5, 23),  # Buddha Purnima
    date(2024, 6, 17),  # Eid-Ul-Adha (Bakri Id)
    date(2024, 7, 17),  # Muharram
    date(2024, 8, 15),  # Independence Day
    date(2024, 9, 16),  # Milad-Un-Nabi
    date(2024, 10, 2),  # Mahatma Gandhi Jayanti
    date(2024, 11, 1),  # Diwali Laxmi Pujan
    date(2024, 11, 15), # Gurunanak Jayanti
    date(2024, 12, 25), # Christmas
}

NSE_HOLIDAYS_2025 = {
    date(2025, 1, 26),  # Republic Day
    date(2025, 3, 14),  # Holi
    date(2025, 4, 14),  # Dr. Ambedkar Jayanti / Ram Navami
    date(2025, 4, 18),  # Good Friday
    date(2025, 5, 1),   # Maharashtra Day
    date(2025, 8, 15),  # Independence Day
    date(2025, 10, 2),  # Gandhi Jayanti
    date(2025, 10, 24), # Dussehra
    date(2025, 11, 5),  # Diwali Laxmi Pujan
    date(2025, 11, 6),  # Diwali Balipratipada
    date(2025, 12, 25), # Christmas
}

NSE_HOLIDAYS_2026 = {
    date(2026, 1, 26),  # Republic Day
    date(2026, 3, 4),   # Mahashivratri
    date(2026, 3, 25),  # Holi
    date(2026, 4, 3),   # Good Friday
    date(2026, 4, 14),  # Dr. Ambedkar Jayanti
    date(2026, 5, 1),   # Maharashtra Day
    date(2026, 8, 15),  # Independence Day
    date(2026, 10, 2),  # Gandhi Jayanti
    date(2026, 11, 14), # Diwali
    date(2026, 12, 25), # Christmas
}

NSE_HOLIDAYS = NSE_HOLIDAYS_2024 | NSE_HOLIDAYS_2025 | NSE_HOLIDAYS_2026


def is_trading_day(d: date) -> bool:
    """Return True if the given date is an NSE trading day."""
    return d.weekday() < 5 and d not in NSE_HOLIDAYS


def prev_trading_day(d: date | None = None) -> date:
    """Return the most recent trading day on or before d (default: today)."""
    d = d or date.today()
    while not is_trading_day(d):
        d -= timedelta(days=1)
    return d


def trading_days_between(start: date, end: date) -> list[date]:
    """Return list of trading days in [start, end] inclusive."""
    days = []
    current = start
    while current <= end:
        if is_trading_day(current):
            days.append(current)
        current += timedelta(days=1)
    return days
