# Philly Food Forays: Features and ML Summary

## Project purpose

Philly Food Forays recommends Philadelphia restaurants for themed food tours.
The first version supports seven local foods:

- Philly Cheesesteak
- Roast Pork Sandwich
- Hoagie
- Philadelphia Soft Pretzel
- Tomato Pie
- Scrapple
- Water Ice

The project intentionally uses small, explainable models and rules suitable for
an MSBA course project.

## Data preparation

`scripts/preprocess_yelp.py` streams Yelp's newline-delimited JSON files without
loading them fully into memory. It:

1. Selects Philadelphia food businesses.
2. Includes restaurants and relevant specialty categories such as bakeries,
   dessert shops, pretzel shops, delis, food stands, and ice-cream shops.
3. Extracts only reviews belonging to selected businesses.
4. Produces a business CSV, review JSONL, and validation summary.

The Yelp source and derived datasets remain local and are excluded from Git.

## Signature-food identification

`src/food_tour/food_matching.py` uses transparent NLP normalization and matching:

- Case-insensitive matching
- Punctuation and accent normalization
- Curated alternative names, including `Italian ice`, `wooder ice`, and `gelati`
- Plural forms
- Conservative fuzzy matching for modest misspellings
- Sentence extraction so sentiment is evaluated around the named food

This component is rule-based by design. It is easier to inspect and explain
than a large language model and does not require an API.

## Sentiment model

`scripts/train_sentiment.py` trains a three-class sentiment classifier:

- 1-2 Yelp stars: negative
- 3 Yelp stars: neutral
- 4-5 Yelp stars: positive

The model is a scikit-learn pipeline containing TF-IDF text features and
logistic regression. Training uses a reproducible balanced sample and reports
precision, recall, F1, accuracy, and a confusion matrix. The current baseline
achieved approximately 77% accuracy on a balanced local test set.

## Food-level aggregation

`scripts/build_food_sentiment.py`:

1. Finds supported foods mentioned in each review.
2. Extracts only the sentence or sentences mentioning each food.
3. Predicts sentiment for those snippets.
4. Aggregates positive, neutral, and negative review counts by business and food.
5. Creates the compact `food_sentiment.csv` used by the app.

## Restaurant ranking

`src/food_tour/ranking.py` creates an explainable recommendation score:

- 45% volume-adjusted food-specific sentiment
- 40% number of food-specific reviews
- 15% overall Yelp review volume

Bayesian adjustment prevents a restaurant with a tiny perfect sample from
outranking an established restaurant with hundreds of strong reviews.
Logarithmic volume scaling prevents the largest restaurant from winning only
because it has the most reviews.

## Streamlit application

The app currently provides:

- Temporary upload of locally generated datasets, with the three uploaders
  side by side in a collapsible "Upload files here" section that starts open
  and collapses once the restaurant and food sentiment CSVs are uploaded
- A bordered "Tune your search" settings panel under "Explore signature
  foods" that lays the search controls out horizontally instead of in one
  long column. The top row holds the food picker, the minimum food reviews
  slider, and the open-only and one-location-per-chain toggles. Below a
  divider, the visit day and time filter and the walking distance filter sit
  side by side, and each one's sub-controls (day, start and end time;
  distance mode, maximum miles, number of stops or starting point) appear
  inside its own half of the panel when its toggle is on
- Selection from the seven supported foods
- Open-business filtering
- Readable weekly opening hours from the Yelp business dataset
- Optional visit-window filtering that includes restaurants open at any point
  between the selected start and end times
- Adjustable minimum number of food-specific reviews
- One location per chain restaurant, choosing the location nearest the other
  top picks (see below)
- Optional distance filtering that keeps recommended spots within walking
  distance (see below)
- A "Your tour" section with a map of the stops numbered in walking order,
  straight-line miles per leg and in total, and a link that opens the same
  route as walking directions in Google Maps (see below)
- A suggested visit order with approximate arrival times, based on each
  stop's opening hours within the visit window (see below)
- Ranked restaurant results with transparent component metrics
- Optional upload and validation of the full review JSONL

Uploaded files are session inputs and are not committed to GitHub.
Opening hours reflect the Yelp Open Dataset snapshot rather than live business
hours, and businesses without recorded hours are omitted when visit filtering
is enabled.

