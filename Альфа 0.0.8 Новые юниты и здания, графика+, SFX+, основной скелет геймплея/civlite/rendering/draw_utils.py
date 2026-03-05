from __future__ import annotations

import os
from pathlib import Path
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

from civlite.world.fog_of_war import FOG_FULL, FOG_PARTIAL, FogOfWar


TILE_COLORS = {
    "water": WATER_COLOR,
    "deep_water": DEEP_WATER_COLOR,
    "land": LAND_COLOR,
    "forest": FOREST_COLOR,
    "hill": HILL_COLOR,
    "swamp": SWAMP_COLOR,
    "desert": DESERT_COLOR,
}

# ------------------- Icon loading / cache -------------------

# project root (folder containing 'civlite') -> .../Civilisation Lite/
_BASE_DIR = Path(__file__).resolve().parents[2]
_ICONS_DIR = _BASE_DIR / "assets" / "icons"

# raw surfaces cache: (entity_id, faction) -> Surface
_ICON_CACHE_RAW: dict[tuple[str, str], pygame.Surface] = {}
# scaled cache: (entity_id, faction, size_px) -> Surface
_ICON_CACHE_SCALED: dict[tuple[str, str, int], pygame.Surface] = {}


def _safe_load_icon(entity_id: str, faction: str) -> pygame.Surface | None:
    """
    Грузит PNG по пути assets/icons/{entity_id}_{faction}.png
    Возвращает Surface или None если файла нет/ошибка.
    """
    if not entity_id or not faction:
        return None

    key = (entity_id, faction)
    if key in _ICON_CACHE_RAW:
        return _ICON_CACHE_RAW[key]

    filename = f"{entity_id}_{faction}.png"
    path = _ICONS_DIR / filename

    if not path.exists():
        _ICON_CACHE_RAW[key] = None  # кешируем отсутствие
        return None

    try:
        surf = pygame.image.load(str(path)).convert_alpha()
        _ICON_CACHE_RAW[key] = surf
        return surf
    except Exception:
        _ICON_CACHE_RAW[key] = None
        return None


def _get_icon_scaled(entity_id: str, faction: str, tile_size: int) -> pygame.Surface | None:
    """
    Возвращает отмасштабированную под tile_size иконку (не вылезает за клетку).
    """
    raw = _safe_load_icon(entity_id, faction)
    if raw is None:
        return None

    # Чтобы иконка не упиралась в границы клетки
    pad = max(1, tile_size // 12)
    max_w = max(1, tile_size - pad * 2)
    max_h = max(1, tile_size - pad * 2)

    cache_key = (entity_id, faction, tile_size)
    if cache_key in _ICON_CACHE_SCALED:
        return _ICON_CACHE_SCALED[cache_key]

    w, h = raw.get_width(), raw.get_height()
    if w <= 0 or h <= 0:
        _ICON_CACHE_SCALED[cache_key] = None
        return None

    scale = min(max_w / w, max_h / h)
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))

    try:
        scaled = pygame.transform.smoothscale(raw, (new_w, new_h))
    except Exception:
        scaled = raw

    _ICON_CACHE_SCALED[cache_key] = scaled
    return scaled


