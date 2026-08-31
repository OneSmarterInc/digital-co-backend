"""Generating written feedback for a graded round.

The model is given what the firm wrote — this round, and their prior rounds for
continuity — and nothing about how any of it was scored. It cannot leak a rubric
it was never shown, which is the same discipline the help channel uses.

It also receives nothing from a later week, so it cannot hint at what is coming.
"""
import re

from advisors.llm_client import get_llm_client

from .prompts import MAX_WORDS, SYSTEM_PROMPT, is_usable


# The model writes "S4" often enough to be worth fixing deterministically rather
# than only asking. Everything a team reads — the field label, the briefings, the
# exhibits — says "S/4", and a second spelling reads as a second system. The
# prompt asks; this guarantees.
_HOUSE_STYLE = (
    (re.compile(r'\bS4HANA\b'), 'S/4HANA'),
    (re.compile(r'\bS4\b'), 'S/4'),
)


def house_style(text: str) -> str:
    """Normalise product spellings in generated prose."""
    for pattern, replacement in _HOUSE_STYLE:
        text = pattern.sub(replacement, text)
    return text

# How many prior rounds to carry. Enough for continuity, not so much that the
# useful detail of this round drowns.
PRIOR_ROUNDS = 3
MAX_TEXT = 1500


def _clip(value, limit=MAX_TEXT):
    text = '' if value is None else str(value)
    return text[:limit]


def _written(payload: dict) -> list[str]:
    """The long free-text answers — the material the course actually assesses."""
    return [
        f'{key.replace("_", " ")}: {_clip(value)}'
        for key, value in (payload or {}).items()
        if isinstance(value, str) and len(value) > 60
    ]


def _choices(payload: dict) -> list[str]:
    return [
        f'{key.replace("_", " ")}: {value}'
        for key, value in (payload or {}).items()
        if not (isinstance(value, str) and len(value) > 60)
    ]



# What each engine finding means in plain behavioural terms. The generator is
# given these, never the flag names or the scores: "coherence_drift" is design
# vocabulary and "-2" is a rubric, but "this round's decision moves off the
# direction they set in week 1" is simply what happened, and it is the thing a
# firm needs told. Anything unmapped is omitted rather than guessed at.
FLAG_PLAIN = {
    'coherence_drift': "this round's decision moves off the direction they set in week 1",
    'mush': 'they funded both directions rather than choosing between them',
    'misallocation': 'they put money behind something their stated direction does not support',
    'no_governance': 'they did not put a governance structure in place',
    'governance_neglect': 'they did not put a governance structure in place',
    'calloway_misread_safe': 'they read the chief executive as wanting the safe option',
    'calloway_exposed': 'they left the chief executive carrying the risk in public',
    'sunk_cost_pushthrough': 'they kept funding an effort because of what had already been spent',
    'integrator_lifeline': "they took the vendor's proprietary shortcut",
    'blame_shift': 'they attributed the failure to the vendor',
    'spin': 'they led with the recovery plan rather than with what went wrong',
    'kill_connected_products': 'they ended the connected-products programme outright',
    'ferraro_capture': 'they let the revenue side set the agenda',
    'data_strategy_slow_walk': 'they kept the data programme alive but deliberately under-resourced',
    'chased_dazzle': "they matched a rival's announcement rather than reasoning from their own economics",
    'herd_chase': "they matched a rival's announcement rather than reasoning from their own economics",
    'herd_pivot': "they moved off their own direction in response to a rival",
    'platform_envy': 'they committed to a full platform ahead of demonstrated demand',
    'platform_on_sand': 'they committed to a platform on a foundation they had already rented out',
    'starved_differentiator': 'they rented the part of the estate that makes them different',
    'sweet_deal_lockin': "they took the provider's terms as offered",
    'reflexive_switch': 'they moved off the vendor immediately rather than negotiating',
    'passive_absorb': 'they absorbed the increase without building an alternative',
    'land_grab': 'they asserted ownership of the machine data',
    'duck': 'they left the data-rights question unsettled',
    'ai_theater': 'they spread pilots across the business rather than aiming at one decision',
    'no_foundation': 'they built on a data foundation that is not there yet',
    'ungoverned_shadow_ai': 'they left unofficial AI use unaddressed',
    'linear_triage': 'they worked the crisis one stage at a time',
    'containment_overclaimed': 'they claimed more containment than they had',
    'concede': 'they withdrew the terms under pressure',
    'fight_public': 'they contested the criticism publicly',
    'committed_spend_retrap': 'they took the same shape of deal a second time',
    'stayed_trapped': 'they took the same shape of deal a second time',
    'did_not_learn': 'they took the same shape of deal a second time',
    'lockin_unlearned': 'they took the same shape of deal a second time',
    'contradictory_deck': 'they presented each decision on its own merits rather than as one line',
    'jargon': 'they framed the board case around technical detail',
    'mis_sized_ask': 'the ask does not match what the next stage needs',
    'folded': 'they qualified the position when it was challenged',
    'incoherence_reckoning': 'the record they presented does not hold together',
    'isolated_decisions': 'the account treats the rounds as unconnected',
    'dishonest_reckoning': 'the account leads with what worked and leaves out what did not',
    'ungrounded_forward': 'the forward plan describes a company that does not exist yet',
    'openness_landmine': 'they opened access without terms on what may be done with the data',
    'late_pivot': 'they changed direction late',
}


