"""
utils.helpers
=============
Pure, stateless utility functions used across the application.

No Flask context, no database queries — safe to call from anywhere,
including tests, CLI scripts, and background jobs.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Union


# ─── Number → Words ───────────────────────────────────────────────────────────

def number_to_words(num: Union[int, float]) -> str:
    """Convert a numeric value to Indian English words (up to crores).

    Examples:
        >>> number_to_words(1050)
        'One Thousand and Fifty'
        >>> number_to_words(100000)
        'One Lakh'
        >>> number_to_words(10000000)
        'One Crore'

    Args:
        num: Integer or float value (truncated to int internally).

    Returns:
        The number spelled out in Indian English, or ``"Zero"`` for 0.
    """
    try:
        num = int(num)
    except (ValueError, TypeError):
        return "Zero"

    if num == 0:
        return "Zero"
    if num < 0:
        return "Negative " + number_to_words(abs(num))

    _UNITS = [
        "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight",
        "Nine", "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen",
        "Sixteen", "Seventeen", "Eighteen", "Nineteen",
    ]
    _TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty",
             "Sixty", "Seventy", "Eighty", "Ninety"]

    def _chunk(n: int) -> str:
        if n < 20:
            return _UNITS[n]
        if n < 100:
            return _TENS[n // 10] + (" " + _UNITS[n % 10] if n % 10 else "")
        return (
            _UNITS[n // 100]
            + " Hundred"
            + (" and " + _chunk(n % 100) if n % 100 else "")
        )

    parts: list[str] = []
    if num >= 10_000_000:
        parts.append(_chunk(num // 10_000_000) + " Crore")
        num %= 10_000_000
    if num >= 100_000:
        parts.append(_chunk(num // 100_000) + " Lakh")
        num %= 100_000
    if num >= 1_000:
        parts.append(_chunk(num // 1_000) + " Thousand")
        num %= 1_000
    if num > 0:
        parts.append(_chunk(num))
    return " ".join(parts)


# ─── Financial Year ────────────────────────────────────────────────────────────

def get_financial_year(d: date) -> str:
    """Return the Indian financial-year string for a given date.

    The Indian FY runs April 1 → March 31.

    Examples:
        >>> get_financial_year(date(2025, 4, 1))
        '25-26'
        >>> get_financial_year(date(2025, 3, 31))
        '24-25'

    Args:
        d: Any :class:`datetime.date` or :class:`datetime.datetime`.

    Returns:
        Two-digit year string like ``'24-25'``.
    """
    y = d.year
    if d.month >= 4:
        return f"{str(y)[-2:]}-{str(y + 1)[-2:]}"
    return f"{str(y - 1)[-2:]}-{str(y)[-2:]}"


# ─── Date Parsing ──────────────────────────────────────────────────────────────

_DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%d.%m.%Y")


def parse_date(val) -> date:
    """Parse a date value from various types / string formats.

    Handles:
    - :class:`datetime.datetime` → extracts ``.date()``
    - :class:`datetime.date`     → returned as-is
    - ``str``                    → tried against multiple common formats

    Falls back to ``date.today()`` if nothing matches.

    Args:
        val: Raw value from Excel cell, form input, or API payload.

    Returns:
        A :class:`datetime.date` instance.
    """
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(val.strip(), fmt).date()
            except ValueError:
                continue
    return date.today()


# ─── Safe Type Coercions ───────────────────────────────────────────────────────

def safe_int(val, default: int = 1) -> int:
    """Convert *val* to ``int``, returning *default* on any failure.

    Args:
        val:     Any value (string, float, None, etc.)
        default: Fallback integer (default ``1``).
    """
    try:
        return int(float(str(val)))
    except (ValueError, TypeError):
        return default


def safe_float(val, default: float = 0.0) -> float:
    """Convert *val* to ``float``, returning *default* on any failure.

    Args:
        val:     Any value (string, int, None, etc.)
        default: Fallback float (default ``0.0``).
    """
    try:
        return float(str(val))
    except (ValueError, TypeError):
        return default
