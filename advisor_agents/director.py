"""
Group room director: picks who speaks next among the active advisors, or
"none". Only beat 0 (the first reply to a new student message) is ever
forced — every beat after that is genuine per-moment discretion, judged
honestly, not a guaranteed floor. A forced floor past beat 0 was tried and
reads as fake: a rigid, always-2-or-3-replies rhythm, the same problem as
never continuing at all, just in the other direction.

No structured/forced tool-use is available here: advisors.llm_client's
.complete(system, messages) is a plain-text interface (see llm_client.py).
So the director asks for a single-word answer and parses it, matching
against the known advisor keys and, as a fallback, their display names, in
case the model answers with the name instead of the internal key.
"""

from .personas import ADVISORS


def _speaker_label(speaker):
    if speaker == "student":
        return "Student"
    advisor = ADVISORS.get(speaker)
    return advisor["name"] if advisor else speaker


def _advisor_roster_line(key):
    a = ADVISORS[key]
    return f"{key}: {a['name']}, {a['role']}. Tends to {a['bias']}."


def _parse_speaker(raw, active_advisors):
    text = (raw or "").strip().lower()
    if not text:
        return None
    for key in active_advisors:
        if key in text:
            return key
    for key in active_advisors:
        name = ADVISORS[key]["name"].lower()
        if name in text or name.split()[0] in text:
            return key
    return None


def build_messages_for(speaker, transcript):
    """
    Formats the shared transcript from ONE advisor's point of view: their own
    past lines stay role "assistant" (unprefixed, natural); everyone else's
    lines (the student's and every other advisor's) become role "user",
    prefixed with who said it, so the model has a clear "that's someone
    else" signal. The Anthropic Messages API only has user/assistant roles
    and allows consecutive user-role messages, so this needs no invented
    shape, just like the JS version this was ported from.
    """
    messages = []
    for entry in transcript:
        if entry["speaker"] == speaker:
            messages.append({"role": "assistant", "content": entry["content"]})
        else:
            label = _speaker_label(entry["speaker"])
            messages.append({"role": "user", "content": f"{label}: {entry['content']}"})
    return messages


def pick_next_speaker(client, active_advisors, transcript, beat_index, forced):
    """
    active_advisors: list of advisor keys still eligible to speak this beat.
    transcript: list of {"speaker": "student"|advisor_key, "content": str},
      oldest first.
    beat_index: 0 for the first reply to the student's new message, 1+ for
      each reply after that within the same round.
    forced: True only for beat 0 — someone should always respond to the
      student. False every beat after, real discretion, "none" allowed.
    Returns an advisor key, or None if nobody should speak (only possible
    when forced=False).
    """
    roster = "\n".join(_advisor_roster_line(k) for k in active_advisors)
    recent = transcript[-16:]
    transcript_text = "\n".join(f"{_speaker_label(t['speaker'])}: {t['content']}" for t in recent)

    if beat_index == 0:
        instruction = (
            "The student just said something new. Pick whoever in the room would "
            "naturally jump in first."
        )
    else:
        instruction = (
            "Judge this specific moment honestly, the way a real room of advisors actually "
            "works: sometimes one reply is plenty and the conversation naturally pauses "
            "there, sometimes someone can't help reacting to what was just said, "
            "occasionally a third person jumps in too, but that is the rare case, not the "
            "default. Only pick a name if a specific advisor here would genuinely, "
            "naturally have something to say about what the LAST person just said, "
            "reacting to them, not answering the student again from scratch."
        )

    if forced:
        tail = f" Reply with exactly one word, one of these keys: {', '.join(active_advisors)}."
    else:
        tail = (
            " Reply with exactly one word: one of these keys "
            f"({', '.join(active_advisors)}), or the single word none."
        )

    prompt = (
        "You're directing a real conversation among a CIO and their business advisors, "
        "people who actually talk to each other, not a queue of one-on-one answers.\n\n"
        f"Advisors in the room:\n{roster}\n\n"
        f"Recent conversation:\n{transcript_text}\n\n"
        f"{instruction}{tail}"
    )
    system = "You choose who speaks next in a room. Answer with exactly one word, nothing else."

    try:
        raw = client.complete(system, [{"role": "user", "content": prompt}])
    except Exception:
        return active_advisors[0] if forced else None

    speaker = _parse_speaker(raw, active_advisors)
    if speaker:
        return speaker
    return active_advisors[0] if forced else None
