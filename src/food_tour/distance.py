"""Distance filters that keep recommended food-tour stops close together."""

from __future__ import annotations

import math
from typing import Any


EARTH_RADIUS_MILES = 3958.8

TOP_RANKED_START = "Top-ranked restaurant"

# Well-known starting points, so users can anchor a tour without geocoding.
LANDMARKS: dict[str, tuple[float, float]] = {
    "City Hall": (39.9526, -75.1635),
    "Reading Terminal Market": (39.9533, -75.1590),
    "Independence Hall": (39.9489, -75.1500),
    "Italian Market (9th St)": (39.9381, -75.1579),
    "South Street (4th & South)": (39.9415, -75.1489),
    "30th Street Station": (39.9557, -75.1820),
    "Philadelphia Museum of Art": (39.9656, -75.1810),
    "Rittenhouse Square": (39.9496, -75.1718),
}

DISTANCE_COLUMN = "miles from start"


def haversine_miles(
    latitude_a: float, longitude_a: float, latitude_b: float, longitude_b: float
) -> float:
    """Return the straight-line (great-circle) distance in miles."""
    phi_a = math.radians(latitude_a)
    phi_b = math.radians(latitude_b)
    delta_phi = math.radians(latitude_b - latitude_a)
    delta_lambda = math.radians(longitude_b - longitude_a)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi_a) * math.cos(phi_b) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(min(1.0, a)))


def _coordinates(row: dict[str, Any]) -> tuple[float, float]:
    return float(row["latitude"]), float(row["longitude"])


def _with_distance(
    row: dict[str, Any], start: tuple[float, float]
) -> dict[str, Any]:
    miles = haversine_miles(*start, *_coordinates(row))
    return {**row, DISTANCE_COLUMN: round(miles, 2)}


def filter_near_start(
    ranked: list[dict[str, Any]],
    max_miles: float,
    start: tuple[float, float] | None = None,
) -> list[dict[str, Any]]:
    """Keep ranked restaurants within ``max_miles`` of a starting point.

    When ``start`` is omitted, the top-ranked restaurant is the starting point,
    so the result is the best spots clustered around the best spot. Ranking
    order is preserved, and each row gains a ``miles from start`` column.
    """
    if not ranked:
        return []
    origin = start if start is not None else _coordinates(ranked[0])
    nearby = [_with_distance(row, origin) for row in ranked]
    return [row for row in nearby if row[DISTANCE_COLUMN] <= max_miles]


def select_close_together(
    ranked: list[dict[str, Any]],
    max_miles: float,
    max_stops: int | None = None,
) -> list[dict[str, Any]]:
    """Greedily pick top spots that are all within ``max_miles`` of each other.

    Restaurants are considered in ranking order. A restaurant joins the tour
    only if it is within ``max_miles`` of every stop already chosen, so the
    largest gap between any two stops never exceeds the limit. The top-ranked
    restaurant is always the first stop, and distances are reported from it.
    """
    chosen: list[dict[str, Any]] = []
    for row in ranked:
        if max_stops is not None and len(chosen) >= max_stops:
            break
        point = _coordinates(row)
        if all(
            haversine_miles(*point, *_coordinates(stop)) <= max_miles
            for stop in chosen
        ):
            chosen.append(row)
    if not chosen:
        return []
    origin = _coordinates(chosen[0])
    return [_with_distance(row, origin) for row in chosen]


def max_pairwise_miles(rows: list[dict[str, Any]]) -> float:
    """Return the largest straight-line distance between any two rows."""
    points = [_coordinates(row) for row in rows]
    return max(
        (
            haversine_miles(*points[i], *points[j])
            for i in range(len(points))
            for j in range(i + 1, len(points))
        ),
        default=0.0,
    )


def stop_shortfall_message(requested: int, found: int) -> str | None:
    """Explain when fewer stops fit the filters than the user asked for.

    Returns ``None`` when the tour has as many stops as requested.
    """
    if found >= requested:
        return None
    noun = "restaurant fits" if found == 1 else "restaurants fit"
    return (
        f"You asked for {requested} stops, but only {found} {noun} your "
        f"filters. Try a larger distance, fewer minimum reviews, or a wider "
        f"visit window."
    )
