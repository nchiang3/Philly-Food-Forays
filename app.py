"""Streamlit entry point for the Philadelphia Food Tour Optimizer."""

from __future__ import annotations

import sys
from base64 import b64encode
from datetime import time
from html import escape
from pathlib import Path

import pydeck as pdk
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR / "src"))

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
    row_chain_key,
    select_close_together_one_per_chain,
)
from food_tour.food_matching import FOOD_ALIASES  # noqa: E402
from food_tour.hours import WEEKDAYS  # noqa: E402
from food_tour.ranking import HOURS_JSON_COLUMN, rank_restaurants  # noqa: E402
from food_tour.route import (  # noqa: E402
    CUMULATIVE_COLUMN,
    GOOGLE_MAPS_MAX_POINTS,
    LEG_COLUMN,
    WALK_MINUTES_COLUMN,
    WALK_ORDER_COLUMN,
    add_route_legs,
    google_maps_walking_urls,
    map_markers,
    map_view,
    order_walking_route,
    route_path,
    route_points,
)
from food_tour.walking import WalkingRoute, fetch_walking_route  # noqa: E402
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

STEP_LABELS = (
    "Instructions",
    "1. Plan your tour",
    "2. Preview the map",
    "3. Details & stats",
)
CLOSE_TOGETHER = "Close to each other"
NEAR_START = "Close to a starting point"


def change_step(step: int) -> None:
    st.session_state["active_step"] = step


def load_session_csv(upload, loader, cache_key):
    """Reuse parsed rows within this session until the uploaded file changes."""
    if upload is None:
        st.session_state.pop(cache_key, None)
        return None, None

    cached = st.session_state.get(cache_key)
    if cached is None or cached[0] != upload.file_id:
        try:
            cached = (upload.file_id, loader(upload), None)
        except (DatasetValidationError, UnicodeDecodeError) as error:
            cached = (upload.file_id, None, str(error))
        st.session_state[cache_key] = cached
    return cached[1], cached[2]


