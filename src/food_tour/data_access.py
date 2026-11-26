"""Validation and streaming access for user-supplied project datasets."""

from __future__ import annotations

import csv
import io
import json
from collections import Counter
from typing import Any, BinaryIO


RESTAURANT_REQUIRED_FIELDS = {
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
}

REVIEW_REQUIRED_FIELDS = {"review_id", "business_id", "stars", "text", "date"}


class DatasetValidationError(ValueError):
    """Raised when an uploaded dataset does not match the expected schema."""


def _text_reader(binary_file: BinaryIO) -> io.TextIOWrapper:
    binary_file.seek(0)
    return io.TextIOWrapper(binary_file, encoding="utf-8", newline="")


def load_restaurants(binary_file: BinaryIO) -> list[dict[str, str]]:
    """Load and validate the compact restaurant CSV."""
    text_file = _text_reader(binary_file)
    try:
        reader = csv.DictReader(text_file)
        fields = set(reader.fieldnames or [])
        missing = RESTAURANT_REQUIRED_FIELDS - fields
        if missing:
            raise DatasetValidationError(
                "Restaurant CSV is missing columns: " + ", ".join(sorted(missing))
            )
        rows = list(reader)
    finally:
        text_file.detach()
        binary_file.seek(0)

    if not rows:
        raise DatasetValidationError("Restaurant CSV contains no data rows.")
    return rows


def summarize_reviews(binary_file: BinaryIO) -> dict[str, Any]:
    """Validate a review JSONL stream without retaining review text in memory."""
    total = 0
    malformed = 0
    missing_fields = 0
    business_ids: set[str] = set()
    star_counts: Counter[str] = Counter()
    sample: list[dict[str, Any]] = []

    text_file = _text_reader(binary_file)
    try:
        for line in text_file:
            total += 1
            try:
                review = json.loads(line)
            except json.JSONDecodeError:
                malformed += 1
                continue
            if not isinstance(review, dict) or not REVIEW_REQUIRED_FIELDS.issubset(review):
                missing_fields += 1
                continue

            business_ids.add(str(review["business_id"]))
            star_counts[str(review["stars"])] += 1
            if len(sample) < 5:
                sample.append(
                    {
                        "business_id": review["business_id"],
                        "stars": review["stars"],
                        "date": review["date"],
                        "text_preview": str(review["text"])[:160],
                    }
                )
    finally:
        text_file.detach()
        binary_file.seek(0)

    if total == 0:
        raise DatasetValidationError("Review JSONL contains no records.")
    if malformed or missing_fields:
        raise DatasetValidationError(
            f"Review JSONL failed validation: {malformed} malformed lines and "
            f"{missing_fields} records missing required fields."
        )

    return {
        "review_count": total,
        "business_count": len(business_ids),
        "star_counts": dict(sorted(star_counts.items())),
        "sample": sample,
    }


def category_options(restaurants: list[dict[str, str]]) -> list[str]:
    """Return normalized Yelp categories for UI filtering."""
    categories: set[str] = set()
    for restaurant in restaurants:
        value = restaurant.get("categories", "")
        categories.update(part.strip() for part in value.split(",") if part.strip())
    categories.discard("Restaurants")
    return sorted(categories, key=str.casefold)