## Distance filtering between top locations

`src/food_tour/distance.py` adds a walking-distance filter that runs after
ranking, so recommendation scores stay comparable with and without it.
Distances are straight-line (haversine) miles computed from Yelp latitude and
longitude; no routing service or API key is needed. The app offers two modes:

- **Close to each other.** Restaurants are taken in ranking order, and each one
  joins the tour only if it is within the chosen limit of every stop already
  selected. The #1 restaurant is always the first stop, the largest gap
  between any two stops never exceeds the limit, and a "Number of stops"
  slider caps the tour length (2 to 15). When fewer restaurants fit than the
  slider asks for, the app shows a warning such as "You asked for 5 stops, but
  only 3 restaurants fit your filters," with a hint to loosen the distance,
  minimum reviews, or visit window.
- **Close to a starting point.** Keeps every ranked restaurant within the limit
  of a start: the top-ranked restaurant or one of eight landmarks (City Hall,
  Reading Terminal Market, Independence Hall, Italian Market, South Street,
  30th Street Station, Philadelphia Museum of Art, Rittenhouse Square).

The maximum distance ranges from 0.25 to 5 miles in quarter-mile steps. Results
gain a `miles from start` column, and the caption reports the farthest pair of
stops (or the farthest stop from the start). Walking routes are typically
20-40% longer than straight-line distance, which the app notes for users.

This answers the instructor's question of what a simple distance filter offers
compared with K-means: it directly chooses which top places to visit near each
other or near the user, while clustering only groups places by location.

Tested with the team's Philadelphia files (6,159 restaurants). For Philly
Cheesesteak with a 1-mile, 5-stop limit, the filter returns five spots whose
farthest pair is 0.97 miles apart. Starting at the Italian Market with a 1-mile
radius keeps 108 of 535 cheesesteak restaurants. Unit tests cover the distance
formula, both modes, the stop limit, the fewer-stops-than-requested message,
and empty inputs.

## One location per chain

`src/food_tour/chains.py` keeps a tour from listing the same chain several
times (for example, three Wawas). A "Show one location per chain" toggle, on by
default, merges rows whose names match after ignoring case, accents,
apostrophes, punctuation, a leading "The", and "&" versus "and". Names must
otherwise match, so "Wawa" and "Wawa Welcome America" stay separate.

The chain keeps the rank of its best-reviewed location, and the app shows the
location closest to the rest of the tour, along with that location's own
scores. A `chain locations` column counts how many locations were merged, and a
caption notes how many chains were collapsed. How "closest" is measured depends
on the distance setting:

- **No distance filter.** The chosen location has the smallest average
  straight-line distance to the best location of each of the top 10 other
  restaurants or chains.
- **Close to each other.** Each chain is considered once, at the rank of its
  best location. Among its locations within the limit of every stop already
  chosen, the one with the smallest average distance to those stops joins the
  tour, so a chain is skipped only when none of its locations fit. If the chain
  is the first stop, the top 10 other restaurants are the reference instead.
- **Close to a starting point.** Locations outside the radius are dropped
  first, then the remaining locations of each chain are compared as in the
  no-filter case.

Unit tests in `tests/test_chains.py` cover name matching, the location choice
in each mode, rank preservation, unnamed rows, and empty inputs.

## Visit order by opening hours

`src/food_tour/schedule.py` turns the tour into a timed plan when the visit
day and time filter is on. The "Your tour" table below the ranked results then
shows a `visit order`, an approximate `arrive around` time, the day's hours,
the score, and the leg miles described in the next section (plus
`miles from start` when a distance filter is on).
The stops scheduled are the tour picked by the "Close to each other"
filter, or otherwise the top restaurants, with a "Stops in tour" slider
(up to 15, default 5).

The plan starts at the window's start time and repeatedly picks the stop that
can be visited soonest:

- Restaurants open at the start come first. A restaurant that opens later is
  scheduled once it opens, and the plan waits for it only when nothing else is
  open.
- Among stops available at the same time, the one that closes sooner goes
  first, then the higher-ranked one.
- Every stop must be reached before it closes and before the window ends. Each
  visit, including walking to the next stop, takes a fixed "Minutes per stop"
  (15 to 120, default 45).
