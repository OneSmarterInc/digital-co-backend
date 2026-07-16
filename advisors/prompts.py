from core.models import Tier


UNDERGRAD_TIER_PROMPT = (
    'Tier modifier: undergraduate. Be proactive, volunteer the key consideration, '
    'and name useful frameworks when they help.'
)
GRADUATE_TIER_PROMPT = (
    'Tier modifier: graduate. Be reactive, answer only what is asked, do not name '
    'frameworks, and preserve any agenda without flagging it as an agenda.'
)
GUARDRAILS = (
    'Guardrails: stay in persona and lane; stay on scenario; never state the optimal '
    'answer; do not invent facts beyond the scenario; redirect off-topic questions in '
    'character; stay consistent with earlier turns in this conversation.'
)


def assemble_system_prompt(advisor, tier: Tier, week_context, run_state: dict) -> str:
    tier_prompt = UNDERGRAD_TIER_PROMPT if tier == Tier.UNDERGRAD else GRADUATE_TIER_PROMPT
    run_context = _run_context_for_advisor(advisor, run_state)
    week_context_block = (
        'Week context:\n'
        f'Facts: {_join(week_context.facts)}\n'
        f'Stance: {week_context.stance}\n'
        f'Signal: {week_context.signal}\n'
        f'Misdirection: {week_context.misdirection}'
    )
    return '\n\n'.join([
        advisor.base_system_prompt,
        tier_prompt,
        week_context_block,
        run_context,
        GUARDRAILS,
    ])


def _join(values):
    return '; '.join(values) if values else 'None'


def _run_context_for_advisor(advisor, run_state: dict) -> str:
    through_lines = run_state.get('through_lines', {})
    relationships = run_state.get('relationships', {})
    return (
        'Run context:\n'
        f'Decision history: {run_state.get("decision_history", [])}\n'
        f'Through-lines: {through_lines}\n'
        f'Relationship balance for this advisor key if present: {relationships.get(advisor.key, 0)}'
    )
