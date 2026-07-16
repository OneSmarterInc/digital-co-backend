"""
Local test harness for tuning an advisor's persona before it's wired into
the Django app. Run: python -m advisors.console diane grad
"""
import sys

from .context_week1 import WEEK1_CONTEXT
from .llm_client import get_llm_client
from .prompts import build_system_prompt


def main():
    advisor_key = sys.argv[1] if len(sys.argv) > 1 else "diane"
    tier = sys.argv[2] if len(sys.argv) > 2 else "grad"

    system = build_system_prompt(advisor_key, tier, WEEK1_CONTEXT[advisor_key])
    client = get_llm_client()
    messages = []

    print(f"Talking to {advisor_key} ({tier} tier). Ctrl+C to quit.\n")
    while True:
        try:
            user_input = input("you> ")
        except (EOFError, KeyboardInterrupt):
            break
        messages.append({"role": "user", "content": user_input})
        reply = client.complete(system, messages)
        messages.append({"role": "assistant", "content": reply})
        print(f"{advisor_key}> {reply}\n")


if __name__ == "__main__":
    main()
