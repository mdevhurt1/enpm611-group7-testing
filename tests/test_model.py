"""Tests for model.py: _as_utc, State, Event, and Issue."""

from datetime import datetime, timedelta, timezone

from .base import AnalysisTestCase
from .helpers import make_event, make_issue
from model import Event, Issue, State, _as_utc

TODO = "not implemented yet"


class TestAsUtc(AnalysisTestCase):
    """_as_utc normalizes datetimes so they can always be subtracted."""

    def test_none_returns_none(self) -> None:
        datetime_value = None
        result = _as_utc(datetime_value)
        self.assertIsNone(result)

    def test_naive_datetime_is_tagged_utc(self) -> None:
        datetime_value = datetime(2024, 1, 1, 12, 0, 0)
        result = _as_utc(datetime_value)
        self.assertEqual(result.tzinfo, timezone.utc)
        self.assertEqual(result.hour, 12)

    def test_aware_datetime_is_converted_to_utc(self) -> None:
        datetime_value = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone(timedelta(hours=-5)))
        result = _as_utc(datetime_value)
        self.assertEqual(result.tzinfo, timezone.utc)
        self.assertEqual(result.hour, 17)  # EST is UTC-5, so 12:00 EST is 17:00 UTC


class TestState(AnalysisTestCase):
    """State is a str-backed enum with open and closed members."""

    def test_members_match_json_values(self) -> None:
        self.assertEqual(State.open.value, 'open')
        self.assertEqual(State.closed.value, 'closed')

    def test_lookup_by_name_matches_lookup_by_value(self) -> None:
        self.assertEqual(State['open'], State.open)
        self.assertEqual(State['closed'], State.closed)

    def test_unknown_name_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            _ = State['unknown']


class TestEvent(AnalysisTestCase):
    """Event construction and from_json parsing."""

    # -- construction --------------------------------------------------------

    def test_no_json_leaves_all_fields_none(self) -> None:
        event = Event(None)
        self.assertIsNone(event.event_type)
        self.assertIsNone(event.author)
        self.assertIsNone(event.event_date)
        self.assertIsNone(event.label)
        self.assertIsNone(event.comment)

    def test_from_json_populates_fields(self) -> None:
        jobj = {
            'event_type': 'closed',
            'author': 'user1',
            'event_date': '2024-01-01T12:00:00Z',
            'label': 'bug',
            'comment': 'Fixed the issue.'
        }
        event = Event(jobj)
        self.assertEqual(event.event_type, 'closed')
        self.assertEqual(event.author, 'user1')
        self.assertEqual(event.event_date.isoformat(), '2024-01-01T12:00:00+00:00')
        self.assertEqual(event.label, 'bug')
        self.assertEqual(event.comment, 'Fixed the issue.')

    # -- event_date ----------------------------------------------------------

    def test_event_date_is_parsed_to_datetime(self) -> None:
        jobj = {'event_date': '2024-01-01T12:00:00Z'}
        event = Event(jobj)
        self.assertIsInstance(event.event_date, datetime)
        self.assertEqual(event.event_date.isoformat(), '2024-01-01T12:00:00+00:00')

    def test_missing_event_date_leaves_none(self) -> None:
        jobj = {
            'event_type': 'closed',
            'author': 'user1',
            'event_date': None,
            'label': 'bug',
            'comment': 'Fixed the issue.'
        }
        event = Event(jobj)
        self.assertIsNone(event.event_date)

    def test_unparseable_event_date_leaves_none(self) -> None:
        jobj = {
            'event_type': 'closed',
            'author': 'user1',
            'event_date': 'not_a_date',
            'label': 'bug',
            'comment': 'Fixed the issue.'
        }
        event = Event(jobj)
        self.assertIsNone(event.event_date)

    # -- is_human ------------------------------------------------------------

    def test_is_human_true_for_regular_user(self) -> None:
        jobj = {
            'event_type': 'closed',
            'author': 'user1',
            'event_date': '2024-01-01T12:00:00Z',
            'label': 'bug',
            'comment': 'Fixed the issue.'
        }
        event = Event(jobj)
        self.assertTrue(event.is_human)

    def test_is_human_false_for_bot_author(self) -> None:
        jobj = {
            'event_type': 'closed',
            'author': 'github-actions[bot]',
            'event_date': '2024-01-01T12:00:00Z',
            'label': 'bug',
            'comment': 'Fixed the issue.'
        }
        event = Event(jobj)
        self.assertFalse(event.is_human)


    def test_is_human_false_for_missing_author(self) -> None:
        jobj = {
            'event_type': 'closed',
            'author': None,
            'event_date': '2024-01-01T12:00:00Z',
            'label': 'bug',
            'comment': 'Fixed the issue.'
        }
        event = Event(jobj)
        self.assertFalse(event.is_human)


