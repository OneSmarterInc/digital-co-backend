from advisor_agents.director import build_messages_for, pick_next_speaker
from advisor_agents.llm_client import get_llm_client as get_agent_llm_client
from advisor_agents.personas import ADVISORS
from advisor_agents.turn_cap import is_group_capped

from .agent_bridge import agent_key, build_group_prompt, build_prompt
from .llm_client import get_llm_client
from .models import AdvisorDefinition, GroupTurn, Message, MessageRole

# Group room sizing. Fewer than two isn't a room; more than four turns the
# cascade into noise and burns budget. See advisor_agents.director for the
# who-speaks-next mechanic these bound.
MIN_GROUP_ADVISORS = 2
MAX_GROUP_ADVISORS = 4
# A real room has a couple of advisors respond before it circles back to the
# student, not everyone at once. Only the first beat is ever forced (see
# pick_next_speaker) — this is just the ceiling per student message.
CASCADE_CAP = 3


def _strip_self_prefix(reply: str, name: str) -> str:
    """Drop a leading "Name:" the model sometimes echoes onto its own reply.

    In the group room each advisor sees the others' lines formatted as
    "Speaker: content" (see build_messages_for), so the model occasionally
    mimics the pattern and opens its reply with its own name — which then reads
    doubled next to the speaker label the UI already shows. Only a leading
    self-label is removed; a name that appears mid-sentence is left alone."""
    stripped = reply.lstrip()
    for label in (name, name.split()[0]):
        prefix = f"{label}:"
        if stripped[: len(prefix)].lower() == prefix.lower():
            return stripped[len(prefix):].lstrip()
    return reply


class AdvisorService:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client or get_llm_client()

    def respond(self, *, advisor, conversation, run_state: dict, week_context=None, tier) -> str:
        # Turns already spent this week = prior advisor replies in the thread.
        turn_count = conversation.messages.filter(role=MessageRole.ADVISOR).count()
        system = build_prompt(advisor, tier, conversation.week_number, run_state, turn_count)
        history = conversation.as_messages()
        response = self.llm_client.complete(system=system, messages=history)
        Message.objects.create(
            conversation=conversation,
            role=MessageRole.ADVISOR,
            content=response,
        )
        return response


class GroupAdvisorService:
    """Drives one student message through a war-room GroupSession.

    Ported from VIKRAM 2's ask_group view, adapted to DigitalCo: the session's
    active_advisors are AdvisorDefinition keys, which this maps into the
    advisor_agents key space (first names) the director and prompts speak.
    Persists a GroupTurn for the student message and one per advisor reply.

    Uses advisor_agents' own LLM client (positional .complete), which the
    director calls directly — advisors.llm_client's echo stub is keyword-only.
    """

    def __init__(self, llm_client=None):
        self.llm_client = llm_client or get_agent_llm_client()

    def respond(self, *, session, message, run_state: dict, tier) -> dict:
        # Resolve the roster into advisor_agents key space, preserving order and
        # dropping anyone outside the six-character cast.
        by_key = {
            d.key: d
            for d in AdvisorDefinition.objects.filter(key__in=session.active_advisors, active=True)
        }
        def_by_agent = {}
        for key in session.active_advisors:
            advisor = by_key.get(key)
            if not advisor:
                continue
            ak = agent_key(advisor.key)
            if ak in ADVISORS and ak not in def_by_agent:
                def_by_agent[ak] = advisor
        active_agent_keys = list(def_by_agent.keys())

        # Prior transcript, in agent-key space, oldest first.
        transcript = []
        for turn in session.turns.all():
            speaker = "student" if turn.speaker == "student" else agent_key(turn.speaker)
            transcript.append({"speaker": speaker, "content": turn.content})

        turn_count_before = sum(1 for t in transcript if t["speaker"] == "student")
        turn_count_after = turn_count_before + 1
        capped = is_group_capped(turn_count_after)

        transcript.append({"speaker": "student", "content": message})
        GroupTurn.objects.create(session=session, speaker="student", content=message)

        still_active = list(active_agent_keys)
        replies = []
        used_this_beat = []

        # When capped, run exactly one closing beat instead of the full cascade,
        # mirroring the one-on-one turn-cap behavior, then the room is done.
        beat_limit = 1 if capped else CASCADE_CAP
        # Only beat 0 is guaranteed: someone should always respond to the
        # student. Every beat after that is genuine discretion (see
        # pick_next_speaker) so the reply count actually varies.
        guaranteed_beats = 0 if capped else 1

        for beat in range(beat_limit):
            if not still_active:
                break
            candidates = [a for a in still_active if a not in used_this_beat]
            if not candidates:
                break

            if capped:
                speaker = candidates[0]
            else:
                forced = beat < guaranteed_beats
                speaker = pick_next_speaker(self.llm_client, candidates, transcript, beat, forced)
                if not speaker:
                    break

            used_this_beat.append(speaker)
            speaker_def = def_by_agent[speaker]
            room_agent_keys = [a for a in still_active if a != speaker]

            system = build_group_prompt(
                speaker_def, tier, session.week_number, run_state, room_agent_keys, closing=capped,
            )
            messages = build_messages_for(speaker, transcript)

            try:
                reply = self.llm_client.complete(system, messages)
            except Exception:
                continue

            reply = _strip_self_prefix(reply, speaker_def.name)
            GroupTurn.objects.create(session=session, speaker=speaker_def.key, content=reply)
            transcript.append({"speaker": speaker, "content": reply})
            replies.append({
                "advisor_key": speaker_def.key,
                "advisor_name": speaker_def.name,
                "reply": reply,
            })

        return {"replies": replies, "turn_count": turn_count_after, "capped": capped}
