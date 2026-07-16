"""Text-to-speech voice IDs for each advisor.

One entry per advisor; the keys match advisor_agents.personas.ADVISORS. The
voice integration reads from here to speak an advisor's reply, so this is the
single place to update when a voice ID changes.
"""
VOICE_IDS = {
    "diane": "rtwSxGB9IQqitcnVusuz",   # Diane Brandt  — Executive Coach
    "marcus": "aNiLrUVuVW79oXlgpTf5",  # Marcus Webb   — numbers and execution
    "renata": "nwioBJrJOPDl3lkmWiaU",  # Renata Voss   — OT / factory floor
    "daniel": "B7OLPfeetMDFZVdgfcgv",  # Daniel Stern
    "frank": "2kq2kyIa294w3Ydf8MEH",   # Frank Delgado — lock-in and cloud economics
    "zoe": "ifYlFrVfqQcaILzZ3gs5",     # Zoe Park
}


def get_voice_id(advisor_key: str):
    """Voice ID for an advisor (accepts 'diane' or 'diane_brandt'), or None."""
    return VOICE_IDS.get(advisor_key.split("_")[0].lower())


def missing_voices():
    """Advisor keys that still need a voice ID assigned."""
    return [key for key, value in VOICE_IDS.items() if not value]