"""Fail-closed registry of packaged skills; no remote code or user-supplied manifests."""

from pathlib import Path
import re
import tomllib
from adex_agent.routing.intent import travel_intent
from .contracts import SkillDefinition, SkillPlan
from .travel import compile_travel, requested_days

_ALLOWED = frozenset({"search:read"})


class SkillRegistry:
    def __init__(self, definitions: tuple[SkillDefinition, ...]):
        self.definitions = {item.id: item for item in definitions}
        if len(self.definitions) != len(definitions):
            raise ValueError("DUPLICATE_SKILL")
        for item in definitions:
            if not re.fullmatch(r"[a-z][a-z0-9_.-]{0,79}", item.id) or not item.version:
                raise ValueError("INVALID_SKILL_ID_OR_VERSION")
            if set(item.capabilities) - _ALLOWED:
                raise ValueError("UNSUPPORTED_SKILL_CAPABILITY")

    def resolve(self, text: str) -> SkillPlan | None:
        if travel_intent(text) or re.search(r"景点预约|预约.*景点|订酒店|预订酒店|订房|酒店.*下单", text):
            return compile_travel(self.definitions["travel.plan"], text)
        return None

    def resolve_context(self, messages: list[dict]) -> SkillPlan | None:
        users = [m["content"] for m in messages if m.get("role") == "user"][-12:]
        if not users:
            return None
        direct = self.resolve(users[-1])
        if direct:
            return direct
        # Explicit editing requests may continue a prior travel skill. Do not
        # carry its policy into unrelated chat or consume assistant claims.
        if (
            re.search(r"第.{1,3}天|行程|酒店|景点|住宿|路线", users[-1]) or requested_days(users[-1])
        ) and re.search(r"改|换|调整|轻松|减少|增加|保留", users[-1]):
            for previous in reversed(users[:-1]):
                if self.resolve(previous):
                    return compile_travel(self.definitions["travel.plan"], previous + "\n" + users[-1])
        return None


def builtin_registry() -> SkillRegistry:
    data = tomllib.loads((Path(__file__).parent / "builtin" / "travel.toml").read_text())
    definition = SkillDefinition(
        data["id"],
        data["version"],
        data["description"],
        tuple(data["capabilities"]),
        tuple(data["stages"]),
        data["instructions"],
    )
    return SkillRegistry((definition,))


REGISTRY = builtin_registry()
