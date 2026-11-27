"""Walking order, leg distances, and map data for a food tour."""

from __future__ import annotations

import math
from typing import Any
from urllib.parse import urlencode

from .distance import haversine_miles
from .walking import WalkingRoute


WALK_ORDER_COLUMN = "walk order"
LEG_COLUMN = "walk from previous"
CUMULATIVE_COLUMN = "walked so far"
WALK_MINUTES_COLUMN = "walking minutes"

# Google Maps direction links accept an origin, a destination, and up to nine
# waypoints, so one link covers at most 11 points.
GOOGLE_MAPS_MAX_POINTS = 11
GOOGLE_MAPS_DIRECTIONS = "https://www.google.com/maps/dir/"

Point = tuple[float, float]


def _point(row: dict[str, Any]) -> Point:
    return float(row["latitude"]), float(row["longitude"])


def _route_points(
    stops: list[dict[str, Any]], start: Point | None
) -> list[Point]:
    points = [_point(row) for row in stops]
    return [start, *points] if start is not None else points


def path_miles(points: list[Point]) -> float:
    """Return the straight-line length of a path through ``points`` in order."""
    return sum(
        haversine_miles(*points[i], *points[i + 1])
        for i in range(len(points) - 1)
    )


def _nearest_neighbor(first: int, distances: list[list[float]]) -> list[int]:
    path = [first]
    remaining = set(range(len(distances))) - {first}
    while remaining:
        here = path[-1]
        # Ties go to the lower index, which is the better-ranked stop.
        following = min(remaining, key=lambda node: (distances[here][node], node))
        path.append(following)
        remaining.remove(following)
    return path


def _two_opt(path: list[int], distances: list[list[float]]) -> list[int]:
    """Improve an open path by reversing segments; the first node stays put."""
    path = list(path)
    count = len(path)
    improved = True
    while improved:
        improved = False
        for i in range(1, count - 1):
            for j in range(i + 1, count):
                before = distances[path[i - 1]][path[i]]
                after = distances[path[i - 1]][path[j]]
                if j + 1 < count:
                    before += distances[path[j]][path[j + 1]]
                    after += distances[path[i]][path[j + 1]]
                if after < before - 1e-9:
                    path[i : j + 1] = reversed(path[i : j + 1])
                    improved = True
    return path


def order_walking_route(
    stops: list[dict[str, Any]], start: Point | None = None
) -> list[dict[str, Any]]:
    """Reorder ``stops`` into a short walking route that visits each once.

    The route is open (it does not return to the beginning). With a ``start``
    point, the walk begins there; otherwise any stop may come first. Each
    candidate first stop gets a nearest-neighbor route, improved with 2-opt
    segment reversals, and the shortest result wins. Ties go to the route
    that starts at the better-ranked stop. Distances are straight-line miles.

    Every row gains a ``walk order`` (1, 2, ...). The input is not modified.
    """
    if not stops:
        return []
    points = _route_points(stops, start)
    distances = [[haversine_miles(*a, *b) for b in points] for a in points]
    first_choices = [0] if start is not None else range(len(points))

    best_path: list[int] | None = None
    best_miles = math.inf
    for first in first_choices:
        path = _two_opt(_nearest_neighbor(first, distances), distances)
        miles = sum(distances[path[k]][path[k + 1]] for k in range(len(path) - 1))
        if miles < best_miles - 1e-9:
            best_path, best_miles = path, miles

    offset = 1 if start is not None else 0
    ordered = [stops[node - offset] for node in best_path if node >= offset]
    return [
        {**row, WALK_ORDER_COLUMN: position}
        for position, row in enumerate(ordered, start=1)
    ]


def add_route_legs(
    stops: list[dict[str, Any]],
    start: Point | None = None,
    walking: WalkingRoute | None = None,
) -> list[dict[str, Any]]:
    """Add miles for each leg and the running total.

    ``stops`` must already be in visiting order. The first leg is measured
    from ``start`` when given, and is 0 otherwise. With a ``walking`` route
    (from :func:`food_tour.walking.fetch_walking_route` for the same points),
    legs use its street walking miles and rows also gain ``walking minutes``;
    otherwise legs are straight-line miles.
    """
    legs: list[float | None] = []
    minutes: list[float | None] = []
    if walking is not None:
        expected = len(stops) if start is not None else max(len(stops) - 1, 0)
        if len(walking.leg_miles) != expected:
            raise ValueError("The walking route has the wrong number of legs.")
        legs = list(walking.leg_miles)
        minutes = list(walking.leg_minutes)
        if start is None and stops:
            legs.insert(0, 0.0)
            minutes.insert(0, 0.0)

    rows: list[dict[str, Any]] = []
    previous = start
    total = 0.0
    for position, row in enumerate(stops):
        here = _point(row)
        if walking is not None:
            leg = legs[position]
        else:
            leg = haversine_miles(*previous, *here) if previous is not None else 0.0
        total += leg
        new_row = {
            **row,
            LEG_COLUMN: round(leg, 2),
            CUMULATIVE_COLUMN: round(total, 2),
        }
        if walking is not None:
            new_row[WALK_MINUTES_COLUMN] = round(minutes[position])
        rows.append(new_row)
        previous = here
    return rows


