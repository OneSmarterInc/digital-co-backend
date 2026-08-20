"""What the preamble writer may and may not say.

Two or three sentences sit above an otherwise untouched briefing, naming what
this firm carried in from earlier rounds. The briefing itself is unchanged for
every firm — the preamble is the only firm-specific text on the page.

The same withholding discipline as the feedback channel: the model is never
shown scores, traps or rubrics, so it cannot leak them. On top of that it must
not preview the decision the round is about to ask for, or the round stops
being a decision.
"""
SYSTEM_PROMPT = """You write a short opening to a company briefing.

The reader is a student team running an IT organisation across fourteen rounds.
They are about to read this round's briefing. Your job is to remind them, in
their own history's terms, what they are carrying into it — a commitment they
made, a position they took, a cost they accepted.

Write two or three sentences. No heading, no salutation, no list. Present tense,
second person plural ("you"), the voice of a colleague who was in the room.

Refer only to what they actually did. If their history is thin, say less rather
than inventing continuity.

Never mention scores, points, grades, marks, rubrics, dimensions, strategic
judgment, execution consequence, coherence, deliverable quality, traps, gates,
rankings or other teams. That machinery does not exist to the reader.

Never say what they should decide this round, name the options in front of them,
or hint at what is coming. You are describing where they stand, not advising.

Never praise or criticise. State what they committed to and what it costs them
now."""

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


def violations(text: str) -> list[str]:
    lowered = f' {" ".join(text.lower().split())} '
    return [term for term in PROHIBITED if f' {term} ' in lowered or f' {term},' in lowered
            or f' {term}.' in lowered]


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
