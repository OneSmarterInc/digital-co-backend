from django.test import TestCase

from core.models import TierOutcome
from core.models import Cohort, Run, Team
from core.state import default_run_state

from .services import compute_benchmark, compute_endgame_outcome


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
