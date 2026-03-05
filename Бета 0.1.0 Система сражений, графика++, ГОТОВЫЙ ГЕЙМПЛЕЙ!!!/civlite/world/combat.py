from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional


@dataclass
class CombatResult:
    attacker_dead: bool
    defender_dead: bool
    damage_to_defender: int
    damage_to_attacker: int
    attacker_roll: int
    defender_roll: int
    defender_shield: int
    counter_roll: int


def _roll(dice: Optional[int]) -> int:
    if not dice:
        return 0
    return random.randint(1, int(dice))


def _floor_half(x: int) -> int:
    # -50% с округлением вниз
    return int(x) // 2


def _apply_damage_with_shield(raw_attack: int, shield: int, hp: int) -> tuple[int, int, int]:
    """
    Возвращает (new_shield, new_hp, dealt_to_hp)
    """
    atk = max(0, int(raw_attack))
    sh = max(0, int(shield))
    h = max(0, int(hp))

    # сначала ломаем щит
    take = min(sh, atk)
    sh -= take
    atk -= take

    # остаток в hp
    dealt_hp = min(h, atk)
    h -= dealt_hp
    return sh, h, dealt_hp


def _is_archer_type(unit_type: str) -> bool:
    ut = (unit_type or "").lower()
    return ("archer" in ut) or ("bow" in ut) or ("longbow" in ut)


def _is_knight_type(unit_type: str) -> bool:
    ut = (unit_type or "").lower()
    return "knight" in ut


def resolve_battle_units(
    *,
    attacker,  # Unit-like: attack, dice, hp, range, min_range
    defender,  # Unit-like
    attacker_food_negative: bool,
    defender_food_negative: bool,
) -> CombatResult:
    """
    Бой юнит vs юнит по твоим правилам.
    """

    # 1) броски
    a_roll = _roll(getattr(attacker, "dice", None))
    d_roll = _roll(getattr(defender, "dice", None))

    # 2) атака = base + roll
    a_atk = int(getattr(attacker, "attack", 0)) + int(a_roll)

    # 3) защита = roll * 2
    shield = int(d_roll) * 2

    # 6) дебафф -50% если еда < 0 у стороны
    if attacker_food_negative:
        a_atk = _floor_half(a_atk)
    if defender_food_negative:
        shield = _floor_half(shield)

    # 4) атакуем защиту и hp
    shield_after, def_hp_after, dealt_def_hp = _apply_damage_with_shield(
        raw_attack=a_atk, shield=shield, hp=int(getattr(defender, "hp", 1))
    )
    defender.hp = def_hp_after  # mutate

    dmg_to_attacker = 0
    counter_roll = 0

    # 5) контратака только melee<->melee или ranged<->ranged
    attacker_is_ranged = int(getattr(attacker, "range", 1)) > 1
    defender_is_ranged = int(getattr(defender, "range", 1)) > 1

    do_counter = (attacker_is_ranged == defender_is_ranged)

    if do_counter and getattr(defender, "hp", 0) > 0:
        counter_roll = _roll(getattr(defender, "dice", None))
        counter_atk = int(getattr(defender, "attack", 0)) + int(counter_roll)

        # дебафф еды для контратаки: бьющий сейчас = defender
        if defender_food_negative:
            counter_atk = _floor_half(counter_atk)

        # в контратаке НЕТ защитного броска у атакующего
        _, att_hp_after, dealt_att_hp = _apply_damage_with_shield(
            raw_attack=counter_atk, shield=0, hp=int(getattr(attacker, "hp", 1))
        )
        attacker.hp = att_hp_after
        dmg_to_attacker = dealt_att_hp

    return CombatResult(
        attacker_dead=int(getattr(attacker, "hp", 0)) <= 0,
        defender_dead=int(getattr(defender, "hp", 0)) <= 0,
        damage_to_defender=dealt_def_hp,
        damage_to_attacker=dmg_to_attacker,
        attacker_roll=int(a_roll),
        defender_roll=int(d_roll),
        defender_shield=int(shield),
        counter_roll=int(counter_roll),
    )


def resolve_attack_structure(
    *,
    attacker,  # Unit-like
    structure: dict,  # {"hp": int, "type": str, ...}
    attacker_food_negative: bool,
    structure_food_negative: bool,
) -> tuple[bool, int, int, int]:
    """
    Атака по зданию:
    - здание не бросает кубик на защиту (пока)
    - здания получают на 50% меньше урона от лучников и рыцарей (обычных и усиленных)
    Возвращает (destroyed, damage, attacker_roll, effective_attack)
    """
    a_roll = _roll(getattr(attacker, "dice", None))
    a_atk = int(getattr(attacker, "attack", 0)) + int(a_roll)

    if attacker_food_negative:
        a_atk = _floor_half(a_atk)

    # хук на будущее
    _ = structure_food_negative

    hp = int(structure.get("hp", 1))

    dmg = min(hp, max(0, a_atk))

    # ✅ здания получают -50% урона от лучников и рыцарей
    unit_type = getattr(attacker, "unit_type", "") or ""
    if _is_archer_type(unit_type) or _is_knight_type(unit_type):
        dmg = _floor_half(dmg)

    hp -= dmg
    structure["hp"] = hp
    destroyed = hp <= 0
    return destroyed, int(dmg), int(a_roll), int(a_atk)