class TestIssueFromJson(AnalysisTestCase):
    """Issue construction and from_json parsing."""

    # -- construction --------------------------------------------------------

    def test_no_json_uses_defaults(self) -> None:
        issue = Issue(None)
        self.assertIsNone(issue.url)
        self.assertIsNone(issue.creator)
        self.assertEqual(issue.labels, [])
        self.assertIsNone(issue.state)
        self.assertEqual(issue.assignees, [])
        self.assertIsNone(issue.title)
        self.assertIsNone(issue.text)
        self.assertEqual(issue.number, -1)
        self.assertIsNone(issue.created_date)
        self.assertIsNone(issue.updated_date)
        self.assertIsNone(issue.timeline_url)
        self.assertEqual(issue.events, [])

    def test_from_json_populates_scalar_fields(self) -> None:
        jobj = {
            'url': 'https://api.github.com/repos/user/repo/issues/1',
            'creator': 'user1',
            'state': 'open',
            'title': 'Issue title',
            'text': 'Issue description',
            'number': 1,
            'created_date': '2024-01-01T12:00:00Z',
            'updated_date': '2024-01-02T12:00:00Z',
            'timeline_url': 'https://api.github.com/repos/user/repo/issues/1/timeline',
            'labels': ['bug', 'enhancement'],
            'assignees': ['user2', 'user3'],
            'events': [make_event(event_type='labeled'), make_event(event_type='commented')]
        }
        issue = Issue(jobj)
        self.assertEqual(issue.url, jobj['url'])
        self.assertEqual(issue.creator, jobj['creator'])
        self.assertEqual(issue.state.value, jobj['state'])
        self.assertEqual(issue.title, jobj['title'])
        self.assertEqual(issue.text, jobj['text'])
        self.assertEqual(issue.number, jobj['number'])
        self.assertEqual(issue.created_date.isoformat(), '2024-01-01T12:00:00+00:00')
        self.assertEqual(issue.updated_date.isoformat(), '2024-01-02T12:00:00+00:00')
        self.assertEqual(issue.timeline_url, jobj['timeline_url'])
        self.assertEqual(issue.labels, jobj['labels'])
        self.assertEqual(issue.assignees, jobj['assignees'])
        self.assertEqual([e.event_type for e in issue.events], ['labeled', 'commented'])

    def test_missing_list_fields_default_to_empty(self) -> None:
        jobj = {
            'url': 'https://api.github.com/repos/user/repo/issues/1',
            'creator': 'user1',
            'state': 'open',
            'title': 'Issue title',
            'text': 'Issue description',
            'number': 1,
            'created_date': '2024-01-01T12:00:00Z',
            'updated_date': '2024-01-02T12:00:00Z',
            'timeline_url': 'https://api.github.com/repos/user/repo/issues/1/timeline'
        }
        issue = Issue(jobj)
        self.assertEqual(issue.labels, [])
        self.assertEqual(issue.assignees, [])
        self.assertEqual(issue.events, [])

    # -- state ---------------------------------------------------------------

    def test_state_string_maps_to_enum(self) -> None:
        jobj = {
            'url': 'https://api.github.com/repos/user/repo/issues/1',
            'creator': 'user1',
            'state': 'open',
            'title': 'Issue title',
            'text': 'Issue description',
            'number': 1,
            'created_date': '2024-01-01T12:00:00Z',
            'updated_date': '2024-01-02T12:00:00Z',
            'timeline_url': 'https://api.github.com/repos/user/repo/issues/1/timeline'
        }
        issue = Issue(jobj)
        self.assertEqual(issue.state, State.open)

    def test_unknown_state_raises_key_error(self) -> None:
        jobj = {
            'url': 'https://api.github.com/repos/user/repo/issues/1',
            'creator': 'user1',
            'state': 'unknown',
            'title': 'Issue title',
            'text': 'Issue description',
            'number': 1,
            'created_date': '2024-01-01T12:00:00Z',
            'updated_date': '2024-01-02T12:00:00Z',
            'timeline_url': 'https://api.github.com/repos/user/repo/issues/1/timeline'
        }
        with self.assertRaises(KeyError):
            _ = Issue(jobj)

    # -- number --------------------------------------------------------------

    def test_number_is_coerced_to_int(self) -> None:
        jobj = {
            'url': 'https://api.github.com/repos/user/repo/issues/1',
            'creator': 'user1',
            'state': 'open',
            'title': 'Issue title',
            'text': 'Issue description',
            'number': '42',
            'created_date': '2024-01-01T12:00:00Z',
            'updated_date': '2024-01-02T12:00:00Z',
            'timeline_url': 'https://api.github.com/repos/user/repo/issues/1/timeline'
        }
        issue = Issue(jobj)
        self.assertEqual(issue.number, 42)

    def test_missing_number_defaults_to_minus_one(self) -> None:
        jobj = {
            'url': 'https://api.github.com/repos/user/repo/issues/1',
            'creator': 'user1',
            'state': 'open',
            'title': 'Issue title',
            'text': 'Issue description',
            'created_date': '2024-01-01T12:00:00Z',
            'updated_date': '2024-01-02T12:00:00Z',
            'timeline_url': 'https://api.github.com/repos/user/repo/issues/1/timeline'
        }
        issue = Issue(jobj)
        self.assertEqual(issue.number, -1)

    def test_unparseable_number_defaults_to_minus_one(self) -> None:
        jobj = {
            'url': 'https://api.github.com/repos/user/repo/issues/1',
            'creator': 'user1',
            'state': 'open',
            'title': 'Issue title',
            'text': 'Issue description',
            'number': 'not_a_number',
            'created_date': '2024-01-01T12:00:00Z',
            'updated_date': '2024-01-02T12:00:00Z',
            'timeline_url': 'https://api.github.com/repos/user/repo/issues/1/timeline'
        }
        issue = Issue(jobj)
        self.assertEqual(issue.number, -1)

    # -- dates ---------------------------------------------------------------

    def test_dates_are_parsed_to_datetime(self) -> None:
        jobj = {
            'url': 'https://api.github.com/repos/user/repo/issues/1',
            'creator': 'user1',
            'state': 'open',
            'title': 'Issue title',
            'text': 'Issue description',
            'number': 1,
            'created_date': '2024-01-01T12:00:00Z',
            'updated_date': '2024-01-02T12:00:00Z',
            'timeline_url': 'https://api.github.com/repos/user/repo/issues/1/timeline'
        }
        issue = Issue(jobj)
        self.assertIsInstance(issue.created_date, datetime)
        self.assertIsInstance(issue.updated_date, datetime)
        self.assertEqual(issue.created_date.isoformat(), '2024-01-01T12:00:00+00:00')
        self.assertEqual(issue.updated_date.isoformat(), '2024-01-02T12:00:00+00:00')

    def test_unparseable_dates_leave_none(self) -> None:
        jobj = {
            'url': 'https://api.github.com/repos/user/repo/issues/1',
            'creator': 'user1',
            'state': 'open',
            'title': 'Issue title',
            'text': 'Issue description',
            'number': 1,
            'created_date': 'not_a_date',
            'updated_date': 'also_not_a_date',
            'timeline_url': 'https://api.github.com/repos/user/repo/issues/1/timeline'
        }
        issue = Issue(jobj)
        self.assertIsNone(issue.created_date)
        self.assertIsNone(issue.updated_date)

    # -- events --------------------------------------------------------------

    def test_events_are_built_as_event_objects(self) -> None:
        jobj = {
            'url': 'https://api.github.com/repos/user/repo/issues/1',
            'creator': 'user1',
            'state': 'open',
            'title': 'Issue title',
            'text': 'Issue description',
            'number': 1,
            'created_date': '2024-01-01T12:00:00Z',
            'updated_date': '2024-01-02T12:00:00Z',
            'timeline_url': 'https://api.github.com/repos/user/repo/issues/1/timeline',
            'events': [
                {'event_type': 'closed', 'author': 'user2', 'event_date': '2024-01-03T12:00:00Z'},
                {'event_type': 'reopened', 'author': 'user3', 'event_date': '2024-01-04T12:00:00Z'}
            ]
        }
        issue = Issue(jobj)
        self.assertEqual(len(issue.events), 2)
        self.assertIsInstance(issue.events[0], Event)
        self.assertIsInstance(issue.events[1], Event)


