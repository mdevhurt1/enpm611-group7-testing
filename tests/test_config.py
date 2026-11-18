"""Tests for config.py.

Covers get_parameter, convert_to_typed_value, set_parameter,
overwrite_from_args, _init_config and _get_default_path.
"""

import argparse
import json
import os
import tempfile
from unittest.mock import patch

import config
from .base import AnalysisTestCase


class ConfigTestCase(AnalysisTestCase):
    """Shared helpers for the config tests."""

    def _chdir(self, path: str) -> None:
        """Change cwd to `path` for the duration of the test."""
        original = os.getcwd()
        os.chdir(path)
        self.addCleanup(os.chdir, original)

    def _temp_dir(self) -> str:
        """Create a temp directory that is removed after the test."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return tmp.name

    def _write_config(self, directory: str, data: dict) -> str:
        """Write `data` as config.json inside `directory` and return its path."""
        path = os.path.join(directory, "config.json")
        with open(path, "w") as fout:
            json.dump(data, fout)
        return path


# -- get_parameter -----------------------------------------------------------

class TestGetParameter(ConfigTestCase):

    def test_environment_variable_beats_config_file(self) -> None:
        # 1. Config file says one thing; chdir so _get_default_path finds it.
        tmp = self._temp_dir()
        self._write_config(tmp, {"TEST_KEY": "from_file"})
        self._chdir(tmp)

        # 2. Environment says another; patch.dict restores os.environ after.
        with patch.dict(os.environ, {"TEST_KEY": "from_env"}):
            # 3. Environment wins.
            self.assertEqual(config.get_parameter("TEST_KEY"), "from_env")

        # Sanity: the file really was loaded, not an empty config.
        self.assertEqual(config._config, {"TEST_KEY": "from_file"})

    def test_json_prefix_is_stripped_and_parsed(self) -> None:
        self._chdir(self._temp_dir())
        
        with patch.dict(os.environ, {"TEST_KEY": "json:{\"a\": 1}"}):
            self.assertEqual(config.get_parameter("TEST_KEY"), {"a": 1})

    def test_key_only_in_config_file_comes_from_file(self) -> None:
        tmp = self._temp_dir()
        self._write_config(tmp, {"TEST_KEY": "from_file"})
        self._chdir(tmp)
        self.assertEqual(config.get_parameter("TEST_KEY"), "from_file")

    def test_unknown_key_returns_none(self) -> None:
        self._chdir(self._temp_dir())
        self.assertIsNone(config.get_parameter("UNKNOWN_KEY"))

    def test_unknown_key_with_default_returns_default(self) -> None:
        self._chdir(self._temp_dir())
        self.assertEqual(config.get_parameter("UNKNOWN_KEY", default=42), 42)


# -- convert_to_typed_value --------------------------------------------------

class TestConvertToTypedValue(ConfigTestCase):

    def test_numeric_string_becomes_int(self) -> None:
        self.assertEqual(config.convert_to_typed_value("42"), 42)

    def test_json_object_string_becomes_dict(self) -> None:
        self.assertEqual(config.convert_to_typed_value('{"a": 1}'), {"a": 1})

    def test_plain_string_stays_string(self) -> None:
        self.assertEqual(config.convert_to_typed_value("hello"), "hello")

    def test_none_stays_none(self) -> None:
        self.assertIsNone(config.convert_to_typed_value(None))


# -- set_parameter -----------------------------------------------------------

class TestSetParameter(ConfigTestCase):

    def test_string_is_stored_as_is(self) -> None:
        self.addCleanup(os.environ.pop, "TEST_KEY", None)
        config.set_parameter("TEST_KEY", "hello")
        self.assertEqual(os.environ["TEST_KEY"], "hello")

    def test_non_string_is_stored_with_json_prefix(self) -> None:
        self.addCleanup(os.environ.pop, "TEST_KEY", None)
        config.set_parameter("TEST_KEY", {"a": 1})
        self.assertEqual(os.environ["TEST_KEY"], "json:{\"a\": 1}")

    def test_non_string_round_trips_through_get_parameter(self) -> None:
        self.addCleanup(os.environ.pop, "TEST_KEY", None)
        config.set_parameter("TEST_KEY", {"a": 1})
        self.assertEqual(config.get_parameter("TEST_KEY"), {"a": 1})


# -- overwrite_from_args -----------------------------------------------------

class TestOverwriteFromArgs(ConfigTestCase):

    def test_writes_only_non_none_values(self) -> None:
        self._chdir(self._temp_dir())

        args = argparse.Namespace(
            user="alice",
            label=None,
            feature="new_feature",
            ENPM611_PROJECT_DATA_PATH=None,
        )
        config.overwrite_from_args(args)
        self.assertEqual(os.environ["user"], "alice")
        self.assertEqual(os.environ["feature"], "new_feature")
        self.assertNotIn("label", os.environ)
        self.assertNotIn("ENPM611_PROJECT_DATA_PATH", os.environ)



# -- _init_config ------------------------------------------------------------

class TestInitConfig(ConfigTestCase):

    def test_empty_config_when_file_is_missing(self) -> None:
        self._chdir(self._temp_dir())
        config._init_config()
        self.assertEqual(config._config, {})

    def test_second_call_does_not_reload(self) -> None:
        tmp = self._temp_dir()
        self._write_config(tmp, {"TEST_KEY": "from_file"})
        self._chdir(tmp)
        config._init_config()
        # Change the file after the first load.
        self._write_config(tmp, {"TEST_KEY": "changed"})
        config._init_config()
        # The config should still be the first one.
        self.assertEqual(config.get_parameter("TEST_KEY"), "from_file")


# -- _get_default_path -------------------------------------------------------

class TestGetDefaultPath(ConfigTestCase):

    def test_found_when_config_is_in_parent_directory(self) -> None:
        tmp = self._temp_dir()
        self._write_config(tmp, {"TEST_KEY": "from_file"})
        # Create a subdirectory and chdir into it.
        subdir = os.path.join(tmp, "subdir")
        os.mkdir(subdir)
        self._chdir(subdir)
        # _get_default_path should find the config in the parent directory.
        path = config._get_default_path()
        self.assertEqual(os.path.realpath(path), os.path.realpath(os.path.join(tmp, "config.json")))
