from dataclasses import dataclass, field
from typing import Any

from core.state import SCORE_DIMENSIONS


@dataclass(frozen=True)
class Artifact:
    title: str
    body: str
    kind: str = 'memo'


@dataclass(frozen=True)
class Briefing:
    title: str
    body: str
    exec_reads: list[str] = field(default_factory=list)
    signals: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class WeekAdvisorContext:
    facts: list[str]
    stance: str
    signal: str = ''
    misdirection: str = ''


@dataclass(frozen=True)
class DecisionField:
    key: str
    label: str
    field_type: str = 'text'
    required: bool = True
    choices: list[dict[str, Any]] = field(default_factory=list)
    trap_choices: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DecisionSpec:
    fields: list[DecisionField]
    deliverable_prompt: str = ''
    rubric_variant: str = 'undergrad'


@dataclass(frozen=True)
class AutoScore:
    scores: dict[str, int] = field(default_factory=dict)
    trap_flags: list[str] = field(default_factory=list)
    components: dict[str, Any] = field(default_factory=dict)

    def normalized_scores(self):
        return {dimension: int(self.scores.get(dimension, 0)) for dimension in SCORE_DIMENSIONS}
