import io
import json
import unittest

from src.food_tour.review_highlights import (
    collect_food_reviews,
    common_themes,
    summarize_food_reviews,
)


def review_file(reviews: list[dict]) -> io.BytesIO:
    lines = [json.dumps(review) for review in reviews] + ["not json"]
    return io.BytesIO("\n".join(lines).encode("utf-8"))


def review(business_id: str, stars: int, text: str, useful: int = 0, date: str = "2020-01-01 12:00:00") -> dict:
    return {
        "review_id": f"{business_id}-{stars}-{len(text)}",
        "business_id": business_id,
        "stars": stars,
        "useful": useful,
        "text": text,
        "date": date,
    }


REVIEWS = [
    review("pats", 5, "Great service. The cheesesteak had crispy bread and juicy onions!", useful=4),
    review("pats", 5, "Loved the cheesesteak with juicy onions and melted whiz on soft bread."),
    review("pats", 4, "The cheesesteak bread was crispy and the onions were juicy."),
    review("pats", 1, "The cheesesteak was cold and the bread was soggy and stale today."),
    review("pats", 5, "No food mention here, just a nice patio."),
    review("genos", 5, "Best cheesesteak in town with juicy onions on fresh bread."),
    review("other", 5, "This cheesesteak should never be collected at all here."),
]


class CollectFoodReviewsTests(unittest.TestCase):
    def test_keeps_only_requested_businesses_that_mention_the_food(self) -> None:
        source = review_file(REVIEWS)
        found = collect_food_reviews(source, ["pats", "missing"], "Philly Cheesesteak")
        self.assertEqual(set(found), {"pats", "missing"})
        self.assertEqual(len(found["pats"]), 4)
        self.assertEqual(found["missing"], [])
        first = found["pats"][0]
        self.assertEqual(first["stars"], 5.0)
        self.assertEqual(first["useful"], 4)
        # Only the sentence mentioning the food is kept.
        self.assertNotIn("Great service", first["snippet"])
        self.assertEqual(source.tell(), 0)

    def test_caps_reviews_per_business_keeping_recent_ones(self) -> None:
        reviews = [
            review("pats", 5, "Good cheesesteak.", date=f"20{year}-01-01")
            for year in range(10, 20)
        ]
        found = collect_food_reviews(
            review_file(reviews), ["pats"], "Philly Cheesesteak", max_per_business=3
        )
        self.assertEqual(
            [item["date"] for item in found["pats"]],
            ["2019-01-01", "2018-01-01", "2017-01-01"],
        )

    def test_no_businesses(self) -> None:
        self.assertEqual(collect_food_reviews(review_file(REVIEWS), [], "Hoagie"), {})


class SummarizeFoodReviewsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reviews = collect_food_reviews(
            review_file(REVIEWS), ["pats"], "Philly Cheesesteak"
        )["pats"]

    def test_common_themes_count_reviews_not_words(self) -> None:
        themes = dict(common_themes(self.reviews))
        self.assertEqual(themes["bread"], 4)
        self.assertEqual(themes["juicy"], 3)
        self.assertNotIn("cheesesteak", themes)
        self.assertNotIn("the", themes)

    def test_summary_quotes_praise_and_critique(self) -> None:
        summary = summarize_food_reviews(self.reviews, "Philly Cheesesteak")
        self.assertEqual(summary["review_count"], 4)
        self.assertAlmostEqual(summary["positive_share"], 0.75)
        self.assertTrue(summary["praise"])
        self.assertLessEqual(len(summary["praise"]), 3)
        for quote in summary["praise"]:
            self.assertGreaterEqual(quote["stars"], 4)
            self.assertIn("cheesesteak", quote["text"].lower())
        self.assertEqual(len(summary["critiques"]), 1)
        self.assertIn("soggy", summary["critiques"][0]["text"])
        self.assertEqual(summary["critiques"][0]["date"], "2020-01-01")

    def test_praise_quotes_are_not_near_duplicates(self) -> None:
        summary = summarize_food_reviews(self.reviews, "Philly Cheesesteak")
        texts = [quote["text"] for quote in summary["praise"]]
        self.assertEqual(len(texts), len(set(texts)))

    def test_empty(self) -> None:
        summary = summarize_food_reviews([], "Hoagie")
        self.assertEqual(summary["review_count"], 0)
        self.assertIsNone(summary["positive_share"])
        self.assertEqual(summary["praise"], [])


if __name__ == "__main__":
    unittest.main()
