#!/usr/bin/env python3
"""Aggregate predicted sentiment by restaurant and signature food."""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import joblib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.preprocess_yelp import iter_jsonl
from src.food_tour.food_matching import extract_food_snippets


OUTPUT_FIELDS = (
    "business_id",
    "food",
    "matched_reviews",
    "positive_reviews",
    "neutral_reviews",
    "negative_reviews",
    "positive_share",
    "average_review_stars",
)


def update_aggregates(
    model: Any,
    batch: list[tuple[str, str, float, str]],
    aggregates: dict[tuple[str, str], dict[str, float]],
) -> int:
    if not batch:
        return 0
    predictions = model.predict([item[3] for item in batch])
    associations = 0
    for (business_id, food, stars, _), sentiment in zip(batch, predictions):
        values = aggregates[(business_id, food)]
        values["matched_reviews"] += 1
        values[f"{sentiment}_reviews"] += 1
        values["star_total"] += stars
        associations += 1
    return associations


def build_summary(
    review_path: Path, model: Any, batch_size: int
) -> tuple[dict[tuple[str, str], dict[str, float]], dict[str, int]]:
    aggregates: dict[tuple[str, str], dict[str, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    batch: list[tuple[str, str, float, str]] = []
    stats = {"reviews_read": 0, "reviews_matching_food": 0, "food_associations": 0}

    for _, review in iter_jsonl(review_path):
        stats["reviews_read"] += 1
        if review is None:
            continue
        text = str(review.get("text", ""))
        snippets = extract_food_snippets(text)
        if not snippets:
            continue
        try:
            business_id = str(review["business_id"])
            stars = float(review["stars"])
        except (KeyError, TypeError, ValueError):
            continue
        stats["reviews_matching_food"] += 1
        batch.extend(
            (business_id, food, stars, snippet)
            for food, snippet in snippets.items()
        )
        if len(batch) >= batch_size:
            stats["food_associations"] += update_aggregates(model, batch, aggregates)
            batch.clear()

    stats["food_associations"] += update_aggregates(model, batch, aggregates)
    return aggregates, stats


def write_summary(
    output_path: Path, aggregates: dict[tuple[str, str], dict[str, float]]
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        for (business_id, food), values in sorted(aggregates.items()):
            total = int(values["matched_reviews"])
            writer.writerow(
                {
                    "business_id": business_id,
                    "food": food,
                    "matched_reviews": total,
                    "positive_reviews": int(values["positive_reviews"]),
                    "neutral_reviews": int(values["neutral_reviews"]),
                    "negative_reviews": int(values["negative_reviews"]),
                    "positive_share": round(values["positive_reviews"] / total, 4),
                    "average_review_stars": round(values["star_total"] / total, 3),
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument("--model", type=Path, default=Path("models/sentiment_model.joblib"))
    parser.add_argument(
        "--output", type=Path, default=Path("data/processed/food_sentiment.csv")
    )
    parser.add_argument("--batch-size", type=int, default=2_000)
    args = parser.parse_args()

    if not args.reviews.is_file():
        raise SystemExit(f"Review file not found: {args.reviews}")
    if not args.model.is_file():
        raise SystemExit(f"Model file not found: {args.model}")

    model = joblib.load(args.model)
    aggregates, stats = build_summary(args.reviews, model, args.batch_size)
    write_summary(args.output, aggregates)
    print({**stats, "summary_rows": len(aggregates), "output": str(args.output)})


if __name__ == "__main__":
    main()
