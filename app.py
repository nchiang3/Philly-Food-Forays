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
    stop_shortfall_message,
)
from food_tour.chains import (  # noqa: E402
    CHAIN_LOCATIONS_COLUMN,
    collapse_chains,
    merged_chain_count,
    select_close_together_one_per_chain,
)
from food_tour.food_matching import FOOD_ALIASES  # noqa: E402
from food_tour.hours import WEEKDAYS  # noqa: E402
from food_tour.ranking import HOURS_JSON_COLUMN, rank_restaurants  # noqa: E402
from food_tour.schedule import (  # noqa: E402
    ARRIVAL_COLUMN,
    DEFAULT_MINUTES_PER_STOP,
    VISIT_ORDER_COLUMN,
    plan_visit_order,
    unscheduled_message,
)


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

one_per_chain = st.toggle(
    "Show one location per chain",
    value=True,
    help=(
        "Chains such as Wawa appear once, using the location closest to the "
        "other top-ranked spots."
    ),
)
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
    if distance_mode == CLOSE_TOGETHER and one_per_chain:
        filtered = select_close_together_one_per_chain(ranked, max_miles, max_stops)
    elif distance_mode == CLOSE_TOGETHER:
        filtered = select_close_together(ranked, max_miles, max_stops)
    else:
        filtered = filter_near_start(ranked, max_miles, LANDMARKS.get(start_name))
        if one_per_chain:
            filtered = collapse_chains(filtered)
elif one_per_chain:
    filtered = collapse_chains(ranked)

st.caption(f"Showing {len(filtered):,} matching restaurants")
chain_count = merged_chain_count(filtered) if one_per_chain else 0
if chain_count:
    chain_label = "1 chain is shown once" if chain_count == 1 else (
        f"{chain_count:,} chains are shown once each"
    )
    st.caption(
        f"{chain_label}, using "
        f"the location closest to the other top spots (see the "
        f"'{CHAIN_LOCATIONS_COLUMN}' column). A chain keeps the rank of its "
        f"best-reviewed location; the row shows the chosen location's own "
        f"scores."
    )
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
if filter_by_distance and distance_mode == CLOSE_TOGETHER:
    shortfall = stop_shortfall_message(max_stops, len(filtered))
    if shortfall:
        st.warning(shortfall)
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
        HOURS_JSON_COLUMN: None,
    },
)
st.caption(
    "Recommendation score: 45% volume-adjusted food sentiment, 40% "
    "food-specific review volume, and 15% overall Yelp review volume."
)

if filter_by_visit and filtered:
    st.subheader("Suggested visit order")
    order_column_a, order_column_b = st.columns(2)
    minutes_per_stop = order_column_a.slider(
        "Minutes per stop (eating plus walking)",
        15,
        120,
        DEFAULT_MINUTES_PER_STOP,
        step=5,
    )
    if filter_by_distance and distance_mode == CLOSE_TOGETHER:
        tour_stops = filtered
        order_column_b.caption(
            f"Scheduling the {len(tour_stops)} stops picked above."
        )
    else:
        stop_limit = min(15, len(filtered))
        stops_to_plan = (
            order_column_b.slider(
                "Stops to schedule", 1, stop_limit, min(5, stop_limit)
            )
            if stop_limit > 1
            else 1
        )
        tour_stops = filtered[:stops_to_plan]
    plan = plan_visit_order(
        tour_stops,
        visit_day,
        visit_start_time,
        visit_end_time,
        minutes_per_stop,
    )
    plan_columns = [
        VISIT_ORDER_COLUMN,
        ARRIVAL_COLUMN,
        "name",
        "address",
        f"{visit_day} hours",
        "recommendation score",
    ]
    if any(DISTANCE_COLUMN in row for row in plan):
        plan_columns.append(DISTANCE_COLUMN)
    st.dataframe(
        [{column: row.get(column) for column in plan_columns} for row in plan],
        width="stretch",
        hide_index=True,
        column_config={
            VISIT_ORDER_COLUMN: st.column_config.NumberColumn(format="%d"),
            DISTANCE_COLUMN: st.column_config.NumberColumn(format="%.2f mi"),
        },
    )
    st.caption(
        f"Starting at {format_visit_time(visit_start_time)}, each next stop is "
        f"the one you can visit soonest: places open at the start come first, "
        f"and later-opening places are scheduled after they open. Ties go to "
        f"the place that closes sooner, then the higher-ranked one. Every stop "
        f"is reached before it closes and before "
        f"{format_visit_time(visit_end_time)}. Times are approximate."
    )
    unscheduled = unscheduled_message(plan)
    if unscheduled:
        st.warning(unscheduled)

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
