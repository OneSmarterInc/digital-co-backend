"""Chat with an advisor from the terminal to test their responses.

This uses the same advisor package and provider selection the app uses, so it
exercises the real in-character system prompt. In the default echo mode it
returns the deterministic stub; set DIGITALCO_LLM_PROVIDER=anthropic (and
ANTHROPIC_API_KEY) to get real answers from the characters.

Usage:
    python manage.py test_advisor --advisor diane --week 3 --tier grad
    python manage.py test_advisor --advisor marcus --week 9 --message "How should we handle lock-in?"
"""
import importlib

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from advisor_agents.personas import ADVISORS
from advisor_agents.prompts import build_system_prompt
from advisor_agents.turn_cap import is_capped
from advisors.llm_client import get_llm_client

EMPTY_CONTEXT = {"facts": "", "stance": "", "signal": ""}


class Command(BaseCommand):
    help = "Chat with an advisor to test their responses (echo stub or live model)."

    def add_arguments(self, parser):
        parser.add_argument("--advisor", required=True, help="Advisor key or first name, e.g. diane")
        parser.add_argument("--week", type=int, default=1, help="Week 1-14 (default 1)")
        parser.add_argument("--tier", default="grad", choices=["undergrad", "grad"])
        parser.add_argument("--message", help="A single message to send; omit for an interactive session")

    def handle(self, *args, **opts):
        key = opts["advisor"].split("_")[0].lower()
        if key not in ADVISORS:
            raise CommandError(f"Unknown advisor '{opts['advisor']}'. Choices: {', '.join(sorted(ADVISORS))}")
        week = opts["week"]
        if not 1 <= week <= 14:
            raise CommandError("Week must be between 1 and 14.")
        tier = opts["tier"]

        module = importlib.import_module(f"advisor_agents.context_week{week}")
        context = getattr(module, f"WEEK{week}_CONTEXT").get(key) or EMPTY_CONTEXT
        client = get_llm_client()
        provider = getattr(settings, "DIGITALCO_LLM_PROVIDER", "echo")
        name = ADVISORS[key]["name"]

        self.stdout.write(self.style.SUCCESS(f"{name} \u2014 week {week}, {tier} tier, provider: {provider}"))
        if provider == "echo":
            self.stdout.write(
                "  echo mode returns a stub; set DIGITALCO_LLM_PROVIDER=anthropic and ANTHROPIC_API_KEY for real answers"
            )
        self.stdout.write("")

        messages = []

        def ask(text):
            messages.append({"role": "user", "content": text})
            turns_done = sum(1 for m in messages if m["role"] == "assistant")
            system = build_system_prompt(key, tier, context, closing=is_capped(turns_done))
            reply = client.complete(system=system, messages=messages)
            messages.append({"role": "assistant", "content": reply})
            self.stdout.write(self.style.HTTP_INFO(f"{name}: ") + reply)
            self.stdout.write("")

        if opts["message"]:
            ask(opts["message"])
            return

        self.stdout.write("Type a message (blank line or Ctrl-C to quit).\n")
        while True:
            try:
                text = input("you: ").strip()
            except (EOFError, KeyboardInterrupt):
                self.stdout.write("\nDone.")
                break
            if not text:
                self.stdout.write("Done.")
                break
            ask(text)