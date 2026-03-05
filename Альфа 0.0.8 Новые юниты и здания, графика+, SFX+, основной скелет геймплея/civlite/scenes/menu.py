from __future__ import annotations

import pygame
from civlite.config import SCREEN_WIDTH, SCREEN_HEIGHT, BG_COLOR
from civlite.audio.music import MusicManager
from civlite.rendering.draw_utils import draw_button

BASE_W, BASE_H = SCREEN_WIDTH, SCREEN_HEIGHT


def run_main_menu(
    screen: pygame.Surface,
    clock: pygame.time.Clock,
    font: pygame.font.Font,
    small_font: pygame.font.Font,
    music: MusicManager
):
    while True:
        clock.tick(60)
        music.play_menu_music()

        W, H = screen.get_size()
        scale = min(W / BASE_W, H / BASE_H)

        def S(v: int) -> int:
            return int(v * scale)

        mouse_pos = pygame.mouse.get_pos()

        play_button = pygame.Rect(W // 2 - S(100), H // 2 - S(60), S(200), S(50))
        settings_button = pygame.Rect(W // 2 - S(100), H // 2, S(200), S(50))
        exit_button = pygame.Rect(W // 2 - S(100), H // 2 + S(60), S(200), S(50))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "exit"
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if play_button.collidepoint(event.pos):
                    music.stop_music()
                    music.reset_menu_flag()
                    return "setup"
                if settings_button.collidepoint(event.pos):
                    return "settings"
                if exit_button.collidepoint(event.pos):
                    return "exit"

        screen.fill(BG_COLOR)
        title_surf = font.render("Civilisation Lite", True, (255, 255, 0))
        screen.blit(title_surf, title_surf.get_rect(center=(W // 2, H // 4)))

        draw_button(play_button, "Играть", screen, small_font, mouse_pos)
        draw_button(settings_button, "Настройки", screen, small_font, mouse_pos)
        draw_button(exit_button, "Выйти", screen, small_font, mouse_pos)

        pygame.display.flip()