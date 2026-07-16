from django.core.exceptions import ValidationError
from django.test import TestCase

from .state import advance_gate, append_decision, default_run_state, validate_run_state


class RunStateTests(TestCase):
    def test_default_state_validates(self):
        state = default_run_state()
        self.assertTrue(validate_run_state(state))

    def test_append_decision_is_append_only(self):
        state = default_run_state()
        updated = append_decision(
            state,
            week=1,
            decision_key='choice',
            choice='balanced',
            trap_flags=[],
        )
        self.assertEqual(state['decision_history'], [])
        self.assertEqual(len(updated['decision_history']), 1)

    def test_gate_cannot_move_backward(self):
        state = advance_gate(default_run_state(), 'security_ot', to_state='detonated', week=10)
        with self.assertRaises(ValidationError):
            advance_gate(state, 'security_ot', to_state='closed', week=11)

    def test_v2_rejects_old_gate_name(self):
        state = default_run_state()
        state['gates']['ot_security'] = state['gates'].pop('security_ot')
        with self.assertRaises(ValidationError):
            validate_run_state(state)

    def test_v2_rejects_board_confidence_scalar(self):
        state = default_run_state()
        state['board_confidence'] = 3
        with self.assertRaises(ValidationError):
            validate_run_state(state)

    def test_known_flag_values_are_validated(self):
        state = default_run_state()
        state['flags']['board_verdict'] = 'maybe'
        with self.assertRaises(ValidationError):
            validate_run_state(state)

    def test_innovation_capability_catalog_matches_week5_values(self):
        state = default_run_state()
        state['flags']['innovation_capability'] = 'embedded'
        self.assertTrue(validate_run_state(state))

    def test_data_rights_week8_postures_are_valid(self):
        for posture in ('shared_value', 'asserted', 'contested_aggressive'):
            state = default_run_state()
            state['through_lines']['data_rights']['posture'] = posture
            self.assertTrue(validate_run_state(state))

    def test_keystone_coherence_weight_is_valid(self):
        state = default_run_state()
        state['through_lines']['coherence']['drift_events'].append({
            'week': 8,
            'kind': 'land_grab',
            'weight': 'keystone',
        })
        self.assertTrue(validate_run_state(state))

# Create your tests here.
