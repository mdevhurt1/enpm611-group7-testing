"""Tests for run.py.

Covers the dispatch for features 0-3, the unknown-feature message, and the
hand-off of --user / --label into config.
"""

import io
import os
import runpy
import sys
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

import config
from .base import AnalysisTestCase


RUN_PY = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "run.py"
)

# feature number -> patch target of the class run.py calls for it.
FEATURES = {
    0: "example_analysis.ExampleAnalysis",
    1: "label_resolution.LabelResolutionAnalysis",
    2: "contributor_activity_analysis.ContributorActivityAnalysis",
    3: "discussion_trend_analysis.DiscussionTrendAnalysis",
}

UNKNOWN_FEATURE_MESSAGE = "Need to specify which feature to run with --feature flag."


class RunTestCase(AnalysisTestCase):
    """Shared helper: execute run.py with the given argv and mocked analyses."""

    def run_script(self, *argv):
        """Run run.py as if invoked as python run.py <argv...>.
        """
        mocks = {}
        for feature, target in FEATURES.items():
            patcher = patch(target)
            mocks[feature] = patcher.start()
            self.addCleanup(patcher.stop)

        stdout, self.stderr = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", ["run.py", *argv]), \
                redirect_stdout(stdout), redirect_stderr(self.stderr):
            runpy.run_path(RUN_PY)
        return mocks, stdout.getvalue()

    def assert_only_feature_ran(self, mocks, expected):
        """Assert `expected` was instantiated and run, and no other feature was touched."""
        for feature, mock in mocks.items():
            if feature == expected:
                mock.assert_called_once_with()
                mock.return_value.run.assert_called_once_with()
            else:
                mock.assert_not_called()

    def assert_no_feature_ran(self, mocks):
        """Assert that no analysis class was instantiated at all."""
        for mock in mocks.values():
            mock.assert_not_called()


# -- feature dispatch --------------------------------------------------------

class TestFeatureDispatch(RunTestCase):

    def test_feature_0_runs_example_analysis_only(self):
        mocks, stdout = self.run_script('--feature', '0')
        self.assert_only_feature_ran(mocks, 0)

    def test_feature_1_runs_label_resolution_only(self):
        mocks, stdout = self.run_script('--feature', '1')
        self.assert_only_feature_ran(mocks, 1)

    def test_feature_2_runs_contributor_activity_only(self):
        mocks, stdout = self.run_script('--feature', '2')
        self.assert_only_feature_ran(mocks, 2)

    def test_feature_3_runs_discussion_trend_only(self):
        mocks, stdout = self.run_script('--feature', '3')
        self.assert_only_feature_ran(mocks, 3)


# -- unknown feature ---------------------------------------------------------

class TestUnknownFeature(RunTestCase):

    def test_unknown_feature_prints_message(self):
        mocks, stdout = self.run_script('--feature', '99')
        self.assertIn(UNKNOWN_FEATURE_MESSAGE, stdout)

    def test_unknown_feature_runs_nothing(self):
        mocks, stdout = self.run_script('--feature', '99')
        self.assert_no_feature_ran(mocks)


# -- argument hand-off to config ---------------------------------------------

class TestArgsReachConfig(RunTestCase):

    def test_user_is_readable_through_config(self):
        mocks, stdout = self.run_script('--feature', '0', '--user', 'alice')
        self.assert_only_feature_ran(mocks, 0)
        self.assertEqual(config.get_parameter('user'), 'alice')

    def test_label_is_readable_through_config(self):
        mocks, stdout = self.run_script('--feature', '0', '--label', 'bug')
        self.assert_only_feature_ran(mocks, 0)
        self.assertEqual(config.get_parameter('label'), 'bug')

    def test_omitted_user_and_label_are_not_set(self):
        mocks, stdout = self.run_script('--feature', '0')
        self.assertIsNone(config.get_parameter('user'))
        self.assertIsNone(config.get_parameter('label'))


# -- argument parsing (beyond minimum coverage) ------------------------------

class TestArgumentParsing(RunTestCase):

    def test_missing_feature_flag_exits_with_usage_error(self):
        # argparse raises SystemExit(2) for a missing required argument.
        with self.assertRaises(SystemExit) as cm:
            self.run_script()
        self.assertEqual(cm.exception.code, 2)
        self.assertIn("the following arguments are required: --feature", self.stderr.getvalue())

    def test_short_flags_are_accepted(self):
        # -f / -u / -l behave like --feature / --user / --label.
        mocks, stdout = self.run_script('-f', '0', '-u', 'alice', '-l', 'bug')
        self.assert_only_feature_ran(mocks, 0)
        self.assertEqual(config.get_parameter('user'), 'alice')
        self.assertEqual(config.get_parameter('label'), 'bug')
