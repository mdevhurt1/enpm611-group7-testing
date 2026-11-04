import os
import unittest
from unittest.mock import patch

import matplotlib.pyplot as plt

import data_loader
import config


# Environment variables the app reads.
APP_ENV_KEYS = ("user", "label", "feature", "ENPM611_PROJECT_DATA_PATH")


class AnalysisTestCase(unittest.TestCase):
    """Base test case that resets shared state between tests.

    Subclasses that define their own setUp/tearDown must call
    super().setUp() / super().tearDown().
    """

    def setUp(self):
        self._reset_shared_state()

        # Keep charts from opening a window.
        show_patcher = patch("matplotlib.pyplot.show")
        self.mock_show = show_patcher.start()
        self.addCleanup(show_patcher.stop)

    def tearDown(self):
        self._reset_shared_state()
        plt.close("all")

    @staticmethod
    def _reset_shared_state():
        # Cached module-level state
        data_loader._ISSUES = None
        config._config = None

        # Environment variables that can leak between tests
        for env_key in APP_ENV_KEYS:
            os.environ.pop(env_key, None)
