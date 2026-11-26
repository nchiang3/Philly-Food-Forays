"""Streamlit entry point for the Philadelphia Food Tour Optimizer."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))

from food_tour.data_access import (  # noqa: E402
    DatasetValidationError,
    load_food_sentiment,
    load_restaurants,
    summarize_reviews,
)
from food_tour.food_matching import FOOD_ALIASES  # noqa: E402


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
minimum_mentions = st.slider("Minimum matching reviews", 1, 25, 3)

restaurant_by_id = {row["business_id"]: row for row in restaurants}
filtered = []
for sentiment in food_sentiment:
    if sentiment["food"] != selected_food:
        continue
    if int(sentiment["matched_reviews"]) < minimum_mentions:
        continue
    restaurant = restaurant_by_id.get(sentiment["business_id"])
    if restaurant is None or (open_only and restaurant.get("is_open") != "1"):
        continue
    filtered.append(
        {
            "name": restaurant["name"],
            "address": restaurant["address"],
            "Yelp stars": float(restaurant["stars"]),
            "matching reviews": int(sentiment["matched_reviews"]),
            "positive sentiment": float(sentiment["positive_share"]),
            "food review stars": float(sentiment["average_review_stars"]),
            "latitude": float(restaurant["latitude"]),
            "longitude": float(restaurant["longitude"]),
        }
    )

filtered.sort(
    key=lambda row: (row["positive sentiment"], row["matching reviews"]),
    reverse=True,
)

st.caption(f"Showing {len(filtered):,} matching restaurants")
st.dataframe(
    filtered[:500],
    width="stretch",
    hide_index=True,
    column_config={
        "positive sentiment": st.column_config.NumberColumn(format="percent"),
        "food review stars": st.column_config.NumberColumn(format="%.2f"),
    },
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
