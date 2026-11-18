
"""Unit tests for the Discussion Trend Analysis feature."""

import io
from contextlib import redirect_stdout
from datetime import datetime, timezone
from unittest.mock import patch
import matplotlib.pyplot as plt
from discussion_trend_analysis import DiscussionTrendAnalysis
from .base import AnalysisTestCase
from .helpers import make_issue, make_event, load_issues


class TestDiscussionTrendAnalysis(AnalysisTestCase):
    """Test issue discussion calculations, trends, and reporting."""

    def setUp(self):
        super().setUp()
        self.analysis = DiscussionTrendAnalysis()

    # ---------------------------------------------------------
    # Comment counting
    # ---------------------------------------------------------

    def test_count_comments_only(self):
        """Only commented events should contribute to the count."""
        issues = load_issues([
            make_issue(events=[
                make_event(event_type="commented"),
                make_event(event_type="labeled"),
                make_event(event_type="commented"),
                make_event(event_type="closed"),
            ])
        ])

        self.assertEqual(self.analysis._count_comments(issues[0]), 2)

    def test_count_comments_empty_events(self):
        """An issue with no events should have zero comments."""
        issues = load_issues([make_issue(events=[])])

        self.assertEqual(self.analysis._count_comments(issues[0]), 0)

    def test_count_comments_none_events(self):
        """A missing events list should produce zero comments."""
        issue = load_issues([make_issue()])[0]
        issue.events = None

        self.assertEqual(self.analysis._count_comments(issue), 0)

    # ---------------------------------------------------------
    # Date parsing
    # ---------------------------------------------------------

    def test_parse_valid_date(self):
        """ISO date strings should be converted to UTC."""
        result = self.analysis._parse_event_date("2025-01-15T10:30:00Z")

        expected = datetime(2025, 1, 15, 10, 30, tzinfo=timezone.utc)

        self.assertEqual(result, expected)

    def test_parse_naive_datetime(self):
        """Datetime values without timezone should assume UTC."""
        result = self.analysis._parse_event_date(datetime(2025, 1, 15, 10, 30))

        self.assertEqual(result.tzinfo, timezone.utc)

    def test_parse_invalid_dates(self):
        """Invalid or missing dates should return None."""
        self.assertIsNone(self.analysis._parse_event_date(None))
        self.assertIsNone(self.analysis._parse_event_date("invalid"))
        self.assertIsNone(self.analysis._parse_event_date(123))

    # ---------------------------------------------------------
    # Monthly activity
    # ---------------------------------------------------------

    def test_group_monthly_activity(self):
        """Issues and comments should use their respective dates."""
        issues = load_issues([
            make_issue(
                created_date="2025-01-10T12:00:00Z",
                events=[
                    make_event(
                        event_type="commented",
                        event_date="2025-02-05T12:00:00Z"
                    ),
                    make_event(
                        event_type="commented",
                        event_date="2025-02-15T12:00:00Z"
                    ),
                    make_event(
                        event_type="closed",
                        event_date="2025-02-20T12:00:00Z"
                    ),
                ]
            )
        ])

        result = self.analysis._group_monthly_activity(issues)

        january = datetime(2025, 1, 1, tzinfo=timezone.utc)
        february = datetime(2025, 2, 1, tzinfo=timezone.utc)

        self.assertEqual(result[january], {"issues": 1, "comments": 0})
        self.assertEqual(result[february], {"issues": 0, "comments": 2})

    def test_group_multiple_issues_same_month(self):
        """Multiple issues created in one month should accumulate."""
        issues = load_issues([make_issue(number=1), make_issue(number=2), make_issue(number=3),])

        result = self.analysis._group_monthly_activity(issues)
        january = datetime(2025, 1, 1, tzinfo=timezone.utc)

        self.assertEqual(result[january]["issues"], 3)
        self.assertEqual(result[january]["comments"], 0)

    def test_group_invalid_dates(self):
        """Invalid issue and comment dates should be ignored."""
        issues = load_issues([
            make_issue(
                created_date="invalid",
                events=[
                    make_event(
                        event_type="commented",
                        event_date="invalid"
                    )
                ]
            )
        ])

        result = self.analysis._group_monthly_activity(issues)

        self.assertEqual(result, {})

    def test_group_empty_issues(self):
        """An empty issue list should produce no monthly activity."""
        result = self.analysis._group_monthly_activity([])

        self.assertEqual(result, {})

    # ---------------------------------------------------------
    # Discussion intensity
    # ---------------------------------------------------------

    def test_intensity_boundaries(self):
        """Check the exact Low, Medium, and High boundaries."""
        issues = load_issues([make_issue(number=i) for i in range(1, 6)])
        counts = list(zip(issues, [0, 2, 3, 10, 11]))
        result = self.analysis._get_intensity_distribution(counts)

        self.assertEqual(result, {"Low": 2, "Medium": 2, "High": 1})

    def test_intensity_empty_input(self):
        """An empty dataset should have zero issues per category."""
        result = self.analysis._get_intensity_distribution([])

        self.assertEqual(result, {"Low": 0, "Medium": 0, "High": 0})

    # ---------------------------------------------------------
    # Most discussed issues
    # ---------------------------------------------------------

    def test_top_issues_sorted(self):
        """Issues should be ranked by descending comment count."""
        issues = load_issues([make_issue(number = i) for i in range(1, 5)])
        counts = list(zip(issues, [2, 15, 5, 10]))
        result = self.analysis._get_top_discussed_issues(counts)

        self.assertEqual([count for _, count in result], [15, 10, 5, 2])

    def test_top_issues_includes_ties(self):
        """All issues tied at fifth place should be included."""
        issues = load_issues([make_issue(number=i) for i in range(1, 9)])
        counts = list(zip(issues, [20, 15, 12, 10, 5, 5, 5, 1]))
        result = self.analysis._get_top_discussed_issues(counts)

        self.assertEqual(len(result), 7)
        self.assertEqual([count for _, count in result], [20, 15, 12, 10, 5, 5, 5])

    def test_top_issues_zero_limit(self):
        """A nonpositive limit should return no issues."""
        issues = load_issues([make_issue()])
        result = self.analysis._get_top_discussed_issues([(issues[0], 5)], limit=0)

        self.assertEqual(result, [])

    def test_top_issues_empty_input(self):
        """An empty list should return no ranked issues."""
        self.assertEqual(self.analysis._get_top_discussed_issues([]), [])

    # ---------------------------------------------------------
    # Discussion hotspots
    # ---------------------------------------------------------

    def test_hotspots_positive_median(self):
        """Hotspots should have at least twice the median."""
        issues = load_issues([make_issue(number=i) for i in range(1, 6)])
        counts = list(zip(issues, [1, 2, 3, 6, 10]))
        median_value, hotspots = (self.analysis._get_discussion_hotspots(counts))

        self.assertEqual(median_value, 3.0)
        self.assertEqual([count for _, count in hotspots], [10, 6])

    def test_hotspots_zero_median(self):
        """When the median is zero, positive counts are hotspots."""
        issues = load_issues([make_issue(number=i) for i in range(1, 6)])
        counts = list(zip(issues, [0, 0, 0, 1, 5]))
        median_value, hotspots = (self.analysis._get_discussion_hotspots(counts))

        self.assertEqual(median_value, 0.0)
        self.assertEqual([count for _, count in hotspots], [5, 1])

    def test_hotspots_empty_input(self):
        """An empty dataset should return no hotspots."""
        self.assertEqual(self.analysis._get_discussion_hotspots([]), (0.0, []))

    # ---------------------------------------------------------
    # Monthly trends
    # ---------------------------------------------------------

    def test_increasing_trend(self):
        """Higher activity in the later half means increasing."""
        monthly = {
            1: {"comments": 2},
            2: {"comments": 4},
            3: {"comments": 8},
            4: {"comments": 12},
        }

        self.assertEqual(self.analysis._describe_trend(monthly, "comments"), "increasing")

    def test_decreasing_trend(self):
        """Lower activity in the later half means decreasing."""
        monthly = {
            1: {"comments": 12},
            2: {"comments": 8},
            3: {"comments": 4},
            4: {"comments": 2},
        }

        self.assertEqual(self.analysis._describe_trend(monthly, "comments"), "decreasing")

    def test_stable_trend(self):
        """Equal monthly averages should be relatively stable."""
        monthly = {
            1: {"comments": 10},
            2: {"comments": 10},
            3: {"comments": 10},
            4: {"comments": 10},
        }

        self.assertEqual(self.analysis._describe_trend(monthly, "comments"), "relatively stable")

    def test_insufficient_monthly_data(self):
        """Fewer than two months should not produce a trend."""
        result = self.analysis._describe_trend({1: {"comments": 5}}, "comments")

        self.assertEqual(result, "stable (not enough monthly data to compare)")

    # ---------------------------------------------------------
    # Console reporting
    # ---------------------------------------------------------

    def test_report_statistics(self):
        """The report should print correct calculated totals."""
        issue = load_issues([make_issue(number=42, title="Example bug")])[0]
        counts = [(issue, 4)]
        monthly = {
            datetime(2025, 1, 1, tzinfo=timezone.utc): {
                "issues": 1,
                "comments": 4
                }
            }
        distribution = {"Low": 0, "Medium": 1, "High": 0}
        output = io.StringIO()

        with redirect_stdout(output):
            self.analysis._print_report(counts, monthly, distribution, counts, 4)

        report = output.getvalue()

        self.assertIn("Total issues analyzed: 1", report)
        self.assertIn("Total comments analyzed: 4", report)
        self.assertIn("Average comments per issue: 4.00", report)
        self.assertIn("Medium: 1 issues (100.0%)", report)
        self.assertIn("#42: Example bug (4 comments)", report)

    def test_report_empty_data(self):
        """An empty report should handle zero issues safely."""
        output = io.StringIO()

        with redirect_stdout(output):
            self.analysis._print_report([], {}, {"Low": 0, "Medium": 0, "High": 0}, [], 0)

        report = output.getvalue()

        self.assertIn("Total issues analyzed: 0", report)
        self.assertIn("No issues to report.", report)
        self.assertIn("no issue data was available", report)

    def test_additional_insights(self):
        """The insights report should print median and hotspots."""
        issue = load_issues([make_issue(number=7, title="Active issue")])[0]
        output = io.StringIO()

        with redirect_stdout(output):
            self.analysis._print_additional_insights(2.0, [(issue, 5)])

        report = output.getvalue()

        self.assertIn("Median comments per issue: 2.00", report)
        self.assertIn("Hotspot threshold: At least 4.00", report)
        self.assertIn("Number of discussion hotspots: 1", report)
        self.assertIn("Issue #7: Active issue", report)

    # ---------------------------------------------------------
    # Chart generation
    # ---------------------------------------------------------

    def test_monthly_chart(self):
        """Monthly chart should create two plotted data series."""
        monthly = {
            datetime(2025, 1, 1, tzinfo=timezone.utc): {
                "issues": 2,
                "comments": 4
            },
            datetime(2025, 2, 1, tzinfo=timezone.utc): {
                "issues": 3,
                "comments": 6
            }
        }

        self.analysis._show_monthly_activity_chart(monthly)

        figure = plt.gcf()
        axes = figure.axes[0]

        self.assertEqual(len(axes.lines), 2)
        self.assertEqual(list(axes.lines[0].get_ydata()), [2, 3])
        self.assertEqual(list(axes.lines[1].get_ydata()), [4, 6])

    def test_intensity_chart(self):
        """Intensity chart should contain three correct bars."""
        distribution = {
            "Low": 5,
            "Medium": 3,
            "High": 2
        }

        self.analysis._show_intensity_chart(distribution)

        figure = plt.gcf()
        axes = figure.axes[0]

        self.assertEqual(len(axes.patches), 3)
        self.assertEqual([bar.get_height() for bar in axes.patches], [5, 3, 2])

    # ---------------------------------------------------------
    # Full feature execution
    # ---------------------------------------------------------

    @patch.object(DiscussionTrendAnalysis, "_show_intensity_chart")
    @patch.object(DiscussionTrendAnalysis, "_show_monthly_activity_chart")

    def test_run_integration(self, mock_monthly, mock_intensity):
        """Run should analyze loaded issues and invoke both charts."""
        load_issues([make_issue(number=1, events=[make_event(event_type="commented"), make_event(event_type="commented"),])])

        output = io.StringIO()

        with redirect_stdout(output):
            self.analysis.run()

        report = output.getvalue()

        self.assertIn("Total issues analyzed: 1", report)
        self.assertIn("Total comments analyzed: 2", report)

        mock_monthly.assert_called_once()
        mock_intensity.assert_called_once()
        self.mock_show.assert_called_once_with(block=True)