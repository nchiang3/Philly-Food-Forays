import unittest

from src.food_tour.distance import LANDMARKS, haversine_miles
from src.food_tour.route import (
    CUMULATIVE_COLUMN,
    LEG_COLUMN,
    WALK_ORDER_COLUMN,
    _two_opt,
    add_route_legs,
    google_maps_walking_urls,
    map_markers,
    map_view,
    order_walking_route,
    path_miles,
    route_path,
    total_route_miles,
)


def spot(name: str, latitude: float, longitude: float = -75.16) -> dict:
    return {"name": name, "latitude": latitude, "longitude": longitude}


def names(rows: list[dict]) -> list[str]:
    return [row["name"] for row in rows]


# Five spots along one street, with uneven gaps so no two legs tie. They are
# listed in ranking order, which jumps back and forth along the street.
A = spot("A", 39.950)
B = spot("B", 39.954)
C = spot("C", 39.959)
D = spot("D", 39.965)
E = spot("E", 39.972)
RANKED = [C, A, E, B, D]


class OrderWalkingRouteTests(unittest.TestCase):
    def test_walks_along_the_street_instead_of_ranking_order(self) -> None:
        route = order_walking_route(RANKED)
        self.assertEqual(names(route), ["A", "B", "C", "D", "E"])
        self.assertEqual([row[WALK_ORDER_COLUMN] for row in route], [1, 2, 3, 4, 5])
        self.assertLess(total_route_miles(route), total_route_miles(RANKED))

    def test_fixed_start_goes_to_nearest_side_first(self) -> None:
        # Starting just north of E, the walk should head south from E to A.
        route = order_walking_route(RANKED, start=(39.975, -75.16))
        self.assertEqual(names(route), ["E", "D", "C", "B", "A"])

    def test_does_not_modify_input(self) -> None:
        order_walking_route(RANKED)
        self.assertNotIn(WALK_ORDER_COLUMN, RANKED[0])
        self.assertEqual(names(RANKED), ["C", "A", "E", "B", "D"])

    def test_single_and_empty(self) -> None:
        self.assertEqual(order_walking_route([]), [])
        route = order_walking_route([A])
        self.assertEqual(names(route), ["A"])
        self.assertEqual(route[0][WALK_ORDER_COLUMN], 1)

    def test_accepts_coordinates_as_text(self) -> None:
        # Uploaded CSV rows carry latitude and longitude as strings.
        rows = [
            {"name": "far", "latitude": "39.970", "longitude": "-75.16"},
            {"name": "near", "latitude": "39.951", "longitude": "-75.16"},
        ]
        route = order_walking_route(rows, start=(39.950, -75.16))
        self.assertEqual(names(route), ["near", "far"])


class TwoOptTests(unittest.TestCase):
    def test_reverses_a_segment_that_shortens_the_path(self) -> None:
        distances = [
            [0, 1, 0.5, 9],
            [1, 0, 1, 0.5],
            [0.5, 1, 0, 1],
            [9, 0.5, 1, 0],
        ]
        self.assertEqual(_two_opt([0, 1, 2, 3], distances), [0, 2, 1, 3])

    def test_keeps_the_first_node(self) -> None:
        distances = [
            [0, 5, 1],
            [5, 0, 1],
            [1, 1, 0],
        ]
        self.assertEqual(_two_opt([0, 1, 2], distances)[0], 0)


class RouteLegsTests(unittest.TestCase):
    def test_legs_and_running_total_without_start(self) -> None:
        rows = add_route_legs([A, B, C])
        self.assertEqual(rows[0][LEG_COLUMN], 0.0)
        ab = haversine_miles(39.950, -75.16, 39.954, -75.16)
        bc = haversine_miles(39.954, -75.16, 39.959, -75.16)
        self.assertEqual(rows[1][LEG_COLUMN], round(ab, 2))
        self.assertEqual(rows[2][LEG_COLUMN], round(bc, 2))
        self.assertEqual(rows[2][CUMULATIVE_COLUMN], round(ab + bc, 2))
        self.assertAlmostEqual(total_route_miles([A, B, C]), ab + bc)

    def test_first_leg_from_start(self) -> None:
        start = LANDMARKS["City Hall"]
        rows = add_route_legs([A], start)
        expected = round(haversine_miles(*start, 39.950, -75.16), 2)
        self.assertEqual(rows[0][LEG_COLUMN], expected)
        self.assertEqual(rows[0][CUMULATIVE_COLUMN], expected)

    def test_path_miles_of_short_paths(self) -> None:
        self.assertEqual(path_miles([]), 0.0)
        self.assertEqual(path_miles([(39.95, -75.16)]), 0.0)


