"""An engine proposal for deliverable quality.

The fourth dimension had no engine behind it: no week module ever emitted a
score, so the modal showed `engine: 0` beside it exactly as it does for the
three the engine drives — which reads as "the engine assessed the writing and
thought it worthless" when in fact it never looked. Across two sections that is
also thirty-odd judgement calls a week typed by hand.

This rides the same model call the written feedback uses: same input, one extra
output.

The constraint that matters more than the score
-----------------------------------------------
**Judge form, not agreement.** A well-argued case for a decision that scores
badly on strategic judgment must still be able to score well here. If the model
marks writing down because it disagrees with the conclusion, this dimension
collapses into a second copy of strategic judgment and four dimensions become
three. That is the failure mode to watch for in the first weeks of live use,
which is why every proposal is logged with its reasoning.
"""
import re

from advisors.llm_client import get_llm_client

# Narrower than the other dimensions on purpose: prose quality varies less than
# strategic judgment, and writing should not swing the standings. Negatives are
# reserved for genuinely thin work, not merely weaker work.
MIN_SCORE = -1
MAX_SCORE = 3

# The rubric weights these rounds more heavily on the artifact itself.
HEAVY_WEEKS = (1, 8, 13, 14)

UNDERGRAD_STANDARD = """This is an undergraduate team. Judge whether they selected the
named frameworks appropriate to the question and applied them correctly, and whether the
document is organised so a reader can follow the argument. Visible structure is a strength
at this level, not a weakness."""

GRADUATE_STANDARD = """This is a graduate team. Judge whether they reason to their
conclusions without leaning on framework scaffolding, in language an executive would
actually want to receive. Naming a framework instead of doing its thinking is a weakness
at this level."""

SYSTEM_PROMPT = """You assess how well a written business deliverable is built.

You are scoring the ARTIFACT, not the decision it argues for. This is the whole job:

- A well-argued case for a decision you think is wrong scores WELL.
- A poorly-argued case for a decision you think is right scores BADLY.
- You have no opinion on the decision. You never had one.

Judge only these:
1. Does the reasoning name its numbers — which figures it relied on, which it set aside?
2. Does it say what was given up? A deliverable that reads as all upside is a brochure.
3. Does it hold together — do the stated choices and the written reasoning agree?
4. Is it specific to this company and this week, or could it be pasted into any deck?
5. Does it meet the standard for its level, described below?

Score on this scale:
  3  Exceptional for the level. Every claim carries its evidence and its cost.
  2  Strong. Reasons well, names trade-offs, specific to the situation.
  1  Competent. Makes its case, but leaves reasoning or costs implicit.
  0  Adequate but generic. Could have been written about another company.
 -1  Thin. Assertion without reasoning, or internally contradictory.

Reply with exactly two lines and nothing else:
SCORE: <integer from -1 to 3>
WHY: <one sentence, about how the document is built, never about the decision>"""


def _standard(tier) -> str:
    return GRADUATE_STANDARD if str(tier).upper().startswith('GRAD') else UNDERGRAD_STANDARD


def build_context(score_record) -> str:
    """The written material and the choices, with no scoring information."""
    from .services import _choices, _clip, _written

    instance = score_record.week_instance
    submission = instance.submission
    tier = instance.run.team.cohort.tier

    parts = [_standard(tier), f'This is round {instance.week_number} of fourteen.']

    if submission:
        choices = _choices(submission.structured_payload)
        if choices:
            parts.append(
                'The calls they committed to. Judge only whether the writing is '
                'consistent with them — never whether they are the right calls:\n'
                + '\n'.join(choices)
            )
        written = _written(submission.structured_payload)
        if written:
            parts.append('What they wrote:\n' + '\n\n'.join(written))
        if submission.deliverable_text:
            parts.append('Their deliverable:\n' + _clip(submission.deliverable_text, 4000))

    parts.append('Score the deliverable.')
    return '\n\n'.join(parts)


def parse(text: str):
    """(score, why, problem). Score is None when nothing usable came back."""
    if not text:
        return None, '', 'no response'
    score_match = re.search(r'SCORE:\s*(-?\d+)', text, re.I)
    if not score_match:
        return None, '', 'no score in the response'
    score = int(score_match.group(1))
    if not (MIN_SCORE <= score <= MAX_SCORE):
        return None, '', f'score {score} outside {MIN_SCORE}..{MAX_SCORE}'
    why_match = re.search(r'WHY:\s*(.+)', text, re.I | re.S)
    return score, (why_match.group(1).strip() if why_match else ''), ''


def propose_quality(score_record, client=None) -> tuple[int, str, str]:
    """(score, why, problem). Score is 0 when nothing usable could be produced.

    Never raises, and never blocks a grade: a failed call proposes 0 and the
    instructor types a number exactly as they do today.
    """
    submission = score_record.week_instance.submission
    if not submission:
        return 0, '', 'nothing was submitted for this round'
    if not (submission.deliverable_text or '').strip():
        return 0, '', 'no written deliverable to assess'

    try:
        raw = (client or get_llm_client()).complete(
            system=SYSTEM_PROMPT,
            messages=[{'role': 'user', 'content': build_context(score_record)}],
        )
    except Exception as exc:
        return 0, '', f'could not be generated: {exc}'

    score, why, problem = parse(raw.strip())
    if score is None:
        return 0, '', problem
    return score, why, ''
