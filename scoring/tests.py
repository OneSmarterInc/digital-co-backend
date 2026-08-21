from django.test import TestCase

from core.models import TierOutcome
from core.models import Cohort, Run, Team
from core.state import default_run_state

from .models import Benchmark
from .services import compute_benchmark, compute_endgame_outcome, finalize_score

_seat_counter = 0


def _seat(team, tag):
    """Put a student in a firm.

    Standings only rank firms that are taking part, so a fixture with no
    members is not a cohort — it is a set of empty seats. These tests are about
    ordering, so the membership just has to exist.
    """
    global _seat_counter
    _seat_counter += 1
    from core.models import User

    student = User.objects.create_user(
        username=f'seat-{tag}-{_seat_counter}@example.com', password='pw',
    )
    team.members.add(student)
    return student


class ScoringTests(TestCase):
    def test_gate_caps_outcome(self):
        state = default_run_state()
        for key in state['accumulated_scores']:
            state['accumulated_scores'][key] = 20
        state['gates']['budget_credibility']['state'] = 'detonated'
        state['gates']['budget_credibility']['detonated'] = True
        self.assertEqual(compute_endgame_outcome(state), TierOutcome.WIN_WITH_SCARS)

    def test_board_denial_caps_outcome(self):
        state = default_run_state()
        for key in state['accumulated_scores']:
            state['accumulated_scores'][key] = 20
        state['flags']['board_verdict'] = 'denied'
        self.assertEqual(compute_endgame_outcome(state), TierOutcome.SQUEAK_THROUGH)

    def test_board_confidence_lost_caps_outcome(self):
        state = default_run_state()
        for key in state['accumulated_scores']:
            state['accumulated_scores'][key] = 20
        state['flags']['board_verdict'] = 'confidence_lost'
        self.assertEqual(compute_endgame_outcome(state), TierOutcome.DISASTER)

    def test_benchmark_orders_by_total_score(self):
        cohort = Cohort.objects.create(name='MIS Fall 2026')
        team_a = Team.objects.create(cohort=cohort, name='A')
        team_b = Team.objects.create(cohort=cohort, name='B')
        _seat(team_a, 'a')
        _seat(team_b, 'b')
        run_a = Run.objects.create(team=team_a)
        run_b = Run.objects.create(team=team_b)
        run_a.state['accumulated_scores']['strategic_judgment'] = 5
        run_b.state['accumulated_scores']['strategic_judgment'] = 9
        run_a.save()
        run_b.save()

        benchmark = compute_benchmark(cohort, 4)
        self.assertEqual(benchmark.standings[0]['team_name'], 'B')

    def test_week_11_benchmark_includes_trust(self):
        cohort = Cohort.objects.create(name='MISX Fall 2026')
        team_a = Team.objects.create(cohort=cohort, name='A')
        team_b = Team.objects.create(cohort=cohort, name='B')
        _seat(team_a, 'a')
        _seat(team_b, 'b')
        run_a = Run.objects.create(team=team_a)
        run_b = Run.objects.create(team=team_b)
        run_a.state['accumulated_scores']['strategic_judgment'] = 8
        run_b.state['accumulated_scores']['strategic_judgment'] = 10
        run_a.state['flags']['trust_state'] = 'repaired'
        run_a.state['flags']['data_advantage'] = 'preserved'
        run_b.state['flags']['trust_state'] = 'damaged'
        run_b.state['flags']['data_advantage'] = 'surrendered'
        run_a.save()
        run_b.save()

        benchmark = compute_benchmark(cohort, 11)
        self.assertEqual(benchmark.standings[0]['team_name'], 'A')
        self.assertEqual(benchmark.standings[0]['factors'], ['accumulated_score', 'trust'])

    def test_week_8_benchmark_omits_data_rights_fuse(self):
        cohort = Cohort.objects.create(name='MIS Fall 2027')
        team_a = Team.objects.create(cohort=cohort, name='A')
        team_b = Team.objects.create(cohort=cohort, name='B')
        _seat(team_a, 'a')
        _seat(team_b, 'b')
        run_a = Run.objects.create(team=team_a)
        run_b = Run.objects.create(team=team_b)
        run_a.state['accumulated_scores']['strategic_judgment'] = 8
        run_b.state['accumulated_scores']['strategic_judgment'] = 10
        run_a.state['flags']['trust_state'] = 'repaired'
        run_a.state['flags']['data_advantage'] = 'preserved'
        run_a.save()
        run_b.save()

        benchmark = compute_benchmark(cohort, 8)
        self.assertEqual(benchmark.standings[0]['team_name'], 'B')
        self.assertEqual(benchmark.standings[0]['trust_points'], 0)

# Create your tests here.


