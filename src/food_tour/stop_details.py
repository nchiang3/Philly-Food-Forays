"""Per-stop details for the tour: address, hours, why it was picked, and timing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import Any
from urllib.parse import urlencode

from .chains import CHAIN_LOCATIONS_COLUMN
from .distance import DISTANCE_COLUMN
from .hours import WEEKDAYS, _load_hours, format_clock, format_day_hours, open_intervals
from .schedule import earliest_visit


GOOGLE_MAPS_SEARCH = "https://www.google.com/maps/search/"

WARNING = "warning"
INFO = "info"


@dataclass(frozen=True)
class TimingNote:
    """A short note about when a stop is open, shown as a warning or info box."""

    level: str
    text: str


@dataclass(frozen=True)
class PlannedVisit:
    """When the tour reaches a scheduled stop, in minutes after midnight."""

    arrival: int
    closing: int
    wait: int


def _minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def full_address(row: dict[str, Any], restaurant: dict[str, Any] | None = None) -> str:
    """Street address plus city, state, and ZIP when the restaurant row has them."""
    restaurant = restaurant or {}
    street = str(row.get("address") or restaurant.get("address") or "").strip()
    city = str(restaurant.get("city") or "").strip()
    state = str(restaurant.get("state") or "").strip()
    postal = str(restaurant.get("postal_code") or "").strip()
    region = " ".join(part for part in (state, postal) if part)
    locality = ", ".join(part for part in (city, region) if part)
    return ", ".join(part for part in (street, locality) if part)


def google_maps_place_url(row: dict[str, Any], address: str | None = None) -> str:
    """Key-free Google Maps search link that opens the place's card."""
    query = " ".join(
        part for part in (str(row.get("name") or ""), address or "") if part
    )
    if not query:
        query = f"{float(row['latitude']):.6f},{float(row['longitude']):.6f}"
    return f"{GOOGLE_MAPS_SEARCH}?{urlencode({'api': '1', 'query': query})}"


def weekly_hours(hours_json: str | None) -> list[tuple[str, str]]:
    """``(weekday, hours)`` for all seven days, "Closed / unavailable" if none."""
    return [(day, format_day_hours(hours_json, day)) for day in WEEKDAYS]


def planned_visits(
    scheduled: list[dict[str, Any]],
    weekday: str,
    start_time: time,
    end_time: time,
    minutes_per_stop: int,
    hours_key: str = "hours_json",
) -> list[PlannedVisit | None]:
    """Replay the visit plan for stops already in visiting order.

    For each stop this gives the arrival time, when that opening ends, and
    how long the tour waits for it to open after finishing the previous stop
    (or after the window starts, for the first stop). It matches
    :func:`food_tour.schedule.plan_visit_order`, which picks each arrival with
    the same rule. A stop the plan could not reach gets ``None``.
    """
    window_end = _minutes(end_time)
    clock = _minutes(start_time)
    visits: list[PlannedVisit | None] = []
    for stop in scheduled:
        visit = earliest_visit(stop.get(hours_key), weekday, clock, window_end)
        if visit is None:
            visits.append(None)
            continue
        arrival, closing = visit
        visits.append(PlannedVisit(arrival, closing, arrival - clock))
        clock = arrival + minutes_per_stop
    return visits


def _window_label(weekday: str, start_time: time, end_time: time) -> str:
    return (
        f"{weekday} {format_clock(_minutes(start_time))}–"
        f"{format_clock(_minutes(end_time))}"
    )


def _closed_days(hours_json: str | None) -> list[str]:
    hours = _load_hours(hours_json)
    if not hours:
        return []
    return [day for day in WEEKDAYS if not open_intervals(hours_json, day)]


def _hours_phrase(day_hours: str, capital: bool = False) -> str:
    if day_hours == "Open 24 hours":
        phrase = "open 24 hours"
    elif day_hours == "Closed / unavailable":
        phrase = "closed"
    else:
        phrase = f"open {day_hours}"
    return phrase[0].upper() + phrase[1:] if capital else phrase


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + f" and {items[-1]}"


