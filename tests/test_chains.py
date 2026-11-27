import unittest

from src.food_tour.chains import (
    CHAIN_LOCATIONS_COLUMN,
    chain_key,
    collapse_chains,
    merged_chain_count,
    select_close_together_one_per_chain,
)
from src.food_tour.distance import (
    DISTANCE_COLUMN,
    LANDMARKS,
    filter_near_start,
    max_pairwise_miles,
    select_close_together,
)


def spot(name: str, latitude: float, longitude: float, score: float = 0.0) -> dict:
    return {
        "name": name,
        "latitude": latitude,
        "longitude": longitude,
        "recommendation score": score,
    }


# Ranked best-first. The best Wawa is in the Far Northeast, about 9 miles from
# the Center City cluster; another Wawa sits near Reading Terminal and a third
# is in South Philadelphia.
RANKED = [
    spot("Wawa", 40.0800, -75.0300, 90),
    spot("Reading Terminal Grill", 39.9533, -75.1590, 85),
    spot("WAWA", 39.9540, -75.1600, 80),
    spot("City Hall Cart", 39.9526, -75.1635, 75),
    spot("Chinatown Steaks", 39.9555, -75.1556, 70),
    spot("Wawa", 39.9250, -75.1700, 65),
    spot("Old City Hoagies", 39.9500, -75.1440, 60),
]


def names(rows: list[dict]) -> list[str]:
    return [row["name"] for row in rows]


class ChainKeyTests(unittest.TestCase):
    def test_ignores_case_punctuation_and_accents(self) -> None:
        self.assertEqual(chain_key("WAWA"), chain_key("Wawa"))
        self.assertEqual(
            chain_key("Pat's King of Steaks"), chain_key("Pats King Of Steaks")
        )
        self.assertEqual(chain_key("Café Ole"), chain_key("cafe ole"))
        self.assertEqual(chain_key("The Taco Spot"), chain_key("Taco Spot"))
        self.assertEqual(chain_key("Ben & Jerry's"), chain_key("Ben and Jerrys"))

    def test_different_names_stay_different(self) -> None:
        self.assertNotEqual(chain_key("Wawa"), chain_key("Wawa Welcome America"))


class CollapseChainsTests(unittest.TestCase):
    def test_keeps_location_closest_to_other_top_picks(self) -> None:
        result = collapse_chains(RANKED)
        wawas = [row for row in result if chain_key(row["name"]) == "wawa"]
        self.assertEqual(len(wawas), 1)
        # The Center City Wawa (third in RANKED) beats the higher-ranked Far
        # Northeast one and the South Philadelphia one.
        self.assertEqual(wawas[0]["latitude"], 39.9540)
        self.assertEqual(wawas[0][CHAIN_LOCATIONS_COLUMN], 3)

    def test_chain_keeps_rank_of_best_location(self) -> None:
        result = collapse_chains(RANKED)
        self.assertEqual(
            names(result),
            [
                "WAWA",
                "Reading Terminal Grill",
                "City Hall Cart",
                "Chinatown Steaks",
                "Old City Hoagies",
            ],
        )

    def test_single_locations_unchanged(self) -> None:
        result = collapse_chains(RANKED)
        grill = result[1]
        self.assertEqual(grill[CHAIN_LOCATIONS_COLUMN], 1)
        self.assertEqual(grill["latitude"], 39.9533)
        self.assertEqual(merged_chain_count(result), 1)

    def test_does_not_modify_input(self) -> None:
        collapse_chains(RANKED)
        self.assertNotIn(CHAIN_LOCATIONS_COLUMN, RANKED[0])

    def test_unnamed_rows_never_merge(self) -> None:
        rows = [spot("", 39.95, -75.16), spot("", 39.96, -75.17)]
        self.assertEqual(len(collapse_chains(rows)), 2)

    def test_empty(self) -> None:
        self.assertEqual(collapse_chains([]), [])
        self.assertEqual(merged_chain_count([]), 0)

    def test_after_near_start_filter_only_in_range_locations_count(self) -> None:
        nearby = filter_near_start(RANKED, 1.0, LANDMARKS["City Hall"])
        result = collapse_chains(nearby)
        wawas = [row for row in result if chain_key(row["name"]) == "wawa"]
        self.assertEqual(len(wawas), 1)
        self.assertEqual(wawas[0]["latitude"], 39.9540)
        self.assertIn(DISTANCE_COLUMN, wawas[0])


class CloseTogetherOnePerChainTests(unittest.TestCase):
    def test_first_stop_is_chain_location_near_other_picks(self) -> None:
        tour = select_close_together_one_per_chain(RANKED, 0.5, max_stops=5)
        self.assertEqual(
            names(tour),
            ["WAWA", "Reading Terminal Grill", "City Hall Cart", "Chinatown Steaks"],
        )
        self.assertEqual(tour[0][CHAIN_LOCATIONS_COLUMN], 3)
        self.assertLessEqual(max_pairwise_miles(tour), 0.5)

    def test_never_repeats_a_chain(self) -> None:
        tour = select_close_together_one_per_chain(RANKED, 20.0)
        keys = [chain_key(row["name"]) for row in tour]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(len(tour), 5)

    def test_picks_fitting_location_closest_to_chosen_stops(self) -> None:
        ranked = [
            spot("Grill", 39.9533, -75.1590),
            spot("Wawa", 39.9250, -75.1700),  # South Philly, 2 miles away
            spot("Wawa", 39.9540, -75.1600),  # next to the Grill
        ]
        tour = select_close_together_one_per_chain(ranked, 3.0)
        self.assertEqual(names(tour), ["Grill", "Wawa"])
        self.assertEqual(tour[1]["latitude"], 39.9540)

    def test_skips_chain_only_when_no_location_fits(self) -> None:
        ranked = [
            spot("Grill", 39.9533, -75.1590),
            spot("Wawa", 40.0800, -75.0300),
            spot("Wawa", 39.9250, -75.1700),
        ]
        self.assertEqual(
            names(select_close_together_one_per_chain(ranked, 0.5)), ["Grill"]
        )

    def test_plain_mode_still_allows_repeats(self) -> None:
        tour = select_close_together(RANKED, 20.0)
        self.assertEqual(len(tour), len(RANKED))

    def test_empty(self) -> None:
        self.assertEqual(select_close_together_one_per_chain([], 1.0), [])


if __name__ == "__main__":
    unittest.main()
