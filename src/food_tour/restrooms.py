"""Philadelphia restroom listings and proximity to a tour."""

import json
from functools import lru_cache
from math import cos, radians
from pathlib import Path

from .distance import haversine_miles

PHLUSH_SOURCE = "https://www.phila.gov/programs/philly-phlush/how-to-access-philly-phlush-restrooms/"
VISITOR_CENTER_SOURCE = "https://www.phlvisitorcenter.com/IndependenceVisitorCenter"
RESTROOM_RADIUS_MILES = 0.35
OSM_RESTROOMS_PATH = Path(__file__).resolve().parents[2] / "data" / "philadelphia_osm_restrooms.json"

# Pins mark approximate facility or venue locations. Entrance notes come from
# the city or venue, and posted hours are informational rather than live status.
PUBLIC_RESTROOMS = (
    {
        "id": "center-city",
        "title": "Philly Phlush · Center City",
        "latitude": 39.9544,
        "longitude": -75.1650,
        "address": "15th and Arch streets, near LOVE Park",
        "leg": "Municipal Services Building, on the side facing LOVE Park.",
        "hours": "Mon–Fri 8 a.m.–10 p.m. · Sat–Sun 8 a.m.–11 p.m. · City holidays 9 a.m.–5 p.m.",
        "accessibility": "Wheelchair accessible · Changing table",
        "fee": "Free",
        "source": PHLUSH_SOURCE,
    },
    {
        "id": "fotterall-square",
        "title": "Philly Phlush · Fotterall Square",
        "latitude": 39.9901,
        "longitude": -75.1507,
        "address": "2400 N. 11th St., off W. Cumberland Street",
        "leg": "Near the mini pitch and basketball court.",
        "hours": "Mon–Fri 10 a.m.–8 p.m. · Sat–Sun 10 a.m.–9 p.m. · City holidays 11 a.m.–3 p.m.",
        "accessibility": "Wheelchair accessible · Changing table",
        "fee": "Free",
        "source": PHLUSH_SOURCE,
    },
    {
        "id": "clark-park",
        "title": "Philly Phlush · Clark Park",
        "latitude": 39.9489,
        "longitude": -75.2090,
        "address": "South 43rd Street and Regent Square",
        "leg": "Near the basketball court.",
        "hours": "Mon–Fri 9 a.m.–9 p.m. · Sat–Sun 9 a.m.–10 p.m. · City holidays 10 a.m.–4 p.m.",
        "accessibility": "Wheelchair accessible · Changing table",
        "fee": "Free",
        "source": PHLUSH_SOURCE,
    },
    {
        "id": "independence-visitor-center",
        "title": "Independence Visitor Center",
        "latitude": 39.9512,
        "longitude": -75.1500,
        "address": "599 Market St.",
        "leg": "Inside the visitor center.",
        "hours": "Venue lists daily 9 a.m.–6 p.m. · Check the source for seasonal hours.",
        "accessibility": "Wheelchair accessible venue",
        "fee": "Free",
        "source": VISITOR_CENTER_SOURCE,
    },
)


@lru_cache(maxsize=1)
def _restroom_listings() -> tuple[dict, ...]:
    """Combine the verified venues with the bundled ODbL snapshot."""
    snapshot = json.loads(OSM_RESTROOMS_PATH.read_text(encoding="utf-8"))
    mapped = []
    for element in snapshot["elements"]:
        lat, lon = element["latitude"], element["longitude"]
        if any(
            haversine_miles(lat, lon, venue["latitude"], venue["longitude"]) < 0.035
            for venue in PUBLIC_RESTROOMS
        ):
            continue
        tags = element["tags"]

        def toilet_tag(name):
            return tags.get(f"toilets:{name}", tags.get(name))

        access = toilet_tag("access")
        access_label = {
            "yes": "Public access mapped",
            "public": "Public access mapped",
            "permissive": "Public access by permission",
        }.get(access, "Public access unconfirmed")
        wheelchair = {"yes": "Wheelchair accessible", "no": "No wheelchair access", "limited": "Limited wheelchair access"}
        accessibility = wheelchair.get(toilet_tag("wheelchair"), "Wheelchair access unknown")
        if toilet_tag("changing_table") == "yes":
            accessibility += " · Changing table mapped"

        kind, osm_id = element["type"], element["id"]
        address = " ".join(
            tags[key] for key in ("addr:housenumber", "addr:street") if key in tags
        )
        mapped.append({
            "id": f"osm-{kind}-{osm_id}",
            "title": tags.get("name") or "Mapped restroom",
            "latitude": lat,
            "longitude": lon,
            "address": address,
            "leg": access_label,
            "hours": toilet_tag("opening_hours") or "Unknown",
            "accessibility": accessibility,
            "fee": {"yes": "Fee required", "no": "Free"}.get(toilet_tag("fee"), "Unknown"),
            "source": f"https://www.openstreetmap.org/{kind}/{osm_id}",
            "source_label": "View OpenStreetMap listing",
        })
    return (*PUBLIC_RESTROOMS, *mapped)


def _distance_to_segment(latitude, longitude, first, last):
    # Scale longitude for the local projection onto this short Philly segment.
    scale = cos(radians(latitude))
    start_lon, start_lat = first
    end_lon, end_lat = last
    dx = (end_lon - start_lon) * scale
    dy = end_lat - start_lat
    squared_length = dx * dx + dy * dy
    fraction = 0.0
    if squared_length:
        projection = ((longitude - start_lon) * scale * dx + (latitude - start_lat) * dy)
        fraction = min(1.0, max(0.0, projection / squared_length))
    return haversine_miles(
        latitude,
        longitude,
        start_lat + fraction * (end_lat - start_lat),
        start_lon + fraction * (end_lon - start_lon),
    )


def nearby_restrooms(path: list[list[float]]) -> list[dict]:
    """Find listed restrooms near the route line, including single-stop tours."""
    if not path:
        return []
    segments = list(zip(path, path[1:])) or [(path[0], path[0])]
    return [
        restroom
        for restroom in _restroom_listings()
        if any(
            _distance_to_segment(restroom["latitude"], restroom["longitude"], first, last)
            <= RESTROOM_RADIUS_MILES
            for first, last in segments
        )
    ]
