#!/usr/bin/env python3
"""Train a small TF-IDF and logistic-regression sentiment classifier."""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.preprocess_yelp import iter_jsonl


LABELS = ("negative", "neutral", "positive")


def star_to_sentiment(stars: float) -> str:
    """Use Yelp stars as transparent proxy labels for review sentiment."""
    if stars <= 2:
        return "negative"
    if stars == 3:
        return "neutral"
    return "positive"


def balanced_reservoir_sample(
    review_path: Path, per_class: int, seed: int
) -> tuple[list[str], list[str], dict[str, int]]:
    """Take an order-independent, bounded sample from each sentiment class."""
    rng = random.Random(seed)
    samples: dict[str, list[str]] = defaultdict(list)
    seen: dict[str, int] = defaultdict(int)

    for _, review in iter_jsonl(review_path):
        if review is None or not str(review.get("text", "")).strip():
            continue
        try:
            label = star_to_sentiment(float(review["stars"]))
        except (KeyError, TypeError, ValueError):
            continue

        seen[label] += 1
        text = str(review["text"])
        if len(samples[label]) < per_class:
            samples[label].append(text)
            continue
        replacement = rng.randrange(seen[label])
        if replacement < per_class:
            samples[label][replacement] = text

    texts: list[str] = []
    labels: list[str] = []
    for label in LABELS:
        texts.extend(samples[label])
        labels.extend([label] * len(samples[label]))
    return texts, labels, dict(seen)


def train_model(
    texts: list[str], labels: list[str], seed: int
) -> tuple[Pipeline, dict[str, Any]]:
    x_train, x_test, y_train, y_test = train_test_split(
        texts,
        labels,
        test_size=0.2,
        random_state=seed,
        stratify=labels,
    )
    model = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    lowercase=True,
                    strip_accents="unicode",
                    ngram_range=(1, 2),
                    min_df=2,
                    max_features=30_000,
                ),
            ),
            (
                "classifier",
                LogisticRegression(
                    max_iter=500,
                    class_weight="balanced",
                    random_state=seed,
                ),
            ),
        ]
    )
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)
    report = {
        "training_records": len(x_train),
        "test_records": len(x_test),
        "classification_report": classification_report(
            y_test, predictions, labels=LABELS, output_dict=True, zero_division=0
        ),
        "confusion_matrix_labels": list(LABELS),
        "confusion_matrix": confusion_matrix(
            y_test, predictions, labels=LABELS
        ).tolist(),
    }
    return model, report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument("--model-output", type=Path, default=Path("models/sentiment_model.joblib"))
    parser.add_argument(
        "--report-output", type=Path, default=Path("reports/sentiment_evaluation.json")
    )
    parser.add_argument("--per-class", type=int, default=20_000)
    parser.add_argument("--seed", type=int, default=42)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if not args.reviews.is_file():
        raise SystemExit(f"Review file not found: {args.reviews}")
    if args.per_class < 100:
        raise SystemExit("--per-class must be at least 100")

    texts, labels, source_counts = balanced_reservoir_sample(
        args.reviews, args.per_class, args.seed
    )
    if any(labels.count(label) < 100 for label in LABELS):
        raise SystemExit("Not enough reviews in every sentiment class.")

    model, report = train_model(texts, labels, args.seed)
    report.update(
        {
            "label_definition": {
                "negative": "1-2 stars",
                "neutral": "3 stars",
                "positive": "4-5 stars",
            },
            "sample_records": len(texts),
            "sample_per_class_requested": args.per_class,
            "seed": args.seed,
            "source_class_counts": source_counts,
        }
    )

    args.model_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, args.model_output)
    args.report_output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
