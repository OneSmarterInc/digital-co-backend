# DigitalCo advisors

The six advisor characters (Diane, Marcus, Renata, Daniel, Frank, Zoe) as a
self-contained Python package. No Django dependency, no database, no
network calls except to the LLM provider. Drop this folder into your
Django project as an app or a plain package and call into it from your
views; everything about state (which team, which week, how many turns
they've used) is yours to own.

## Module map

| File | What it is |
|---|---|
| `personas.py` | The six advisors' professional cores: lane, voice, bias, what they see, their failure mode when unchecked. Also the fixed `GUARDRAILS` text and the `TIER_MODIFIERS` (undergrad MISX vs. graduate MIS). |
| `bios.py` | Their personal lives, backstory, family, the thing outside the lane. Feeds the system prompt so they can bring up their own life naturally, never invented on the fly, always the same fixed facts. |
| `context_week1.py` ... `context_week14.py` | One file per week. Each has a `WEEKN_CONTEXT` dict with a `facts` / `stance` / `signal` / `misdirection` entry per advisor, pulled from that week's script. Some advisors have no material in a given week (the script just doesn't feature them); those entries are empty strings, not invented. |
| `prompts.py` | `build_system_prompt()` — assembles one advisor's full system prompt for one turn: persona + personal life + tier + week context + run context (optional) + guardrails + closing instruction (optional). This is the one function your views actually call. |
| `run_state.py` | `new_run_state()` — a plain dict template for the facts that accumulate across the arc (strategy statement, OT investment, lock-in level, data-rights posture, etc.), the "propagates forward" state each week's script names. Not persisted here; you decide how to store it (JSONField, model columns, whatever fits your schema). |
| `run_context.py` | `advisor_run_context(advisor_key, run_state)` — slices a run_state dict down to what one advisor's lane actually cares about (Frank sees lock-in and vendor terms, Renata sees OT posture, etc.) and phrases it as a string. Returns `""` if nothing relevant has happened yet. |
| `turn_cap.py` | `DEFAULT_TURN_CAP` and `is_capped(turn_count)`. You track the turn count per team/week/advisor; when capped, pass `closing=True` into `build_system_prompt()` so the advisor wraps up in character instead of the conversation just erroring out. |
| `llm_client.py` | `get_llm_client()` — provider-agnostic. Reads `DIGITALCO_LLM_PROVIDER` from the environment: `echo` (default, no API calls, just echoes input, good for wiring/tests) or `anthropic` (real calls, needs `ANTHROPIC_API_KEY`, reads `DIGITALCO_LLM_MODEL` or defaults to `claude-sonnet-5`). Everything routes through `.complete(system, messages)` so swapping providers never touches calling code. |
| `console.py` | A command-line harness for tuning outside Django: `py -m advisors.console diane grad`. Not meant to ship in the product. |
| `images/` | The twelve portraits, one `<Name>_eyes_open.png` / `<Name>_eyes_closed.png` pair per advisor, matching the render style and shot list in `digitalco-advisor-cast-bible.md`. |

## Setup

```
pip install anthropic
```

Environment variables:
- `DIGITALCO_LLM_PROVIDER` — `echo` or `anthropic`. Leave unset (defaults to `echo`) to wire things up with zero API cost before flipping it on.
- `ANTHROPIC_API_KEY` — required once you switch to `anthropic`.
- `DIGITALCO_LLM_MODEL` — optional, defaults to `claude-sonnet-5`.

## Calling it from a Django view

```python
from advisors.prompts import build_system_prompt
from advisors.llm_client import get_llm_client
from advisors.run_context import advisor_run_context
from advisors.turn_cap import is_capped
import importlib

def ask_advisor(advisor_key, tier, week_number, run_state, turn_count, conversation, user_message):
    week_ctx = importlib.import_module(f"advisors.context_week{week_number}")
    context = getattr(week_ctx, f"WEEK{week_number}_CONTEXT")[advisor_key]

    system = build_system_prompt(
        advisor_key,
        tier,                                   # "undergrad" or "grad"
        context,
        run_context=advisor_run_context(advisor_key, run_state),
        closing=is_capped(turn_count),
    )

    client = get_llm_client()
    messages = conversation + [{"role": "user", "content": user_message}]
    return client.complete(system, messages)
```

`conversation` is just the running list of `{"role": ..., "content": ...}` turns for this team-advisor-week thread, however you're persisting it (a model, a session, a JSONField, your call).

## What this package does NOT include, by design

- **Django models.** No `Team`, `WeekSubmission`, `AdvisorTurn`, or migrations. `run_state` and turn counts are plain data; wire them into your own schema.
- **Views or URLs.** The example above is the shape, not a working endpoint.
- **Scoring.** The four-dimension scoring and gate logic from the rubric docs is a separate system; the advisors never score, by rule, and this package doesn't touch it.
- **Live tools.** All six advisors reason only from the scenario facts they're given and are guardrailed against inventing beyond it. None of them make external calls or look anything up; if that ever changes for one of them, that's a new capability to design, not something this package assumes.

## Testing without spending API credits

Leave `DIGITALCO_LLM_PROVIDER` unset. The `echo` client returns `[echo] <your message>` so you can wire up views, persistence, and the turn cap end to end before a single real token gets spent.
