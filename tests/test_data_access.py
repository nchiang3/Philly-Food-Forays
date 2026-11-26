import io
import json
import unittest

from src.food_tour.data_access import (
    DatasetValidationError,
    load_food_sentiment,
    load_restaurants,
    summarize_reviews,
)


class DataAccessTests(unittest.TestCase):
    def test_loads_valid_restaurant_csv(self) -> None:
        fields = [
            "business_id",
            "name",
            "city",
            "state",
            "latitude",
            "longitude",
            "stars",
            "review_count",
            "is_open",
            "categories",
        ]
        content = ",".join(fields) + "\n1,Cafe,Philadelphia,PA,1,2,4.5,10,1,Restaurants\n"
        rows = load_restaurants(io.BytesIO(content.encode()))
        self.assertEqual(rows[0]["name"], "Cafe")

    def test_rejects_missing_restaurant_columns(self) -> None:
        with self.assertRaises(DatasetValidationError):
            load_restaurants(io.BytesIO(b"business_id,name\n1,Cafe\n"))

    def test_summarizes_review_jsonl(self) -> None:
        reviews = [
            {
                "review_id": "r1",
                "business_id": "b1",
                "stars": 5,
                "text": "Excellent",
                "date": "2024-01-01",
            },
            {
                "review_id": "r2",
                "business_id": "b1",
                "stars": 4,
                "text": "Good",
                "date": "2024-01-02",
            },
        ]
        content = "".join(json.dumps(row) + "\n" for row in reviews).encode()
        summary = summarize_reviews(io.BytesIO(content))
        self.assertEqual(summary["review_count"], 2)
        self.assertEqual(summary["business_count"], 1)

    def test_loads_food_sentiment_csv(self) -> None:
        fields = [
            "business_id",
            "food",
            "matched_reviews",
            "positive_reviews",
            "neutral_reviews",
            "negative_reviews",
            "positive_share",
            "average_review_stars",
        ]
        content = ",".join(fields) + "\nb1,Hoagie,10,8,1,1,0.8,4.2\n"
        rows = load_food_sentiment(io.BytesIO(content.encode()))
        self.assertEqual(rows[0]["food"], "Hoagie")


if __name__ == "__main__":
    unittest.main()
