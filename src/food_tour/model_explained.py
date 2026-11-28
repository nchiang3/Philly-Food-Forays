"""Content and score breakdowns for the "Model explained" step.

The page is written for a data-science audience: where the data comes from,
how current it is, how the sentiment model and ranking score work, and why
each tour-building rule was chosen. Numbers that come from code (score
weights, the prior strength, thresholds) are read from their modules so the
page cannot drift from the model it describes.
"""

from __future__ import annotations

import math
from html import escape
from typing import Any

from .chains import REFERENCE_COUNT
from .ranking import (
    FOOD_REVIEW_VOLUME_WEIGHT,
    OVERALL_REVIEW_VOLUME_WEIGHT,
    PRIOR_STRENGTH,
    SENTIMENT_WEIGHT,
)
from .restrooms import RESTROOM_RADIUS_MILES
from .review_highlights import MAX_REVIEWS_PER_BUSINESS


# Measured from the team's copy of the Yelp Open Dataset (the JSON files in
# yelp_dataset.tar are timestamped 2022-01-19) by scanning every review's
# "date" field. The newest review in the full file and in the Philadelphia
# subset is dated 2022-01-19, so the snapshot is effective as of that day.
SNAPSHOT_DATE = "January 19, 2022"
FIRST_REVIEW_DATE = "February 16, 2005"
ALL_REVIEW_COUNT = 6_990_280
PHILLY_REVIEW_COUNT = 708_284
DATASET_URL = "https://www.yelp.com/dataset"

CITATION_TEXT = (
    "Yelp Inc. (2022). <em>Yelp Open Dataset</em> [Data set]. "
    f'Snapshot of January 19, 2022. <a href="{DATASET_URL}">{DATASET_URL}</a>'
)
BIBTEX = f"""@misc{{yelp_open_dataset_2022,
  author       = {{{{Yelp Inc.}}}},
  title        = {{Yelp Open Dataset}},
  year         = {{2022}},
  note         = {{Snapshot of 2022-01-19; reviews dated 2005-02-16 to 2022-01-19}},
  howpublished = {{\\url{{{DATASET_URL}}}}}
}}"""

SCORE_LATEX = (
    r"\text{score} = 100\left("
    rf"{SENTIMENT_WEIGHT:.2f}\,\underbrace{{\frac{{p + k\,\bar{{s}}}}{{n + k}}}}_{{\text{{shrunk sentiment}}}}"
    rf" + {FOOD_REVIEW_VOLUME_WEIGHT:.2f}\,\underbrace{{\frac{{\ln(1+n)}}{{\ln(1+n_{{\max}})}}}}_{{\text{{food volume}}}}"
    rf" + {OVERALL_REVIEW_VOLUME_WEIGHT:.2f}\,\underbrace{{\frac{{\ln(1+N)}}{{\ln(1+N_{{\max}})}}}}_{{\text{{overall volume}}}}"
    r"\right)"
)

SEGMENTS = (
    ("sentiment", "Shrunk food sentiment", SENTIMENT_WEIGHT),
    ("food-volume", "Food review volume", FOOD_REVIEW_VOLUME_WEIGHT),
    ("overall-volume", "Overall Yelp volume", OVERALL_REVIEW_VOLUME_WEIGHT),
)


def _percent(weight: float) -> str:
    return f"{weight * 100:.0f}%"


