"""Streamlit entry point for the Philadelphia Food Tour Optimizer."""

from __future__ import annotations

import sys
from datetime import time
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))

from food_tour.data_access import (  # noqa: E402
    DatasetValidationError,
    load_food_sentiment,
    load_restaurants,
    summarize_reviews,
)
from food_tour.distance import (  # noqa: E402
    DISTANCE_COLUMN,
    LANDMARKS,
    TOP_RANKED_START,
    filter_near_start,
    max_pairwise_miles,
    select_close_together,
)
from food_tour.food_matching import FOOD_ALIASES  # noqa: E402
from food_tour.hours import WEEKDAYS  # noqa: E402
from food_tour.ranking import rank_restaurants  # noqa: E402


VISIT_TIMES = [time(hour, minute) for hour in range(24) for minute in (0, 30)]


def format_visit_time(value: time) -> str:
    """Display an explicit, user-friendly 12-hour time."""
    return value.strftime("%I:%M %p").lstrip("0")


st.set_page_config(
    page_title="Philly Food Forays",
    page_icon="🥨",
    layout="wide",
)

st.title("🥨 Philly Food Forays")
st.write(
    "Upload your locally generated Philadelphia datasets. Files are used only "
    "for the active Streamlit session and are not added to this repository."
)

with st.expander("How to prepare the files", expanded=False):
    st.code(
        "python3 scripts/preprocess_yelp.py \\\n+  --businesses yelp_academic_dataset_business.json \\\n+  --reviews yelp_academic_dataset_review-001.json",
        language="bash",
    )

restaurant_upload = st.file_uploader(
    "Philadelphia restaurant CSV",
    type=["csv"],
    max_upload_size=25,
    help="Expected file: philadelphia_restaurants.csv (approximately 6.35 MB).",
)
review_upload = st.file_uploader(
    "Philadelphia review JSONL (optional; needed only for training/validation)",
    type=["jsonl"],
    max_upload_size=650,
    help="Expected file: philadelphia_reviews.jsonl (approximately 535 MB).",
)
sentiment_upload = st.file_uploader(
    "Food sentiment summary CSV",
    type=["csv"],
    max_upload_size=25,
    help="Expected file: food_sentiment.csv, created by build_food_sentiment.py.",
)

if restaurant_upload is None:
    st.info("Upload the restaurant CSV to begin.")
    st.stop()

try:
    restaurants = load_restaurants(restaurant_upload)
except (DatasetValidationError, UnicodeDecodeError) as error:
    st.error(str(error))
    st.stop()

if sentiment_upload is None:
    st.info("Upload food_sentiment.csv to generate food-specific recommendations.")
    st.stop()

try:
    food_sentiment = load_food_sentiment(sentiment_upload)
except (DatasetValidationError, UnicodeDecodeError) as error:
    st.error(str(error))
    st.stop()

open_count = sum(row.get("is_open") == "1" for row in restaurants)
metric_a, metric_b, metric_c = st.columns(3)
metric_a.metric("Restaurants", f"{len(restaurants):,}")
metric_b.metric("Marked open", f"{open_count:,}")
metric_c.metric("Uploaded size", f"{restaurant_upload.size / 1_000_000:.1f} MB")

st.subheader("Explore signature foods")
selected_food = st.selectbox("Which Philadelphia food?", list(FOOD_ALIASES))
open_only = st.toggle("Show only businesses marked open", value=True)
minimum_mentions = st.slider("Minimum matching food reviews", 1, 100, 5)
filter_by_visit = st.toggle("Filter by planned visit day and time", value=False)
visit_day = None
visit_start_time = None
visit_end_time = None
if filter_by_visit:
    visit_column_a, visit_column_b, visit_column_c = st.columns(3)
    visit_day = visit_column_a.selectbox("Day visiting", WEEKDAYS)
    visit_start_time = visit_column_b.selectbox(
        "Start Time",
        VISIT_TIMES[:-1],
        index=VISIT_TIMES.index(time(12, 0)),
        format_func=format_visit_time,
    )
    end_time_options = [value for value in VISIT_TIMES if value > visit_start_time]
    default_end_time = time(17, 0)
    end_time_index = (
        end_time_options.index(default_end_time)
        if default_end_time in end_time_options
        else len(end_time_options) - 1
    )
    visit_end_time = visit_column_c.selectbox(
        "End Time",
        end_time_options,
        index=end_time_index,
        format_func=format_visit_time,
    )

