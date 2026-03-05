from __future__ import annotations

import random
import time
import pygame

from civlite.config import SCREEN_WIDTH, SCREEN_HEIGHT, BG_COLOR
from civlite.audio.music import MusicManager

BASE_W, BASE_H = SCREEN_WIDTH, SCREEN_HEIGHT

LOADING_TIPS = [
    "Совет: исследуйте окружающие земли!",
    "Совет: стройте города рядом с ресурсами.",
    "Совет: леса замедляют движение юнитов.",
    "Совет: пустыня требует больше очков движения.",
    "Совет: глубокое море недоступно для обычных юнитов."
]

LOAD_TEXTS = [
    (0, "Генерируем карту..."),
    (200, "Рассеиваем биомы..."),
    (450, "Вербуем юнитов..."),
    (620, "Расставляем ресурсы..."),
    (790, "Собираем данные о врагах..."),
    (990, "Подготовка завершена...")
]


def run_loading_screen(screen: pygame.Surface, clock: pygame.time.Clock, small_font: pygame.font.Font, music: MusicManager):
    music.play_loading_music()

    progress = 0
    max_progress = 1000
    tip_timer = 0.0
    tip_interval = random.randint(6, 7)
    current_tip = random.choice(LOADING_TIPS)
    load_text = ""

    while progress < max_progress:
        dt = clock.tick(60) / 1000.0
        tip_timer += dt

        if tip_timer > tip_interval:
            current_tip = random.choice(LOADING_TIPS)
            tip_timer = 0.0
            tip_interval = random.randint(6, 7)

        event_chance = random.random()
        if event_chance < 0.6:
            progress += random.randint(1, 5)
        elif event_chance < 0.9:
            progress += random.randint(10, 50)
        else:
            progress += random.randint(0, 2)

        progress = min(progress, max_progress)

        load_text = ""
        for threshold, text in LOAD_TEXTS:
            if progress >= threshold:
                load_text = text

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "exit"

        W, H = screen.get_size()
        scale = min(W / BASE_W, H / BASE_H)

        def S(v: int) -> int:
            return int(v * scale)

        screen.fill(BG_COLOR)

        tip_surf = small_font.render(current_tip, True, (255, 255, 255))
        screen.blit(tip_surf, tip_surf.get_rect(center=(W // 2, H // 2 - S(60))))

        bar_width = W - S(200)
        bar_height = S(30)
        bar_x = S(100)
        bar_y = H // 2

        pygame.draw.rect(screen, (100, 100, 100), (bar_x, bar_y, bar_width, bar_height))
        pygame.draw.rect(screen, (50, 200, 50), (bar_x, bar_y, int(bar_width * (progress / max_progress)), bar_height))

        load_surf = small_font.render(load_text, True, (255, 255, 255))
        screen.blit(load_surf, load_surf.get_rect(center=(W // 2, H // 2 + S(50))))

        pygame.display.flip()

    music.stop_music()
    music.play_menu_music()
    time.sleep(0.3)
    return "main_menu"