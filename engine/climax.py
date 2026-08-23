from core.models import TierOutcome
from scoring.config import BOARD_VERDICT_CAPS, ENDGAME_THRESHOLDS, GATE_CAPS, OUTCOME_ORDER
from .derivations import derive_data_rights_trace, squeeze_severity, wk4_cloud_commitment


META_LESSON = (
    'The fourteen weeks were one continuous strategy: early choices shaped later '
    'options, credibility, constraints, and the outcome the team could honestly claim.'
)


DRIFT_WEIGHTS = {
    'light': 1,
    'medium': 2,
    'heavy': 3,
    'keystone': 3,
    'convergence': 4,
}


# Holding is deliberately quieter than breaking: one point where the equivalent
# drift costs two. Over fourteen rounds a firm that keeps its line accumulates a
# real advantage without any single week feeling decisive.
HOLD_WEIGHT = 1


def arc_coherence(drift_events, anchor_strength, hold_events=()):
    """Where the firm ended up on its own stated direction.

    Anchor grade, plus every round it held the line, minus every round it drifted.
    The additive term is the point: subtract-only meant a firm that took the
    worse-looking option because the better-looking one contradicted its own
    commitment scored the same as a firm that never faced the choice.
    """
    base = {
        'strong': 8,
        'adequate': 5,
        'weak': 2,
        None: 0,
    }.get(anchor_strength, 0)
    drift = sum(DRIFT_WEIGHTS.get(event.get('weight', 'medium'), 2) for event in drift_events)
    hold = HOLD_WEIGHT * len(hold_events or ())
    score = base + hold - drift
    if score >= 5:
        return 'strong'
    if score >= 2:
        return 'adequate'
    return 'weak'


def board_receptiveness(state: dict):
    relationships = state.get('relationships', {})
    flags = state.get('flags', {})
    score = 0
    score += 2 * relationships.get('calloway', 0)
    score += 2 * relationships.get('reinhardt', 0)
    score += relationships.get('petrillo', 0)
    score += relationships.get('ferraro', 0)
    score += relationships.get('fischer', 0)
    score += relationships.get('tran', 0)
    score += state['accumulated_scores'].get('execution_consequence', 0)
    if state['gates']['budget_credibility']['state'] != 'open':
        score -= 4
    if state['gates']['security_ot']['state'] == 'detonated':
        score -= 3
    if flags.get('breach_catastrophic'):
        score -= 4
    if flags.get('trust_state') == 'repaired':
        score += 3
    elif flags.get('trust_state') == 'partially_repaired':
        score += 1
    elif flags.get('trust_state') == 'damaged':
        score -= 4
    if flags.get('data_advantage') == 'preserved':
        score += 3
    elif flags.get('data_advantage') == 'surrendered':
        score -= 3
    if flags.get('infra_sustainable'):
        score += 2
    if flags.get('lockin_lesson') == 'learned':
        score += 1
    elif flags.get('lockin_lesson') == 'not_learned':
        score -= 2
    score -= len(state['through_lines']['coherence'].get('drift_events', []))
    if score >= 8:
        return 'supportive'
    if score >= 3:
        return 'skeptical'
    return 'hostile'


def resolve_endgame(state: dict, auto=None):
    earned = _earned_tier(state)
    caps = []
    for gate_key, gate in state['gates'].items():
        cap = GATE_CAPS.get(gate_key, {}).get(gate['state'])
        if cap:
            caps.append(cap)
    board_cap = BOARD_VERDICT_CAPS.get(state.get('flags', {}).get('board_verdict'))
    if board_cap:
        caps.append(board_cap)
    if state['through_lines']['coherence'].get('anchor_strength') == 'weak':
        caps.append(TierOutcome.WIN_WITH_SCARS)
    if not caps:
        return earned
    return min([earned, *caps], key=lambda outcome: OUTCOME_ORDER.index(outcome))


def generate_debrief(state: dict):
    return {
        'tier': state.get('flags', {}).get('endgame_tier') or resolve_endgame(state),
        'scars': accumulated_scars(state),
        'decision_trace': trace_decisions(state),
        'coherence_thread': trace_coherence(state),
        'lockin_thread': trace_lockin(state),
        'data_rights_thread': trace_data_rights(state),
        'security_thread': trace_security(state),
        'leadership': trace_leadership(state),
        'meta_lesson': META_LESSON,
    }


def trace_decisions(state: dict):
    return list(state.get('decision_history', []))


