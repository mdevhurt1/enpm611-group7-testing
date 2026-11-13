import io
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone

import matplotlib.pyplot as plt

from label_resolution import LabelResolutionAnalysis
from model import Event
from .base import AnalysisTestCase
from .helpers import load_issues, make_event, make_issue


START = datetime(2024, 1, 1, tzinfo=timezone.utc)


def closed_issue(days, labels=("kind/bug",), number=1, **overrides):
    """A closed issue whose 'closed' event is `days` after creation."""
    issue = make_issue(
        number=number,
        state="closed",
        labels=list(labels),
        created_date=START.isoformat(),
        events=[
            make_event(
                event_type="closed",
                event_date=(START + timedelta(days=days)).isoformat(),
            )
        ],
    )
    issue.update(overrides)
    return issue


def event(event_type, event_date):
    """Build a runtime Event object directly."""
    e = Event(None)
    e.event_type = event_type
    e.event_date = event_date
    return e


class LabelResolutionTestCase(AnalysisTestCase):
    """Shared helpers: build the analysis on fake issues and capture output."""

    def analysis_for(self, issue_dicts):
        load_issues(issue_dicts)
        return LabelResolutionAnalysis()

    def run_quietly(self, func):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            result = func()
        return result, buffer.getvalue()


class TestGetResolutionDate(LabelResolutionTestCase):

    def setUp(self):
        super().setUp()
        self.analysis = self.analysis_for([make_issue()])
        self.issue = self.analysis.issues[0]

    def test_no_events_returns_none(self):
        self.issue.events = []
        self.assertIsNone(self.analysis.get_resolution_date(self.issue))

    def test_only_non_closing_events_returns_none(self):
        self.issue.events = [
            event("labeled", START),
            event("commented", START + timedelta(days=1)),
        ]
        self.assertIsNone(self.analysis.get_resolution_date(self.issue))

    def test_event_with_no_type_is_ignored(self):
        self.issue.events = [event(None, START)]
        self.assertIsNone(self.analysis.get_resolution_date(self.issue))

    def test_closing_event_without_date_is_ignored(self):
        self.issue.events = [event("closed", None)]
        self.assertIsNone(self.analysis.get_resolution_date(self.issue))

    def test_single_closed_event_returns_its_date(self):
        close = START + timedelta(days=3)
        self.issue.events = [event("closed", close)]
        self.assertEqual(self.analysis.get_resolution_date(self.issue), close)

    def test_event_type_match_is_case_insensitive(self):
        # the dataset only uses lowercase "closed".
        close = START + timedelta(days=2)
        self.issue.events = [event("Closed", close)]
        self.assertEqual(self.analysis.get_resolution_date(self.issue), close)

    def test_reopened_issue_uses_latest_close(self):
        first = START + timedelta(days=1)
        last = START + timedelta(days=10)
        self.issue.events = [
            event("closed", last),
            event("reopened", START + timedelta(days=5)),
            event("closed", first),
        ]
        self.assertEqual(self.analysis.get_resolution_date(self.issue), last)


class TestCalculateResolutionTimes(LabelResolutionTestCase):

    def test_open_issues_are_skipped(self):
        analysis = self.analysis_for([make_issue(state="open")])
        result, output = self.run_quietly(analysis.calculate_resolution_times)
        self.assertEqual(dict(result), {})
        self.assertIn("Total issues: 1", output)
        self.assertIn("Closed issues: 0", output)

    def test_resolution_time_is_computed_in_fractional_days(self):
        analysis = self.analysis_for([closed_issue(1.5, labels=["kind/bug"])])
        result, _ = self.run_quietly(analysis.calculate_resolution_times)
        self.assertEqual(list(result.keys()), ["kind/bug"])
        self.assertAlmostEqual(result["kind/bug"][0], 1.5)

    def test_time_is_added_to_every_label_of_the_issue(self):
        analysis = self.analysis_for([closed_issue(4, labels=["kind/bug", "area/docs"])])
        result, _ = self.run_quietly(analysis.calculate_resolution_times)
        self.assertEqual(result["kind/bug"], [4.0])
        self.assertEqual(result["area/docs"], [4.0])

    def test_blank_and_non_string_labels_are_ignored(self):
        #  dataset labels are always non-empty strings.
        analysis = self.analysis_for(
            [closed_issue(2, labels=["", "   ", None, 42, "kind/bug"])]
        )
        result, _ = self.run_quietly(analysis.calculate_resolution_times)
        self.assertEqual(list(result.keys()), ["kind/bug"])

    def test_closed_issue_without_labels_contributes_nothing(self):
        analysis = self.analysis_for([closed_issue(2, labels=[])])
        result, output = self.run_quietly(analysis.calculate_resolution_times)
        self.assertEqual(dict(result), {})
        self.assertIn("Closed issues: 1", output)

    def test_closed_issue_without_closing_event_is_counted_as_missing(self):
        issue = closed_issue(2)
        issue["events"] = [make_event(event_type="commented")]
        analysis = self.analysis_for([issue])
        result, output = self.run_quietly(analysis.calculate_resolution_times)
        self.assertEqual(dict(result), {})
        self.assertIn("Closed issues without a closing event: 1", output)

    def test_closed_issue_without_created_date_is_skipped(self):
        # every dataset issue has a created_date string.
        issue = closed_issue(2, created_date=None)
        analysis = self.analysis_for([issue])
        result, output = self.run_quietly(analysis.calculate_resolution_times)
        self.assertEqual(dict(result), {})
        self.assertIn("Closed issues: 1", output)
        # Not reported as a missing closing event: the close event exists.
        self.assertIn("Closed issues without a closing event: 0", output)

    def test_close_before_creation_is_discarded(self):
        # guards against corrupt or out-of-order timestamps.
        analysis = self.analysis_for([closed_issue(-3)])
        result, _ = self.run_quietly(analysis.calculate_resolution_times)
        self.assertEqual(dict(result), {})

    def test_zero_day_resolution_is_kept(self):
        analysis = self.analysis_for([closed_issue(0)])
        result, _ = self.run_quietly(analysis.calculate_resolution_times)
        self.assertEqual(result["kind/bug"], [0.0])

    def test_summary_counts_for_mixed_issues(self):
        no_close = closed_issue(1, number=3)
        no_close["events"] = []
        analysis = self.analysis_for([
            closed_issue(1, number=1),
            make_issue(number=2, state="open"),
            no_close,
        ])
        _, output = self.run_quietly(analysis.calculate_resolution_times)
        self.assertIn("Total issues: 3", output)
        self.assertIn("Closed issues: 2", output)
        self.assertIn("Closed issues without a closing event: 1", output)

    def test_mixed_naive_and_aware_timestamps_are_handled(self):
        # created_date without a UTC offset and a closing event
        # with one. model.Issue.days_to_close() normalizes both with
        # _as_utc(), but this analysis subtracts them directly.
        issue = closed_issue(4)
        issue["created_date"] = START.replace(tzinfo=None).isoformat()
        analysis = self.analysis_for([issue])

        self.assertAlmostEqual(analysis.issues[0].days_to_close(), 4.0)
        result, _ = self.run_quietly(analysis.calculate_resolution_times)
        self.assertAlmostEqual(result["kind/bug"][0], 4.0)


