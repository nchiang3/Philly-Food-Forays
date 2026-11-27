"""Order tour stops by opening hours within the selected visit window."""

from __future__ import annotations

from datetime import time
from typing import Any

from .hours import format_clock, open_intervals


VISIT_ORDER_COLUMN = "visit order"
ARRIVAL_COLUMN = "arrive around"
NOT_IN_WINDOW = "Doesn't fit window"

DEFAULT_MINUTES_PER_STOP = 45


def _minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def earliest_visit(
    hours_json: str | None,
    weekday: str,
    not_before: int,
    window_end: int,
) -> tuple[int, int] | None:
    """Return ``(arrival, closing)`` for the first open moment at or after
    ``not_before`` and before ``window_end``, in minutes after midnight.

    Returns ``None`` when the business does not open again before the window
    ends (or has no usable hours).
    """
    for open_start, open_end in open_intervals(hours_json, weekday):
        arrival = max(not_before, open_start)
        if arrival < open_end and arrival < window_end:
            return arrival, open_end
    return None


def plan_visit_order(
    stops: list[dict[str, Any]],
    weekday: str,
    start_time: time,
    end_time: time,
    minutes_per_stop: int = DEFAULT_MINUTES_PER_STOP,
    hours_key: str = "hours_json",
) -> list[dict[str, Any]]:
    """Order ``stops`` so each is visited while it is open, within the window.

    Starting at ``start_time``, the next stop is always the one that can be
    visited soonest: restaurants already open come first, and later-opening
    ones are scheduled once they open. Among stops available at the same
    time, the one that closes soonest goes first, then the better-ranked one
    (earlier in ``stops``). Each visit, including walking to the next stop,
    takes ``minutes_per_stop``. A stop must be reached before it closes and
    before ``end_time``.

    Every row gains a ``visit order`` (1, 2, ...) and an ``arrive around``
    time. Stops that cannot be reached in the window are listed last with no
    visit order and ``arrive around`` set to "Doesn't fit window".
    """
    window_start = _minutes(start_time)
    window_end = _minutes(end_time)
    if window_end <= window_start:
        raise ValueError("End time must be later than start time.")
    if minutes_per_stop <= 0:
        raise ValueError("Minutes per stop must be positive.")

    remaining = list(enumerate(stops))
    planned: list[dict[str, Any]] = []
    clock = window_start
    while remaining:
        options = []
        for position, (rank, stop) in enumerate(remaining):
            visit = earliest_visit(
                stop.get(hours_key), weekday, clock, window_end
            )
            if visit is not None:
                arrival, closing = visit
                options.append((arrival, closing, rank, position))
        if not options:
            break
        arrival, _closing, _rank, position = min(options)
        _, stop = remaining.pop(position)
        planned.append(
            {
                **stop,
                VISIT_ORDER_COLUMN: len(planned) + 1,
                ARRIVAL_COLUMN: format_clock(arrival),
            }
        )
        clock = arrival + minutes_per_stop

    skipped = [
        {**stop, VISIT_ORDER_COLUMN: None, ARRIVAL_COLUMN: NOT_IN_WINDOW}
        for _, stop in remaining
    ]
    return planned + skipped


def unscheduled_message(plan: list[dict[str, Any]]) -> str | None:
    """Explain how many stops could not be fit into the visit window."""
    skipped = sum(row.get(VISIT_ORDER_COLUMN) is None for row in plan)
    if not skipped:
        return None
    noun = "stop doesn't" if skipped == 1 else "stops don't"
    return (
        f"{skipped} {noun} fit in the visit window at this pace. They are "
        f"listed last. Try fewer minutes per stop, fewer stops, or a later "
        f"end time."
    )