def _record_shows(score_record) -> str:
    """What actually happened this round, as distinct from what they say happened.

    Without this the generator only had the firm's own deliverable, so a firm
    that reversed its direction and wrote that it had not was congratulated for
    continuity — the opposite of what the round teaches. The engine's reading is
    given as fact, in plain terms, and the prompt is told it outranks the
    firm's account of itself.
    """
    auto = score_record.auto_components or {}
    coherence = (auto.get('scores') or {}).get('coherence', 0)
    flags = auto.get('trap_flags') or []

    lines = []
    if coherence < 0:
        lines.append(
            'The record shows this round moving OFF the direction they set in week 1. '
            'If their writing claims the direction is unchanged, that claim is not '
            'supported — say so plainly, and describe what actually changed.'
        )
    elif coherence > 0:
        lines.append('The record shows this round continuing the direction they set in week 1.')

    observed = [FLAG_PLAIN[f] for f in flags if f in FLAG_PLAIN]
    if observed:
        lines.append('Also on the record this round: ' + '; '.join(observed) + '.')

    return '\n'.join(lines)


def build_context(score_record) -> str:
    """Everything the model may see. Nothing from a later week."""
    instance = score_record.week_instance
    run = instance.run
    week = instance.week_number
    submission = instance.submission

    parts = [f'This is round {week} of fourteen.']

    anchor = (run.state or {}).get('coherence_anchor', '').strip()
    if anchor and week > 1:
        parts.append(
            'The strategy statement this firm committed to in week 1, in their own '
            f'words:\n"{_clip(anchor, 600)}"'
        )

    # Prior rounds, for the sentence that connects a decision to a commitment.
    history = [
        d for d in (run.state or {}).get('decision_history', [])
        if d.get('week') and d['week'] < week
    ][-PRIOR_ROUNDS:]
    if history:
        lines = []
        for entry in history:
            choices = ', '.join(f'{k}: {v}' for k, v in (entry.get('choices') or {}).items()
                                if not (isinstance(v, str) and len(v) > 60))
            lines.append(f'Round {entry["week"]} — {_clip(choices, 500)}')
        parts.append('What they committed in earlier rounds:\n' + '\n'.join(lines))

    if submission:
        written = _written(submission.structured_payload)
        if written:
            parts.append('What they wrote this round:\n' + '\n\n'.join(written))
        choices = _choices(submission.structured_payload)
        if choices:
            parts.append('The calls they made this round:\n' + '\n'.join(choices))
        if submission.deliverable_text:
            parts.append(
                'Their written deliverable this round:\n' + _clip(submission.deliverable_text)
            )

    # Last, so it is the freshest thing in context and outranks the firm's own
    # account of itself, which it directly contradicts in the case that matters.
    record = _record_shows(score_record)
    if record:
        parts.append('What the record shows, which is not always what they wrote:\n' + record)

    parts.append('Write their feedback.')
    return '\n\n'.join(parts)


def generate_feedback(score_record, client=None) -> tuple[str, str]:
    """(feedback, problem). Feedback is '' when it could not be produced safely.

    Never raises: a grade must save whether or not feedback could be written.
    """
    submission = score_record.week_instance.submission
    if not submission:
        return '', 'nothing was submitted for this round'

    context = build_context(score_record)
    try:
        llm = client or get_llm_client()
        text = llm.complete(
            system=SYSTEM_PROMPT,
            messages=[{'role': 'user', 'content': context}],
        ).strip()
    except Exception as exc:
        return '', f'could not be generated: {exc}'

    # One retry, and only on length. A draft that ran long is usually good and
    # simply overshot, so asking it to cut is worth a second call. A draft that
    # named the scoring is discarded outright — retrying a leak just samples
    # until one slips through the guard.
    ok, problem = is_usable(text)
    if not ok and 'long' in problem:
        try:
            text = llm.complete(
                system=SYSTEM_PROMPT,
                messages=[
                    {'role': 'user', 'content': context},
                    {'role': 'assistant', 'content': text},
                    {'role': 'user', 'content': (
                        f'That is {len(text.split())} words. The limit is {MAX_WORDS}. '
                        'Rewrite it under the limit by cutting, not by compressing every '
                        'sentence into a clause. Same three paragraphs, fewer words. '
                        'Reply with the rewritten feedback only.'
                    )},
                ],
            ).strip()
        except Exception as exc:
            return '', f'could not be generated: {exc}'

    ok, problem = is_usable(text)
    if not ok:
        # Worse than nothing: generic or rubric-leaking feedback teaches the
        # wrong lesson, so it is discarded rather than shown.
        return '', problem
    return house_style(text), ''
