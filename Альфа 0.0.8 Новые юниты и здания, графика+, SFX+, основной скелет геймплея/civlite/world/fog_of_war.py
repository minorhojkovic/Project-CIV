from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List


FOG_FULL = 0      # не исследовано / ничего не видно
FOG_PARTIAL = 1   # было видно раньше, но сейчас не видно (тайл виден, объекты — нет)
FOG_VISIBLE = 2   # видно сейчас (всё видно)


@dataclass(frozen=True)
class VisionSource:
    x: int
    y: int
    radius: int


class FogOfWar:
    """
    Fog of War на фракцию.

    fog[faction_id][y][x] -> FOG_FULL / FOG_PARTIAL / FOG_VISIBLE

    Обновление:
      - begin_update(): VISIBLE -> PARTIAL
      - reveal_circle(): ставит VISIBLE в радиусе
      - update_from_sources(): begin_update + reveal от всех источников
    """

    def __init__(self, width: int, height: int, faction_ids: Iterable[str]):
        self.width = int(width)
        self.height = int(height)
        self.fog: Dict[str, List[List[int]]] = {
            fid: [[FOG_FULL for _ in range(self.width)] for _ in range(self.height)]
            for fid in faction_ids
        }

    def begin_update(self, faction_id: str) -> None:
        grid = self.fog[faction_id]
        for y in range(self.height):
            row = grid[y]
            for x in range(self.width):
                if row[x] == FOG_VISIBLE:
                    row[x] = FOG_PARTIAL

    def reveal_circle(self, faction_id: str, cx: int, cy: int, radius: int) -> None:
        r = int(radius)
        if r <= 0:
            return

        grid = self.fog[faction_id]

        x0 = max(0, cx - r)
        x1 = min(self.width - 1, cx + r)
        y0 = max(0, cy - r)
        y1 = min(self.height - 1, cy + r)

        rr = r * r
        for y in range(y0, y1 + 1):
            dy = y - cy
            row = grid[y]
            for x in range(x0, x1 + 1):
                dx = x - cx
                if dx * dx + dy * dy <= rr:
                    row[x] = FOG_VISIBLE

    def update_from_sources(self, faction_id: str, sources: Iterable[VisionSource]) -> None:
        self.begin_update(faction_id)
        for s in sources:
            self.reveal_circle(faction_id, s.x, s.y, s.radius)

    def get_state(self, faction_id: str, x: int, y: int) -> int:
        return self.fog[faction_id][y][x]

    def is_visible_now(self, faction_id: str, x: int, y: int) -> bool:
        return self.get_state(faction_id, x, y) == FOG_VISIBLE

    def is_ever_seen(self, faction_id: str, x: int, y: int) -> bool:
        return self.get_state(faction_id, x, y) != FOG_FULL
