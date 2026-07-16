from abc import ABC, abstractmethod

from core.models import Tier

from .structures import Artifact, AutoScore, Briefing, DecisionSpec, WeekAdvisorContext


class WeekModule(ABC):
    week_number: int
    title: str

    def briefing(self, tier: Tier) -> Briefing:
        raise NotImplementedError

    def artifacts(self, tier: Tier) -> list[Artifact]:
        return []

    def advisor_context(self, advisor_key: str, tier: Tier, run_state: dict) -> WeekAdvisorContext:
        raise NotImplementedError

    def decision_spec(self, tier: Tier) -> DecisionSpec:
        raise NotImplementedError

    @abstractmethod
    def score_auto(self, submission, run_state: dict) -> AutoScore:
        raise NotImplementedError

    @abstractmethod
    def apply_state_update(self, submission, auto: AutoScore, run_state: dict) -> dict:
        raise NotImplementedError

    def finalize_state_update(self, score_record, run_state: dict) -> dict:
        return run_state

    def reads_state(self) -> list[str]:
        return []