class TestIssueClosedDate(AnalysisTestCase):
    """Issue.closed_date picks the most recent 'closed' event."""

    def test_no_events_returns_none(self) -> None:
        jobj = {
            'url': 'https://api.github.com/repos/user/repo/issues/1',
            'creator': 'user1',
            'state': 'open',
            'title': 'Issue title',
            'text': 'Issue description',
            'number': 1,
            'created_date': '2024-01-01T12:00:00Z',
            'updated_date': '2024-01-02T12:00:00Z',
            'timeline_url': 'https://api.github.com/repos/user/repo/issues/1/timeline'
        }
        issue = Issue(jobj)
        self.assertIsNone(issue.closed_date)

    def test_no_closed_event_returns_none(self) -> None:
        jobj = {
            'url': 'https://api.github.com/repos/user/repo/issues/1',
            'creator': 'user1',
            'state': 'open',
            'title': 'Issue title',
            'text': 'Issue description',
            'number': 1,
            'created_date': '2024-01-01T12:00:00Z',
            'updated_date': '2024-01-02T12:00:00Z',
            'timeline_url': 'https://api.github.com/repos/user/repo/issues/1/timeline',
            'events': [
                {'event_type': 'reopened', 'author': 'user3', 'event_date': '2024-01-04T12:00:00Z'}
            ]
        }
        issue = Issue(jobj)
        self.assertIsNone(issue.closed_date)

    def test_single_closed_event_returns_its_date(self) -> None:
        jobj = {
            'url': 'https://api.github.com/repos/user/repo/issues/1',
            'creator': 'user1',
            'state': 'closed',
            'title': 'Issue title',
            'text': 'Issue description',
            'number': 1,
            'created_date': '2024-01-01T12:00:00Z',
            'updated_date': '2024-01-02T12:00:00Z',
            'timeline_url': 'https://api.github.com/repos/user/repo/issues/1/timeline',
            'events': [
                {'event_type': 'closed', 'author': 'user2', 'event_date': '2024-01-03T12:00:00Z'}
            ]
        }
        issue = Issue(jobj)
        self.assertEqual(issue.closed_date.isoformat(), '2024-01-03T12:00:00+00:00')

    def test_multiple_closed_events_returns_latest(self) -> None:
        jobj = {
            'url': 'https://api.github.com/repos/user/repo/issues/1',
            'creator': 'user1',
            'state': 'closed',
            'title': 'Issue title',
            'text': 'Issue description',
            'number': 1,
            'created_date': '2024-01-01T12:00:00Z',
            'updated_date': '2024-01-02T12:00:00Z',
            'timeline_url': 'https://api.github.com/repos/user/repo/issues/1/timeline',
            'events': [
                {'event_type': 'closed', 'author': 'user2', 'event_date': '2024-01-03T12:00:00Z'},
                {'event_type': 'closed', 'author': 'user3', 'event_date': '2024-01-04T12:00:00Z'}
            ]
        }
        issue = Issue(jobj)
        self.assertEqual(issue.closed_date.isoformat(), '2024-01-04T12:00:00+00:00')

    def test_closed_event_without_date_is_ignored(self) -> None:
        jobj = {
            'url': 'https://api.github.com/repos/user/repo/issues/1',
            'creator': 'user1',
            'state': 'closed',
            'title': 'Issue title',
            'text': 'Issue description',
            'number': 1,
            'created_date': '2024-01-01T12:00:00Z',
            'updated_date': '2024-01-02T12:00:00Z',
            'timeline_url': 'https://api.github.com/repos/user/repo/issues/1/timeline',
            'events': [
                {'event_type': 'closed', 'author': 'user2', 'event_date': None},
                {'event_type': 'closed', 'author': 'user3', 'event_date': '2024-01-04T12:00:00Z'}
            ]
        }
        issue = Issue(jobj)
        self.assertEqual(issue.closed_date.isoformat(), '2024-01-04T12:00:00+00:00')

    def test_result_is_timezone_aware_utc(self) -> None:
        jobj = {
            'url': 'https://api.github.com/repos/user/repo/issues/1',
            'creator': 'user1',
            'state': 'closed',
            'title': 'Issue title',
            'text': 'Issue description',
            'number': 1,
            'created_date': '2024-01-01T12:00:00Z',
            'updated_date': '2024-01-02T12:00:00Z',
            'timeline_url': 'https://api.github.com/repos/user/repo/issues/1/timeline',
            'events': [
                {'event_type': 'closed', 'author': 'user2', 'event_date': '2024-01-03T12:00:00Z'}
            ]
        }
        issue = Issue(jobj)
        self.assertEqual(issue.closed_date.tzinfo, timezone.utc)


