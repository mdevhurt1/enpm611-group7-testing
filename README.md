# ENPM611 Team 1: Poetry Issue Analyzer

A command-line application that analyzes the GitHub issues of the open-source
[Poetry](https://github.com/python-poetry/poetry) project (issue and event data
provided as a JSON file). It answers three questions about how issues are
labeled, who works on them, and how issue activity changes over time, and shows
the results as console output and matplotlib charts.

This repository is a fork of the ENPM611 application template. The design
diagrams from Milestone 1 are in [`docs/`](docs/).

## Setup

**Python version:** Python 3.10 or newer (developed and tested with Python 3.12).

**Dependencies:** `python-dateutil`, `numpy`, `pandas`, `matplotlib`
(listed in `requirements.txt`).

1. Clone this repository.
2. Create and activate a virtual environment in the repository root:
   - macOS / Linux: `python3 -m venv venv && source venv/bin/activate`
   - Windows (PowerShell): `python -m venv venv; venv\Scripts\Activate.ps1`
3. Install the dependencies: `pip install -r requirements.txt`

### Configure the dataset path

Download the issues JSON file from the project assignment in Canvas. Then tell
the application where it is, using **either** way (the environment variable
takes priority and keeps your personal path out of the repository):

- Environment variable (recommended)
  - macOS / Linux: `export ENPM611_PROJECT_DATA_PATH=/path/to/poetry_issues.json`
  - Windows (PowerShell): `$env:ENPM611_PROJECT_DATA_PATH="C:\path\to\poetry_issues.json"`
- or edit `ENPM611_PROJECT_DATA_PATH` in `config.json` (do not commit your personal path).

Do not commit the data file. If the path is missing or wrong, the application
prints a clear error message instead of crashing.

## Running the features

```
python run.py --feature 1                    # label comparison (all labels)
python run.py --feature 1 --label kind/bug   # one label in detail
python run.py --feature 2                    # contributor activity (whole project)
python run.py --feature 2 --user abn         # one contributor vs. the top contributors
python run.py --feature 3                    # activity trends over time
python run.py --feature 0                    # template example analysis
```

The label (`kind/bug`) and user (`abn`) above are examples from the Poetry
dataset. Use a label or user that exists in **your** dataset file: label names
and contributors differ between datasets. `--label` and `--user` are optional
and case-insensitive. If the label or user
is not found, the application suggests similar names and exits cleanly.
Charts open in a matplotlib window; close the window to continue (feature 2
shows two charts, one after the other).

## The three analyses

Every analysis prints its **question**, **method** and **finding** to the console.

### Feature 1: Label resolution (`label_resolution_analysis.py`)

**Question:** Which types of issues, grouped by label, take the longest to resolve in the Poetry project?

**Run Command:**
```bash
python run.py --feature 1
```

The project data path must be configured through the `ENPM611_PROJECT_DATA_PATH` environment variable before running the analysis.

**Method:**
- Loads issue data using the project's `DataLoader`.
- Identifies closed issues with valid creation dates and closing events.
- Calculates resolution time in days using the issue creation date and closing event date.
- Groups resolution times by issue label.
- Calculates the median resolution time for each label with at least five resolved issues.

**Output:**
- Displays each issue label, its median resolution time in days, and the number of issues analyzed in the terminal.
- Generates a Matplotlib bar chart titled **Median Issue Resolution Time by Label**.
- The chart compares issue labels on the X-axis against median days to close on the Y-axis.

**Limitations:**
- Only closed issues with valid creation dates and closing events are included.
- Issues without usable resolution dates are excluded.
- Labels with fewer than five resolved issues are excluded from the results.
- The analysis measures resolution time based on recorded closing events and does not account for the complexity or severity of individual issues.

  
### Feature 2: Contributor activity (`contributor_activity_analysis.py`)

- **Question:** Who does the work on the project, do frequent commenters also
  label or close issues, and how concentrated are first replies on a few people?
- **Run:**
  ```
  python run.py --feature 2               # project-wide view
  python run.py --feature 2 --user abn    # one contributor (case-insensitive)
  ```
