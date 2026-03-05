from collections import deque
from civlite.config import MAP_WIDTH, MAP_HEIGHT

TILE_MOVE_COST = {
    "land": 3,
    "forest": 4,
    "desert": 4,
    "hill": 6,
    "swamp": 6,
    "water": 12,
    "deep_water": 12
}

FACTIONS = ("red", "yellow", "blue", "black")


class Unit:
    def __init__(self, x, y, max_move_points=11, faction: str = "red"):
        self.x = x
        self.y = y

        if faction not in FACTIONS:
            faction = "red"
        self.faction = faction

        self.max_move_points = max_move_points
        self.move_points = max_move_points
        self.selected = False
        self.used_negative = False

        # Анимация перемещения
        self.path = []
        self.moving = False
        self.path_index = 0
        self.time_per_tile = 0.5  # 2 клетки в секунду
        self.time_accumulator = 0

        # Карта, по которой идем (для стоимости)
        self.target_game_map = None

    def reset_move(self):
        self.move_points = self.max_move_points
        self.used_negative = False

    def can_move(self):
        return not self.moving and (self.move_points > 0 or not self.used_negative)

    def get_tile_cost(self, tile_type):
        return TILE_MOVE_COST.get(tile_type, 3)

    def get_reachable_tiles(self, game_map):
        reachable = set()
        visited = {}
        queue = deque()
        queue.append((self.x, self.y, self.move_points, self.used_negative))
        visited[(self.x, self.y)] = (self.move_points, self.used_negative)

        while queue:
            cx, cy, mp_left, used_neg = queue.popleft()
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < MAP_WIDTH and 0 <= ny < MAP_HEIGHT:
                        cost = self.get_tile_cost(game_map[ny][nx])
                        new_mp = mp_left - cost
                        new_used_neg = used_neg

                        if new_mp < 0 and not used_neg:
                            new_used_neg = True
                        elif new_mp < 0 and used_neg:
                            continue

                        if (nx, ny) in visited:
                            old_mp, old_used_neg = visited[(nx, ny)]
                            if old_mp >= new_mp and old_used_neg <= new_used_neg:
                                continue

                        visited[(nx, ny)] = (new_mp, new_used_neg)
                        reachable.add((nx, ny))
                        queue.append((nx, ny, new_mp, new_used_neg))

        reachable.discard((self.x, self.y))
        return list(reachable)

    def move_to(self, x, y, game_map):
        if not self.can_move():
            return False

        queue = deque()
        queue.append((self.x, self.y, self.move_points, self.used_negative, []))
        visited = {}

        target_path = None

        while queue:
            cx, cy, mp_left, used_neg, path = queue.popleft()
            path = path + [(cx, cy)]
            if (cx, cy) == (x, y):
                target_path = path
                break

            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < MAP_WIDTH and 0 <= ny < MAP_HEIGHT:
                        cost = self.get_tile_cost(game_map[ny][nx])
                        new_mp = mp_left - cost
                        new_used_neg = used_neg

                        if new_mp < 0 and not used_neg:
                            new_used_neg = True
                        elif new_mp < 0 and used_neg:
                            continue

                        if (nx, ny) in visited:
                            old_mp, old_used_neg = visited[(nx, ny)]
                            if old_mp >= new_mp and old_used_neg <= new_used_neg:
                                continue

                        visited[(nx, ny)] = (new_mp, new_used_neg)
                        queue.append((nx, ny, new_mp, new_used_neg, path))

        if target_path:
            # исключаем стартовую клетку (на ней звука шага нет)
            self.path = target_path[1:]
            self.path_index = 0
            self.moving = True
            self.time_accumulator = 0
            self.target_game_map = game_map
            return True

        return False

    def update(self, dt) -> int:
        """
        Возвращает количество клеток, на которые юнит реально перешёл за этот кадр
        (для шаговых звуков).
        """
        steps_made = 0

        if self.moving and self.path_index < len(self.path):
            self.time_accumulator += dt

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
