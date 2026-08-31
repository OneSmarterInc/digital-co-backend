"""What the preamble writer may and may not say.

Two or three sentences sit above an otherwise untouched briefing, naming what
this firm carried in from earlier rounds. The briefing itself is unchanged for
every firm — the preamble is the only firm-specific text on the page.

The same withholding discipline as the feedback channel: the model is never
shown scores, traps or rubrics, so it cannot leak them. On top of that it must
not preview the decision the round is about to ask for, or the round stops
being a decision.
"""
import re

SYSTEM_PROMPT = """You write a short opening to a company briefing.

The reader is a student team running an IT organisation across fourteen rounds.
They are about to read this round's briefing. Your job is to remind them, in
their own history's terms, what they are carrying into it — a commitment they
made, a position they took, a cost they accepted.

Write two or three sentences, and no more than 65 words in total. Length is a hard
limit, not a guideline — an opening that runs long is discarded unread, so cut rather
than qualify. No heading, no salutation, no list. Present tense,
second person plural ("you"), the voice of a colleague who was in the room.

Refer only to what they actually did. If their history is thin, say less rather
than inventing continuity.

Never mention scores, points, grades, marks, rubrics, dimensions, strategic
judgment, execution consequence, coherence, deliverable quality, traps, gates,
rankings or other teams. That machinery does not exist to the reader.

Never say what they should decide this round, name the options in front of them,
or hint at what is coming. You are describing where they stand, not advising.

Never praise or criticise. State what they committed to and what it costs them
now.

Write the ERP programme as "S/4", with the slash, every time. It is written that
way everywhere else the team reads, and "S4" reads as a different system."""

# Same family as the feedback guard: anything that names the scoring machinery,
# and anything that turns a reminder into advice.
PROHIBITED = (
    'strategic judgment', 'execution consequence', 'coherence', 'deliverable quality',
    'score', 'scores', 'scored', 'scoring', 'points', 'grade', 'graded', 'grading',
    'mark', 'marks', 'rubric', 'dimension', 'dimensions', 'weight', 'weighted',
    'trap', 'traps', 'gate', 'gates', 'penalty', 'penalised', 'penalized',
    'rank', 'ranked', 'ranking', 'standings', 'leaderboard',
    'other teams', 'other firms', 'your peers', 'compared to',
)

ADVISORY = (
    'you should', 'we recommend', 'the right choice', 'the best option',
    'you must choose', 'i suggest', 'my advice',
)

MIN_WORDS = 15
MAX_WORDS = 90


# Same allowance as the feedback guard: stage gates are the governance mechanism
# the course asks firms to build, not the scoring machinery.
ALLOWED_PHRASES = ('stage gate', 'stage gates', 'gated governance', 'gated')


def violations(text: str) -> list[str]:
    """Matched on word boundaries, so ordinary words that merely contain a
    prohibited one — mitigate, upgrade, benchmarks — are not rejected."""
    lowered = ' '.join((text or '').lower().split())
    for phrase in ALLOWED_PHRASES:
        lowered = lowered.replace(phrase, ' ')
    return [term for term in PROHIBITED if re.search(rf'\b{re.escape(term)}\b', lowered)]


def is_usable(text: str) -> tuple[bool, str]:
    """(ok, problem). A preamble that breaks a rule is dropped, not shown.

    Nothing here is recoverable by editing, because no human is in this loop —
    the preamble is generated when the round opens and read immediately.
    """
    stripped = (text or '').strip()
    if not stripped:
        return False, 'no preamble was produced'

    words = len(stripped.split())
    if words < MIN_WORDS:
        return False, 'too short to say anything'
    if words > MAX_WORDS:
        return False, 'too long for an opening'

    found = violations(stripped)
    if found:
        return False, f'names the scoring machinery: {", ".join(sorted(set(found)))}'

    lowered = stripped.lower()
    advisory = [term for term in ADVISORY if term in lowered]
    if advisory:
        return False, f'tells them what to decide: {", ".join(sorted(set(advisory)))}'

    return True, ''
