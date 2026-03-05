from __future__ import annotations

import random
import pygame
from civlite.config import (
    SCREEN_WIDTH,
    BG_COLOR,
    MENU_COLOR,
    TILE_SIZE,
    MAP_WIDTH,
    MAP_HEIGHT,
    TOP_UI_HEIGHT,
    BOTTOM_UI_HEIGHT,
    EXTRA_DEBUG_HEIGHT,
)
from civlite.rendering.draw_utils import (
    draw_map,
    draw_button,
    draw_units,
    draw_grid,
    draw_highlight_tiles,
    draw_bases,
)
from civlite.world.map_generator import generate_map
from civlite.entities.unit import Unit
from civlite.audio.music import MusicManager
from civlite.audio.sfx import SfxManager

from civlite.scenes.turn_order_cutscene import run_turn_order_cutscene
from civlite.scenes.turn_transition_cutscene import run_turn_transition_cutscene

FACTIONS = ["red", "yellow", "blue", "black"]
FACTION_NAMES_RU = {
    "red": "Красные",
    "yellow": "Жёлтые",
    "blue": "Синие",
    "black": "Чёрные",
}

# ------------------- Gameplay constants -------------------
BASE_YIELD_GOLD = 2
BASE_YIELD_FOOD = 2
BASE_YIELD_POP_CAP = 5

WORKER_FOOD_UPKEEP = 1
WORKER_GOLD_UPKEEP = 0
WORKER_POP_USED = 1


def _is_land_tile(tile: str) -> bool:
    return tile not in ("water", "deep_water")


