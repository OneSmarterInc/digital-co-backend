from copy import deepcopy

from django.core.exceptions import ValidationError


SCHEMA_VERSION = 2
SCORE_DIMENSIONS = (
    'strategic_judgment',
    'execution_consequence',
    'coherence',
    'deliverable_quality',
)
GATE_KEYS = ('security_ot', 'budget_credibility')
GATE_STATES = ('open', 'closed', 'detonated')
CLOUD_LOCKIN_STATES = ('unset', 'locked', 'broken')
DATA_RIGHTS_POSTURES = (
    'unset',
    'open_unresolved',
    'scoped',
    'closed',
    'shared_value',
    'asserted',
    'contested_aggressive',
)
ANCHOR_STRENGTHS = (None, 'strong', 'adequate', 'weak')
RELATIONSHIP_KEYS = (
    'calloway',
    'reinhardt',
    'petrillo',
    'ferraro',
    'fischer',
    'tran',
)
FLAG_CATALOG = {
    'integrator_accelerator_taken': {'type': bool},
    'additive_threat_recognized': {'type': bool},
    'innovation_capability': {'values': ('separate_group', 'embedded')},
    'meridian_chased': {'type': bool},
    'predictive_built': {'type': bool},
    'hedge_begun': {'type': bool},
    'shadow_ai_governed': {'type': bool},
    'shadow_ai_incident_open': {'type': bool},
    'breach_contained': {'type': bool},
    'breach_catastrophic': {'type': bool},
    'fleet_impact': {'values': ('severe', 'moderate', 'limited')},
    'data_advantage': {'values': ('preserved', 'surrendered', 'won_but_hollow')},
    'trust_state': {'values': ('repaired', 'partially_repaired', 'damaged')},
    'infra_sustainable': {'type': bool},
    'lockin_lesson': {'values': ('learned', 'not_learned')},
    'board_verdict': {'values': ('granted', 'denied', 'confidence_lost')},
    'arc_coherence_settled': {'values': ('strong', 'adequate', 'weak')},
    'endgame_tier': {'values': ('TRIUMPH', 'WIN_WITH_SCARS', 'SQUEAK_THROUGH', 'DISASTER')},
    'connected_products_killed': {'type': bool},
    's4_precommitted': {'type': bool},
    'governance_built': {'type': bool},
    'calloway_patron': {'type': bool},
}


def default_gate():
    return {'state': 'open', 'set_week': None, 'detonated': False}


def default_run_state():
    return {
        'schema_version': SCHEMA_VERSION,
        'coherence_anchor': '',
        'accumulated_scores': {dimension: 0 for dimension in SCORE_DIMENSIONS},
        'gates': {
            'security_ot': default_gate(),
            'budget_credibility': default_gate(),
        },
        'through_lines': {
            'security_ot': {'posture': 0, 'neglect': 0, 'notes': []},
            'cloud_lockin': {'state': 'unset', 'depth': 0, 'notes': []},
            'data_rights': {'posture': 'unset', 'notes': []},
            'coherence': {
                'anchor_set': False,
                'anchor_strength': None,
                'drift_events': [],
                # Holding a line was previously invisible: the arc subtracted
                # drift from the week-1 anchor grade and had no additive term,
                # so a firm that held under pressure finished identical to one
                # that was never tested. Read with .get() everywhere — runs
                # created before this key exists must keep working.
                'hold_events': [],
            },
        },
        'relationships': {key: 0 for key in RELATIONSHIP_KEYS},
        'decision_history': [],
        'flags': {},
    }


def validate_run_state(state):
    if not isinstance(state, dict):
        raise ValidationError('Run.state must be an object.')
    required = default_run_state()
    missing = [key for key in required if key not in state]
    if missing:
        raise ValidationError(f'Run.state is missing required keys: {", ".join(missing)}')
    if state.get('schema_version') != SCHEMA_VERSION:
        raise ValidationError(f'Run.state schema_version must be {SCHEMA_VERSION}.')
    _validate_scores(state['accumulated_scores'])
    _validate_gates(state['gates'])
    _validate_through_lines(state['through_lines'])
    _validate_relationships(state['relationships'])
    if not isinstance(state.get('decision_history'), list):
        raise ValidationError('decision_history must be a list.')
    if not isinstance(state.get('flags'), dict):
        raise ValidationError('flags must be an object.')
    if 'board_confidence' in state:
        raise ValidationError('Run.state must not contain a separate board_confidence scalar.')
    _validate_flags(state['flags'])
    return True


def _validate_scores(scores):
    for dimension in SCORE_DIMENSIONS:
        if dimension not in scores:
            raise ValidationError(f'accumulated_scores.{dimension} is required.')
        if not isinstance(scores[dimension], (int, float)):
            raise ValidationError(f'accumulated_scores.{dimension} must be numeric.')


