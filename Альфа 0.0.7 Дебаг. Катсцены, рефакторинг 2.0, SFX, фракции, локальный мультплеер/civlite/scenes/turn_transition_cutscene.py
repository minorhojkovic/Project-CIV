from __future__ import annotations

import pygame


def run_turn_transition_cutscene(
    screen: pygame.Surface,
    clock: pygame.time.Clock,
    font: pygame.font.Font,
    small_font: pygame.font.Font,
    music,
    *,
    background_from: pygame.Surface,
    background_to: pygame.Surface,
    line1: str,
    line2: str,
    fade_in_duration: float = 0.6,
    hold_duration: float = 1.0,
    fade_out_duration: float = 0.6,
    music_fade_in: bool = False,
    target_music_volume: int = 50,
):
    """
    Рендерим напрямую в текущее разрешение окна.
    Фон (surface) масштабируем под текущее окно.
    """
    W, H = screen.get_size()

    def draw(alpha: int, use_to: bool):
        nonlocal W, H
        W, H = screen.get_size()

        base = background_to if use_to else background_from

        # Подгоняем фон под текущее окно (временно; когда game.py станет адаптивным — это станет нативным)
        if base.get_size() != (W, H):
            bg = pygame.transform.smoothscale(base, (W, H))
        else:
            bg = base

        screen.blit(bg, (0, 0))

        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, alpha))
        screen.blit(overlay, (0, 0))

        if alpha >= 150:
            t1 = font.render(line1, True, (255, 255, 255))
            screen.blit(t1, t1.get_rect(center=(W // 2, H // 2 - 20)))
            if line2:
                t2 = small_font.render(line2, True, (220, 220, 220))
                screen.blit(t2, t2.get_rect(center=(W // 2, H // 2 + 20)))

        pygame.display.flip()

    # fade in
    if fade_in_duration > 0:
        t = 0.0
        while t < fade_in_duration:
            dt = clock.tick(60) / 1000.0
            t += dt
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    return
            alpha = int(255 * min(1.0, t / fade_in_duration))
            draw(alpha, use_to=False)
    else:
        draw(255, use_to=False)

    # hold
    hold = 0.0
    while hold < hold_duration:
        dt = clock.tick(60) / 1000.0
        hold += dt
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return
        draw(255, use_to=False)

    # fade out (to)
    if music_fade_in:
        try:
            music.set_volume(0)
        except Exception:
            pass

    if fade_out_duration > 0:
        t = 0.0
        while t < fade_out_duration:
            dt = clock.tick(60) / 1000.0
            t += dt

            if music_fade_in:
                try:
                    v = int(target_music_volume * min(1.0, t / fade_out_duration))
                    music.set_volume(v)
                except Exception:
                    pass

            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    return

            alpha = int(255 * (1.0 - min(1.0, t / fade_out_duration)))
            draw(alpha, use_to=True)
    else:
        draw(255, use_to=True)