class TestIssueDaysToClose(AnalysisTestCase):
    """Issue.days_to_close measures creation to closing in days."""

    def test_open_issue_returns_none(self) -> None:
        jobj = {
            'url': 'https://api.github.com/repos/user/repo/issues/1',
            'creator': 'user1',
            'state': 'open',
            'title': 'Issue title',
            'text': 'Issue description',
            'number': 1,
            'created_date': '2024-01-01T12:00:00Z',
            'updated_date': '2024-01-02T12:00:00Z',
            'timeline_url': 'https://api.github.com/repos/user/repo/issues/1/timeline',
            'events': []
        }
        issue = Issue(jobj)
        self.assertIsNone(issue.days_to_close())

    def test_closed_issue_without_closed_event_returns_none(self) -> None:
        jobj = {
            'url': 'https://api.github.com/repos/user/repo/issues/1',
            'creator': 'user1',
            'state': 'closed',
            'title': 'Issue title',
            'text': 'Issue description',
            'number': 1,
            'created_date': '2024-01-01T12:00:00Z',
            'updated_date': '2024-01-02T12:00:00Z',
            'timeline_url': 'https://api.github.com/repos/user/repo/issues/1/timeline',
            'events': []
        }
        issue = Issue(jobj)
        self.assertIsNone(issue.days_to_close())

    def test_missing_created_date_returns_none(self) -> None:
        jobj = {
            'url': 'https://api.github.com/repos/user/repo/issues/1',
            'creator': 'user1',
            'state': 'closed',
            'title': 'Issue title',
            'text': 'Issue description',
            'number': 1,
            'created_date': None,
            'updated_date': '2024-01-02T12:00:00Z',
            'timeline_url': 'https://api.github.com/repos/user/repo/issues/1/timeline',
            'events': [
                {'event_type': 'closed', 'author': 'user2', 'event_date': '2024-01-03T12:00:00Z'}
            ]
        }
        issue = Issue(jobj)
        self.assertIsNone(issue.days_to_close())

    def test_computes_fractional_days(self) -> None:
        jobj = {
            'url': 'https://api.github.com/repos/user/repo/issues/1',
            'creator': 'user1',
            'state': 'closed',
            'title': 'Issue title',
            'text': 'Issue description',
            'number': 1,
            'created_date': '2024-01-01T12:00:00Z',
            'updated_date': '2024-01-02T12:00:00Z',
            'timeline_url': 'https://api.github.com/repos/user/repo/issues/1/timeline',
            'events': [
                {'event_type': 'closed', 'author': 'user2', 'event_date': '2024-01-03T18:00:00Z'}
            ]
        }
        issue = Issue(jobj)
        self.assertAlmostEqual(issue.days_to_close(), 2.25)  # 2 days and 6 hours

    def test_closed_before_created_returns_none(self) -> None:
        jobj = {
            'url': 'https://api.github.com/repos/user/repo/issues/1',
            'creator': 'user1',
            'state': 'closed',
            'title': 'Issue title',
            'text': 'Issue description',
            'number': 1,
            'created_date': '2024-01-03T12:00:00Z',
            'updated_date': '2024-01-04T12:00:00Z',
            'timeline_url': 'https://api.github.com/repos/user/repo/issues/1/timeline',
            'events': [
                {'event_type': 'closed', 'author': 'user2', 'event_date': '2024-01-02T12:00:00Z'}
            ]
        }
        issue = Issue(jobj)
        self.assertIsNone(issue.days_to_close())

    def test_naive_created_date_is_treated_as_utc(self) -> None:
        jobj = {
            'url': 'https://api.github.com/repos/user/repo/issues/1',
            'creator': 'user1',
            'state': 'closed',
            'title': 'Issue title',
            'text': 'Issue description',
            'number': 1,
            'created_date': '2024-01-01T12:00:00',  # naive datetime
            'updated_date': '2024-01-02T12:00:00Z',
            'timeline_url': 'https://api.github.com/repos/user/repo/issues/1/timeline',
            'events': [
                {'event_type': 'closed', 'author': 'user2', 'event_date': '2024-01-03T12:00:00Z'}
            ]
        }
        issue = Issue(jobj)
        self.assertAlmostEqual(issue.days_to_close(), 2.0)  # 2 days


