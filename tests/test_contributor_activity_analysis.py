"""Tests for contributor_activity_analysis.py.

Covers the constructor, _aggregate, _first_responses, _yearly_concentration,
the _print_* methods, the _plot_* methods and run.
"""

import io
from contextlib import redirect_stdout
from typing import Dict, List, Optional, Tuple
from unittest.mock import patch

import matplotlib.pyplot as plt
import pandas as pd

from contributor_activity_analysis import ContributorActivityAnalysis
from .base import AnalysisTestCase
from .helpers import load_issues, make_event, make_issue


def _activity(counts: Dict[str, Tuple[int, int, int]]) -> pd.DataFrame:
    """Build an `activity` frame shaped like _aggregate's output.

    `counts` maps contributor -> (comments, label_actions, closes).
    """
    df = pd.DataFrame.from_dict(counts, orient="index",
                                columns=["comments", "label_actions", "closes"])
    df.index.name = "contributor"
    df["issues_touched"] = 1
    df["triage_actions"] = df["label_actions"] + df["closes"]
    df["total"] = df["comments"] + df["triage_actions"]
    return df.sort_values("total", ascending=False, kind="stable")


def _first(rows: List[Tuple[int, str]]) -> pd.DataFrame:
    """Build a `first` frame shaped like _first_responses' output from (year, responder) rows."""
    return pd.DataFrame([{"issue": n, "year": year, "responder": responder}
                         for n, (year, responder) in enumerate(rows, start=1)],
                        columns=["issue", "year", "responder"])


def _ranked(count: int) -> pd.DataFrame:
    """`count` comment-only contributors c00, c01, ... with distinct, falling totals."""
    return _activity({f"c{i:02d}": (20 - i, 0, 0) for i in range(count)})


def _commented_issues(count: int, author: str = "bob", year: int = 2024) -> List[dict]:
    """`count` issues opened in `year`, each answered by `author`."""
    date = f"{year}-06-01T12:00:00Z"
    return [make_issue(number=n, creator="alice", created_date=date, events=[
                make_event(event_type="commented", author=author, event_date=date),
            ]) for n in range(1, count + 1)]


def _figure_titles() -> List[str]:
    """Titles of all open figures, in creation order."""
    return [plt.figure(n).axes[0].get_title() for n in plt.get_fignums()]


