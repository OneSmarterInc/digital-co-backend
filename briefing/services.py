"""The firm-aware preamble above a round's briefing.

Generated once, when the round opens, and stored on the WeekInstance — so every
member of the firm reads the same words, and re-opening the page does not
re-roll them. Round 1 never has one: there is no history to be aware of yet.

Failure is silent by design. A briefing that renders without its preamble is
the normal briefing; a briefing that 500s because a model timed out is a firm
that cannot play the round.
"""
from advisors.llm_client import get_llm_client

from .prompts import SYSTEM_PROMPT, is_usable

PRIOR_ROUNDS = 3
MAX_TEXT = 800


def _clip(value, limit=MAX_TEXT):
    return ('' if value is None else str(value))[:limit]


def build_context(run, week_number: int) -> str:
    """This firm's own history, and nothing else.

    Deliberately excludes the current round's briefing text: the preamble must
    not summarise or preview the round it introduces.
    """
    state = run.state or {}
    parts = [f'This firm is opening round {week_number} of fourteen.']

    anchor = (state.get('coherence_anchor') or '').strip()
    if anchor:
        parts.append(
            'The strategy statement they committed to in round 1, in their own '
            f'words:\n"{_clip(anchor, 600)}"'
        )

    history = [
        d for d in (state.get('decision_history') or [])
        if d.get('week') and d['week'] < week_number
    ][-PRIOR_ROUNDS:]
    if history:
        lines = []
        for entry in history:
            choices = ', '.join(
                f'{k}: {v}' for k, v in (entry.get('choices') or {}).items()
                if not (isinstance(v, str) and len(v) > 60)
            )
            lines.append(f'Round {entry["week"]} — {_clip(choices, 400)}')
        parts.append('What they committed in recent rounds:\n' + '\n'.join(lines))

    parts.append('Write their opening.')
    return '\n\n'.join(parts)


def generate_preamble(run, week_number: int, client=None) -> tuple[str, str]:
    """(preamble, problem). Empty preamble means the briefing renders as-is."""
    if week_number <= 1:
        return '', 'round 1 has no history to reflect'

    state = run.state or {}
    has_history = bool(
        (state.get('coherence_anchor') or '').strip()
        or [d for d in (state.get('decision_history') or [])
            if d.get('week') and d['week'] < week_number]
    )
    if not has_history:
        # Nothing to be aware of. Asking anyway invites invention.
        return '', 'this firm has no recorded history yet'

    try:
        text = (client or get_llm_client()).complete(
            system=SYSTEM_PROMPT,
            messages=[{'role': 'user', 'content': build_context(run, week_number)}],
        ).strip()
    except Exception as exc:
        return '', f'could not be generated: {exc}'

    ok, problem = is_usable(text)
    if not ok:
        return '', problem
    return text, ''


def ensure_preamble(week_instance, client=None) -> str:
    """Generate and store the preamble the first time a round is opened.

    Idempotent: once generated (or once tried and stored as blank) the stored
    value stands, so a second page load cannot produce different words for the
    same firm and round.
    """
    if week_instance.preamble_generated_at is not None:
        return week_instance.preamble

    text, problem = generate_preamble(
        week_instance.run, week_instance.week_number, client=client
    )
    week_instance.preamble = text
    week_instance.preamble_problem = problem
    from django.utils import timezone
    week_instance.preamble_generated_at = timezone.now()
    week_instance.save(
        update_fields=['preamble', 'preamble_problem', 'preamble_generated_at', 'updated_at']
    )
    return text
