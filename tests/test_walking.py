import io
import json
import unittest
from urllib.error import URLError

from src.food_tour.route import (
    CUMULATIVE_COLUMN,
    LEG_COLUMN,
    WALK_MINUTES_COLUMN,
    add_route_legs,
    map_markers,
)
from src.food_tour.walking import (
    FOOT_ROUTING_URL,
    METERS_PER_MILE,
    USER_AGENT,
    WalkingRoute,
    fetch_walking_route,
    parse_walking_route,
    walking_route_url,
)


POINTS = [(39.9526, -75.1635), (39.9533, -75.1590), (39.9489, -75.1500)]

# Trimmed from a real routing.openstreetmap.de foot-profile response.
PAYLOAD = {
    "code": "Ok",
    "routes": [
        {
            "legs": [
                {"distance": 468.8, "duration": 375},
                {"distance": 1310, "duration": 1048.5},
            ],
            "geometry": {
                "coordinates": [
                    [-75.163559, 39.952608],
                    [-75.163463, 39.953044],
                    [-75.159, 39.9533],
                    [-75.15, 39.9489],
                ]
            },
        }
    ],
}


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def fake_opener(payload, calls=None):
    def opener(request, timeout):
        if calls is not None:
            calls.append((request, timeout))
        return FakeResponse(json.dumps(payload).encode("utf-8"))

    return opener


def failing_opener(request, timeout):
    raise URLError("offline")


def spot(name, latitude, longitude):
    return {"name": name, "latitude": latitude, "longitude": longitude}


STOPS = [spot("City Hall", *POINTS[0]), spot("Reading", *POINTS[1]), spot("Indy", *POINTS[2])]


class WalkingRouteUrlTests(unittest.TestCase):
    def test_longitude_first_and_full_geometry(self) -> None:
        url = walking_route_url(POINTS[:2])
        self.assertTrue(url.startswith(FOOT_ROUTING_URL))
        self.assertIn("-75.163500,39.952600;-75.159000,39.953300?", url)
        self.assertIn("overview=full", url)
        self.assertIn("geometries=geojson", url)

    def test_needs_two_points(self) -> None:
        with self.assertRaises(ValueError):
            walking_route_url(POINTS[:1])


class ParseWalkingRouteTests(unittest.TestCase):
    def test_reads_legs_and_path(self) -> None:
        route = parse_walking_route(PAYLOAD, 2)
        self.assertEqual(len(route.path), 4)
        self.assertAlmostEqual(route.leg_miles[0], 468.8 / METERS_PER_MILE)
        self.assertAlmostEqual(route.leg_minutes[1], 1048.5 / 60)
        self.assertAlmostEqual(route.total_miles, (468.8 + 1310) / METERS_PER_MILE)
        self.assertAlmostEqual(route.total_minutes, (375 + 1048.5) / 60)

    def test_rejects_errors_and_mismatched_legs(self) -> None:
        self.assertIsNone(parse_walking_route({"code": "NoRoute"}, 2))
        self.assertIsNone(parse_walking_route({"code": "Ok", "routes": []}, 2))
        self.assertIsNone(parse_walking_route(PAYLOAD, 3))
        broken = {
            "code": "Ok",
            "routes": [{"legs": [{"duration": 1}, {"distance": 2, "duration": 3}],
                        "geometry": {"coordinates": [[0, 0], [1, 1]]}}],
        }
        self.assertIsNone(parse_walking_route(broken, 2))
        self.assertIsNone(parse_walking_route([], 2))


class FetchWalkingRouteTests(unittest.TestCase):
    def test_sends_user_agent_and_timeout(self) -> None:
        calls = []
        route = fetch_walking_route(POINTS, timeout=5, opener=fake_opener(PAYLOAD, calls))
        self.assertIsInstance(route, WalkingRoute)
        request, timeout = calls[0]
        self.assertEqual(timeout, 5)
        self.assertEqual(request.get_header("User-agent"), USER_AGENT)

    def test_returns_none_when_offline_or_bad_json(self) -> None:
        self.assertIsNone(fetch_walking_route(POINTS, opener=failing_opener))

        def bad_json(request, timeout):
            return FakeResponse(b"not json")

        self.assertIsNone(fetch_walking_route(POINTS, opener=bad_json))

    def test_single_point_skips_the_request(self) -> None:
        self.assertIsNone(fetch_walking_route(POINTS[:1], opener=failing_opener))


class LegsFromWalkingRouteTests(unittest.TestCase):
    def test_uses_street_miles_and_minutes(self) -> None:
        walking = parse_walking_route(PAYLOAD, 2)
        rows = add_route_legs(STOPS, walking=walking)
        self.assertEqual(rows[0][LEG_COLUMN], 0.0)
        self.assertEqual(rows[0][WALK_MINUTES_COLUMN], 0)
        self.assertEqual(rows[1][LEG_COLUMN], round(468.8 / METERS_PER_MILE, 2))
        self.assertEqual(rows[1][WALK_MINUTES_COLUMN], round(375 / 60))
        self.assertEqual(
            rows[2][CUMULATIVE_COLUMN], round((468.8 + 1310) / METERS_PER_MILE, 2)
        )

    def test_with_start_every_stop_has_a_leg(self) -> None:
        walking = parse_walking_route(PAYLOAD, 2)
        rows = add_route_legs(STOPS[1:], start=POINTS[0], walking=walking)
        self.assertEqual(rows[0][LEG_COLUMN], round(468.8 / METERS_PER_MILE, 2))
        self.assertEqual(rows[1][WALK_MINUTES_COLUMN], round(1048.5 / 60))

    def test_wrong_leg_count_is_an_error(self) -> None:
        walking = parse_walking_route(PAYLOAD, 2)
        with self.assertRaises(ValueError):
            add_route_legs(STOPS[:2], walking=walking)

    def test_straight_line_rows_have_no_minutes(self) -> None:
        self.assertNotIn(WALK_MINUTES_COLUMN, add_route_legs(STOPS)[1])

    def test_marker_tooltip_includes_minutes(self) -> None:
        walking = parse_walking_route(PAYLOAD, 2)
        markers = map_markers(add_route_legs(STOPS, walking=walking))
        self.assertEqual(markers[1]["leg"], "0.29 mi (6 min walk) from previous stop")


if __name__ == "__main__":
    unittest.main()
