"""Smoke tests proving discovery works and helpers build valid Issues."""

from .base import AnalysisTestCase
from model import Issue, Event, State
from .helpers import make_issue, make_event, load_issues


class TestDiscoverySmoke(AnalysisTestCase):
    """Runs under unittest discover and checks the helpers build valid Issues."""

    def test_load_issues_builds_valid_issues(self) -> None:
        """Create two issue dicts, load them, and verify both are valid Issue objects."""

        sample = [
            make_issue(number=1, url="https://example.com/1", title="First"),
            make_issue(number=2, url="https://example.com/2", state="closed", title="Second"),
        ]

        result = load_issues(sample)
        self.assertEqual(len(result), 2)

        # Issue #1 (open)
        i1 = result[0]
        self.assertIsInstance(i1, Issue)
        self.assertEqual(i1.title, "First")
        self.assertEqual(i1.number, 1)
        self.assertEqual(i1.state, State.open)

        # Issue #2 (closed)
        i2 = result[1]
        self.assertIsInstance(i2, Issue)
        self.assertEqual(i2.title, "Second")
        self.assertEqual(i2.state, State.closed)


class TestHelpersValidity(AnalysisTestCase):
    """Ensure make_issue / make_event produce dicts that Issue / Event can consume."""

    # -- make_issue ----------------------------------------------------------

    def test_make_issue_produces_valid_dict(self) -> None:
        d = make_issue()
        for key in ("url", "creator", "labels", "state", "assignees",
                     "title", "text", "number", "created_date",
                     "updated_date", "timeline_url", "events"):
            self.assertIn(key, d)

    def test_make_issue_default_state_is_open(self) -> None:
        d = make_issue()
        self.assertEqual(d["state"], "open")

    def test_make_issue_override_works(self) -> None:
        d = make_issue(state="closed", number=42, labels=["feature"])
        self.assertEqual(d["state"], "closed")
        self.assertEqual(d["number"], 42)
        self.assertIn("feature", d["labels"])

    def test_make_issue_builds_valid_issue_object(self) -> None:
        d = make_issue(state="closed")
        issue = Issue(d)
        self.assertIsInstance(issue, Issue)
        self.assertEqual(issue.state, State.closed)
        self.assertIsNotNone(issue.created_date)
        self.assertIsNotNone(issue.updated_date)

    # -- load_issues ---------------------------------------------------------

    def test_load_issues_injects_into_data_loader(self) -> None:
        dicts = [make_issue(number=10)]
        result = load_issues(dicts)
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], Issue)

        # Verify the singleton was also set so downstream code sees it
        import data_loader
        self.assertIs(data_loader._ISSUES, result)

    def test_load_issues_sets_singleton_twice(self) -> None:
        """Two calls both update the singleton (no caching in the helper)."""
        import data_loader
        dicts = [make_issue(number=1)]
        load_issues(dicts)
        first_singleton = data_loader._ISSUES
        self.assertEqual(len(first_singleton), 1)
        load_issues(dicts)
        second_singleton = data_loader._ISSUES
        # Second call replaced the singleton with a fresh list of Issues
        self.assertIsNot(second_singleton, first_singleton)
        self.assertIsInstance(second_singleton[0], Issue)

    # -- make_event ----------------------------------------------------------

    def test_make_event_produces_valid_dict(self) -> None:
        d = make_event()
        for key in ("event_type", "author", "event_date", "label", "comment"):
            self.assertIn(key, d)

    def test_make_event_override_works(self) -> None:
        d = make_event(event_type="closed", label="bug")
        self.assertEqual(d["event_type"], "closed")
        self.assertEqual(d["label"], "bug")

    # -- integration ---------------------------------------------------------

    def test_issue_with_events_roundtrips(self) -> None:
        """Create an issue with events, load it, and verify event parsing."""

        evt = make_event(
            event_type="labeled",
            label="enhancement",
            author="charlie",
        )
        dicts = [make_issue(events=[evt], number=99)]
        issues = load_issues(dicts)

        issue = issues[0]
        self.assertEqual(issue.number, 99)
        self.assertEqual(len(issue.events), 1)

        ev = issue.events[0]
        self.assertIsInstance(ev, Event)
        self.assertEqual(ev.event_type, "labeled")
        self.assertEqual(ev.label, "enhancement")
        self.assertEqual(ev.author, "charlie")
