"""The round countdown must measure from when a round opened.

The calendar is derived from start_date plus N round-lengths, which is only
correct if rounds advance on exactly that cadence. They do not: an instructor
advances early, extends for a holiday, or opens a round late. Before this, a sim
advanced a day early showed round 2 closing in fourteen days while round 1 had
shown seven, and the error compounded every round. Students plan against that
number.
"""
from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from api.instructor_api import _fmt_date, _rounds
from core.models import Cohort, Tier


def _end(rows, n):
    return rows[n - 1]['end']


def _closes(opened, days):
    """The end date of a round of `days` days that opened on `opened`.

    A round covers its full length inclusive of the opening day, so a seven-day
    round opening on the 15th ends on the 21st and the next opens on the 22nd.
    The end date used to be the day the successor began, which read as an
    overlap and put the deadline at midnight of the wrong day.
    """
    return _fmt_date(opened + timedelta(days=days - 1))


class RoundCountdownAnchorTests(TestCase):
    def setUp(self):
        self.today = date.today()
        self.cohort = Cohort.objects.create(
            name='SIM-CLOCK', tier=Tier.UNDERGRAD, start_date=self.today, days_per_week=7,
        )

    def test_without_an_anchor_the_calendar_is_unchanged(self):
        """Cohorts predating the anchor keep exactly their old schedule."""
        rows = _rounds(self.cohort, 2)
        self.assertEqual(_end(rows, 1), _closes(self.today, 7))
        self.assertEqual(_end(rows, 2), _closes(self.today, 14))

    def test_a_round_advanced_early_closes_one_round_length_from_opening(self):
        """The reported bug: R1 showed 7 days, R2 showed 14 from the same 'now'."""
        self.cohort.current_round_opened_at = timezone.now()
        self.cohort.save(update_fields=['current_round_opened_at'])

        rows = _rounds(self.cohort, 2)
        self.assertEqual(
            _end(rows, 2), _closes(self.today, 7),
            'round 2 still closes on the calendar slot rather than a week from opening',
        )

    def test_later_rounds_follow_on_from_the_active_one(self):
        self.cohort.current_round_opened_at = timezone.now()
        self.cohort.save(update_fields=['current_round_opened_at'])

        rows = _rounds(self.cohort, 2)
        self.assertEqual(_end(rows, 3), _closes(self.today, 14))
        self.assertEqual(_end(rows, 4), _closes(self.today, 21))

    def test_completed_rounds_keep_their_original_dates(self):
        """Past rounds are history. Rewriting them to fit a later anchor would
        be a different lie from the one being fixed."""
        self.cohort.current_round_opened_at = timezone.now()
        self.cohort.save(update_fields=['current_round_opened_at'])

        rows = _rounds(self.cohort, 3)
        self.assertEqual(_end(rows, 1), _closes(self.today, 7))
        self.assertEqual(rows[0]['status'], 'Completed')

    def test_a_round_opened_late_closes_late(self):
        """The other direction: a class cancelled, the round opened a week on."""
        self.cohort.current_round_opened_at = timezone.now() + timedelta(days=10)
        self.cohort.save(update_fields=['current_round_opened_at'])

        rows = _rounds(self.cohort, 2)
        self.assertEqual(_end(rows, 2), _closes(self.today, 17))

    def test_extensions_still_lengthen_the_active_round(self):
        self.cohort.current_round_opened_at = timezone.now()
        self.cohort.round_extensions = {'2': 3}
        self.cohort.save(update_fields=['current_round_opened_at', 'round_extensions'])

        rows = _rounds(self.cohort, 2)
        self.assertEqual(rows[1]['extended_days'], 3)
        self.assertEqual(_end(rows, 2), _closes(self.today, 10))

    def test_a_cohort_with_no_start_date_still_renders(self):
        self.cohort.start_date = None
        self.cohort.current_round_opened_at = timezone.now()
        self.cohort.save(update_fields=['start_date', 'current_round_opened_at'])

        rows = _rounds(self.cohort, 2)
        self.assertEqual(_end(rows, 1), '—')
        # Once anchored, the active round and everything after it have real dates.
        self.assertEqual(_end(rows, 2), _closes(self.today, 7))


class DeadlineInstantTests(TestCase):
    """The deadline is the end of the round's last day, in the cohort's zone.

    A bare date left every client to infer a time, and they inferred midnight
    UTC — the previous evening in New York, the same morning in Delhi.
    """

    def _cohort(self, tz):
        return Cohort.objects.create(
            name=f'SIM-TZ-{tz}', tier=Tier.UNDERGRAD,
            start_date=date(2026, 7, 15), days_per_week=7, timezone=tz,
        )

    def test_a_round_closes_at_the_configured_hour_on_its_final_day(self):
        """An afternoon deadline, not midnight: the instructor is awake for it."""
        rows = _rounds(self._cohort('America/New_York'), 1)
        self.assertEqual(rows[0]['end_at'], '2026-07-21T16:00:00-04:00')
        self.assertEqual(rows[0]['end'], _fmt_date(date(2026, 7, 21)))

    def test_the_close_time_is_set_in_one_place(self):
        """Changing the hour must not mean hunting through the calendar code."""
        from api.instructor_api import ROUND_CLOSE_HOUR, ROUND_CLOSE_MINUTE

        rows = _rounds(self._cohort('America/New_York'), 1)
        clock = rows[0]['end_at'].split('T')[1][:5]
        self.assertEqual(clock, f'{ROUND_CLOSE_HOUR:02d}:{ROUND_CLOSE_MINUTE:02d}')

    def test_the_next_round_opens_the_day_after_this_one_ends(self):
        rows = _rounds(self._cohort('America/New_York'), 1)
        self.assertEqual(rows[1]['start'], _fmt_date(date(2026, 7, 22)))

    def test_the_offset_is_the_cohorts_own(self):
        delhi = _rounds(self._cohort('Asia/Calcutta'), 1)[0]['end_at']
        york = _rounds(self._cohort('America/New_York'), 1)[0]['end_at']
        self.assertTrue(delhi.endswith('+05:30'), delhi)
        self.assertTrue(york.endswith('-04:00'), york)
        self.assertNotEqual(delhi, york, 'two zones produced the same instant')

    def test_daylight_saving_is_handled_by_the_zone_not_a_fixed_offset(self):
        cohort = self._cohort('America/New_York')
        cohort.start_date = date(2026, 1, 5)
        cohort.save(update_fields=['start_date'])
        # January is EST (-05:00); July is EDT (-04:00). A hardcoded offset
        # would be an hour wrong for half the term.
        self.assertTrue(_rounds(cohort, 1)[0]['end_at'].endswith('-05:00'))

    def test_an_unknown_timezone_falls_back_rather_than_raising(self):
        cohort = self._cohort('Not/AZone')
        rows = _rounds(cohort, 1)
        self.assertTrue(rows[0]['end_at'].endswith('+00:00'), rows[0]['end_at'])

    def test_the_zone_travels_with_the_row(self):
        rows = _rounds(self._cohort('America/New_York'), 1)
        self.assertEqual(rows[0]['timezone'], 'America/New_York')
