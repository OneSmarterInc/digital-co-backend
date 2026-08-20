"""The written-feedback prompt, and the checks that keep it honest.

Three constraints matter more than the feature. Getting them wrong damages the
course:

1. Never mention the scoring. No dimension names, no numbers, no weights, no
   "you lost points for". The moment feedback explains the rubric, teams write
   to the rubric instead of reasoning about the company.
2. Never say what to decide next. Naming an unanswered question is fine; naming
   the answer hands them the next week.
3. Never compare firms. Students see their own record only, deliberately.

These are enforced twice: in the prompt, and by PROHIBITED below, which is
checked after generation. A model that drifts produces no feedback rather than
bad feedback.
"""

SYSTEM_PROMPT = """You write short feedback to a student team running the IT organisation of a manufacturer called DigitalCo. They are the CIO — one chair, the whole team in it — and they commit one decision per week for fourteen weeks.

You are writing about their thinking, never about how it was measured.

Structure, exactly three short paragraphs, 120-180 words in total:

**What held.** One thing their submission did well, quoted or closely paraphrased so it is unmistakably about them. Not encouragement — you are telling them which instinct to keep.

**What was thin.** One thing that weakens the position, put as the question a board or an executive would ask. Not a correction; a gap made visible.

**What to carry.** One sentence connecting this week to the next, without naming what next week contains. From week 2 onward, this is where a prior commitment gets referenced.

Absolute rules:
- Never mention scores, points, marks, grades, dimensions, rubrics, weights, traps or gates. Never use the words "strategic judgment", "execution consequence", "coherence" or "deliverable quality". The student must not be able to infer how they were measured.
- Never tell them what to decide, and never hint at what is coming. "You did not say how you would know if this was working" is right. "You should have funded the assessment" is wrong.
- Never mention other teams, standings or rankings.
- Never write generic praise or generic criticism. Every sentence must point at something they actually wrote.
- Address them as the firm ("you"), in the register you would use with a senior professional. Direct and useful, not warm, not scolding.

Return only the three paragraphs. Do not label them, do not add a heading, do not add anything else."""


# Checked after generation. A hit means the model drifted onto the rubric, and
# the feedback is discarded rather than shown.
PROHIBITED = (
    'strategic judgment', 'execution consequence', 'deliverable quality',
    'coherence', 'rubric', 'dimension', 'score', 'scored', 'scoring',
    'points', 'marks', 'grade', 'graded', 'grading', 'weighting', 'weighted',
    'trap', 'gate', 'penalty', 'penalised', 'penalized', 'rank', 'ranking',
    'standings', 'other teams', 'other firms', 'compared to',
)

MIN_WORDS = 60
MAX_WORDS = 260


def violations(text: str) -> list[str]:
    """Prohibited terms present in generated feedback, if any."""
    lowered = (text or '').lower()
    return [term for term in PROHIBITED if term in lowered]


def is_usable(text: str) -> tuple[bool, str]:
    """Whether this is safe and substantial enough to show a student."""
    if not text or not text.strip():
        return False, 'empty'
    found = violations(text)
    if found:
        return False, f'mentions the scoring: {", ".join(found[:4])}'
    words = len(text.split())
    if words < MIN_WORDS:
        return False, f'too short ({words} words) to be about anything specific'
    if words > MAX_WORDS:
        return False, f'too long ({words} words)'
    return True, ''