- **Method:** every event is classified as a comment, a label action
  (labeled/unlabeled) or a close, and counted per contributor. Bots and unknown
  users are excluded, and labels or closes made by the reporter on their own
  issue are not counted as triage (issue templates apply labels in the
  reporter's name). Spearman rank correlations relate the measures. For every
  issue, the first reply by a human other than the reporter is found, and the
  share handled by the top 1 / 3 / 10 responders is computed overall and per year.
- **Output (no `--user`):** the top 10 contributors, rank correlations between
  comments and triage actions, a written finding, a first-reply concentration
  table by year (a "bus factor" view), and three charts: a grouped bar chart
  of the top contributors, a scatter plot of comments vs. triage actions, and
  the top-responder share by year.
- **Output (`--user`):** that contributor's comments, label actions, closes,
  rank, share of all activity and share of first replies, a finding comparing
  their triage share with the top 10, and a bar chart next to the average of
  the top 10. If the user does not exist, similar names are suggested and the
  program exits cleanly.
- **Limitations:**
  - The provided subset (`poetry_issues.json`) is not representative over time,
    so concentration figures differ from those of the full file
    (`poetry_issues_all.json`); always state which file a number comes from.
  - "Frequent commenter" means at least 10 comments, a small group in the
    subset, so percentages for that group rest on few people.
  - Years with fewer than 10 answered issues are left out of the concentration
    table and chart. Correlations describe the data and do not show cause.

### Feature 3: Discussion trends (`discussion_trend_analysis.py`)

**Question:**
How has issue creation and discussion activity changed over time in the Poetry project, and which issues attract the most discussion?

**Run Command:**
python run.py --feature 3

**Method:**
This feature analyzes GitHub issue discussions in the Poetry project using the following steps:
1. Counts comment events for each issue, excluding other timeline events.
2. Groups issues by their creation month and comments by their actual comment event dates to analyze monthly activity.
3. Classifies issues into three discussion-intensity categories based on comment counts:
    Low: 0–2 comments
    Medium: 3–10 comments
    High: More than 10 comments
4. Ranks issues by their number of comments and identifies the most-discussed issues, including ties at the fifth position.
5. alculates the median number of comments per issue and identifies discussion hotspots using twice the median as the threshold. If the median is zero, issues with at least one comment are considered hotspots.
6. Compares average monthly activity across the earlier and later halves of the observation period to identify increasing, decreasing, or relatively stable trends.

**Output:**
The feature prints a console report containing:

- Total issues and comments analyzed.
- Average comments per issue.
- Monthly issue creation and comment activity.
- Issue creation and comment activity trends.
- Months with the highest and lowest comment activity.
- Discussion-intensity distribution, including percentages.
- Most-discussed issues and their comment counts.
- Median comments per issue and the number of discussion hotspots.
- An interpretation of the discussion patterns.

It generates two visualizations:
1. Monthly Issue and Comment Activity: A line chart comparing the number of issues created and comments posted over time.
2. Discussion Intensity Distribution: A bar chart showing the number of issues in the Low, Medium, and High discussion categories.

**Limitations**
- Comment count does not reflect issue complexity: An issue receiving many comments is not necessarily more complex or important than one receiving fewer comments. The analysis measures discussion volume rather than the actual significance or difficulty of an issue.
- Limited trend interpretation: Monthly activity trends show changes in issue creation and comment volume but do not explain why those changes occurred or measure the quality of discussions.

## Known limitations and assumptions

- **Bots are excluded** (authors ending in `[bot]`) from comment, contributor
  and response-time statistics.
- **Time to close** uses the date of the last `closed` event. Closed issues
  without a closing event in the data (20 of 401 in `poetry_issues.json`) and
  open issues are left out of timing statistics. Reopened issues use their latest close.
- **Triage** (feature 2): labels and closes made by the issue's own reporter are
  not counted, because issue templates attribute automatic labels to the
  reporter and reporters closing their own issue is not triage work.
- **First response** is the first human comment by someone other than the
  issue creator. **Time to triage** only counts issues whose `status/triage`
  label was actually removed; issues closed while still marked "triage" are not
  included.
- **Triagers** (feature 3) are people with at least 5 label or close actions on
  issues they did not report.
- **Subset vs. full dataset:** the provided subset (`poetry_issues.json`) is not
  representative over time: almost all of its closings are in 2024, which makes
  the closed/opened ratio and early-year statistics unreliable. Feature 3 prints
  a warning when this happens. Running the analyses on `poetry_issues_all.json`
  gives noticeably different results (for example in the first-response
  concentration); always state which file a result comes from.
- Most issues in the dataset are from 2024, so earlier years have few issues
  and their medians are less reliable (years with fewer than 10 issues are not
  used in the first-vs-last comparison). The final quarter may be incomplete.
- Medians for labels with few resolved issues are unreliable; feature 1 only
  compares labels with at least 5 resolved issues.
- If a dataset has too few issues with a closing event (no label with at least 5
  timed issues), feature 1 falls back to comparing discussion per label only and
  says so.
- Results depend on the dataset file used.

## Differences from the Milestone 1 design

- `model.py` gained small helpers shared by all analyses (`Event.is_human`,
  `Issue.closed_date`, `Issue.days_to_close()`, `Issue.human_comments()`) instead
  of duplicating this logic in each analysis.
- `data_loader.py` raises a clear error when the data path is not configured;
  `run.py` now has a `main()` function and reports that error cleanly.
- Feature 2 does more than the Milestone 1 sequence diagram shows: it also
  prints a written finding after the correlations, computes first-reply
  concentration (extra table and a third chart), and prints a message and exits
  when the requested user does not exist. The component structure is unchanged.
- The three analysis modules also import `model.py` (for `Issue`), which the
  component diagram does not show.

## Team contributions

Each member describes their own work in their own subsection below.

### Shengjie Liu

- **Implementation:** Feature 2, contributor activity analysis (`contributor_activity_analysis.py`).
- **Shared code:** helpers in `model.py` (`is_human`, `closed_date`, `days_to_close`, `human_comments`), a clear error in `data_loader.py` when the data file is missing, and `numpy` in `requirements.txt` (pull request #2).

### Tyree Black

_Implemented Feature 1: Label Resolution Analysis. Created `label_resolution.py` to analyze closed issues by label, calculate median resolution times using issue creation dates and closing events, and generate a Matplotlib bar chart comparing the median number of days to close for each label. Added the Feature 1 execution branch to `run.py` so the analysis can be launched using `python run.py --feature 1`._

### Divhya Gnanasekar
_Implemented Feature 3: Developed the Discussion Trend Analysis 'discussion_trend_analysis.py', including monthly activity tracking, discussion intensity classification, hotspot identification, console reports, and visualizations._

## Running the tests
From the project root, run:

```
python -m coverage run -m unittest discover
```

This command creates a .coverage data file. Generate a readable report with:

```
python -m coverage report --omit="*/test_*.py,tests/*"
```
