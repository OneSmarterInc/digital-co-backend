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

import re

SYSTEM_PROMPT = """You write short feedback to a student team running the IT organisation of a manufacturer called DigitalCo. They are the CIO — one chair, the whole team in it — and they commit one decision per week for fourteen weeks.

You are writing about their thinking, never about how it was measured.

Structure, exactly three short paragraphs, 120-180 words in total:

**What held.** One thing their submission did well, quoted or closely paraphrased so it is unmistakably about them. Not encouragement — you are telling them which instinct to keep.

**What was thin.** One thing that weakens the position, put as the question a board or an executive would ask. Not a correction; a gap made visible.

**What to carry.** One sentence connecting this week to the next, without naming what next week contains. From week 2 onward, this is where a prior commitment gets referenced.

Absolute rules:
A firm's own deliverable is their account of what they did, not evidence that it is
true. Where the record contradicts that account — most often a firm describing a
change of direction as continuity — the record is what happened. Name the change in
plain words rather than repeating their framing back to them. Never congratulate a
firm for holding a line the record shows they left.

- Never mention scores, points, marks, grades, dimensions, rubrics, weights, traps or gates. Never use the words "strategic judgment", "execution consequence", "coherence" or "deliverable quality". The student must not be able to infer how they were measured.
- Never tell them what to decide, and never hint at what is coming. "You did not say how you would know if this was working" is right. "You should have funded the assessment" is wrong.
- Never mention other teams, standings or rankings.
- Never write generic praise or generic criticism. Every sentence must point at something they actually wrote.
- Address them as the firm ("you"), in the register you would use with a senior professional. Direct and useful, not warm, not scolding.

Return only the three paragraphs. Do not label them, do not add a heading, do not add anything else."""


# Checked after generation. A hit means the model drifted onto the rubric, and
# the feedback is discarded rather than shown.
# Matched on word boundaries, so every inflection that matters must be listed
# rather than relied on as a substring. That is the trade for not rejecting
# "mitigate" and "benchmarks".
PROHIBITED = (
    'strategic judgment', 'execution consequence', 'deliverable quality',
    'coherence', 'rubric', 'rubrics', 'dimension', 'dimensions',
    'score', 'scores', 'scored', 'scoring',
    # Singular 'point', 'mark' and 'weight' are deliberately absent: "the point
    # of the plan", "a mark of seriousness" and "the weight of the argument" are
    # ordinary English, and blocking them costs more than the leak they guard.
    # The scoring senses are the plurals and the participles.
    'points', 'marks',
    'grade', 'grades', 'graded', 'grading',
    'weighting', 'weighted',
    'trap', 'traps', 'gate', 'gates',
    'penalty', 'penalties', 'penalise', 'penalised', 'penalize', 'penalized',
    'rank', 'ranks', 'ranked', 'ranking', 'rankings',
    'standings', 'leaderboard',
    'other teams', 'other firms', 'compared to',
)

MIN_WORDS = 60
MAX_WORDS = 260


# Governance vocabulary that happens to contain a prohibited word. "Stage
# gates" is the mechanism Week 2 asks firms to build and the decision form names
# it, so feedback about governance says it constantly. Stripped before checking
# rather than removed from PROHIBITED, because "the gate closed" is still a leak.
ALLOWED_PHRASES = ('stage gate', 'stage gates', 'gated governance', 'gated')


def violations(text: str) -> list[str]:
    """Prohibited terms present in generated feedback, if any.

    Matched on word boundaries. Substring matching rejected nineteen ordinary
    words — mitigate, investigate, upgrade, delegate, benchmarks, endpoints,
    underscore — which is why drafts failed intermittently and for no visible
    reason: perfectly good feedback was discarded for containing "mitigate".
    """
    lowered = (text or '').lower()
    for phrase in ALLOWED_PHRASES:
        lowered = lowered.replace(phrase, ' ')
    return [term for term in PROHIBITED if re.search(rf'\b{re.escape(term)}\b', lowered)]


def is_usable(text: str) -> tuple[bool, str]:
    """Whether this is safe and substantial enough to show a student."""
    if not text or not text.strip():
        return False, 'empty'
    found = violations(text)
    if found:
        # Deliberately does not list the offending words. This string is shown
        # in the grading pane, and naming them reintroduced the vocabulary the
        # check exists to keep out — a validator line reading "mentions the
        # scoring: weighted, gate" puts "gate" on the instructor's screen.
        # The words are available to a caller that wants them via violations().
        return False, 'the draft named the scoring, so it was discarded'
    words = len(text.split())
    if words < MIN_WORDS:
        return False, f'too short ({words} words) to be about anything specific'
    if words > MAX_WORDS:
        return False, f'too long ({words} words)'
    return True, ''
