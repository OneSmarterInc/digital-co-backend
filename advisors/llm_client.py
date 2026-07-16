from dataclasses import dataclass
from typing import Protocol

from django.conf import settings


class LLMClient(Protocol):
    def complete(self, *, system: str, messages: list[dict[str, str]]) -> str:
        ...


@dataclass
class EchoLLMClient:
    prefix: str = 'Stub advisor response'

    def complete(self, *, system: str, messages: list[dict[str, str]]) -> str:
        last_user = next((m['content'] for m in reversed(messages) if m['role'] == 'user'), '')
        return f'{self.prefix}: {last_user}'.strip()


def get_llm_client() -> LLMClient:
    provider = getattr(settings, 'DIGITALCO_LLM_PROVIDER', 'echo')
    if provider == 'echo':
        return EchoLLMClient()
    if provider == 'anthropic':
        # The real characters, powered by the VIKRAM advisor package's client.
        import os

        from advisor_agents.llm_client import AnthropicClient

        return AnthropicClient(os.environ.get('DIGITALCO_LLM_MODEL', 'claude-sonnet-5'))
    raise ValueError(f'Unsupported LLM provider: {provider}')
