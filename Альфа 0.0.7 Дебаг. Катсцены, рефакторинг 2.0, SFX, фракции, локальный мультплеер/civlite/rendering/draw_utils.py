from __future__ import annotations

import pygame
from civlite.config import (
    TILE_SIZE,
    MAP_WIDTH,
    MAP_HEIGHT,
    TOP_UI_HEIGHT,
    WATER_COLOR,
    DEEP_WATER_COLOR,
    LAND_COLOR,
    FOREST_COLOR,
    HILL_COLOR,
    SWAMP_COLOR,
    DESERT_COLOR,
    BUTTON_COLOR,
    BUTTON_HOVER,
    TEXT_COLOR,
)

TILE_COLORS = {
    "water": WATER_COLOR,
    "deep_water": DEEP_WATER_COLOR,
    "land": LAND_COLOR,
    "forest": FOREST_COLOR,
    "hill": HILL_COLOR,
    "swamp": SWAMP_COLOR,
    "desert": DESERT_COLOR,
}


def draw_map(game_map, screen: pygame.Surface, *, offset_y: int = TOP_UI_HEIGHT, origin_x: int = 0, tile_size: int = TILE_SIZE):
    """
    Рисует карту, учитывая origin_x и tile_size.
    """
    h = len(game_map)
    w = len(game_map[0]) if h else 0
    for y in range(h):
        for x in range(w):
            tile = game_map[y][x]
            color = TILE_COLORS.get(tile, (255, 0, 255))
            pygame.draw.rect(
                screen,
                color,
                (origin_x + x * tile_size, offset_y + y * tile_size, tile_size, tile_size)
            )


def _scale_surface_to_fit(surf: pygame.Surface, max_w: int, max_h: int) -> pygame.Surface:
    """Мягко уменьшаем surface, если не влазит."""
    w, h = surf.get_width(), surf.get_height()
    if w <= max_w and h <= max_h:
        return surf

    scale = min(max_w / max(1, w), max_h / max(1, h))
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    return pygame.transform.smoothscale(surf, (new_w, new_h))


def draw_button(rect: pygame.Rect, text: str, screen: pygame.Surface, font: pygame.font.Font, mouse_pos):
    hover = rect.collidepoint(mouse_pos)
    color = BUTTON_HOVER if hover else BUTTON_COLOR

    pygame.draw.rect(screen, color, rect, border_radius=8)
    pygame.draw.rect(screen, (0, 0, 0), rect, 2, border_radius=8)

    pad = 8
    max_w = max(1, rect.width - pad * 2)
    max_h = max(1, rect.height - pad * 2)

    text_surf = font.render(text, True, TEXT_COLOR)
    text_surf = _scale_surface_to_fit(text_surf, max_w, max_h)

    text_rect = text_surf.get_rect(center=rect.center)
    screen.blit(text_surf, text_rect)


def draw_units(units, screen: pygame.Surface, *, offset_y: int = 0, origin_x: int = 0, tile_size: int = TILE_SIZE):
    """
    Рисует юниты. Цвет берётся из faction.
    """
    FACTION_COLORS = {
        "red": (200, 50, 50),
        "yellow": (200, 200, 50),
        "blue": (50, 50, 200),
        "black": (40, 40, 40),
    }

    r_body = max(2, tile_size // 3)
    r_sel = max(r_body + 2, tile_size // 2)

    for u in units:
        cx = origin_x + u.x * tile_size + tile_size // 2
        cy = offset_y + u.y * tile_size + tile_size // 2

        color = FACTION_COLORS.get(getattr(u, "faction", None), (150, 150, 150))

        pygame.draw.circle(screen, color, (cx, cy), r_body)
        pygame.draw.circle(screen, (0, 0, 0), (cx, cy), r_body, 1)

        if getattr(u, "selected", False):
            pygame.draw.circle(screen, (0, 255, 0), (cx, cy), r_sel, 2)


def draw_grid(screen: pygame.Surface, *, offset_y: int = TOP_UI_HEIGHT, origin_x: int = 0, tile_size: int = TILE_SIZE,
              map_w: int = MAP_WIDTH, map_h: int = MAP_HEIGHT):
    for x in range(map_w + 1):
        px = origin_x + x * tile_size
        pygame.draw.line(
            screen, (50, 50, 50),
            (px, offset_y),
            (px, offset_y + map_h * tile_size)
        )
    for y in range(map_h + 1):
        py = offset_y + y * tile_size
        pygame.draw.line(
            screen, (50, 50, 50),
            (origin_x, py),
            (origin_x + map_w * tile_size, py)
        )


def draw_highlight_tiles(screen: pygame.Surface, tiles, *, offset_y: int = TOP_UI_HEIGHT, origin_x: int = 0, tile_size: int = TILE_SIZE,
                         map_w: int = MAP_WIDTH, map_h: int = MAP_HEIGHT):
    overlay = pygame.Surface((map_w * tile_size, map_h * tile_size), pygame.SRCALPHA)
    for (x, y) in tiles:
        pygame.draw.rect(
            overlay,
            (0, 255, 0, 90),
            (x * tile_size, y * tile_size, tile_size, tile_size)
        )
    screen.blit(overlay, (origin_x, offset_y))


def draw_bases(bases, screen: pygame.Surface, *, offset_y: int = TOP_UI_HEIGHT, origin_x: int = 0, tile_size: int = TILE_SIZE):
    if not bases:
        return

    for b in bases:
        x = b["x"]
        y = b["y"]
        faction = b.get("faction")

        px = origin_x + x * tile_size
        py = offset_y + y * tile_size

        base_color = (200, 200, 200)
        if faction == "red":
            base_color = (220, 80, 80)
        elif faction == "yellow":
            base_color = (220, 220, 80)
        elif faction == "blue":
            base_color = (80, 80, 220)
        elif faction == "black":
            base_color = (80, 80, 80)

        pad = max(1, tile_size // 10)
        pygame.draw.rect(screen, base_color, (px + pad, py + pad, tile_size - pad * 2, tile_size - pad * 2))
        pygame.draw.rect(screen, (0, 0, 0), (px + pad, py + pad, tile_size - pad * 2, tile_size - pad * 2), 1)