def route_points(
    stops: list[dict[str, Any]], start: Point | None = None
) -> list[Point]:
    """Return ``(latitude, longitude)`` for the start (if any) and each stop."""
    return _route_points(stops, start)


def total_route_miles(
    stops: list[dict[str, Any]], start: Point | None = None
) -> float:
    """Return the straight-line length of the route through ``stops``."""
    return path_miles(_route_points(stops, start))


def _format_point(point: Point) -> str:
    return f"{point[0]:.6f},{point[1]:.6f}"


def google_maps_walking_urls(
    stops: list[dict[str, Any]],
    start: Point | None = None,
    max_points: int = GOOGLE_MAPS_MAX_POINTS,
) -> list[str]:
    """Build Google Maps walking-directions links for the route, in order.

    Uses Google's documented, key-free ``maps/dir/?api=1`` URL format with
    coordinates, so each stop lands on the exact Yelp location. A route with
    more points than one link allows is split into consecutive links, each
    starting where the previous one ended. With a single stop and no start,
    the link gives directions from the user's current location.
    """
    if max_points < 2:
        raise ValueError("A directions link needs room for at least two points.")
    points = _route_points(stops, start)
    if not points:
        return []
    if len(points) == 1:
        return [_directions_url(None, points[0], [])]
    urls = []
    for begin in range(0, len(points) - 1, max_points - 1):
        chunk = points[begin : begin + max_points]
        urls.append(_directions_url(chunk[0], chunk[-1], chunk[1:-1]))
    return urls


def _directions_url(
    origin: Point | None, destination: Point, waypoints: list[Point]
) -> str:
    params = {"api": "1"}
    if origin is not None:
        params["origin"] = _format_point(origin)
    params["destination"] = _format_point(destination)
    if waypoints:
        params["waypoints"] = "|".join(_format_point(point) for point in waypoints)
    params["travelmode"] = "walking"
    return f"{GOOGLE_MAPS_DIRECTIONS}?{urlencode(params, safe=',|')}"


def map_markers(
    stops: list[dict[str, Any]],
    start: Point | None = None,
    start_label: str = "Start",
) -> list[dict[str, Any]]:
    """Compact marker rows for a map: one per stop, plus the start if given.

    Each marker has a short ``label`` ("1", "2", ... or "S" for the start), a
    ``title`` for tooltips, ``latitude`` and ``longitude`` as floats, and an
    ``is_start`` flag. Only these small fields are kept so large columns such
    as raw hours are not sent to the browser.
    """
    markers = []
    if start is not None:
        markers.append(
            {
                "label": "S",
                "title": f"Start: {start_label}",
                "address": "",
                "leg": "",
                "latitude": start[0],
                "longitude": start[1],
                "is_start": True,
            }
        )
    for position, row in enumerate(stops, start=1):
        latitude, longitude = _point(row)
        leg = row.get(LEG_COLUMN)
        minutes = row.get(WALK_MINUTES_COLUMN)
        leg_text = "" if leg is None else f"{leg:.2f} mi"
        if leg_text and minutes is not None:
            leg_text += f" ({minutes:.0f} min walk)"
        if leg_text:
            leg_text += " from previous stop"
        markers.append(
            {
                "label": str(position),
                "title": f"{position}. {row.get('name', '')}",
                "address": row.get("address", "") or "",
                "leg": leg_text,
                "latitude": latitude,
                "longitude": longitude,
                "is_start": False,
            }
        )
    return markers


def route_path(
    stops: list[dict[str, Any]], start: Point | None = None
) -> list[list[float]]:
    """Return the route as ``[longitude, latitude]`` pairs for a map line."""
    return [[longitude, latitude] for latitude, longitude in _route_points(stops, start)]


def map_view(points: list[Point]) -> dict[str, float]:
    """Pick a map center and zoom level that fits ``points``."""
    if not points:
        raise ValueError("At least one point is needed to center the map.")
    latitudes = [point[0] for point in points]
    longitudes = [point[1] for point in points]
    center_latitude = (min(latitudes) + max(latitudes)) / 2
    center_longitude = (min(longitudes) + max(longitudes)) / 2
    # Web Mercator stretches latitude by 1 / cos(latitude), so convert the
    # latitude span to longitude-sized degrees before comparing.
    span = max(
        max(longitudes) - min(longitudes),
        (max(latitudes) - min(latitudes)) / math.cos(math.radians(center_latitude)),
        0.002,
    )
    # At zoom z, about 360 * pixels / (256 * 2**z) degrees fit on screen.
    # Solving for a ~450 px map with 50% padding gives 2**z = 420 / span.
    zoom = max(10.0, min(16.0, math.log2(420 / span)))
    return {
        "latitude": center_latitude,
        "longitude": center_longitude,
        "zoom": round(zoom, 1),
    }
