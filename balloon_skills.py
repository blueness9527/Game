# -*- coding: utf-8 -*-

import math
import time
from dataclasses import dataclass


MAX_SKILL_SLOTS = 9
RAINBOW_SPLASH_RADIUS = 96


@dataclass(frozen=True)
class SkillDefinition:
    slot: int
    cannon_id: str
    name: str
    cooldown_seconds: float
    description: str


SKILLS_BY_CANNON: dict[str, dict[int, SkillDefinition]] = {
    "rainbow": {
        1: SkillDefinition(
            slot=1,
            cannon_id="rainbow",
            name="彩虹连爆",
            cooldown_seconds=10,
            description="下一次命中时击破目标周围气球",
        )
    },
    "diamond": {
        1: SkillDefinition(
            slot=1,
            cannon_id="diamond",
            name="钻石清场",
            cooldown_seconds=20,
            description="立即清空当前所有气球",
        )
    },
}


class SkillManager:
    def __init__(self) -> None:
        self.cooldowns: dict[str, float] = {}
        self.pending_effects: dict[str, bool] = {}

    def get_slots(self, cannon_id: str) -> list[SkillDefinition | None]:
        skills = SKILLS_BY_CANNON.get(cannon_id, {})
        return [skills.get(slot) for slot in range(1, MAX_SKILL_SLOTS + 1)]

    def get_skill(self, cannon_id: str, slot: int) -> SkillDefinition | None:
        return SKILLS_BY_CANNON.get(cannon_id, {}).get(slot)

    def remaining_cooldown(self, skill: SkillDefinition) -> int:
        ready_at = self.cooldowns.get(self._key(skill), 0)
        remaining = max(0, ready_at - time.monotonic())
        return math.ceil(remaining)

    def can_use(self, skill: SkillDefinition) -> tuple[bool, str]:
        remaining = self.remaining_cooldown(skill)
        if remaining > 0:
            return False, f"{skill.name}冷却中，还需 {remaining}s"
        return True, ""

    def mark_used(self, skill: SkillDefinition) -> None:
        self.cooldowns[self._key(skill)] = time.monotonic() + skill.cooldown_seconds

    def activate_pending(self, effect_name: str) -> None:
        self.pending_effects[effect_name] = True

    def consume_pending(self, effect_name: str) -> bool:
        active = self.pending_effects.get(effect_name, False)
        if active:
            self.pending_effects[effect_name] = False
        return active

    def reset_pending(self) -> None:
        self.pending_effects.clear()

    def _key(self, skill: SkillDefinition) -> str:
        return f"{skill.cannon_id}:{skill.slot}"
