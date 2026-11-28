"""Summarize what reviewers say about a stop's signature food, without an API.

The summary is extractive and explainable: it finds the words reviewers use
most often alongside the food, then quotes the review sentences that best
represent those common themes, preferring reviews other Yelp users voted
useful. Praise comes from 4-5 star reviews and critiques from 1-2 star
reviews, matching the sentiment labels used for training.
"""

from __future__ import annotations

import io
import json
import math
import re
from collections import Counter
from typing import Any, BinaryIO, Iterable

from .food_matching import FOOD_ALIASES, extract_food_snippets, match_foods, normalize_text


# Reviews kept per restaurant; the most recent ones are enough for themes.
MAX_REVIEWS_PER_BUSINESS = 1500
MIN_QUOTE_WORDS = 6
MAX_QUOTE_WORDS = 40

STOPWORDS = frozenset(
    """
    a about above after again all also am an and any are as at be because been
    before being below best better between both but by can could did do does
    doing don down during each even ever every few for from further get got
    had has have having he her here hers him his how i if in into is it its
    just like ll me more most much my no nor not now of off on once one only
    or other our out over own place re really same she should so some such
    than that the their them then there these they this those through to too
    under until up us ve very was we were what when where which while who why
    will with would you your yours food restaurant philly philadelphia go
    went come came order ordered try tried time times back definitely make
    made way thing things lot bit always never still say said know think
    though got getting well pretty little two first next day night
    didn wasn isn doesn couldn wouldn aren weren
    """.split()
)

FOOD_WORDS = frozenset(
    word
    for aliases in FOOD_ALIASES.values()
    for alias in aliases
    for word in normalize_text(alias).split()
)


def _text_reader(binary_file: BinaryIO) -> io.TextIOWrapper:
    binary_file.seek(0)
    return io.TextIOWrapper(binary_file, encoding="utf-8", newline="")


def collect_food_reviews(
    binary_file: BinaryIO,
    business_ids: Iterable[str],
    food: str,
    max_per_business: int = MAX_REVIEWS_PER_BUSINESS,
) -> dict[str, list[dict[str, Any]]]:
    """Stream the review JSONL once and keep reviews mentioning ``food``.

    Only reviews of ``business_ids`` are parsed; other lines are skipped with
    a quick text check, so the ~535 MB file streams in seconds. Each kept
    review has ``stars``, ``useful``, ``date``, and ``snippet`` (only the
    sentences that mention the food). Every requested business appears in
    the result, with an empty list when no review mentions the food.
    """
    wanted = {str(business_id) for business_id in business_ids}
    found: dict[str, list[dict[str, Any]]] = {business_id: [] for business_id in wanted}
    if not wanted:
        return found

    text_file = _text_reader(binary_file)
    try:
        for line in text_file:
            if not any(business_id in line for business_id in wanted):
                continue
            try:
                review = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(review, dict):
                continue
            business_id = str(review.get("business_id", ""))
            if business_id not in wanted:
                continue
            snippet = extract_food_snippets(str(review.get("text", ""))).get(food)
            if not snippet:
                continue
            try:
                stars = float(review.get("stars"))
            except (TypeError, ValueError):
                continue
            try:
                useful = int(review.get("useful") or 0)
            except (TypeError, ValueError):
                useful = 0
            found[business_id].append(
                {
                    "stars": stars,
                    "useful": useful,
                    "date": str(review.get("date") or ""),
                    "snippet": snippet,
                }
            )
    finally:
        text_file.detach()
        binary_file.seek(0)

    for business_id, reviews in found.items():
        if len(reviews) > max_per_business:
            reviews.sort(key=lambda review: review["date"], reverse=True)
            found[business_id] = reviews[:max_per_business]
    return found


def _content_words(text: str) -> list[str]:
    return [
        word
        for word in normalize_text(text).split()
        if len(word) >= 3
        and word not in STOPWORDS
        and word not in FOOD_WORDS
        and not word.isdigit()
    ]


def _sentences(snippet: str, food: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", snippet)
    return [
        part.strip()
        for part in parts
        if part.strip() and food in match_foods(part)
    ]


def common_themes(
    reviews: list[dict[str, Any]], limit: int = 6, min_reviews: int = 2
) -> list[tuple[str, int]]:
    """Words most reviews use near the food, as ``(word, review count)``."""
    counts: Counter[str] = Counter()
    for review in reviews:
        counts.update(set(_content_words(review["snippet"])))
    return [
        (word, count)
        for word, count in counts.most_common(limit * 3)
        if count >= min_reviews
    ][:limit]


def _best_quotes(
    reviews: list[dict[str, Any]],
    food: str,
    weights: dict[str, float],
    limit: int,
) -> list[dict[str, Any]]:
    candidates = []
    for review in reviews:
        for sentence in _sentences(review["snippet"], food):
            word_count = len(sentence.split())
            if not MIN_QUOTE_WORDS <= word_count <= MAX_QUOTE_WORDS:
                continue
            words = set(_content_words(sentence))
            theme_score = sum(weights.get(word, 0.0) for word in words)
            score = theme_score / math.sqrt(word_count) + 0.3 * math.log1p(
                review["useful"]
            )
            candidates.append((score, sentence, review))
    candidates.sort(key=lambda item: item[0], reverse=True)

    quotes: list[dict[str, Any]] = []
    seen: list[set[str]] = []
    for _score, sentence, review in candidates:
        words = set(_content_words(sentence))
        # Skip near-duplicates of a quote already chosen.
        if any(len(words & other) > 0.6 * max(len(words), 1) for other in seen):
            continue
        quotes.append(
            {
                "text": sentence,
                "stars": review["stars"],
                "date": review["date"][:10],
            }
        )
        seen.append(words)
        if len(quotes) == limit:
            break
    return quotes


def summarize_food_reviews(
    reviews: list[dict[str, Any]],
    food: str,
    praise_count: int = 3,
    critique_count: int = 1,
) -> dict[str, Any]:
    """Summarize reviews from :func:`collect_food_reviews` for one stop.

    Returns ``review_count``, ``positive_share`` (share of 4-5 star reviews),
    ``themes`` (common words and how many reviews use them), and ``praise``
    and ``critiques`` quotes, each with ``text``, ``stars``, and ``date``.
    """
    positive = [review for review in reviews if review["stars"] >= 4]
    negative = [review for review in reviews if review["stars"] <= 2]
    themes = common_themes(reviews)
    total = max(len(reviews), 1)

    def weights(group: list[dict[str, Any]]) -> dict[str, float]:
        counts: Counter[str] = Counter()
        for review in group:
            counts.update(set(_content_words(review["snippet"])))
        size = max(len(group), 1)
        return {word: count / size for word, count in counts.items() if count >= 2}

    return {
        "review_count": len(reviews),
        "positive_share": len(positive) / total if reviews else None,
        "themes": themes,
        "praise": _best_quotes(positive, food, weights(positive), praise_count),
        "critiques": _best_quotes(negative, food, weights(negative), critique_count),
    }
