"""Parse and display weekly opening hours from the Yelp dataset."""

from __future__ import annotations

import json
from datetime import time
from typing import Any


WEEKDAYS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


def _load_hours(hours_json: str | None) -> dict[str, str]:
    """Return a normalized Yelp hours mapping, or an empty mapping if invalid."""
    if not hours_json:
        return {}
    try:
        value = json.loads(hours_json)
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(value, dict):
        return {}
    return {
        str(day): str(intervals)
        for day, intervals in value.items()
        if intervals is not None
    }


def _minutes(value: str) -> int:
    hour, minute = value.strip().split(":", maxsplit=1)
    return int(hour) * 60 + int(minute)


def _intervals(value: str | None) -> list[tuple[int, int]]:
    if not value:
        return []
    parsed: list[tuple[int, int]] = []
    for interval in value.split(","):
        try:
            start, end = interval.strip().split("-", maxsplit=1)
            parsed.append((_minutes(start), _minutes(end)))
        except (ValueError, TypeError):
            continue
    return parsed


def _display_time(total_minutes: int) -> str:
    hour, minute = divmod(total_minutes, 60)
    suffix = "AM" if hour < 12 else "PM"
    display_hour = hour % 12 or 12
    return f"{display_hour}:{minute:02d} {suffix}"


def format_day_hours(hours_json: str | None, weekday: str) -> str:
    """Format one day's hours for display."""
    intervals = _intervals(_load_hours(hours_json).get(weekday))
    if not intervals:
        return "Closed / unavailable"
    formatted = []
    for start, end in intervals:
        if start == end:
            formatted.append("Open 24 hours")
        else:
            formatted.append(f"{_display_time(start)}–{_display_time(end)}")
    return ", ".join(formatted)


def format_weekly_hours(hours_json: str | None) -> str:
    """Format every available day as a compact weekly schedule."""
    hours = _load_hours(hours_json)
    if not hours:
        return "Hours unavailable"
    parts = []
    for weekday in WEEKDAYS:
        if weekday in hours:
            parts.append(f"{weekday[:3]} {format_day_hours(hours_json, weekday)}")
    return "; ".join(parts) or "Hours unavailable"


def is_open_at(hours_json: str | None, weekday: str, visit_time: time) -> bool:
    """Return whether the schedule confirms the business is open then.

    Overnight ranges are checked on both the selected weekday and the previous
    weekday, so Monday 6 PM–2 AM correctly includes Tuesday at 1 AM.
    """
    if weekday not in WEEKDAYS:
        raise ValueError(f"Unknown weekday: {weekday}")

    hours = _load_hours(hours_json)
    target = visit_time.hour * 60 + visit_time.minute

    for start, end in _intervals(hours.get(weekday)):
        if start == end or (start < end and start <= target < end):
            return True
        if start > end and target >= start:
            return True

    previous_day = WEEKDAYS[(WEEKDAYS.index(weekday) - 1) % len(WEEKDAYS)]
    for start, end in _intervals(hours.get(previous_day)):
        if start > end and target < end:
            return True
    return False
