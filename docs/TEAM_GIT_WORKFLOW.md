# Team Setup and Git Workflow

This guide explains how each teammate can work on Philly Food Forays without
overwriting someone else's changes.

## 1. Install the basic tools

Each teammate needs:

- Git
- Python 3.11 or newer
- A GitHub account with access to the repository
- The Yelp Open Dataset downloaded independently under Yelp's terms

Confirm Git is installed:

```bash
git --version
```

## 2. Clone the repository once

Choose a folder on the computer, open Terminal there, and run:

```bash
git clone git@github.com:nchiang3/Philly-Food-Forays.git
cd Philly-Food-Forays
```

If SSH has not been configured with GitHub, use the HTTPS clone URL shown on
the repository's **Code** menu or configure a GitHub SSH key first.

## 3. Create the local Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

On Windows PowerShell, activate with:

```powershell
.venv\Scripts\Activate.ps1
```

The `.venv` folder is ignored by Git and stays on each teammate's computer.

## 4. Add the Yelp files locally

Place the downloaded Yelp files under `data/raw/`:

```text
data/raw/yelp_academic_dataset_business.json
data/raw/yelp_academic_dataset_review-001.json
```

Raw and processed Yelp data are ignored by Git. Each teammate generates local
processed files with:

```bash
python3 scripts/preprocess_yelp.py \
  --businesses data/raw/yelp_academic_dataset_business.json \
  --reviews data/raw/yelp_academic_dataset_review-001.json

python3 scripts/train_sentiment.py \
  --reviews data/processed/philadelphia_reviews.jsonl

python3 scripts/build_food_sentiment.py \
  --reviews data/processed/philadelphia_reviews.jsonl
```

## 5. Start each change from an updated `main`

Local files do **not** update automatically when a teammate pushes changes.
Before starting work, run:

```bash
git switch main
git pull origin main
```

`git pull` downloads and applies changes that have been pushed and merged into
GitHub's `main` branch. Uncommitted local edits can block or complicate a pull,
so commit or stash work before pulling.

## 6. Create a branch for the task

Use a short descriptive branch name:

```bash
git switch -c feature/map-clustering
```

Examples:

- `feature/map-clustering`
- `feature/business-hours`
- `fix/water-ice-matching`
- `docs/presentation-notes`

Branches let teammates work independently without changing `main` immediately.

## 7. Make and test the change

Inspect changes frequently:

```bash
git status
git diff
```

Run the automated tests before committing:

```bash
python3 -m unittest discover -s tests -v
```

Run the app when the change affects the interface:

```bash
streamlit run app.py
```

## 8. Commit and push the branch

Stage only the intended files:

```bash
git add path/to/changed_file.py tests/test_changed_feature.py
git commit -m "Add map clustering controls"
git push -u origin feature/map-clustering
```

Do not use `git add .` without first checking `git status`. Never force-add raw
Yelp data, secrets, `.venv`, trained models, or generated datasets.

## 9. Open and merge a pull request

On GitHub:

1. Open the repository.
2. Select **Compare & pull request** for the pushed branch.
3. Explain what changed and how it was tested.
4. Ask at least one teammate to review it.
5. Merge only after tests and review are complete.
6. Delete the remote feature branch after merging.

For a small class team, pull requests are still useful because they provide a
clear record and prevent accidental overwrites.

## 10. Receive teammates' changes locally

After a teammate's pull request is merged, your local project remains unchanged
until you run:

```bash
git switch main
git pull origin main
```

If you are working on another branch, first update `main`, then incorporate it:

```bash
git switch main
git pull origin main
git switch your-branch-name
git merge main
```

Resolve any reported conflicts carefully, rerun tests, and commit the resolution.

## Daily checklist

```text
1. Pull the latest main branch.
2. Create or switch to your feature branch.
3. Make one focused change.
4. Run tests and inspect git diff.
5. Commit and push the feature branch.
6. Open a pull request for review.
```

