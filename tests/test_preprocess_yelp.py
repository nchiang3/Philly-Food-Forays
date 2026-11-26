import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.preprocess_yelp import filter_businesses, filter_reviews


class PreprocessYelpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_jsonl(self, name: str, records: list[dict]) -> Path:
        path = self.root / name
        path.write_text(
            "".join(json.dumps(record) + "\n" for record in records),
            encoding="utf-8",
        )
        return path

    def test_filters_philadelphia_restaurants(self) -> None:
        source = self.write_jsonl(
            "businesses.json",
            [
                {
                    "business_id": "keep",
                    "name": "Good Food",
                    "city": "Philadelphia",
                    "state": "PA",
                    "categories": "Sandwiches, Restaurants",
                    "latitude": 39.95,
                    "longitude": -75.16,
                    "is_open": 1,
                },
                {
                    "business_id": "wrong-city",
                    "city": "Pittsburgh",
                    "state": "PA",
                    "categories": "Restaurants",
                },
                {
                    "business_id": "not-food",
                    "city": "Philadelphia",
                    "state": "PA",
                    "categories": "Museums, Arts & Entertainment",
                },
                {
                    "business_id": "water-ice",
                    "name": "Local Water Ice",
                    "city": "Philadelphia",
                    "state": "PA",
                    "categories": "Shaved Ice, Desserts, Food",
                    "latitude": 39.96,
                    "longitude": -75.17,
                    "is_open": 1,
                },
            ],
        )
        output = self.root / "restaurants.csv"

        business_ids, stats = filter_businesses(
            source, output, "Philadelphia", "PA", False
        )

        self.assertEqual(business_ids, {"keep", "water-ice"})
        self.assertEqual(stats["restaurants_selected"], 2)
        with output.open(encoding="utf-8", newline="") as result:
            rows = list(csv.DictReader(result))
        self.assertEqual({row["name"] for row in rows}, {"Good Food", "Local Water Ice"})

    def test_filters_reviews_by_selected_business_id(self) -> None:
        source = self.write_jsonl(
            "reviews.json",
            [
                {"review_id": "r1", "business_id": "keep", "text": "Great"},
                {"review_id": "r2", "business_id": "skip", "text": "Fine"},
            ],
        )
        output = self.root / "reviews.jsonl"

        stats = filter_reviews(source, output, {"keep"})

        rows = [json.loads(line) for line in output.read_text().splitlines()]
        self.assertEqual(stats["reviews_selected"], 1)
        self.assertEqual(rows[0]["review_id"], "r1")


if __name__ == "__main__":
    unittest.main()
