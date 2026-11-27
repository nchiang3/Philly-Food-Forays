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

- Temporary upload of locally generated datasets
- Selection from the seven supported foods
- Open-business filtering
- Readable weekly opening hours from the Yelp business dataset
- Optional visit-window filtering that includes restaurants open at any point
  between the selected start and end times
- Adjustable minimum number of food-specific reviews
- Optional distance filtering that keeps recommended spots within walking
  distance (see below)
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
  slider caps the tour length (2 to 15).
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
formula, both modes, the stop limit, and empty inputs.

## Planned next features

- Geographic clustering of suitable restaurants
- Interactive map display
- Calendar-date filtering for holidays and special closures
- Visit-order optimization that prioritizes restaurants open at the start while
  scheduling later-opening options within the selected time window
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