class ContributorActivityTestCase(AnalysisTestCase):
    """Shared helpers for the contributor activity tests."""

    def _analysis(self, user: Optional[object] = None) -> ContributorActivityAnalysis:
        """Build the analysis as if run.py had been given --user `user`."""
        with patch("contributor_activity_analysis.config.get_parameter", return_value=user):
            return ContributorActivityAnalysis()

    @staticmethod
    def _capture(fn, *args):
        """Call fn(*args) and return (result, everything it printed)."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            result = fn(*args)
        return result, buf.getvalue()

    @staticmethod
    def _line_with(output: str, text: str) -> str:
        """The first printed line containing `text`."""
        return next(line for line in output.splitlines() if text in line)


# -- __init__ ----------------------------------------------------------------

class TestInit(ContributorActivityTestCase):

    def test_user_is_none_when_no_user_parameter(self) -> None:
        self.assertIsNone(self._analysis().USER)

    def test_user_is_stripped_of_surrounding_whitespace(self) -> None:
        self.assertEqual(self._analysis(user="  user  ").USER, "user")

    def test_non_string_user_is_converted_to_string(self) -> None:
        self.assertEqual(self._analysis(user=123).USER, "123")


# -- _aggregate --------------------------------------------------------------

class TestAggregate(ContributorActivityTestCase):

    def _aggregate(self, *issue_dicts: dict) -> pd.DataFrame:
        return self._analysis()._aggregate(load_issues(list(issue_dicts)))

    def test_no_issues_returns_empty_frame(self) -> None:
        self.assertTrue(self._analysis()._aggregate([]).empty)

    def test_comment_is_counted_as_comment(self) -> None:
        result = self._aggregate(make_issue(creator="alice", events=[
            make_event(event_type="commented", author="bob"),
        ]))
        self.assertEqual(result.loc["bob", "comments"], 1)

    def test_comment_by_reporter_is_counted(self) -> None:
        result = self._aggregate(make_issue(creator="alice", events=[
            make_event(event_type="commented", author="alice"),
        ]))
        self.assertEqual(result.loc["alice", "comments"], 1)

    def test_labeled_and_unlabeled_are_counted_as_label_actions(self) -> None:
        result = self._aggregate(make_issue(creator="alice", events=[
            make_event(event_type="labeled", author="bob", label="bug"),
            make_event(event_type="unlabeled", author="bob", label="bug"),
        ]))
        self.assertEqual(result.loc["bob", "label_actions"], 2)

    def test_label_action_by_reporter_is_not_counted(self) -> None:
        result = self._aggregate(make_issue(creator="alice", events=[
            make_event(event_type="labeled", author="alice", label="bug"),
            make_event(event_type="commented", author="bob"),
        ]))
        self.assertNotIn("alice", result.index)

    def test_close_by_other_user_is_counted(self) -> None:
        result = self._aggregate(make_issue(creator="alice", events=[
            make_event(event_type="closed", author="bob"),
        ]))
        self.assertEqual(result.loc["bob", "closes"], 1)

    def test_close_by_reporter_is_not_counted(self) -> None:
        result = self._aggregate(make_issue(creator="alice", events=[
            make_event(event_type="closed", author="alice"),
            make_event(event_type="commented", author="bob"),
        ]))
        self.assertNotIn("alice", result.index)

    def test_bot_events_are_excluded(self) -> None:
        result = self._aggregate(make_issue(creator="alice", events=[
            make_event(event_type="commented", author="dependabot[bot]"),
            make_event(event_type="labeled", author="dependabot[bot]", label="bug"),
            make_event(event_type="closed", author="dependabot[bot]"),
            make_event(event_type="commented", author="bob"),
        ]))
        self.assertEqual(list(result.index), ["bob"])

    def test_events_without_author_are_excluded(self) -> None:
        result = self._aggregate(make_issue(creator="alice", events=[
            make_event(event_type="commented", author=None),
            make_event(event_type="labeled", author=None, label="bug"),
            make_event(event_type="closed", author=None),
            make_event(event_type="commented", author="bob"),
        ]))
        self.assertEqual(list(result.index), ["bob"])

    def test_other_event_types_are_ignored(self) -> None:
        result = self._aggregate(make_issue(creator="alice", events=[
            make_event(event_type="assigned", author="bob"),
            make_event(event_type="referenced", author="bob"),
            make_event(event_type="commented", author="bob"),
        ]))
        self.assertEqual(result.loc["bob", "total"], 1)

    def test_missing_measure_columns_are_filled_with_zero(self) -> None:
        result = self._aggregate(make_issue(creator="alice", events=[
            make_event(event_type="commented", author="bob"),
        ]))
        self.assertEqual(result.loc["bob", "label_actions"], 0)
        self.assertEqual(result.loc["bob", "closes"], 0)

    def test_issues_touched_counts_distinct_issues(self) -> None:
        result = self._aggregate(
            make_issue(number=1, creator="alice", events=[
                make_event(event_type="commented", author="bob"),
                make_event(event_type="labeled", author="bob", label="bug"),
            ]),
            make_issue(number=2, creator="alice", events=[
                make_event(event_type="commented", author="bob"),
            ]),
        )
        self.assertEqual(result.loc["bob", "issues_touched"], 2)

    def test_triage_actions_is_label_actions_plus_closes(self) -> None:
        result = self._aggregate(make_issue(creator="alice", events=[
            make_event(event_type="labeled", author="bob", label="bug"),
            make_event(event_type="unlabeled", author="bob", label="bug"),
            make_event(event_type="closed", author="bob"),
        ]))
        self.assertEqual(result.loc["bob", "triage_actions"], 3)

    def test_total_is_comments_plus_triage_actions(self) -> None:
        result = self._aggregate(make_issue(creator="alice", events=[
            make_event(event_type="commented", author="bob"),
            make_event(event_type="labeled", author="bob", label="bug"),
            make_event(event_type="unlabeled", author="bob", label="bug"),
            make_event(event_type="closed", author="bob"),
        ]))
        self.assertEqual(result.loc["bob", "total"], 4)

    def test_result_is_sorted_by_total_descending(self) -> None:
        result = self._aggregate(
            make_issue(number=1, creator="alice", events=[
                make_event(event_type="commented", author="bob"),
            ]),
            make_issue(number=2, creator="alice", events=[
                make_event(event_type="labeled", author="carol", label="bug"),
                make_event(event_type="unlabeled", author="carol", label="bug"),
            ]),
        )
        self.assertEqual(list(result.index), ["carol", "bob"])

    def test_index_is_named_contributor(self) -> None:
        result = self._aggregate(make_issue(creator="alice", events=[
            make_event(event_type="commented", author="bob"),
        ]))
        self.assertEqual(result.index.name, "contributor")


# -- _first_responses --------------------------------------------------------

class TestFirstResponses(ContributorActivityTestCase):

    def _first_responses(self, *issue_dicts: dict) -> pd.DataFrame:
        return self._analysis()._first_responses(load_issues(list(issue_dicts)))

    def test_no_issues_returns_empty_frame_with_columns(self) -> None:
        result = self._analysis()._first_responses([])
        self.assertTrue(result.empty)
        self.assertEqual(list(result.columns), ["issue", "year", "responder"])

    def test_issue_without_created_date_is_skipped(self) -> None:
        result = self._first_responses(make_issue(creator="alice", created_date=None, events=[
            make_event(event_type="commented", author="bob"),
        ]))
        self.assertTrue(result.empty)

    def test_issue_without_replies_is_skipped(self) -> None:
        self.assertTrue(self._first_responses(make_issue(creator="alice", events=[])).empty)

    def test_comment_by_reporter_is_not_a_reply(self) -> None:
        result = self._first_responses(make_issue(creator="alice", events=[
            make_event(event_type="commented", author="alice"),
        ]))
        self.assertTrue(result.empty)

    def test_bot_comment_is_not_a_reply(self) -> None:
        result = self._first_responses(make_issue(creator="alice", events=[
            make_event(event_type="commented", author="dependabot[bot]"),
        ]))
        self.assertTrue(result.empty)

    def test_comment_without_date_is_not_a_reply(self) -> None:
        result = self._first_responses(make_issue(creator="alice", events=[
            make_event(event_type="commented", author="bob", event_date=None),
        ]))
        self.assertTrue(result.empty)

    def test_non_comment_events_are_not_replies(self) -> None:
        result = self._first_responses(make_issue(creator="alice", events=[
            make_event(event_type="labeled", author="bob", label="bug"),
            make_event(event_type="closed", author="bob"),
        ]))
        self.assertTrue(result.empty)

    def test_records_issue_number_and_responder(self) -> None:
        result = self._first_responses(make_issue(number=42, creator="alice", events=[
            make_event(event_type="commented", author="bob"),
        ]))
        self.assertEqual(result.loc[0, "issue"], 42)
        self.assertEqual(result.loc[0, "responder"], "bob")

    def test_one_row_per_answered_issue(self) -> None:
        result = self._first_responses(*_commented_issues(3))
        self.assertEqual(list(result["issue"]), [1, 2, 3])

    def test_earliest_reply_wins_regardless_of_event_order(self) -> None:
        result = self._first_responses(make_issue(creator="alice", events=[
            make_event(event_type="commented", author="bob", event_date="2024-01-02T12:00:00Z"),
            make_event(event_type="commented", author="carol", event_date="2024-01-01T12:00:00Z"),
        ]))
        self.assertEqual(result.loc[0, "responder"], "carol")

    def test_aware_and_naive_reply_dates_are_compared_in_utc(self) -> None:
        # bob replied at 07:00 UTC; carol's naive 08:00 is treated as UTC.
        result = self._first_responses(make_issue(creator="alice", events=[
            make_event(event_type="commented", author="carol", event_date="2024-01-01T08:00:00"),
            make_event(event_type="commented", author="bob", event_date="2024-01-01T09:00:00+02:00"),
        ]))
        self.assertEqual(result.loc[0, "responder"], "bob")

    def test_year_is_the_year_the_issue_was_opened_in_utc(self) -> None:
        # 23:00 on 31 Dec at UTC-2 is 01:00 on 1 Jan in UTC.
        result = self._first_responses(make_issue(
            creator="alice", created_date="2023-12-31T23:00:00-02:00", events=[
                make_event(event_type="commented", author="bob", event_date="2024-01-02T00:00:00Z"),
            ]))
        self.assertEqual(result.loc[0, "year"], 2024)


# -- _yearly_concentration ---------------------------------------------------

class TestYearlyConcentration(ContributorActivityTestCase):

    def test_empty_frame_returns_empty_frame(self) -> None:
        self.assertTrue(self._analysis()._yearly_concentration(_first([])).empty)

    def test_year_below_minimum_issues_is_dropped(self) -> None:
        analysis = self._analysis()
        first = _first([(2024, "bob")] * (analysis.MIN_YEAR_ISSUES - 1))
        self.assertTrue(analysis._yearly_concentration(first).empty)

    def test_year_at_minimum_issues_is_kept(self) -> None:
        analysis = self._analysis()
        first = _first([(2024, "bob")] * analysis.MIN_YEAR_ISSUES)
        self.assertEqual(list(analysis._yearly_concentration(first).index), [2024])

    def test_top_responder_and_shares_are_computed(self) -> None:
        first = _first([(2024, "bob")] * 5 + [(2024, "carol")] * 2
                       + [(2024, "dave"), (2024, "eve"), (2024, "frank")])
        row = self._analysis()._yearly_concentration(first).loc[2024]
        self.assertEqual(row["issues"], 10)
        self.assertEqual(row["top_responder"], "bob")
        self.assertEqual(row["top1_share"], 50.0)
        self.assertEqual(row["top3_share"], 80.0)
        self.assertEqual(row["responders"], 5)

    def test_shares_are_rounded_to_one_decimal(self) -> None:
        first = _first([(2024, "bob")] * 4 + [(2024, f"u{i}") for i in range(8)])
        row = self._analysis()._yearly_concentration(first).loc[2024]
        self.assertEqual(row["top1_share"], 33.3)  # 4 of 12

    def test_years_are_computed_independently_and_sorted(self) -> None:
        first = _first([(2024, "carol")] * 10 + [(2023, "bob")] * 10)
        result = self._analysis()._yearly_concentration(first)
        self.assertEqual(list(result.index), [2023, 2024])
        self.assertEqual(list(result["top_responder"]), ["bob", "carol"])


# -- _print_summary ----------------------------------------------------------

class TestPrintSummary(ContributorActivityTestCase):

    def test_prints_contributor_and_commenter_counts(self) -> None:
        activity = _activity({"bob": (3, 1, 0), "carol": (2, 0, 0), "dave": (0, 2, 0)})
        _, output = self._capture(self._analysis()._print_summary, activity)
        self.assertIn("3 human contributors with activity; 2 commented, "
                      "1 of those also labeled or closed issues.", output)

    def test_table_is_limited_to_top_n(self) -> None:
        analysis = self._analysis()
        _, output = self._capture(analysis._print_summary, _ranked(analysis.TOP_N + 1))
        self.assertIn(f"Top {analysis.TOP_N} contributors by total activity:", output)
        self.assertIn("c09", output)
        self.assertNotIn("c10", output)

    def test_table_shows_the_four_measure_columns(self) -> None:
        _, output = self._capture(self._analysis()._print_summary, _ranked(1))
        header = self._line_with(output, "comments")
        for column in ("comments", "label_actions", "closes", "issues_touched"):
            self.assertIn(column, header)
        self.assertNotIn("total", header)


# -- _print_correlations -----------------------------------------------------

class TestPrintCorrelations(ContributorActivityTestCase):

    def test_fewer_than_two_active_contributors_prints_notice(self) -> None:
        activity = _activity({"bob": (5, 0, 0), "carol": (4, 0, 0)})
        _, output = self._capture(self._analysis()._print_correlations, activity)
        self.assertIn("Not enough active contributors to calculate correlations.", output)

    def test_contributors_below_minimum_events_are_left_out(self) -> None:
        # carol has exactly 5 events (kept); dave has 4 (left out).
        activity = _activity({"bob": (10, 5, 0), "carol": (4, 1, 0), "dave": (4, 0, 0)})
        _, output = self._capture(self._analysis()._print_correlations, activity)
        self.assertIn("(contributors with >= 5 events, n=2)", output)

    def test_prints_one_line_per_measure_pair(self) -> None:
        activity = _activity({"bob": (10, 5, 1), "carol": (5, 1, 2)})
        _, output = self._capture(self._analysis()._print_correlations, activity)
        for pair in ("comments vs label_actions", "comments vs closes",
                     "comments vs triage_actions"):
            self.assertIn(pair, output)

    def test_correlation_value_is_printed_with_sign(self) -> None:
        activity = _activity({"bob": (10, 5, 1), "carol": (5, 1, 2)})
        _, output = self._capture(self._analysis()._print_correlations, activity)
        self.assertIn("+1.00", self._line_with(output, "comments vs label_actions"))
        self.assertIn("-1.00", self._line_with(output, "comments vs closes"))

    def test_constant_measure_prints_na(self) -> None:
        activity = _activity({"bob": (10, 0, 5), "carol": (5, 0, 1)})
        _, output = self._capture(self._analysis()._print_correlations, activity)
        self.assertIn("n/a", self._line_with(output, "comments vs label_actions"))
        self.assertIn("+1.00", self._line_with(output, "comments vs closes"))


# -- _print_finding ----------------------------------------------------------

class TestPrintFinding(ContributorActivityTestCase):

    def test_compares_frequent_and_occasional_commenters(self) -> None:
        # bob has exactly 10 comments, so he counts as a frequent commenter.
        activity = _activity({"bob": (10, 1, 0), "carol": (2, 0, 0), "dave": (3, 0, 1)})
        _, output = self._capture(self._analysis()._print_finding, activity)
        self.assertIn("100.0% of frequent commenters (>= 10 comments, n=1) also label or close "
                      "issues, compared with 50.0% of occasional commenters (n=2).", output)

    def test_comparison_is_omitted_when_one_group_is_empty(self) -> None:
        activity = _activity({"bob": (9, 1, 0), "carol": (2, 0, 0)})
        _, output = self._capture(self._analysis()._print_finding, activity)
        self.assertNotIn("frequent commenters", output)

    def test_positive_correlation_wording(self) -> None:
        activity = _activity({"bob": (10, 5, 0), "carol": (5, 1, 0)})
        _, output = self._capture(self._analysis()._print_finding, activity)
        self.assertIn("people who comment more also triage more (rank correlation +1.00)", output)

    def test_negative_correlation_wording(self) -> None:
        activity = _activity({"bob": (10, 1, 0), "carol": (5, 5, 0)})
        _, output = self._capture(self._analysis()._print_finding, activity)
        self.assertIn("people who comment more tend to triage less (rank correlation -1.00)", output)

    def test_weak_correlation_wording(self) -> None:
        # Comment ranks 1-4 against triage ranks 2, 4, 1, 3: Spearman correlation 0.
        activity = _activity({"p1": (5, 6, 0), "p2": (6, 8, 0), "p3": (7, 5, 0), "p4": (8, 7, 0)})
        _, output = self._capture(self._analysis()._print_finding, activity)
        self.assertIn("commenting volume and triage work are only weakly related", output)

    def test_correlation_line_is_omitted_with_fewer_than_two_active(self) -> None:
        activity = _activity({"bob": (10, 5, 0), "carol": (2, 0, 0)})
        _, output = self._capture(self._analysis()._print_finding, activity)
        self.assertNotIn("rank correlation", output)

    def test_prints_top_n_share_of_activity(self) -> None:
        # Totals 20..10 sum to 165; the top 10 hold 155 of them (94%).
        analysis = self._analysis()
        _, output = self._capture(analysis._print_finding, _ranked(analysis.TOP_N + 1))
        self.assertIn("The top 10 contributors account for 94% of all counted activity.", output)


# -- _print_responders -------------------------------------------------------

class TestPrintResponders(ContributorActivityTestCase):

    def test_empty_frame_prints_notice(self) -> None:
        _, output = self._capture(self._analysis()._print_responders, _first([]))
        self.assertIn("No issue received a reply from someone other than its reporter.", output)

    def test_prints_totals_and_top_responder_shares(self) -> None:
        first = _first([(2024, "bob"), (2024, "bob"), (2024, "carol"), (2024, "dave")])
        _, output = self._capture(self._analysis()._print_responders, first)
        self.assertIn("4 issues got a first reply from someone other than the reporter, "
                      "from 3 different people.", output)
        self.assertIn("Top responder: bob (50%); top 3: 100%; top 10: 100%.", output)
        self.assertIn("FINDING: bob wrote the first reply on 50% of answered issues", output)

    def test_yearly_table_is_omitted_when_no_year_qualifies(self) -> None:
        _, output = self._capture(self._analysis()._print_responders, _first([(2024, "bob")]))
        self.assertNotIn("distinct responders", output)

    def test_yearly_table_is_printed_with_renamed_columns(self) -> None:
        _, output = self._capture(self._analysis()._print_responders,
                                  _first([(2024, "bob")] * 10))
        for header in ("answered issues", "top responder", "top-1 %", "top-3 %",
                       "distinct responders"):
            self.assertIn(header, output)
        self.assertNotIn("top1_share", output)

    def test_trend_line_needs_two_qualifying_years(self) -> None:
        _, output = self._capture(self._analysis()._print_responders,
                                  _first([(2024, "bob")] * 10))
        self.assertNotIn("share went from", output)

    def test_trend_line_compares_first_and_last_qualifying_year(self) -> None:
        first = _first([(2023, "bob")] * 10 + [(2024, "bob")] * 5 + [(2024, "carol")] * 5)
        _, output = self._capture(self._analysis()._print_responders, first)
        self.assertIn("The top responder's share went from 100% in 2023 to 50% in 2024", output)


# -- _print_user_summary -----------------------------------------------------

class TestPrintUserSummary(ContributorActivityTestCase):

    def test_known_user_returns_true_and_prints_breakdown(self) -> None:
        activity = _activity({"bob": (3, 2, 1), "carol": (1, 0, 0)})
        found, output = self._capture(self._analysis(user="bob")._print_user_summary,
                                      activity, _first([]))
        self.assertTrue(found)
        self.assertIn("Contributor: bob", output)
        self.assertIn("Comments:        3", output)
        self.assertIn("Label actions:   2", output)
        self.assertIn("Issues closed:   1", output)
        self.assertIn("Issues touched:  1", output)

    def test_lookup_is_case_insensitive_and_adopts_data_spelling(self) -> None:
        analysis = self._analysis(user="BOB")
        found, output = self._capture(analysis._print_user_summary,
                                      _activity({"Bob": (1, 0, 0)}), _first([]))
        self.assertTrue(found)
        self.assertEqual(analysis.USER, "Bob")
        self.assertIn("Contributor: Bob", output)

    def test_rank_and_share_of_activity(self) -> None:
        # Ties share the better rank: carol is #1, bob and dave are both #2.
        activity = _activity({"carol": (6, 0, 0), "bob": (2, 0, 0), "dave": (2, 0, 0)})
        _, output = self._capture(self._analysis(user="bob")._print_user_summary,
                                  activity, _first([]))
        self.assertIn("Overall rank:    #2 of 3 contributors (20.0% of all activity)", output)

    def test_first_replies_line_is_printed_when_first_is_not_empty(self) -> None:
        first = _first([(2024, "bob"), (2024, "carol"), (2024, "carol"), (2024, "carol")])
        _, output = self._capture(self._analysis(user="bob")._print_user_summary,
                                  _activity({"bob": (1, 0, 0)}), first)
        self.assertIn("First replies:   1 (25.0% of 4 first replies to issues)", output)

    def test_first_replies_line_is_omitted_when_first_is_empty(self) -> None:
        _, output = self._capture(self._analysis(user="bob")._print_user_summary,
                                  _activity({"bob": (1, 0, 0)}), _first([]))
        self.assertNotIn("First replies:", output)

    def test_triage_share_is_compared_with_top_n(self) -> None:
        # bob: 3 of 4 events are triage; top 10 overall: 3 of 9.
        activity = _activity({"bob": (1, 2, 1), "carol": (5, 0, 0)})
        _, output = self._capture(self._analysis(user="bob")._print_user_summary,
                                  activity, _first([]))
        self.assertIn("75% of bob's activity is triage (labeling/closing) versus "
                      "33% for the top 10 contributors overall.", output)

    def test_unknown_user_returns_false(self) -> None:
        analysis = self._analysis(user="unknown_user")
        found, output = self._capture(analysis._print_user_summary,
                                      _activity({"bob": (1, 0, 0)}), _first([]))
        self.assertFalse(found)
        self.assertEqual(analysis.USER, "unknown_user")
        self.assertIn('No activity found for user "unknown_user" (bots are excluded).', output)

    def test_unknown_user_with_close_match_prints_suggestions(self) -> None:
        activity = _activity({"Bob": (1, 0, 0), "carol": (1, 0, 0)})
        _, output = self._capture(self._analysis(user="bbo")._print_user_summary,
                                  activity, _first([]))
        self.assertIn("Did you mean: Bob?", output)
        self.assertNotIn("Most active contributors", output)

    def test_unknown_user_without_close_match_prints_five_most_active(self) -> None:
        _, output = self._capture(self._analysis(user="zzzzzz")._print_user_summary,
                                  _ranked(6), _first([]))
        self.assertIn("Most active contributors: c00, c01, c02, c03, c04", output)
        self.assertNotIn("c05", output)
        self.assertNotIn("Did you mean", output)


# -- _plot_activity ----------------------------------------------------------

class TestPlotActivity(ContributorActivityTestCase):

    def test_without_user_plots_top_n_contributors(self) -> None:
        analysis = self._analysis()
        analysis._plot_activity(_ranked(analysis.TOP_N + 1))
        ax = plt.gca()
        labels = [t.get_text() for t in ax.get_xticklabels()]
        self.assertEqual(labels, [f"c{i:02d}" for i in range(analysis.TOP_N)])
        self.assertEqual(ax.get_title(), "Activity of the top 10 contributors (bots excluded)")

    def test_with_user_plots_user_next_to_top_n_average(self) -> None:
        activity = _activity({"carol": (6, 0, 0), "bob": (2, 0, 0)})
        self._analysis(user="bob")._plot_activity(activity)
        ax = plt.gca()
        labels = [t.get_text() for t in ax.get_xticklabels()]
        self.assertEqual(labels, ["bob", "Average of top 10"])
        comment_bars = [bar.get_height() for bar in ax.containers[0]]
        self.assertEqual(comment_bars, [2, 4])  # bob, then the mean of 6 and 2
        self.assertEqual(ax.get_title(), "Activity of bob compared with the top 10 contributors")

    def test_draws_one_bar_series_per_measure(self) -> None:
        self._analysis()._plot_activity(_activity({"bob": (3, 2, 1)}))
        ax = plt.gca()
        self.assertEqual(len(ax.containers), 3)
        self.assertEqual([t.get_text() for t in ax.get_legend().get_texts()],
                         ["Comments", "Label actions", "Issues closed"])
        self.assertEqual([c[0].get_height() for c in ax.containers], [3, 2, 1])


# -- _plot_relationship ------------------------------------------------------

class TestPlotRelationship(ContributorActivityTestCase):

    def test_splits_contributors_into_triagers_and_comment_only(self) -> None:
        activity = _activity({"bob": (3, 0, 0), "carol": (1, 1, 0), "dave": (2, 0, 0)})
        self._analysis()._plot_relationship(activity)
        legend = [t.get_text() for t in plt.gca().get_legend().get_texts()]
        self.assertEqual(legend, ["Comments only (2)", "Also label/close issues (1)"])

    def test_annotates_at_most_six_contributors(self) -> None:
        self._analysis()._plot_relationship(_ranked(8))
        annotated = [t.get_text() for t in plt.gca().texts]
        self.assertEqual(annotated, [f"c{i:02d}" for i in range(6)])


# -- _plot_responders --------------------------------------------------------

class TestPlotResponders(ContributorActivityTestCase):

    def test_no_qualifying_year_draws_nothing(self) -> None:
        self._analysis()._plot_responders(_first([(2024, "bob")] * 9))
        self.assertEqual(plt.get_fignums(), [])
        self.mock_show.assert_not_called()

    def test_plots_top1_and_top3_share_per_year(self) -> None:
        first = _first([(2023, "bob")] * 10 + [(2024, "bob")] * 5 + [(2024, "carol")] * 5)
        self._analysis()._plot_responders(first)
        top1, top3 = plt.gca().lines
        self.assertEqual(list(top1.get_xdata()), [2023, 2024])
        self.assertEqual(list(top1.get_ydata()), [100.0, 50.0])
        self.assertEqual(list(top3.get_ydata()), [100.0, 100.0])

    def test_annotates_each_year_with_top_responder(self) -> None:
        first = _first([(2023, "bob")] * 10 + [(2024, "carol")] * 12)
        self._analysis()._plot_responders(first)
        self.assertEqual([t.get_text() for t in plt.gca().texts],
                         ["bob (n=10)", "carol (n=12)"])


# -- run ---------------------------------------------------------------------

class TestRun(ContributorActivityTestCase):

    ACTIVITY_TITLE = "Activity of the top 10 contributors (bots excluded)"
    RELATIONSHIP_TITLE = "Do frequent commenters also triage issues?"
    RESPONDERS_TITLE = "How concentrated are first replies on a few people?"

    def test_no_activity_prints_notice_and_draws_nothing(self) -> None:
        load_issues([])
        _, output = self._capture(self._analysis().run)
        self.assertIn("No contributor activity found.", output)
        self.assertEqual(plt.get_fignums(), [])

    def test_project_view_prints_all_sections_and_draws_three_charts(self) -> None:
        issues = _commented_issues(10)
        issues[0]["events"].append(make_event(event_type="labeled", author="carol", label="bug"))
        load_issues(issues)
        _, output = self._capture(self._analysis().run)
        self.assertIn("2 human contributors with activity", output)       # _print_summary
        self.assertIn("Not enough active contributors", output)           # _print_correlations
        self.assertIn("of all counted activity", output)                  # _print_finding
        self.assertIn("FIRST-REPLY CONCENTRATION", output)                # _print_responders
        self.assertEqual(_figure_titles(),
                         [self.ACTIVITY_TITLE, self.RELATIONSHIP_TITLE, self.RESPONDERS_TITLE])
        self.assertEqual(self.mock_show.call_count, 3)

    def test_project_view_with_one_contributor_skips_relationship_chart(self) -> None:
        load_issues(_commented_issues(10))
        self._capture(self._analysis().run)
        self.assertEqual(_figure_titles(), [self.ACTIVITY_TITLE, self.RESPONDERS_TITLE])

    def test_project_view_without_first_replies_skips_responders_chart(self) -> None:
        load_issues([make_issue(creator="alice", events=[
            make_event(event_type="labeled", author="bob", label="bug"),
            make_event(event_type="closed", author="carol"),
        ])])
        _, output = self._capture(self._analysis().run)
        self.assertIn("No issue received a reply from someone other than its reporter.", output)
        self.assertEqual(_figure_titles(), [self.ACTIVITY_TITLE, self.RELATIONSHIP_TITLE])

    def test_user_view_prints_user_summary_and_draws_one_chart(self) -> None:
        issues = _commented_issues(10)
        issues[0]["events"].append(make_event(event_type="labeled", author="carol", label="bug"))
        load_issues(issues)
        _, output = self._capture(self._analysis(user="bob").run)
        self.assertIn("Contributor: bob", output)
        self.assertNotIn("FIRST-REPLY CONCENTRATION", output)
        self.assertEqual(_figure_titles(),
                         ["Activity of bob compared with the top 10 contributors"])

    def test_unknown_user_draws_nothing(self) -> None:
        load_issues(_commented_issues(1))
        _, output = self._capture(self._analysis(user="unknown_user").run)
        self.assertIn('No activity found for user "unknown_user"', output)
        self.assertEqual(plt.get_fignums(), [])
