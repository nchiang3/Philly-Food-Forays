import unittest
from datetime import time
from urllib.parse import parse_qs, urlparse

from src.food_tour.schedule import plan_visit_order
from src.food_tour.stop_details import (
    INFO,
    WARNING,
    PlannedVisit,
    full_address,
    google_maps_place_url,
    planned_visits,
    timing_notes,
    weekly_hours,
    why_picked,
)


def stop(name: str, monday_hours: str | None, **extra) -> dict:
    hours = None if monday_hours is None else f'{{"Monday": "{monday_hours}"}}'
    return {"name": name, "hours_json": hours, **extra}


def notes_for(row, visit, scheduled=True, position=1, minutes=45, **extra):
    return timing_notes(
        row,
        visit,
        scheduled=scheduled,
        position=position,
        weekday="Monday",
        start_time=time(12, 0),
        end_time=time(17, 0),
        minutes_per_stop=minutes,
        **extra,
    )


class AddressTests(unittest.TestCase):
    def test_full_address_adds_city_state_and_zip(self) -> None:
        row = {"address": "1237 E Passyunk Ave"}
        restaurant = {"city": "Philadelphia", "state": "PA", "postal_code": "19147"}
        self.assertEqual(
            full_address(row, restaurant),
            "1237 E Passyunk Ave, Philadelphia, PA 19147",
        )

    def test_full_address_with_missing_parts(self) -> None:
        self.assertEqual(full_address({"address": ""}, {"city": "Philadelphia"}), "Philadelphia")
        self.assertEqual(full_address({}, None), "")

    def test_google_maps_place_url_searches_name_and_address(self) -> None:
        url = google_maps_place_url({"name": "Pat's"}, "1237 E Passyunk Ave")
        query = parse_qs(urlparse(url).query)
        self.assertEqual(query["api"], ["1"])
        self.assertEqual(query["query"], ["Pat's 1237 E Passyunk Ave"])

    def test_google_maps_place_url_falls_back_to_coordinates(self) -> None:
        url = google_maps_place_url({"latitude": 39.95, "longitude": -75.16})
        self.assertIn("39.950000%2C-75.160000", url)


class WeeklyHoursTests(unittest.TestCase):
    def test_lists_all_seven_days(self) -> None:
        hours = weekly_hours('{"Monday": "11:0-14:0"}')
        self.assertEqual(len(hours), 7)
        self.assertEqual(hours[0], ("Monday", "11:00 AM–2:00 PM"))
        self.assertEqual(hours[1], ("Tuesday", "Closed / unavailable"))


class PlannedVisitsTests(unittest.TestCase):
    def test_matches_the_visit_plan(self) -> None:
        stops = [
            stop("Late", "15:0-22:0"),
            stop("Open", "10:0-22:0"),
            stop("Lunch", "11:0-14:0"),
        ]
        plan = plan_visit_order(stops, "Monday", time(12, 0), time(17, 0), 45)
        visits = planned_visits(plan, "Monday", time(12, 0), time(17, 0), 45)
        self.assertEqual([row["name"] for row in plan], ["Lunch", "Open", "Late"])
        self.assertEqual(
            visits,
            [
                PlannedVisit(720, 840, 0),
                PlannedVisit(765, 1320, 0),
                # Open finishes at 1:30 PM; Late opens at 3 PM.
                PlannedVisit(900, 1320, 90),
            ],
        )

    def test_unreachable_stop_is_none(self) -> None:
        visits = planned_visits(
            [stop("Evening", "18:0-22:0")], "Monday", time(12, 0), time(17, 0), 45
        )
        self.assertEqual(visits, [None])


