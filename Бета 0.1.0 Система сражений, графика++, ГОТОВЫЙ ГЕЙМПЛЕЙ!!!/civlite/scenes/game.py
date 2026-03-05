# civlite/scenes/game.py

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
    START_GOLD,
    START_FOOD,
    BLOCK_SPEND_WHEN_NEGATIVE,
    BUILDINGS,
    UNITS,
    BUILD_MENU_ORDER,
)
from civlite.rendering.draw_utils import (
    draw_map,
    draw_button,
    draw_units,
    draw_highlight_tiles,
    draw_bases,
    draw_attack_tiles,
    draw_health_icons,
)
from civlite.world.map_generator import generate_map
from civlite.entities.unit import Unit
from civlite.audio.music import MusicManager
from civlite.audio.sfx import SfxManager
from civlite.scenes.turn_order_cutscene import run_turn_order_cutscene
from civlite.scenes.turn_transition_cutscene import run_turn_transition_cutscene
from civlite.world.fog_of_war import FogOfWar, VisionSource, FOG_FULL
from civlite.world.combat import resolve_battle_units, resolve_attack_structure


FACTIONS = ["red", "yellow", "blue", "black"]
FACTION_NAMES_RU = {
    "red": "Красные",
    "yellow": "Жёлтые",
    "blue": "Синие",
    "black": "Чёрные",
}

VISION_RADIUS_BASE = 5
VISION_RADIUS_BUILDING = 3

SPAWN_RADIUS_AROUND_BUILDING = 3

BUILD_MAX_DIST = 4
BUILD_MIN_GAP = 1

AI_MUSIC_DUCK = 0.30
DUCK_FADE_SECONDS = 3.0


# ---------------- camera constants ----------------
ZOOM_MIN = 0.60
ZOOM_MAX = 2.80
ZOOM_STEP = 1.12  # per wheel notch
DRAG_CLICK_THRESHOLD_PX = 6

# ---------------- heal economy ----------------
HEAL_COST_PER_HP = 2  # 2 resource for 1 HP


def _is_land_tile(tile: str) -> bool:
    return tile not in ("water", "deep_water")


def _manhattan(a, b) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _chebyshev(a, b) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _generate_citadels_for_factions(game_map, factions: list[str], min_dist: int = 20, max_tries: int = 5000):
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
        buildings.append({"x": x, "y": y, "faction": faction, "type": "citadel", "hp": cit_hp, "max_hp": cit_hp})
    return buildings


def _get_active_factions_from_roles(faction_roles: dict) -> list[str]:
    return [f for f in FACTIONS if faction_roles.get(f) in ("human", "ai")]


def _reset_moves_for_faction(units: list[Unit], faction: str):
    for u in units:
        if getattr(u, "faction", None) == faction:
            u.reset_move()
            # FIX: 1 attack per turn
            u.attacked_this_turn = False


def _clear_selection(units: list[Unit]):
    for u in units:
        u.selected = False


def _ensure_camera(game_state: dict):
    cam = game_state.get("camera")
    if not isinstance(cam, dict):
        cam = {}
    cam.setdefault("zoom", 1.0)
    cam.setdefault("pan_x", 0.0)
    cam.setdefault("pan_y", 0.0)
    cam.setdefault("dragging", False)
    cam.setdefault("drag_start_mouse", (0, 0))
    cam.setdefault("drag_start_pan", (0.0, 0.0))
    cam.setdefault("click_candidate", False)
    game_state["camera"] = cam


