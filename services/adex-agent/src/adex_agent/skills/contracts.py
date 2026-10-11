"""Skills describe policy and read steps; they cannot grant service permissions."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class SkillDefinition:
    id: str
    version: str
    description: str
    capabilities: tuple[str, ...]
    stages: tuple[str, ...]
    instructions: str


@dataclass(frozen=True)
class SkillPlan:
    skill: SkillDefinition
    search_queries: tuple[str, ...]
    policy: str
    requested_action: Literal["plan", "reservation", "order"] = "plan"

    def system_policy(self) -> str:
        # Only repository-controlled definitions become instructions. User text
        # stays in user messages/search data and cannot introduce tool permissions.
        return (
            f"\nSkill: {self.skill.id}@{self.skill.version}\n"
            + "执行阶段："
            + " → ".join(self.skill.stages)
            + "\n"
            + self.skill.instructions
            + "\n"
            + self.policy
        )