class TimingNotesTests(unittest.TestCase):
    def test_open_on_arrival(self) -> None:
        notes = notes_for(stop("Open", "10:0-22:0"), PlannedVisit(720, 1320, 0))
        self.assertEqual([note.level for note in notes], [INFO])
        self.assertIn("open until 10:00 PM", notes[0].text)

    def test_closed_at_start_is_moved_later_and_waits(self) -> None:
        notes = notes_for(
            stop("Late", "15:0-22:0"), PlannedVisit(900, 1320, 90), position=3
        )
        texts = " ".join(note.text for note in notes)
        self.assertIn("Closed when your tour starts at 12:00 PM", texts)
        self.assertIn("placed later in the route", texts)
        self.assertIn("wait about 90 minutes", texts)
        self.assertNotIn(WARNING, [note.level for note in notes])

    def test_first_stop_closed_at_start(self) -> None:
        notes = notes_for(stop("Late", "13:0-22:0"), PlannedVisit(780, 1320, 60))
        self.assertIn("tour starts by waiting for it", notes[0].text)

    def test_closes_before_the_stay_ends(self) -> None:
        notes = notes_for(stop("Lunch", "11:0-14:0"), PlannedVisit(820, 840, 0))
        warning = [note for note in notes if note.level == WARNING]
        self.assertEqual(len(warning), 1)
        self.assertIn("Closes at 2:00 PM, only 20 minutes after", warning[0].text)

    def test_stop_that_does_not_fit_and_closes_early(self) -> None:
        notes = notes_for(stop("Lunch", "11:0-14:0"), None, scheduled=False)
        self.assertEqual(notes[0].level, WARNING)
        self.assertIn("Not open when the tour would get there", notes[0].text)
        self.assertIn("it's open 11:00 AM–2:00 PM, and it closes at 2:00 PM", notes[0].text)
        self.assertIn("left off the map", notes[0].text)

    def test_stop_that_does_not_fit_before_window_ends(self) -> None:
        notes = notes_for(stop("Open", "10:0-22:0"), None, scheduled=False)
        self.assertIn("Doesn't fit the tour plan", notes[0].text)
        self.assertIn("it's open 10:00 AM–10:00 PM, but", notes[0].text)

    def test_open_24_hours_wording(self) -> None:
        notes = notes_for(stop("Always", "0:0-0:0"), PlannedVisit(720, 1440, 0))
        self.assertEqual(
            notes[0].text,
            "Open 24 hours on Monday. You arrive around 12:00 PM, and it's "
            "open through the rest of your window.",
        )

    def test_opening_time_is_the_real_opening_not_the_arrival(self) -> None:
        # Opens at 1 PM, but the tour only gets there at 1:30 PM.
        notes = notes_for(
            stop("Late", "13:0-22:0"), PlannedVisit(810, 1320, 0), position=2
        )
        self.assertIn("It opens at 1:00 PM, so it's placed later", notes[0].text)
        self.assertEqual(len(notes), 2)
        self.assertIn("Open 1:00 PM–10:00 PM on Monday", notes[1].text)

    def test_permanently_closed_business(self) -> None:
        notes = notes_for(
            stop("Gone", "10:0-22:0"),
            PlannedVisit(720, 1320, 0),
            restaurant={"is_open": "0"},
        )
        self.assertEqual(notes[0].level, WARNING)
        self.assertIn("closed for good", notes[0].text)

    def test_without_visit_window_lists_closed_days(self) -> None:
        notes = timing_notes(
            stop("Weekdays", "10:0-22:0"),
            None,
            scheduled=True,
            position=1,
            weekday=None,
            start_time=None,
            end_time=None,
            minutes_per_stop=None,
        )
        self.assertIn("Closed on Tuesday, Wednesday", notes[0].text)
        self.assertIn("and Sunday", notes[0].text)
        self.assertIn("No visit day and time", notes[-1].text)

    def test_without_visit_window_or_hours(self) -> None:
        notes = timing_notes(
            stop("Unknown", None),
            None,
            scheduled=True,
            position=1,
            weekday=None,
            start_time=None,
            end_time=None,
            minutes_per_stop=None,
        )
        self.assertEqual([note.level for note in notes], [WARNING])
        self.assertIn("no opening hours", notes[0].text)


def ranked(name: str, mentions: int, share: float, **extra) -> dict:
    return {
        "name": name,
        "recommendation score": 80.0,
        "matching food reviews": mentions,
        "food positive sentiment": share,
        "food review stars": 4.25,
        "Yelp stars": 4.5,
        "overall Yelp reviews": 1200,
        **extra,
    }


class WhyPickedTests(unittest.TestCase):
    def test_reasons_cover_rank_food_reviews_and_stars(self) -> None:
        best = ranked("A", 300, 0.82)
        tour = [best, ranked("B", 100, 0.9)]
        reasons = why_picked(best, 2, 40, "Hoagie", tour)
        self.assertEqual(
            reasons[0],
            "Ranked #2 of 40 Hoagie spots that match your filters, with a "
            "recommendation score of 80.0 out of 100.",
        )
        self.assertIn("300 reviews mention its Hoagie", reasons[1])
        self.assertIn("82% of those", reasons[1])
        self.assertIn("the most of any stop on this tour", reasons[1])
        self.assertIn("4.5 Yelp stars from 1,200 reviews", reasons[2])

    def test_most_positive_on_tour(self) -> None:
        row = ranked("B", 100, 0.9)
        reasons = why_picked(row, 1, 5, "Hoagie", [ranked("A", 300, 0.8), row])
        self.assertIn("the most positive of any stop", reasons[1])

    def test_chain_and_distance_reasons(self) -> None:
        row = ranked(
            "Wawa", 50, 0.7, **{"chain locations": 4, "miles from start": 0.4}
        )
        reasons = why_picked(row, 3, 9, "Hoagie", [row], "City Hall")
        self.assertIn("Wawa has 4 locations", reasons[-2])
        self.assertEqual(
            reasons[-1], "It's 0.40 miles (straight line) from City Hall."
        )


if __name__ == "__main__":
    unittest.main()
