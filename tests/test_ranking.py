import unittest

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


if __name__ == "__main__":
    unittest.main()
