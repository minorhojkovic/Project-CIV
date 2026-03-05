# civlite/scenes/game.py (или где у тебя лежит run_game_scene)

from __future__ import annotations

import random
import pygame

from civlite.config import (
    SCREEN_WIDTH,
    BG_COLOR,
    MENU_COLOR,
    MAP_WIDTH,
    MAP_HEIGHT,
    TOP_UI_HEIGHT,
    BOTTOM_UI_HEIGHT,
    EXTRA_DEBUG_HEIGHT,
    # economy / rules
    START_GOLD,
    START_FOOD,
    BLOCK_SPEND_WHEN_NEGATIVE,
    # buildings / units
    BUILDINGS,
    UNITS,
    BUILD_MENU_ORDER,
)
from civlite.rendering.draw_utils import (
    draw_map,
    draw_button,
    draw_units,
    draw_highlight_tiles,
    draw_bases,  # временно: рисуем здания как "bases"
)
from civlite.world.map_generator import generate_map
from civlite.entities.unit import Unit
from civlite.audio.music import MusicManager
from civlite.audio.sfx import SfxManager

from civlite.scenes.turn_order_cutscene import run_turn_order_cutscene
from civlite.scenes.turn_transition_cutscene import run_turn_transition_cutscene

from civlite.world.fog_of_war import FogOfWar, VisionSource, FOG_FULL


FACTIONS = ["red", "yellow", "blue", "black"]
FACTION_NAMES_RU = {
    "red": "Красные",
    "yellow": "Жёлтые",
    "blue": "Синие",
    "black": "Чёрные",
}

# ------------------- Fog of war constants -------------------
VISION_RADIUS_BASE = 5
VISION_RADIUS_UNIT = 5

# ------------------- Build/spawn constants -------------------
SPAWN_RADIUS_AROUND_BUILDING = 3

# ------------------- Build placement rules -------------------
BUILD_MAX_DIST = 4  # максимум 4 клетки до ближайшего здания своей фракции (Chebyshev)
BUILD_MIN_GAP = 1   # минимум 1 клетка между зданиями => нельзя вплотную (в т.ч. по диагонали)

# ------------------- Music ducking constants -------------------
AI_MUSIC_DUCK = 0.30
DUCK_FADE_SECONDS = 3.0


def _is_land_tile(tile: str) -> bool:
    return tile not in ("water", "deep_water")


def _manhattan(a, b) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _chebyshev(a, b) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _generate_citadels_for_factions(game_map, factions: list[str], min_dist: int = 20, max_tries: int = 5000):
    """Стартовые Цитадели (1 на фракцию)."""
    land_cells = [(x, y) for y in range(MAP_HEIGHT) for x in range(MAP_WIDTH) if _is_land_tile(game_map[y][x])]
    if not land_cells:
        return []

    random.shuffle(land_cells)
    positions: list[tuple[int, int]] = []
    tries = 0

    while len(positions) < len(factions) and tries < max_tries:
        tries += 1
        x, y = random.choice(land_cells)
        if all(_manhattan((x, y), p) >= min_dist for p in positions):
            positions.append((x, y))

    if len(positions) < len(factions):
        dist = min_dist
        while len(positions) < len(factions) and dist > 5:
            dist -= 1
            positions = []
            tries = 0
            while len(positions) < len(factions) and tries < max_tries:
                tries += 1
                x, y = random.choice(land_cells)
                if all(_manhattan((x, y), p) >= dist for p in positions):
                    positions.append((x, y))

    cit_hp = int(BUILDINGS.get("citadel", {}).get("hp", 200))
    buildings = []
    for faction, (x, y) in zip(factions, positions[: len(factions)]):
        buildings.append({"x": x, "y": y, "faction": faction, "type": "citadel", "hp": cit_hp})
    return buildings


def _get_active_factions_from_roles(faction_roles: dict) -> list[str]:
    return [f for f in FACTIONS if faction_roles.get(f) in ("human", "ai")]


def _reset_moves_for_faction(units: list[Unit], faction: str):
    for u in units:
        if getattr(u, "faction", None) == faction:
            u.reset_move()


def _clear_selection(units: list[Unit]):
    for u in units:
        u.selected = False