CLOSE_TOGETHER = "Close to each other"
NEAR_START = "Close to a starting point"

filter_by_distance = st.toggle(
    "Keep top spots within walking distance", value=False
)
distance_mode = None
max_miles = None
if filter_by_distance:
    distance_column_a, distance_column_b, distance_column_c = st.columns(3)
    distance_mode = distance_column_a.radio(
        "Measure distance",
        [CLOSE_TOGETHER, NEAR_START],
        help=(
            "Close to each other: every stop is within the limit of every "
            "other stop. Close to a starting point: every stop is within the "
            "limit of the chosen start."
        ),
    )
    max_miles = distance_column_b.slider(
        "Maximum distance (miles)", 0.25, 5.0, 1.0, step=0.25
    )
    if distance_mode == CLOSE_TOGETHER:
        max_stops = distance_column_c.slider("Number of stops", 2, 15, 5)
    else:
        start_name = distance_column_c.selectbox(
            "Starting point", [TOP_RANKED_START, *LANDMARKS]
        )

ranked = rank_restaurants(
    restaurants,
    food_sentiment,
    selected_food,
    minimum_mentions,
    open_only,
    visit_day,
    visit_start_time,
    visit_end_time,
)

filtered = ranked
if filter_by_distance:
    limit_label = f"{max_miles:g} mile" + ("" if max_miles == 1 else "s")
    if distance_mode == CLOSE_TOGETHER:
        filtered = select_close_together(ranked, max_miles, max_stops)
    else:
        filtered = filter_near_start(ranked, max_miles, LANDMARKS.get(start_name))

st.caption(f"Showing {len(filtered):,} matching restaurants")
if filter_by_distance and filtered:
    if distance_mode == CLOSE_TOGETHER:
        st.caption(
            f"Picked in ranking order, keeping each spot only if it is within "
            f"{limit_label} of every spot already chosen. The farthest "
            f"two stops are {max_pairwise_miles(filtered):.2f} miles apart. "
            f"Distances are straight-line from the #1 spot; walking routes "
            f"are usually 20-40% longer."
        )
    else:
        farthest = max(row[DISTANCE_COLUMN] for row in filtered)
        start_label = (
            "the top-ranked restaurant"
            if start_name == TOP_RANKED_START
            else start_name
        )
        st.caption(
            f"Restaurants within {limit_label} (straight line) of "
            f"{start_label}. "
            f"The farthest is {farthest:.2f} miles away; walking routes are "
            f"usually 20-40% longer."
        )
elif filter_by_distance and ranked:
    st.warning("No restaurants fit within that distance. Try a larger limit.")
if filter_by_visit:
    st.caption(
        "Restaurants qualify if they are open at any point in the selected "
        "window. Hours come from the Yelp Open Dataset; businesses with "
        "missing hours are excluded."
    )
st.dataframe(
    filtered[:500],
    width="stretch",
    hide_index=True,
    column_config={
        "food positive sentiment": st.column_config.NumberColumn(format="percent"),
        "volume-adjusted sentiment": st.column_config.NumberColumn(format="percent"),
        "food review stars": st.column_config.NumberColumn(format="%.2f"),
        DISTANCE_COLUMN: st.column_config.NumberColumn(format="%.2f mi"),
    },
)
st.caption(
    "Recommendation score: 45% volume-adjusted food sentiment, 40% "
    "food-specific review volume, and 15% overall Yelp review volume."
)

st.subheader("Review data")
if review_upload is None:
    st.info(
        "The review file is optional for browsing restaurants. Upload it when "
        "running sentiment analysis or other review-based features."
    )
else:
    review_key = f"{review_upload.name}:{review_upload.size}"
    if st.button("Validate review file", type="primary"):
        with st.spinner("Streaming and validating the review file..."):
            try:
                st.session_state["review_summary"] = summarize_reviews(review_upload)
                st.session_state["review_summary_key"] = review_key
            except (DatasetValidationError, UnicodeDecodeError) as error:
                st.error(str(error))

    if st.session_state.get("review_summary_key") == review_key:
        summary = st.session_state["review_summary"]
        review_a, review_b, review_c = st.columns(3)
        review_a.metric("Reviews", f"{summary['review_count']:,}")
        review_b.metric("Restaurants reviewed", f"{summary['business_count']:,}")
        review_c.metric("Uploaded size", f"{review_upload.size / 1_000_000:.1f} MB")
        st.write("Review star distribution", summary["star_counts"])
        st.dataframe(summary["sample"], width="stretch", hide_index=True)
