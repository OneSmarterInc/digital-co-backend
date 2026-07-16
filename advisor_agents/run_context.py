"""
Slices a team's RunState down to what one advisor would actually know and
care about, per the spec's fourth prompt layer: "the security advisor is
told the current OT posture and the vendor advisor is told the lock-in
state." Returns "" when nothing relevant has happened yet, so the caller
can skip the run_context layer in build_system_prompt entirely.
"""

ADVISOR_FIELDS = {
    "diane": ["strategy_statement", "alignment_choice", "early_action_posture"],
    "marcus": ["platform_sourcing", "cloud_architecture", "s4_fate"],
    "renata": ["ot_security_investment", "petrillo_trust", "breach_response"],
    "daniel": ["strategy_statement", "data_rights_posture", "platform_decision", "ai_deployment"],
    "frank": ["cloud_commitment", "lock_in_level", "s4_fate"],
    "zoe": ["tech_bets", "platform_decision", "ai_deployment"],
}

FIELD_LABELS = {
    "strategy_statement": "the team's declared strategy statement",
    "early_action_posture": "how the team handled the early-action decision",
    "petrillo_trust": "the trust level built with Sharon Petrillo on the factory floor",
    "reinhardt_credibility": "the credibility built with Doug Reinhardt",
    "ferraro_handling": "how the team handled Carl Ferraro",
    "fischer_alliance": "whether Lena Fischer is an ally or a rival",
    "alignment_choice": "which side the team backed in the alignment fight",
    "s4_fate": "what happened to the S/4HANA migration",
    "platform_sourcing": "the make/buy/rent call on the data platform",
    "cloud_commitment": "the cloud/hyperscaler commitment",
    "lock_in_level": "how deep the vendor lock-in has gotten",
    "tech_bets": "which emerging technologies the team bet on",
    "platform_decision": "whether the team pursued a platform play",
    "ot_security_investment": "how seriously OT security has been invested in",
    "data_rights_posture": "the team's data-rights and governance posture",
    "ai_deployment": "where and how AI got deployed",
    "shadow_ai_governance": "how shadow AI is being governed",
    "breach_response": "how the team handled the security breach",
    "privacy_resolution": "how the data-rights fight was resolved",
    "cloud_architecture": "the fleet's cloud/edge architecture",
    "board_ask": "what the team asked the board for",
}


def advisor_run_context(advisor_key, run_state):
    fields = ADVISOR_FIELDS.get(advisor_key, [])
    known = [(f, run_state.get(f)) for f in fields if run_state.get(f)]
    if not known:
        return ""
    return "; ".join(f"{FIELD_LABELS[f]} is {value}" for f, value in known)
