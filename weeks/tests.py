from django.test import TestCase

from core.models import Cohort, Run, Team, Tier, User
from core.state import SCORE_DIMENSIONS
from engine.services import submit_week, view_briefing
from scoring.models import Benchmark
from scoring.services import reveal_benchmark, student_benchmark_payload
from scoring.services import finalize_score
from weeks.models import WeekInstanceStatus
from weeks.registry import registry


class WeekLifecycleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='student', password='pw')
        self.cohort = Cohort.objects.create(name='MIS Fall 2026', tier=Tier.UNDERGRAD)
        self.team = Team.objects.create(cohort=self.cohort, name='Team A')
        self.team.members.add(self.user)
        self.run = Run.objects.create(team=self.team)

    def test_week1_full_lifecycle_sound_path(self):
        instance = view_briefing(self.run)
        self.assertEqual(instance.status, WeekInstanceStatus.CONSULTATION)

        submission = submit_week(
            instance,
            structured_payload=week1_payload(),
            deliverable_text='A rigorous current-state memo with a 30-60-90 plan.',
            submitted_by=self.user,
        )
        instance.refresh_from_db()
        self.run.refresh_from_db()
        self.assertEqual(instance.status, WeekInstanceStatus.SUBMITTED)
        self.assertEqual(submission.week_instance, instance)
        self.assertEqual(len(self.run.state['decision_history']), 1)
        self.assertEqual(
            self.run.state['coherence_anchor'],
            'DigitalCo will turn the installed base into a data-and-services business while stabilizing the core.',
        )
        self.assertTrue(self.run.state['through_lines']['coherence']['anchor_set'])
        self.assertEqual(self.run.state['through_lines']['security_ot']['posture'], 1)
        self.assertEqual(self.run.state['through_lines']['security_ot']['neglect'], 0)
        self.assertEqual(self.run.state['relationships']['petrillo'], 1)
        self.assertIn('Hyperscaler + S/4 integrator contracts flagged in Week 1', self.run.state['through_lines']['cloud_lockin']['notes'])
        self.assertEqual(self.run.state['decision_history'][0]['decision_key'], 'inheritance')

        finalize_score(instance.score_record, instructor_scores={'coherence': 2})
        instance.refresh_from_db()
        self.run.refresh_from_db()
        self.assertEqual(instance.status, WeekInstanceStatus.SCORED)
        self.assertEqual(self.run.state['accumulated_scores']['strategic_judgment'], 3)
        self.assertEqual(self.run.state['accumulated_scores']['execution_consequence'], 2)
        self.assertEqual(self.run.state['accumulated_scores']['coherence'], 2)

    def test_week1_kill_connected_products_trap(self):
        submission = self._submit_with({'connected_products_disposition': 'kill'})
        self.run.refresh_from_db()
        self.assertIn('kill_connected_products', submission.active_week_instance.score_record.auto_components['trap_flags'])
        self.assertTrue(self.run.state['flags']['connected_products_killed'])

    def test_week1_commit_s4_blind_trap(self):
        submission = self._submit_with({'s4_disposition': 'commit_finish'})
        self.run.refresh_from_db()
        self.assertIn('commit_s4_blind', submission.active_week_instance.score_record.auto_components['trap_flags'])
        self.assertTrue(self.run.state['flags']['s4_precommitted'])

    def test_week1_ferraro_capture_trap(self):
        submission = self._submit_with({'primary_stakeholder_anchor': 'ferraro'})
        self.run.refresh_from_db()
        self.assertIn('ferraro_capture', submission.active_week_instance.score_record.auto_components['trap_flags'])
        self.assertEqual(self.run.state['relationships']['ferraro'], 2)

    def test_week1_ot_neglect_seeded_when_black_box_ignored(self):
        self._submit_with({
            'early_action': 'diagnose_only',
            'ot_black_box_engaged': False,
        })
        self.run.refresh_from_db()
        self.assertEqual(self.run.state['through_lines']['security_ot']['posture'], 0)
        self.assertEqual(self.run.state['through_lines']['security_ot']['neglect'], 1)

    def test_week1_contract_shape(self):
        module = registry.get(1)
        self.assertEqual(module.title, 'The Inheritance')
        self.assertEqual(module.reads_state(), [])
        self.assertGreaterEqual(len(module.artifacts(Tier.UNDERGRAD)), 4)
        self.assertIn('strategy_statement', [field.key for field in module.decision_spec(Tier.GRADUATE).fields])

    def test_week2_extends_week1_and_creates_patron_governance(self):
        self._submit_with({})
        self.run.refresh_from_db()
        self.run.state['through_lines']['coherence']['anchor_strength'] = 'strong'
        self.run.current_week = 2
        self.run.save()

        week2 = view_briefing(self.run)
        submission = submit_week(
            week2,
            structured_payload=week2_payload(),
            deliverable_text='Aligned IT strategy with stage-gated governance.',
            submitted_by=self.user,
        )
        self.run.refresh_from_db()
        week2.refresh_from_db()

        self.assertEqual(week2.status, WeekInstanceStatus.SUBMITTED)
        self.assertEqual(submission.week_instance.week_number, 2)
        self.assertEqual(week2.score_record.auto_components['components']['wk1_direction'], 'data_services')
        self.assertEqual(week2.score_record.auto_components['scores']['coherence'], 2)
        self.assertTrue(self.run.state['flags']['calloway_patron'])
        self.assertTrue(self.run.state['flags']['governance_built'])
        self.assertEqual(self.run.state['relationships']['calloway'], 2)
        self.assertEqual(self.run.state['relationships']['reinhardt'], 1)
        self.assertEqual(len(self.run.state['decision_history']), 2)
        self.assertEqual(self.run.state['decision_history'][1]['decision_key'], 'alignment')

        finalize_score(week2.score_record, instructor_scores={'deliverable_quality': 1})
        week2.refresh_from_db()
        self.run.refresh_from_db()
        self.assertEqual(week2.status, WeekInstanceStatus.SCORED)
        self.assertEqual(self.run.state['accumulated_scores']['coherence'], 2)

    def test_week2_coherence_drift_from_week1_data_services_to_stabilize(self):
        self._submit_with({})
        self.run.refresh_from_db()
        self.run.current_week = 2
        self.run.save()

        week2 = view_briefing(self.run)
        submit_week(
            week2,
            structured_payload=week2_payload({'alignment_choice': 'stabilize'}),
            deliverable_text='Safe stabilization plan.',
            submitted_by=self.user,
        )
        self.run.refresh_from_db()
        week2.refresh_from_db()

        self.assertIn('coherence_drift', week2.score_record.auto_components['trap_flags'])
        self.assertEqual(week2.score_record.auto_components['scores']['coherence'], -2)
        self.assertEqual(self.run.state['through_lines']['coherence']['drift_events'][0]['kind'], 'drift')

    def test_week2_weak_anchor_caps_continuity_bonus(self):
        self._submit_with({})
        self.run.refresh_from_db()
        self.run.state['through_lines']['coherence']['anchor_strength'] = 'weak'
        self.run.current_week = 2
        self.run.save()

        week2 = view_briefing(self.run)
        submit_week(
            week2,
            structured_payload=week2_payload(),
            deliverable_text='Aligned IT strategy.',
            submitted_by=self.user,
        )
        week2.refresh_from_db()
        self.assertEqual(week2.score_record.auto_components['scores']['coherence'], 1)

    def test_week2_mush_records_drift_and_no_governance_tax(self):
        self._submit_with({})
        self.run.refresh_from_db()
        self.run.current_week = 2
        self.run.save()

        week2 = view_briefing(self.run)
        submit_week(
            week2,
            structured_payload=week2_payload({
                'alignment_choice': 'balanced_split',
                'governance_included': False,
                'governance_has_stage_gates': False,
            }),
            deliverable_text='A compromise for everyone.',
            submitted_by=self.user,
        )
        self.run.refresh_from_db()
        week2.refresh_from_db()

        self.assertIn('mush', week2.score_record.auto_components['trap_flags'])
        self.assertIn('no_governance', week2.score_record.auto_components['trap_flags'])
        self.assertFalse(self.run.state['flags']['governance_built'])
        self.assertEqual(self.run.state['through_lines']['coherence']['drift_events'][0]['kind'], 'mush')

    def test_week2_different_week1_outcome_changes_coherence(self):
        self._submit_with({'connected_products_disposition': 'kill'})
        self.run.refresh_from_db()
        self.run.current_week = 2
        self.run.save()

        week2 = view_briefing(self.run)
        submit_week(
            week2,
            structured_payload=week2_payload(),
            deliverable_text='Transform anyway.',
            submitted_by=self.user,
        )
        week2.refresh_from_db()
        self.assertEqual(week2.score_record.auto_components['components']['wk1_direction'], 'stabilize')
        self.assertIn('coherence_drift', week2.score_record.auto_components['trap_flags'])

    def test_week2_contract_shape(self):
        module = registry.get(2)
        self.assertEqual(module.title, 'The Alignment Confrontation')
        self.assertEqual(module.reads_state(), [
            'coherence_anchor',
            'through_lines.coherence',
            'relationships',
            'through_lines.security_ot',
            'decision_history',
            'flags',
        ])
        self.assertIn('alignment_choice', [field.key for field in module.decision_spec(Tier.UNDERGRAD).fields])

    def test_week3_sound_path_uses_governance_and_converts_reinhardt(self):
        self._complete_week1_and_week2()
        week3 = view_briefing(self.run)
        submit_week(
            week3,
            structured_payload=week3_payload(),
            deliverable_text='Forward-looking restructure plan.',
            submitted_by=self.user,
        )
        week3.refresh_from_db()
        self.run.refresh_from_db()

        self.assertEqual(week3.status, WeekInstanceStatus.SUBMITTED)
        self.assertEqual(week3.score_record.auto_components['scores']['strategic_judgment'], 3)
        self.assertEqual(week3.score_record.auto_components['scores']['execution_consequence'], 3)
        self.assertEqual(self.run.state['gates']['budget_credibility']['state'], 'open')

        finalize_score(
            week3.score_record,
            instructor_scores={'deliverable_quality': 1},
            instructor_components={'plan_sound': True},
        )
        self.run.refresh_from_db()
        week3.refresh_from_db()
        self.assertEqual(week3.status, WeekInstanceStatus.SCORED)
        self.assertEqual(self.run.state['relationships']['reinhardt'], 3)
        self.assertEqual(self.run.state['gates']['budget_credibility']['state'], 'open')

    def test_week3_integrator_accelerator_persists_long_fuse(self):
        self._complete_week1_and_week2()
        week3 = view_briefing(self.run)
        submit_week(
            week3,
            structured_payload=week3_payload({'integrator_decision': 'take_accelerator'}),
            deliverable_text='Accelerator rescue plan.',
            submitted_by=self.user,
        )

        reloaded = Run.objects.get(pk=self.run.pk)
        self.assertTrue(reloaded.state['flags']['integrator_accelerator_taken'])
        self.assertEqual(reloaded.state['through_lines']['cloud_lockin']['depth'], 1)
        self.assertIn('Integrator accelerator taken in Week 3', reloaded.state['through_lines']['cloud_lockin']['notes'][-1])
        self.assertEqual(reloaded.state['decision_history'][-1]['week'], 3)
        self.assertEqual(reloaded.state['decision_history'][-1]['decision_key'], 'migration_reckoning')

    def test_week3_budget_gate_closes_on_money_thrown_without_sound_plan(self):
        self._complete_week1_and_week2()
        week3 = view_briefing(self.run)
        submit_week(
            week3,
            structured_payload=week3_payload({
                'migration_fate': 'rescue',
                'integrator_decision': 'take_accelerator',
            }),
            deliverable_text='Push through plan.',
            submitted_by=self.user,
        )
        week3.refresh_from_db()
        self.assertEqual(week3.score_record.auto_components['trap_flags'], [
            'sunk_cost_pushthrough',
            'integrator_lifeline',
            'misallocation',
        ])

        finalize_score(
            week3.score_record,
            instructor_components={'plan_sound': False},
        )
        self.run.refresh_from_db()
        self.assertEqual(self.run.state['gates']['budget_credibility']['state'], 'closed')
        self.assertEqual(self.run.state['gates']['budget_credibility']['set_week'], 3)
        self.assertEqual(self.run.state['relationships']['reinhardt'], -1)

    def test_week3_rescue_against_stabilize_week1_avoids_coherence_penalty(self):
        self._complete_week1_and_week2(week1_overrides={'connected_products_disposition': 'kill'})
        week3 = view_briefing(self.run)
        submit_week(
            week3,
            structured_payload=week3_payload({'migration_fate': 'rescue'}),
            deliverable_text='Core rescue plan.',
            submitted_by=self.user,
        )
        week3.refresh_from_db()
        self.assertIn('sunk_cost_pushthrough', week3.score_record.auto_components['trap_flags'])
        self.assertNotIn('misallocation', week3.score_record.auto_components['trap_flags'])
        self.assertEqual(week3.score_record.auto_components['scores']['coherence'], 0)

    def test_week3_no_governance_creates_improvisation_penalty(self):
        self._submit_with({})
        self.run.refresh_from_db()
        self.run.current_week = 2
        self.run.save()
        week2 = view_briefing(self.run)
        submit_week(
            week2,
            structured_payload=week2_payload({
                'governance_included': False,
                'governance_has_stage_gates': False,
            }),
            deliverable_text='No durable governance.',
            submitted_by=self.user,
        )
        self.run.refresh_from_db()
        self.run.current_week = 3
        self.run.save()

        week3 = view_briefing(self.run)
        submit_week(
            week3,
            structured_payload=week3_payload(),
            deliverable_text='Forward plan without governance.',
            submitted_by=self.user,
        )
        week3.refresh_from_db()
        self.assertEqual(week3.score_record.auto_components['scores']['execution_consequence'], 1)

    def test_week3_contract_shape(self):
        module = registry.get(3)
        self.assertEqual(module.title, 'The Reckoning')
        self.assertEqual(module.reads_state(), [
            'coherence_anchor',
            'through_lines.coherence',
            'decision_history',
            'flags.s4_precommitted',
            'flags.governance_built',
            'relationships',
            'gates.budget_credibility',
        ])
        self.assertIn('migration_fate', [field.key for field in module.decision_spec(Tier.GRADUATE).fields])

    def test_week4_sound_path_closes_phase_and_generates_benchmark(self):
        self._complete_week1_week2_week3()
        week4 = view_briefing(self.run)
        submit_week(
            week4,
            structured_payload=week4_payload(),
            deliverable_text='Core-versus-context sourcing memo.',
            submitted_by=self.user,
        )
        week4.refresh_from_db()
        self.run.refresh_from_db()
        self.assertEqual(week4.status, WeekInstanceStatus.SUBMITTED)
        self.assertEqual(week4.score_record.auto_components['scores']['strategic_judgment'], 3)
        self.assertEqual(self.run.state['through_lines']['cloud_lockin']['state'], 'unset')
        self.assertEqual(self.run.state['relationships']['fischer'], 1)

        finalize_score(week4.score_record, instructor_scores={'deliverable_quality': 1})
        week4.refresh_from_db()
        benchmark = Benchmark.objects.get(cohort=self.cohort, after_week=4)
        self.assertEqual(week4.status, WeekInstanceStatus.SCORED)
        self.assertIsNone(benchmark.revealed_at)
        self.assertEqual(benchmark.standings[0]['team_name'], 'Team A')

    def test_week4_sweet_deal_stacks_with_week3_integrator_depth(self):
        self._complete_week1_week2_week3(week3_overrides={'integrator_decision': 'take_accelerator'})
        self.run.refresh_from_db()
        self.assertEqual(self.run.state['through_lines']['cloud_lockin']['depth'], 1)

        week4 = view_briefing(self.run)
        submit_week(
            week4,
            structured_payload=week4_payload({'cloud_commitment': 'sweet_deal_as_written'}),
            deliverable_text='Take the generous cloud offer.',
            submitted_by=self.user,
        )
        self.run.refresh_from_db()
        week4.refresh_from_db()
        self.assertIn('sweet_deal_lockin', week4.score_record.auto_components['trap_flags'])
        self.assertEqual(self.run.state['through_lines']['cloud_lockin']['state'], 'locked')
        self.assertEqual(self.run.state['through_lines']['cloud_lockin']['depth'], 3)
        self.assertEqual(self.run.state['decision_history'][-1]['decision_key'], 'platform_sourcing')

    def test_week4_student_benchmark_payload_excludes_hidden_state(self):
        self._complete_week1_week2_week3(week3_overrides={'integrator_decision': 'take_accelerator'})
        week4 = view_briefing(self.run)
        submit_week(
            week4,
            structured_payload=week4_payload({'cloud_commitment': 'sweet_deal_as_written'}),
            deliverable_text='Take the generous cloud offer.',
            submitted_by=self.user,
        )
        week4.refresh_from_db()
        finalize_score(week4.score_record)
        self.run.refresh_from_db()
        benchmark = Benchmark.objects.get(cohort=self.cohort, after_week=4)
        payload = student_benchmark_payload(benchmark)
        rendered_payload = str(payload).lower()

        forbidden = [
            'week 7',
            'week 12',
            'fuse',
            'detonation',
            'lock-in crisis',
            'future consequence',
            'cloud_lockin',
            'lockin.depth',
            'lockin.notes',
            'integrator_accelerator_taken',
            'trap_flags',
            'budget_credibility',
            'gate_factor',
        ]
        for term in forbidden:
            self.assertNotIn(term, rendered_payload)

        self.assertTrue(self.run.state['flags']['integrator_accelerator_taken'])
        self.assertEqual(self.run.state['through_lines']['cloud_lockin']['state'], 'locked')
        self.assertGreater(self.run.state['through_lines']['cloud_lockin']['depth'], 0)

    def test_week4_benchmark_visibility_gating_and_no_spoiler_html(self):
        self._complete_week1_week2_week3()
        week4 = view_briefing(self.run)
        submit_week(
            week4,
            structured_payload=week4_payload(),
            deliverable_text='Core-versus-context sourcing memo.',
            submitted_by=self.user,
        )
        week4.refresh_from_db()
        finalize_score(week4.score_record)
        benchmark = Benchmark.objects.get(cohort=self.cohort, after_week=4)

        self.client.force_login(self.user)
        response = self.client.get(f'/benchmarks/{self.cohort.id}/4/')
        self.assertEqual(response.status_code, 403)

        reveal_benchmark(benchmark)
        response = self.client.get(f'/benchmarks/{self.cohort.id}/4/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode().lower()
        for term in ('week 7', 'week 12', 'fuse', 'detonation', 'lock-in crisis', 'future consequence'):
            self.assertNotIn(term, content)

    def test_week4_closed_budget_gate_pulls_benchmark_standing_down(self):
        other_user = User.objects.create_user(username='other', password='pw')
        other_team = Team.objects.create(cohort=self.cohort, name='Team B')
        other_team.members.add(other_user)
        other_run = Run.objects.create(team=other_team)

        self._complete_week1_week2_week3()
        other_week1 = view_briefing(other_run)
        submit_week(other_week1, structured_payload=week1_payload(), deliverable_text='Memo.', submitted_by=other_user)
        other_run.refresh_from_db()
        other_run.current_week = 2
        other_run.save()
        other_week2 = view_briefing(other_run)
        submit_week(other_week2, structured_payload=week2_payload(), deliverable_text='Alignment.', submitted_by=other_user)
        other_run.refresh_from_db()
        other_run.current_week = 3
        other_run.save()
        other_week3 = view_briefing(other_run)
        submit_week(
            other_week3,
            structured_payload=week3_payload({
                'migration_fate': 'rescue',
                'integrator_decision': 'take_accelerator',
            }),
            deliverable_text='Push through.',
            submitted_by=other_user,
        )
        other_week3.refresh_from_db()
        finalize_score(other_week3.score_record, instructor_components={'plan_sound': False})
        other_run.refresh_from_db()
        self.assertEqual(other_run.state['gates']['budget_credibility']['state'], 'closed')

        for run, user in ((self.run, self.user), (other_run, other_user)):
            run.current_week = 4
            run.save()
            week4 = view_briefing(run)
            submit_week(week4, structured_payload=week4_payload(), deliverable_text='Sourcing.', submitted_by=user)
            week4.refresh_from_db()
            finalize_score(week4.score_record)

        benchmark = Benchmark.objects.get(cohort=self.cohort, after_week=4)
        rows = {row['team_name']: row for row in benchmark.standings}
        self.assertLess(rows['Team B']['gate_factor'], rows['Team A']['gate_factor'])
        self.assertLess(rows['Team B']['benchmark_score'], rows['Team A']['benchmark_score'])

    def test_week4_contract_shape(self):
        module = registry.get(4)
        self.assertEqual(module.title, 'The Foundation')
        self.assertEqual(module.reads_state(), [
            'coherence_anchor',
            'through_lines.coherence',
            'decision_history',
            'gates.budget_credibility',
            'through_lines.cloud_lockin',
            'flags.integrator_accelerator_taken',
            'relationships',
        ])
        self.assertIn('cloud_commitment', [field.key for field in module.decision_spec(Tier.UNDERGRAD).fields])

    def test_week5_sound_path_sets_downstream_threads(self):
        self._complete_week1_week2_week3_week4()
        week5 = view_briefing(self.run)
        submit_week(
            week5,
            structured_payload=week5_payload(),
            deliverable_text='Disciplined disruption read.',
            submitted_by=self.user,
        )
        week5.refresh_from_db()
        self.run.refresh_from_db()

        self.assertEqual(week5.status, WeekInstanceStatus.SUBMITTED)
        self.assertEqual(week5.score_record.auto_components['scores']['strategic_judgment'], 3)
        self.assertEqual(week5.score_record.auto_components['scores']['execution_consequence'], 2)
        self.assertTrue(self.run.state['flags']['additive_threat_recognized'])
        self.assertEqual(self.run.state['flags']['innovation_capability'], 'embedded')
        self.assertFalse(self.run.state['flags']['meridian_chased'])
        self.assertEqual(self.run.state['relationships']['fischer'], 2)
        self.assertEqual(self.run.state['decision_history'][-1]['decision_key'], 'disruption_read')

    def test_week5_chasing_dazzle_sets_traps_and_drift(self):
        self._complete_week1_week2_week3_week4()
        week5 = view_briefing(self.run)
        submit_week(
            week5,
            structured_payload=week5_payload({
                'portfolio.autonomy': 'bet',
                'portfolio.digital_twins': 'bet',
                'meridian_response': 'chase',
            }),
            deliverable_text='Chase Meridian.',
            submitted_by=self.user,
        )
        week5.refresh_from_db()
        self.run.refresh_from_db()

        self.assertIn('chased_dazzle', week5.score_record.auto_components['trap_flags'])
        self.assertIn('herd_chase', week5.score_record.auto_components['trap_flags'])
        self.assertIn('herd_pivot', week5.score_record.auto_components['trap_flags'])
        self.assertTrue(self.run.state['flags']['meridian_chased'])
        self.assertEqual(self.run.state['through_lines']['coherence']['drift_events'][-1]['kind'], 'herd_pivot')

    def test_week5_complacency_when_quiet_threats_ignored(self):
        self._complete_week1_week2_week3_week4()
        week5 = view_briefing(self.run)
        submit_week(
            week5,
            structured_payload=week5_payload({
                'portfolio.additive_manufacturing': 'ignore',
                'portfolio.edge_ai_low_end': 'ignore',
            }),
            deliverable_text='Dismiss the quiet threats.',
            submitted_by=self.user,
        )
        week5.refresh_from_db()
        self.assertIn('complacency', week5.score_record.auto_components['trap_flags'])

    def test_week5_benchmark_changes_briefing_tone_not_evaluation(self):
        module = registry.get(5)
        top_team = Team.objects.create(cohort=self.cohort, name='Top Team')
        bottom_team = Team.objects.create(cohort=self.cohort, name='Bottom Team')
        top_run = Run.objects.create(team=top_team)
        bottom_run = Run.objects.create(team=bottom_team)
        Benchmark.objects.create(
            cohort=self.cohort,
            after_week=4,
            standings=[
                {'team_id': top_team.id, 'team_name': 'Top Team', 'rank': 1, 'benchmark_score': 20, 'total_score': 20},
                {'team_id': self.team.id, 'team_name': 'Team A', 'rank': 2, 'benchmark_score': 10, 'total_score': 10},
                {'team_id': bottom_team.id, 'team_name': 'Bottom Team', 'rank': 3, 'benchmark_score': 2, 'total_score': 2},
            ],
        )

        top_briefing = module.briefing_for_run(Tier.GRADUATE, top_run)
        bottom_briefing = module.briefing_for_run(Tier.GRADUATE, bottom_run)
        self.assertIn('room to breathe', top_briefing.body)
        self.assertIn('visibly behind peers', bottom_briefing.body)
        for fact in ('Meridian Industrial', 'additive manufacturing', 'edge AI'):
            self.assertIn(fact, top_briefing.body)
            self.assertIn(fact, bottom_briefing.body)

        self.assertEqual(module.decision_spec(Tier.GRADUATE), module.decision_spec(Tier.GRADUATE))
        top_auto = module.score_auto(_FakeSubmission(week5_payload()), top_run.state)
        bottom_auto = module.score_auto(_FakeSubmission(week5_payload()), bottom_run.state)
        self.assertEqual(top_auto.normalized_scores(), bottom_auto.normalized_scores())
        self.assertEqual(top_auto.trap_flags, bottom_auto.trap_flags)

    def test_week5_contract_shape(self):
        module = registry.get(5)
        self.assertEqual(module.title, 'The Read')
        self.assertEqual(module.reads_state(), [
            'coherence_anchor',
            'through_lines.coherence',
            'decision_history',
            'benchmarks.latest',
            'through_lines.cloud_lockin',
            'relationships',
        ])
        self.assertIn('portfolio.autonomy', [field.key for field in module.decision_spec(Tier.UNDERGRAD).fields])

    def test_week6_sound_path_writes_scoped_data_rights(self):
        self._complete_week1_week2_week3_week4_week5()
        week6 = view_briefing(self.run)
        submit_week(
            week6,
            structured_payload=week6_payload(),
            deliverable_text='Right-sized platform analysis.',
            submitted_by=self.user,
        )
        week6.refresh_from_db()
        self.run.refresh_from_db()

        self.assertEqual(week6.status, WeekInstanceStatus.SUBMITTED)
        self.assertEqual(week6.score_record.auto_components['scores']['strategic_judgment'], 3)
        self.assertEqual(week6.score_record.auto_components['scores']['execution_consequence'], 2)
        self.assertEqual(self.run.state['through_lines']['data_rights']['posture'], 'scoped')
        self.assertEqual(self.run.state['relationships']['ferraro'], 1)
        self.assertEqual(self.run.state['relationships']['fischer'], 3)
        self.assertEqual(self.run.state['decision_history'][-1]['decision_key'], 'platform_question')

    def test_week6_open_unguarded_sets_data_rights_fuse(self):
        self._complete_week1_week2_week3_week4_week5()
        week6 = view_briefing(self.run)
        submit_week(
            week6,
            structured_payload=week6_payload({'openness': 'open_unguarded'}),
            deliverable_text='Open dealer ecosystem without rights.',
            submitted_by=self.user,
        )
        self.run.refresh_from_db()
        week6.refresh_from_db()

        self.assertIn('openness_landmine', week6.score_record.auto_components['trap_flags'])
        self.assertEqual(self.run.state['through_lines']['data_rights']['posture'], 'open_unresolved')
        self.assertIn('Dealer platform opened in Week 6', self.run.state['through_lines']['data_rights']['notes'][-1])
        self.assertEqual(self.run.state['relationships']['ferraro'], -2)

    def test_week6_grand_platform_on_rented_differentiator_gets_double_coherence_hit(self):
        self._complete_week1_week2_week3()
        week4 = view_briefing(self.run)
        submit_week(
            week4,
            structured_payload=week4_payload({'differentiator_layer': 'rent'}),
            deliverable_text='Rent differentiator.',
            submitted_by=self.user,
        )
        week4.refresh_from_db()
        finalize_score(week4.score_record)
        self.run.refresh_from_db()
        self.run.current_week = 5
        self.run.save()
        week5 = view_briefing(self.run)
        submit_week(week5, structured_payload=week5_payload(), deliverable_text='Read.', submitted_by=self.user)
        self.run.refresh_from_db()
        self.run.current_week = 6
        self.run.save()

        week6 = view_briefing(self.run)
        submit_week(
            week6,
            structured_payload=week6_payload({'platform_decision': 'grand_platform'}),
            deliverable_text='Grand platform.',
            submitted_by=self.user,
        )
        week6.refresh_from_db()
        self.run.refresh_from_db()
        self.assertIn('platform_envy', week6.score_record.auto_components['trap_flags'])
        self.assertIn('platform_on_sand', week6.score_record.auto_components['trap_flags'])
        self.assertEqual(week6.score_record.auto_components['scores']['coherence'], -4)
        self.assertEqual(self.run.state['through_lines']['coherence']['drift_events'][-1]['kind'], 'platform_envy')

    def test_week6_pure_product_over_caution(self):
        self._complete_week1_week2_week3_week4_week5()
        week6 = view_briefing(self.run)
        submit_week(
            week6,
            structured_payload=week6_payload({'platform_decision': 'pure_product'}),
            deliverable_text='Stay product-only.',
            submitted_by=self.user,
        )
        week6.refresh_from_db()
        self.assertIn('over_caution', week6.score_record.auto_components['trap_flags'])

    def test_week6_contract_shape(self):
        module = registry.get(6)
        self.assertEqual(module.title, 'The Platform Question')
        self.assertEqual(module.reads_state(), [
            'coherence_anchor',
            'through_lines.coherence',
            'decision_history',
            'through_lines.cloud_lockin',
            'through_lines.data_rights',
            'relationships',
        ])
        self.assertIn('platform_decision', [field.key for field in module.decision_spec(Tier.GRADUATE).fields])

    def test_week7_sound_path_from_low_lockin_lifecycle(self):
        self._complete_week1_to_week6()
        week7 = view_briefing(self.run)
        submit_week(
            week7,
            structured_payload=week7_payload(),
            deliverable_text='Vendor squeeze response with measured hedge.',
            submitted_by=self.user,
        )
        week7.refresh_from_db()
        self.run.refresh_from_db()

        self.assertEqual(week7.status, WeekInstanceStatus.SUBMITTED)
        self.assertEqual(week7.score_record.auto_components['components']['squeeze_severity'], 1)
        self.assertEqual(week7.score_record.auto_components['scores']['strategic_judgment'], 2)
        self.assertEqual(week7.score_record.auto_components['scores']['execution_consequence'], 5)
        self.assertTrue(self.run.state['flags']['hedge_begun'])
        self.assertEqual(self.run.state['decision_history'][-1]['decision_key'], 'vendor_squeeze')

        finalize_score(week7.score_record, instructor_components={'ot_signal_addressed': True})
        week7.refresh_from_db()
        self.run.refresh_from_db()
        self.assertEqual(week7.status, WeekInstanceStatus.SCORED)
        self.assertEqual(self.run.state['gates']['security_ot']['state'], 'open')
        self.assertIn('OT signal caught and acted on in Week 7', self.run.state['through_lines']['security_ot']['notes'][-1])

    def test_week7_high_lockin_history_produces_severe_pressure(self):
        self._complete_week1_to_week6(
            week3_overrides={'integrator_decision': 'take_accelerator'},
            week4_overrides={'cloud_commitment': 'sweet_deal_as_written'},
        )
        week7 = view_briefing(self.run)
        submit_week(
            week7,
            structured_payload=week7_payload({'vendor_response': 'absorb'}),
            deliverable_text='Absorb and hedge from a trapped position.',
            submitted_by=self.user,
        )
        week7.refresh_from_db()
        self.run.refresh_from_db()

        self.assertEqual(week7.score_record.auto_components['components']['squeeze_severity'], 3)
        self.assertEqual(week7.score_record.auto_components['components']['wk4_cloud_commitment'], 'sweet_deal_as_written')
        self.assertNotIn('passive_absorb', week7.score_record.auto_components['trap_flags'])
        self.assertTrue(self.run.state['flags']['integrator_accelerator_taken'])
        self.assertEqual(self.run.state['through_lines']['cloud_lockin']['state'], 'locked')
        self.assertGreaterEqual(self.run.state['through_lines']['cloud_lockin']['depth'], 3)

    def test_week7_renegotiation_benefit_depends_on_week4_position(self):
        self._complete_week1_to_week6()
        hedged_module = registry.get(7)
        hedged_auto = hedged_module.score_auto(_FakeSubmission(week7_payload()), self.run.state)

        trapped_team = Team.objects.create(cohort=self.cohort, name='Trapped Team')
        trapped_run = Run.objects.create(team=trapped_team)
        self.run = trapped_run
        self._complete_week1_to_week6(week4_overrides={'cloud_commitment': 'sweet_deal_as_written'})
        trapped_auto = hedged_module.score_auto(_FakeSubmission(week7_payload()), self.run.state)

        self.assertGreater(
            hedged_auto.normalized_scores()['execution_consequence'],
            trapped_auto.normalized_scores()['execution_consequence'],
        )
        self.assertEqual(hedged_auto.components['squeeze_severity'], 1)
        self.assertEqual(trapped_auto.components['squeeze_severity'], 3)

    def test_week7_ot_gate_closes_when_prior_posture_and_signal_missing(self):
        self._complete_week1_to_week6(week1_overrides={
            'early_action': 'diagnose_only',
            'ot_black_box_engaged': False,
        })
        week7 = view_briefing(self.run)
        submit_week(
            week7,
            structured_payload=week7_payload({'ot_signal_addressed': False}),
            deliverable_text='Cloud-focused response that misses OT.',
            submitted_by=self.user,
        )
        week7.refresh_from_db()
        finalize_score(week7.score_record, instructor_components={'ot_signal_addressed': False})
        self.run.refresh_from_db()

        self.assertEqual(self.run.state['gates']['security_ot']['state'], 'closed')
        self.assertEqual(self.run.state['gates']['security_ot']['set_week'], 7)

    def test_week7_no_spoiler_student_facing_text(self):
        module = registry.get(7)
        briefing = module.briefing(Tier.UNDERGRAD)
        artifacts = module.artifacts(Tier.UNDERGRAD)
        rendered = ' '.join(
            [briefing.title, briefing.body, *briefing.exec_reads, *briefing.signals]
            + [artifact.title + ' ' + artifact.body for artifact in artifacts]
        ).lower()

        for term in ('week 12', 'future lock-in resolution', 'later payoff', 'endgame cap'):
            self.assertNotIn(term, rendered)

    def test_week7_state_reload_preserves_severity(self):
        self._complete_week1_to_week6(
            week3_overrides={'integrator_decision': 'take_accelerator'},
            week4_overrides={'cloud_commitment': 'sweet_deal_as_written'},
        )
        module = registry.get(7)
        before = module.score_auto(_FakeSubmission(week7_payload()), self.run.state)
        reloaded = Run.objects.get(pk=self.run.pk)
        after = module.score_auto(_FakeSubmission(week7_payload()), reloaded.state)

        self.assertEqual(before.components['squeeze_severity'], after.components['squeeze_severity'])
        self.assertEqual(after.components['squeeze_severity'], 3)

    def test_week7_end_to_end_history_drives_severity_and_continuity(self):
        self._complete_week1_to_week6(
            week3_overrides={'integrator_decision': 'take_accelerator'},
            week4_overrides={'cloud_commitment': 'sweet_deal_as_written'},
        )
        self.assertEqual([entry['week'] for entry in self.run.state['decision_history']], [1, 2, 3, 4, 5, 6])

        week7 = view_briefing(self.run)
        submit_week(
            week7,
            structured_payload=week7_payload({'vendor_response': 'absorb'}),
            deliverable_text='Absorb and hedge with transparent ownership.',
            submitted_by=self.user,
        )
        self.run.refresh_from_db()
        week7.refresh_from_db()

        self.assertEqual(week7.score_record.auto_components['components']['squeeze_severity'], 3)
        self.assertEqual([entry['week'] for entry in self.run.state['decision_history']], [1, 2, 3, 4, 5, 6, 7])
        self.assertEqual(self.run.state['decision_history'][-1]['decision_key'], 'vendor_squeeze')

    def test_week7_contract_shape(self):
        module = registry.get(7)
        self.assertEqual(module.title, 'The Squeeze')
        self.assertEqual(module.reads_state(), [
            'through_lines.cloud_lockin',
            'flags.integrator_accelerator_taken',
            'through_lines.security_ot',
            'gates.security_ot',
            'relationships',
            'coherence_anchor',
            'through_lines.coherence',
            'decision_history',
        ])
        self.assertIn('vendor_response', [field.key for field in module.decision_spec(Tier.GRADUATE).fields])

    def test_week8_sound_path_closes_phase2_and_generates_benchmark(self):
        self._complete_week1_to_week7()
        week8 = view_briefing(self.run)
        submit_week(
            week8,
            structured_payload=week8_payload(),
            deliverable_text='Data strategy keystone memo.',
            submitted_by=self.user,
        )
        week8.refresh_from_db()
        self.run.refresh_from_db()

        self.assertEqual(week8.status, WeekInstanceStatus.SUBMITTED)
        self.assertEqual(week8.score_record.auto_components['scores']['coherence'], 4)
        self.assertEqual(self.run.state['through_lines']['data_rights']['posture'], 'shared_value')
        self.assertTrue(self.run.state['flags']['predictive_built'])
        self.assertEqual(self.run.state['relationships']['ferraro'], 2)
        self.assertEqual(self.run.state['relationships']['tran'], 1)
        self.assertEqual(self.run.state['decision_history'][-1]['decision_key'], 'data_keystone')

        finalize_score(week8.score_record, instructor_scores={'deliverable_quality': 1})
        week8.refresh_from_db()
        benchmark = Benchmark.objects.get(cohort=self.cohort, after_week=8)
        self.assertEqual(week8.status, WeekInstanceStatus.SCORED)
        self.assertIsNone(benchmark.revealed_at)
        self.assertEqual(benchmark.standings[0]['factors'], ['accumulated_score'])

    def test_week8_land_grab_compounds_week6_open_platform(self):
        self._complete_week1_to_week7(week6_overrides={'openness': 'open_unguarded'})
        week8 = view_briefing(self.run)
        submit_week(
            week8,
            structured_payload=week8_payload({'rights_posture': 'land_grab'}),
            deliverable_text='Assert ownership of all machine data.',
            submitted_by=self.user,
        )
        week8.refresh_from_db()
        self.run.refresh_from_db()

        self.assertIn('land_grab', week8.score_record.auto_components['trap_flags'])
        self.assertEqual(self.run.state['through_lines']['data_rights']['posture'], 'contested_aggressive')
        self.assertTrue(self.run.state['flags']['land_grab'])
        self.assertTrue(self.run.state['flags']['predictive_built'])
        self.assertLess(self.run.state['relationships']['ferraro'], 0)
        self.assertEqual(self.run.state['relationships']['tran'], -2)
        self.assertEqual(self.run.state['through_lines']['coherence']['drift_events'][-1]['weight'], 'keystone')

    def test_week8_duck_leaves_no_predictive_advantage(self):
        self._complete_week1_to_week7()
        week8 = view_briefing(self.run)
        submit_week(
            week8,
            structured_payload=week8_payload({
                'rights_posture': 'duck',
                'governance_built': False,
                'analytics_architecture': 'descriptive_only',
            }),
            deliverable_text='Avoid the data-rights fight.',
            submitted_by=self.user,
        )
        week8.refresh_from_db()
        self.run.refresh_from_db()

        self.assertIn('duck', week8.score_record.auto_components['trap_flags'])
        self.assertIn('governance_neglect', week8.score_record.auto_components['trap_flags'])
        self.assertFalse(self.run.state['flags']['predictive_built'])
        self.assertEqual(week8.score_record.auto_components['scores']['coherence'], -3)

    def test_week8_benchmark_accumulated_score_only_omits_gate_and_drift_modifiers(self):
        self._complete_week1_to_week7()
        self.run.state['gates']['budget_credibility']['state'] = 'closed'
        self.run.state['through_lines']['coherence']['drift_events'].append({'week': 8, 'kind': 'test'})
        self.run.save()

        week8 = view_briefing(self.run)
        submit_week(week8, structured_payload=week8_payload(), deliverable_text='Keystone.', submitted_by=self.user)
        week8.refresh_from_db()
        finalize_score(week8.score_record)
        self.run.refresh_from_db()
        benchmark = Benchmark.objects.get(cohort=self.cohort, after_week=8)
        row = benchmark.standings[0]

        self.assertEqual(row['benchmark_score'], row['total_score'])
        self.assertEqual(row['gate_factor'], 1)
        self.assertEqual(row['drift_penalty'], 0)
        self.assertEqual(row['factors'], ['accumulated_score'])

    def test_week8_student_benchmark_excludes_data_rights_fuse_and_future_spoilers(self):
        self._complete_week1_to_week7(week6_overrides={'openness': 'open_unguarded'})
        week8 = view_briefing(self.run)
        submit_week(
            week8,
            structured_payload=week8_payload({'rights_posture': 'land_grab'}),
            deliverable_text='Aggressive data ownership.',
            submitted_by=self.user,
        )
        week8.refresh_from_db()
        finalize_score(week8.score_record)
        self.run.refresh_from_db()
        benchmark = Benchmark.objects.get(cohort=self.cohort, after_week=8)
        payload = student_benchmark_payload(benchmark)
        rendered_payload = str(payload).lower()

        self.assertEqual(self.run.state['through_lines']['data_rights']['posture'], 'contested_aggressive')
        for term in (
            'data_rights',
            'contested_aggressive',
            'land_grab',
            'week 11',
            'future warning',
            'revolt',
            'fuse',
        ):
            self.assertNotIn(term, rendered_payload)

    def test_week8_end_to_end_weeks1_to_8_continuity(self):
        self._complete_week1_to_week7(
            week3_overrides={'integrator_decision': 'take_accelerator'},
            week4_overrides={'cloud_commitment': 'sweet_deal_as_written'},
            week6_overrides={'openness': 'open_unguarded'},
        )
        self.assertEqual([entry['week'] for entry in self.run.state['decision_history']], [1, 2, 3, 4, 5, 6, 7])

        week8 = view_briefing(self.run)
        submit_week(
            week8,
            structured_payload=week8_payload({'rights_posture': 'land_grab'}),
            deliverable_text='Week 8 keystone.',
            submitted_by=self.user,
        )
        week8.refresh_from_db()
        finalize_score(week8.score_record)
        self.run.refresh_from_db()

        self.assertEqual([entry['week'] for entry in self.run.state['decision_history']], [1, 2, 3, 4, 5, 6, 7, 8])
        self.assertEqual(self.run.state['decision_history'][-1]['decision_key'], 'data_keystone')
        self.assertEqual(self.run.state['through_lines']['data_rights']['posture'], 'contested_aggressive')
        self.assertTrue(Benchmark.objects.filter(cohort=self.cohort, after_week=8).exists())

    def test_week8_dramatic_irony_same_visible_benchmark_different_internal_risk(self):
        risky_team = Team.objects.create(cohort=self.cohort, name='Risky Team')
        safe_team = Team.objects.create(cohort=self.cohort, name='Safe Team')
        risky_run = Run.objects.create(team=risky_team)
        safe_run = Run.objects.create(team=safe_team)

        self.run = risky_run
        self._complete_week1_to_week7(week6_overrides={'openness': 'open_unguarded'})
        risky_week8 = view_briefing(self.run)
        submit_week(
            risky_week8,
            structured_payload=week8_payload({'rights_posture': 'land_grab'}),
            deliverable_text='Aggressive data ownership.',
            submitted_by=self.user,
        )
        risky_week8.refresh_from_db()
        finalize_score(risky_week8.score_record)
        risky_run.refresh_from_db()

        self.run = safe_run
        self._complete_week1_to_week7()
        safe_week8 = view_briefing(self.run)
        submit_week(safe_week8, structured_payload=week8_payload(), deliverable_text='Shared value.', submitted_by=self.user)
        safe_week8.refresh_from_db()
        finalize_score(safe_week8.score_record)
        safe_run.refresh_from_db()

        benchmark = Benchmark.objects.get(cohort=self.cohort, after_week=8)
        rows = {row['team_name']: row for row in benchmark.standings}
        self.assertEqual(rows['Risky Team']['benchmark_score'], rows['Risky Team']['total_score'])
        self.assertEqual(rows['Safe Team']['benchmark_score'], rows['Safe Team']['total_score'])
        self.assertEqual(risky_run.state['through_lines']['data_rights']['posture'], 'contested_aggressive')
        self.assertEqual(safe_run.state['through_lines']['data_rights']['posture'], 'shared_value')
        self.assertNotIn('data_rights', str(student_benchmark_payload(benchmark)).lower())

    def test_week8_contract_shape(self):
        module = registry.get(8)
        self.assertEqual(module.title, 'The Keystone')
        self.assertEqual(module.reads_state(), [
            'coherence_anchor',
            'through_lines.coherence',
            'decision_history',
            'through_lines.data_rights',
            'through_lines.cloud_lockin',
            'gates.security_ot',
            'gates.budget_credibility',
            'relationships',
        ])
        self.assertIn('rights_posture', [field.key for field in module.decision_spec(Tier.GRADUATE).fields])

    def test_week9_sound_path_uses_predictive_foundation_and_governs_shadow_ai(self):
        self._complete_week1_to_week8()
        prior_reinhardt = self.run.state['relationships']['reinhardt']
        prior_fischer = self.run.state['relationships']['fischer']
        prior_tran = self.run.state['relationships']['tran']
        week9 = view_briefing(self.run)
        submit_week(
            week9,
            structured_payload=week9_payload(),
            deliverable_text='AI bet focused on predictive maintenance.',
            submitted_by=self.user,
        )
        week9.refresh_from_db()
        self.run.refresh_from_db()

        self.assertEqual(week9.status, WeekInstanceStatus.SUBMITTED)
        self.assertEqual(week9.score_record.auto_components['scores']['strategic_judgment'], 3)
        self.assertEqual(week9.score_record.auto_components['scores']['execution_consequence'], 2)
        self.assertEqual(week9.score_record.auto_components['scores']['coherence'], 2)
        self.assertTrue(self.run.state['flags']['shadow_ai_governed'])
        self.assertFalse(self.run.state['flags'].get('shadow_ai_incident_open', False))
        self.assertEqual(self.run.state['relationships']['reinhardt'], prior_reinhardt + 1)
        self.assertEqual(self.run.state['relationships']['fischer'], prior_fischer + 1)
        self.assertEqual(self.run.state['relationships']['tran'], prior_tran + 1)
        self.assertEqual(self.run.state['decision_history'][-1]['decision_key'], 'ai_bet')

    def test_week9_release_valve_rewards_board_aligned_substance_not_theater(self):
        self._complete_week1_to_week8()
        module = registry.get(9)
        briefing = module.briefing(Tier.UNDERGRAD)
        substance = module.score_auto(_FakeSubmission(week9_payload()), self.run.state)
        theater = module.score_auto(_FakeSubmission(week9_payload({'deployment': 'theater_scatter'})), self.run.state)

        self.assertIn('board is right', briefing.signals[0])
        self.assertGreater(substance.normalized_scores()['strategic_judgment'], 0)
        self.assertGreater(substance.normalized_scores()['coherence'], 0)
        self.assertIn('ai_theater', theater.trap_flags)
        self.assertLess(theater.normalized_scores()['strategic_judgment'], 0)
        self.assertLess(theater.normalized_scores()['coherence'], 0)

    def test_week9_predictive_choice_without_week8_foundation_is_right_but_weak(self):
        self._complete_week1_to_week7()
        week8 = view_briefing(self.run)
        submit_week(
            week8,
            structured_payload=week8_payload({
                'rights_posture': 'duck',
                'governance_built': False,
                'analytics_architecture': 'descriptive_only',
            }),
            deliverable_text='Hollow data strategy.',
            submitted_by=self.user,
        )
        week8.refresh_from_db()
        finalize_score(week8.score_record)
        self.run.refresh_from_db()
        self.run.current_week = 9
        self.run.save()

        week9 = view_briefing(self.run)
        submit_week(
            week9,
            structured_payload=week9_payload(),
            deliverable_text='Correct AI instinct without foundation.',
            submitted_by=self.user,
        )
        week9.refresh_from_db()
        self.run.refresh_from_db()

        self.assertFalse(self.run.state['flags']['predictive_built'])
        self.assertIn('no_foundation', week9.score_record.auto_components['trap_flags'])
        self.assertNotIn('ai_theater', week9.score_record.auto_components['trap_flags'])
        self.assertEqual(week9.score_record.auto_components['scores']['strategic_judgment'], 1)
        self.assertEqual(week9.score_record.auto_components['scores']['coherence'], 0)

    def test_week9_single_hyperscaler_deepens_cloud_lockin(self):
        self._complete_week1_to_week8()
        prior_depth = self.run.state['through_lines']['cloud_lockin']['depth']
        week9 = view_briefing(self.run)
        submit_week(
            week9,
            structured_payload=week9_payload({'vendor_concentration': 'single_hyperscaler'}),
            deliverable_text='Concentrate AI with the same hyperscaler.',
            submitted_by=self.user,
        )
        week9.refresh_from_db()
        self.run.refresh_from_db()

        self.assertIn('lockin_unlearned', week9.score_record.auto_components['trap_flags'])
        self.assertEqual(self.run.state['through_lines']['cloud_lockin']['depth'], prior_depth + 1)
        self.assertIn('AI concentrated on the same hyperscaler in Week 9', self.run.state['through_lines']['cloud_lockin']['notes'][-1])

    def test_week9_ungoverned_shadow_ai_opens_incident(self):
        self._complete_week1_to_week8()
        week9 = view_briefing(self.run)
        submit_week(
            week9,
            structured_payload=week9_payload({'shadow_ai_response': 'ungoverned'}),
            deliverable_text='AI strategy without shadow-AI governance.',
            submitted_by=self.user,
        )
        week9.refresh_from_db()
        self.run.refresh_from_db()

        self.assertIn('ungoverned_shadow_ai', week9.score_record.auto_components['trap_flags'])
        self.assertTrue(self.run.state['flags']['shadow_ai_incident_open'])
        self.assertFalse(self.run.state['flags'].get('shadow_ai_governed', False))
        self.assertEqual(self.run.state['through_lines']['coherence']['drift_events'][-1]['kind'], 'shadow_ai_ungoverned')

    def test_week9_end_to_end_weeks1_to_9_continuity(self):
        self._complete_week1_to_week8(
            week3_overrides={'integrator_decision': 'take_accelerator'},
            week4_overrides={'cloud_commitment': 'sweet_deal_as_written'},
            week6_overrides={'openness': 'open_unguarded'},
            week8_overrides={'rights_posture': 'land_grab'},
        )
        self.assertEqual([entry['week'] for entry in self.run.state['decision_history']], [1, 2, 3, 4, 5, 6, 7, 8])

        week9 = view_briefing(self.run)
        submit_week(
            week9,
            structured_payload=week9_payload({'vendor_concentration': 'single_hyperscaler'}),
            deliverable_text='Week 9 AI bet.',
            submitted_by=self.user,
        )
        week9.refresh_from_db()
        self.run.refresh_from_db()

        self.assertEqual([entry['week'] for entry in self.run.state['decision_history']], [1, 2, 3, 4, 5, 6, 7, 8, 9])
        self.assertEqual(self.run.state['decision_history'][-1]['decision_key'], 'ai_bet')
        self.assertEqual(self.run.state['through_lines']['data_rights']['posture'], 'contested_aggressive')
        self.assertTrue(self.run.state['flags']['shadow_ai_governed'])
        self.assertGreaterEqual(self.run.state['through_lines']['cloud_lockin']['depth'], 4)

    def test_week9_contract_shape(self):
        module = registry.get(9)
        self.assertEqual(module.title, 'The Bet')
        self.assertEqual(module.reads_state(), [
            'coherence_anchor',
            'through_lines.coherence',
            'decision_history',
            'flags.predictive_built',
            'flags.governance_built',
            'through_lines.cloud_lockin',
            'gates.security_ot',
            'gates.budget_credibility',
            'relationships',
        ])
        self.assertIn('deployment', [field.key for field in module.decision_spec(Tier.GRADUATE).fields])

    def test_week10_open_gate_contains_breach_and_keeps_gate_open(self):
        self._complete_week1_to_week9()
        prior_petrillo = self.run.state['relationships']['petrillo']
        prior_tran = self.run.state['relationships']['tran']
        week10 = view_briefing(self.run)
        submit_week(
            week10,
            structured_payload=week10_payload(),
            deliverable_text='Parallel incident response with transparent disclosure.',
            submitted_by=self.user,
        )
        week10.refresh_from_db()
        self.run.refresh_from_db()

        self.assertEqual(week10.status, WeekInstanceStatus.SUBMITTED)
        self.assertEqual(week10.score_record.auto_components['components']['breach_severity'], 1)
        self.assertEqual(week10.score_record.auto_components['components']['inherited_condition'], 'containable')
        self.assertTrue(week10.score_record.auto_components['components']['containment_available'])
        self.assertEqual(week10.score_record.auto_components['scores']['execution_consequence'], 6)
        self.assertEqual(self.run.state['gates']['security_ot']['state'], 'open')
        self.assertFalse(self.run.state['gates']['security_ot']['detonated'])
        self.assertTrue(self.run.state['flags']['breach_contained'])
        self.assertFalse(self.run.state['flags']['breach_catastrophic'])
        self.assertEqual(self.run.state['flags']['fleet_impact'], 'limited')
        self.assertEqual(self.run.state['relationships']['petrillo'], prior_petrillo + 1)
        self.assertEqual(self.run.state['relationships']['tran'], prior_tran + 1)

    def test_week10_closed_gate_inherits_catastrophic_condition_with_same_response(self):
        self._complete_week1_to_week9(
            week1_overrides={'early_action': 'diagnose_only', 'ot_black_box_engaged': False},
            week7_overrides={'ot_signal_addressed': False},
            week7_instructor_signal=False,
        )
        self.assertEqual(self.run.state['gates']['security_ot']['state'], 'closed')

        week10 = view_briefing(self.run)
        submit_week(
            week10,
            structured_payload=week10_payload(),
            deliverable_text='Strong response from a bad inherited position.',
            submitted_by=self.user,
        )
        week10.refresh_from_db()
        self.run.refresh_from_db()

        self.assertEqual(week10.score_record.auto_components['components']['breach_severity'], 4)
        self.assertEqual(week10.score_record.auto_components['components']['inherited_condition'], 'catastrophic_blind')
        self.assertFalse(week10.score_record.auto_components['components']['containment_available'])
        self.assertIn('containment_overclaimed', week10.score_record.auto_components['trap_flags'])
        self.assertEqual(week10.score_record.auto_components['scores']['execution_consequence'], 4)
        self.assertEqual(self.run.state['gates']['security_ot']['state'], 'detonated')
        self.assertTrue(self.run.state['gates']['security_ot']['detonated'])
        self.assertTrue(self.run.state['flags']['breach_catastrophic'])
        self.assertEqual(self.run.state['flags']['fleet_impact'], 'severe')

    def test_week10_prior_ot_posture_changes_inherited_visibility(self):
        self._complete_week1_to_week9(
            week1_overrides={'early_action': 'diagnose_only', 'ot_black_box_engaged': False},
            week7_overrides={'ot_signal_addressed': False},
            week7_instructor_signal=False,
        )
        weak_module = registry.get(10)
        weak_auto = weak_module.score_auto(_FakeSubmission(week10_payload()), self.run.state)

        prepared_run = Run.objects.create(team=Team.objects.create(cohort=self.cohort, name='Prepared Team'))
        self.run = prepared_run
        self._complete_week1_to_week9()
        prepared_auto = weak_module.score_auto(_FakeSubmission(week10_payload()), self.run.state)

        self.assertGreater(
            weak_auto.components['breach_severity'],
            prepared_auto.components['breach_severity'],
        )
        self.assertFalse(weak_auto.components['containment_available'])
        self.assertTrue(prepared_auto.components['containment_available'])

    def test_week10_shadow_ai_open_compounds_breach_severity(self):
        self._complete_week1_to_week9(week9_overrides={'shadow_ai_response': 'ungoverned'})
        week10 = view_briefing(self.run)
        submit_week(
            week10,
            structured_payload=week10_payload(),
            deliverable_text='Incident response after shadow-AI exposure.',
            submitted_by=self.user,
        )
        week10.refresh_from_db()
        self.run.refresh_from_db()

        self.assertTrue(self.run.state['flags']['shadow_ai_incident_open'])
        self.assertEqual(week10.score_record.auto_components['components']['breach_severity'], 2)
        self.assertEqual(week10.score_record.auto_components['components']['inherited_condition'], 'serious_mappable')

    def test_week10_state_reload_preserves_breach_severity(self):
        self._complete_week1_to_week9(
            week1_overrides={'early_action': 'diagnose_only', 'ot_black_box_engaged': False},
            week7_overrides={'ot_signal_addressed': False},
            week7_instructor_signal=False,
            week9_overrides={'shadow_ai_response': 'ungoverned'},
        )
        module = registry.get(10)
        before = module.score_auto(_FakeSubmission(week10_payload()), self.run.state)
        reloaded = Run.objects.get(pk=self.run.pk)
        after = module.score_auto(_FakeSubmission(week10_payload()), reloaded.state)

        self.assertEqual(before.components['breach_severity'], after.components['breach_severity'])
        self.assertEqual(after.components['breach_severity'], 4)

    def test_week10_linear_or_spin_response_scores_response_not_gate(self):
        self._complete_week1_to_week9()
        week10 = view_briefing(self.run)
        submit_week(
            week10,
            structured_payload=week10_payload({
                'disclosure': 'spin_or_hide',
                'triage_approach': 'linear',
            }),
            deliverable_text='Sequential response and message control.',
            submitted_by=self.user,
        )
        week10.refresh_from_db()
        self.run.refresh_from_db()

        self.assertIn('linear_triage', week10.score_record.auto_components['trap_flags'])
        self.assertIn('spin', week10.score_record.auto_components['trap_flags'])
        self.assertEqual(week10.score_record.auto_components['scores']['coherence'], -2)
        self.assertEqual(self.run.state['through_lines']['coherence']['drift_events'][-1]['kind'], 'panicked_response')

    def test_week10_end_to_end_weeks1_to_10_continuity(self):
        self._complete_week1_to_week9(
            week3_overrides={'integrator_decision': 'take_accelerator'},
            week4_overrides={'cloud_commitment': 'sweet_deal_as_written'},
            week6_overrides={'openness': 'open_unguarded'},
            week8_overrides={'rights_posture': 'land_grab'},
            week9_overrides={'vendor_concentration': 'single_hyperscaler'},
        )
        self.assertEqual([entry['week'] for entry in self.run.state['decision_history']], [1, 2, 3, 4, 5, 6, 7, 8, 9])

        week10 = view_briefing(self.run)
        submit_week(
            week10,
            structured_payload=week10_payload(),
            deliverable_text='Week 10 breach response.',
            submitted_by=self.user,
        )
        week10.refresh_from_db()
        self.run.refresh_from_db()

        self.assertEqual([entry['week'] for entry in self.run.state['decision_history']], [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        self.assertEqual(self.run.state['decision_history'][-1]['decision_key'], 'the_breach')
        self.assertEqual(self.run.state['decision_history'][-1]['ransom_decision'], 'refuse')
        self.assertIn('Fleet compromise in Week 10', self.run.state['through_lines']['data_rights']['notes'][-1])

    def test_week10_contract_shape(self):
        module = registry.get(10)
        self.assertEqual(module.title, 'The Breach')
        self.assertEqual(module.reads_state(), [
            'gates.security_ot',
            'through_lines.security_ot',
            'relationships',
            'flags.shadow_ai_incident_open',
            'through_lines.data_rights',
            'coherence_anchor',
            'through_lines.coherence',
            'gates.budget_credibility',
            'decision_history',
        ])
        self.assertIn('ransom_decision', [field.key for field in module.decision_spec(Tier.GRADUATE).fields])

    def test_week11_shared_value_extends_prior_position_and_repairs_trust(self):
        self._complete_week1_to_week10()
        prior_ferraro = self.run.state['relationships']['ferraro']
        week11 = view_briefing(self.run)
        submit_week(
            week11,
            structured_payload=week11_payload(),
            deliverable_text='Shared-value trust repair.',
            submitted_by=self.user,
        )
        week11.refresh_from_db()
        self.run.refresh_from_db()

        self.assertEqual(week11.status, WeekInstanceStatus.SUBMITTED)
        self.assertEqual(week11.score_record.auto_components['components']['wk8_rights_posture'], 'shared_value')
        self.assertEqual(week11.score_record.auto_components['components']['convergence_severity'], 1)
        self.assertNotIn('late_pivot', week11.score_record.auto_components['trap_flags'])
        self.assertEqual(week11.score_record.auto_components['scores']['strategic_judgment'], 4)
        self.assertEqual(week11.score_record.auto_components['scores']['coherence'], 2)
        self.assertEqual(self.run.state['flags']['data_advantage'], 'preserved')
        self.assertEqual(self.run.state['flags']['trust_state'], 'repaired')
        self.assertEqual(self.run.state['relationships']['ferraro'], prior_ferraro + 1)
        self.assertEqual(self.run.state['decision_history'][-1]['decision_key'], 'trust_reckoning')

        finalize_score(week11.score_record)
        benchmark = Benchmark.objects.get(cohort=self.cohort, after_week=11)
        self.assertEqual(benchmark.standings[0]['factors'], ['accumulated_score', 'trust'])

    def test_week11_same_resolution_after_land_grab_scores_as_late_pivot(self):
        self._complete_week1_to_week10(
            week6_overrides={'openness': 'open_unguarded'},
            week8_overrides={'rights_posture': 'land_grab'},
            week9_overrides={'shadow_ai_response': 'ungoverned'},
        )
        week11 = view_briefing(self.run)
        submit_week(
            week11,
            structured_payload=week11_payload(),
            deliverable_text='Late shared-value pivot.',
            submitted_by=self.user,
        )
        week11.refresh_from_db()
        self.run.refresh_from_db()

        self.assertEqual(week11.score_record.auto_components['components']['wk8_rights_posture'], 'land_grab')
        self.assertEqual(week11.score_record.auto_components['components']['convergence_severity'], 4)
        self.assertIn('late_pivot', week11.score_record.auto_components['trap_flags'])
        self.assertEqual(week11.score_record.auto_components['scores']['strategic_judgment'], 2)
        self.assertEqual(week11.score_record.auto_components['components']['repair_ceiling'], 'damaged')
        self.assertEqual(self.run.state['flags']['data_advantage'], 'preserved')
        self.assertEqual(self.run.state['flags']['trust_state'], 'partially_repaired')

    def test_week11_hold_firm_and_concede_resolve_advantage_differently(self):
        self._complete_week1_to_week10()
        week11 = view_briefing(self.run)
        submit_week(
            week11,
            structured_payload=week11_payload({'rights_resolution': 'hold_firm'}),
            deliverable_text='Hold firm.',
            submitted_by=self.user,
        )
        self.run.refresh_from_db()
        week11.refresh_from_db()

        self.assertIn('hold_firm', week11.score_record.auto_components['trap_flags'])
        self.assertEqual(self.run.state['flags']['data_advantage'], 'won_but_hollow')
        self.assertEqual(self.run.state['flags']['trust_state'], 'damaged')
        self.assertEqual(self.run.state['through_lines']['coherence']['drift_events'][-1]['weight'], 'convergence')

    def test_week11_trace_regenerates_exactly_after_reload(self):
        self._complete_week1_to_week10(
            week3_overrides={'integrator_decision': 'take_accelerator'},
            week4_overrides={'cloud_commitment': 'sweet_deal_as_written'},
            week6_overrides={'openness': 'open_unguarded'},
            week8_overrides={'rights_posture': 'land_grab'},
            week9_overrides={'shadow_ai_response': 'ungoverned'},
        )
        from engine.derivations import derive_data_rights_trace

        trace_before = derive_data_rights_trace(self.run.state)
        reloaded = Run.objects.get(pk=self.run.pk)
        trace_after = derive_data_rights_trace(reloaded.state)

        self.assertEqual(trace_before, trace_after)
        self.assertEqual(trace_after['inputs']['week6_openness'], 'open_unguarded')
        self.assertEqual(trace_after['inputs']['week8_rights_posture'], 'land_grab')
        self.assertEqual(trace_after['inputs']['through_lines.data_rights.posture'], 'contested_aggressive')
        self.assertEqual(trace_after['derived']['convergence_severity'], 4)

    def test_week11_student_facing_content_excludes_internal_trace_terms(self):
        module = registry.get(11)
        briefing = module.briefing(Tier.UNDERGRAD)
        artifacts = module.artifacts(Tier.UNDERGRAD)
        rendered = ' '.join(
            [briefing.title, briefing.body, *briefing.exec_reads, *briefing.signals]
            + [artifact.title + ' ' + artifact.body for artifact in artifacts]
        ).lower()

        for term in ('derive_data_rights_trace', 'convergence_severity', 'repair_ceiling', 'canonical state'):
            self.assertNotIn(term, rendered)

    def test_week11_end_to_end_weeks1_to_11_continuity_and_benchmark(self):
        self._complete_week1_to_week10(
            week3_overrides={'integrator_decision': 'take_accelerator'},
            week4_overrides={'cloud_commitment': 'sweet_deal_as_written'},
            week6_overrides={'openness': 'open_unguarded'},
            week8_overrides={'rights_posture': 'land_grab'},
            week9_overrides={'vendor_concentration': 'single_hyperscaler'},
        )
        self.assertEqual([entry['week'] for entry in self.run.state['decision_history']], [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])

        week11 = view_briefing(self.run)
        submit_week(
            week11,
            structured_payload=week11_payload(),
            deliverable_text='Week 11 convergence resolution.',
            submitted_by=self.user,
        )
        week11.refresh_from_db()
        finalize_score(week11.score_record)
        self.run.refresh_from_db()

        self.assertEqual([entry['week'] for entry in self.run.state['decision_history']], [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11])
        self.assertEqual(self.run.state['decision_history'][-1]['decision_key'], 'trust_reckoning')
        self.assertTrue(Benchmark.objects.filter(cohort=self.cohort, after_week=11).exists())

    def test_week11_contract_shape(self):
        module = registry.get(11)
        self.assertEqual(module.title, 'The Reckoning of Trust')
        self.assertEqual(module.reads_state(), [
            'through_lines.data_rights',
            'flags.fleet_impact',
            'relationships',
            'coherence_anchor',
            'through_lines.coherence',
            'decision_history',
            'gates.budget_credibility',
        ])
        self.assertIn('rights_resolution', [field.key for field in module.decision_spec(Tier.GRADUATE).fields])

    def test_week12_sound_path_breaks_cost_curve_and_sustains_infra(self):
        self._complete_week1_to_week11()
        prior_reinhardt = self.run.state['relationships']['reinhardt']
        week12 = view_briefing(self.run)
        submit_week(
            week12,
            structured_payload=week12_payload(),
            deliverable_text='Edge and repatriation infrastructure plan.',
            submitted_by=self.user,
        )
        week12.refresh_from_db()
        self.run.refresh_from_db()

        self.assertEqual(week12.status, WeekInstanceStatus.SUBMITTED)
        self.assertEqual(week12.score_record.auto_components['scores']['strategic_judgment'], 3)
        self.assertEqual(week12.score_record.auto_components['scores']['execution_consequence'], 5)
        self.assertEqual(week12.score_record.auto_components['scores']['coherence'], 2)
        self.assertTrue(self.run.state['flags']['infra_sustainable'])
        self.assertEqual(self.run.state['through_lines']['cloud_lockin']['state'], 'broken')
        self.assertEqual(self.run.state['relationships']['reinhardt'], prior_reinhardt + 1)
        self.assertEqual(self.run.state['decision_history'][-1]['decision_key'], 'cost_reckoning')

    def test_week12_learning_dimension_after_week4_sweet_deal(self):
        self._complete_week1_to_week11(week4_overrides={'cloud_commitment': 'sweet_deal_as_written'})
        week12 = view_briefing(self.run)
        submit_week(
            week12,
            structured_payload=week12_payload(),
            deliverable_text='Learned lock-in lesson.',
            submitted_by=self.user,
        )
        week12.refresh_from_db()
        self.run.refresh_from_db()

        self.assertIn('learned', week12.score_record.auto_components['trap_flags'])
        self.assertEqual(self.run.state['flags']['lockin_lesson'], 'learned')
        self.assertEqual(week12.score_record.auto_components['components']['wk4_took_sweet_deal'], True)

    def test_week12_committed_spend_after_week4_sweet_deal_not_learned(self):
        self._complete_week1_to_week11(week4_overrides={'cloud_commitment': 'sweet_deal_as_written'})
        prior_depth = self.run.state['through_lines']['cloud_lockin']['depth']
        week12 = view_briefing(self.run)
        submit_week(
            week12,
            structured_payload=week12_payload({
                'architecture': 'minimal_change',
                'hyperscaler_decision': 'committed_spend_discount',
            }),
            deliverable_text='Take the committed-spend discount.',
            submitted_by=self.user,
        )
        week12.refresh_from_db()
        self.run.refresh_from_db()

        self.assertIn('committed_spend_retrap', week12.score_record.auto_components['trap_flags'])
        self.assertIn('did_not_learn', week12.score_record.auto_components['trap_flags'])
        self.assertEqual(self.run.state['flags']['lockin_lesson'], 'not_learned')
        self.assertEqual(self.run.state['through_lines']['cloud_lockin']['depth'], prior_depth + 2)
        self.assertFalse(self.run.state['flags']['infra_sustainable'])
        self.assertEqual(week12.score_record.auto_components['scores']['coherence'], -4)

    def test_week12_renegotiation_leverage_depends_on_week7_hedge(self):
        self._complete_week1_to_week11()
        module = registry.get(12)
        hedged_auto = module.score_auto(_FakeSubmission(week12_payload()), self.run.state)

        unhedged_team = Team.objects.create(cohort=self.cohort, name='Unhedged Team')
        self.run = Run.objects.create(team=unhedged_team)
        self._complete_week1_to_week11(week7_overrides={'hedge_plan': False})
        unhedged_auto = module.score_auto(_FakeSubmission(week12_payload()), self.run.state)

        self.assertGreater(
            hedged_auto.normalized_scores()['execution_consequence'],
            unhedged_auto.normalized_scores()['execution_consequence'],
        )
        self.assertTrue(hedged_auto.components['hedge_begun'])
        self.assertFalse(unhedged_auto.components['hedge_begun'])

    def test_week12_data_gravity_centralize_stays_trapped(self):
        self._complete_week1_to_week11()
        week12 = view_briefing(self.run)
        submit_week(
            week12,
            structured_payload=week12_payload({'architecture': 'centralize'}),
            deliverable_text='Centralized cost response.',
            submitted_by=self.user,
        )
        week12.refresh_from_db()
        self.run.refresh_from_db()

        self.assertIn('data_gravity', week12.score_record.auto_components['trap_flags'])
        self.assertEqual(self.run.state['through_lines']['coherence']['drift_events'][-1]['kind'], 'lockin_unbroken')
        self.assertFalse(self.run.state['flags']['infra_sustainable'])

    def test_week12_end_to_end_weeks1_to_12_continuity(self):
        self._complete_week1_to_week11(
            week3_overrides={'integrator_decision': 'take_accelerator'},
            week4_overrides={'cloud_commitment': 'sweet_deal_as_written'},
            week6_overrides={'openness': 'open_unguarded'},
            week8_overrides={'rights_posture': 'land_grab'},
            week9_overrides={'vendor_concentration': 'single_hyperscaler'},
        )
        self.assertEqual([entry['week'] for entry in self.run.state['decision_history']], [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11])

        week12 = view_briefing(self.run)
        submit_week(
            week12,
            structured_payload=week12_payload(),
            deliverable_text='Week 12 cost reckoning.',
            submitted_by=self.user,
        )
        week12.refresh_from_db()
        self.run.refresh_from_db()

        self.assertEqual([entry['week'] for entry in self.run.state['decision_history']], [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])
        self.assertEqual(self.run.state['decision_history'][-1]['decision_key'], 'cost_reckoning')
        self.assertEqual(self.run.state['flags']['lockin_lesson'], 'learned')

    def test_week12_contract_shape(self):
        module = registry.get(12)
        self.assertEqual(module.title, 'The Reckoning of Cost')
        self.assertEqual(module.reads_state(), [
            'through_lines.cloud_lockin',
            'flags.hedge_begun',
            'decision_history',
            'relationships',
            'coherence_anchor',
            'through_lines.coherence',
            'gates.budget_credibility',
        ])
        self.assertIn('architecture', [field.key for field in module.decision_spec(Tier.GRADUATE).fields])

    def test_week13_supportive_board_and_clean_deck_grants(self):
        self._complete_week1_to_week12()
        self.run.state['through_lines']['coherence']['anchor_strength'] = 'strong'
        self.run.save()
        week13 = view_briefing(self.run)
        submit_week(
            week13,
            structured_payload=week13_payload(),
            deliverable_text='Board-grade transformation deck.',
            submitted_by=self.user,
        )
        week13.refresh_from_db()
        self.run.refresh_from_db()

        self.assertEqual(week13.status, WeekInstanceStatus.SUBMITTED)
        self.assertEqual(week13.score_record.auto_components['components']['board_receptiveness'], 'supportive')
        self.assertEqual(self.run.state['flags']['board_verdict'], 'granted')
        self.assertIn(self.run.state['flags']['arc_coherence_settled'], ('strong', 'adequate'))
        self.assertEqual(self.run.state['decision_history'][-1]['decision_key'], 'the_audit')

    def test_week13_supportive_board_but_weak_deck_denies(self):
        self._complete_week1_to_week12()
        self.run.state['through_lines']['coherence']['anchor_strength'] = 'strong'
        self.run.save()
        week13 = view_briefing(self.run)
        submit_week(
            week13,
            structured_payload=week13_payload({'ask_sizing': 'too_big'}),
            deliverable_text='Overreaching board ask.',
            submitted_by=self.user,
        )
        week13.refresh_from_db()
        self.run.refresh_from_db()

        self.assertEqual(week13.score_record.auto_components['components']['board_receptiveness'], 'supportive')
        self.assertIn('mis_sized_ask', week13.score_record.auto_components['trap_flags'])
        self.assertEqual(self.run.state['flags']['board_verdict'], 'denied')

    def test_week13_skeptical_board_and_clean_deck_denies_from_record(self):
        self._complete_week1_to_week12()
        self.run.state['through_lines']['coherence']['anchor_strength'] = 'strong'
        self.run.state['relationships'] = {key: 0 for key in self.run.state['relationships']}
        self.run.state['accumulated_scores']['execution_consequence'] = 3
        self.run.state['flags']['trust_state'] = 'partially_repaired'
        self.run.state['flags']['data_advantage'] = 'preserved'
        self.run.state['flags']['infra_sustainable'] = False
        self.run.save()

        week13 = view_briefing(self.run)
        submit_week(
            week13,
            structured_payload=week13_payload(),
            deliverable_text='Strong deck into a skeptical room.',
            submitted_by=self.user,
        )
        week13.refresh_from_db()
        self.run.refresh_from_db()

        self.assertEqual(week13.score_record.auto_components['components']['board_receptiveness'], 'skeptical')
        self.assertNotIn('mis_sized_ask', week13.score_record.auto_components['trap_flags'])
        self.assertEqual(self.run.state['flags']['board_verdict'], 'denied')

    def test_week13_hostile_board_loses_confidence_even_with_competent_deck(self):
        self._complete_week1_to_week12(
            week1_overrides={'early_action': 'diagnose_only', 'ot_black_box_engaged': False},
            week7_overrides={'ot_signal_addressed': False},
            week7_instructor_signal=False,
            week8_overrides={'rights_posture': 'land_grab'},
            week9_overrides={'shadow_ai_response': 'ungoverned'},
            week12_overrides={'architecture': 'minimal_change', 'hyperscaler_decision': 'committed_spend_discount'},
        )
        self.run.state['through_lines']['coherence']['anchor_strength'] = 'strong'
        self.run.state['relationships'] = {key: -2 for key in self.run.state['relationships']}
        self.run.state['accumulated_scores']['execution_consequence'] = 0
        self.run.state['flags']['trust_state'] = 'damaged'
        self.run.state['flags']['data_advantage'] = 'won_but_hollow'
        self.run.state['flags']['infra_sustainable'] = False
        self.run.state['flags']['lockin_lesson'] = 'not_learned'
        self.run.save()
        week13 = view_briefing(self.run)
        submit_week(
            week13,
            structured_payload=week13_payload(),
            deliverable_text='Competent deck, no remaining confidence.',
            submitted_by=self.user,
        )
        week13.refresh_from_db()
        self.run.refresh_from_db()

        self.assertEqual(week13.score_record.auto_components['components']['board_receptiveness'], 'hostile')
        self.assertEqual(self.run.state['flags']['board_verdict'], 'confidence_lost')

    def test_week13_incoherent_arc_cannot_claim_coherence(self):
        self._complete_week1_to_week12(week8_overrides={'rights_posture': 'concede'})
        self.run.state['through_lines']['coherence']['drift_events'].extend([
            {'week': 13, 'kind': 'extra_drift', 'weight': 'heavy'},
            {'week': 13, 'kind': 'extra_drift', 'weight': 'heavy'},
        ])
        self.run.save()
        week13 = view_briefing(self.run)
        submit_week(
            week13,
            structured_payload=week13_payload({'narrative_coherence': 'coherent'}),
            deliverable_text='Polished but unsupported story.',
            submitted_by=self.user,
        )
        week13.refresh_from_db()

        self.assertIn('incoherence_reckoning', week13.score_record.auto_components['trap_flags'])
        self.assertEqual(week13.score_record.auto_components['components']['arc_coherence'], 'weak')

    def test_week13_end_to_end_weeks1_to_13_continuity(self):
        self._complete_week1_to_week12(
            week3_overrides={'integrator_decision': 'take_accelerator'},
            week4_overrides={'cloud_commitment': 'sweet_deal_as_written'},
            week6_overrides={'openness': 'open_unguarded'},
            week8_overrides={'rights_posture': 'land_grab'},
            week9_overrides={'vendor_concentration': 'single_hyperscaler'},
        )
        self.assertEqual([entry['week'] for entry in self.run.state['decision_history']], [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])

        week13 = view_briefing(self.run)
        submit_week(
            week13,
            structured_payload=week13_payload(),
            deliverable_text='Week 13 board audit.',
            submitted_by=self.user,
        )
        week13.refresh_from_db()
        self.run.refresh_from_db()

        self.assertEqual([entry['week'] for entry in self.run.state['decision_history']], [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13])
        self.assertEqual(self.run.state['decision_history'][-1]['decision_key'], 'the_audit')
        self.assertIn(self.run.state['flags']['board_verdict'], ('granted', 'denied', 'confidence_lost'))

    def test_week13_contract_shape(self):
        module = registry.get(13)
        self.assertEqual(module.title, 'The Audit')
        self.assertEqual(module.reads_state(), [
            'coherence_anchor',
            'through_lines.coherence',
            'decision_history',
            'relationships',
            'gates',
            'flags',
            'benchmarks.latest',
        ])
        self.assertIn('ask_sizing', [field.key for field in module.decision_spec(Tier.GRADUATE).fields])

    def test_week14_sound_path_completes_run_and_generates_debrief(self):
        self._complete_week1_to_week13()
        week14 = view_briefing(self.run)
        submit_week(
            week14,
            structured_payload=week14_payload(),
            deliverable_text='Integrated strategic synthesis with honest consequence reckoning.',
            submitted_by=self.user,
        )
        week14.refresh_from_db()
        self.run.refresh_from_db()

        self.assertEqual(week14.status, WeekInstanceStatus.SUBMITTED)
        self.assertEqual(self.run.state['decision_history'][-1]['decision_key'], 'the_synthesis')
        self.assertIn('endgame_tier', self.run.state['flags'])
        self.assertIn('coherence_thread', self.run.state['debrief'])

        finalize_score(week14.score_record, instructor_scores={'deliverable_quality': 2})
        week14.refresh_from_db()
        self.run.refresh_from_db()
        benchmark = Benchmark.objects.get(cohort=self.cohort, after_week=14)
        payload = student_benchmark_payload(benchmark)

        self.assertEqual(week14.status, WeekInstanceStatus.SCORED)
        self.assertEqual(self.run.status, 'COMPLETE')
        self.assertEqual(self.run.tier_outcome, self.run.state['flags']['endgame_tier'])
        self.assertEqual(payload['standings'][0]['tier_outcome'], self.run.tier_outcome)

    def test_week14_victory_narrative_over_scars_is_penalized(self):
        self._complete_week1_to_week13(
            week3_overrides={'integrator_decision': 'take_accelerator'},
            week4_overrides={'cloud_commitment': 'sweet_deal_as_written'},
            week12_overrides={'architecture': 'minimal_change', 'hyperscaler_decision': 'committed_spend_discount'},
        )
        week14 = view_briefing(self.run)
        submit_week(
            week14,
            structured_payload=week14_payload({'consequence_reckoning': 'victory_narrative'}),
            deliverable_text='A victory narrative that avoids the scars.',
            submitted_by=self.user,
        )
        week14.refresh_from_db()

        self.assertIn('dishonest_reckoning', week14.score_record.auto_components['trap_flags'])
        self.assertIn('cloud_lockin', week14.score_record.auto_components['components']['scars'])

    def test_week14_weak_arc_cannot_claim_genuine_integration(self):
        self._complete_week1_to_week13(week8_overrides={'rights_posture': 'concede'})
        self.run.state['flags']['arc_coherence_settled'] = 'weak'
        self.run.save()
        week14 = view_briefing(self.run)
        submit_week(
            week14,
            structured_payload=week14_payload(),
            deliverable_text='Claims an integrated story despite weak settled coherence.',
            submitted_by=self.user,
        )
        week14.refresh_from_db()

        self.assertIn('isolated_decisions', week14.score_record.auto_components['trap_flags'])
        self.assertEqual(week14.score_record.auto_components['scores']['coherence'], -2)

    def test_week14_deterministic_endgame_and_debrief_after_reload(self):
        from engine.climax import generate_debrief, resolve_endgame

        self._complete_week1_to_week13(
            week3_overrides={'integrator_decision': 'take_accelerator'},
            week4_overrides={'cloud_commitment': 'sweet_deal_as_written'},
            week6_overrides={'openness': 'open_unguarded'},
            week8_overrides={'rights_posture': 'land_grab'},
            week9_overrides={'vendor_concentration': 'single_hyperscaler'},
        )
        week14 = view_briefing(self.run)
        submit_week(
            week14,
            structured_payload=week14_payload(),
            deliverable_text='Final synthesis.',
            submitted_by=self.user,
        )
        week14.refresh_from_db()
        finalize_score(week14.score_record)
        self.run.refresh_from_db()

        tier_before = resolve_endgame(self.run.state)
        debrief_before = generate_debrief(self.run.state)
        state_before = self.run.state
        reloaded = Run.objects.get(pk=self.run.pk)
        tier_after = resolve_endgame(reloaded.state)
        debrief_after = generate_debrief(reloaded.state)

        self.assertEqual(tier_before, tier_after)
        self.assertEqual(debrief_before, debrief_after)
        self.assertEqual(state_before['debrief'], debrief_after)
        self.assertEqual([entry['week'] for entry in reloaded.state['decision_history']], list(range(1, 15)))

    def test_week14_contract_shape(self):
        module = registry.get(14)
        self.assertEqual(module.title, 'The Synthesis')
        self.assertEqual(module.reads_state(), [
            'accumulated_scores',
            'gates',
            'flags.board_verdict',
            'flags.arc_coherence_settled',
            'flags',
            'coherence_anchor',
            'through_lines.coherence',
            'decision_history',
            'benchmarks.latest',
        ])
        self.assertIn('integration', [field.key for field in module.decision_spec(Tier.GRADUATE).fields])

    def _submit_with(self, overrides):
        instance = view_briefing(self.run)
        payload = week1_payload()
        payload.update(overrides)
        return submit_week(
            instance,
            structured_payload=payload,
            deliverable_text='A rigorous current-state memo.',
            submitted_by=self.user,
        )

    def _complete_week1_and_week2(self, week1_overrides=None):
        self._submit_with(week1_overrides or {})
        self.run.refresh_from_db()
        self.run.current_week = 2
        self.run.save()
        week2 = view_briefing(self.run)
        submit_week(
            week2,
            structured_payload=week2_payload(),
            deliverable_text='Aligned IT strategy with stage-gated governance.',
            submitted_by=self.user,
        )
        self.run.refresh_from_db()
        self.run.current_week = 3
        self.run.save()

    def _complete_week1_week2_week3(self, week1_overrides=None, week3_overrides=None):
        self._complete_week1_and_week2(week1_overrides)
        week3 = view_briefing(self.run)
        submit_week(
            week3,
            structured_payload=week3_payload(week3_overrides),
            deliverable_text='Forward-looking restructure plan.',
            submitted_by=self.user,
        )
        self.run.refresh_from_db()
        self.run.current_week = 4
        self.run.save()

    def _complete_week1_week2_week3_week4(self, week1_overrides=None, week3_overrides=None, week4_overrides=None):
        self._complete_week1_week2_week3(week1_overrides, week3_overrides)
        week4 = view_briefing(self.run)
        submit_week(
            week4,
            structured_payload=week4_payload(week4_overrides),
            deliverable_text='Core-versus-context sourcing memo.',
            submitted_by=self.user,
        )
        week4.refresh_from_db()
        finalize_score(week4.score_record)
        self.run.refresh_from_db()
        self.run.current_week = 5
        self.run.save()

    def _complete_week1_week2_week3_week4_week5(self, week1_overrides=None, week3_overrides=None, week4_overrides=None):
        self._complete_week1_week2_week3_week4(week1_overrides, week3_overrides, week4_overrides)
        week5 = view_briefing(self.run)
        submit_week(
            week5,
            structured_payload=week5_payload(),
            deliverable_text='Disciplined disruption read.',
            submitted_by=self.user,
        )
        self.run.refresh_from_db()
        self.run.current_week = 6
        self.run.save()

    def _complete_week1_to_week6(self, week1_overrides=None, week3_overrides=None, week4_overrides=None, week6_overrides=None):
        self._complete_week1_week2_week3_week4_week5(week1_overrides, week3_overrides, week4_overrides)
        week6 = view_briefing(self.run)
        submit_week(
            week6,
            structured_payload=week6_payload(week6_overrides),
            deliverable_text='Right-sized platform analysis.',
            submitted_by=self.user,
        )
        self.run.refresh_from_db()
        self.run.current_week = 7
        self.run.save()

    def _complete_week1_to_week7(
        self,
        week1_overrides=None,
        week3_overrides=None,
        week4_overrides=None,
        week6_overrides=None,
        week7_overrides=None,
        week7_instructor_signal=True,
    ):
        self._complete_week1_to_week6(week1_overrides, week3_overrides, week4_overrides, week6_overrides)
        week7 = view_briefing(self.run)
        submit_week(
            week7,
            structured_payload=week7_payload(week7_overrides),
            deliverable_text='Vendor squeeze response with measured hedge.',
            submitted_by=self.user,
        )
        week7.refresh_from_db()
        finalize_score(week7.score_record, instructor_components={'ot_signal_addressed': week7_instructor_signal})
        self.run.refresh_from_db()
        self.run.current_week = 8
        self.run.save()

    def _complete_week1_to_week8(
        self,
        week1_overrides=None,
        week3_overrides=None,
        week4_overrides=None,
        week6_overrides=None,
        week7_overrides=None,
        week7_instructor_signal=True,
        week8_overrides=None,
    ):
        self._complete_week1_to_week7(
            week1_overrides,
            week3_overrides,
            week4_overrides,
            week6_overrides,
            week7_overrides,
            week7_instructor_signal,
        )
        week8 = view_briefing(self.run)
        submit_week(
            week8,
            structured_payload=week8_payload(week8_overrides),
            deliverable_text='Data strategy keystone memo.',
            submitted_by=self.user,
        )
        week8.refresh_from_db()
        finalize_score(week8.score_record)
        self.run.refresh_from_db()
        self.run.current_week = 9
        self.run.save()

    def _complete_week1_to_week9(
        self,
        week1_overrides=None,
        week3_overrides=None,
        week4_overrides=None,
        week6_overrides=None,
        week7_overrides=None,
        week7_instructor_signal=True,
        week8_overrides=None,
        week9_overrides=None,
    ):
        self._complete_week1_to_week8(
            week1_overrides,
            week3_overrides,
            week4_overrides,
            week6_overrides,
            week7_overrides,
            week7_instructor_signal,
            week8_overrides,
        )
        week9 = view_briefing(self.run)
        submit_week(
            week9,
            structured_payload=week9_payload(week9_overrides),
            deliverable_text='AI bet focused on predictive maintenance.',
            submitted_by=self.user,
        )
        self.run.refresh_from_db()
        self.run.current_week = 10
        self.run.save()

    def _complete_week1_to_week10(
        self,
        week1_overrides=None,
        week3_overrides=None,
        week4_overrides=None,
        week6_overrides=None,
        week7_overrides=None,
        week7_instructor_signal=True,
        week8_overrides=None,
        week9_overrides=None,
        week10_overrides=None,
    ):
        self._complete_week1_to_week9(
            week1_overrides,
            week3_overrides,
            week4_overrides,
            week6_overrides,
            week7_overrides,
            week7_instructor_signal,
            week8_overrides,
            week9_overrides,
        )
        week10 = view_briefing(self.run)
        submit_week(
            week10,
            structured_payload=week10_payload(week10_overrides),
            deliverable_text='Parallel incident response with transparent disclosure.',
            submitted_by=self.user,
        )
        self.run.refresh_from_db()
        self.run.current_week = 11
        self.run.save()

    def _complete_week1_to_week11(
        self,
        week1_overrides=None,
        week3_overrides=None,
        week4_overrides=None,
        week6_overrides=None,
        week7_overrides=None,
        week7_instructor_signal=True,
        week8_overrides=None,
        week9_overrides=None,
        week10_overrides=None,
        week11_overrides=None,
    ):
        self._complete_week1_to_week10(
            week1_overrides,
            week3_overrides,
            week4_overrides,
            week6_overrides,
            week7_overrides,
            week7_instructor_signal,
            week8_overrides,
            week9_overrides,
            week10_overrides,
        )
        week11 = view_briefing(self.run)
        submit_week(
            week11,
            structured_payload=week11_payload(week11_overrides),
            deliverable_text='Shared-value trust repair.',
            submitted_by=self.user,
        )
        week11.refresh_from_db()
        finalize_score(week11.score_record)
        self.run.refresh_from_db()
        self.run.current_week = 12
        self.run.save()

    def _complete_week1_to_week12(
        self,
        week1_overrides=None,
        week3_overrides=None,
        week4_overrides=None,
        week6_overrides=None,
        week7_overrides=None,
        week7_instructor_signal=True,
        week8_overrides=None,
        week9_overrides=None,
        week10_overrides=None,
        week11_overrides=None,
        week12_overrides=None,
    ):
        self._complete_week1_to_week11(
            week1_overrides,
            week3_overrides,
            week4_overrides,
            week6_overrides,
            week7_overrides,
            week7_instructor_signal,
            week8_overrides,
            week9_overrides,
            week10_overrides,
            week11_overrides,
        )
        week12 = view_briefing(self.run)
        submit_week(
            week12,
            structured_payload=week12_payload(week12_overrides),
            deliverable_text='Edge and repatriation infrastructure plan.',
            submitted_by=self.user,
        )
        self.run.refresh_from_db()
        self.run.current_week = 13
        self.run.save()

    def _complete_week1_to_week13(
        self,
        week1_overrides=None,
        week3_overrides=None,
        week4_overrides=None,
        week6_overrides=None,
        week7_overrides=None,
        week7_instructor_signal=True,
        week8_overrides=None,
        week9_overrides=None,
        week10_overrides=None,
        week11_overrides=None,
        week12_overrides=None,
        week13_overrides=None,
    ):
        self._complete_week1_to_week12(
            week1_overrides,
            week3_overrides,
            week4_overrides,
            week6_overrides,
            week7_overrides,
            week7_instructor_signal,
            week8_overrides,
            week9_overrides,
            week10_overrides,
            week11_overrides,
            week12_overrides,
        )
        week13 = view_briefing(self.run)
        submit_week(
            week13,
            structured_payload=week13_payload(week13_overrides),
            deliverable_text='Board audit.',
            submitted_by=self.user,
        )
        self.run.refresh_from_db()
        self.run.current_week = 14
        self.run.save()


class InstructorGradingDoesNotDoubleTests(TestCase):
    """Regression guard for the grade double-count.

    The instructor's dimension inputs are an ADJUSTMENT: merge_score_components
    adds them on top of the engine's proposal. The grading modal used to pre-fill
    those inputs with the engine's own numbers, so an instructor who agreed with
    the engine and hit save submitted auto as the adjustment and recorded
    auto + auto — every graded score came out at exactly double.

    Submitting all zeros must record the engine's proposal unchanged, in both the
    score record and the run's accumulated totals.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='grader-student', password='pw')
        self.cohort = Cohort.objects.create(name='SIM-GRADE', tier=Tier.UNDERGRAD)
        self.team = Team.objects.create(cohort=self.cohort, name='Team A')
        self.team.members.add(self.user)
        self.run = Run.objects.create(team=self.team)

    def _submitted_record(self):
        instance = view_briefing(self.run)
        submit_week(
            instance,
            structured_payload=week1_payload(),
            deliverable_text='A rigorous current-state memo with a 30-60-90 plan.',
            submitted_by=self.user,
        )
        instance.refresh_from_db()
        return instance.score_record

    def test_zero_adjustment_records_the_engine_proposal(self):
        record = self._submitted_record()
        auto = dict(record.auto_components['scores'])
        # Guard the guard: a run where the engine proposed nothing would pass
        # this test even while doubled.
        self.assertTrue(any(auto.get(d) for d in SCORE_DIMENSIONS))

        finalize_score(record, instructor_scores={d: 0 for d in SCORE_DIMENSIONS})
        record.refresh_from_db()
        for dimension in SCORE_DIMENSIONS:
            self.assertEqual(getattr(record, dimension), auto.get(dimension, 0))

    def test_zero_adjustment_does_not_double_accumulated_totals(self):
        record = self._submitted_record()
        auto = dict(record.auto_components['scores'])
        finalize_score(record, instructor_scores={d: 0 for d in SCORE_DIMENSIONS})
        self.run.refresh_from_db()
        for dimension in SCORE_DIMENSIONS:
            self.assertEqual(
                self.run.state['accumulated_scores'][dimension], auto.get(dimension, 0)
            )

    def test_an_adjustment_still_lands_on_top_of_the_engine_score(self):
        record = self._submitted_record()
        auto = dict(record.auto_components['scores'])
        finalize_score(record, instructor_scores={'coherence': 2})
        record.refresh_from_db()
        self.assertEqual(record.coherence, auto.get('coherence', 0) + 2)


def week1_payload():
    return {
        'current_state_assessment': (
            'The root problem is an ungoverned transformation on a broken data foundation, '
            'invisible factory floor, and depleted IT trust.'
        ),
        'strategy_statement': (
            'DigitalCo will turn the installed base into a data-and-services business while '
            'stabilizing the core.'
        ),
        'connected_products_disposition': 'pause_assess',
        's4_disposition': 'stabilize_map',
        'data_strategy_posture': 'pursue',
        'early_action': 'ot_visibility_assessment',
        'early_action_detail': 'Commission visibility assessment with Petrillo.',
        'ot_black_box_engaged': True,
        'primary_stakeholder_anchor': 'petrillo',
    }


def week2_payload(overrides=None):
    payload = {
        'alignment_rationale': 'Back data-and-services with disciplined governance and Calloway cover.',
        'alignment_choice': 'transform_data_services',
        'governance_included': True,
        'governance_has_stage_gates': True,
        'governance_gives_business_voice': True,
        'calloway_positioning': 'team_recommendation_with_cover',
    }
    if overrides:
        payload.update(overrides)
    return payload


def week3_payload(overrides=None):
    payload = {
        'migration_plan': 'Restructure around mapped dependencies with transparent board ownership.',
        'migration_fate': 'restructure',
        'integrator_decision': 'renegotiate',
        'has_execution_plan': True,
        'communication_posture': 'transparent_ownership',
    }
    if overrides:
        payload.update(overrides)
    return payload


def week4_payload(overrides=None):
    payload = {
        'sourcing_rationale': 'Own differentiating data-services logic and protect cloud portability.',
        'sourcing_approach': 'core_context_split',
        'differentiator_layer': 'own',
        'cloud_commitment': 'portability_protected',
    }
    if overrides:
        payload.update(overrides)
    return payload


def week5_payload(overrides=None):
    payload = {
        'technology_read': 'Pilot quiet disruptions, hold conviction, and avoid keynote chasing.',
        'portfolio.autonomy': 'watch',
        'portfolio.digital_twins': 'pilot',
        'portfolio.additive_manufacturing': 'pilot',
        'portfolio.edge_ai_low_end': 'pilot',
        'innovation_capability': 'embedded',
        'meridian_response': 'strategic_conviction',
    }
    if overrides:
        payload.update(overrides)
    return payload


class _FakeSubmission:
    def __init__(self, payload):
        self.structured_payload = payload


def week6_payload(overrides=None):
    payload = {
        'platform_rationale': 'Build connected services with scoped dealer openness and explicit data rights.',
        'platform_decision': 'connected_services',
        'investment_level': 'right_sized',
        'openness': 'scoped_with_data_rights',
    }
    if overrides:
        payload.update(overrides)
    return payload


def week7_payload(overrides=None):
    payload = {
        'vendor_rationale': 'Renegotiate from the existing position, own the cost issue, and begin a real hedge.',
        'vendor_response': 'renegotiate',
        'communication_posture': 'transparent_ownership',
        'hedge_plan': True,
        'ot_signal_addressed': True,
    }
    if overrides:
        payload.update(overrides)
    return payload


def week8_payload(overrides=None):
    payload = {
        'data_strategy_rationale': 'Build governed predictive data advantage through a shared-value rights model.',
        'rights_posture': 'shared_value',
        'governance_built': True,
        'analytics_architecture': 'predictive',
    }
    if overrides:
        payload.update(overrides)
    return payload


def week9_payload(overrides=None):
    payload = {
        'ai_strategy_rationale': 'Focus AI on predictive maintenance, hedge vendors, and govern shadow AI.',
        'deployment': 'predictive_maintenance_core',
        'ai_sourcing': 'build_differentiating_rent_commodity',
        'vendor_concentration': 'hedged',
        'shadow_ai_response': 'governed_with_plan',
    }
    if overrides:
        payload.update(overrides)
    return payload


def week10_payload(overrides=None):
    payload = {
        'breach_response_rationale': 'Contain in parallel, disclose transparently, and refuse ransom with legal reasoning.',
        'containment': 'contained',
        'disclosure': 'transparent',
        'ransom_decision': 'refuse',
        'triage_approach': 'parallel',
    }
    if overrides:
        payload.update(overrides)
    return payload


def week11_payload(overrides=None):
    payload = {
        'trust_rationale': 'Resolve through shared value, reframe publicly, settle where useful, and repair trust.',
        'rights_resolution': 'shared_value',
        'public_response': 'reframe_and_offer',
        'legal_posture': 'settle_where_serves',
        'trust_repair_plan': True,
    }
    if overrides:
        payload.update(overrides)
    return payload


def week12_payload(overrides=None):
    payload = {
        'cost_reckoning_rationale': 'Break the cloud cost curve with edge processing, selective repatriation, and FinOps.',
        'architecture': 'edge_and_repatriate',
        'hyperscaler_decision': 'renegotiate',
        'finops_discipline': True,
    }
    if overrides:
        payload.update(overrides)
    return payload


def week13_payload(overrides=None):
    payload = {
        'audit_rationale': 'Present one coherent data-and-services story in board language with a well-sized ask.',
        'narrative_coherence': 'coherent',
        'business_case': 'board_language',
        'ask_sizing': 'well_sized',
        'hostile_question_handled': 'defended',
    }
    if overrides:
        payload.update(overrides)
    return payload


def week14_payload(overrides=None):
    payload = {
        'synthesis_rationale': 'Integrate the full arc, own the scars, and set the next strategy from the earned position.',
        'integration': 'genuine',
        'consequence_reckoning': 'honest',
        'forward_strategy': 'grounded_in_real_position',
    }
    if overrides:
        payload.update(overrides)
    return payload

# Create your tests here.


class RegradingIsIdempotentTests(TestCase):
    """Editing a saved grade must overwrite, not accumulate.

    Grading adds the merged score to the run's running total, so a second save
    would count it twice — the same double-count as the pre-filled modal, in a
    new place. The record remembers its contribution and reverses it first.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='regrade-student', password='pw')
        self.cohort = Cohort.objects.create(name='SIM-REGRADE', tier=Tier.UNDERGRAD)
        self.team = Team.objects.create(cohort=self.cohort, name='Team A')
        self.team.members.add(self.user)
        self.run = Run.objects.create(team=self.team)

    def _record(self):
        instance = view_briefing(self.run)
        submit_week(
            instance,
            structured_payload=week1_payload(),
            deliverable_text='A rigorous current-state memo with a 30-60-90 plan.',
            submitted_by=self.user,
        )
        instance.refresh_from_db()
        return instance.score_record

    def test_regrading_replaces_rather_than_adds(self):
        record = self._record()
        auto = dict(record.auto_components['scores'])

        finalize_score(record, instructor_scores={'coherence': 2})
        self.run.refresh_from_db()
        first = dict(self.run.state['accumulated_scores'])

        # Same grade again: nothing should move.
        finalize_score(record, instructor_scores={'coherence': 2})
        self.run.refresh_from_db()
        self.assertEqual(self.run.state['accumulated_scores'], first)

        # A different adjustment replaces the old one.
        finalize_score(record, instructor_scores={'coherence': -1})
        self.run.refresh_from_db()
        record.refresh_from_db()
        self.assertEqual(record.coherence, auto.get('coherence', 0) - 1)
        self.assertEqual(
            self.run.state['accumulated_scores']['coherence'],
            auto.get('coherence', 0) - 1,
        )

    def test_the_weeks_state_update_runs_only_on_the_first_grading(self):
        """Flags and through-lines follow from the decision, not the score, and
        are not written to survive being applied twice."""
        record = self._record()
        finalize_score(record)
        self.run.refresh_from_db()
        after_first = {
            'relationships': dict(self.run.state['relationships']),
            'through_lines': str(self.run.state['through_lines']),
            'flags': dict(self.run.state.get('flags', {})),
        }

        finalize_score(record)
        self.run.refresh_from_db()
        self.assertEqual(dict(self.run.state['relationships']), after_first['relationships'])
        self.assertEqual(str(self.run.state['through_lines']), after_first['through_lines'])
        self.assertEqual(dict(self.run.state.get('flags', {})), after_first['flags'])

    def test_a_record_graded_before_applied_scores_existed_still_reverses(self):
        """Rows graded by the old code carry their contribution in the dimension
        columns; that is what gets reversed on the first edit."""
        record = self._record()
        finalize_score(record, instructor_scores={'coherence': 2})
        # Simulate a pre-migration row.
        record.applied_scores = {}
        record.save(update_fields=['applied_scores'])
        self.run.refresh_from_db()
        before = dict(self.run.state['accumulated_scores'])

        finalize_score(record, instructor_scores={'coherence': 2})
        self.run.refresh_from_db()
        self.assertEqual(self.run.state['accumulated_scores'], before)

    def test_feedback_is_stored_when_supplied_and_left_alone_when_not(self):
        record = self._record()
        finalize_score(record, feedback='What held: you named a real trade-off.')
        record.refresh_from_db()
        self.assertIn('What held', record.feedback)

        finalize_score(record, instructor_scores={'coherence': 1})
        record.refresh_from_db()
        self.assertIn('What held', record.feedback)   # not wiped by a re-grade