def show_restaurant_preview(tour_stops, candidates, one_per_chain):
    """Show the selected stops and up to five other ranked candidates."""
    def restaurant_key(row):
        if one_per_chain:
            return row_chain_key(row)
        return (row["name"], row["address"], row["latitude"], row["longitude"])

    selected = {restaurant_key(row) for row in tour_stops}
    alternatives = [row for row in candidates if restaurant_key(row) not in selected][:5]
    rows = []
    for restaurants, status, css_class in (
        (tour_stops, "Selected", ""),
        (alternatives, "Alternate", ' class="alternate"'),
    ):
        for row in restaurants:
            rows.append(
                f"<tr{css_class}><td>{escape(row['name'])}</td>"
                f"<td>{escape(row['address'])}</td>"
                f"<td>{row['recommendation score']:.1f}</td><td>{status}</td></tr>"
            )
    st.html(
        '<table class="restaurant-preview" aria-label="Selected restaurants and alternatives">'
        '<thead><tr><th scope="col">Restaurant</th><th scope="col">Address</th>'
        '<th scope="col">Score</th><th scope="col">Status</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


# Free CARTO basemap built on OpenStreetMap data; no API key needed.
CARTO_VOYAGER_STYLE = (
    "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json"
)
ROUTE_COLOR = [44, 98, 155]
START_COLOR = [166, 35, 54]


class RoutingUnavailable(Exception):
    """Raised so a failed routing request is not cached."""


@st.cache_data(ttl=24 * 60 * 60, show_spinner="Finding walking routes...")
def _cached_walking_route(points: tuple[tuple[float, float], ...]) -> WalkingRoute:
    walking = fetch_walking_route(list(points))
    if walking is None:
        raise RoutingUnavailable
    return walking


def get_walking_route(
    points: list[tuple[float, float]],
) -> WalkingRoute | None:
    """Street walking route for ``points``, cached for a day; None on failure."""
    if len(points) < 2:
        return None
    rounded = tuple((round(lat, 6), round(lng, 6)) for lat, lng in points)
    try:
        return _cached_walking_route(rounded)
    except RoutingUnavailable:
        return None


def show_tour_map(
    route_rows: list[dict],
    start: tuple[float, float] | None,
    start_label: str,
    path: list[list[float]],
) -> None:
    """Draw the numbered route on a key-free map, with Google Maps links."""
    markers = [
        {**marker, "color": START_COLOR if marker["is_start"] else ROUTE_COLOR}
        for marker in map_markers(route_rows, start, start_label)
    ]
    view = map_view(
        [(row["latitude"], row["longitude"]) for row in markers]
        + [(latitude, longitude) for longitude, latitude in path]
    )
    layers = [
        pdk.Layer(
            "PathLayer",
            data=[{"path": path}],
            get_path="path",
            get_color=ROUTE_COLOR,
            width_min_pixels=4,
        ),
        pdk.Layer(
            "ScatterplotLayer",
            data=markers,
            get_position=["longitude", "latitude"],
            get_fill_color="color",
            get_line_color=[255, 255, 255],
            stroked=True,
            line_width_min_pixels=2,
            get_radius=25,
            radius_min_pixels=13,
            pickable=True,
        ),
        pdk.Layer(
            "TextLayer",
            data=markers,
            get_position=["longitude", "latitude"],
            get_text="label",
            get_size=14,
            get_color=[255, 255, 255],
            get_text_anchor=pdk.types.String("middle"),
            get_alignment_baseline=pdk.types.String("center"),
        ),
    ]
    st.pydeck_chart(
        pdk.Deck(
            layers=layers,
            initial_view_state=pdk.ViewState(**view),
            map_provider="carto",
            map_style=CARTO_VOYAGER_STYLE,
            tooltip={"html": "<b>{title}</b><br/>{address}<br/>{leg}"},
        )
    )

    links = google_maps_walking_urls(route_rows, start)
    if len(links) == 1:
        st.link_button("Open walking route in Google Maps", links[0])
    else:
        link_columns = st.columns(len(links))
        for part, (column, link) in enumerate(zip(link_columns, links), start=1):
            column.link_button(
                f"Open part {part} of {len(links)} in Google Maps", link
            )
        st.caption(
            f"Google Maps links hold up to {GOOGLE_MAPS_MAX_POINTS} points, "
            f"so the route is split into {len(links)} links. Each part starts "
            f"where the previous one ended."
        )
st.set_page_config(
    page_title="Philly Food Forays",
    page_icon="🥨",
    layout="wide",
)

st.html(APP_DIR / "assets" / "theme.css")

restaurant_upload = st.session_state.get("restaurant_upload")
review_upload = st.session_state.get("review_upload")
sentiment_upload = st.session_state.get("sentiment_upload")
restaurants, restaurant_error = load_session_csv(
    restaurant_upload, load_restaurants, "parsed_restaurants"
)
food_sentiment, sentiment_error = load_session_csv(
    sentiment_upload, load_food_sentiment, "parsed_food_sentiment"
)
ready = restaurants is not None and food_sentiment is not None
active_step = st.session_state.get("active_step", 0) if ready else 0
st.session_state["active_step"] = active_step

with st.container(key="tour-step-bar"):
    for step, column in enumerate(st.columns(4, gap="small")):
        column.button(
            STEP_LABELS[step],
            key=f"step_{step}",
            type="primary" if step == active_step else "secondary",
            disabled=step > 0 and not ready,
            width="stretch",
            on_click=change_step,
            args=(step,),
        )

# Keep the upload and filter widgets mounted to retain their session state.
# Hide the inactive panel visually and from the accessibility tree.
if active_step != 0:
    st.html("<style>.st-key-instructions-panel { display: none; }</style>")
if active_step != 1:
    st.html("<style>.st-key-planning-panel { display: none; }</style>")

with st.container(key="tour-page-layout"):
    left_rail, content, right_rail = st.columns([1, 8, 1], gap="small")
    if active_step > 0:
        left_rail.button(
            ("← Instructions", "← Edit filters", "← Back to map")[active_step - 1],
            key="previous_step",
            width="stretch",
            on_click=change_step,
            args=(active_step - 1,),
        )
    if active_step < 3:
        right_rail.button(
            ("Start planning →", "View map →", "View details →")[active_step],
            key="next_step",
            width="stretch",
            type="primary",
            disabled=not ready,
            on_click=change_step,
            args=(active_step + 1,),
        )

with content, st.container(key="instructions-panel"):
    if active_step == 0:
        bell_image = b64encode((APP_DIR / "assets" / "liberty-bell.webp").read_bytes()).decode("ascii")
        st.html(
            f"""
            <div class="food-forays-hero">
              <img src="data:image/webp;base64,{bell_image}" alt="" class="food-forays-bell">
              <div class="food-forays-intro">
                <h1>Philly Food Forays</h1>
                <p>Find Philly’s signature foods and turn your favorite stops into a walking tour.</p>
              </div>
            </div>
            """
        )

    st.header("Instructions")
    st.markdown(
        "1. **Plan your tour.** Pick a Philly food and set your visit, distance, and stop preferences.\n"
        "2. **Preview the map.** Explore the walking route and return to the planner to adjust it.\n"
        "3. **Details & stats.** Browse restaurant rankings, the itinerary, and review data."
    )
    st.markdown("**Upload the restaurant and food sentiment CSVs to start.**")
    st.caption("Your uploaded files are used only for the active Streamlit session.")

    with st.expander("How to prepare the files", expanded=False):
        st.code(
            "python3 scripts/preprocess_yelp.py \\\n  --businesses yelp_academic_dataset_business.json \\\n  --reviews yelp_academic_dataset_review-001.json",
            language="bash",
        )

    # The uploaders' keys hold the current files in session state before the
    # widgets render, so the expander can stay open until both required files
    # are in and then collapse on the next rerun.
    with st.expander("Upload files here", expanded=not ready):
        upload_column_a, upload_column_b, upload_column_c = st.columns(3)
        with upload_column_a:
            st.file_uploader(
                "Philadelphia restaurant CSV",
                type=["csv"],
                max_upload_size=25,
                key="restaurant_upload",
                help="Expected file: philadelphia_restaurants.csv (approximately 6.35 MB).",
            )
        with upload_column_b:
            st.file_uploader(
                "Philadelphia review JSONL (optional; needed only for training/validation)",
                type=["jsonl"],
                max_upload_size=650,
                key="review_upload",
                help="Expected file: philadelphia_reviews.jsonl (approximately 535 MB).",
            )
        with upload_column_c:
            st.file_uploader(
                "Food sentiment summary CSV",
                type=["csv"],
                max_upload_size=25,
                key="sentiment_upload",
                help="Expected file: food_sentiment.csv, created by build_food_sentiment.py.",
            )
    if restaurant_error or sentiment_error:
        for error in (restaurant_error, sentiment_error):
            if error:
                st.error(error)
    elif ready:
        st.success("Required files are ready. Select Start planning or Step 1.")

if not ready:
    st.stop()

with content, st.container(key="planning-panel"):
    st.header("1. Plan your tour")
    with st.container(border=True):
        st.markdown("**Tune your search**")
        st.caption(
            "Pick a food, then adjust the filters. Matches update as you go."
        )

        basics_food, basics_reviews, basics_toggles = st.columns([2, 2, 1.6])
        selected_food = basics_food.selectbox(
            "Which Philadelphia food?", list(FOOD_ALIASES)
        )
        minimum_mentions = basics_reviews.slider(
            "Minimum matching food reviews", 1, 100, 5
        )
        with basics_toggles:
            open_only = st.toggle("Show only businesses marked open", value=True)
            one_per_chain = st.toggle(
                "Show one location per chain",
                value=True,
                help=(
                    "Chains such as Wawa appear once, using the location closest "
                    "to the other top-ranked spots."
                ),
            )

    st.markdown("**Optional filters**")
    visit_panel, planner_distance_panel = st.columns(2)
    with visit_panel, st.container(border=True, key="visit-filters"):
        filter_by_visit = st.toggle("Filter by planned visit day and time", value=False)
        visit_day = st.selectbox("Day visiting", WEEKDAYS, disabled=not filter_by_visit)
        visit_column_a, visit_column_b = st.columns(2)
        visit_start_time = visit_column_a.selectbox(
            "Start Time",
            VISIT_TIMES[:-1],
            index=VISIT_TIMES.index(time(12, 0)),
            format_func=format_visit_time,
            disabled=not filter_by_visit,
        )
        end_time_options = [value for value in VISIT_TIMES if value > visit_start_time]
        default_end_time = time(17, 0)
        if default_end_time not in end_time_options:
            default_end_time = end_time_options[-1]
        visit_end_time = visit_column_b.selectbox(
            "End Time",
            end_time_options,
            index=end_time_options.index(default_end_time),
            format_func=format_visit_time,
            disabled=not filter_by_visit,
        )
        minutes_per_stop = st.slider(
            "Minutes per stop (eating plus walking)",
            15,
            120,
            DEFAULT_MINUTES_PER_STOP,
            step=5,
            disabled=not filter_by_visit,
        )

if active_step == 2:
    content.header("2. Preview the map")
distance_panel = content if active_step == 2 else planner_distance_panel

with distance_panel, st.container(border=True, key="distance-filters"):
    filter_by_distance = st.toggle(
        "Keep top spots within walking distance", key="filter_by_distance"
    )
    distance_mode = st.radio(
        "Measure distance",
        [CLOSE_TOGETHER, NEAR_START],
        horizontal=True,
        key="distance_mode",
        disabled=not filter_by_distance,
        help=(
            "Close to each other: every stop is within the limit of "
            "every other stop. Close to a starting point: every stop "
            "is within the limit of the chosen start."
        ),
    )
    distance_column_a, distance_column_b = st.columns(2)
    max_miles = distance_column_a.slider(
        "Maximum distance (miles)", 0.25, 5.0, 1.0,
        step=0.25,
        key="max_miles",
        disabled=not filter_by_distance,
    )
    max_stops = distance_column_b.slider(
        "Number of stops", 1, 15, 5, key="max_stops"
    )
    start_name = st.selectbox(
        "Starting point",
        [TOP_RANKED_START, *LANDMARKS],
        key="start_name",
        disabled=not (filter_by_distance and distance_mode == NEAR_START),
    )

ranked = rank_restaurants(
    restaurants,
    food_sentiment,
    selected_food,
    minimum_mentions,
    open_only,
    visit_day if filter_by_visit else None,
    visit_start_time if filter_by_visit else None,
    visit_end_time if filter_by_visit else None,
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

tour_stops = filtered[:max_stops]
if active_step == 1:
    with content:
        st.subheader("Restaurant preview")
        st.caption(f"{len(tour_stops):,} tour picks · {len(filtered):,} matching restaurants")
        if tour_stops:
            if filter_by_distance and distance_mode == CLOSE_TOGETHER:
                candidates = collapse_chains(ranked) if one_per_chain else ranked
            else:
                candidates = filtered
            show_restaurant_preview(tour_stops, candidates, one_per_chain)
        else:
            st.info("No restaurants match your filters.")

route_rows = []
if filtered and active_step in (2, 3):
    route_start = None
    route_start_label = ""
    if (
        filter_by_distance
        and distance_mode == NEAR_START
        and start_name != TOP_RANKED_START
    ):
        route_start = LANDMARKS[start_name]
        route_start_label = start_name

    if filter_by_visit:
        plan = plan_visit_order(
            tour_stops,
            visit_day,
            visit_start_time,
            visit_end_time,
            minutes_per_stop,
        )
        scheduled = [row for row in plan if row[VISIT_ORDER_COLUMN] is not None]
        skipped = [row for row in plan if row[VISIT_ORDER_COLUMN] is None]
        ordered_stops = scheduled
        walking = get_walking_route(route_points(ordered_stops, route_start))
        route_rows = add_route_legs(ordered_stops, route_start, walking)
        table_rows = route_rows + skipped
        table_columns = [
            VISIT_ORDER_COLUMN,
            ARRIVAL_COLUMN,
            "name",
            "address",
            f"{visit_day} hours",
            "recommendation score",
            LEG_COLUMN,
            CUMULATIVE_COLUMN,
        ]
        order_column = VISIT_ORDER_COLUMN
    else:
        ordered_stops = order_walking_route(tour_stops, route_start)
        walking = get_walking_route(route_points(ordered_stops, route_start))
        route_rows = add_route_legs(ordered_stops, route_start, walking)
        table_rows = route_rows
        table_columns = [
            WALK_ORDER_COLUMN,
            "name",
            "address",
            "recommendation score",
            LEG_COLUMN,
            CUMULATIVE_COLUMN,
        ]
        order_column = WALK_ORDER_COLUMN

if active_step == 2:
    with content:
        if not filtered:
            st.info("No restaurants match your filters. Select Edit filters to adjust your search.")
        elif not route_rows:
            st.info("No stops fit the visit window. Select Edit filters to adjust your visit.")
        if route_rows:
            total_miles = route_rows[-1][CUMULATIVE_COLUMN]
            if walking is not None:
                metric_a, metric_b, _ = st.columns(3)
                metric_a.metric("Total walk", f"{total_miles:.2f} mi")
                metric_b.metric("Walking time", f"{walking.total_minutes:.0f} min")
                path = walking.path
            else:
                st.metric("Total walk (straight line)", f"{total_miles:.2f} mi")
                path = route_path(route_rows, route_start)
            map_panel, stops_panel = st.columns([3, 1], gap="medium")
            with map_panel:
                show_tour_map(route_rows, route_start, route_start_label, path)
            with stops_panel:
                st.subheader("Stops")
                for row in route_rows:
                    st.text(f"{row[order_column]}. {row['name']}")
            if walking is not None:
                st.caption(
                    "The map line, miles, and minutes follow walkable streets and "
                    "paths from OpenStreetMap, routed by the free FOSSGIS OSRM "
                    "service (routing.openstreetmap.de). Times assume a steady "
                    "walking pace and leave out time spent eating. The Google Maps "
                    "link opens the same stops in the same order, with Google's "
                    "own directions."
                )
            elif len(route_points(route_rows, route_start)) > 1:
                st.info(
                    "Street walking routes are unavailable right now (the free "
                    "routing service didn't respond), so the map shows straight "
                    "lines between stops. Real walks are usually 20-40% longer. "
                    "The Google Maps link still gives turn-by-turn walking "
                    "directions."
                )

if active_step == 3:
    with content:
        st.header("3. Details & stats")
        open_count = sum(row.get("is_open") == "1" for row in restaurants)
        metric_a, metric_b, metric_c = st.columns(3)
        metric_a.metric("Restaurants", f"{len(restaurants):,}")
        metric_b.metric("Marked open", f"{open_count:,}")
        metric_c.metric("Uploaded size", f"{restaurant_upload.size / 1_000_000:.1f} MB")

        st.subheader("Restaurant rankings")
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

        if filtered:
            st.subheader("Tour itinerary")
            if walking is not None:
                table_columns.insert(table_columns.index(CUMULATIVE_COLUMN), WALK_MINUTES_COLUMN)
            if any(DISTANCE_COLUMN in row for row in table_rows):
                table_columns.append(DISTANCE_COLUMN)

            st.dataframe(
                [{column: row.get(column) for column in table_columns} for row in table_rows],
                width="stretch",
                hide_index=True,
                column_config={
                    order_column: st.column_config.NumberColumn(format="%d"),
                    LEG_COLUMN: st.column_config.NumberColumn(format="%.2f mi"),
                    CUMULATIVE_COLUMN: st.column_config.NumberColumn(format="%.2f mi"),
                    WALK_MINUTES_COLUMN: st.column_config.NumberColumn(format="%d min"),
                    DISTANCE_COLUMN: st.column_config.NumberColumn(format="%.2f mi"),
                },
            )
            start_note = (
                f" The walk starts at {route_start_label}." if route_start else ""
            )
            if filter_by_visit:
                st.caption(
                    f"Starting at {format_visit_time(visit_start_time)}, each next "
                    f"stop is the one you can visit soonest: places open at the start "
                    f"come first, and later-opening places are scheduled after they "
                    f"open. Ties go to the place that closes sooner, then the "
                    f"higher-ranked one. Every stop is reached before it closes and "
                    f"before {format_visit_time(visit_end_time)}. Times are "
                    f"approximate.{start_note}"
                )
                unscheduled = unscheduled_message(plan)
                if unscheduled:
                    st.warning(unscheduled)
            else:
                first_step = (
                    f"starts at {route_start_label}"
                    if route_start
                    else "tries each stop as the first one"
                )
                st.caption(
                    f"Stops are ordered to keep the walk short: the app {first_step}, "
                    "walks to the nearest unvisited stop each time, then reverses any "
                    "stretch of the route that makes it shorter. The order is chosen "
                    "with straight-line distances"
                    + ("; the miles shown are along the streets." if walking else ".")
                )
        st.subheader("Review data")
        if review_upload is None:
            st.info(
                "The review file is optional for browsing restaurants. Upload it when "
                "running sentiment analysis or other review-based features."
            )
        else:
            review_key = review_upload.file_id
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
