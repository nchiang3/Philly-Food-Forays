"""Transparent restaurant ranking that rewards quality and credible volume."""

from __future__ import annotations

import math
from datetime import time
from typing import Any

from .hours import format_day_hours, format_weekly_hours, is_open_at, is_open_during


SENTIMENT_WEIGHT = 0.45
FOOD_REVIEW_VOLUME_WEIGHT = 0.40
OVERALL_REVIEW_VOLUME_WEIGHT = 0.15
PRIOR_STRENGTH = 20
HOURS_JSON_COLUMN = "hours_json"


def rank_restaurants(
    restaurants: list[dict[str, str]],
    food_sentiment: list[dict[str, str]],
    selected_food: str,
    minimum_mentions: int,
    open_only: bool,
    visit_day: str | None = None,
    visit_start_time: time | None = None,
    visit_end_time: time | None = None,
) -> list[dict[str, Any]]:
    """Rank restaurants using Bayesian sentiment and logarithmic review volume."""
    restaurant_by_id = {row["business_id"]: row for row in restaurants}
    candidates = [
        row
        for row in food_sentiment
        if row["food"] == selected_food
        and int(row["matched_reviews"]) >= minimum_mentions
        and row["business_id"] in restaurant_by_id
        and (
            not open_only
            or restaurant_by_id[row["business_id"]].get("is_open") == "1"
        )
        and (
            visit_day is None
            or visit_start_time is None
            or (
                is_open_during(
                    restaurant_by_id[row["business_id"]].get("hours_json"),
                    visit_day,
                    visit_start_time,
                    visit_end_time,
                )
                if visit_end_time is not None
                else is_open_at(
                    restaurant_by_id[row["business_id"]].get("hours_json"),
                    visit_day,
                    visit_start_time,
                )
            )
        )
    ]
    if not candidates:
        return []

    total_positive = sum(int(row["positive_reviews"]) for row in candidates)
    total_mentions = sum(int(row["matched_reviews"]) for row in candidates)
    prior_positive_share = total_positive / total_mentions
    max_mentions = max(int(row["matched_reviews"]) for row in candidates)
    max_overall_reviews = max(
        int(restaurant_by_id[row["business_id"]]["review_count"])
        for row in candidates
    )

    ranked: list[dict[str, Any]] = []
    for sentiment in candidates:
        restaurant = restaurant_by_id[sentiment["business_id"]]
        mentions = int(sentiment["matched_reviews"])
        positive = int(sentiment["positive_reviews"])
        overall_reviews = int(restaurant["review_count"])

        adjusted_sentiment = (
            positive + PRIOR_STRENGTH * prior_positive_share
        ) / (mentions + PRIOR_STRENGTH)
        food_volume = math.log1p(mentions) / math.log1p(max_mentions)
        overall_volume = math.log1p(overall_reviews) / math.log1p(max_overall_reviews)
        score = 100 * (
            SENTIMENT_WEIGHT * adjusted_sentiment
            + FOOD_REVIEW_VOLUME_WEIGHT * food_volume
            + OVERALL_REVIEW_VOLUME_WEIGHT * overall_volume
        )

        result = {
            # Hidden in the app; links a stop back to its reviews and details.
            "business_id": restaurant["business_id"],
            "name": restaurant["name"],
            "address": restaurant["address"],
            "opening hours": format_weekly_hours(restaurant.get("hours_json")),
            "recommendation score": round(score, 1),
            "Yelp stars": float(restaurant["stars"]),
            "overall Yelp reviews": overall_reviews,
            "matching food reviews": mentions,
            "food positive sentiment": round(float(sentiment["positive_share"]), 4),
            "volume-adjusted sentiment": round(adjusted_sentiment, 4),
            "food review stars": float(sentiment["average_review_stars"]),
            "latitude": float(restaurant["latitude"]),
            "longitude": float(restaurant["longitude"]),
            # Raw Yelp hours, kept for visit-order planning; hidden in the app.
            HOURS_JSON_COLUMN: restaurant.get("hours_json"),
        }
        if visit_day is not None:
            result[f"{visit_day} hours"] = format_day_hours(
                restaurant.get("hours_json"), visit_day
            )
        ranked.append(result)

    ranked.sort(key=lambda row: row["recommendation score"], reverse=True)
    return ranked