def _blit_icon_in_tile(
    screen: pygame.Surface,
    icon: pygame.Surface,
    *,
    px: int,
    py: int,
    tile_size: int,
):
    """
    Рисует icon по центру клетки (px,py) размера tile_size
    """
    if icon is None:
        return
    rect = icon.get_rect(center=(px + tile_size // 2, py + tile_size // 2))
    screen.blit(icon, rect)


# ------------------- map rendering -------------------

def draw_map(
    game_map,
    screen: pygame.Surface,
    *,
    offset_y: int = TOP_UI_HEIGHT,
    origin_x: int = 0,
    tile_size: int = TILE_SIZE,
    fog: FogOfWar | None = None,
    faction_id: str | None = None,
):
    """
    Рисует карту. Если fog + faction_id заданы:
      - FOG_FULL: рисуем чёрный прямоугольник
      - FOG_PARTIAL: рисуем тайл + затемняем
      - иначе: рисуем нормально
    """
    h = len(game_map)
    w = len(game_map[0]) if h else 0

    partial_overlay = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
    partial_overlay.fill((0, 0, 0, 140))

    for y in range(h):
        for x in range(w):
            px = origin_x + x * tile_size
            py = offset_y + y * tile_size

            if fog is not None and faction_id is not None:
                st = fog.get_state(faction_id, x, y)
                if st == FOG_FULL:
                    pygame.draw.rect(screen, (0, 0, 0), (px, py, tile_size, tile_size))
                    continue

            tile = game_map[y][x]
            color = TILE_COLORS.get(tile, (255, 0, 255))
            pygame.draw.rect(screen, color, (px, py, tile_size, tile_size))

            if fog is not None and faction_id is not None:
                st = fog.get_state(faction_id, x, y)
                if st == FOG_PARTIAL:
                    screen.blit(partial_overlay, (px, py))


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


# ------------------- units rendering -------------------

def draw_units(
    units,
    screen: pygame.Surface,
    *,
    offset_y: int = 0,
    origin_x: int = 0,
    tile_size: int = TILE_SIZE,
    fog: FogOfWar | None = None,
    faction_id: str | None = None,
):
    """
    Рисует юниты.
    Если fog + faction_id заданы:
      - рисуем юнита только если клетка видима сейчас для этой фракции
    Теперь приоритет: иконка из assets/icons/{unit_type}_{faction}.png
    Фоллбек: старые кружки.
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
        ux, uy = int(getattr(u, "x", 0)), int(getattr(u, "y", 0))

        if fog is not None and faction_id is not None:
            if not fog.is_visible_now(faction_id, ux, uy):
                continue

        px = origin_x + ux * tile_size
        py = offset_y + uy * tile_size

        unit_type = getattr(u, "unit_type", None) or "worker"
        fac = getattr(u, "faction", None) or "red"

        icon = _get_icon_scaled(str(unit_type), str(fac), tile_size)
        if icon is not None:
            _blit_icon_in_tile(screen, icon, px=px, py=py, tile_size=tile_size)
        else:
            # fallback circles
            cx = px + tile_size // 2
            cy = py + tile_size // 2
            color = FACTION_COLORS.get(fac, (150, 150, 150))
            pygame.draw.circle(screen, color, (cx, cy), r_body)
            pygame.draw.circle(screen, (0, 0, 0), (cx, cy), r_body, 1)

        if getattr(u, "selected", False):
            cx = px + tile_size // 2
            cy = py + tile_size // 2
            pygame.draw.circle(screen, (0, 255, 0), (cx, cy), r_sel, 2)


def draw_grid(
    screen: pygame.Surface,
    *,
    offset_y: int = TOP_UI_HEIGHT,
    origin_x: int = 0,
    tile_size: int = TILE_SIZE,
    map_w: int = MAP_WIDTH,
    map_h: int = MAP_HEIGHT,
):
    for x in range(map_w + 1):
        px = origin_x + x * tile_size
        pygame.draw.line(screen, (50, 50, 50), (px, offset_y), (px, offset_y + map_h * tile_size))
    for y in range(map_h + 1):
        py = offset_y + y * tile_size
        pygame.draw.line(screen, (50, 50, 50), (origin_x, py), (origin_x + map_w * tile_size, py))


def draw_highlight_tiles(
    screen: pygame.Surface,
    tiles,
    *,
    offset_y: int = TOP_UI_HEIGHT,
    origin_x: int = 0,
    tile_size: int = TILE_SIZE,
    map_w: int = MAP_WIDTH,
    map_h: int = MAP_HEIGHT,
    fog: FogOfWar | None = None,
    faction_id: str | None = None,
):
    """
    Подсветка клеток.
    Если fog + faction_id заданы — НЕ подсвечиваем FOG_FULL.
    """
    overlay = pygame.Surface((map_w * tile_size, map_h * tile_size), pygame.SRCALPHA)

    for (x, y) in tiles:
        if fog is not None and faction_id is not None:
            if fog.get_state(faction_id, x, y) == FOG_FULL:
                continue
        pygame.draw.rect(overlay, (0, 255, 0, 90), (x * tile_size, y * tile_size, tile_size, tile_size))

    screen.blit(overlay, (origin_x, offset_y))


# ------------------- buildings/bases rendering -------------------

def draw_bases(
    bases,
    screen: pygame.Surface,
    *,
    offset_y: int = TOP_UI_HEIGHT,
    origin_x: int = 0,
    tile_size: int = TILE_SIZE,
    fog: FogOfWar | None = None,
    faction_id: str | None = None,
):
    """
    Рисует базы/здания.
    Теперь приоритет: иконка из assets/icons/{building_type}_{faction}.png
    Где building_type берём из b["building_type"] (если нет — "citadel").
    Фоллбек: старый прямоугольник.
    """
    if not bases:
        return

    # fallback colors (если иконки нет)
    base_color_map = {
        "red": (220, 80, 80),
        "yellow": (220, 220, 80),
        "blue": (80, 80, 220),
        "black": (80, 80, 80),
    }

    for b in bases:
        x = int(b.get("x", 0))
        y = int(b.get("y", 0))
        faction = b.get("faction") or "red"
        building_type = b.get("building_type") or b.get("type") or "citadel"

        if fog is not None and faction_id is not None:
            if not fog.is_visible_now(faction_id, x, y):
                continue

        px = origin_x + x * tile_size
        py = offset_y + y * tile_size

        icon = _get_icon_scaled(str(building_type), str(faction), tile_size)
        if icon is not None:
            _blit_icon_in_tile(screen, icon, px=px, py=py, tile_size=tile_size)
        else:
            # fallback rect
            base_color = base_color_map.get(faction, (200, 200, 200))
            pad = max(1, tile_size // 10)
            pygame.draw.rect(
                screen,
                base_color,
                (px + pad, py + pad, tile_size - pad * 2, tile_size - pad * 2),
            )
            pygame.draw.rect(
                screen,
                (0, 0, 0),
                (px + pad, py + pad, tile_size - pad * 2, tile_size - pad * 2),
                1,
            )