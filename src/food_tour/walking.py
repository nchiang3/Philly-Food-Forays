"""Street-level walking routes from a free, key-less OSRM routing server.

The default server is the FOSSGIS OSRM service (routing.openstreetmap.de),
which routes on OpenStreetMap data with a real pedestrian ("foot") profile.
It needs no API key or account, but it is a donated public service with a
fair-use policy: send a descriptive User-Agent, keep requests occasional, and
cache results. The app caches each route for a day and falls back to
straight lines whenever the server cannot be reached.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.request import Request, urlopen


FOOT_ROUTING_URL = "https://routing.openstreetmap.de/routed-foot/route/v1/foot/"
USER_AGENT = "PhillyFoodForays/1.0 (Streamlit student project)"
METERS_PER_MILE = 1609.344
DEFAULT_TIMEOUT_SECONDS = 10

Point = tuple[float, float]


@dataclass(frozen=True)
class WalkingRoute:
    """A walking route through points in order.

    ``path`` holds ``[longitude, latitude]`` pairs that follow the streets,
    ready for a map line. ``leg_miles`` and ``leg_minutes`` have one entry per
    leg (one fewer than the number of points).
    """

    path: list[list[float]]
    leg_miles: list[float]
    leg_minutes: list[float]

    @property
    def total_miles(self) -> float:
        return sum(self.leg_miles)

    @property
    def total_minutes(self) -> float:
        return sum(self.leg_minutes)


def walking_route_url(points: list[Point], base_url: str = FOOT_ROUTING_URL) -> str:
    """Build an OSRM route request for ``(latitude, longitude)`` points."""
    if len(points) < 2:
        raise ValueError("A walking route needs at least two points.")
    # OSRM expects longitude first.
    coordinates = ";".join(
        f"{longitude:.6f},{latitude:.6f}" for latitude, longitude in points
    )
    return f"{base_url}{coordinates}?overview=full&geometries=geojson&steps=false"


def parse_walking_route(payload: dict[str, Any], leg_count: int) -> WalkingRoute | None:
    """Read an OSRM route response; return ``None`` if it is unusable."""
    if not isinstance(payload, dict) or payload.get("code") != "Ok":
        return None
    routes = payload.get("routes") or []
    if not routes:
        return None
    route = routes[0]
    legs = route.get("legs") or []
    path = (route.get("geometry") or {}).get("coordinates") or []
    if len(legs) != leg_count or len(path) < 2:
        return None
    try:
        leg_miles = [float(leg["distance"]) / METERS_PER_MILE for leg in legs]
        leg_minutes = [float(leg["duration"]) / 60 for leg in legs]
        path = [[float(point[0]), float(point[1])] for point in path]
    except (KeyError, TypeError, ValueError, IndexError):
        return None
    return WalkingRoute(path=path, leg_miles=leg_miles, leg_minutes=leg_minutes)


def fetch_walking_route(
    points: list[Point],
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    base_url: str = FOOT_ROUTING_URL,
    opener: Callable[..., Any] = urlopen,
) -> WalkingRoute | None:
    """Ask the routing server for a walking route through ``points`` in order.

    Returns ``None`` for fewer than two points, or when the server is slow,
    unreachable, or returns something unexpected, so callers can fall back to
    straight lines.
    """
    if len(points) < 2:
        return None
    request = Request(
        walking_route_url(points, base_url), headers={"User-Agent": USER_AGENT}
    )
    try:
        with opener(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError):
        # URLError, HTTPError, and timeouts are OSErrors; bad JSON is a
        # ValueError.
        return None
    return parse_walking_route(payload, len(points) - 1)
