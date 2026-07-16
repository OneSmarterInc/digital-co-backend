"""
A team's accumulated state across the fourteen-week arc. Plain data, no
Django dependency, so the same shape works whether it ends up backed by a
JSONField, a set of model columns, or a test fixture. Every field starts
None and fills in as the team plays through the corresponding week.
"""

RUN_STATE_TEMPLATE = {
    "strategy_statement": None,      # week 1
    "early_action_posture": None,    # week 1
    "petrillo_trust": None,          # week 1, feeds the OT gate
    "reinhardt_credibility": None,   # week 1
    "ferraro_handling": None,        # week 1, feeds weeks 8/11
    "fischer_alliance": None,        # week 1, feeds weeks 5/6
    "alignment_choice": None,        # week 2
    "s4_fate": None,                 # week 3
    "platform_sourcing": None,       # week 4
    "cloud_commitment": None,        # week 4, the deepest lock-in thread
    "lock_in_level": None,           # updated weeks 4/7/12
    "tech_bets": None,               # week 5
    "platform_decision": None,       # week 6, seeds week 11
    "ot_security_investment": None,  # tracked weeks 1/7, gates week 10
    "data_rights_posture": None,     # week 8, the keystone
    "ai_deployment": None,           # week 9
    "shadow_ai_governance": None,    # week 9
    "breach_response": None,         # week 10
    "privacy_resolution": None,      # week 11
    "cloud_architecture": None,      # week 12
    "board_ask": None,               # week 13
}


def new_run_state():
    return dict(RUN_STATE_TEMPLATE)