def trace_flags(state: dict):
    return dict(state.get('flags', {}))


def accumulated_scars(state: dict):
    flags = state.get('flags', {})
    scars = []
    if flags.get('breach_catastrophic'):
        scars.append('catastrophic_breach')
    elif flags.get('breach_contained'):
        scars.append('contained_breach')
    if state['through_lines']['cloud_lockin'].get('state') == 'locked':
        scars.append('cloud_lockin')
    if flags.get('trust_state') == 'damaged':
        scars.append('damaged_trust')
    if state['gates']['budget_credibility']['state'] != 'open':
        scars.append('budget_credibility')
    if state['gates']['security_ot']['state'] == 'detonated':
        scars.append('security_ot_detonated')
    return scars


def trace_coherence(state: dict):
    coherence = state['through_lines']['coherence']
    return {
        'anchor': state.get('coherence_anchor', ''),
        'anchor_strength': coherence.get('anchor_strength'),
        # hold_events must be passed explicitly. The parameter defaults to empty,
        # so omitting it silently reproduced the old subtract-only arc: holds were
        # recorded in state, the arithmetic was right, and nothing handed it the
        # data. A default that quietly restores the previous behaviour is the
        # hardest kind of bug to see, so both call sites now pass all three.
        'settled': state.get('flags', {}).get('arc_coherence_settled')
        or arc_coherence(
            coherence.get('drift_events', []),
            coherence.get('anchor_strength'),
            coherence.get('hold_events', []),
        ),
        'drift_events': list(coherence.get('drift_events', [])),
        # Carried alongside drift so the debrief can say where a firm held its
        # line, not only where it broke.
        'hold_events': list(coherence.get('hold_events', [])),
        'decision_weeks': _decision_weeks(state),
    }


def trace_lockin(state: dict):
    cloud = state['through_lines']['cloud_lockin']
    flags = state.get('flags', {})
    return {
        'week4_commitment': wk4_cloud_commitment(state),
        'state': cloud.get('state'),
        'depth': cloud.get('depth'),
        'squeeze_severity': squeeze_severity(state),
        'integrator_accelerator_taken': bool(flags.get('integrator_accelerator_taken')),
        'hedge_begun': bool(flags.get('hedge_begun')),
        'infra_sustainable': bool(flags.get('infra_sustainable')),
        'lockin_lesson': flags.get('lockin_lesson'),
        'notes': list(cloud.get('notes', [])),
    }


def trace_data_rights(state: dict):
    trace = derive_data_rights_trace(state)
    flags = state.get('flags', {})
    trace['end_state'] = {
        'trust_state': flags.get('trust_state'),
        'data_advantage': flags.get('data_advantage'),
        'predictive_built': bool(flags.get('predictive_built')),
    }
    return trace


def trace_security(state: dict):
    security = state['through_lines']['security_ot']
    gate = state['gates']['security_ot']
    flags = state.get('flags', {})
    return {
        'posture': security.get('posture'),
        'neglect': security.get('neglect'),
        'gate_state': gate.get('state'),
        'detonated': bool(gate.get('detonated')),
        'breach_contained': bool(flags.get('breach_contained')),
        'breach_catastrophic': bool(flags.get('breach_catastrophic')),
        'notes': list(security.get('notes', [])),
    }


def trace_leadership(state: dict):
    flags = state.get('flags', {})
    return {
        'board_verdict': flags.get('board_verdict'),
        'board_receptiveness': board_receptiveness(state),
        'relationships': dict(state.get('relationships', {})),
        'governance_built': bool(flags.get('governance_built')),
        'calloway_patron': bool(flags.get('calloway_patron')),
        'arc_coherence': flags.get('arc_coherence_settled'),
        'endgame_tier': flags.get('endgame_tier') or resolve_endgame(state),
    }


def _decision_weeks(state: dict):
    return [entry.get('week') for entry in state.get('decision_history', [])]


def _earned_tier(state: dict):
    total = sum(state['accumulated_scores'].values())
    if total >= ENDGAME_THRESHOLDS[TierOutcome.TRIUMPH]:
        return TierOutcome.TRIUMPH
    if total >= ENDGAME_THRESHOLDS[TierOutcome.WIN_WITH_SCARS]:
        return TierOutcome.WIN_WITH_SCARS
    if total >= ENDGAME_THRESHOLDS[TierOutcome.SQUEAK_THROUGH]:
        return TierOutcome.SQUEAK_THROUGH
    return TierOutcome.DISASTER
