import os


class EchoClient:
    def complete(self, system, messages):
        last = messages[-1]["content"] if messages else ""
        return f"[echo] {last}"


class AnthropicClient:
    def __init__(self, model):
        import anthropic

        self._client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self._model = model

    def complete(self, system, messages):
        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system,
            messages=messages,
        )
        parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
        return "".join(parts).strip()


def get_llm_client():
    provider = os.environ.get("DIGITALCO_LLM_PROVIDER", "echo")
    if provider == "echo":
        return EchoClient()
    if provider == "anthropic":
        model = os.environ.get("DIGITALCO_LLM_MODEL", "claude-sonnet-5")
        return AnthropicClient(model)
    raise ValueError(f"unknown DIGITALCO_LLM_PROVIDER: {provider}")