class BenchmarkGateTests(TestCase):
    """Standings must not publish until every playing firm has the round graded.

    They rank firms against each other on accumulated score, so a firm that is
    merely *not yet graded* looks identical to one that played badly — and the
    table is student-visible while the instructor is still working through the
    queue.
    """

    def setUp(self):
        from core.models import Cohort, Run, Team, Tier, User

        self.cohort = Cohort.objects.create(name='SIM-GATE', tier=Tier.UNDERGRAD)
        self.runs = []
        for n in (1, 2, 3):
            team = Team.objects.create(cohort=self.cohort, name=f'Team {n}')
            student = User.objects.create_user(username=f'gate-{n}@example.com', password='pw')
            team.members.add(student)
            self.runs.append((Run.objects.create(team=team), student))

    def _play_to(self, run, student, upto):
        """Submit every round up to and including `upto`, grading rounds below it."""
        from engine.services import submit_week, view_briefing
        from weeks.tests import (
            week1_payload, week2_payload, week3_payload, week4_payload,
        )

        payloads = {1: week1_payload, 2: week2_payload, 3: week3_payload, 4: week4_payload}
        for week in range(1, upto + 1):
            run.refresh_from_db()
            # Rounds do not self-advance; the instructor moves the cohort on.
            run.current_week = week
            run.save()
            instance = view_briefing(run)
            submit_week(
                instance,
                structured_payload=payloads[week](),
                deliverable_text='A considered memo with a clear plan.',
                submitted_by=student,
            )
            instance.refresh_from_db()
            if week < upto:
                finalize_score(instance.score_record, graded_by=student)
        instance.refresh_from_db()
        return instance.score_record

    def test_standings_are_withheld_until_the_last_firm_is_graded(self):
        """The record is always computed — Week 5 depends on a Benchmark
        existing — but it is not fit to show until every firm is in it."""
        from scoring.services import benchmark_ready

        records = [self._play_to(run, student, 4) for run, student in self.runs]

        finalize_score(records[0], graded_by=None)
        self.assertTrue(
            Benchmark.objects.filter(cohort=self.cohort, after_week=4).exists(),
            'the benchmark record must exist or Week 5 cannot open',
        )
        self.assertFalse(benchmark_ready(self.cohort, 4), 'shown while two firms were ungraded')

        finalize_score(records[1], graded_by=None)
        self.assertFalse(benchmark_ready(self.cohort, 4))

        # The last grade makes it visible, with no separate release step.
        finalize_score(records[2], graded_by=None)
        self.assertTrue(benchmark_ready(self.cohort, 4))
        benchmark = Benchmark.objects.get(cohort=self.cohort, after_week=4)
        self.assertEqual(len(benchmark.standings), 3)

    def test_week_5_is_never_frozen_by_an_ungraded_firm(self):
        """The reason computation is not gated: a firm that never submits would
        otherwise hold every other firm at Week 5 permanently."""
        from engine.services import submit_week, view_briefing
        from weeks.tests import week5_payload

        records = [self._play_to(run, student, 4) for run, student in self.runs]
        finalize_score(records[0], graded_by=None)  # only one firm graded

        run, student = self.runs[0]
        run.refresh_from_db()
        run.current_week = 5
        run.save()
        instance = view_briefing(run)
        submit_week(
            instance,
            structured_payload=week5_payload(),
            deliverable_text='Disciplined disruption read.',
            submitted_by=student,
        )
        instance.refresh_from_db()
        self.assertEqual(instance.week_number, 5)

    def test_an_empty_firm_does_not_hold_the_cohort_hostage(self):
        """A firm is created with a run attached, so an unfilled one would sit
        permanently ungraded and block the benchmark forever."""
        from core.models import Run, Team

        empty = Team.objects.create(cohort=self.cohort, name='Team 4')
        Run.objects.create(team=empty)

        for run, student in self.runs:
            finalize_score(self._play_to(run, student, 4), graded_by=None)

        from scoring.services import benchmark_ready
        self.assertTrue(benchmark_ready(self.cohort, 4), 'an empty firm blocked the cohort')
        benchmark = Benchmark.objects.get(cohort=self.cohort, after_week=4)
        names = [row['team_name'] for row in benchmark.standings]
        self.assertNotIn('Team 4', names, 'an empty firm was ranked')

    def test_pending_names_the_firms_still_owed(self):
        from scoring.services import benchmark_pending, benchmark_ready

        records = [self._play_to(run, student, 4) for run, student in self.runs]
        finalize_score(records[0], graded_by=None)

        pending = [t.name for t in benchmark_pending(self.cohort, 4)]
        self.assertEqual(sorted(pending), ['Team 2', 'Team 3'])
        self.assertFalse(benchmark_ready(self.cohort, 4))

        finalize_score(records[1], graded_by=None)
        finalize_score(records[2], graded_by=None)
        self.assertEqual(benchmark_pending(self.cohort, 4), [])
        self.assertTrue(benchmark_ready(self.cohort, 4))

    def test_regrading_after_publication_keeps_standings_current(self):
        """Re-grading is not a reason to withdraw a published table — every firm
        is still graded, so it simply recomputes."""
        records = [self._play_to(run, student, 4) for run, student in self.runs]
        for record in records:
            finalize_score(record, graded_by=None)
        self.assertTrue(Benchmark.objects.filter(cohort=self.cohort, after_week=4).exists())

        finalize_score(records[0], instructor_scores={'strategic_judgment': 5}, graded_by=None)
        self.assertTrue(Benchmark.objects.filter(cohort=self.cohort, after_week=4).exists())
