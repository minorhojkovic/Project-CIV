from __future__ import annotations

import pygame
from civlite.config import SCREEN_WIDTH, SCREEN_HEIGHT, BG_COLOR
from civlite.rendering.draw_utils import draw_button
from civlite.audio.music import MusicManager

BASE_W, BASE_H = SCREEN_WIDTH, SCREEN_HEIGHT

FACTIONS = ["red", "yellow", "blue", "black"]
FACTION_NAMES_RU = {
    "red": "Красные",
    "yellow": "Жёлтые",
    "blue": "Синие",
    "black": "Чёрные",
}

ROLE_CYCLE = [None, "human", "ai"]
ROLE_NAMES_RU = {
    None: "Выкл",
    "human": "Игрок",
    "ai": "ИИ",
}


def _count_active(roles: dict) -> int:
    return sum(1 for f in FACTIONS if roles.get(f) in ("human", "ai"))


def run_setup_scene(
    screen: pygame.Surface,
    clock: pygame.time.Clock,
    font: pygame.font.Font,
    small_font: pygame.font.Font,
    music: MusicManager,
    *,
    faction_roles: dict | None = None,
):
    if faction_roles is None:
        faction_roles = {
            "red": "human",
            "yellow": "ai",
            "blue": "ai",
            "black": "ai",
        }
    else:
        normalized = {}
        for f in FACTIONS:
            v = faction_roles.get(f)
            normalized[f] = v if v in (None, "human", "ai") else None
        faction_roles = normalized

    warning_text = ""

    def cycle_role(faction: str):
        cur = faction_roles.get(faction)
        idx = ROLE_CYCLE.index(cur)
        faction_roles[faction] = ROLE_CYCLE[(idx + 1) % len(ROLE_CYCLE)]

    def role_text(f):
        r = faction_roles.get(f)
        return f"{FACTION_NAMES_RU[f]}: {ROLE_NAMES_RU[r]}"

    while True:
        clock.tick(60)
        music.play_menu_music()

        W, H = screen.get_size()
        scale = min(W / BASE_W, H / BASE_H)

        def S(v: int) -> int:
            return int(v * scale)

        mouse_pos = pygame.mouse.get_pos()

        btn_h = S(42)
        gap = S(10)
        center_x = W // 2

        title_y = H // 6
        content_top = title_y + S(55)

        btn_back = pygame.Rect(S(20), S(20), S(140), S(40))

        t_roles_y = content_top
        row1_y = t_roles_y + S(28)
        row2_y = row1_y + btn_h + gap

        col1_x = center_x - S(240)
        col2_x = center_x + S(10)

        role_red = pygame.Rect(col1_x, row1_y, S(230), btn_h)
        role_yellow = pygame.Rect(col2_x, row1_y, S(230), btn_h)
        role_blue = pygame.Rect(col1_x, row2_y, S(230), btn_h)
        role_black = pygame.Rect(col2_x, row2_y, S(230), btn_h)

        info_y = row2_y + btn_h + S(18)
        btn_start = pygame.Rect(center_x - S(150), info_y + S(20), S(300), S(46))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "exit", faction_roles

            if event.type == pygame.MOUSEBUTTONDOWN:
                if btn_back.collidepoint(event.pos):
                    return "main_menu", faction_roles

                if role_red.collidepoint(event.pos):
                    cycle_role("red"); warning_text = ""
                elif role_yellow.collidepoint(event.pos):
                    cycle_role("yellow"); warning_text = ""
                elif role_blue.collidepoint(event.pos):
                    cycle_role("blue"); warning_text = ""
                elif role_black.collidepoint(event.pos):
                    cycle_role("black"); warning_text = ""

                if btn_start.collidepoint(event.pos):
                    if _count_active(faction_roles) == 0:
                        warning_text = "Нужно включить хотя бы 1 фракцию (Игрок или ИИ)."
                    else:
                        return "game", faction_roles

        screen.fill(BG_COLOR)

        title = font.render("Настройка фракций", True, (255, 255, 0))
        screen.blit(title, title.get_rect(center=(center_x, title_y)))

        draw_button(btn_back, "Назад", screen, small_font, mouse_pos)

        t = small_font.render("Роль фракции (клик: Выкл → Игрок → ИИ → Выкл):", True, (255, 255, 255))
        screen.blit(t, (center_x - S(240), t_roles_y))

        draw_button(role_red, role_text("red"), screen, small_font, mouse_pos)
        draw_button(role_yellow, role_text("yellow"), screen, small_font, mouse_pos)
        draw_button(role_blue, role_text("blue"), screen, small_font, mouse_pos)
        draw_button(role_black, role_text("black"), screen, small_font, mouse_pos)

        active = _count_active(faction_roles)
        info = small_font.render(f"Активных фракций: {active}", True, (255, 255, 255))
        screen.blit(info, (center_x - S(90), info_y))

        if warning_text:
            warn = small_font.render(warning_text, True, (255, 120, 120))
            screen.blit(warn, (center_x - S(240), info_y + S(22)))

        draw_button(btn_start, "Старт", screen, small_font, mouse_pos)

        pygame.display.flip()