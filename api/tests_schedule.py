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


class RoundCountdownAnchorTests(TestCase):
    def setUp(self):
        self.today = date.today()
        self.cohort = Cohort.objects.create(
            name='SIM-CLOCK', tier=Tier.UNDERGRAD, start_date=self.today, days_per_week=7,
        )

    def test_without_an_anchor_the_calendar_is_unchanged(self):
        """Cohorts predating the anchor keep exactly their old schedule."""
        rows = _rounds(self.cohort, 2)
        self.assertEqual(_end(rows, 1), _fmt_date(self.today + timedelta(days=7)))
        self.assertEqual(_end(rows, 2), _fmt_date(self.today + timedelta(days=14)))

    def test_a_round_advanced_early_closes_one_round_length_from_opening(self):
        """The reported bug: R1 showed 7 days, R2 showed 14 from the same 'now'."""
        self.cohort.current_round_opened_at = timezone.now()
        self.cohort.save(update_fields=['current_round_opened_at'])

        rows = _rounds(self.cohort, 2)
        self.assertEqual(
            _end(rows, 2), _fmt_date(self.today + timedelta(days=7)),
            'round 2 still closes on the calendar slot rather than a week from opening',
        )

    def test_later_rounds_follow_on_from_the_active_one(self):
        self.cohort.current_round_opened_at = timezone.now()
        self.cohort.save(update_fields=['current_round_opened_at'])

        rows = _rounds(self.cohort, 2)
        self.assertEqual(_end(rows, 3), _fmt_date(self.today + timedelta(days=14)))
        self.assertEqual(_end(rows, 4), _fmt_date(self.today + timedelta(days=21)))

    def test_completed_rounds_keep_their_original_dates(self):
        """Past rounds are history. Rewriting them to fit a later anchor would
        be a different lie from the one being fixed."""
        self.cohort.current_round_opened_at = timezone.now()
        self.cohort.save(update_fields=['current_round_opened_at'])

        rows = _rounds(self.cohort, 3)
        self.assertEqual(_end(rows, 1), _fmt_date(self.today + timedelta(days=7)))
        self.assertEqual(rows[0]['status'], 'Completed')

    def test_a_round_opened_late_closes_late(self):
        """The other direction: a class cancelled, the round opened a week on."""
        self.cohort.current_round_opened_at = timezone.now() + timedelta(days=10)
        self.cohort.save(update_fields=['current_round_opened_at'])

        rows = _rounds(self.cohort, 2)
        self.assertEqual(_end(rows, 2), _fmt_date(self.today + timedelta(days=17)))

    def test_extensions_still_lengthen_the_active_round(self):
        self.cohort.current_round_opened_at = timezone.now()
        self.cohort.round_extensions = {'2': 3}
        self.cohort.save(update_fields=['current_round_opened_at', 'round_extensions'])

        rows = _rounds(self.cohort, 2)
        self.assertEqual(rows[1]['extended_days'], 3)
        self.assertEqual(_end(rows, 2), _fmt_date(self.today + timedelta(days=10)))

    def test_a_cohort_with_no_start_date_still_renders(self):
        self.cohort.start_date = None
        self.cohort.current_round_opened_at = timezone.now()
        self.cohort.save(update_fields=['start_date', 'current_round_opened_at'])

        rows = _rounds(self.cohort, 2)
        self.assertEqual(_end(rows, 1), '—')
        # Once anchored, the active round and everything after it have real dates.
        self.assertEqual(_end(rows, 2), _fmt_date(self.today + timedelta(days=7)))