def _validate_gates(gates):
    for key in GATE_KEYS:
        gate = gates.get(key)
        if not isinstance(gate, dict):
            raise ValidationError(f'gates.{key} is required.')
        if gate.get('state') not in GATE_STATES:
            raise ValidationError(f'gates.{key}.state is invalid.')
        if not isinstance(gate.get('detonated'), bool):
            raise ValidationError(f'gates.{key}.detonated must be boolean.')
    if 'ot_security' in gates:
        raise ValidationError('gates.ot_security was renamed to gates.security_ot in schema v2.')


def _validate_through_lines(through_lines):
    required = default_run_state()['through_lines']
    missing = [key for key in required if key not in through_lines]
    if missing:
        raise ValidationError(f'through_lines is missing required keys: {", ".join(missing)}')

    security = through_lines['security_ot']
    for counter in ('posture', 'neglect'):
        if not isinstance(security.get(counter), int) or security[counter] < 0:
            raise ValidationError(f'through_lines.security_ot.{counter} must be a non-negative integer.')
    if not isinstance(security.get('notes'), list):
        raise ValidationError('through_lines.security_ot.notes must be a list.')

    cloud = through_lines['cloud_lockin']
    if cloud.get('state') not in CLOUD_LOCKIN_STATES:
        raise ValidationError('through_lines.cloud_lockin.state is invalid.')
    if not isinstance(cloud.get('depth'), int) or cloud['depth'] < 0:
        raise ValidationError('through_lines.cloud_lockin.depth must be a non-negative integer.')
    if not isinstance(cloud.get('notes'), list):
        raise ValidationError('through_lines.cloud_lockin.notes must be a list.')

    data_rights = through_lines['data_rights']
    if data_rights.get('posture') not in DATA_RIGHTS_POSTURES:
        raise ValidationError('through_lines.data_rights.posture is invalid.')
    if not isinstance(data_rights.get('notes'), list):
        raise ValidationError('through_lines.data_rights.notes must be a list.')

    coherence = through_lines['coherence']
    if not isinstance(coherence.get('anchor_set'), bool):
        raise ValidationError('through_lines.coherence.anchor_set must be boolean.')
    if coherence.get('anchor_strength') not in ANCHOR_STRENGTHS:
        raise ValidationError('through_lines.coherence.anchor_strength is invalid.')
    if not isinstance(coherence.get('drift_events'), list):
        raise ValidationError('through_lines.coherence.drift_events must be a list.')
    for event in coherence['drift_events']:
        if not isinstance(event, dict) or 'week' not in event or 'kind' not in event:
            raise ValidationError('Each coherence drift event must include week and kind.')
        if 'weight' in event and event['weight'] not in ('light', 'medium', 'heavy', 'keystone', 'convergence'):
            raise ValidationError('Coherence drift event weight is invalid.')


def _validate_relationships(relationships):
    for key in RELATIONSHIP_KEYS:
        if key not in relationships:
            raise ValidationError(f'relationships.{key} is required.')
        if not isinstance(relationships[key], int):
            raise ValidationError(f'relationships.{key} must be an integer.')


def _validate_flags(flags):
    for key, value in flags.items():
        spec = FLAG_CATALOG.get(key)
        if not spec:
            continue
        if 'type' in spec and not isinstance(value, spec['type']):
            raise ValidationError(f'flags.{key} must be {spec["type"].__name__}.')
        if 'values' in spec and value not in spec['values']:
            raise ValidationError(f'flags.{key} has an invalid value.')


def append_decision(state, *, week, decision_key, choice, trap_flags=None):
    new_state = deepcopy(state)
    new_state['decision_history'].append({
        'week': week,
        'decision_key': decision_key,
        'choice': choice,
        'trap_flags': trap_flags or [],
    })
    validate_run_state(new_state)
    return new_state


def append_note(state, path, note):
    new_state = deepcopy(state)
    target = new_state
    for key in path:
        target = target[key]
    target.append(note)
    validate_run_state(new_state)
    return new_state


def set_flag(state, key, value=True):
    new_state = deepcopy(state)
    if key in new_state['flags'] and new_state['flags'][key] != value:
        raise ValidationError(f'Flag {key} already exists with a different value.')
    new_state['flags'][key] = value
    validate_run_state(new_state)
    return new_state


def advance_gate(state, gate_key, *, to_state, week):
    new_state = deepcopy(state)
    gate = new_state['gates'][gate_key]
    current_index = GATE_STATES.index(gate['state'])
    next_index = GATE_STATES.index(to_state)
    if next_index < current_index:
        raise ValidationError('Gates can only move forward.')
    gate['state'] = to_state
    gate['set_week'] = gate['set_week'] or week
    gate['detonated'] = to_state == 'detonated' or gate['detonated']
    validate_run_state(new_state)
    return new_state
