"""Generating written feedback for a graded round.

The model is given what the firm wrote — this round, and their prior rounds for
continuity — and nothing about how any of it was scored. It cannot leak a rubric
it was never shown, which is the same discipline the help channel uses.

It also receives nothing from a later week, so it cannot hint at what is coming.
"""
from advisors.llm_client import get_llm_client

from .prompts import SYSTEM_PROMPT, is_usable

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

    parts.append('Write their feedback.')
    return '\n\n'.join(parts)


def generate_feedback(score_record, client=None) -> tuple[str, str]:
    """(feedback, problem). Feedback is '' when it could not be produced safely.

    Never raises: a grade must save whether or not feedback could be written.
    """
    submission = score_record.week_instance.submission
    if not submission:
        return '', 'nothing was submitted for this round'

    try:
        text = (client or get_llm_client()).complete(
            system=SYSTEM_PROMPT,
            messages=[{'role': 'user', 'content': build_context(score_record)}],
        ).strip()
    except Exception as exc:
        return '', f'could not be generated: {exc}'

    ok, problem = is_usable(text)
    if not ok:
        # Worse than nothing: generic or rubric-leaking feedback teaches the
        # wrong lesson, so it is discarded rather than shown.
        return '', problem
    return text, ''