def timing_notes(
    row: dict[str, Any],
    visit: PlannedVisit | None,
    *,
    scheduled: bool,
    position: int,
    weekday: str | None,
    start_time: time | None,
    end_time: time | None,
    minutes_per_stop: int | None,
    restaurant: dict[str, Any] | None = None,
    hours_key: str = "hours_json",
) -> list[TimingNote]:
    """Explain when the stop is open relative to its planned tour time.

    Warnings call out a stop that isn't open during its planned time: one the
    tour can't reach before it closes or the window ends, one that closes
    sooner than the planned stay, and one Yelp marks as permanently closed.
    Info notes explain a stop that is closed when the tour starts and so was
    moved later, and waits for an opening. Without a visit window, the notes
    point out missing hours and days the stop is closed.
    """
    notes: list[TimingNote] = []
    hours_json = row.get(hours_key)
    if restaurant is not None and str(restaurant.get("is_open", "1")) != "1":
        notes.append(
            TimingNote(
                WARNING,
                "Yelp marks this business as closed for good, so it may no "
                "longer be operating. It shows up because \"Show only "
                "businesses marked open\" is off.",
            )
        )

    planned = (
        weekday is not None
        and start_time is not None
        and end_time is not None
        and minutes_per_stop is not None
    )
    if not planned:
        if not _load_hours(hours_json):
            notes.append(
                TimingNote(
                    WARNING,
                    "Yelp has no opening hours for this spot. Check before "
                    "you go.",
                )
            )
        else:
            closed = _closed_days(hours_json)
            if closed:
                notes.append(
                    TimingNote(INFO, f"Closed on {_join(closed)}, per Yelp.")
                )
            notes.append(
                TimingNote(
                    INFO,
                    "No visit day and time is set, so this tour isn't checked "
                    "against opening hours. Turn on \"Filter by planned visit "
                    "day and time\" to plan around them.",
                )
            )
        return notes

    window = _window_label(weekday, start_time, end_time)
    day_hours = format_day_hours(hours_json, weekday)
    window_start = _minutes(start_time)
    window_end = _minutes(end_time)

    if not scheduled or visit is None:
        closings = [
            close
            for open_, close in open_intervals(hours_json, weekday)
            if open_ < window_end and close > window_start
        ]
        if closings and max(closings) < window_end:
            notes.append(
                TimingNote(
                    WARNING,
                    f"Not open when the tour would get there. On {weekday} "
                    f"it's {_hours_phrase(day_hours)}, and it closes at "
                    f"{format_clock(max(closings))}, before the other stops "
                    f"in your {window} window are done at {minutes_per_stop} "
                    f"minutes each. It's left off the map. Try fewer minutes "
                    f"per stop, fewer stops, or an earlier start.",
                )
            )
        else:
            notes.append(
                TimingNote(
                    WARNING,
                    f"Doesn't fit the tour plan. On {weekday} it's "
                    f"{_hours_phrase(day_hours)}, but at {minutes_per_stop} "
                    f"minutes per stop the other stops fill your {window} "
                    f"window first. It's left off the map. Try fewer minutes "
                    f"per stop, fewer stops, or a later end time.",
                )
            )
        return notes

    arrival = format_clock(visit.arrival)
    intervals = open_intervals(hours_json, weekday)
    if not any(open_ <= window_start < close for open_, close in intervals):
        opening = max(
            (open_ for open_, close in intervals if open_ <= visit.arrival < close),
            default=visit.arrival,
        )
        moved = (
            "so the tour starts by waiting for it"
            if position == 1
            else "so it's placed later in the route"
        )
        notes.append(
            TimingNote(
                INFO,
                f"Closed when your tour starts at "
                f"{format_clock(window_start)}. It opens at "
                f"{format_clock(opening)}, {moved}.",
            )
        )
    if visit.wait > 0 and position > 1:
        notes.append(
            TimingNote(
                INFO,
                f"You'll wait about {visit.wait} minutes for it to open after "
                f"the previous stop.",
            )
        )

    time_open = visit.closing - visit.arrival
    if time_open < minutes_per_stop:
        notes.append(
            TimingNote(
                WARNING,
                f"Closes at {format_clock(visit.closing)}, only {time_open} "
                f"minutes after you arrive around {arrival}, which is less "
                f"than your {minutes_per_stop}-minute stop. Head straight "
                f"there, or order to go.",
            )
        )
    elif visit.arrival + minutes_per_stop > window_end:
        notes.append(
            TimingNote(
                INFO,
                f"Arrive around {arrival}; the {minutes_per_stop}-minute stop "
                f"runs past the end of your {window} window.",
            )
        )
    elif visit.closing >= 24 * 60:
        notes.append(
            TimingNote(
                INFO,
                f"{_hours_phrase(day_hours, capital=True)} on {weekday}. You "
                f"arrive around {arrival}, and it's open through the rest of "
                f"your window.",
            )
        )
    else:
        notes.append(
            TimingNote(
                INFO,
                f"{_hours_phrase(day_hours, capital=True)} on {weekday}. You "
                f"arrive around {arrival}, and it's open until "
                f"{format_clock(visit.closing)}.",
            )
        )
    return notes


def why_picked(
    row: dict[str, Any],
    rank: int,
    total: int,
    food: str,
    tour: list[dict[str, Any]],
    start_label: str | None = None,
) -> list[str]:
    """Plain-language reasons this restaurant made the tour.

    ``rank`` is the restaurant's position (1 = best) among the ``total``
    restaurants that match the filters, and ``tour`` is every stop on the
    tour, used to point out where this stop leads the others.
    """
    reasons = [
        f"Ranked #{rank} of {total:,} {food} spots that match your filters, "
        f"with a recommendation score of {row['recommendation score']:.1f} "
        f"out of 100."
    ]

    mentions = int(row.get("matching food reviews") or 0)
    share = float(row.get("food positive sentiment") or 0)
    food_stars = row.get("food review stars")
    food_sentence = (
        f"{mentions:,} reviews mention its {food}, and {share:.0%} of those "
        f"mentions read as positive"
    )
    if food_stars is not None:
        food_sentence += f" (those reviews average {float(food_stars):.1f} stars)"
    others = [stop for stop in tour if stop is not row]
    if others and mentions > max(
        int(stop.get("matching food reviews") or 0) for stop in others
    ):
        food_sentence += ", the most of any stop on this tour"
    elif others and share > max(
        float(stop.get("food positive sentiment") or 0) for stop in others
    ):
        food_sentence += ", the most positive of any stop on this tour"
    reasons.append(food_sentence + ".")

    yelp_stars = row.get("Yelp stars")
    overall = row.get("overall Yelp reviews")
    if yelp_stars is not None and overall is not None:
        reasons.append(
            f"Overall it has {float(yelp_stars):.1f} Yelp stars from "
            f"{int(overall):,} reviews."
        )

    locations = int(row.get(CHAIN_LOCATIONS_COLUMN) or 1)
    if locations > 1:
        reasons.append(
            f"{row.get('name', 'This chain')} has {locations} locations; this "
            f"one is the closest to the other top spots."
        )

    distance = row.get(DISTANCE_COLUMN)
    if distance is not None:
        where = start_label or "the starting point"
        reasons.append(
            f"It's {float(distance):.2f} miles (straight line) from {where}."
        )
    return reasons
