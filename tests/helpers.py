"""Test factories that produce plain dicts matching the JSON schema loaded by
Issue.from_json / Event.from_json, plus a loader that instantiates Issue
objects and injects them into data_loader._ISSUES.
"""

from datetime import datetime, timezone
from model import Issue


def make_event(**overrides) -> dict:
    """Return a plain dict representing one issue timeline event."""
    base = {
        "event_type": "labeled",
        "author": "tester",
        "event_date": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
        "label": None,
        "comment": None,
    }
    base.update(overrides)
    return base


def make_issue(**overrides) -> dict:
    """Return a plain dict representing one issue."""
    base = {
        "url": "https://github.com/example/repo/issues/1",
        "creator": "alice",
        "labels": ["bug"],
        "state": "open",
        "assignees": ["bob"],
        "title": "Example Issue",
        "text": "Body text",
        "number": 1,
        "created_date": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
        "updated_date": datetime(2025, 1, 2, tzinfo=timezone.utc).isoformat(),
        "timeline_url": "https://github.com/example/repo/issues/1/timeline",
        "events": [],
    }
    base.update(overrides)
    return base


def load_issues(dicts: list[dict]) -> list[Issue]:
    """Convert a list of issue dicts into Issue objects and store them in the
    data_loader singleton so subsequent code sees them without touching disk.
    """
    import data_loader

    data_loader._ISSUES = [Issue(d) for d in dicts]
    return data_loader._ISSUES
