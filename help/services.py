"""The starved help channel.

One turn in, one turn out. The conversation is not persisted: this is a help
desk, not an advisor, and keeping transcripts would create a second place where
scenario content could accumulate.
"""

from advisors.llm_client import get_llm_client

from .prompts import HELP_SYSTEM_PROMPT

MAX_QUESTION_CHARS = 600


class HelpService:
    def __init__(self, client=None):
        self.client = client or get_llm_client()

    def answer(self, question: str) -> str:
        question = (question or '').strip()[:MAX_QUESTION_CHARS]
        if not question:
            return ''
        return self.client.complete(
            system=HELP_SYSTEM_PROMPT,
            messages=[{'role': 'user', 'content': question}],
        ).strip()