def _manhattan(a, b) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _generate_bases_for_factions(game_map, factions: list[str], min_dist: int = 20, max_tries: int = 5000):
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

    bases = []
    for faction, (x, y) in zip(factions, positions[: len(factions)]):
        bases.append({"x": x, "y": y, "faction": faction})
    return bases


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
    """
    ТЗ:
    - Верхнее меню: TOP_UI_HEIGHT * 2 (фикс)
    - Нижнее меню: BOTTOM_UI_HEIGHT (фикс)
    - Лишняя высота уходит в игровую область
    - Карта масштабируется tile (целое число) и центрируется в игровой области
    - UI (кнопки/отступы по X) масштабируется по ширине (ui_scale = W / SCREEN_WIDTH)
    """
    W, H = screen.get_size()

    top_h = TOP_UI_HEIGHT * 2
    bottom_h = BOTTOM_UI_HEIGHT
    extra_h = EXTRA_DEBUG_HEIGHT

    # игровая область по высоте
    game_area_h = max(1, H - top_h - bottom_h)
    game_area_y = top_h

    # tile по ширине/высоте (целый)
    tile_by_w = max(1, W // MAP_WIDTH)
    tile_by_h = max(1, game_area_h // MAP_HEIGHT)
    tile = max(6, min(tile_by_w, tile_by_h))

    map_px_w = MAP_WIDTH * tile
    map_px_h = MAP_HEIGHT * tile

    origin_x = max(0, (W - map_px_w) // 2)
    map_offset_y = game_area_y + max(0, (game_area_h - map_px_h) // 2)

    bottom_y = H - bottom_h

    # панель фракций для debug/add_unit — показываем над нижним меню
    faction_panel_y = bottom_y - extra_h

    ui_scale = W / max(1, SCREEN_WIDTH)
    return ui_scale, tile, top_h, bottom_h, extra_h, map_px_w, map_px_h, origin_x, bottom_y, faction_panel_y, map_offset_y


def _make_game_surface(game_map, bases, units, screen: pygame.Surface) -> pygame.Surface:
    """
    Рендер кадра игры в Surface без flip() — под катсцены.
    """
    W, H = screen.get_size()
    surf = pygame.Surface((W, H))
    surf.fill(BG_COLOR)

    layout = _compute_scale_and_layout(screen)
    tile = layout[1]
    origin_x = layout[7]
    map_offset_y = layout[10]

    draw_map(game_map, surf, offset_y=map_offset_y, origin_x=origin_x, tile_size=tile)
    draw_bases(bases, surf, offset_y=map_offset_y, origin_x=origin_x, tile_size=tile)
    draw_units(units, surf, offset_y=map_offset_y, origin_x=origin_x, tile_size=tile)
    return surf


# ------------------- economy helpers -------------------
def _ensure_economy(game_state: dict, active_factions: list[str]):
    eco = game_state.get("economy")
    if not isinstance(eco, dict):
        eco = {}

    for f in active_factions:
        if f not in eco or not isinstance(eco.get(f), dict):
            eco[f] = {"gold": 0, "food": 0, "pop": 0, "pop_cap": 0}
        eco[f].setdefault("gold", 0)
        eco[f].setdefault("food", 0)
        eco[f].setdefault("pop", 0)
        eco[f].setdefault("pop_cap", 0)

    game_state["economy"] = eco


def _recalc_economy_from_world(game_state: dict, active_factions: list[str], bases, units: list[Unit]):
    _ensure_economy(game_state, active_factions)
    eco: dict = game_state["economy"]

    for f in active_factions:
        eco[f]["gold"] = 0
        eco[f]["food"] = 0
        eco[f]["pop"] = 0
        eco[f]["pop_cap"] = 0

    if bases:
        for b in bases:
            f = b.get("faction")
            if f in eco:
                eco[f]["gold"] += BASE_YIELD_GOLD
                eco[f]["food"] += BASE_YIELD_FOOD
                eco[f]["pop_cap"] += BASE_YIELD_POP_CAP

    for u in units:
        f = getattr(u, "faction", None)
        if f in eco:
            eco[f]["food"] -= WORKER_FOOD_UPKEEP
            eco[f]["gold"] -= WORKER_GOLD_UPKEEP
            eco[f]["pop"] += WORKER_POP_USED

    game_state["economy"] = eco


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

    # --- гарантируем стартовые значения меню ---
    action_mode = game_state.get("action_mode")
    current_menu = game_state.get("current_menu")
    show_bottom = game_state.get("show_bottom", False)
    if current_menu is None:
        current_menu = "game"
        game_state["current_menu"] = "game"
    if not show_bottom:
        show_bottom = True
        game_state["show_bottom"] = True

    spawn_faction = game_state.get("spawn_faction", "red")

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

    # --- bases ---
    if game_state.get("bases") is None:
        game_state["bases"] = _generate_bases_for_factions(game_map, active_factions, min_dist=20)
    bases = game_state["bases"]

    _recalc_economy_from_world(game_state, active_factions, bases, units)

    # --- music ---
    music.stop_music()
    music.reset_menu_flag()
    music.play_random_game_music()
    target_music_volume = int(getattr(music, "volume", 50))

    big_font = font

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
        _reset_moves_for_faction(units, game_state["current_faction"])

        bg_from = screen.copy()
        bg_to = _make_game_surface(game_map, bases, units, screen)

        cf = game_state["current_faction"]
        if is_ai_faction(cf):
            run_turn_transition_cutscene(
                screen,
                clock,
                big_font,
                small_font,
                music,
                background_from=bg_from,
                background_to=bg_to,
                line1=f"Ходит ИИ {FACTION_NAMES_RU.get(cf, cf)}",
                line2="",
                fade_in_duration=0.0,
                hold_duration=1.0,
                fade_out_duration=0.0,
                music_fade_in=True,
                target_music_volume=target_music_volume,
            )
        else:
            run_turn_transition_cutscene(
                screen,
                clock,
                big_font,
                small_font,
                music,
                background_from=bg_from,
                background_to=bg_to,
                line1=f"Ход {FACTION_NAMES_RU.get(cf, cf)}",
                line2="",
                fade_in_duration=0.0,
                hold_duration=1.0,
                fade_out_duration=0.8,
                music_fade_in=True,
                target_music_volume=target_music_volume,
            )

    turn_order: list[str] = game_state.get("turn_order") or []
    turn_index: int = game_state.get("turn_index", 0)
    major_turn: int = game_state.get("major_turn", 1)
    current_faction: str | None = game_state.get("current_faction")

    def advance_turn_once():
        nonlocal turn_index, major_turn, current_faction
        if not turn_order:
            return None

        _clear_selection(units)

        turn_index += 1
        if turn_index >= len(turn_order):
            turn_index = 0
            major_turn += 1

        current_faction = turn_order[turn_index]
        game_state["turn_index"] = turn_index
        game_state["major_turn"] = major_turn
        game_state["current_faction"] = current_faction
        _reset_moves_for_faction(units, current_faction)

        _recalc_economy_from_world(game_state, active_factions, bases, units)
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
                for e in pygame.event.get():
                    if e.type == pygame.QUIT:
                        return
                screen.fill((0, 0, 0))
                pygame.display.flip()

            bg_from2 = screen.copy()
            nxt2 = advance_turn_once()
            if not nxt2:
                return

            bg_to2 = _make_game_surface(game_map, bases, units, screen)

            if is_human_faction(nxt2):
                run_turn_transition_cutscene(
                    screen,
                    clock,
                    big_font,
                    small_font,
                    music,
                    background_from=bg_from2,
                    background_to=bg_to2,
                    line1=f"Конец хода ИИ {FACTION_NAMES_RU.get(ai_current, ai_current)}",
                    line2=f"Ход {FACTION_NAMES_RU.get(nxt2, nxt2)}",
                    fade_in_duration=0.6,
                    hold_duration=1.0,
                    fade_out_duration=0.6,
                )
                return

            run_turn_transition_cutscene(
                screen,
                clock,
                big_font,
                small_font,
                music,
                background_from=bg_from2,
                background_to=bg_to2,
                line1=f"Конец хода ИИ {FACTION_NAMES_RU.get(ai_current, ai_current)}",
                line2=f"Ходит ИИ {FACTION_NAMES_RU.get(nxt2, nxt2)}",
                fade_in_duration=0.6,
                hold_duration=1.0,
                fade_out_duration=0.0,
            )
            ai_current = nxt2

    def run_end_turn_sequence_for_player():
        nonlocal current_faction

        if not current_faction:
            return
        if not is_human_faction(current_faction):
            return

        prev = current_faction
        bg_from = screen.copy()

        nxt = advance_turn_once()
        if not nxt:
            return

        bg_to = _make_game_surface(game_map, bases, units, screen)

        if is_human_faction(nxt):
            run_turn_transition_cutscene(
                screen,
                clock,
                big_font,
                small_font,
                music,
                background_from=bg_from,
                background_to=bg_to,
                line1=f"Конец хода {FACTION_NAMES_RU.get(prev, prev)}",
                line2=f"Ход {FACTION_NAMES_RU.get(nxt, nxt)}",
                fade_in_duration=0.6,
                hold_duration=1.0,
                fade_out_duration=0.6,
            )
            return

        if is_ai_faction(nxt):
            run_turn_transition_cutscene(
                screen,
                clock,
                big_font,
                small_font,
                music,
                background_from=bg_from,
                background_to=bg_to,
                line1=f"Конец хода {FACTION_NAMES_RU.get(prev, prev)}",
                line2=f"Ходит ИИ {FACTION_NAMES_RU.get(nxt, nxt)}",
                fade_in_duration=0.6,
                hold_duration=1.0,
                fade_out_duration=0.0,
            )
            run_ai_chain_until_human(nxt)

    if current_faction and is_ai_faction(current_faction):
        run_ai_chain_until_human(current_faction)

    # ---------- map click helpers ----------
    def is_click_on_map(pos, *, map_offset_y: int, origin_x: int, tile: int) -> bool:
        x, y = pos
        return (origin_x <= x < origin_x + MAP_WIDTH * tile) and (
            map_offset_y <= y < map_offset_y + MAP_HEIGHT * tile
        )

    def pos_to_tile(pos, *, map_offset_y: int, origin_x: int, tile: int):
        x, y = pos
        return (x - origin_x) // tile, (y - map_offset_y) // tile

    # ---------- button layout helper ----------
    def _layout_row_buttons(x0: int, x1: int, y: int, h: int, base_widths: list[int], gap: int) -> list[pygame.Rect]:
        """
        Делает ряд кнопок, который гарантированно влезает в [x0..x1].
        Если суммарная ширина > доступной — ужимает пропорционально.
        """
        avail_w = max(1, x1 - x0)
        n = len(base_widths)
        total_gaps = gap * (n - 1)
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
        mouse_pos = pygame.mouse.get_pos()
        music.check_game_music()

        scale, tile, top_h, bottom_h, extra_h, map_px_w, map_px_h, origin_x, bottom_y, faction_panel_y, map_offset_y = (
            _compute_scale_and_layout(screen)
        )

        def S(v: int) -> int:
            return max(1, int(v * scale))

        W, H = screen.get_size()

        # ---------- UI rects (нормальная адаптация) ----------
        # TOP: 2 rows, кнопки только в верхнем ряду
        row_h = top_h // 2
        top_pad_x = S(10)
        top_gap = S(10)

        btn_h_top = max(24, int(row_h * 0.70))
        btn_y_top = int((row_h - btn_h_top) / 2)

        base_w_top = [S(140), S(140), S(200)]
        r_game, r_debug, r_settings = _layout_row_buttons(
            x0=top_pad_x, x1=W - top_pad_x, y=btn_y_top, h=btn_h_top, base_widths=base_w_top, gap=top_gap
        )
        top_button_game = r_game
        top_button_debug = r_debug
        top_button_settings = r_settings

        # BOTTOM: один ряд по центру высоты bottom_h
        bot_pad_x = S(10)
        bot_gap = S(10)

        btn_h_bot = max(22, int(bottom_h * 0.70))
        btn_y_bot = bottom_y + int((bottom_h - btn_h_bot) / 2)

        base_w_bot = [S(230), S(230), S(230)]
        b1, b2, b3 = _layout_row_buttons(
            x0=bot_pad_x, x1=W - bot_pad_x, y=btn_y_bot, h=btn_h_bot, base_widths=base_w_bot, gap=bot_gap
        )

        bottom_gen = b1
        bottom_exit = b2
        bottom_end_turn = b3

        bottom_add_unit = b1
        bottom_remove_unit = b2
        bottom_exit_action = b3

        # debug faction buttons (панель над нижним меню)
        panel_pad = S(10)
        faction_btn_h = max(22, S(30))
        faction_gap = S(10)

        faction_red = pygame.Rect(panel_pad, faction_panel_y + panel_pad, S(150), faction_btn_h)
        faction_yellow = pygame.Rect(faction_red.right + faction_gap, faction_panel_y + panel_pad, S(150), faction_btn_h)
        faction_blue = pygame.Rect(faction_yellow.right + faction_gap, faction_panel_y + panel_pad, S(150), faction_btn_h)
        faction_black = pygame.Rect(faction_blue.right + faction_gap, faction_panel_y + panel_pad, S(150), faction_btn_h)

        # ---------- input ----------
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game_state["game_map"] = game_map
                game_state["units"] = units
                game_state["action_mode"] = action_mode
                game_state["current_menu"] = current_menu
                game_state["show_bottom"] = show_bottom
                game_state["spawn_faction"] = spawn_faction
                return "exit"

            if event.type == pygame.MOUSEBUTTONDOWN:
                if top_button_game.collidepoint(event.pos):
                    show_bottom = True
                    current_menu = "game"
                    action_mode = None
                elif top_button_debug.collidepoint(event.pos):
                    show_bottom = True
                    current_menu = "debug"
                    action_mode = None
                elif top_button_settings.collidepoint(event.pos):
                    game_state["game_map"] = game_map
                    game_state["units"] = units
                    game_state["action_mode"] = action_mode
                    game_state["current_menu"] = current_menu
                    game_state["show_bottom"] = show_bottom
                    game_state["spawn_faction"] = spawn_faction
                    music.stop_music()
                    return "settings"

                if show_bottom:
                    if current_menu == "game":
                        if bottom_gen.collidepoint(event.pos):
                            game_map = generate_map(MAP_WIDTH, MAP_HEIGHT)
                            units.clear()
                            game_state["game_map"] = game_map
                            game_state["units"] = units

                            game_state["bases"] = _generate_bases_for_factions(game_map, active_factions, min_dist=20)
                            bases = game_state["bases"]

                            game_state["turn_order"] = None
                            game_state["turn_index"] = 0
                            game_state["major_turn"] = 1
                            game_state["current_faction"] = None
                            _clear_selection(units)

                            _recalc_economy_from_world(game_state, active_factions, bases, units)

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
                            _reset_moves_for_faction(units, current_faction)

                            bg_from = screen.copy()
                            bg_to = _make_game_surface(game_map, bases, units, screen)

                            if is_ai_faction(current_faction):
                                run_turn_transition_cutscene(
                                    screen,
                                    clock,
                                    big_font,
                                    small_font,
                                    music,
                                    background_from=bg_from,
                                    background_to=bg_to,
                                    line1=f"Ходит ИИ {FACTION_NAMES_RU.get(current_faction, current_faction)}",
                                    line2="",
                                    fade_in_duration=0.0,
                                    hold_duration=1.0,
                                    fade_out_duration=0.0,
                                    music_fade_in=True,
                                    target_music_volume=target_music_volume,
                                )
                                run_ai_chain_until_human(current_faction)
                            else:
                                run_turn_transition_cutscene(
                                    screen,
                                    clock,
                                    big_font,
                                    small_font,
                                    music,
                                    background_from=bg_from,
                                    background_to=bg_to,
                                    line1=f"Ход {FACTION_NAMES_RU.get(current_faction, current_faction)}",
                                    line2="",
                                    fade_in_duration=0.0,
                                    hold_duration=1.0,
                                    fade_out_duration=0.8,
                                    music_fade_in=True,
                                    target_music_volume=target_music_volume,
                                )

                        elif bottom_exit.collidepoint(event.pos):
                            music.stop_music()
                            game_state["game_map"] = game_map
                            game_state["units"] = units
                            game_state["action_mode"] = action_mode
                            game_state["current_menu"] = current_menu
                            game_state["show_bottom"] = show_bottom
                            game_state["spawn_faction"] = spawn_faction
                            return "main_menu"

                        elif bottom_end_turn.collidepoint(event.pos):
                            if current_faction and is_human_faction(current_faction):
                                run_end_turn_sequence_for_player()

                    elif current_menu == "debug":
                        if bottom_add_unit.collidepoint(event.pos):
                            action_mode = "add_unit"
                        elif bottom_remove_unit.collidepoint(event.pos):
                            action_mode = "remove_unit"
                        elif bottom_exit_action.collidepoint(event.pos):
                            action_mode = None

                        if action_mode == "add_unit":
                            if faction_red.collidepoint(event.pos):
                                spawn_faction = "red"
                            elif faction_yellow.collidepoint(event.pos):
                                spawn_faction = "yellow"
                            elif faction_blue.collidepoint(event.pos):
                                spawn_faction = "blue"
                            elif faction_black.collidepoint(event.pos):
                                spawn_faction = "black"

                if is_click_on_map(event.pos, map_offset_y=map_offset_y, origin_x=origin_x, tile=tile):
                    tile_x, tile_y = pos_to_tile(event.pos, map_offset_y=map_offset_y, origin_x=origin_x, tile=tile)
                    if not (0 <= tile_x < MAP_WIDTH and 0 <= tile_y < MAP_HEIGHT):
                        continue

                    tile_name = game_map[tile_y][tile_x]

                    if action_mode == "add_unit" and tile_name != "deep_water":
                        units.append(Unit(tile_x, tile_y, faction=spawn_faction))
                        _recalc_economy_from_world(game_state, active_factions, bases, units)

                    elif action_mode == "remove_unit":
                        removed = False
                        for u in list(units):
                            if u.x == tile_x and u.y == tile_y:
                                units.remove(u)
                                removed = True
                                break
                        if removed:
                            _recalc_economy_from_world(game_state, active_factions, bases, units)

                    elif action_mode is None:
                        if not (current_faction and is_human_faction(current_faction)):
                            continue

                        clicked_unit = None
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
                                (
                                    u
                                    for u in units
                                    if u.selected
                                    and not u.moving
                                    and getattr(u, "faction", None) == current_faction
                                ),
                                None,
                            )
                            if selected_unit and selected_unit.can_move():
                                reachable = selected_unit.get_reachable_tiles(game_map)
                                if (tile_x, tile_y) in reachable:
                                    selected_unit.move_to(tile_x, tile_y, game_map)

        # ---------- updates ----------
        for u in units:
            steps = u.update(dt)
            for _ in range(steps):
                sfx.play_unit_move()

        # ---------- draw world ----------
        screen.fill(BG_COLOR)
        draw_map(game_map, screen, offset_y=map_offset_y, origin_x=origin_x, tile_size=tile)
        draw_bases(bases, screen, offset_y=map_offset_y, origin_x=origin_x, tile_size=tile)
        draw_units(units, screen, offset_y=map_offset_y, origin_x=origin_x, tile_size=tile)

        if action_mode in ("add_unit", "remove_unit"):
            draw_grid(screen, offset_y=map_offset_y, origin_x=origin_x, tile_size=tile, map_w=MAP_WIDTH, map_h=MAP_HEIGHT)
        else:
            if current_faction and is_human_faction(current_faction):
                selected_unit = next(
                    (
                        u
                        for u in units
                        if u.selected and not u.moving and getattr(u, "faction", None) == current_faction
                    ),
                    None,
                )
                if selected_unit and selected_unit.can_move():
                    highlight_tiles = selected_unit.get_reachable_tiles(game_map)
                    draw_highlight_tiles(
                        screen,
                        highlight_tiles,
                        offset_y=map_offset_y,
                        origin_x=origin_x,
                        tile_size=tile,
                        map_w=MAP_WIDTH,
                        map_h=MAP_HEIGHT,
                    )

        # ---------- top UI ----------
        pygame.draw.rect(screen, MENU_COLOR, (0, 0, W, top_h))
        draw_button(top_button_game, "Игра", screen, small_font, mouse_pos)
        draw_button(top_button_debug, "Дебаг", screen, small_font, mouse_pos)
        draw_button(top_button_settings, "Настройки", screen, small_font, mouse_pos)

        # info text (ряд 1)
        if current_faction:
            role = faction_roles.get(current_faction)
            role_ru = "Игрок" if role == "human" else ("ИИ" if role == "ai" else "???")
            info_text = (
                f"КРУПНЫЙ ХОД: {major_turn} | "
                f"ПОДХОД: {turn_index + 1}/{len(turn_order)} | "
                f"{FACTION_NAMES_RU.get(current_faction, current_faction)} ({role_ru})"
            )
        else:
            info_text = "Нет активных фракций"

        info_surf = small_font.render(info_text, True, (0, 0, 0))
        info_x = top_button_settings.right + S(15)
        info_y = max(2, (row_h - info_surf.get_height()) // 2)
        if info_x < W - 10:
            screen.blit(info_surf, (info_x, info_y))

        # ---------- bottom UI ----------
        if show_bottom:
            pygame.draw.rect(screen, MENU_COLOR, (0, bottom_y, W, bottom_h))

            if current_menu == "game":
                draw_button(bottom_gen, "Генерация мира", screen, small_font, mouse_pos)
                draw_button(bottom_exit, "Выход в меню", screen, small_font, mouse_pos)
                draw_button(bottom_end_turn, "Закончить ход", screen, small_font, mouse_pos)

            elif current_menu == "debug":
                draw_button(bottom_add_unit, "Добавить юнита", screen, small_font, mouse_pos)
                draw_button(bottom_remove_unit, "Удалить юнита", screen, small_font, mouse_pos)

                if action_mode in ("add_unit", "remove_unit"):
                    draw_button(bottom_exit_action, "Выйти из режима", screen, small_font, mouse_pos)

                # панель выбора фракции (над нижним меню)
                if action_mode == "add_unit":
                    panel_y = max(top_h, faction_panel_y)
                    panel_h = min(extra_h, max(0, bottom_y - panel_y))
                    if panel_h > 0:
                        pygame.draw.rect(screen, MENU_COLOR, (0, panel_y, W, panel_h))
                        draw_button(
                            faction_red,
                            "Красные" + (" ✓" if spawn_faction == "red" else ""),
                            screen,
                            small_font,
                            mouse_pos,
                        )
                        draw_button(
                            faction_yellow,
                            "Желтые" + (" ✓" if spawn_faction == "yellow" else ""),
                            screen,
                            small_font,
                            mouse_pos,
                        )
                        draw_button(
                            faction_blue,
                            "Синие" + (" ✓" if spawn_faction == "blue" else ""),
                            screen,
                            small_font,
                            mouse_pos,
                        )
                        draw_button(
                            faction_black,
                            "Черные" + (" ✓" if spawn_faction == "black" else ""),
                            screen,
                            small_font,
                            mouse_pos,
                        )

        pygame.display.flip()
