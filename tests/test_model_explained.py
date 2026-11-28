import unittest

from src.food_tour.model_explained import (
    BIBTEX,
    DECISIONS,
    breakdown_html,
    data_source_html,
    decisions_html,
    glance_html,
    prior_positive_share,
    ranking_intro_html,
    ranking_terms_html,
    score_components,
)
from src.food_tour.ranking import rank_restaurants


def restaurant(business_id: str, name: str, review_count: int) -> dict[str, str]:
    return {
        "business_id": business_id,
        "name": name,
        "address": "1 Market St",
        "is_open": "1",
        "stars": "4.0",
        "review_count": str(review_count),
        "latitude": "39.95",
        "longitude": "-75.16",
        "hours_json": "",
    }


def sentiment(business_id: str, matched: int, positive: int) -> dict[str, str]:
    return {
        "business_id": business_id,
        "food": "Hoagie",
        "matched_reviews": str(matched),
        "positive_reviews": str(positive),
        "positive_share": str(positive / matched),
        "average_review_stars": "4.0",
    }


RANKED = rank_restaurants(
    [
        restaurant("a", "Big & Busy", 2000),
        restaurant("b", "Small <Shop>", 40),
        restaurant("c", "Middle", 300),
    ],
    [sentiment("a", 200, 150), sentiment("b", 3, 3), sentiment("c", 40, 30)],
    "Hoagie",
    1,
    open_only=True,
)


class ScoreComponentTests(unittest.TestCase):
    def test_parts_add_up_to_the_score(self) -> None:
        for item in score_components(RANKED):
            self.assertAlmostEqual(sum(item["parts"].values()), item["score"], delta=0.06)

    def test_largest_pool_member_gets_full_volume_points(self) -> None:
        top = next(item for item in score_components(RANKED) if item["business_id"] == "a")
        self.assertAlmostEqual(top["parts"]["food-volume"], 40.0)
        self.assertAlmostEqual(top["parts"]["overall-volume"], 15.0)

    def test_prior_is_the_pooled_positive_share(self) -> None:
        self.assertAlmostEqual(prior_positive_share(RANKED), 183 / 243, places=3)

    def test_empty_inputs(self) -> None:
        self.assertEqual(score_components([]), [])
        self.assertIsNone(prior_positive_share([]))
        self.assertEqual(breakdown_html([], "Hoagie"), "")


class ContentTests(unittest.TestCase):
    def test_data_source_names_dataset_and_snapshot_date(self) -> None:
        html = data_source_html()
        self.assertIn("Yelp Open Dataset", html)
        self.assertIn("January 19, 2022", html)
        self.assertIn("2022-01-19", BIBTEX)

    def test_weights_come_from_the_ranking_module(self) -> None:
        html = ranking_intro_html()
        for label in ("45% Shrunk food sentiment", "40% Food review volume", "15% Overall Yelp volume"):
            self.assertIn(label, html)
        self.assertIn("<i>k</i> = 20", ranking_terms_html(0.8, "Hoagie"))
        self.assertIn("about 80%", ranking_terms_html(0.8, "Hoagie"))

    def test_names_are_escaped(self) -> None:
        html = breakdown_html(score_components(RANKED), "Hoagie")
        self.assertIn("Small &lt;Shop&gt;", html)
        self.assertNotIn("<Shop>", html)

    def test_glance_and_decisions_render(self) -> None:
        self.assertIn("6,159", glance_html(6159, 5994, 59832))
        html = decisions_html()
        self.assertEqual(html.count('class="mx-decision"'), len(DECISIONS))
        self.assertIn("without an API", html)


if __name__ == "__main__":
    unittest.main()
