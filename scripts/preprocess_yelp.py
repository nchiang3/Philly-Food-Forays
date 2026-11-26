#!/usr/bin/env python3
"""Create Philadelphia restaurant and review datasets from Yelp JSONL files.

The Yelp Open Dataset files are newline-delimited JSON. This script processes
them one record at a time so the multi-gigabyte review file never needs to be
loaded fully into memory.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any, Iterable


BUSINESS_FIELDS = (
    "business_id",
    "name",
    "address",
    "city",
    "state",
    "postal_code",
    "latitude",
    "longitude",
    "stars",
    "review_count",
    "is_open",
    "categories",
    "hours_json",
    "attributes_json",
)

REVIEW_FIELDS = (
    "review_id",
    "business_id",
    "stars",
    "useful",
    "funny",
    "cool",
    "text",
    "date",
)

# Yelp does not label every food-serving business as a Restaurant. These
# additional categories retain bakeries, water-ice shops, pretzel shops, delis,
# and similar specialty businesses needed for the seven signature foods.
FOOD_BUSINESS_CATEGORIES = {
    "bakeries",
    "delis",
    "desserts",
    "food stands",
    "ice cream & frozen yogurt",
    "pizza",
    "pretzels",
    "restaurants",
    "sandwiches",
    "shaved ice",
}


def iter_jsonl(path: Path) -> Iterable[tuple[int, dict[str, Any] | None]]:
    """Yield line numbers and decoded objects, returning None for bad lines."""
    with path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            try:
                value = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                yield line_number, None
                continue
            yield line_number, value if isinstance(value, dict) else None


def category_tokens(value: Any) -> set[str]:
    """Normalize Yelp's comma-separated categories into lowercase tokens."""
    if not isinstance(value, str):
        return set()
    return {part.strip().casefold() for part in value.split(",") if part.strip()}


def is_target_restaurant(
    business: dict[str, Any], city: str, state: str | None, open_only: bool
) -> bool:
    """Return whether a business matches the requested restaurant scope."""
    if str(business.get("city", "")).strip().casefold() != city.casefold():
        return False
    if state and str(business.get("state", "")).strip().casefold() != state.casefold():
        return False
    if not FOOD_BUSINESS_CATEGORIES.intersection(
        category_tokens(business.get("categories"))
    ):
        return False
    return not open_only or business.get("is_open") == 1


def prepare_business_row(business: dict[str, Any]) -> dict[str, Any]:
    """Select stable business fields and serialize nested values."""
    row = {field: business.get(field) for field in BUSINESS_FIELDS}
    row["hours_json"] = json.dumps(
        business.get("hours"), ensure_ascii=False, sort_keys=True
    )
    row["attributes_json"] = json.dumps(
        business.get("attributes"), ensure_ascii=False, sort_keys=True
    )
    return row


def filter_businesses(
    source_path: Path,
    output_path: Path,
    city: str,
    state: str | None,
    open_only: bool,
) -> tuple[set[str], dict[str, int]]:
    """Write matching restaurant records and return their business IDs."""
    business_ids: set[str] = set()
    stats = {
        "business_records_read": 0,
        "malformed_business_records": 0,
        "restaurants_selected": 0,
        "restaurants_missing_coordinates": 0,
    }

    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=BUSINESS_FIELDS)
        writer.writeheader()
        for _, business in iter_jsonl(source_path):
            stats["business_records_read"] += 1
            if business is None:
                stats["malformed_business_records"] += 1
                continue
            if not is_target_restaurant(business, city, state, open_only):
                continue

            business_id = business.get("business_id")
            if not isinstance(business_id, str) or not business_id:
                stats["malformed_business_records"] += 1
                continue
            if business.get("latitude") is None or business.get("longitude") is None:
                stats["restaurants_missing_coordinates"] += 1

            writer.writerow(prepare_business_row(business))
            business_ids.add(business_id)
            stats["restaurants_selected"] += 1

    os.replace(temp_path, output_path)
    return business_ids, stats


def filter_reviews(
    source_path: Path, output_path: Path, business_ids: set[str]
) -> dict[str, int]:
    """Write reviews belonging to selected restaurants as JSONL."""
    stats = {
        "review_records_read": 0,
        "malformed_review_records": 0,
        "reviews_selected": 0,
    }
    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as target:
        for _, review in iter_jsonl(source_path):
            stats["review_records_read"] += 1
            if review is None:
                stats["malformed_review_records"] += 1
                continue
            if review.get("business_id") not in business_ids:
                continue
            selected = {field: review.get(field) for field in REVIEW_FIELDS}
            target.write(json.dumps(selected, ensure_ascii=False) + "\n")
            stats["reviews_selected"] += 1

    os.replace(temp_path, output_path)
    return stats


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--businesses", type=Path, required=True)
    parser.add_argument("--reviews", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--city", default="Philadelphia")
    parser.add_argument("--state", default="PA")
    parser.add_argument(
        "--open-only", action="store_true", help="Exclude businesses marked closed."
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if not args.businesses.is_file():
        raise SystemExit(f"Business file not found: {args.businesses}")
    if args.reviews is not None and not args.reviews.is_file():
        raise SystemExit(f"Review file not found: {args.reviews}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    businesses_output = args.output_dir / "philadelphia_restaurants.csv"
    reviews_output = args.output_dir / "philadelphia_reviews.jsonl"
    summary_output = args.output_dir / "preprocessing_summary.json"

    business_ids, summary = filter_businesses(
        args.businesses, businesses_output, args.city, args.state, args.open_only
    )
    if not business_ids:
        raise SystemExit("No matching restaurants found; check city/state filters.")

    if args.reviews is not None:
        summary.update(filter_reviews(args.reviews, reviews_output, business_ids))

    summary.update(
        {
            "city": args.city,
            "state": args.state,
            "open_only": args.open_only,
            "business_output_bytes": businesses_output.stat().st_size,
            "review_output_bytes": (
                reviews_output.stat().st_size if args.reviews is not None else 0
            ),
        }
    )
    summary_output.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