def score_components(ranked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Split each ranked row's score into its three weighted parts (in points).

    ``ranked`` must be the full output of ``rank_restaurants`` for one search,
    because the volume terms are scaled by the largest counts in that pool.
    The three parts add up to the row's recommendation score, up to rounding.
    """
    if not ranked:
        return []
    max_mentions = max(int(row["matching food reviews"]) for row in ranked)
    max_overall = max(int(row["overall Yelp reviews"]) for row in ranked)

    def log_share(value: int, largest: int) -> float:
        return math.log1p(value) / math.log1p(largest) if largest > 0 else 0.0

    breakdown = []
    for row in ranked:
        parts = {
            "sentiment": 100 * SENTIMENT_WEIGHT * float(row["volume-adjusted sentiment"]),
            "food-volume": 100
            * FOOD_REVIEW_VOLUME_WEIGHT
            * log_share(int(row["matching food reviews"]), max_mentions),
            "overall-volume": 100
            * OVERALL_REVIEW_VOLUME_WEIGHT
            * log_share(int(row["overall Yelp reviews"]), max_overall),
        }
        breakdown.append(
            {
                "business_id": row.get("business_id"),
                "name": row["name"],
                "score": float(row["recommendation score"]),
                "parts": parts,
            }
        )
    return breakdown


def prior_positive_share(ranked: list[dict[str, Any]]) -> float | None:
    """Pool-wide share of positive food mentions, the shrinkage target."""
    mentions = sum(int(row["matching food reviews"]) for row in ranked)
    if not mentions:
        return None
    positive = sum(
        float(row["food positive sentiment"]) * int(row["matching food reviews"])
        for row in ranked
    )
    return positive / mentions


def glance_html(restaurant_count: int, food_rows: int, food_mentions: int) -> str:
    tiles = (
        (SNAPSHOT_DATE, "Data effective date (newest review)"),
        (f"{PHILLY_REVIEW_COUNT:,}", "Philadelphia reviews in the snapshot"),
        (f"{restaurant_count:,}", "Food businesses in your restaurant file"),
        (f"{food_mentions:,}", f"Food mentions scored, across {food_rows:,} business-food pairs"),
    )
    cells = "".join(
        f'<div class="mx-tile"><strong>{escape(value)}</strong><span>{escape(label)}</span></div>'
        for value, label in tiles
    )
    return f'<div class="mx-tiles">{cells}</div>'


def data_source_html() -> str:
    return f"""
<section class="mx-card mx-source">
  <h3>Data source</h3>
  <p class="mx-citation">{CITATION_TEXT}</p>
  <dl class="mx-facts">
    <div><dt>Effective date</dt><dd>{SNAPSHOT_DATE}. That is the date of the newest review in
      the file, and the JSON files in Yelp's download are timestamped the same day.</dd></div>
    <div><dt>Review window</dt><dd>{FIRST_REVIEW_DATE} to {SNAPSHOT_DATE}.
      {ALL_REVIEW_COUNT:,} reviews in total, {PHILLY_REVIEW_COUNT:,} of them for the
      Philadelphia food businesses this app keeps.</dd></div>
    <div><dt>Point-in-time fields</dt><dd>Hours, the open or closed flag, stars and review counts
      describe businesses as of the snapshot, not today. The app says so wherever it shows them.</dd></div>
    <div><dt>Coverage notes</dt><dd>Philadelphia review volume roughly halves in 2020 and 2021
      (pandemic closures), and January 2022 is a partial month. Yelp's open dataset is a subset of
      Yelp's data, not a census of every business or review.</dd></div>
    <div><dt>Terms</dt><dd>Use is governed by the Dataset User Agreement included in Yelp's
      download. Raw and derived Yelp files stay local and are excluded from Git.</dd></div>
  </dl>
</section>
"""


PIPELINE = (
    ("1", "Filter", "Stream Yelp JSON; keep Philadelphia restaurants, bakeries, delis, pretzel and water-ice shops"),
    ("2", "Match foods", "Find the 7 signature foods with aliases and conservative fuzzy matching"),
    ("3", "Score sentences", "TF-IDF + logistic regression labels each food sentence negative, neutral or positive"),
    ("4", "Aggregate", "Count positive, neutral and negative mentions per business and food"),
    ("5", "Rank", "Shrunk sentiment plus log-scaled volume gives one score per restaurant"),
    ("6", "Build the tour", "Distance, chain, hours and routing rules turn the ranking into a walk"),
)


def pipeline_html() -> str:
    steps = "".join(
        f'<li><span class="mx-step-number">{number}</span>'
        f"<strong>{escape(title)}</strong><span>{escape(text)}</span></li>"
        for number, title, text in PIPELINE
    )
    return (
        '<section class="mx-card"><h3>Pipeline at a glance</h3>'
        f'<ol class="mx-pipeline" aria-label="Model pipeline">{steps}</ol></section>'
    )


def sentiment_html() -> str:
    return """
<section class="mx-card">
  <h3>Sentiment model</h3>
  <div class="mx-two-column">
    <div>
      <h4>How it works</h4>
      <ul>
        <li><b>Labels.</b> Yelp stars are weak labels: 1-2 stars negative, 3 neutral, 4-5 positive.</li>
        <li><b>Sample.</b> A seeded reservoir sample of up to 20,000 reviews per class (balanced),
          split 80/20 with stratification.</li>
        <li><b>Features.</b> TF-IDF on word unigrams and bigrams, lowercased and accent-stripped,
          <code>min_df=2</code>, capped at 30,000 features.</li>
        <li><b>Classifier.</b> Multinomial logistic regression with balanced class weights.</li>
        <li><b>Result.</b> About 77% accuracy on the balanced held-out set; the script also writes
          per-class precision, recall, F1 and a confusion matrix.</li>
        <li><b>Inference.</b> The model scores only the sentences that mention a food, so a review
          that loves the fries but not the cheesesteak counts against the cheesesteak.</li>
      </ul>
    </div>
    <div>
      <h4>Why this model</h4>
      <ul>
        <li>A strong, well-understood text baseline that trains in minutes on a laptop.</li>
        <li>Coefficients are inspectable, so the words that drive a prediction can be shown.</li>
        <li>Star-derived labels need no hand annotation and are reproducible from the data.</li>
        <li>No hosted model or API key, so the project runs entirely offline and for free.</li>
      </ul>
      <h4>Known caveats</h4>
      <ul>
        <li>Stars rate the whole visit, not one dish, so labels are noisy at the sentence level.</li>
        <li>The model trains on full reviews but predicts on short sentences (a domain shift).</li>
        <li>Neutral is the hardest class; 3-star reviews often mix praise and complaints.</li>
      </ul>
    </div>
  </div>
</section>
"""


def ranking_intro_html() -> str:
    return f"""
<section class="mx-card mx-ranking">
  <h3>Recommendation score</h3>
  <p>Each restaurant that matches the search gets a 0-100 score built from three parts. The
  pool for the prior and the maximums is the set of restaurants that pass the current filters
  (food, minimum reviews, open-only and visit window).</p>
  <div class="mx-weights" role="img" aria-label="Score weights: {_percent(SENTIMENT_WEIGHT)} sentiment, {_percent(FOOD_REVIEW_VOLUME_WEIGHT)} food review volume, {_percent(OVERALL_REVIEW_VOLUME_WEIGHT)} overall volume">
    {"".join(f'<span class="mx-seg-{key}" style="flex: {weight}">{_percent(weight)} {escape(label)}</span>' for key, label, weight in SEGMENTS)}
  </div>
</section>
"""


def ranking_terms_html(prior: float | None, food: str) -> str:
    prior_text = (
        f"For {escape(food)} with your current filters, s&#772; is about {prior:.0%}."
        if prior is not None
        else ""
    )
    return f"""
<div class="mx-two-column mx-terms">
  <div class="mx-card">
    <h4>Terms</h4>
    <ul>
      <li><i>p</i>: food mentions the model scored positive; <i>n</i>: all food mentions.</li>
      <li><i>s&#772;</i>: positive share across the whole pool (the prior mean). {prior_text}</li>
      <li><i>k</i> = {PRIOR_STRENGTH}: prior strength, in pseudo-reviews.</li>
      <li><i>N</i>: the restaurant's total Yelp reviews, for any food.</li>
      <li>Maximums are taken over the same pool, so volume terms run from 0 to 1.</li>
    </ul>
  </div>
  <div class="mx-card">
    <h4>Why this form</h4>
    <ul>
      <li><b>Shrinkage.</b> A beta-binomial style posterior mean pulls small samples toward the
        pool average. Two glowing mentions cannot beat 300 that are 85% positive.</li>
      <li><b>Log volume.</b> Rewards credible evidence with diminishing returns, so the busiest
        place does not win on size alone.</li>
      <li><b>Overall volume.</b> A small tie-breaker for established, findable businesses.</li>
      <li><b>Hand-set weights.</b> There is no ground-truth "best stop" label to learn weights
        from, so they are fixed and shown openly rather than fitted.</li>
    </ul>
    <p class="mx-muted">Alternatives considered: average stars (ignores the food and sample size),
    a Wilson lower bound (similar intent, harder to explain), and learning-to-rank (needs labels
    the data does not have).</p>
  </div>
</div>
"""


def breakdown_html(breakdown: list[dict[str, Any]], food: str) -> str:
    """Stacked bars showing how each tour stop's score splits into its parts."""
    if not breakdown:
        return ""
    rows = []
    for item in breakdown:
        parts = item["parts"]
        segments = "".join(
            f'<span class="mx-seg-{key}" style="width: {parts[key]:.2f}%" '
            f'title="{escape(label)}: {parts[key]:.1f} points"></span>'
            for key, label, _ in SEGMENTS
        )
        detail = ", ".join(
            f"{escape(label.lower())} {parts[key]:.1f}" for key, label, _ in SEGMENTS
        )
        rows.append(
            f'<li><span class="mx-bar-name">{escape(item["name"])}</span>'
            f'<span class="mx-bar" role="img" aria-label="Score {item["score"]:.1f}: {detail}">{segments}</span>'
            f'<span class="mx-bar-score">{item["score"]:.1f}</span></li>'
        )
    legend = "".join(
        f'<span><i class="mx-seg-{key}"></i>{escape(label)}</span>' for key, label, _ in SEGMENTS
    )
    return f"""
<section class="mx-card">
  <h3>Your tour's scores, decomposed</h3>
  <p class="mx-muted">Live from your current {escape(food)} search. Each bar is out of 100 points;
  hover a segment for its exact value.</p>
  <div class="mx-legend">{legend}</div>
  <ol class="mx-bars">{''.join(rows)}</ol>
</section>
"""


DECISIONS = (
    (
        "Rule-based food matching",
        "Curated aliases (\"wooder ice\", \"gelati\"), plural forms, and fuzzy matching only for "
        "distinctive food words (similarity of at least 0.84, same first letter).",
        "Every match can be traced to a rule and the whole corpus runs offline. Precision beats "
        "recall here: a missed mention lowers volume a little, a false one adds a wrong stop.",
        "Some false positives remain, for example a Japanese restaurant matching Water Ice.",
    ),
    (
        "Distance filter instead of K-means",
        "Two modes: every stop within the limit of every other stop, or every stop within the "
        "limit of a start. Straight-line haversine miles from Yelp coordinates.",
        "Clustering groups places by location but does not pick which top places to visit. A "
        "direct distance constraint on the ranked list answers the tourist's question.",
        "Straight lines understate walks by about 20-40%, which the app notes.",
    ),
    (
        "Greedy \"close to each other\" selection",
        "Walk the ranking in order and keep a restaurant only if it is within the limit of every "
        "stop already chosen. The #1 restaurant always anchors the tour.",
        "Guarantees the largest gap never exceeds the limit, keeps the highest-ranked places, "
        "and is instant.",
        "A strong outlier, like a top cheesesteak far from the center, can pull the tour away "
        "from denser areas. Trying several anchors is on the roadmap.",
    ),
    (
        "Fewer-stops warning",
        "When fewer restaurants fit than the stop count asks for, the app says how many fit and "
        "which filter to loosen.",
        "A shorter tour without explanation looks like a bug. Naming the binding constraint "
        "keeps the filter honest.",
        "The hint lists likely causes; it does not test which one binds.",
    ),
    (
        "Opening-hours ordering",
        "With a visit window, repeatedly pick the stop you can visit soonest. Ties go to the one "
        "that closes sooner, then to the higher rank. Overnight hours carry over.",
        "A simple, explainable earliest-available heuristic that never sends you to a closed "
        "door, and puts closing-soon places first.",
        "Uses a fixed minutes-per-stop pace, not routed walking times, and does not search "
        "every order, so an early-closing stop can occasionally be crowded out.",
    ),
    (
        "Shortest walking order",
        "Without a visit window: nearest-neighbour from every possible first stop, improved with "
        "2-opt, keeping the shortest one-way route. Streets come from the free FOSSGIS OSRM server.",
        "Near-optimal for 15 stops or fewer in well under a second, with one routing request "
        "per tour.",
        "The order is chosen with straight-line distances; only the drawn line and minutes follow streets.",
    ),
    (
        "One location per chain",
        "Names that match after normalising case, accents, punctuation, a leading \"The\" and "
        "\"&\" are merged. The chain keeps its best rank but shows the location closest to the "
        f"rest of the tour (or to the top {REFERENCE_COUNT} other picks).",
        "Five Wawas is not a food tour. Keeping the best rank stays fair to the chain, while "
        "the closest location keeps the walk short.",
        "Exact-name matching on purpose: \"Wawa\" and \"Wawa Welcome America\" stay separate.",
    ),
    (
        "Review highlights without an API",
        "For each stop, keep up to the "
        f"{MAX_REVIEWS_PER_BUSINESS:,} most recent sentences about the food, count the words that "
        "appear with it, and quote the real 4-5 star and 1-2 star sentences that best match them.",
        "The team chose not to add a paid LLM API key. Extractive summaries cost nothing, run "
        "offline, and every quote is a real reviewer's words, so nothing can be hallucinated.",
        "Less fluent than a written summary, and word counts can miss sarcasm or negation.",
    ),
    (
        "Free maps and restroom data",
        "pydeck on CARTO's OpenStreetMap basemap, key-free Google Maps direction links, and "
        f"OpenStreetMap and city restroom listings within {RESTROOM_RADIUS_MILES:g} miles of the route.",
        "No Google Cloud billing or secrets to manage, and the app still hands off to Google Maps "
        "for turn-by-turn directions.",
        "Community-mapped restroom data can be incomplete or out of date.",
    ),
)


def decisions_html() -> str:
    cards = "".join(
        f"""<article class="mx-decision">
  <h4>{escape(title)}</h4>
  <p><span class="mx-tag">What</span>{escape(what)}</p>
  <p><span class="mx-tag mx-tag-why">Why</span>{escape(why)}</p>
  <p><span class="mx-tag mx-tag-tradeoff">Trade-off</span>{escape(tradeoff)}</p>
</article>"""
        for title, what, why, tradeoff in DECISIONS
    )
    return (
        '<section class="mx-card"><h3>Design decisions</h3>'
        '<p class="mx-muted">Each rule that turns the ranking into a tour, why it was chosen, '
        "and what it gives up.</p>"
        f'<div class="mx-decisions">{cards}</div></section>'
    )


def limitations_html() -> str:
    return """
<section class="mx-card mx-limits">
  <h3>Limitations and next steps</h3>
  <ul>
    <li>The snapshot is from early 2022, so some businesses have since closed, moved or changed hours.</li>
    <li>Sentiment uses star-based weak labels; a small hand-labelled set of food sentences would
      measure sentence-level accuracy directly.</li>
    <li>Score weights are fixed by judgement; a sensitivity check or a short user study would
      show how much the rankings depend on them.</li>
    <li>Next up: seed "close to each other" tours from several top restaurants, schedule with real
      walking times, and review food-matching false positives.</li>
  </ul>
</section>
"""
