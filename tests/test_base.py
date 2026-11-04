"""Tests for AnalysisTestCase: shared state must not leak between tests."""

import argparse
import os
import unittest
from unittest.mock import MagicMock, patch

import matplotlib.pyplot as plt

import config
import data_loader
from .base import AnalysisTestCase

APP_ENV_KEYS = ("user", "label", "feature", "ENPM611_PROJECT_DATA_PATH")


def _pollute_environment() -> None:
    """Set the variables the app sets when run.py is given --user/--label."""
    config.overwrite_from_args(
        argparse.Namespace(feature=1, user="alice", label="bug")
    )
    os.environ["ENPM611_PROJECT_DATA_PATH"] = "some/file.json"


class TestAnalysisTestCase(AnalysisTestCase):

    def test_setup_removes_app_environment_variables(self) -> None:
        _pollute_environment()
        self.setUp()
        for key in APP_ENV_KEYS:
            # Assert on the single value
            self.assertIsNone(os.environ.get(key), f"{key} was not removed")

    def test_teardown_removes_app_environment_variables(self) -> None:
        _pollute_environment()
        self.tearDown()
        for key in APP_ENV_KEYS:
            # Assert on the single value
            self.assertIsNone(os.environ.get(key), f"{key} was not removed")

    @unittest.skipIf(os.name == "nt", "environment names are case-insensitive on Windows")
    def test_login_user_variable_is_left_alone(self) -> None:
        with patch.dict(os.environ, {"USER": "login-name"}):
            self.setUp()
            self.tearDown()
            self.assertEqual(os.environ.get("USER"), "login-name")

    def test_teardown_resets_cached_module_state(self) -> None:
        data_loader._ISSUES = []
        config._config = {}
        self.tearDown()
        self.assertIsNone(data_loader._ISSUES)
        self.assertIsNone(config._config)

    def test_show_is_patched(self) -> None:
        self.assertIsInstance(plt.show, MagicMock)
        self.assertIs(plt.show, self.mock_show)


class TestSubclassWithOwnSetUpClass(AnalysisTestCase):
    """A subclass that overrides setUpClass without super() keeps the patch."""

    @classmethod
    def setUpClass(cls):
        cls.fixture = "anything"

    @classmethod
    def tearDownClass(cls):
        pass

    def test_show_is_still_patched(self) -> None:
        self.assertIsInstance(plt.show, MagicMock)