class GoogleMapsUrlTests(unittest.TestCase):
    def test_single_link_with_waypoints_in_order(self) -> None:
        urls = google_maps_walking_urls([A, B, C])
        self.assertEqual(len(urls), 1)
        url = urls[0]
        self.assertTrue(url.startswith("https://www.google.com/maps/dir/?api=1"))
        self.assertIn("origin=39.950000,-75.160000", url)
        self.assertIn("destination=39.959000,-75.160000", url)
        self.assertIn("waypoints=39.954000,-75.160000", url)
        self.assertIn("travelmode=walking", url)

    def test_start_becomes_origin(self) -> None:
        url = google_maps_walking_urls([A, B], start=(39.94, -75.15))[0]
        self.assertIn("origin=39.940000,-75.150000", url)
        self.assertIn("waypoints=39.950000,-75.160000&", url)
        self.assertIn("destination=39.954000,-75.160000", url)

    def test_waypoints_are_separated_by_pipes(self) -> None:
        url = google_maps_walking_urls([A, B, C, D])[0]
        self.assertIn("waypoints=39.954000,-75.160000|39.959000,-75.160000", url)

    def test_long_route_splits_into_linked_parts(self) -> None:
        stops = [spot(str(k), 39.95 + k * 0.001) for k in range(12)]
        urls = google_maps_walking_urls(stops)
        self.assertEqual(len(urls), 2)
        # The second link picks up where the first one ended.
        self.assertIn("destination=39.960000,-75.160000", urls[0])
        self.assertIn("origin=39.960000,-75.160000", urls[1])
        self.assertIn("destination=39.961000,-75.160000", urls[1])
        self.assertEqual(urls[0].count("|"), 8)

    def test_single_stop_gives_directions_from_current_location(self) -> None:
        url = google_maps_walking_urls([A])[0]
        self.assertNotIn("origin=", url)
        self.assertIn("destination=39.950000,-75.160000", url)

    def test_empty_and_invalid(self) -> None:
        self.assertEqual(google_maps_walking_urls([]), [])
        with self.assertRaises(ValueError):
            google_maps_walking_urls([A, B], max_points=1)


class MapDataTests(unittest.TestCase):
    def test_markers_number_stops_and_mark_start(self) -> None:
        rows = add_route_legs([A, B], start=(39.94, -75.15))
        markers = map_markers(rows, (39.94, -75.15), "City Hall")
        self.assertEqual([m["label"] for m in markers], ["S", "1", "2"])
        self.assertTrue(markers[0]["is_start"])
        self.assertEqual(markers[0]["title"], "Start: City Hall")
        self.assertEqual(markers[2]["title"], "2. B")
        self.assertIn("mi from previous stop", markers[2]["leg"])
        self.assertNotIn("hours_json", markers[1])

    def test_route_path_is_longitude_first(self) -> None:
        self.assertEqual(
            route_path([A, B], start=(39.94, -75.15)),
            [[-75.15, 39.94], [-75.16, 39.950], [-75.16, 39.954]],
        )

    def test_view_centers_on_points_and_zooms_out_for_wider_tours(self) -> None:
        close = map_view([(39.950, -75.16), (39.954, -75.16)])
        wide = map_view([(39.90, -75.20), (40.05, -75.05)])
        self.assertAlmostEqual(close["latitude"], 39.952)
        self.assertAlmostEqual(close["longitude"], -75.16)
        self.assertGreater(close["zoom"], wide["zoom"])
        self.assertGreaterEqual(wide["zoom"], 10)
        self.assertEqual(map_view([(39.95, -75.16)])["zoom"], 16)

    def test_view_needs_points(self) -> None:
        with self.assertRaises(ValueError):
            map_view([])


if __name__ == "__main__":
    unittest.main()
