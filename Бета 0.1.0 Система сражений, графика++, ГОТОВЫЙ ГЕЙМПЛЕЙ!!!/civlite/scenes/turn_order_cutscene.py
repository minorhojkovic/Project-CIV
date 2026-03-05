from __future__ import annotations

import random
import pygame
from civlite.config import SCREEN_WIDTH, SCREEN_HEIGHT
from civlite.audio.music import MusicManager
from civlite.audio.sfx import SfxManager

BASE_W, BASE_H = SCREEN_WIDTH, SCREEN_HEIGHT

FACTION_NAMES_RU = {
    "red": "Красные",
    "yellow": "Жёлтые",
    "blue": "Синие",
    "black": "Чёрные",
}


def roll_turn_order_with_ties(active_factions: list[str]) -> tuple[dict[str, int], list[str]]:
    remaining = list(active_factions)
    order: list[str] = []
    final_rolls: dict[str, int] = {}

    while remaining:
        rolls = {f: random.randint(1, 6) for f in remaining}
        buckets: dict[int, list[str]] = {}
        for f, v in rolls.items():
            buckets.setdefault(v, []).append(f)

        next_remaining: list[str] = []
        for v in sorted(buckets.keys(), reverse=True):
            group = buckets[v]
            if len(group) == 1:
                f = group[0]
                order.append(f)
                final_rolls[f] = v
            else:
                next_remaining.extend(group)

        remaining = next_remaining

    return final_rolls, order


def run_turn_order_cutscene(
    screen: pygame.Surface,
    clock: pygame.time.Clock,
    font: pygame.font.Font,
    small_font: pygame.font.Font,
    music: MusicManager,
    sfx: SfxManager,
    *,
    active_factions: list[str],
) -> tuple[dict[str, int], list[str]]:
    active = list(active_factions)
    if not active:
        return {}, []

    show_order = [f for f in ["red", "yellow", "blue", "black"] if f in active]

    try:
        music.set_volume(0)
    except Exception:
        pass

    numbers: dict[str, int | None] = {f: None for f in show_order}

    # базовые размеры (будут масштабироваться)
    btn_base = pygame.Rect(BASE_W // 2 - 180, BASE_H - 140, 360, 56)
    start_y_base = BASE_H // 2 - (len(show_order) * 44) // 2
    line_h_base = 52

    def render(spinning: bool, mouse_pos: tuple[int, int]):
        W, H = screen.get_size()
        scale = min(W / BASE_W, H / BASE_H)

        def S(v: int) -> int:
            return int(v * scale)

        btn = pygame.Rect(W // 2 - S(180), H - S(140), S(360), S(56))
        start_y = H // 2 - S((len(show_order) * 44) // 2)
        line_h = S(line_h_base)

        screen.fill((0, 0, 0))

        title = font.render("Порядок хода", True, (255, 255, 255))
        screen.blit(title, title.get_rect(center=(W // 2, S(110))))

        subtitle = small_font.render("Бросок d6 (при равенстве — перекид)", True, (210, 210, 210))
        screen.blit(subtitle, subtitle.get_rect(center=(W // 2, S(150))))

        for i, f in enumerate(show_order):
            y = start_y + i * line_h
            name = FACTION_NAMES_RU.get(f, f)
            left = small_font.render(name, True, (255, 255, 255))
            screen.blit(left, (W // 2 - S(200), y))

            val = numbers.get(f)
            txt = "?" if val is None else str(val)
            col = (230, 230, 230) if spinning else (255, 255, 255)
            right = small_font.render(txt, True, col)
            screen.blit(right, (W // 2 + S(160), y))

        hover = btn.collidepoint(mouse_pos)
        c = (120, 120, 120) if hover else (90, 90, 90)
        pygame.draw.rect(screen, c, btn, border_radius=S(10))
        pygame.draw.rect(screen, (0, 0, 0), btn, max(1, S(2)), border_radius=S(10))
        bt = small_font.render("Испытать удачу", True, (255, 255, 255))
        screen.blit(bt, bt.get_rect(center=btn.center))

        return btn

    # 1) ожидание клика
    while True:
        clock.tick(60)
        mouse_pos = pygame.mouse.get_pos()
        btn = render(spinning=False, mouse_pos=mouse_pos)
        pygame.display.flip()

        clicked = False
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return {}, []
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and btn.collidepoint(e.pos):
                clicked = True
        if clicked:
            break

    # 2) start + спин
    sfx.drum_play_start()

    spin_time = 1.8
    t = 0.0
    loop_started = False

    while t < spin_time:
        dt = clock.tick(60) / 1000.0
        t += dt

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return {}, []

        if (not loop_started) and (not sfx.drum_is_busy()):
            sfx.drum_start_loop()
            loop_started = True

        sfx.drum_update()

        for f in show_order:
            numbers[f] = random.randint(1, 6)

        mouse_pos = pygame.mouse.get_pos()
        render(spinning=True, mouse_pos=mouse_pos)
        pygame.display.flip()

    while not loop_started:
        dt = clock.tick(60) / 1000.0
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return {}, []
        if not sfx.drum_is_busy():
            sfx.drum_start_loop()
            loop_started = True
        sfx.drum_update()
        mouse_pos = pygame.mouse.get_pos()
        render(spinning=True, mouse_pos=mouse_pos)
        pygame.display.flip()

    # 3) итоговые броски
    rolls, order = roll_turn_order_with_ties(active)

    # 4) вскрытие + diceX
    n = len(show_order)
    dice_seq = {4: [1, 2, 3, 4], 3: [2, 3, 4], 2: [3, 4], 1: [4]}.get(n, [4])

    numbers = {f: None for f in show_order}
    for i, f in enumerate(show_order):
        pre = 0.15
        p = 0.0
        while p < pre:
            dt = clock.tick(60) / 1000.0
            p += dt
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    return {}, []
            sfx.drum_update()
            mouse_pos = pygame.mouse.get_pos()
            render(spinning=False, mouse_pos=mouse_pos)
            pygame.display.flip()

        numbers[f] = rolls.get(f, random.randint(1, 6))
        sfx.play_dice(dice_seq[min(i, len(dice_seq) - 1)])

        post = 0.55
        q = 0.0
        while q < post:
            dt = clock.tick(60) / 1000.0
            q += dt
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    return {}, []
            sfx.drum_update()
            mouse_pos = pygame.mouse.get_pos()
            render(spinning=False, mouse_pos=mouse_pos)
            pygame.display.flip()

    # 5) остановка после цикла -> end
    sfx.drum_request_stop_after_cycle()
    while True:
        dt = clock.tick(60) / 1000.0
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return rolls, order
        sfx.drum_update()
        mouse_pos = pygame.mouse.get_pos()
        render(spinning=False, mouse_pos=mouse_pos)
        pygame.display.flip()
        if not sfx.drum_is_busy():
            break

    # 6) чёрный экран "Ход ..."
    first = order[0] if order else None
    screen.fill((0, 0, 0))
    if first:
        t1 = font.render(f"Ход {FACTION_NAMES_RU.get(first, first)}", True, (255, 255, 255))
        W, H = screen.get_size()
        screen.blit(t1, t1.get_rect(center=(W // 2, H // 2)))
    pygame.display.flip()

    return rolls, order