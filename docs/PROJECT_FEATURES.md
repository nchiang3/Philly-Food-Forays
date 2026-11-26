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
- Adjustable minimum number of food-specific reviews
- Ranked restaurant results with transparent component metrics
- Optional upload and validation of the full review JSONL

Uploaded files are session inputs and are not committed to GitHub.

## Planned next features

- Geographic clustering of suitable restaurants
- Interactive map display
- Date and business-hours filtering
- User control over rating versus travel-distance preference
- A compact food-tour recommendation view
