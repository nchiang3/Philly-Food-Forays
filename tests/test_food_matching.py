import unittest

from src.food_tour.food_matching import match_foods, normalize_text


class FoodMatchingTests(unittest.TestCase):
    def test_normalizes_case_and_punctuation(self) -> None:
        self.assertEqual(normalize_text("  Philly CHEESE-STEAK!! "), "philly cheese steak")

    def test_matches_each_supported_food(self) -> None:
        examples = {
            "Best CHEESESTEAK in town": "Philly Cheesesteak",
            "The roast pork sandwich was excellent": "Roast Pork Sandwich",
            "I ordered two hoagies": "Hoagie",
            "A warm soft pretzel": "Philadelphia Soft Pretzel",
            "Loved the tomato pie": "Tomato Pie",
            "Breakfast scrapple was crispy": "Scrapple",
            "Refreshing Italian ice": "Water Ice",
        }
        for text, expected in examples.items():
            with self.subTest(text=text):
                self.assertIn(expected, match_foods(text))

    def test_tolerates_misspellings(self) -> None:
        self.assertIn("Philly Cheesesteak", match_foods("The cheesteak was fantastic"))
        self.assertIn("Philadelphia Soft Pretzel", match_foods("Great soft pretzle"))
        self.assertIn("Water Ice", match_foods("Loved the watter ice"))

    def test_does_not_match_unrelated_food(self) -> None:
        self.assertEqual(match_foods("The pizza and salad were delicious"), [])


if __name__ == "__main__":
    unittest.main()

