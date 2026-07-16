from .bios import BIOS
from .personas import ADVISORS, GUARDRAILS, TIER_MODIFIERS
from .turn_cap import CLOSING_INSTRUCTION


def build_system_prompt(advisor_key, tier, week_context, run_context=None, closing=False, room_advisors=None):
    advisor = ADVISORS[advisor_key]
    bio = BIOS.get(advisor_key)

    persona = (
        f"You are {advisor['name']}, {advisor['role']} on DigitalCo's advisory bench. "
        f"You own {advisor['lane']}. Your voice is {advisor['voice']}. "
        f"What you see that the others miss: {advisor['sees']}. "
        f"Your bias: {advisor['bias']}. If a team lets you run the room unchecked, "
        f"the failure mode is that {advisor['captured_failure']}."
    )

    personal_life = ""
    if bio:
        personal_life = (
            "Your life outside this lane, fixed and consistent every time you're asked: "
            f"{bio['background']} {bio['personality_beyond_lane']} {bio['family_and_life']} "
            "You may bring this up naturally, an aside, a comparison, a direct answer when a "
            "student asks about you, when it genuinely fits. Don't let it take over; the "
            "team's business problem stays the point."
        )

    tier_block = TIER_MODIFIERS[tier]

    week_block = (
        f"This week's facts: {week_context['facts']}\n"
        f"Your stance this week: {week_context['stance']}\n"
        f"Your signal: {week_context['signal']}"
    )
    if week_context.get("misdirection"):
        week_block += f"\nYour misdirection: {week_context['misdirection']}"

    layers = [persona]
    if personal_life:
        layers.append(personal_life)
    layers.append(tier_block)
    layers.append(week_block)
    if run_context:
        layers.append("What you know about this team's choices so far: " + run_context)

    # Group room only (the group service). Absent for the ordinary one-advisor
    # call site, so this never changes behavior there. Friction hooks are derived
    # straight from each advisor's own established `bias` field, nothing new invented,
    # consistent with GUARDRAILS' "invent nothing beyond your own established personal life."
    if room_advisors:
        room_lines = []
        for key in room_advisors:
            other = ADVISORS[key]
            room_lines.append(f"- {other['name']}, {other['role']}: {other['lane']}. Tends to {other['bias']}.")
        layers.append(
            "You are not alone with the team right now. Sitting in the room with you:\n"
            + "\n".join(room_lines)
            + "\n\nThis is a real conversation between advisors, not a queue of one-on-one "
            "answers. Push back on each other, agree, build on someone's point, or ask one of "
            "them a direct question, the way you actually would sitting across the table from "
            "a colleague whose blind spots you know. Not every message is addressed to the team "
            "alone, and you don't need to speak every beat, only when you'd genuinely have "
            "something to say. None of this dims who you are: your own voice and your own bias "
            "stay exactly as strong as they'd be one-on-one, if anything a room full of people "
            "who know your angle already is more you, not less."
        )

    layers.append(GUARDRAILS)
    if closing:
        layers.append(CLOSING_INSTRUCTION)

    return "\n\n".join(layers)
