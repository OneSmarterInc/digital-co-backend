"""
Spec: "Put a hard cap on the number of turns a student gets with an
advisor in a week... when the cap is reached, the advisor should close
out gracefully and in character rather than erroring."
"""

DEFAULT_TURN_CAP = 6

# Group room only. Separate from DEFAULT_TURN_CAP (which counts a student's
# turns with ONE advisor): a group round produces more total content per
# student message than a one-on-one turn, so the cap is lower and counts
# student messages in the group session, not individual advisor replies.
GROUP_TURN_CAP = 8

CLOSING_INSTRUCTION = (
    "This is your last exchange with this team for this week's consultation, "
    "the turn budget is spent. Close out warmly and in character: give your "
    "one clearest remaining thought, and send them back to the decision. "
    "Don't apologize for the cap or break character to mention it."
)
# Reused as-is for the group room's closing beat too: it's already generic
# enough (no one-on-one-specific language) to fit both.


def is_capped(turn_count, cap=DEFAULT_TURN_CAP):
    return turn_count >= cap


def is_group_capped(turn_count, cap=GROUP_TURN_CAP):
    return turn_count >= cap
