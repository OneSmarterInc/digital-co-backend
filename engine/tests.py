from django.test import TestCase

from core.models import TierOutcome
from core.state import default_run_state

from .climax import arc_coherence, board_receptiveness, resolve_endgame
from .derivations import (
    breach_severity,
    contradicts,
    convergence_severity,
    derive_data_rights_trace,
    derive_wk1_direction,
    extends,
    repair_ceiling,
    squeeze_severity,
    wk4_cloud_commitment,
    wk4_differentiator,
    wk4_took_sweet_deal,
    wk8_rights_posture,
)


class EngineDerivationTests(TestCase):
    def test_prior_decision_accessor(self):
        state = default_run_state()
        state['decision_history'].append({
            'week': 1,
            'decision_key': 'inheritance',
            'choices': {
                'data_strategy_posture': 'pursue',
                'connected_products_disposition': 'pause_assess',
                's4_disposition': 'stabilize_map',
            },
            'trap_flags': [],
        })
        self.assertEqual(derive_wk1_direction(state), 'data_services')
        self.assertTrue(extends('transform_data_services', 'data_services'))
        self.assertTrue(contradicts('stabilize', 'data_services'))

    def test_wk4_differentiator_reads_platform_sourcing_decision(self):
        state = default_run_state()
        state['decision_history'].append({
            'week': 4,
            'decision_key': 'platform_sourcing',
            'choices': {'differentiator_layer': 'rent', 'cloud_commitment': 'sweet_deal_as_written'},
            'trap_flags': [],
        })
        self.assertEqual(wk4_differentiator(state), 'rent')
        self.assertEqual(wk4_cloud_commitment(state), 'sweet_deal_as_written')
        self.assertTrue(wk4_took_sweet_deal(state))

    def test_severity_helpers_read_shared_state(self):
        state = default_run_state()
        state['through_lines']['cloud_lockin']['state'] = 'locked'
        state['through_lines']['cloud_lockin']['depth'] = 2
        state['flags']['integrator_accelerator_taken'] = True
        state['gates']['security_ot']['state'] = 'detonated'
        state['through_lines']['security_ot']['neglect'] = 4
        self.assertEqual(squeeze_severity(state), 3)
        self.assertEqual(breach_severity(state), 4)
        self.assertEqual(repair_ceiling(4), 'damaged')

    def test_breach_severity_compounds_shadow_ai_incident(self):
        state = default_run_state()
        state['flags']['shadow_ai_incident_open'] = True
        self.assertEqual(breach_severity(state), 2)
        state['through_lines']['security_ot']['neglect'] = 2
        self.assertEqual(breach_severity(state), 4)

    def test_data_rights_trace_is_derived_from_canonical_state(self):
        state = default_run_state()
        state['decision_history'].append({
            'week': 6,
            'decision_key': 'platform_question',
            'choices': {'openness': 'open_unguarded'},
            'trap_flags': [],
        })
        state['decision_history'].append({
            'week': 8,
            'decision_key': 'data_keystone',
            'choices': {'rights_posture': 'land_grab'},
            'trap_flags': ['land_grab'],
        })
        state['through_lines']['data_rights']['posture'] = 'contested_aggressive'
        state['flags']['fleet_impact'] = 'severe'
        state['relationships']['ferraro'] = -2
        state['relationships']['tran'] = -1

        trace = derive_data_rights_trace(state)
        self.assertEqual(wk8_rights_posture(state), 'land_grab')
        self.assertEqual(convergence_severity(state), 4)
        self.assertEqual(trace['inputs']['week6_openness'], 'open_unguarded')
        self.assertEqual(trace['inputs']['week8_rights_posture'], 'land_grab')
        self.assertEqual(trace['derived']['repair_ceiling'], 'damaged')
        self.assertEqual(trace['result'], 'full_revolt')

    def test_climax_helpers(self):
        state = default_run_state()
        for key in state['accumulated_scores']:
            state['accumulated_scores'][key] = 20
        state['relationships']['reinhardt'] = 3
        state['flags']['board_verdict'] = 'denied'
        self.assertEqual(
            arc_coherence([{'week': 11, 'kind': 'contradiction', 'weight': 'convergence'}], 'strong'),
            'adequate',
        )
        self.assertEqual(board_receptiveness(state), 'supportive')
        self.assertEqual(resolve_endgame(state), TierOutcome.SQUEAK_THROUGH)

# Create your tests here.


class ArcCoherenceRewardsHoldingTests(TestCase):
    """The arc must distinguish a firm that held its line from one that was
    never tested. Before this it could not: it started at the week-1 anchor
    grade and only ever subtracted, so avoiding every penalised option scored
    identically to taking the worse-looking road on purpose.
    """

    def test_holding_beats_never_being_tested(self):
        # A weak anchor is where the difference shows: an adequate one already
        # sits on the 'strong' threshold with no events at all.
        untested = arc_coherence([], 'weak', [])
        held = arc_coherence([], 'weak', [{'week': w} for w in (2, 4, 6)])
        self.assertEqual(untested, 'adequate')
        self.assertEqual(held, 'strong', 'holding the line earned nothing')

    def test_holding_is_quieter_than_breaking(self):
        """One hold must not cancel one drift — breaking is the louder signal."""
        one_drift = arc_coherence([{'week': 2}], 'adequate', [{'week': 3}])
        clean = arc_coherence([], 'adequate', [])
        self.assertNotEqual(one_drift, clean)
        # 5 - 2 + 1 = 4 -> adequate; two holds are needed to undo one drift.
        self.assertEqual(one_drift, 'adequate')
        self.assertEqual(arc_coherence([{'week': 2}], 'adequate', [{'week': 3}, {'week': 4}]), 'strong')

    def test_drift_still_dominates_a_run_that_zigzagged(self):
        # Four drifts at two apiece outweigh a strong anchor and a single hold.
        drifts = [{'week': w} for w in (2, 3, 4, 5)]
        holds = [{'week': 6}]
        self.assertEqual(arc_coherence(drifts, 'strong', holds), 'weak')

    def test_a_run_predating_hold_events_still_scores(self):
        """Runs created before the ledger existed pass no hold list at all."""
        self.assertEqual(arc_coherence([], 'strong'), 'strong')
        self.assertEqual(arc_coherence([{'week': 2}, {'week': 3}], 'strong'), 'adequate')
