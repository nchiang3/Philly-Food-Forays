# Philly-Food-Forays
# Food Tour Optimizer

## Project Overview

The Food Tour Optimizer is a proposed Streamlit application designed to help tourists discover highly rated restaurants specializing in a particular type of food within a walkable area.

When visiting a city known for a specific dish, tourists may struggle to identify the best restaurants and determine which areas of the city offer the most convenient options.

Our goal is to use machine learning to identify restaurants with positive customer feedback and recommend geographic areas where tourists can explore multiple restaurants without traveling long distances.

## Dataset

We plan to use the **Philadelphia restaurant data from the Yelp Open Dataset**.

In our initial review of the dataset, we identified several useful attributes:

- **Latitude and longitude:** Restaurant locations for geographic clustering
- **Review text:** Customer feedback for sentiment classification
- **Stars:** Customer ratings for evaluating restaurant quality
- **Categories:** Restaurant classifications for identifying relevant food types

We will use these attributes to filter restaurants by food category, analyze customer sentiment, and identify geographic clusters of restaurants.

## Machine Learning Approach

### 1. Sentiment Classification

We plan to use Natural Language Processing (NLP) to classify customer reviews based on their sentiment.

Reviews will be categorized as:
- Positive
- Neutral
- Negative

We will explore classification methods such as TF-IDF with Logistic Regression to analyze review text.

The resulting sentiment labels will help us evaluate customer satisfaction and identify restaurants with favorable feedback.

### 2. K-Means Clustering

We plan to use K-means clustering to group restaurants based on their geographic locations.

Using latitude and longitude, the model will identify clusters of restaurants within Philadelphia.

We can then evaluate these clusters based on restaurant ratings, review sentiment, and the number of relevant restaurants in each area.

The goal is to recommend **the best areas of the city for users to begin their food tour**, balancing restaurant quality with geographic convenience.

## Proposed Application Features

The Streamlit application will allow users to:

1. Select a food category or type of cuisine.
2. View restaurants matching their selection.
3. Explore geographic clusters of restaurants.
4. See recommended areas based on restaurant ratings and customer sentiment.
5. View restaurant locations on an interactive map.

## Technology Stack

| Component | Technology |
|---|---|
| Programming language | Python |
| Web application | Streamlit |
| Dataset | Yelp Open Dataset |
| Data processing | pandas, NumPy |
| Sentiment classification | scikit-learn / NLP |
| Geographic clustering | K-means (scikit-learn) |
| Mapping | Folium or similar |
| Version control | GitHub |
| Deployment | Streamlit Community Cloud |

## Proposed Project Workflow

**Step 1: Data Preparation**
- Load and filter the Yelp dataset for Philadelphia.
- Identify restaurants by category.
- Merge restaurant information with customer reviews.
- Clean and prepare review text for analysis.

**Step 2: Sentiment Classification**
- Develop a model to classify customer reviews.
- Apply sentiment labels to restaurant reviews.
- Summarize sentiment results by restaurant.

**Step 3: Geographic Clustering**
- Apply K-means clustering to restaurant coordinates.
- Identify geographic concentrations of restaurants.
- Compare clusters based on restaurant ratings and sentiment.

**Step 4: Streamlit Application**
- Build an interface for selecting food categories.
- Display restaurant recommendations and cluster results.
- Visualize restaurant locations and recommended food-tour areas on a map.

**Step 5: Deployment**
- Deploy the application using Streamlit Community Cloud.
- Test the user interface and model outputs.

## Project Scope

For the initial version, we will focus exclusively on Philadelphia using the Yelp Open Dataset.

Our primary objective is to demonstrate how **sentiment classification and K-means clustering** can work together to recommend food-tour areas.

Optimized walking routes, live restaurant data, and price prediction are potential future enhancements, but are not part of the initial project scope.

## Project Status

Planning and initial dataset exploration.

## Team

Yue Teng
Lindsay Nielsen
Nicole Chiang
