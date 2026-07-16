from core.models import TierOutcome


def decision_choice(state: dict, decision_key: str):
    for entry in reversed(state.get('decision_history', [])):
        if entry.get('decision_key') == decision_key:
            return entry.get('choice')
    return None


def derive_wk1_direction(state: dict):
    wk1 = _decision_entry(state, 1, 'inheritance')
    if not wk1:
        return 'ambiguous'
    choices = wk1.get('choices', {})
    if choices.get('data_strategy_posture') == 'pursue' and choices.get('connected_products_disposition') != 'kill':
        return 'data_services'
    if choices.get('connected_products_disposition') == 'kill' or choices.get('s4_disposition') == 'commit_finish':
        return 'stabilize'
    return 'ambiguous'


def contradicts(choice: str, prior_direction: str):
    return (
        (choice == 'stabilize' and prior_direction == 'data_services')
        or (choice == 'transform_data_services' and prior_direction == 'stabilize')
    )


def extends(choice: str, prior_direction: str):
    return (
        (choice == 'transform_data_services' and prior_direction == 'data_services')
        or (choice == 'stabilize' and prior_direction == 'stabilize')
        or prior_direction == 'ambiguous'
    )


def _decision_entry(state: dict, week: int, decision_key: str):
    for entry in reversed(state.get('decision_history', [])):
        if entry.get('week') == week and entry.get('decision_key') == decision_key:
            return entry
    return None


def wk4_differentiator(state: dict):
    wk4 = _decision_entry(state, 4, 'platform_sourcing')
    if not wk4:
        return None
    return wk4.get('choices', {}).get('differentiator_layer')


def wk4_cloud_commitment(state: dict):
    wk4 = _decision_entry(state, 4, 'platform_sourcing')
    if not wk4:
        return None
    return wk4.get('choices', {}).get('cloud_commitment')


def wk8_rights_posture(state: dict):
    wk8 = _decision_entry(state, 8, 'data_keystone')
    if not wk8:
        return None
    return wk8.get('choices', {}).get('rights_posture')


def wk4_took_sweet_deal(state: dict):
    return wk4_cloud_commitment(state) in ('sweet_deal_as_written', 'sweet_deal', 'take_sweet_deal', True)


def squeeze_severity(state: dict):
    cloud = state['through_lines']['cloud_lockin']
    severity = int(cloud.get('depth', 0))
    if cloud.get('state') == 'locked':
        severity += 2
    if state.get('flags', {}).get('integrator_accelerator_taken'):
        severity += 1
    return _band(severity, low=1, high=3)


def breach_severity(state: dict):
    gate = state['gates']['security_ot']
    security = state['through_lines']['security_ot']
    severity = 1 + max(0, int(security.get('neglect', 0)) - int(security.get('posture', 0)))
    if gate.get('state') == 'closed':
        severity += 2
    if gate.get('state') == 'detonated':
        severity += 4
    if state.get('flags', {}).get('shadow_ai_incident_open'):
        severity += 1
    return _band(severity, low=1, high=4)


def convergence_severity(state: dict):
    flags = state.get('flags', {})
    severity = 0
    if state['through_lines']['data_rights'].get('posture') == 'contested_aggressive':
        severity += 3
    elif state['through_lines']['data_rights'].get('posture') == 'asserted':
        severity += 2
    if flags.get('fleet_impact') == 'severe':
        severity += 3
    elif flags.get('fleet_impact') == 'moderate':
        severity += 1
    if flags.get('shadow_ai_incident_open'):
        severity += 1
    if state.get('relationships', {}).get('tran', 0) < 0:
        severity += 1
    severity -= max(state.get('relationships', {}).get('ferraro', 0), 0)
    return _band(severity, low=1, high=4)


def derive_data_rights_trace(state: dict):
    data_rights = state['through_lines']['data_rights']
    relationships = state.get('relationships', {})
    flags = state.get('flags', {})
    severity = convergence_severity(state)
    return {
        'crisis': 'data_rights_convergence',
        'inputs': {
            'week6_openness': _week6_openness(state),
            'week8_rights_posture': wk8_rights_posture(state),
            'through_lines.data_rights.posture': data_rights.get('posture'),
            'flags.fleet_impact': flags.get('fleet_impact'),
            'flags.shadow_ai_incident_open': bool(flags.get('shadow_ai_incident_open')),
            'relationships.ferraro': relationships.get('ferraro', 0),
            'relationships.tran': relationships.get('tran', 0),
            'coherence_drift_count': len(state['through_lines']['coherence'].get('drift_events', [])),
        },
        'derived': {
            'convergence_severity': severity,
            'repair_ceiling': repair_ceiling(severity),
        },
        'result': _convergence_condition(severity),
    }


def _week6_openness(state: dict):
    wk6 = _decision_entry(state, 6, 'platform_question')
    if not wk6:
        return None
    return wk6.get('choices', {}).get('openness')


def _convergence_condition(severity: int):
    if severity >= 4:
        return 'full_revolt'
    if severity >= 3:
        return 'deep_revolt'
    if severity >= 2:
        return 'serious_trust_crisis'
    return 'manageable_tension'


def repair_ceiling(severity):
    if severity >= 4:
        return 'damaged'
    if severity >= 2:
        return 'partially_repaired'
    return 'repaired'


def _band(value, *, low, high):
    return max(low, min(high, value))


def outcome_rank(outcome):
    order = (
        TierOutcome.DISASTER,
        TierOutcome.SQUEAK_THROUGH,
        TierOutcome.WIN_WITH_SCARS,
        TierOutcome.TRIUMPH,
    )
    return order.index(outcome)
