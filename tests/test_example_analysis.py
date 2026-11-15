"""Tests for example_analysis.py.

Covers the constructor and run: the printed event count (with and without
--user) and the bar chart of top issue creators.
"""

import io
from contextlib import redirect_stdout
from typing import List, Optional
from unittest.mock import patch

from example_analysis import ExampleAnalysis
from .base import AnalysisTestCase
from .helpers import load_issues, make_event, make_issue


def _issues_with_events() -> List[dict]:
    """Issues whose events are split between two authors.

    Returns three issues with these event distributions:
      - alice: 4 events across issue 1 and issue 2
      - bob:   3 events across all three issues
      Total: 7 events across 3 issues.
    """
    return [
        make_issue(
            creator="alice",
            events=[
                make_event(event_type="labeled", author="alice"),
                make_event(event_type="commented", author="bob"),
                make_event(event_type="assigned", author="alice"),
            ],
        ),
        make_issue(
            creator="bob",
            events=[
                make_event(event_type="labeled", author="alice"),
                make_event(event_type="commented", author="alice"),
            ],
        ),
        make_issue(
            creator="charlie",
            events=[
                make_event(event_type="labeled", author="bob"),
                make_event(event_type="commented", author="bob"),
            ],
        ),
    ]


class ExampleAnalysisTestCase(AnalysisTestCase):
    """Shared helpers for the example analysis tests."""

    def _analysis(self, user: Optional[str] = None) -> ExampleAnalysis:
        """Build the analysis as if run.py had been given --user `user`."""
        with patch("example_analysis.config.get_parameter", return_value=user):
            return ExampleAnalysis()

    @staticmethod
    def _capture(fn, *args):
        """Call fn(*args) and return (result, everything it printed)."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            result = fn(*args)
        return result, buf.getvalue()


# -- __init__ ----------------------------------------------------------------

class TestInit(ExampleAnalysisTestCase):

    def test_user_is_read_from_config(self) -> None:
        analysis = self._analysis(user="alice")
        self.assertEqual("alice", analysis.USER)

    def test_user_defaults_to_none(self) -> None:
        analysis = self._analysis()
        self.assertIsNone(analysis.USER)


# -- run ---------------------------------------------------------------------

class TestRun(ExampleAnalysisTestCase):

    def test_without_user_counts_all_events(self) -> None:
        load_issues(_issues_with_events())
        _, output = self._capture(self._analysis().run)
        self.assertEqual("Found 7 events across 3 issues.", output.strip())

    def test_with_user_counts_only_that_authors_events(self) -> None:
        load_issues(_issues_with_events())
        _, output = self._capture(self._analysis(user="alice").run)
        self.assertEqual("Found 4 events across 3 issues for alice.", output.strip())

    def test_bar_chart_is_shown_once(self) -> None:
        load_issues(_issues_with_events())
        self._capture(self._analysis().run)
        self.mock_show.assert_called_once()