class TestRun(LabelResolutionTestCase):

    def run_analysis(self, issue_dicts):
        analysis = self.analysis_for(issue_dicts)
        _, output = self.run_quietly(analysis.run)
        return output

    def issues_for(self, label, days_list, start_number=1):
        return [
            closed_issue(d, labels=[label], number=start_number + i)
            for i, d in enumerate(days_list)
        ]

    def test_no_usable_data_prints_message_and_skips_chart(self):
        output = self.run_analysis([make_issue(state="open")])
        self.assertIn("No issues with usable resolution dates", output)
        self.mock_show.assert_not_called()

    def test_labels_below_threshold_print_message_and_skip_chart(self):
        output = self.run_analysis(self.issues_for("kind/bug", [1, 2, 3, 4]))
        self.assertIn("No labels have at least 5 resolved issues.", output)
        self.mock_show.assert_not_called()

    def test_threshold_boundary_includes_five_and_excludes_four(self):
        output = self.run_analysis(
            self.issues_for("five", [1, 2, 3, 4, 5], start_number=1)
            + self.issues_for("four", [1, 2, 3, 4], start_number=100)
        )
        self.assertIn("five", output)
        detail = output.split("DETAILED RESULTS")[1]
        self.assertNotIn("four", detail)

    def test_median_for_odd_number_of_issues(self):
        output = self.run_analysis(self.issues_for("kind/bug", [10, 1, 7, 3, 100]))
        self.assertIn("Median:     7.00 days Issues: 5", output)

    def test_median_for_even_number_of_issues(self):
        output = self.run_analysis(self.issues_for("kind/bug", [1, 2, 3, 4, 5, 6]))
        self.assertIn("Median:     3.50 days Issues: 6", output)

    def test_finding_names_longest_and_shortest_labels(self):
        output = self.run_analysis(
            self.issues_for("fast", [1] * 5, start_number=1)
            + self.issues_for("medium", [5] * 5, start_number=100)
            + self.issues_for("slow", [20] * 5, start_number=200)
        )
        self.assertIn("QUESTION:", output)
        self.assertIn("METHOD:", output)
        self.assertIn(
            "longest median resolution time is 'slow' at 20.00 days, "
            "based on 5 issues.", output)
        self.assertIn(
            "shortest median resolution time is 'fast' at 1.00 days, "
            "based on 5 issues.", output)

    def test_detailed_results_are_sorted_ascending(self):
        output = self.run_analysis(
            self.issues_for("slow", [20] * 5, start_number=1)
            + self.issues_for("fast", [1] * 5, start_number=100)
            + self.issues_for("medium", [5] * 5, start_number=200)
        )
        detail = output.split("DETAILED RESULTS")[1]
        self.assertLess(detail.index("fast"), detail.index("medium"))
        self.assertLess(detail.index("medium"), detail.index("slow"))

    def test_single_label_is_both_longest_and_shortest(self):
        output = self.run_analysis(self.issues_for("only", [2] * 5))
        self.assertIn("longest median resolution time is 'only'", output)
        self.assertIn("shortest median resolution time is 'only'", output)

    def test_chart_shows_sorted_medians_with_title_and_axis_labels(self):
        self.run_analysis(
            self.issues_for("slow", [20] * 5, start_number=1)
            + self.issues_for("fast", [1] * 5, start_number=100)
        )
        self.mock_show.assert_called_once()

        ax = plt.gcf().axes[0]
        self.assertEqual(ax.get_title(), "Median Issue Resolution Time by Label")
        self.assertEqual(ax.get_xlabel(), "Issue Label")
        self.assertEqual(ax.get_ylabel(), "Median Days to Close")

        heights = [bar.get_height() for bar in ax.patches]
        self.assertEqual(heights, [1.0, 20.0])
        tick_labels = [t.get_text() for t in ax.get_xticklabels()]
        self.assertEqual(tick_labels, ["fast", "slow"])


if __name__ == "__main__":
    unittest.main()
