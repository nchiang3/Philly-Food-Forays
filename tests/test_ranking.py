import unittest
from datetime import time

from src.food_tour.ranking import rank_restaurants


class RankingTests(unittest.TestCase):
    def test_review_volume_outweighs_tiny_perfect_sample(self) -> None:
        restaurants = [
            {
                "business_id": "tiny",
                "name": "Tiny Sample",
                "address": "1 A St",
                "is_open": "1",
                "stars": "5.0",
                "review_count": "10",
                "latitude": "1",
                "longitude": "2",
                "hours_json": '{"Monday": "9:0-17:0"}',
            },
            {
                "business_id": "popular",
                "name": "Popular Shop",
                "address": "2 B St",
                "is_open": "1",
                "stars": "4.5",
                "review_count": "2500",
                "latitude": "1",
                "longitude": "2",
                "hours_json": '{"Monday": "9:0-17:0"}',
            },
        ]
        sentiment = [
            {
                "business_id": "tiny",
                "food": "Philly Cheesesteak",
                "matched_reviews": "5",
                "positive_reviews": "5",
                "positive_share": "1.0",
                "average_review_stars": "5.0",
            },
            {
                "business_id": "popular",
                "food": "Philly Cheesesteak",
                "matched_reviews": "500",
                "positive_reviews": "375",
                "positive_share": "0.75",
                "average_review_stars": "4.3",
            },
        ]

        ranked = rank_restaurants(
            restaurants, sentiment, "Philly Cheesesteak", 1, True
        )

        self.assertEqual(ranked[0]["name"], "Popular Shop")

    def test_filters_for_planned_visit_time(self) -> None:
        restaurants = [
            {
                "business_id": "lunch",
                "name": "Lunch Shop",
                "address": "1 A St",
                "is_open": "1",
                "stars": "4.5",
                "review_count": "100",
                "latitude": "1",
                "longitude": "2",
                "hours_json": '{"Monday": "9:0-17:0"}',
            },
            {
                "business_id": "dinner",
                "name": "Dinner Shop",
                "address": "2 B St",
                "is_open": "1",
                "stars": "4.5",
                "review_count": "100",
                "latitude": "1",
                "longitude": "2",
                "hours_json": '{"Monday": "17:0-23:0"}',
            },
        ]
        sentiment = [
            {
                "business_id": business_id,
                "food": "Hoagie",
                "matched_reviews": "20",
                "positive_reviews": "16",
                "positive_share": "0.8",
                "average_review_stars": "4.2",
            }
            for business_id in ("lunch", "dinner")
        ]

        ranked = rank_restaurants(
            restaurants,
            sentiment,
            "Hoagie",
            1,
            True,
            "Monday",
            time(12, 0),
        )

        self.assertEqual([row["name"] for row in ranked], ["Lunch Shop"])
        self.assertEqual(ranked[0]["Monday hours"], "9:00 AM–5:00 PM")


if __name__ == "__main__":
    unittest.main()
