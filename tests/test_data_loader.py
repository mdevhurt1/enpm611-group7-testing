import io
import json
import os
import runpy
import tempfile
from contextlib import redirect_stdout
from unittest.mock import patch

import config
import data_loader
from data_loader import DataLoader
from model import Event, Issue, State
from .base import AnalysisTestCase
from .helpers import make_event, make_issue


DATA_PATH_KEY = "ENPM611_PROJECT_DATA_PATH"


class DataLoaderTestCase(AnalysisTestCase):
    """Shared helpers for the data loader tests."""

    def setUp(self):
        super().setUp()
        # Start every test with an empty config so the repo's config.json
        # (which points at the real poetry_issues_all.json) is never read.
        # Tests opt in to a data path via the env variable or config._config.
        config._config = {}

    def _temp_dir(self) -> str:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return tmp.name

    def _write_data_file(self, content, name="issues.json") -> str:
        """Write `content` (a list to JSON-encode, or raw text) to a file."""
        path = os.path.join(self._temp_dir(), name)
        with open(path, "w") as fout:
            if isinstance(content, str):
                fout.write(content)
            else:
                json.dump(content, fout)
        return path

    def _use_data_file(self, content) -> str:
        """Write a data file and point the app at it via the env variable."""
        path = self._write_data_file(content)
        os.environ[DATA_PATH_KEY] = path
        return path

    def _get_issues_quietly(self, loader):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            issues = loader.get_issues()
        return issues, buffer.getvalue()


# -- __init__ ----------------------------------------------------------------

class TestInit(DataLoaderTestCase):

    def test_data_path_comes_from_environment_variable(self):
        os.environ[DATA_PATH_KEY] = "/some/where/issues.json"
        self.assertEqual(DataLoader().data_path, "/some/where/issues.json")

    def test_data_path_comes_from_config_file(self):
        config._config = {DATA_PATH_KEY: "/from/config.json"}
        self.assertEqual(DataLoader().data_path, "/from/config.json")

    def test_environment_variable_overrides_config_file(self):
        config._config = {DATA_PATH_KEY: "/from/config.json"}
        os.environ[DATA_PATH_KEY] = "/from/env.json"
        self.assertEqual(DataLoader().data_path, "/from/env.json")

    def test_data_path_is_none_when_not_configured(self):
        config._config = {}
        self.assertIsNone(DataLoader().data_path)

    def test_data_path_is_read_once_at_construction(self):
        os.environ[DATA_PATH_KEY] = "/first.json"
        loader = DataLoader()
        os.environ[DATA_PATH_KEY] = "/second.json"
        self.assertEqual(loader.data_path, "/first.json")


# -- _load -------------------------------------------------------------------

