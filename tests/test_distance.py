import unittest

from src.food_tour.distance import (
    DISTANCE_COLUMN,
    LANDMARKS,
    filter_near_start,
    haversine_miles,
    max_pairwise_miles,
    select_close_together,
    stop_shortfall_message,
)


def spot(name: str, latitude: float, longitude: float) -> dict:
    return {"name": name, "latitude": latitude, "longitude": longitude}


# Ranked best-first. Center City spots are a few blocks apart; the Northeast
# Philadelphia spot is about 9 miles away.
RANKED = [
    spot("Reading Terminal", 39.9533, -75.1590),
    spot("Far Northeast", 40.0800, -75.0300),
    spot("City Hall Cart", 39.9526, -75.1635),
    spot("Chinatown", 39.9555, -75.1556),
    spot("Old City", 39.9500, -75.1440),
]


class HaversineTests(unittest.TestCase):
    def test_known_distance(self) -> None:
        # City Hall to the Philadelphia Museum of Art is roughly 1.3 miles.
        miles = haversine_miles(*LANDMARKS["City Hall"], *LANDMARKS["Philadelphia Museum of Art"])
        self.assertAlmostEqual(miles, 1.3, delta=0.15)

    def test_same_point_is_zero(self) -> None:
        self.assertEqual(haversine_miles(39.95, -75.16, 39.95, -75.16), 0.0)


class FilterNearStartTests(unittest.TestCase):
    def test_defaults_to_top_ranked_spot_and_keeps_order(self) -> None:
        result = filter_near_start(RANKED, 1.0)
        self.assertEqual(
            [row["name"] for row in result],
            ["Reading Terminal", "City Hall Cart", "Chinatown", "Old City"],
        )
        self.assertEqual(result[0][DISTANCE_COLUMN], 0.0)

    def test_uses_given_start(self) -> None:
        result = filter_near_start(RANKED, 0.3, LANDMARKS["City Hall"])
        self.assertEqual(
            [row["name"] for row in result], ["Reading Terminal", "City Hall Cart"]
        )

    def test_does_not_modify_input(self) -> None:
        filter_near_start(RANKED, 1.0)
        self.assertNotIn(DISTANCE_COLUMN, RANKED[0])

    def test_empty(self) -> None:
        self.assertEqual(filter_near_start([], 1.0), [])


class SelectCloseTogetherTests(unittest.TestCase):
    def test_every_pair_within_limit(self) -> None:
        result = select_close_together(RANKED, 0.5)
        names = [row["name"] for row in result]
        self.assertEqual(names, ["Reading Terminal", "City Hall Cart", "Chinatown"])
        self.assertLessEqual(max_pairwise_miles(result), 0.5)

    def test_respects_stop_limit(self) -> None:
        result = select_close_together(RANKED, 2.0, max_stops=2)
        self.assertEqual(
            [row["name"] for row in result], ["Reading Terminal", "City Hall Cart"]
        )

    def test_empty(self) -> None:
        self.assertEqual(select_close_together([], 1.0), [])
        self.assertEqual(max_pairwise_miles([]), 0.0)


class StopShortfallMessageTests(unittest.TestCase):
    def test_no_message_when_enough_stops(self) -> None:
        self.assertIsNone(stop_shortfall_message(5, 5))

    def test_message_names_requested_and_found(self) -> None:
        message = stop_shortfall_message(5, 3)
        self.assertIn("You asked for 5 stops, but only 3 restaurants fit", message)

    def test_singular_wording(self) -> None:
        self.assertIn("only 1 restaurant fits", stop_shortfall_message(4, 1))

    def test_close_together_shortfall(self) -> None:
        # Only three Center City spots are within half a mile of each other.
        tour = select_close_together(RANKED, 0.5, max_stops=5)
        self.assertEqual(len(tour), 3)
        self.assertIn("only 3 restaurants", stop_shortfall_message(5, len(tour)))


if __name__ == "__main__":
    unittest.main()
