from __future__ import annotations

from collections import deque
from typing import Any

from civlite.config import MAP_WIDTH, MAP_HEIGHT, UNITS

TILE_MOVE_COST = {
    "land": 3,
    "forest": 4,
    "desert": 4,
    "hill": 6,
    "swamp": 6,
    "water": 12,
    "deep_water": 12,
}

FACTIONS = ("red", "yellow", "blue", "black")


class Unit:
    """
    Unit параметризуется через config.UNITS по unit_type.

    Поддерживает:
    - hp / attack / range
    - move_mult (множитель к базовым очкам хода)
    - vision_mult (множитель к базовому обзору)

    + удобные геттеры под будущую экономику/популяцию/найм:
    - get_cost(), get_upkeep(), get_pop_used(), get_required_building()
    """

    BASE_MOVE_POINTS = 11
    BASE_VISION = 5  # базовый обзор юнита

    def __init__(self, x: int, y: int, *, faction: str = "red", unit_type: str = "worker"):
        self.x = int(x)
        self.y = int(y)

        if faction not in FACTIONS:
            faction = "red"
        self.faction = faction

        # selection / turn flags
        self.selected = False
        self.used_negative = False
        self.created_major_turn = -10**9  # чтобы game.py мог блокировать ход в ход создания

        # movement animation
        self.path: list[tuple[int, int]] = []
        self.moving = False
        self.path_index = 0
        self.time_per_tile = 0.5  # 2 клетки в секунду
        self.time_accumulator = 0.0
        self.target_game_map = None

        # --- typed stats (через config) ---
        self._unit_type = "worker"
        self.unit_type = unit_type  # triggers apply stats

        # movement points
        self.max_move_points = self._calc_max_move_points()
        self.move_points = self.max_move_points

    # -------------------- type/stats --------------------
    @property
    def unit_type(self) -> str:
        return self._unit_type

    @unit_type.setter
    def unit_type(self, value: str):
        v = str(value) if value else "worker"
        if v not in UNITS:
            v = "worker"
        self._unit_type = v
        self._apply_type_stats()

    def _cfg(self) -> dict[str, Any]:
        return UNITS.get(self._unit_type, UNITS.get("worker", {}))

    def _calc_max_move_points(self) -> int:
        cfg = self._cfg()
        move_mult = float(cfg.get("move_mult", 1.0))
        mp = int(round(self.BASE_MOVE_POINTS * move_mult))
        return max(1, mp)

    def _apply_type_stats(self):
        cfg = self._cfg()

        self.max_hp = int(cfg.get("hp", 1))
        if not hasattr(self, "hp"):
            self.hp = self.max_hp
        else:
            self.hp = min(int(self.hp), self.max_hp)

        self.attack = int(cfg.get("attack", 0))
        self.range = max(1, int(cfg.get("range", 1)))

        self.vision_mult = float(cfg.get("vision_mult", 1.0))
        self.vision = max(1, int(round(self.BASE_VISION * self.vision_mult)))

        new_max = self._calc_max_move_points()
        if not hasattr(self, "max_move_points"):
            self.max_move_points = new_max
            self.move_points = new_max
        else:
            self.max_move_points = new_max
            self.move_points = min(int(getattr(self, "move_points", new_max)), new_max)

    # -------------------- economy helpers (for game.py) --------------------
    def get_cost(self) -> dict[str, int]:
        cfg = self._cfg()
        c = cfg.get("cost", {}) or {}
        return {"gold": int(c.get("gold", 0)), "food": int(c.get("food", 0))}

    def get_upkeep(self) -> dict[str, int]:
        cfg = self._cfg()
        u = cfg.get("upkeep", {}) or {}
        return {"gold": int(u.get("gold", 0)), "food": int(u.get("food", 0))}

    def get_pop_used(self) -> int:
        cfg = self._cfg()
        return max(0, int(cfg.get("pop_used", 0)))

    def get_required_building(self) -> str | None:
        cfg = self._cfg()
        req = cfg.get("requires", {}) or {}
        b = req.get("building")
        if b is None:
            return None
        b = str(b)
        return b if b else None

    def get_combat_power_multiplier(self, *, food_is_negative: bool, neg_food_mult: float = 0.5) -> float:
        """
        В боевой логике: если food < 0 -> множитель боеспособности (например 0.5).
        Сейчас это просто хелпер.
        """
        if food_is_negative:
            return max(0.0, float(neg_food_mult))
        return 1.0

    # -------------------- turn/move --------------------
    def reset_move(self):
        self.move_points = self.max_move_points
        self.used_negative = False

    def can_move(self) -> bool:
        return (not self.moving) and (self.move_points > 0 or not self.used_negative)

    def get_tile_cost(self, tile_type: str) -> int:
        return TILE_MOVE_COST.get(tile_type, 3)

    def get_reachable_tiles(self, game_map) -> list[tuple[int, int]]:
        reachable: set[tuple[int, int]] = set()

        # visited[(x,y)] = (best_mp_left, used_negative_flag)
        visited: dict[tuple[int, int], tuple[int, bool]] = {}
        queue = deque()
        queue.append((self.x, self.y, self.move_points, self.used_negative))
        visited[(self.x, self.y)] = (self.move_points, self.used_negative)

        while queue:
            cx, cy, mp_left, used_neg = queue.popleft()

            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue

                    nx, ny = cx + dx, cy + dy
                    if not (0 <= nx < MAP_WIDTH and 0 <= ny < MAP_HEIGHT):
                        continue

                    cost = self.get_tile_cost(game_map[ny][nx])
                    new_mp = mp_left - cost
                    new_used_neg = used_neg

                    # одноразовый "уход в минус"
                    if new_mp < 0:
                        if used_neg:
                            continue
                        new_used_neg = True

                    prev = visited.get((nx, ny))
                    if prev is not None:
                        prev_mp, prev_used = prev
                        # доминирование: лучше иметь больше mp, и лучше НЕ использовать минус
                        # если новый вариант не лучше — пропускаем
                        if (new_used_neg and not prev_used) and new_mp <= prev_mp:
                            continue
                        if (new_used_neg == prev_used) and new_mp <= prev_mp:
                            continue

                    visited[(nx, ny)] = (new_mp, new_used_neg)
                    reachable.add((nx, ny))
                    queue.append((nx, ny, new_mp, new_used_neg))

        reachable.discard((self.x, self.y))
        return list(reachable)

    def move_to(self, x: int, y: int, game_map) -> bool:
        if not self.can_move():
            return False

        # visited[(x,y)] = (best_mp_left, used_neg) to prune
        visited: dict[tuple[int, int], tuple[int, bool]] = {}
        queue = deque()
        queue.append((self.x, self.y, self.move_points, self.used_negative, []))

        target_path = None

        while queue:
            cx, cy, mp_left, used_neg, path = queue.popleft()
            path2 = path + [(cx, cy)]

            if (cx, cy) == (x, y):
                target_path = path2
                break

            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue

                    nx, ny = cx + dx, cy + dy
                    if not (0 <= nx < MAP_WIDTH and 0 <= ny < MAP_HEIGHT):
                        continue

                    cost = self.get_tile_cost(game_map[ny][nx])
                    new_mp = mp_left - cost
                    new_used_neg = used_neg

                    if new_mp < 0:
                        if used_neg:
                            continue
                        new_used_neg = True

                    prev = visited.get((nx, ny))
                    if prev is not None:
                        prev_mp, prev_used = prev
                        if (new_used_neg and not prev_used) and new_mp <= prev_mp:
                            continue
                        if (new_used_neg == prev_used) and new_mp <= prev_mp:
                            continue

                    visited[(nx, ny)] = (new_mp, new_used_neg)
                    queue.append((nx, ny, new_mp, new_used_neg, path2))

        if target_path:
            self.path = target_path[1:]  # исключаем стартовую клетку
            self.path_index = 0
            self.moving = True
            self.time_accumulator = 0.0
            self.target_game_map = game_map
            return True

        return False

    def update(self, dt: float) -> int:
        """
        Возвращает количество клеток, на которые юнит реально перешёл за этот кадр (для звуков шагов).
        """
        steps_made = 0

        if self.moving and self.path_index < len(self.path):
            self.time_accumulator += float(dt)

            while self.time_accumulator >= self.time_per_tile and self.path_index < len(self.path):
                self.time_accumulator -= self.time_per_tile

                next_x, next_y = self.path[self.path_index]
                cost = self.get_tile_cost(self.target_game_map[next_y][next_x])

                if self.move_points - cost < 0 and not self.used_negative:
                    self.used_negative = True
                    self.move_points -= cost
                    if self.move_points < 0:
                        self.move_points = -1
                else:
                    self.move_points -= cost

                self.x, self.y = next_x, next_y
                self.path_index += 1
                steps_made += 1

        if self.path_index >= len(self.path) and self.moving:
            self.moving = False
            self.path = []

        return steps_made