class TestIssueHumanComments(AnalysisTestCase):
    """Issue.human_comments returns comment events from real users."""

    def test_no_events_returns_empty_list(self) -> None:
        jobj = {
            'url': 'https://api.github.com/repos/user/repo/issues/1',
            'creator': 'user1',
            'state': 'open',
            'title': 'Issue title',
            'text': 'Issue description',
            'number': 1,
            'created_date': '2024-01-01T12:00:00Z',
            'updated_date': '2024-01-02T12:00:00Z',
            'timeline_url': 'https://api.github.com/repos/user/repo/issues/1/timeline',
            'events': []
        }
        issue = Issue(jobj)
        self.assertEqual(issue.human_comments(), [])

    def test_only_commented_events_are_returned(self) -> None:
        jobj = {
            'url': 'https://api.github.com/repos/user/repo/issues/1',
            'creator': 'user1',
            'state': 'open',
            'title': 'Issue title',
            'text': 'Issue description',
            'number': 1,
            'created_date': '2024-01-01T12:00:00Z',
            'updated_date': '2024-01-02T12:00:00Z',
            'timeline_url': 'https://api.github.com/repos/user/repo/issues/1/timeline',
            'events': [
                {'event_type': 'closed', 'author': 'user2', 'event_date': '2024-01-03T12:00:00Z'},
                {'event_type': 'commented', 'author': 'user3', 'event_date': '2024-01-04T12:00:00Z'},
                {'event_type': 'reopened', 'author': 'user4', 'event_date': '2024-01-05T12:00:00Z'}
            ]
        }
        issue = Issue(jobj)
        human_comments = issue.human_comments()
        self.assertEqual(len(human_comments), 1)
        self.assertEqual(human_comments[0].event_type, 'commented')
        self.assertEqual(human_comments[0].author, 'user3')

    def test_bot_comments_are_excluded(self) -> None:
        jobj = {
            'url': 'https://api.github.com/repos/user/repo/issues/1',
            'creator': 'user1',
            'state': 'open',
            'title': 'Issue title',
            'text': 'Issue description',
            'number': 1,
            'created_date': '2024-01-01T12:00:00Z',
            'updated_date': '2024-01-02T12:00:00Z',
            'timeline_url': 'https://api.github.com/repos/user/repo/issues/1/timeline',
            'events': [
                {'event_type': 'commented', 'author': 'github-actions[bot]', 'event_date': '2024-01-03T12:00:00Z'},
                {'event_type': 'commented', 'author': 'user3', 'event_date': '2024-01-04T12:00:00Z'}
            ]
        }
        issue = Issue(jobj)
        human_comments = issue.human_comments()
        self.assertEqual(len(human_comments), 1)
        self.assertEqual(human_comments[0].author, 'user3')

    def test_comments_without_author_are_excluded(self) -> None:
        jobj = {
            'url': 'https://api.github.com/repos/user/repo/issues/1',
            'creator': 'user1',
            'state': 'open',
            'title': 'Issue title',
            'text': 'Issue description',
            'number': 1,
            'created_date': '2024-01-01T12:00:00Z',
            'updated_date': '2024-01-02T12:00:00Z',
            'timeline_url': 'https://api.github.com/repos/user/repo/issues/1/timeline',
            'events': [
                {'event_type': 'commented', 'author': None, 'event_date': '2024-01-03T12:00:00Z'},
                {'event_type': 'commented', 'author': 'user3', 'event_date': '2024-01-04T12:00:00Z'}
            ]
        }
        issue = Issue(jobj)
        human_comments = issue.human_comments()
        self.assertEqual(len(human_comments), 1)
        self.assertEqual(human_comments[0].author, 'user3')

    def test_preserves_event_order(self) -> None:
        jobj = {
            'url': 'https://api.github.com/repos/user/repo/issues/1',
            'creator': 'user1',
            'state': 'open',
            'title': 'Issue title',
            'text': 'Issue description',
            'number': 1,
            'created_date': '2024-01-01T12:00:00Z',
            'updated_date': '2024-01-02T12:00:00Z',
            'timeline_url': 'https://api.github.com/repos/user/repo/issues/1/timeline',
            'events': [
                {'event_type': 'commented', 'author': 'user3', 'event_date': '2024-01-03T12:00:00Z'},
                {'event_type': 'commented', 'author': None, 'event_date': '2024-01-04T12:00:00Z'},
                {'event_type': 'commented', 'author': 'user4', 'event_date': '2024-01-05T12:00:00Z'}
            ]
        }
        issue = Issue(jobj)
        human_comments = issue.human_comments()
        self.assertEqual(len(human_comments), 2)
        self.assertEqual(human_comments[0].author, 'user3')
        self.assertEqual(human_comments[1].author, 'user4')
