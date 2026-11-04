import os
import unittest
from unittest.mock import patch

import matplotlib.pyplot as plt

# Local module imports (needed in tearDown)
import data_loader
import config


class AnalysisTestCase(unittest.TestCase):
    """Base test case that resets shared state between tests."""

    @classmethod
    def setUpClass(cls):
        # Patch matplotlib show for the entire test class
        cls._show_patcher = patch("matplotlib.pyplot.show")
        cls._show_patcher.start()

    @classmethod
    def tearDownClass(cls):
        plt.close("all")
        cls._show_patcher.stop()

    def setUp(self):
        # Reset cached module-level state
        data_loader._ISSUES = None
        config._config = None

        # Remove environment variables that can leak between tests
        for env_key in ("USER", "LABEL", "ENPM611_PROJECT_DATA_PATH"):
            os.environ.pop(env_key, None)

    def tearDown(self):
        # Reset cached module-level state
        data_loader._ISSUES = None
        config._config = None

        # Remove environment variables that can leak between tests
        for env_key in ("USER", "LABEL", "ENPM611_PROJECT_DATA_PATH"):
            os.environ.pop(env_key, None)

        plt.close("all")
