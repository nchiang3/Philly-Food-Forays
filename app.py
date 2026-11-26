"""Streamlit entry point for the Philadelphia Food Tour Optimizer."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))

from food_tour.data_access import (  # noqa: E402
    DatasetValidationError,
    category_options,
    load_restaurants,
    summarize_reviews,
)


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
    "Philadelphia review JSONL (optional for initial exploration)",
    type=["jsonl"],
    max_upload_size=650,
    help="Expected file: philadelphia_reviews.jsonl (approximately 535 MB).",
)

if restaurant_upload is None:
    st.info("Upload the restaurant CSV to begin.")
    st.stop()

try:
    restaurants = load_restaurants(restaurant_upload)
except (DatasetValidationError, UnicodeDecodeError) as error:
    st.error(str(error))
    st.stop()

open_count = sum(row.get("is_open") == "1" for row in restaurants)
metric_a, metric_b, metric_c = st.columns(3)
metric_a.metric("Restaurants", f"{len(restaurants):,}")
metric_b.metric("Marked open", f"{open_count:,}")
metric_c.metric("Uploaded size", f"{restaurant_upload.size / 1_000_000:.1f} MB")

st.subheader("Explore restaurants")
categories = category_options(restaurants)
selected_category = st.selectbox("Food or cuisine category", ["All"] + categories)
open_only = st.toggle("Show only businesses marked open", value=True)

filtered = restaurants
if selected_category != "All":
    filtered = [
        row
        for row in filtered
        if selected_category in {part.strip() for part in row["categories"].split(",")}
    ]
if open_only:
    filtered = [row for row in filtered if row.get("is_open") == "1"]

st.caption(f"Showing {len(filtered):,} matching restaurants")
preview_fields = ["name", "address", "stars", "review_count", "categories"]
st.dataframe(
    [{field: row.get(field) for field in preview_fields} for row in filtered[:500]],
    width="stretch",
    hide_index=True,
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