class TestLoad(DataLoaderTestCase):

    def test_missing_path_raises_file_not_found(self):
        config._config = {}
        with self.assertRaises(FileNotFoundError) as ctx:
            DataLoader()._load()
        self.assertIn(DATA_PATH_KEY, str(ctx.exception))

    def test_empty_path_raises_file_not_found(self):
        loader = DataLoader()
        loader.data_path = ""
        with self.assertRaises(FileNotFoundError):
            loader._load()

    def test_nonexistent_file_raises_file_not_found(self):
        missing = os.path.join(self._temp_dir(), "does_not_exist.json")
        os.environ[DATA_PATH_KEY] = missing
        with self.assertRaises(FileNotFoundError) as ctx:
            DataLoader()._load()
        self.assertIn("does_not_exist.json", str(ctx.exception))

    def test_directory_path_raises_file_not_found(self):
        os.environ[DATA_PATH_KEY] = self._temp_dir()
        with self.assertRaises(FileNotFoundError):
            DataLoader()._load()

    def test_valid_file_returns_issue_objects(self):
        self._use_data_file([make_issue(number=1), make_issue(number=2)])
        issues = DataLoader()._load()
        self.assertEqual(len(issues), 2)
        self.assertTrue(all(isinstance(i, Issue) for i in issues))
        self.assertEqual([i.number for i in issues], [1, 2])

    def test_issue_fields_and_events_are_parsed(self):
        self._use_data_file([
            make_issue(
                number=9785,
                state="closed",
                labels=["kind/bug", "status/triage"],
                creator="dbrtly",
                created_date="2024-10-20T00:33:06+00:00",
                events=[
                    make_event(event_type="labeled", label="kind/bug"),
                    make_event(event_type="closed",
                               event_date="2024-10-21T00:33:06+00:00"),
                ],
            )
        ])
        issue = DataLoader()._load()[0]
        self.assertEqual(issue.number, 9785)
        self.assertEqual(issue.state, State.closed)
        self.assertEqual(issue.labels, ["kind/bug", "status/triage"])
        self.assertEqual(issue.creator, "dbrtly")
        self.assertEqual(len(issue.events), 2)
        self.assertIsInstance(issue.events[0], Event)
        self.assertEqual(issue.events[0].label, "kind/bug")
        self.assertAlmostEqual(issue.days_to_close(), 1.0)

    def test_record_with_real_dataset_quirks_is_parsed(self):
        record = {
            "url": "https://github.com/python-poetry/poetry/issues/1234",
            "creator": "someone",
            "labels": ["kind/bug"],
            "state": "closed",
            "assignees": [],
            "title": "Mock issue with dataset quirks",
            "text": None,
            "number": 1234,
            "created_date": "2023-05-01T10:00:00+00:00",
            "updated_date": "2023-05-03T10:00:00+00:00",
            "timeline_url": "https://api.github.com/repos/python-poetry/poetry/issues/1234/timeline",
            "events": [
                {"event_type": "commented", "author": None,
                 "event_date": "2023-05-02T10:00:00+00:00",
                 "comment": "from a deleted account"},
                {"event_type": "closed", "author": "maintainer",
                 "event_date": None},
            ],
        }
        self._use_data_file([record])
        issue = DataLoader()._load()[0]

        self.assertIsNone(issue.text)
        self.assertIsNone(issue.events[0].author)
        self.assertIsNone(issue.events[0].label)
        self.assertIsNone(issue.events[1].event_date)
        self.assertIsNone(issue.events[1].comment)
        # The closed event has no date, so no close date can be derived.
        self.assertIsNone(issue.closed_date)

    def test_empty_json_array_returns_empty_list(self):
        self._use_data_file([])
        self.assertEqual(DataLoader()._load(), [])

    def test_malformed_json_raises_decode_error(self):
        self._use_data_file('[{"number": 1,')
        with self.assertRaises(json.JSONDecodeError):
            DataLoader()._load()


# -- get_issues --------------------------------------------------------------

class TestGetIssues(DataLoaderTestCase):

    def test_first_call_loads_caches_and_prints_summary(self):
        path = self._use_data_file([make_issue(number=1), make_issue(number=2)])
        issues, output = self._get_issues_quietly(DataLoader())

        self.assertEqual(len(issues), 2)
        self.assertIs(data_loader._ISSUES, issues)
        self.assertEqual(output.strip(), f"Loaded 2 issues from {path}.")

    def test_second_call_returns_cache_without_reloading(self):
        self._use_data_file([make_issue()])
        loader = DataLoader()
        with patch.object(DataLoader, "_load", wraps=loader._load) as spy:
            first, _ = self._get_issues_quietly(loader)
            second, output = self._get_issues_quietly(loader)

        spy.assert_called_once()
        self.assertIs(first, second)
        self.assertEqual(output, "")  # no second "Loaded ..." message

    def test_cache_is_shared_between_loader_instances(self):
        self._use_data_file([make_issue(number=1)])
        first, _ = self._get_issues_quietly(DataLoader())

        # A second loader pointed at a different file still gets the
        # cached issues: the singleton is module-level by design.
        self._use_data_file([make_issue(number=2), make_issue(number=3)])
        second, _ = self._get_issues_quietly(DataLoader())

        self.assertIs(first, second)
        self.assertEqual([i.number for i in second], [1])

    def test_preloaded_cache_skips_disk(self):
        data_loader._ISSUES = []
        config._config = {}  # no data path configured at all
        issues, output = self._get_issues_quietly(DataLoader())
        self.assertEqual(issues, [])
        self.assertEqual(output, "")

    def test_failed_load_leaves_cache_empty_so_retry_works(self):
        config._config = {}
        with self.assertRaises(FileNotFoundError):
            DataLoader().get_issues()
        self.assertIsNone(data_loader._ISSUES)

        self._use_data_file([make_issue()])
        issues, _ = self._get_issues_quietly(DataLoader())
        self.assertEqual(len(issues), 1)


# -- __main__ ----------------------------------------------------------------

class TestMainBlock(DataLoaderTestCase):

    def test_running_module_as_script_loads_issues(self):
        path = self._use_data_file([make_issue(), make_issue(number=2)])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            runpy.run_module("data_loader", run_name="__main__")
        self.assertIn(f"Loaded 2 issues from {path}.", buffer.getvalue())
