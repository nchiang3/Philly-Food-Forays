import unittest
from datetime import time

from src.food_tour.hours import (
    format_day_hours,
    format_weekly_hours,
    is_open_at,
)


class HoursTests(unittest.TestCase):
    def test_formats_weekly_hours(self) -> None:
        hours = '{"Monday": "9:0-17:30", "Tuesday": "0:0-0:0"}'
        self.assertEqual(format_day_hours(hours, "Monday"), "9:00 AM–5:30 PM")
        self.assertEqual(
            format_weekly_hours(hours),
            "Mon 9:00 AM–5:30 PM; Tue Open 24 hours",
        )

    def test_checks_regular_and_overnight_hours(self) -> None:
        hours = '{"Monday": "16:0-2:0"}'
        self.assertTrue(is_open_at(hours, "Monday", time(18, 0)))
        self.assertTrue(is_open_at(hours, "Tuesday", time(1, 0)))
        self.assertFalse(is_open_at(hours, "Tuesday", time(3, 0)))

    def test_missing_hours_are_not_treated_as_open(self) -> None:
        self.assertFalse(is_open_at("{}", "Monday", time(12, 0)))


if __name__ == "__main__":
    unittest.main()
