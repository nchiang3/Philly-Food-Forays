import unittest
from datetime import time

from src.food_tour.schedule import (
    ARRIVAL_COLUMN,
    NOT_IN_WINDOW,
    VISIT_ORDER_COLUMN,
    earliest_visit,
    plan_visit_order,
    unscheduled_message,
)


def stop(name: str, monday_hours: str | None) -> dict:
    hours = None if monday_hours is None else f'{{"Monday": "{monday_hours}"}}'
    return {"name": name, "hours_json": hours}


def names(plan: list[dict]) -> list[str]:
    return [row["name"] for row in plan]


class EarliestVisitTests(unittest.TestCase):
    def test_open_now_and_opening_later(self) -> None:
        hours = '{"Monday": "11:0-14:0,17:0-22:0"}'
        self.assertEqual(earliest_visit(hours, "Monday", 12 * 60, 20 * 60), (720, 840))
        self.assertEqual(
            earliest_visit(hours, "Monday", 15 * 60, 20 * 60), (1020, 1320)
        )

    def test_none_when_it_opens_after_the_window(self) -> None:
        hours = '{"Monday": "18:0-22:0"}'
        self.assertIsNone(earliest_visit(hours, "Monday", 12 * 60, 17 * 60))

    def test_none_without_hours(self) -> None:
        self.assertIsNone(earliest_visit(None, "Monday", 12 * 60, 17 * 60))


class PlanVisitOrderTests(unittest.TestCase):
    def test_open_at_start_first_and_later_openings_after(self) -> None:
        # Ranked best-first: the top spot opens latest.
        stops = [
            stop("Dinner Spot", "16:0-22:0"),
            stop("Lunch Counter", "11:0-15:0"),
            stop("Afternoon Cafe", "13:0-18:0"),
        ]
        plan = plan_visit_order(stops, "Monday", time(12, 0), time(17, 0), 60)
        self.assertEqual(
            names(plan), ["Lunch Counter", "Afternoon Cafe", "Dinner Spot"]
        )
        self.assertEqual(
            [row[ARRIVAL_COLUMN] for row in plan],
            ["12:00 PM", "1:00 PM", "4:00 PM"],
        )
        self.assertEqual([row[VISIT_ORDER_COLUMN] for row in plan], [1, 2, 3])

    def test_waits_for_a_later_opening_when_nothing_else_is_open(self) -> None:
        stops = [stop("Late Opener", "14:30-20:0")]
        plan = plan_visit_order(stops, "Monday", time(12, 0), time(17, 0))
        self.assertEqual(plan[0][ARRIVAL_COLUMN], "2:30 PM")

    def test_closing_soonest_goes_first_then_rank(self) -> None:
        stops = [
            stop("All Day", "0:0-0:0"),
            stop("Closes Soon", "9:0-13:0"),
            stop("Also All Day", "0:0-0:0"),
        ]
        plan = plan_visit_order(stops, "Monday", time(12, 0), time(17, 0), 30)
        self.assertEqual(names(plan), ["Closes Soon", "All Day", "Also All Day"])

    def test_stop_that_closes_before_it_can_be_reached_is_listed_last(self) -> None:
        stops = [
            stop("Long Lunch", "11:0-17:0"),
            stop("Short Window", "11:0-12:30"),
            stop("Another", "11:0-17:0"),
        ]
        # Short Window closes soonest, so it goes first and fits.
        plan = plan_visit_order(stops, "Monday", time(12, 0), time(17, 0), 60)
        self.assertEqual(names(plan)[0], "Short Window")

        stops = [stop("Long Lunch", "11:0-17:0"), stop("Gone", "11:0-12:0")]
        plan = plan_visit_order(stops, "Monday", time(12, 0), time(17, 0), 60)
        self.assertEqual(names(plan), ["Long Lunch", "Gone"])
        self.assertIsNone(plan[1][VISIT_ORDER_COLUMN])
        self.assertEqual(plan[1][ARRIVAL_COLUMN], NOT_IN_WINDOW)

    def test_stops_past_the_window_end_do_not_fit(self) -> None:
        stops = [stop(f"Spot {i}", "0:0-0:0") for i in range(4)]
        plan = plan_visit_order(stops, "Monday", time(12, 0), time(14, 0), 60)
        self.assertEqual([row[VISIT_ORDER_COLUMN] for row in plan], [1, 2, None, None])
        self.assertIn("2 stops don't fit", unscheduled_message(plan))

    def test_overnight_hours_from_previous_day_count(self) -> None:
        late_night = {"name": "Night Owl", "hours_json": '{"Sunday": "20:0-3:0"}'}
        plan = plan_visit_order([late_night], "Monday", time(1, 0), time(2, 0))
        self.assertEqual(plan[0][ARRIVAL_COLUMN], "1:00 AM")

    def test_keeps_other_columns_and_handles_empty_input(self) -> None:
        row = {**stop("Spot", "9:0-17:0"), "recommendation score": 88.0}
        plan = plan_visit_order([row], "Monday", time(12, 0), time(13, 0))
        self.assertEqual(plan[0]["recommendation score"], 88.0)
        self.assertEqual(plan_visit_order([], "Monday", time(12, 0), time(13, 0)), [])
        self.assertIsNone(unscheduled_message(plan))

    def test_rejects_bad_window_and_pace(self) -> None:
        with self.assertRaises(ValueError):
            plan_visit_order([], "Monday", time(17, 0), time(12, 0))
        with self.assertRaises(ValueError):
            plan_visit_order([], "Monday", time(12, 0), time(17, 0), 0)


if __name__ == "__main__":
    unittest.main()