- Stops that cannot be reached in the window are listed last as "Doesn't fit
  window", with a warning suggesting fewer minutes per stop, fewer stops, or a
  later end time.

Overnight hours from the previous day count (a Sunday 8 PM–3 AM bar is open at
1 AM on Monday). Times are approximate because walking time between stops is
folded into the per-stop minutes rather than routed. The raw Yelp hours travel
with each ranked row in a hidden `hours_json` column.

Unit tests in `tests/test_schedule.py` cover open-at-start ordering, waiting
for a later opening, the closing-time and rank tie-breaks, stops that close or
fall past the window, overnight hours, and invalid inputs.

## Tour map and walking route

`src/food_tour/route.py` powers the "Your tour" section, which appears below
the ranked results whenever any restaurants match. The tour is the stops
picked by the "Close to each other" filter, or otherwise the top restaurants,
with a "Stops in tour" slider (up to 15, default 5).

**Visit order.**

- When the visit day and time filter is on, the stops keep the opening-hours
  order from the previous section, and stops that don't fit the window are
  left off the map.
- Otherwise the app builds a short walking route. It tries each stop as the
  first one, walks to the nearest unvisited stop each time (nearest
  neighbor), then reverses any stretch of the route that makes it shorter
  (2-opt), and keeps the shortest result. The route is one-way and does not
  return to the first stop. With up to 15 stops this takes well under a
  second.
- When "Close to a starting point" uses a landmark, the walk starts at that
  landmark, which appears on the map as a blue "S" marker.

**Table and map.** The table adds a `walk order` (in walking mode), a
`walk from previous` column with each leg's straight-line miles, and a
`walked so far` running total. A metric shows the total walk. The map draws
numbered markers (1, 2, 3, ...) connected by lines in visiting order;
hovering a marker shows the name, address, and leg distance.

**Why not an embedded Google map.** Google's embedded maps and its
JavaScript, Directions, and Distance Matrix APIs all need a Google Cloud API
key with billing turned on, and the key would have to be stored and kept out
of the repository. Instead:

- The map uses pydeck (already installed with Streamlit) on CARTO's free
  basemap, which is built on OpenStreetMap data and needs no key or account.
- An "Open walking route in Google Maps" button uses Google's documented,
  key-free directions link
  (`https://www.google.com/maps/dir/?api=1&origin=...&destination=...&waypoints=...&travelmode=walking`)
  with each stop's Yelp coordinates, in the same order. Google then shows real
  street-by-street walking directions, distance, and time. One link holds at
  most 11 points (origin, destination, and 9 stops in between), so a longer
  route is split into parts, each starting where the previous one ended.

Distances on the map and in the table are straight-line miles, which are
usually 20-40% shorter than the real walk; the app says so next to the map. A
free routing service (for example a public OSRM server) could supply walking
distances, but public servers are rate-limited and not meant for production,
so it is left as a future option.

Unit tests in `tests/test_route.py` cover the walking order (including a
fixed start and text coordinates from the CSV), the 2-opt step, leg and
total distances, the Google Maps links (waypoint order, start as origin,
splitting long routes, single stops), and the map markers, line, and zoom.

## Planned next features

- Geographic clustering of suitable restaurants
- Calendar-date filtering for holidays and special closures
- Visit-order refinements: use walking distance between stops instead of a
  fixed minutes-per-stop pace, and try alternative orders so a stop that closes
  early is never crowded out
- User control over rating versus travel-distance preference
- A compact food-tour recommendation view
- Smarter "close to each other" seeding: try each of the top 10 restaurants as
  the first stop and keep the group with the highest combined score. Today the
  #1 spot anchors the tour, so a highly ranked outlier (for cheesesteaks,
  Dalessandro's in Roxborough) pulls the tour away from denser areas such as
  South Philadelphia.
- Custom starting point: type an address or use the browser's location instead
  of picking a landmark
- Walking distance and time from a routing service instead of straight-line
  miles
- Review food-matching false positives found while testing distance filters
  (for example, Morimoto appearing among Water Ice results)
- Load files automatically from `data/processed/` when running locally, so
  teammates skip the upload step
