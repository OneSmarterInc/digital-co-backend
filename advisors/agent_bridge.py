"""Bridges the DigitalCo advisors app to the VIKRAM advisor_agents package.

Maps our AdvisorDefinition, Run state, tier, and week number into the inputs
advisor_agents wants (build_system_prompt, the per-week context, the per-advisor
run context, and the turn cap), so the advisors answer as the real characters
instead of the echo stub. The engine and scoring are untouched.
"""
import importlib

from advisor_agents.personas import ADVISORS
from advisor_agents.prompts import build_system_prompt
from advisor_agents.run_context import advisor_run_context
from advisor_agents.turn_cap import is_capped

_EMPTY_CONTEXT = {"facts": "", "stance": "", "signal": ""}


def agent_key(advisor_key: str) -> str:
    """'diane_brandt' -> 'diane'; advisor_agents keys off the first name."""
    return advisor_key.split("_")[0]


def agent_tier(tier_value: str) -> str:
    """Our Tier value -> advisor_agents tier ('undergrad' or 'grad')."""
    return "undergrad" if "under" in (tier_value or "").lower() else "grad"


# Relationship scores are small accumulating integers. These turn a score into a
# word that completes the advisor package's sentence for that relationship, with
# wording chosen to fit each label (trust, credibility, handling, ally/rival).
_TRUST_WORDS = {"high": "strong", "up": "building", "down": "shaky", "low": "broken"}
_CREDIBILITY_WORDS = {"high": "high", "up": "improving", "down": "shaky", "low": "lost"}
_HANDLING_WORDS = {"high": "a real strength", "up": "positive", "down": "strained", "low": "a real problem"}
_ALLIANCE_WORDS = {"high": "a firm ally", "up": "leaning ally", "down": "leaning rival", "low": "an open rival"}


def _relationship_bucket(score):
    """A small integer score -> one of four bands, or None when nothing has moved."""
    if not isinstance(score, int) or score == 0:
        return None
    if score >= 2:
        return "high"
    if score == 1:
        return "up"
    if score == -1:
        return "down"
    return "low"  # score <= -2


def _set_relationship(mapped, field, score, words):
    bucket = _relationship_bucket(score)
    if bucket:
        mapped[field] = words[bucket]


def map_run_state(state: dict) -> dict:
    """Best-effort projection of our run.state onto advisor_agents run_state.

    Only the fields that map cleanly are filled; the rest stay unset, and the
    context slicer simply omits anything unknown.
    """
    state = state or {}
    through = state.get("through_lines", {}) or {}
    security = through.get("security_ot", {}) or {}
    lockin = through.get("cloud_lockin", {}) or {}
    rights = through.get("data_rights", {}) or {}

    mapped = {}
    anchor = state.get("coherence_anchor")
    if anchor:
        mapped["strategy_statement"] = anchor
    if security.get("posture") is not None:
        mapped["ot_security_investment"] = "actively invested" if security.get("posture") else "neglected"
    lock_state = lockin.get("state")
    if lock_state and lock_state != "unset":
        mapped["lock_in_level"] = lock_state
        mapped["cloud_commitment"] = lock_state
    rights_posture = rights.get("posture")
    if rights_posture and rights_posture != "unset":
        mapped["data_rights_posture"] = rights_posture

    # Relationships: only the four the advisors actually react to, skipping any
    # that are still neutral so the run-context layer stays empty until they move.
    rel = state.get("relationships", {}) or {}
    _set_relationship(mapped, "petrillo_trust", rel.get("petrillo"), _TRUST_WORDS)
    _set_relationship(mapped, "reinhardt_credibility", rel.get("reinhardt"), _CREDIBILITY_WORDS)
    _set_relationship(mapped, "ferraro_handling", rel.get("ferraro"), _HANDLING_WORDS)
    _set_relationship(mapped, "fischer_alliance", rel.get("fischer"), _ALLIANCE_WORDS)
    return mapped


def build_prompt(advisor, tier_value, week_number, run_state, turn_count) -> str:
    """Assemble the in-character system prompt for one advisor turn."""
    key = agent_key(advisor.key)
    # Advisors outside the six-character cast (inactive placeholders) fall back
    # to the app's own base prompt rather than crashing.
    if key not in ADVISORS:
        return advisor.base_system_prompt

    module = importlib.import_module(f"advisor_agents.context_week{week_number}")
    week_context = getattr(module, f"WEEK{week_number}_CONTEXT").get(key) or _EMPTY_CONTEXT
    run_ctx = advisor_run_context(key, map_run_state(run_state))
    return build_system_prompt(
        key,
        agent_tier(tier_value),
        week_context,
        run_context=run_ctx,
        closing=is_capped(turn_count),
    )


def build_group_prompt(advisor, tier_value, week_number, run_state, room_advisor_keys, closing=False) -> str:
    """In-character system prompt for one advisor speaking in a group room.

    Mirrors build_prompt but adds the room layer: `room_advisor_keys` are the
    advisor_agents keys (first names) of the *other* advisors present, so the
    speaker knows who's across the table. `closing` is passed explicitly because
    the group's turn cap counts student messages per session, not this advisor's
    replies (see the group service), so is_capped's per-advisor count doesn't apply.
    """
    key = agent_key(advisor.key)
    if key not in ADVISORS:
        return advisor.base_system_prompt

    module = importlib.import_module(f"advisor_agents.context_week{week_number}")
    week_context = getattr(module, f"WEEK{week_number}_CONTEXT").get(key) or _EMPTY_CONTEXT
    run_ctx = advisor_run_context(key, map_run_state(run_state))
    return build_system_prompt(
        key,
        agent_tier(tier_value),
        week_context,
        run_context=run_ctx,
        closing=closing,
        room_advisors=[k for k in room_advisor_keys if k in ADVISORS],
    )