def _compute_scale_and_layout(screen: pygame.Surface):
    W, H = screen.get_size()

    top_h = TOP_UI_HEIGHT * 2
    bottom_h = BOTTOM_UI_HEIGHT
    extra_h = EXTRA_DEBUG_HEIGHT

    game_area_h = max(1, H - top_h - bottom_h)
    game_area_y = top_h

    tile_by_w = max(1, W // MAP_WIDTH)
    tile_by_h = max(1, game_area_h // MAP_HEIGHT)
    tile = max(6, min(tile_by_w, tile_by_h))

    map_px_w = MAP_WIDTH * tile
    map_px_h = MAP_HEIGHT * tile

    origin_x = max(0, (W - map_px_w) // 2)
    map_offset_y = game_area_y + max(0, (game_area_h - map_px_h) // 2)

    bottom_y = H - bottom_h

    ui_scale = W / max(1, SCREEN_WIDTH)
    return ui_scale, tile, top_h, bottom_h, extra_h, map_px_w, map_px_h, origin_x, bottom_y, map_offset_y


def _make_game_surface(
    game_map,
    buildings,
    units,
    screen: pygame.Surface,
    *,
    fog: FogOfWar | None,
    view_faction: str | None,
) -> pygame.Surface:
    W, H = screen.get_size()
    surf = pygame.Surface((W, H))
    surf.fill(BG_COLOR)

    _, tile, _, _, _, _, _, origin_x, _, map_offset_y = _compute_scale_and_layout(screen)

    draw_map(game_map, surf, offset_y=map_offset_y, origin_x=origin_x, tile_size=tile, fog=fog, faction_id=view_faction)
    draw_bases(buildings, surf, offset_y=map_offset_y, origin_x=origin_x, tile_size=tile, fog=fog, faction_id=view_faction)
    draw_units(units, surf, offset_y=map_offset_y, origin_x=origin_x, tile_size=tile, fog=fog, faction_id=view_faction)
    return surf


# ------------------- economy (stock + per-turn deltas) -------------------
def _ensure_economy(game_state: dict, active_factions: list[str]):
    eco = game_state.get("economy")
    if not isinstance(eco, dict):
        eco = {}

    for f in active_factions:
        if f not in eco or not isinstance(eco.get(f), dict):
            eco[f] = {}

        eco[f].setdefault("gold", int(START_GOLD))
        eco[f].setdefault("food", int(START_FOOD))

        # UI-only (пересчитываем)
        eco[f].setdefault("gold_delta", 0)
        eco[f].setdefault("food_delta", 0)
        eco[f].setdefault("pop", 0)
        eco[f].setdefault("pop_cap", 0)

    game_state["economy"] = eco


def _recalc_deltas_and_pop(game_state: dict, active_factions: list[str], buildings, units: list[Unit]):
    """
    Считаем:
    - gold_delta/food_delta: сколько изменится за ход (yield - upkeep)
    - pop/pop_cap
    НЕ меняем "склад" (gold/food) — склад меняется только при end-turn.
    """
    _ensure_economy(game_state, active_factions)
    eco: dict = game_state["economy"]

    for f in active_factions:
        eco[f]["gold_delta"] = 0
        eco[f]["food_delta"] = 0
        eco[f]["pop"] = 0
        eco[f]["pop_cap"] = 0

    # buildings
    for b in (buildings or []):
        f = b.get("faction")
        bt = b.get("type")
        if f not in eco:
            continue
        cfg = BUILDINGS.get(bt, {})
        y = cfg.get("yield", {}) or {}
        up = cfg.get("upkeep", {}) or {}
        eco[f]["gold_delta"] += int(y.get("gold", 0)) - int(up.get("gold", 0))
        eco[f]["food_delta"] += int(y.get("food", 0)) - int(up.get("food", 0))
        eco[f]["pop_cap"] += int(cfg.get("pop_cap", 0))

    # units
    for u in units:
        f = getattr(u, "faction", None)
        if f not in eco:
            continue
        ut = getattr(u, "unit_type", "worker")
        cfg = UNITS.get(ut, {})
        up = cfg.get("upkeep", {}) or {}
        eco[f]["gold_delta"] -= int(up.get("gold", 0))
        eco[f]["food_delta"] -= int(up.get("food", 0))
        eco[f]["pop"] += int(cfg.get("pop_used", 1))

    game_state["economy"] = eco


def _apply_end_turn_economy(game_state: dict, faction_id: str):
    """Применяем изменение ресурсов на склад (gold/food) по delta."""
    eco = game_state.get("economy", {}).get(faction_id)
    if not isinstance(eco, dict):
        return
    eco["gold"] = int(eco.get("gold", 0)) + int(eco.get("gold_delta", 0))
    eco["food"] = int(eco.get("food", 0)) + int(eco.get("food_delta", 0))


def _can_spend(game_state: dict, faction_id: str, *, gold_cost: int, food_cost: int) -> bool:
    eco = game_state.get("economy", {}).get(faction_id, {})
    gold = int(eco.get("gold", 0))
    food = int(eco.get("food", 0))

    if BLOCK_SPEND_WHEN_NEGATIVE:
        if gold < 0 and gold_cost > 0:
            return False
        if food < 0 and food_cost > 0:
            return False

    # нельзя, если не хватает
    if gold < gold_cost:
        return False
    if food < food_cost:
        return False
    return True


def _spend(game_state: dict, faction_id: str, *, gold_cost: int, food_cost: int):
    eco = game_state.get("economy", {}).get(faction_id, {})
    eco["gold"] = int(eco.get("gold", 0)) - int(gold_cost)
    eco["food"] = int(eco.get("food", 0)) - int(food_cost)


# ------------------- Fog helpers -------------------
def _build_vision_sources_for_faction(faction_id: str, buildings, units: list[Unit]) -> list[VisionSource]:
    src: list[VisionSource] = []

    for b in (buildings or []):
        if b.get("faction") != faction_id:
            continue
        bt = b.get("type")
        cfg = BUILDINGS.get(bt, {})
        vr = int(cfg.get("vision", 3))
        src.append(VisionSource(int(b["x"]), int(b["y"]), vr))

    for u in units:
        if getattr(u, "faction", None) != faction_id:
            continue
        vr = int(getattr(u, "vision", VISION_RADIUS_UNIT))
        src.append(VisionSource(int(u.x), int(u.y), vr))

    return src

def _update_fog_for_faction(game_state: dict, faction_id: str, buildings, units: list[Unit]):
    fog: FogOfWar = game_state["fog"]
    sources = _build_vision_sources_for_faction(faction_id, buildings, units)
    fog.update_from_sources(faction_id, sources)


def _update_fog_for_all_active(game_state: dict, active_factions: list[str], buildings, units: list[Unit]):
    for f in active_factions:
        _update_fog_for_faction(game_state, f, buildings, units)


# ------------------- building / spawn helpers -------------------
def _find_building_at(buildings, x: int, y: int):
    for b in (buildings or []):
        if int(b["x"]) == x and int(b["y"]) == y:
            return b
    return None


def _occupied_tiles(buildings, units: list[Unit]) -> set[tuple[int, int]]:
    occ = set()
    for b in (buildings or []):
        occ.add((int(b["x"]), int(b["y"])))
    for u in units:
        occ.add((int(u.x), int(u.y)))
    return occ


def _spawn_zone_tiles_for_building(
    *,
    center_xy: tuple[int, int],
    radius: int,
    game_map,
    buildings,
    units: list[Unit],
    fog: FogOfWar,
    faction_id: str,
) -> list[tuple[int, int]]:
    cx, cy = center_xy
    rr = radius * radius
    occupied = _occupied_tiles(buildings, units)

    tiles: list[tuple[int, int]] = []
    x0 = max(0, cx - radius)
    x1 = min(MAP_WIDTH - 1, cx + radius)
    y0 = max(0, cy - radius)
    y1 = min(MAP_HEIGHT - 1, cy + radius)

    for y in range(y0, y1 + 1):
        dy = y - cy
        for x in range(x0, x1 + 1):
            dx = x - cx
            if dx * dx + dy * dy > rr:
                continue
            if not fog.is_visible_now(faction_id, x, y):
                continue
            if game_map[y][x] in ("water", "deep_water"):
                continue
            if (x, y) in occupied:
                continue
            tiles.append((x, y))

    return tiles


def _buildable_tiles_for_faction(
    *,
    faction_id: str,
    game_map,
    buildings,
    units: list[Unit],
    fog: FogOfWar,
) -> list[tuple[int, int]]:
    """
    Правила:
    - только видимые клетки
    - нельзя вода/глубокая вода
    - нельзя поверх юнитов/зданий
    - до ближайшего здания своей фракции <= 4 (chebyshev)
    - минимум 1 клетка между зданиями => chebyshev <= 1 запрещено (включая диагональ)
    """
    own = [b for b in (buildings or []) if b.get("faction") == faction_id]
    if not own:
        return []

    occupied = _occupied_tiles(buildings, units)

    res: list[tuple[int, int]] = []
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            if (x, y) in occupied:
                continue
            if game_map[y][x] in ("water", "deep_water"):
                continue
            if not fog.is_visible_now(faction_id, x, y):
                continue

            too_close = False
            nearest = 10**9

            for b in own:
                bx, by = int(b["x"]), int(b["y"])
                d = _chebyshev((x, y), (bx, by))
                nearest = min(nearest, d)
                if d <= BUILD_MIN_GAP:
                    too_close = True
                    break

            if too_close:
                continue
            if nearest > BUILD_MAX_DIST:
                continue

            res.append((x, y))

    return res


def run_game_scene(
    screen: pygame.Surface,
    clock: pygame.time.Clock,
    *,
    font: pygame.font.Font,
    small_font: pygame.font.Font,
    music: MusicManager,
    sfx: SfxManager,
    game_state: dict,
):
    # --- init world ---
    if game_state.get("game_map") is None:
        game_state["game_map"] = generate_map(MAP_WIDTH, MAP_HEIGHT)
        game_state["units"] = []

    game_map = game_state["game_map"]
    units: list[Unit] = game_state["units"]

    # buildings list
    if game_state.get("buildings") is None:
        game_state["buildings"] = []
    buildings = game_state["buildings"]

    # --- UI/state ---
    top_tab = game_state.get("top_tab") or "game"
    selected_building = game_state.get("selected_building")

    placing_building = bool(game_state.get("placing_building", False))
    selected_building_type: str | None = game_state.get("selected_building_type")

    placing_unit = bool(game_state.get("placing_unit", False))
    selected_unit_type: str | None = game_state.get("selected_unit_type")

    build_menu_index = int(game_state.get("build_menu_index", 0))

    # --- roles ---
    faction_roles = game_state.get("faction_roles")
    if not isinstance(faction_roles, dict):
        faction_roles = None

    if faction_roles is None and isinstance(game_state.get("players"), list):
        tmp = {f: None for f in FACTIONS}
        for p in game_state["players"]:
            f = p.get("faction")
            t = p.get("type")
            if f in FACTIONS and t in ("human", "ai"):
                tmp[f] = t
        faction_roles = tmp

    if faction_roles is None:
        faction_roles = {f: "human" for f in FACTIONS}

    game_state["faction_roles"] = faction_roles

    # --- active factions ---
    if game_state.get("active_factions") is None:
        game_state["active_factions"] = _get_active_factions_from_roles(faction_roles)
    active_factions: list[str] = game_state["active_factions"]
    if not active_factions:
        return "main_menu"

    # --- initial buildings (citadels) ---
    if not buildings:
        buildings[:] = _generate_citadels_for_factions(game_map, active_factions, min_dist=20)

    # --- economy init + deltas ---
    _ensure_economy(game_state, active_factions)
    _recalc_deltas_and_pop(game_state, active_factions, buildings, units)

    # --- Fog init ---
    if game_state.get("fog") is None:
        game_state["fog"] = FogOfWar(MAP_WIDTH, MAP_HEIGHT, active_factions)
        _update_fog_for_all_active(game_state, active_factions, buildings, units)
    fog: FogOfWar = game_state["fog"]

    # --- music ---
    music.stop_music()
    music.reset_menu_flag()
    music.play_random_game_music()
    music.check_game_music()
    target_music_volume = int(getattr(music, "volume", 50))

    def ensure_music_running():
        music.check_game_music()

    big_font = font

    # ------------------- duck helpers -------------------
    def _ensure_duck_state():
        if "music_duck" not in game_state:
            game_state["music_duck"] = {"cur": 1.0, "start": 1.0, "target": 1.0, "t": 0.0, "dur": 0.0}

    def _set_duck_immediate(value: float):
        _ensure_duck_state()
        st = game_state["music_duck"]
        v = max(0.0, min(1.0, float(value)))
        st["cur"] = v
        st["start"] = v
        st["target"] = v
        st["t"] = 0.0
        st["dur"] = 0.0
        try:
            music.set_duck(v)
        except Exception:
            pass

    def _start_duck_fade(target: float, duration: float):
        _ensure_duck_state()
        st = game_state["music_duck"]
        tgt = max(0.0, min(1.0, float(target)))
        dur = max(0.0, float(duration))

        if abs(float(st["cur"]) - tgt) < 1e-4:
            st["cur"] = tgt
            st["start"] = tgt
            st["target"] = tgt
            st["t"] = 0.0
            st["dur"] = 0.0
            try:
                music.set_duck(tgt)
            except Exception:
                pass
            return

        st["start"] = float(st["cur"])
        st["target"] = tgt
        st["t"] = 0.0
        st["dur"] = dur

    def _update_duck(dt: float):
        _ensure_duck_state()
        st = game_state["music_duck"]
        dur = float(st.get("dur", 0.0))

        if dur <= 0.0:
            try:
                music.set_duck(float(st["cur"]))
            except Exception:
                pass
            return

        st["t"] = float(st.get("t", 0.0)) + float(dt)
        k = min(1.0, st["t"] / dur)
        cur = float(st["start"]) + (float(st["target"]) - float(st["start"])) * k
        st["cur"] = cur
        try:
            music.set_duck(cur)
        except Exception:
            pass

        if k >= 1.0:
            st["cur"] = float(st["target"])
            st["start"] = float(st["target"])
            st["t"] = 0.0
            st["dur"] = 0.0

    def is_human_faction(faction: str | None) -> bool:
        return faction is not None and faction_roles.get(faction) == "human"

    def is_ai_faction(faction: str | None) -> bool:
        return faction is not None and faction_roles.get(faction) == "ai"

    # --- init order with dice cutscene ---
    if game_state.get("turn_order") is None:
        _, turn_order = run_turn_order_cutscene(
            screen, clock, big_font, small_font, music, sfx, active_factions=active_factions
        )
        if not turn_order:
            return "exit"

        game_state["turn_order"] = turn_order
        game_state["turn_index"] = 0
        game_state["major_turn"] = 1
        game_state["current_faction"] = turn_order[0]

        if is_ai_faction(game_state["current_faction"]):
            _set_duck_immediate(AI_MUSIC_DUCK)
        else:
            _set_duck_immediate(1.0)

        _reset_moves_for_faction(units, game_state["current_faction"])

        selected_building = None
        top_tab = "game"
        placing_building = False
        placing_unit = False
        selected_building_type = None
        selected_unit_type = None

        _update_fog_for_faction(game_state, game_state["current_faction"], buildings, units)
        ensure_music_running()

        bg_from = screen.copy()
        bg_to = _make_game_surface(game_map, buildings, units, screen, fog=fog, view_faction=game_state["current_faction"])

        cf = game_state["current_faction"]
        if is_ai_faction(cf):
            run_turn_transition_cutscene(
                screen, clock, big_font, small_font, music,
                background_from=bg_from, background_to=bg_to,
                line1=f"Ходит ИИ {FACTION_NAMES_RU.get(cf, cf)}", line2="",
                fade_in_duration=0.0, hold_duration=1.0, fade_out_duration=0.0,
                music_fade_in=True, target_music_volume=target_music_volume,
            )
        else:
            run_turn_transition_cutscene(
                screen, clock, big_font, small_font, music,
                background_from=bg_from, background_to=bg_to,
                line1=f"Ход {FACTION_NAMES_RU.get(cf, cf)}", line2="",
                fade_in_duration=0.0, hold_duration=1.0, fade_out_duration=0.8,
                music_fade_in=True, target_music_volume=target_music_volume,
            )

    turn_order: list[str] = game_state.get("turn_order") or []
    turn_index: int = game_state.get("turn_index", 0)
    major_turn: int = game_state.get("major_turn", 1)
    current_faction: str | None = game_state.get("current_faction")

    def is_unit_move_locked(u: Unit) -> bool:
        return getattr(u, "created_major_turn", -10**9) == major_turn

    def _format_turn_economy_text() -> str:
        if not current_faction:
            return "Нет активных фракций"

        eco = game_state.get("economy", {}).get(current_faction, {})
        gold = int(eco.get("gold", 0))
        food = int(eco.get("food", 0))
        gd = int(eco.get("gold_delta", 0))
        fd = int(eco.get("food_delta", 0))
        pop = int(eco.get("pop", 0))
        pop_cap = int(eco.get("pop_cap", 0))

        return (
            f"Ход: {major_turn}, "
            f"Золото: {gold} ({gd:+d}), "
            f"Еда: {food} ({fd:+d}), "
            f"Население: {pop} / {pop_cap}"
        )

    def advance_turn_once():
        nonlocal turn_index, major_turn, current_faction
        nonlocal selected_building, top_tab, placing_building, placing_unit
        nonlocal selected_building_type, selected_unit_type

        if not turn_order:
            return None

        # close modes/selection
        _clear_selection(units)
        selected_building = None
        placing_building = False
        placing_unit = False
        selected_building_type = None
        selected_unit_type = None
        top_tab = "game"

        # apply economy for previous faction
        prev_faction = current_faction
        if prev_faction:
            _recalc_deltas_and_pop(game_state, active_factions, buildings, units)
            _apply_end_turn_economy(game_state, prev_faction)

        # advance index/turn
        turn_index += 1
        if turn_index >= len(turn_order):
            turn_index = 0
            major_turn += 1

        current_faction = turn_order[turn_index]
        game_state["turn_index"] = turn_index
        game_state["major_turn"] = major_turn
        game_state["current_faction"] = current_faction

        _reset_moves_for_faction(units, current_faction)

        _recalc_deltas_and_pop(game_state, active_factions, buildings, units)
        _update_fog_for_faction(game_state, current_faction, buildings, units)

        if is_ai_faction(current_faction):
            _start_duck_fade(AI_MUSIC_DUCK, DUCK_FADE_SECONDS)
        else:
            _start_duck_fade(1.0, DUCK_FADE_SECONDS)

        ensure_music_running()
        return current_faction

    def run_ai_chain_until_human(start_ai_faction: str):
        nonlocal current_faction
        ai_current = start_ai_faction

        while True:
            hold = random.uniform(5.0, 7.0)
            elapsed = 0.0
            while elapsed < hold:
                dt = clock.tick(60) / 1000.0
                elapsed += dt
                _update_duck(dt)
                ensure_music_running()

                for e in pygame.event.get():
                    if e.type == pygame.QUIT:
                        return

                screen.fill((0, 0, 0))
                pygame.display.flip()

            bg_from2 = screen.copy()
            nxt2 = advance_turn_once()
            if not nxt2:
                return

            bg_to2 = _make_game_surface(game_map, buildings, units, screen, fog=fog, view_faction=nxt2)

            if is_human_faction(nxt2):
                run_turn_transition_cutscene(
                    screen, clock, big_font, small_font, music,
                    background_from=bg_from2, background_to=bg_to2,
                    line1=f"Конец хода ИИ {FACTION_NAMES_RU.get(ai_current, ai_current)}",
                    line2=f"Ход {FACTION_NAMES_RU.get(nxt2, nxt2)}",
                    fade_in_duration=0.6, hold_duration=1.0, fade_out_duration=0.6,
                )
                ensure_music_running()
                return

            run_turn_transition_cutscene(
                screen, clock, big_font, small_font, music,
                background_from=bg_from2, background_to=bg_to2,
                line1=f"Конец хода ИИ {FACTION_NAMES_RU.get(ai_current, ai_current)}",
                line2=f"Ходит ИИ {FACTION_NAMES_RU.get(nxt2, nxt2)}",
                fade_in_duration=0.6, hold_duration=1.0, fade_out_duration=0.0,
            )
            ensure_music_running()
            ai_current = nxt2

    if current_faction and is_ai_faction(current_faction):
        ensure_music_running()
        run_ai_chain_until_human(current_faction)

    # ---------- map click helpers ----------
    def is_click_on_map(pos, *, map_offset_y: int, origin_x: int, tile: int) -> bool:
        x, y = pos
        return (origin_x <= x < origin_x + MAP_WIDTH * tile) and (map_offset_y <= y < map_offset_y + MAP_HEIGHT * tile)

    def pos_to_tile(pos, *, map_offset_y: int, origin_x: int, tile: int):
        x, y = pos
        return (x - origin_x) // tile, (y - map_offset_y) // tile

    # ---------- button layout helper ----------
    def _layout_row_buttons(x0: int, x1: int, y: int, h: int, base_widths: list[int], gap: int) -> list[pygame.Rect]:
        avail_w = max(1, x1 - x0)
        total_gaps = gap * (len(base_widths) - 1)
        want_w = sum(base_widths) + total_gaps

        if want_w > avail_w:
            scale_w = max(0.1, (avail_w - total_gaps) / max(1, sum(base_widths)))
            widths = [max(60, int(w * scale_w)) for w in base_widths]
        else:
            widths = base_widths[:]

        rects = []
        x = x0
        for w in widths:
            rects.append(pygame.Rect(x, y, w, h))
            x += w + gap
        return rects

    # ---------- main loop ----------
    while True:
        dt = clock.tick(60) / 1000.0
        _update_duck(dt)

        mouse_pos = pygame.mouse.get_pos()
        ensure_music_running()

        scale, tile, top_h, bottom_h, _, _, _, origin_x, bottom_y, map_offset_y = _compute_scale_and_layout(screen)

        def S(v: int) -> int:
            return max(1, int(v * scale))

        W, H = screen.get_size()

        # update UI deltas
        _recalc_deltas_and_pop(game_state, active_factions, buildings, units)

        # ---------- TOP UI ----------
        row_h = top_h // 2
        top_pad_x = S(10)
        top_gap = S(10)

        btn_h = max(24, int(row_h * 0.70))
        btn_y_row1 = int((row_h - btn_h) / 2)
        btn_y_row2 = row_h + int((row_h - btn_h) / 2)

        base_w_top = [S(140), S(180), S(200)]
        r_game, r_buildings, r_settings = _layout_row_buttons(
            x0=top_pad_x, x1=W - top_pad_x, y=btn_y_row1, h=btn_h, base_widths=base_w_top, gap=top_gap
        )

        can_act = bool(current_faction and is_human_faction(current_faction))

        # row2
        build_buttons: list[tuple[str, pygame.Rect]] = []
        train_buttons: list[tuple[str, pygame.Rect]] = []
        nav_left = nav_right = None

        # (A) BUILDINGS TAB -> scroll menu
        if can_act and top_tab == "buildings" and not placing_unit and not placing_building:
            visible_count = 3
            total = len(BUILD_MENU_ORDER)
            max_index = max(0, total - visible_count)
            build_menu_index = max(0, min(build_menu_index, max_index))

            widths = [S(80)] + [S(260)] * visible_count + [S(80)]
            rects = _layout_row_buttons(
                x0=top_pad_x, x1=W - top_pad_x, y=btn_y_row2, h=btn_h, base_widths=widths, gap=top_gap
            )
            nav_left = rects[0]
            nav_right = rects[-1]
            mid = rects[1:-1]

            for i in range(visible_count):
                idx = build_menu_index + i
                if 0 <= idx < total:
                    bid = BUILD_MENU_ORDER[idx]
                    build_buttons.append((bid, mid[i]))

        # (B) selected building -> train menu (first 3)
        if can_act and selected_building and not placing_unit and not placing_building:
            if selected_building.get("faction") == current_faction:
                btype = selected_building.get("type")
                cfg = BUILDINGS.get(btype, {})
                train = list(cfg.get("train_units", []) or [])
                if train:
                    visible = train[:3]
                    widths = [S(260)] * len(visible)
                    rects = _layout_row_buttons(
                        x0=top_pad_x, x1=W - top_pad_x, y=btn_y_row2, h=btn_h, base_widths=widths, gap=top_gap
                    )
                    for uid, rr in zip(visible, rects):
                        train_buttons.append((uid, rr))

        # ---------- bottom ----------
        bot_pad_x = S(10)
        bot_gap = S(10)
        btn_h_bot = max(22, int(bottom_h * 0.70))
        btn_y_bot = bottom_y + int((bottom_h - btn_h_bot) / 2)
        base_w_bot = [S(230), S(230), S(230)]
        bottom_gen, bottom_exit, bottom_end_turn = _layout_row_buttons(
            x0=bot_pad_x, x1=W - bot_pad_x, y=btn_y_bot, h=btn_h_bot, base_widths=base_w_bot, gap=bot_gap
        )

        # ---------- input ----------
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game_state["game_map"] = game_map
                game_state["units"] = units
                game_state["buildings"] = buildings
                game_state["top_tab"] = top_tab
                game_state["selected_building"] = selected_building
                game_state["placing_building"] = placing_building
                game_state["selected_building_type"] = selected_building_type
                game_state["placing_unit"] = placing_unit
                game_state["selected_unit_type"] = selected_unit_type
                game_state["build_menu_index"] = build_menu_index
                return "exit"

            if event.type == pygame.MOUSEBUTTONDOWN:
                # tabs
                if r_game.collidepoint(event.pos):
                    top_tab = "game"
                    placing_building = False
                    placing_unit = False
                    selected_building_type = None
                    selected_unit_type = None

                elif r_buildings.collidepoint(event.pos):
                    top_tab = "buildings"
                    selected_building = None
                    placing_unit = False
                    selected_unit_type = None

                elif r_settings.collidepoint(event.pos):
                    game_state["game_map"] = game_map
                    game_state["units"] = units
                    game_state["buildings"] = buildings
                    game_state["top_tab"] = top_tab
                    game_state["selected_building"] = selected_building
                    game_state["placing_building"] = placing_building
                    game_state["selected_building_type"] = selected_building_type
                    game_state["placing_unit"] = placing_unit
                    game_state["selected_unit_type"] = selected_unit_type
                    game_state["build_menu_index"] = build_menu_index
                    music.stop_music()
                    return "settings"

                # row2 nav
                if nav_left and nav_left.collidepoint(event.pos):
                    build_menu_index = max(0, build_menu_index - 1)
                if nav_right and nav_right.collidepoint(event.pos):
                    visible_count = 3
                    max_index = max(0, len(BUILD_MENU_ORDER) - visible_count)
                    build_menu_index = min(max_index, build_menu_index + 1)

                # click build choice
                for bid, rr in build_buttons:
                    if rr.collidepoint(event.pos):
                        if current_faction and can_act:
                            cfg = BUILDINGS.get(bid, {})
                            cost = cfg.get("cost", {}) or {}
                            gc = int(cost.get("gold", 0))
                            fc = int(cost.get("food", 0))
                            if _can_spend(game_state, current_faction, gold_cost=gc, food_cost=fc):
                                placing_building = True
                                selected_building_type = bid
                                selected_building = None
                                placing_unit = False
                                selected_unit_type = None
                            else:
                                sfx.play_unit_select()
                        break

                # click train choice
                for uid, rr in train_buttons:
                    if rr.collidepoint(event.pos):
                        if current_faction and can_act and selected_building and selected_building.get("faction") == current_faction:
                            ucfg = UNITS.get(uid, {})
                            cost = ucfg.get("cost", {}) or {}
                            gc = int(cost.get("gold", 0))
                            fc = int(cost.get("food", 0))
                            if _can_spend(game_state, current_faction, gold_cost=gc, food_cost=fc):
                                placing_unit = True
                                selected_unit_type = uid
                                placing_building = False
                                selected_building_type = None
                            else:
                                sfx.play_unit_select()
                        break

                # bottom
                if bottom_gen.collidepoint(event.pos):
                    game_map = generate_map(MAP_WIDTH, MAP_HEIGHT)
                    units.clear()
                    buildings[:] = _generate_citadels_for_factions(game_map, active_factions, min_dist=20)

                    game_state["game_map"] = game_map
                    game_state["units"] = units
                    game_state["buildings"] = buildings

                    game_state["turn_order"] = None
                    game_state["turn_index"] = 0
                    game_state["major_turn"] = 1
                    game_state["current_faction"] = None

                    game_state["economy"] = {}
                    _ensure_economy(game_state, active_factions)
                    _recalc_deltas_and_pop(game_state, active_factions, buildings, units)

                    selected_building = None
                    top_tab = "game"
                    placing_building = False
                    selected_building_type = None
                    placing_unit = False
                    selected_unit_type = None
                    build_menu_index = 0

                    game_state["fog"] = FogOfWar(MAP_WIDTH, MAP_HEIGHT, active_factions)
                    fog = game_state["fog"]
                    _update_fog_for_all_active(game_state, active_factions, buildings, units)

                    _, new_order = run_turn_order_cutscene(
                        screen, clock, big_font, small_font, music, sfx, active_factions=active_factions
                    )
                    if not new_order:
                        return "exit"

                    game_state["turn_order"] = new_order
                    turn_order = new_order
                    turn_index = 0
                    major_turn = 1
                    current_faction = new_order[0]
                    game_state["turn_index"] = 0
                    game_state["major_turn"] = 1
                    game_state["current_faction"] = current_faction

                    if is_ai_faction(current_faction):
                        _set_duck_immediate(AI_MUSIC_DUCK)
                    else:
                        _set_duck_immediate(1.0)

                    _reset_moves_for_faction(units, current_faction)
                    _update_fog_for_faction(game_state, current_faction, buildings, units)
                    ensure_music_running()

                    bg_from = screen.copy()
                    bg_to = _make_game_surface(game_map, buildings, units, screen, fog=fog, view_faction=current_faction)

                    if is_ai_faction(current_faction):
                        run_turn_transition_cutscene(
                            screen, clock, big_font, small_font, music,
                            background_from=bg_from, background_to=bg_to,
                            line1=f"Ходит ИИ {FACTION_NAMES_RU.get(current_faction, current_faction)}", line2="",
                            fade_in_duration=0.0, hold_duration=1.0, fade_out_duration=0.0,
                            music_fade_in=True, target_music_volume=target_music_volume,
                        )
                        ensure_music_running()
                        run_ai_chain_until_human(current_faction)
                    else:
                        run_turn_transition_cutscene(
                            screen, clock, big_font, small_font, music,
                            background_from=bg_from, background_to=bg_to,
                            line1=f"Ход {FACTION_NAMES_RU.get(current_faction, current_faction)}", line2="",
                            fade_in_duration=0.0, hold_duration=1.0, fade_out_duration=0.8,
                            music_fade_in=True, target_music_volume=target_music_volume,
                        )
                        ensure_music_running()

                elif bottom_exit.collidepoint(event.pos):
                    music.stop_music()
                    game_state["game_map"] = game_map
                    game_state["units"] = units
                    game_state["buildings"] = buildings
                    game_state["top_tab"] = top_tab
                    game_state["selected_building"] = selected_building
                    game_state["placing_building"] = placing_building
                    game_state["selected_building_type"] = selected_building_type
                    game_state["placing_unit"] = placing_unit
                    game_state["selected_unit_type"] = selected_unit_type
                    game_state["build_menu_index"] = build_menu_index
                    return "main_menu"

                elif bottom_end_turn.collidepoint(event.pos):
                    if current_faction and is_human_faction(current_faction):
                        prev = current_faction
                        bg_from = screen.copy()
                        nxt = advance_turn_once()
                        if nxt:
                            bg_to = _make_game_surface(game_map, buildings, units, screen, fog=fog, view_faction=nxt)
                            if is_human_faction(nxt):
                                run_turn_transition_cutscene(
                                    screen, clock, big_font, small_font, music,
                                    background_from=bg_from, background_to=bg_to,
                                    line1=f"Конец хода {FACTION_NAMES_RU.get(prev, prev)}",
                                    line2=f"Ход {FACTION_NAMES_RU.get(nxt, nxt)}",
                                    fade_in_duration=0.6, hold_duration=1.0, fade_out_duration=0.6,
                                )
                                ensure_music_running()
                            else:
                                run_turn_transition_cutscene(
                                    screen, clock, big_font, small_font, music,
                                    background_from=bg_from, background_to=bg_to,
                                    line1=f"Конец хода {FACTION_NAMES_RU.get(prev, prev)}",
                                    line2=f"Ходит ИИ {FACTION_NAMES_RU.get(nxt, nxt)}",
                                    fade_in_duration=0.6, hold_duration=1.0, fade_out_duration=0.0,
                                )
                                ensure_music_running()
                                run_ai_chain_until_human(nxt)

                # map clicks
                if is_click_on_map(event.pos, map_offset_y=map_offset_y, origin_x=origin_x, tile=tile):
                    tile_x, tile_y = pos_to_tile(event.pos, map_offset_y=map_offset_y, origin_x=origin_x, tile=tile)
                    if not (0 <= tile_x < MAP_WIDTH and 0 <= tile_y < MAP_HEIGHT):
                        continue

                    if not current_faction:
                        continue

                    if fog.get_state(current_faction, tile_x, tile_y) == FOG_FULL:
                        continue

                    # (1) placing building
                    if placing_building and selected_building_type and can_act:
                        possible = set(_buildable_tiles_for_faction(
                            faction_id=current_faction, game_map=game_map, buildings=buildings, units=units, fog=fog
                        ))
                        if (tile_x, tile_y) in possible:
                            cfg = BUILDINGS.get(selected_building_type, {})
                            cost = cfg.get("cost", {}) or {}
                            gc = int(cost.get("gold", 0))
                            fc = int(cost.get("food", 0))
                            if _can_spend(game_state, current_faction, gold_cost=gc, food_cost=fc):
                                _spend(game_state, current_faction, gold_cost=gc, food_cost=fc)
                                hp = int(cfg.get("hp", 10))
                                buildings.append({
                                    "x": int(tile_x), "y": int(tile_y),
                                    "faction": current_faction, "type": selected_building_type, "hp": hp
                                })
                                _recalc_deltas_and_pop(game_state, active_factions, buildings, units)
                                _update_fog_for_faction(game_state, current_faction, buildings, units)
                                sfx.play_unit_select()
                                placing_building = False
                                selected_building_type = None
                                top_tab = "game"
                        else:
                            placing_building = False
                            selected_building_type = None
                        continue

                    # (2) placing unit
                    if placing_unit and selected_unit_type and selected_building and can_act:
                        if selected_building.get("faction") != current_faction:
                            placing_unit = False
                            selected_unit_type = None
                            continue

                        bx, by = int(selected_building["x"]), int(selected_building["y"])
                        zone = set(_spawn_zone_tiles_for_building(
                            center_xy=(bx, by),
                            radius=SPAWN_RADIUS_AROUND_BUILDING,
                            game_map=game_map,
                            buildings=buildings,
                            units=units,
                            fog=fog,
                            faction_id=current_faction,
                        ))
                        if (tile_x, tile_y) in zone:
                            ucfg = UNITS.get(selected_unit_type, {})
                            cost = ucfg.get("cost", {}) or {}
                            gc = int(cost.get("gold", 0))
                            fc = int(cost.get("food", 0))
                            if _can_spend(game_state, current_faction, gold_cost=gc, food_cost=fc):
                                _spend(game_state, current_faction, gold_cost=gc, food_cost=fc)

                                new_u = Unit(tile_x, tile_y, faction=current_faction, unit_type=selected_unit_type)
                                new_u.created_major_turn = major_turn
                                units.append(new_u)

                                _recalc_deltas_and_pop(game_state, active_factions, buildings, units)
                                _update_fog_for_faction(game_state, current_faction, buildings, units)

                                sfx.play_unit_select()
                                placing_unit = False
                                selected_unit_type = None
                                selected_building = None
                        else:
                            placing_unit = False
                            selected_unit_type = None
                            selected_building = None
                        continue

                    # (3) select building
                    clicked_building = _find_building_at(buildings, tile_x, tile_y)
                    if clicked_building and fog.is_visible_now(current_faction, tile_x, tile_y):
                        selected_building = clicked_building
                        placing_unit = False
                        selected_unit_type = None
                        placing_building = False
                        selected_building_type = None
                        top_tab = "game"
                        _clear_selection(units)
                        continue

                    selected_building = None

                    # (4) unit control
                    if not can_act:
                        continue

                    clicked_unit = None
                    if fog.is_visible_now(current_faction, tile_x, tile_y):
                        for u in units:
                            if (
                                u.x == tile_x
                                and u.y == tile_y
                                and not u.moving
                                and getattr(u, "faction", None) == current_faction
                            ):
                                clicked_unit = u
                                break

                    if clicked_unit:
                        was_selected = clicked_unit.selected
                        _clear_selection(units)
                        clicked_unit.selected = True
                        if not was_selected:
                            sfx.play_unit_select()
                    else:
                        selected_unit = next(
                            (u for u in units if u.selected and not u.moving and getattr(u, "faction", None) == current_faction),
                            None,
                        )
                        if selected_unit and selected_unit.can_move() and not is_unit_move_locked(selected_unit):
                            reachable = selected_unit.get_reachable_tiles(game_map)
                            reachable = [(x, y) for (x, y) in reachable if fog.get_state(current_faction, x, y) != FOG_FULL]
                            if (tile_x, tile_y) in reachable:
                                occ = _occupied_tiles(buildings, units)
                                if (tile_x, tile_y) not in occ:
                                    selected_unit.move_to(tile_x, tile_y, game_map)

        # ---------- updates ----------
        moved_any = False
        moved_factions: set[str] = set()
        for u in units:
            before = (u.x, u.y)
            steps = u.update(dt)
            after = (u.x, u.y)
            for _ in range(steps):
                sfx.play_unit_move()
            if after != before:
                moved_any = True
                f = getattr(u, "faction", None)
                if f:
                    moved_factions.add(f)

        if moved_any:
            for f in moved_factions:
                if f in active_factions:
                    _update_fog_for_faction(game_state, f, buildings, units)

        # ---------- draw world ----------
        screen.fill(BG_COLOR)

        view_faction = current_faction
        draw_map(game_map, screen, offset_y=map_offset_y, origin_x=origin_x, tile_size=tile, fog=fog, faction_id=view_faction)
        draw_bases(buildings, screen, offset_y=map_offset_y, origin_x=origin_x, tile_size=tile, fog=fog, faction_id=view_faction)
        draw_units(units, screen, offset_y=map_offset_y, origin_x=origin_x, tile_size=tile, fog=fog, faction_id=view_faction)

        # highlight movement
        if current_faction and is_human_faction(current_faction) and not placing_unit and not placing_building:
            selected_unit = next(
                (u for u in units if u.selected and not u.moving and getattr(u, "faction", None) == current_faction),
                None,
            )
            if selected_unit and selected_unit.can_move() and not is_unit_move_locked(selected_unit):
                highlight_tiles = selected_unit.get_reachable_tiles(game_map)
                highlight_tiles = [(x, y) for (x, y) in highlight_tiles if fog.get_state(current_faction, x, y) != FOG_FULL]
                occ = _occupied_tiles(buildings, units)
                highlight_tiles = [(x, y) for (x, y) in highlight_tiles if (x, y) not in occ]
                draw_highlight_tiles(
                    screen,
                    highlight_tiles,
                    offset_y=map_offset_y,
                    origin_x=origin_x,
                    tile_size=tile,
                    map_w=MAP_WIDTH,
                    map_h=MAP_HEIGHT,
                    fog=fog,
                    faction_id=current_faction,
                )

        # highlight build placement
        if placing_building and current_faction and is_human_faction(current_faction):
            tiles = _buildable_tiles_for_faction(
                faction_id=current_faction, game_map=game_map, buildings=buildings, units=units, fog=fog
            )
            if tiles:
                draw_highlight_tiles(
                    screen,
                    tiles,
                    offset_y=map_offset_y,
                    origin_x=origin_x,
                    tile_size=tile,
                    map_w=MAP_WIDTH,
                    map_h=MAP_HEIGHT,
                    fog=fog,
                    faction_id=current_faction,
                )

        # highlight unit spawn placement
        if placing_unit and current_faction and is_human_faction(current_faction) and selected_building:
            bx, by = int(selected_building["x"]), int(selected_building["y"])
            zone = _spawn_zone_tiles_for_building(
                center_xy=(bx, by),
                radius=SPAWN_RADIUS_AROUND_BUILDING,
                game_map=game_map,
                buildings=buildings,
                units=units,
                fog=fog,
                faction_id=current_faction,
            )
            if zone:
                draw_highlight_tiles(
                    screen,
                    zone,
                    offset_y=map_offset_y,
                    origin_x=origin_x,
                    tile_size=tile,
                    map_w=MAP_WIDTH,
                    map_h=MAP_HEIGHT,
                    fog=fog,
                    faction_id=current_faction,
                )

        # ---------- draw UI ----------
        pygame.draw.rect(screen, MENU_COLOR, (0, 0, W, top_h))

        draw_button(r_game, ("Игра ✓" if top_tab == "game" else "Игра"), screen, small_font, mouse_pos)
        draw_button(r_buildings, ("Постройки ✓" if top_tab == "buildings" else "Постройки"), screen, small_font, mouse_pos)
        draw_button(r_settings, "Настройки", screen, small_font, mouse_pos)

        # row2: build menu
        if nav_left and nav_right and can_act and top_tab == "buildings" and not placing_unit and not placing_building:
            draw_button(nav_left, "←", screen, small_font, mouse_pos)
            for bid, rr in build_buttons:
                cfg = BUILDINGS.get(bid, {})
                name = str(cfg.get("name", bid))
                cost_g = int((cfg.get("cost", {}) or {}).get("gold", 0))
                draw_button(rr, f"{name} - {cost_g}$", screen, small_font, mouse_pos)
            draw_button(nav_right, "→", screen, small_font, mouse_pos)

        # row2: train menu
        elif train_buttons and can_act and selected_building and not placing_unit and not placing_building:
            for uid, rr in train_buttons:
                ucfg = UNITS.get(uid, {})
                nm = str(ucfg.get("name", uid))
                cg = int((ucfg.get("cost", {}) or {}).get("gold", 0))
                cf = int((ucfg.get("cost", {}) or {}).get("food", 0))
                draw_button(rr, f"{nm} - {cg}$, {cf}🍖", screen, small_font, mouse_pos)

        # info text
        else:
            info_text = _format_turn_economy_text()
            info_surf = small_font.render(info_text, True, (0, 0, 0))
            x = (W - info_surf.get_width()) // 2
            y = btn_y_row2 + (btn_h - info_surf.get_height()) // 2
            x = max(S(10), min(x, W - info_surf.get_width() - S(10)))
            screen.blit(info_surf, (x, y))

        # bottom
        pygame.draw.rect(screen, MENU_COLOR, (0, bottom_y, W, bottom_h))
        draw_button(bottom_gen, "Генерация мира", screen, small_font, mouse_pos)
        draw_button(bottom_exit, "Выход в меню", screen, small_font, mouse_pos)
        draw_button(bottom_end_turn, "Закончить ход", screen, small_font, mouse_pos)

        pygame.display.flip()