def _compute_view_layout(screen: pygame.Surface, *, zoom: float, pan_x: float, pan_y: float):
    W, H = screen.get_size()

    top_h = TOP_UI_HEIGHT * 2
    bottom_h = BOTTOM_UI_HEIGHT
    extra_h = EXTRA_DEBUG_HEIGHT

    game_area_h = max(1, H - top_h - bottom_h)
    game_area_y = top_h

    tile_by_w = max(1, W // MAP_WIDTH)
    tile_by_h = max(1, game_area_h // MAP_HEIGHT)
    tile_fit = max(6, min(tile_by_w, tile_by_h))

    z = max(ZOOM_MIN, min(ZOOM_MAX, float(zoom)))
    tile = max(4, int(tile_fit * z))

    map_px_w = MAP_WIDTH * tile
    map_px_h = MAP_HEIGHT * tile

    origin_center_x = (W - map_px_w) // 2
    origin_center_y = game_area_y + (game_area_h - map_px_h) // 2

    origin_x = int(origin_center_x + pan_x)
    map_offset_y = int(origin_center_y + pan_y)

    bottom_y = H - bottom_h
    ui_scale = W / max(1, SCREEN_WIDTH)

    return ui_scale, tile, top_h, bottom_h, extra_h, map_px_w, map_px_h, origin_x, bottom_y, map_offset_y


def _clamp_camera_to_bounds(game_state: dict, screen: pygame.Surface):
    _ensure_camera(game_state)
    cam = game_state["camera"]

    W, H = screen.get_size()
    top_h = TOP_UI_HEIGHT * 2
    bottom_h = BOTTOM_UI_HEIGHT
    game_area_y = top_h
    game_area_h = max(1, H - top_h - bottom_h)

    _, _, _, _, _, map_px_w, map_px_h, origin_x, _, map_offset_y = _compute_view_layout(
        screen, zoom=cam["zoom"], pan_x=cam["pan_x"], pan_y=cam["pan_y"]
    )

    origin_center_x = (W - map_px_w) // 2
    origin_center_y = game_area_y + (game_area_h - map_px_h) // 2

    if map_px_w >= W:
        min_origin_x = W - map_px_w
        max_origin_x = 0
    else:
        min_origin_x = max_origin_x = origin_center_x

    if map_px_h >= game_area_h:
        min_origin_y = game_area_y + (game_area_h - map_px_h)
        max_origin_y = game_area_y
    else:
        min_origin_y = max_origin_y = origin_center_y

    clamped_origin_x = max(min_origin_x, min(max_origin_x, origin_x))
    clamped_origin_y = max(min_origin_y, min(max_origin_y, map_offset_y))

    cam["pan_x"] = float(clamped_origin_x - origin_center_x)
    cam["pan_y"] = float(clamped_origin_y - origin_center_y)


def _make_game_surface(game_map, buildings, units, screen: pygame.Surface, *, fog: FogOfWar | None, view_faction: str | None, game_state: dict):
    _ensure_camera(game_state)
    _clamp_camera_to_bounds(game_state, screen)
    cam = game_state["camera"]

    W, H = screen.get_size()
    surf = pygame.Surface((W, H))
    surf.fill(BG_COLOR)

    _, tile, _, _, _, _, _, origin_x, _, map_offset_y = _compute_view_layout(
        screen, zoom=cam["zoom"], pan_x=cam["pan_x"], pan_y=cam["pan_y"]
    )

    draw_map(game_map, surf, offset_y=map_offset_y, origin_x=origin_x, tile_size=tile, fog=fog, faction_id=view_faction)
    draw_bases(buildings, surf, offset_y=map_offset_y, origin_x=origin_x, tile_size=tile, fog=fog, faction_id=view_faction)
    draw_units(units, surf, offset_y=map_offset_y, origin_x=origin_x, tile_size=tile, fog=fog, faction_id=view_faction)
    draw_health_icons(surf, buildings=buildings, units=units, offset_y=map_offset_y, origin_x=origin_x, tile_size=tile, fog=fog, faction_id=view_faction)
    return surf


# ------------------- economy -------------------
def _ensure_economy(game_state: dict, active_factions: list[str]):
    eco = game_state.get("economy")
    if not isinstance(eco, dict):
        eco = {}

    for f in active_factions:
        if f not in eco or not isinstance(eco.get(f), dict):
            eco[f] = {}

        eco[f].setdefault("gold", int(START_GOLD))
        eco[f].setdefault("food", int(START_FOOD))

        eco[f].setdefault("gold_delta", 0)
        eco[f].setdefault("food_delta", 0)
        eco[f].setdefault("pop", 0)
        eco[f].setdefault("pop_cap", 0)

    game_state["economy"] = eco


def _recalc_deltas_and_pop(game_state: dict, active_factions: list[str], buildings, units: list[Unit]):
    _ensure_economy(game_state, active_factions)
    eco: dict = game_state["economy"]

    for f in active_factions:
        eco[f]["gold_delta"] = 0
        eco[f]["food_delta"] = 0
        eco[f]["pop"] = 0
        eco[f]["pop_cap"] = 0

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
        bx, by = int(b["x"]), int(b["y"])
        btype = b.get("type")
        radius = VISION_RADIUS_BASE if btype == "citadel" else VISION_RADIUS_BUILDING
        src.append(VisionSource(bx, by, radius))

    for u in units:
        if getattr(u, "faction", None) != faction_id:
            continue
        r = int(getattr(u, "vision", 5))
        src.append(VisionSource(int(u.x), int(u.y), r))

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


def _find_unit_at(units: list[Unit], x: int, y: int) -> Unit | None:
    for u in units:
        if int(u.x) == x and int(u.y) == y:
            return u
    return None


def _food_negative(game_state: dict, faction_id: str) -> bool:
    eco = game_state.get("economy", {}).get(faction_id, {})
    return int(eco.get("food", 0)) < 0


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
    _ensure_camera(game_state)

    if game_state.get("game_map") is None:
        game_state["game_map"] = generate_map(MAP_WIDTH, MAP_HEIGHT)
        game_state["units"] = []

    game_map = game_state["game_map"]
    units: list[Unit] = game_state["units"]

    if game_state.get("buildings") is None:
        game_state["buildings"] = []
    buildings = game_state["buildings"]

    for b in buildings:
        if "max_hp" not in b:
            bt = b.get("type") or "citadel"
            b["max_hp"] = int(BUILDINGS.get(bt, {}).get("hp", b.get("hp", 1)))

    top_tab = game_state.get("top_tab") or "game"
    selected_building = game_state.get("selected_building")

    placing_building = bool(game_state.get("placing_building", False))
    selected_building_type: str | None = game_state.get("selected_building_type")

    placing_unit = bool(game_state.get("placing_unit", False))
    selected_unit_type: str | None = game_state.get("selected_unit_type")

    build_menu_index = int(game_state.get("build_menu_index", 0))
    train_menu_index = int(game_state.get("train_menu_index", 0))

    # explicit mode for showing train menu in row2
    show_train_menu = bool(game_state.get("show_train_menu", False))

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

    if game_state.get("active_factions") is None:
        game_state["active_factions"] = _get_active_factions_from_roles(faction_roles)
    active_factions: list[str] = game_state["active_factions"]
    if not active_factions:
        return "main_menu"

    if not buildings:
        buildings[:] = _generate_citadels_for_factions(game_map, active_factions, min_dist=20)

    _ensure_economy(game_state, active_factions)
    _recalc_deltas_and_pop(game_state, active_factions, buildings, units)

    if game_state.get("fog") is None:
        game_state["fog"] = FogOfWar(MAP_WIDTH, MAP_HEIGHT, active_factions)
        _update_fog_for_all_active(game_state, active_factions, buildings, units)
    fog: FogOfWar = game_state["fog"]

    music.stop_music()
    music.reset_menu_flag()
    music.play_random_game_music()
    music.check_game_music()
    target_music_volume = int(getattr(music, "volume", 50))

    def ensure_music_running():
        music.check_game_music()

    big_font = font

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

    if game_state.get("turn_order") is None:
        _, turn_order = run_turn_order_cutscene(screen, clock, big_font, small_font, music, sfx, active_factions=active_factions)
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
        train_menu_index = 0
        show_train_menu = False
        game_state["show_train_menu"] = False

        _update_fog_for_faction(game_state, game_state["current_faction"], buildings, units)
        ensure_music_running()

        bg_from = screen.copy()
        bg_to = _make_game_surface(game_map, buildings, units, screen, fog=fog, view_faction=game_state["current_faction"], game_state=game_state)

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
        return f"Ход: {major_turn}, Золото: {gold} ({gd:+d}), Еда: {food} ({fd:+d}), Население: {pop}/{pop_cap}"

    def _format_selected_unit_info(u: Unit) -> str:
        ut = getattr(u, "unit_type", "worker")
        cfg = UNITS.get(ut, {})
        name = str(cfg.get("name", ut))
        hp = int(getattr(u, "hp", 1))
        max_hp = int(getattr(u, "max_hp", hp))
        atk = int(getattr(u, "attack", 0))
        mp = int(getattr(u, "move_points", 0))
        mp_max = int(getattr(u, "max_move_points", mp))
        return f"[U] {name} - HP {hp}/{max_hp}, ATK {atk}, MP {mp}/{mp_max}"

    def _format_selected_building_info(b: dict) -> str:
        btype = str(b.get("type", "building"))
        cfg = BUILDINGS.get(btype, {})
        name = str(cfg.get("name", btype))
        hp = int(b.get("hp", 1))
        max_hp = int(b.get("max_hp", hp))
        return f"{name} - {hp}/{max_hp}"

    def _heal_unit_with_food(u: Unit, faction_id: str) -> int:
        hp = int(getattr(u, "hp", 1))
        max_hp = int(getattr(u, "max_hp", hp))
        missing = max(0, max_hp - hp)
        if missing <= 0:
            return 0

        eco = game_state.get("economy", {}).get(faction_id, {})
        food = int(eco.get("food", 0))
        can_hp = max(0, food // HEAL_COST_PER_HP)
        heal = min(missing, can_hp)
        if heal <= 0:
            return 0

        _spend(game_state, faction_id, gold_cost=0, food_cost=heal * HEAL_COST_PER_HP)
        u.hp = hp + heal
        return heal

    def _repair_building_with_gold(b: dict, faction_id: str) -> int:
        hp = int(b.get("hp", 1))
        max_hp = int(b.get("max_hp", hp))
        missing = max(0, max_hp - hp)
        if missing <= 0:
            return 0

        eco = game_state.get("economy", {}).get(faction_id, {})
        gold = int(eco.get("gold", 0))
        can_hp = max(0, gold // HEAL_COST_PER_HP)
        heal = min(missing, can_hp)
        if heal <= 0:
            return 0

        _spend(game_state, faction_id, gold_cost=heal * HEAL_COST_PER_HP, food_cost=0)
        b["hp"] = hp + heal
        return heal

    def advance_turn_once():
        nonlocal turn_index, major_turn, current_faction
        nonlocal selected_building, top_tab, placing_building, placing_unit
        nonlocal selected_building_type, selected_unit_type
        nonlocal train_menu_index, show_train_menu

        if not turn_order:
            return None

        _clear_selection(units)
        selected_building = None
        placing_building = False
        placing_unit = False
        selected_building_type = None
        selected_unit_type = None
        top_tab = "game"
        train_menu_index = 0
        show_train_menu = False
        game_state["show_train_menu"] = False

        prev_faction = current_faction
        if prev_faction:
            _recalc_deltas_and_pop(game_state, active_factions, buildings, units)
            _apply_end_turn_economy(game_state, prev_faction)

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

            bg_to2 = _make_game_surface(game_map, buildings, units, screen, fog=fog, view_faction=nxt2, game_state=game_state)

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

    def is_click_on_map(pos, *, map_offset_y: int, origin_x: int, tile: int) -> bool:
        x, y = pos
        return (origin_x <= x < origin_x + MAP_WIDTH * tile) and (map_offset_y <= y < map_offset_y + MAP_HEIGHT * tile)

    def pos_to_tile(pos, *, map_offset_y: int, origin_x: int, tile: int):
        x, y = pos
        return (x - origin_x) // tile, (y - map_offset_y) // tile

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

    def handle_map_click(tile_x: int, tile_y: int, *, tile: int, origin_x: int, map_offset_y: int, can_act: bool):
        nonlocal selected_building, top_tab, placing_building, placing_unit
        nonlocal selected_building_type, selected_unit_type
        nonlocal train_menu_index, show_train_menu

        if not (0 <= tile_x < MAP_WIDTH and 0 <= tile_y < MAP_HEIGHT):
            return

        if not current_faction:
            return

        if fog.get_state(current_faction, tile_x, tile_y) == FOG_FULL:
            return

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
                        "faction": current_faction, "type": selected_building_type,
                        "hp": hp, "max_hp": hp
                    })
                    _recalc_deltas_and_pop(game_state, active_factions, buildings, units)
                    _update_fog_for_faction(game_state, current_faction, buildings, units)
                    sfx.play_unit_select()
                    placing_building = False
                    selected_building_type = None
                    top_tab = "game"
                    train_menu_index = 0
                    show_train_menu = False
                    game_state["show_train_menu"] = False
            else:
                placing_building = False
                selected_building_type = None
            return

        if placing_unit and selected_unit_type and selected_building and can_act:
            if selected_building.get("faction") != current_faction:
                placing_unit = False
                selected_unit_type = None
                return

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
                    new_u.attacked_this_turn = False  # FIX
                    units.append(new_u)

                    _recalc_deltas_and_pop(game_state, active_factions, buildings, units)
                    _update_fog_for_faction(game_state, current_faction, buildings, units)

                    sfx.play_unit_select()
                    placing_unit = False
                    selected_unit_type = None
                    selected_building = None
                    train_menu_index = 0
                    show_train_menu = False
                    game_state["show_train_menu"] = False
            else:
                placing_unit = False
                selected_unit_type = None
                selected_building = None
            return

        # FIX: allow selecting only OWN buildings. Enemy buildings should not be selected (so attacks can work).
        clicked_building = _find_building_at(buildings, tile_x, tile_y)
        if clicked_building and fog.is_visible_now(current_faction, tile_x, tile_y):
            if clicked_building.get("faction") == current_faction:
                selected_building = clicked_building
                train_menu_index = 0
                placing_unit = False
                selected_unit_type = None
                placing_building = False
                selected_building_type = None
                top_tab = "game"
                show_train_menu = False
                game_state["show_train_menu"] = False
                _clear_selection(units)
                return
            # enemy building: do nothing here (do not return) -> can be attacked below

        if not can_act:
            return

        selected_unit = next(
            (u for u in units if u.selected and not u.moving and getattr(u, "faction", None) == current_faction),
            None,
        )

        if selected_unit:
            # FIX: 1 attack per turn
            if getattr(selected_unit, "attacked_this_turn", False):
                enemy_u = None
                enemy_b = None
            else:
                enemy_u = _find_unit_at(units, tile_x, tile_y)
                enemy_b = _find_building_at(buildings, tile_x, tile_y)

            if enemy_u is not None and enemy_u.faction != current_faction:
                if fog.is_visible_now(current_faction, tile_x, tile_y) and selected_unit.in_attack_range(tile_x, tile_y):
                    res = resolve_battle_units(
                        attacker=selected_unit,
                        defender=enemy_u,
                        attacker_food_negative=_food_negative(game_state, current_faction),
                        defender_food_negative=_food_negative(game_state, enemy_u.faction),
                    )

                    if selected_unit in units:
                        selected_unit.move_points = 0
                        selected_unit.used_negative = True
                        selected_unit.attacked_this_turn = True  # FIX

                    if res.defender_dead and enemy_u in units:
                        sfx.play_unit_death(getattr(enemy_u, "unit_type", "worker"))
                        units.remove(enemy_u)
                    if res.attacker_dead and selected_unit in units:
                        sfx.play_unit_death(getattr(selected_unit, "unit_type", "worker"))
                        units.remove(selected_unit)

                    _clear_selection(units)
                    selected_building = None
                    train_menu_index = 0
                    show_train_menu = False
                    game_state["show_train_menu"] = False
                    _recalc_deltas_and_pop(game_state, active_factions, buildings, units)
                    _update_fog_for_all_active(game_state, active_factions, buildings, units)
                    return

            if enemy_b is not None and enemy_b.get("faction") != current_faction:
                if fog.is_visible_now(current_faction, tile_x, tile_y) and selected_unit.in_attack_range(tile_x, tile_y):
                    destroyed, dmg, roll, eff = resolve_attack_structure(
                        attacker=selected_unit,
                        structure=enemy_b,
                        attacker_food_negative=_food_negative(game_state, current_faction),
                        structure_food_negative=_food_negative(game_state, enemy_b.get("faction")),
                    )

                    if selected_unit in units:
                        selected_unit.move_points = 0
                        selected_unit.used_negative = True
                        selected_unit.attacked_this_turn = True  # FIX

                    if destroyed and enemy_b in buildings:
                        sfx.play_building_destruction()
                        buildings.remove(enemy_b)

                        if enemy_b.get("type") == "citadel":
                            dead_f = enemy_b.get("faction")
                            if dead_f in active_factions:
                                active_factions.remove(dead_f)
                                game_state["turn_order"] = [f for f in (game_state.get("turn_order") or []) if f != dead_f]
                                turn_order[:] = game_state["turn_order"]

                    _clear_selection(units)
                    selected_building = None
                    train_menu_index = 0
                    show_train_menu = False
                    game_state["show_train_menu"] = False
                    _recalc_deltas_and_pop(game_state, active_factions, buildings, units)
                    _update_fog_for_all_active(game_state, active_factions, buildings, units)
                    return

        # unit selection: only own units
        clicked_unit = None
        if fog.is_visible_now(current_faction, tile_x, tile_y):
            for u in units:
                if (
                    u.x == tile_x and u.y == tile_y and not u.moving
                    and getattr(u, "faction", None) == current_faction
                ):
                    clicked_unit = u
                    break

        if clicked_unit:
            was_selected = clicked_unit.selected
            _clear_selection(units)
            clicked_unit.selected = True
            # when selecting a unit, clear building selection + menus
            selected_building = None
            train_menu_index = 0
            show_train_menu = False
            game_state["show_train_menu"] = False
            if not was_selected:
                sfx.play_unit_select()
        else:
            selected_unit2 = next(
                (u for u in units if u.selected and not u.moving and getattr(u, "faction", None) == current_faction),
                None,
            )
            if selected_unit2 and selected_unit2.can_move() and not is_unit_move_locked(selected_unit2):
                # never allow deep_water destinations (even if pathfinder returns them)
                if game_map[tile_y][tile_x] == "deep_water":
                    return

                reachable = selected_unit2.get_reachable_tiles(game_map)
                reachable = [(x, y) for (x, y) in reachable if fog.get_state(current_faction, x, y) != FOG_FULL]
                reachable = [(x, y) for (x, y) in reachable if game_map[y][x] != "deep_water"]
                if (tile_x, tile_y) in reachable:
                    occ = _occupied_tiles(buildings, units)
                    if (tile_x, tile_y) not in occ:
                        selected_unit2.move_to(tile_x, tile_y, game_map)

    # ---------- main loop ----------
    while True:
        dt = clock.tick(60) / 1000.0
        _update_duck(dt)

        mouse_pos = pygame.mouse.get_pos()
        ensure_music_running()

        cam = game_state["camera"]
        _clamp_camera_to_bounds(game_state, screen)

        scale, tile, top_h, bottom_h, _, _, _, origin_x, bottom_y, map_offset_y = _compute_view_layout(
            screen, zoom=cam["zoom"], pan_x=cam["pan_x"], pan_y=cam["pan_y"]
        )

        def S(v: int) -> int:
            return max(1, int(v * scale))

        W, H = screen.get_size()

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

        # selection states for UI row2
        selected_unit_ui = None
        if current_faction:
            selected_unit_ui = next(
                (u for u in units if u.selected and not u.moving and getattr(u, "faction", None) == current_faction),
                None,
            )
        selected_building_ui = selected_building if isinstance(selected_building, dict) else None

        # row2 dynamic buttons
        build_buttons: list[tuple[str, pygame.Rect]] = []
        train_buttons: list[tuple[str, pygame.Rect]] = []
        nav_left = nav_right = None
        train_nav_left = train_nav_right = None

        # action rects
        unit_btn_reinforce = None
        unit_btn_disband = None
        building_btn_repair = None
        building_btn_demolish = None
        building_btn_hire = None
        info_text_row2 = None

        show_train_menu_mode = (
            can_act
            and (selected_building_ui is not None)
            and (selected_building_ui.get("faction") == current_faction)
            and show_train_menu
            and (not placing_unit)
            and (not placing_building)
        )

        show_unit_actions = can_act and selected_unit_ui is not None and not placing_unit and not placing_building
        show_building_actions = (
            can_act
            and selected_building_ui is not None
            and not show_train_menu_mode
            and not placing_unit
            and not placing_building
        )

        if show_building_actions:
            info_text_row2 = _format_selected_building_info(selected_building_ui)

            btype = str(selected_building_ui.get("type", "building"))

            show_hire = btype in ("citadel", "barracks")
            show_repair_demolish = (btype != "citadel") and (selected_building_ui.get("faction") == current_faction)

            # FIX: slightly smaller action buttons
            widths = [S(520)]
            if show_hire:
                widths.append(S(180))
            if show_repair_demolish:
                widths.extend([S(180), S(180)])

            rects = _layout_row_buttons(
                x0=top_pad_x, x1=W - top_pad_x, y=btn_y_row2, h=btn_h, base_widths=widths, gap=top_gap
            )

            idx = 1
            if show_hire:
                building_btn_hire = rects[idx]
                idx += 1
            if show_repair_demolish:
                building_btn_repair = rects[idx]
                building_btn_demolish = rects[idx + 1]

        elif show_unit_actions:
            info_text_row2 = _format_selected_unit_info(selected_unit_ui)

            # FIX: slightly smaller action buttons
            widths = [S(520), S(200), S(200)]
            rects = _layout_row_buttons(
                x0=top_pad_x, x1=W - top_pad_x, y=btn_y_row2, h=btn_h, base_widths=widths, gap=top_gap
            )
            unit_btn_reinforce = rects[1]
            unit_btn_disband = rects[2]

        else:
            # default row2 logic (build menu / train menu / economy text)
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

            # show train buttons only in train-menu mode
            if show_train_menu_mode and selected_building_ui:
                btype = selected_building_ui.get("type")
                cfg = BUILDINGS.get(btype, {})
                train = list(cfg.get("train_units", []) or [])
                if train:
                    visible_count = 3
                    total = len(train)
                    max_index = max(0, total - visible_count)
                    train_menu_index = max(0, min(train_menu_index, max_index))

                    if total > visible_count:
                        widths = [S(80)] + [S(260)] * visible_count + [S(80)]
                        rects = _layout_row_buttons(
                            x0=top_pad_x, x1=W - top_pad_x, y=btn_y_row2, h=btn_h, base_widths=widths, gap=top_gap
                        )
                        train_nav_left = rects[0]
                        train_nav_right = rects[-1]
                        mid = rects[1:-1]
                    else:
                        widths = [S(260)] * total
                        mid = _layout_row_buttons(
                            x0=top_pad_x, x1=W - top_pad_x, y=btn_y_row2, h=btn_h, base_widths=widths, gap=top_gap
                        )

                    visible = train[train_menu_index: train_menu_index + visible_count]
                    for uid, rr in zip(visible, mid):
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
                game_state["train_menu_index"] = train_menu_index
                game_state["show_train_menu"] = show_train_menu
                return "exit"

            # zoom with wheel
            if event.type == pygame.MOUSEWHEEL:
                mx, my = pygame.mouse.get_pos()

                old_zoom = float(cam["zoom"])
                old_pan_x = float(cam["pan_x"])
                old_pan_y = float(cam["pan_y"])

                _, old_tile, _, _, _, _, _, old_origin_x, _, old_map_offset_y = _compute_view_layout(
                    screen, zoom=old_zoom, pan_x=old_pan_x, pan_y=old_pan_y
                )

                if is_click_on_map((mx, my), map_offset_y=old_map_offset_y, origin_x=old_origin_x, tile=old_tile):
                    map_x = (mx - old_origin_x) / max(1, old_tile)
                    map_y = (my - old_map_offset_y) / max(1, old_tile)
                else:
                    map_x = None
                    map_y = None

                factor = (ZOOM_STEP ** event.y) if event.y != 0 else 1.0
                new_zoom = max(ZOOM_MIN, min(ZOOM_MAX, old_zoom * factor))
                cam["zoom"] = new_zoom

                if map_x is not None:
                    _, new_tile, _, _, _, map_px_w, map_px_h, _, _, _ = _compute_view_layout(
                        screen, zoom=new_zoom, pan_x=0.0, pan_y=0.0
                    )
                    W2, H2 = screen.get_size()
                    top_h2 = TOP_UI_HEIGHT * 2
                    bottom_h2 = BOTTOM_UI_HEIGHT
                    game_area_h2 = max(1, H2 - top_h2 - bottom_h2)
                    game_area_y2 = top_h2
                    origin_center_x = (W2 - map_px_w) // 2
                    origin_center_y = game_area_y2 + (game_area_h2 - map_px_h) // 2

                    cam["pan_x"] = float(mx - origin_center_x - map_x * new_tile)
                    cam["pan_y"] = float(my - origin_center_y - map_y * new_tile)

                _clamp_camera_to_bounds(game_state, screen)

            if event.type == pygame.MOUSEBUTTONDOWN:
                # FIX: RMB resets top menu state (exit from any submenu)
                if event.button == 3:
                    top_tab = "game"
                    placing_building = False
                    selected_building_type = None
                    placing_unit = False
                    selected_unit_type = None
                    selected_building = None
                    train_menu_index = 0
                    show_train_menu = False
                    game_state["show_train_menu"] = False
                    _clear_selection(units)

                    cam["dragging"] = False
                    cam["click_candidate"] = False
                    continue

                # start drag if left button pressed on map
                if event.button == 1:
                    if is_click_on_map(event.pos, map_offset_y=map_offset_y, origin_x=origin_x, tile=tile):
                        cam["dragging"] = True
                        cam["drag_start_mouse"] = event.pos
                        cam["drag_start_pan"] = (float(cam["pan_x"]), float(cam["pan_y"]))
                        cam["click_candidate"] = True

                # tabs
                if r_game.collidepoint(event.pos):
                    top_tab = "game"
                    placing_building = False
                    placing_unit = False
                    selected_building_type = None
                    selected_unit_type = None
                    show_train_menu = False
                    game_state["show_train_menu"] = False

                elif r_buildings.collidepoint(event.pos):
                    top_tab = "buildings"
                    selected_building = None
                    placing_unit = False
                    selected_unit_type = None
                    train_menu_index = 0
                    show_train_menu = False
                    game_state["show_train_menu"] = False

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
                    game_state["train_menu_index"] = train_menu_index
                    game_state["show_train_menu"] = show_train_menu
                    music.stop_music()
                    return "settings"

                # --- unit/building action buttons ---
                if can_act and current_faction and is_human_faction(current_faction):
                    # building actions
                    if selected_building_ui is not None and selected_building_ui.get("faction") == current_faction:
                        btype = str(selected_building_ui.get("type", "building"))
                        if building_btn_hire and building_btn_hire.collidepoint(event.pos):
                            # explicit switch to train menu mode
                            show_train_menu = True
                            game_state["show_train_menu"] = True

                            placing_unit = False
                            selected_unit_type = None
                            placing_building = False
                            selected_building_type = None
                            train_menu_index = 0
                            game_state["train_menu_index"] = 0

                            sfx.play_unit_select()

                        if building_btn_repair and building_btn_repair.collidepoint(event.pos):
                            if btype != "citadel":
                                healed = _repair_building_with_gold(selected_building_ui, current_faction)
                                if healed > 0:
                                    _recalc_deltas_and_pop(game_state, active_factions, buildings, units)
                                sfx.play_unit_select()

                        if building_btn_demolish and building_btn_demolish.collidepoint(event.pos):
                            if btype != "citadel":
                                if selected_building_ui in buildings:
                                    buildings.remove(selected_building_ui)
                                selected_building = None
                                selected_building_ui = None
                                train_menu_index = 0
                                show_train_menu = False
                                game_state["show_train_menu"] = False
                                _recalc_deltas_and_pop(game_state, active_factions, buildings, units)
                                _update_fog_for_all_active(game_state, active_factions, buildings, units)
                                sfx.play_building_destruction()

                    # unit actions
                    if selected_unit_ui is not None and getattr(selected_unit_ui, "faction", None) == current_faction:
                        if unit_btn_reinforce and unit_btn_reinforce.collidepoint(event.pos):
                            healed = _heal_unit_with_food(selected_unit_ui, current_faction)
                            if healed > 0:
                                _recalc_deltas_and_pop(game_state, active_factions, buildings, units)
                            sfx.play_unit_select()

                        if unit_btn_disband and unit_btn_disband.collidepoint(event.pos):
                            if selected_unit_ui in units:
                                units.remove(selected_unit_ui)
                            _clear_selection(units)
                            show_train_menu = False
                            game_state["show_train_menu"] = False
                            _recalc_deltas_and_pop(game_state, active_factions, buildings, units)
                            _update_fog_for_all_active(game_state, active_factions, buildings, units)
                            sfx.play_unit_death(getattr(selected_unit_ui, "unit_type", "worker"))

                # row2 nav (buildings)
                if nav_left and nav_left.collidepoint(event.pos):
                    build_menu_index = max(0, build_menu_index - 1)
                if nav_right and nav_right.collidepoint(event.pos):
                    visible_count = 3
                    max_index = max(0, len(BUILD_MENU_ORDER) - visible_count)
                    build_menu_index = min(max_index, build_menu_index + 1)

                # row2 nav (train)
                if train_nav_left and train_nav_left.collidepoint(event.pos):
                    train_menu_index = max(0, train_menu_index - 1)
                if train_nav_right and train_nav_right.collidepoint(event.pos):
                    if selected_building_ui:
                        cfg = BUILDINGS.get(selected_building_ui.get("type"), {})
                        train = list(cfg.get("train_units", []) or [])
                        visible_count = 3
                        max_index = max(0, len(train) - visible_count)
                        train_menu_index = min(max_index, train_menu_index + 1)

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
                                train_menu_index = 0
                                show_train_menu = False
                                game_state["show_train_menu"] = False
                            else:
                                sfx.play_unit_select()
                        break

                # click train choice
                for uid, rr in train_buttons:
                    if rr.collidepoint(event.pos):
                        if current_faction and can_act and selected_building_ui and selected_building_ui.get("faction") == current_faction:
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
                    train_menu_index = 0
                    show_train_menu = False
                    game_state["show_train_menu"] = False

                    game_state["fog"] = FogOfWar(MAP_WIDTH, MAP_HEIGHT, active_factions)
                    fog = game_state["fog"]
                    _update_fog_for_all_active(game_state, active_factions, buildings, units)

                    _, new_order = run_turn_order_cutscene(screen, clock, big_font, small_font, music, sfx, active_factions=active_factions)
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
                    bg_to = _make_game_surface(game_map, buildings, units, screen, fog=fog, view_faction=current_faction, game_state=game_state)

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
                    game_state["train_menu_index"] = train_menu_index
                    game_state["show_train_menu"] = show_train_menu
                    return "main_menu"

                elif bottom_end_turn.collidepoint(event.pos):
                    if current_faction and is_human_faction(current_faction):
                        prev = current_faction
                        bg_from = screen.copy()
                        nxt = advance_turn_once()
                        if nxt:
                            bg_to = _make_game_surface(game_map, buildings, units, screen, fog=fog, view_faction=nxt, game_state=game_state)
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

            if event.type == pygame.MOUSEMOTION:
                if cam["dragging"]:
                    mx, my = event.pos
                    sx, sy = cam["drag_start_mouse"]
                    dx = mx - sx
                    dy = my - sy

                    if abs(dx) >= DRAG_CLICK_THRESHOLD_PX or abs(dy) >= DRAG_CLICK_THRESHOLD_PX:
                        cam["click_candidate"] = False

                    px0, py0 = cam["drag_start_pan"]
                    cam["pan_x"] = float(px0) + float(dx)
                    cam["pan_y"] = float(py0) + float(dy)

                    _clamp_camera_to_bounds(game_state, screen)

            if event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1 and cam["dragging"]:
                    cam["dragging"] = False

                    if cam.get("click_candidate", False):
                        scale, tile, top_h, bottom_h, _, _, _, origin_x, bottom_y, map_offset_y = _compute_view_layout(
                            screen, zoom=cam["zoom"], pan_x=cam["pan_x"], pan_y=cam["pan_y"]
                        )
                        if is_click_on_map(event.pos, map_offset_y=map_offset_y, origin_x=origin_x, tile=tile):
                            tx, ty = pos_to_tile(event.pos, map_offset_y=map_offset_y, origin_x=origin_x, tile=tile)
                            handle_map_click(tx, ty, tile=tile, origin_x=origin_x, map_offset_y=map_offset_y, can_act=can_act)

                    cam["click_candidate"] = False

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
        draw_health_icons(screen, buildings=buildings, units=units, offset_y=map_offset_y, origin_x=origin_x, tile_size=tile, fog=fog, faction_id=view_faction)

        # highlight movement
        if current_faction and is_human_faction(current_faction) and not placing_unit and not placing_building:
            selected_unit = next(
                (u for u in units if u.selected and not u.moving and getattr(u, "faction", None) == current_faction),
                None,
            )
            if selected_unit and selected_unit.can_move() and not is_unit_move_locked(selected_unit):
                highlight_tiles = selected_unit.get_reachable_tiles(game_map)
                highlight_tiles = [(x, y) for (x, y) in highlight_tiles if fog.get_state(current_faction, x, y) != FOG_FULL]
                highlight_tiles = [(x, y) for (x, y) in highlight_tiles if game_map[y][x] != "deep_water"]
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

        # highlight targets
        if current_faction and is_human_faction(current_faction) and not placing_unit and not placing_building:
            selected_unit = next(
                (u for u in units if u.selected and not u.moving and getattr(u, "faction", None) == current_faction),
                None,
            )
            if selected_unit:
                attack_tiles = []

                for enemy in units:
                    if enemy.faction == current_faction:
                        continue
                    if not fog.is_visible_now(current_faction, enemy.x, enemy.y):
                        continue
                    if selected_unit.in_attack_range(enemy.x, enemy.y):
                        attack_tiles.append((int(enemy.x), int(enemy.y)))

                for b in buildings:
                    if b.get("faction") == current_faction:
                        continue
                    bx, by = int(b["x"]), int(b["y"])
                    if not fog.is_visible_now(current_faction, bx, by):
                        continue
                    if selected_unit.in_attack_range(bx, by):
                        attack_tiles.append((bx, by))

                if attack_tiles:
                    draw_attack_tiles(
                        screen,
                        attack_tiles,
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

        draw_button(r_game, ("Игра" if top_tab != "game" else "Игра *"), screen, small_font, mouse_pos)
        draw_button(r_buildings, ("Постройки" if top_tab != "buildings" else "Постройки *"), screen, small_font, mouse_pos)
        draw_button(r_settings, "Настройки", screen, small_font, mouse_pos)

        # Row2 priority: action menus -> build/train -> info text
        if show_building_actions and info_text_row2:
            info_surf = small_font.render(info_text_row2, True, (0, 0, 0))
            x = max(top_pad_x, (W - info_surf.get_width()) // 2)
            x = min(x, W - top_pad_x - info_surf.get_width())
            y = btn_y_row2 + (btn_h - info_surf.get_height()) // 2
            screen.blit(info_surf, (x, y))

            if building_btn_hire:
                draw_button(building_btn_hire, "Нанять", screen, small_font, mouse_pos)
            if building_btn_repair:
                draw_button(building_btn_repair, "Починить", screen, small_font, mouse_pos)
            if building_btn_demolish:
                draw_button(building_btn_demolish, "Снести", screen, small_font, mouse_pos)

        elif show_unit_actions and info_text_row2:
            info_surf = small_font.render(info_text_row2, True, (0, 0, 0))
            x = max(top_pad_x, (W - info_surf.get_width()) // 2)
            x = min(x, W - top_pad_x - info_surf.get_width())
            y = btn_y_row2 + (btn_h - info_surf.get_height()) // 2
            screen.blit(info_surf, (x, y))

            draw_button(unit_btn_reinforce, "Подкрепление", screen, small_font, mouse_pos)
            draw_button(unit_btn_disband, "Распустить", screen, small_font, mouse_pos)

        elif nav_left and nav_right and can_act and top_tab == "buildings" and not placing_unit and not placing_building:
            draw_button(nav_left, "<", screen, small_font, mouse_pos)
            for bid, rr in build_buttons:
                cfg = BUILDINGS.get(bid, {})
                name = str(cfg.get("name", bid))
                cost_g = int((cfg.get("cost", {}) or {}).get("gold", 0))
                draw_button(rr, f"{name} - {cost_g}$", screen, small_font, mouse_pos)
            draw_button(nav_right, ">", screen, small_font, mouse_pos)

        elif train_buttons and can_act and selected_building_ui and show_train_menu_mode and not placing_unit and not placing_building:
            if train_nav_left and train_nav_right:
                draw_button(train_nav_left, "<", screen, small_font, mouse_pos)
                draw_button(train_nav_right, ">", screen, small_font, mouse_pos)

            for uid, rr in train_buttons:
                ucfg = UNITS.get(uid, {})
                nm = str(ucfg.get("name", uid))
                cg = int((ucfg.get("cost", {}) or {}).get("gold", 0))
                cf = int((ucfg.get("cost", {}) or {}).get("food", 0))
                draw_button(rr, f"{nm} - {cg}$, {cf}F", screen, small_font, mouse_pos)

        else:
            info_text = _format_turn_economy_text()
            info_surf = small_font.render(info_text, True, (0, 0, 0))
            x = (W - info_surf.get_width()) // 2
            y = btn_y_row2 + (btn_h - info_surf.get_height()) // 2
            x = max(S(10), min(x, W - info_surf.get_width() - S(10)))
            screen.blit(info_surf, (x, y))

        pygame.draw.rect(screen, MENU_COLOR, (0, bottom_y, W, bottom_h))
        draw_button(bottom_gen, "Генерация мира", screen, small_font, mouse_pos)
        draw_button(bottom_exit, "Выход в меню", screen, small_font, mouse_pos)
        draw_button(bottom_end_turn, "Закончить ход", screen, small_font, mouse_pos)

        pygame.display.flip()