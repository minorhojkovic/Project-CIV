from __future__ import annotations

import pygame
from civlite.config import BG_COLOR, SCREEN_WIDTH, SCREEN_HEIGHT
from civlite.audio.music import MusicManager
from civlite.audio.sfx import SfxManager
from civlite.rendering.draw_utils import draw_button


# Базовый размер (под который делался UI)
BASE_W, BASE_H = SCREEN_WIDTH, SCREEN_HEIGHT
ASPECT = BASE_W / BASE_H


def _fmt_res(res: tuple[int, int]) -> str:
    return f"{res[0]}x{res[1]}"


def _desktop_size() -> tuple[int, int]:
    """
    Самый надёжный способ узнать размер монитора в pygame 2 на Windows.
    """
    try:
        sizes = pygame.display.get_desktop_sizes()
        if sizes:
            w, h = sizes[0]
            return int(w), int(h)
    except Exception:
        pass

    info = pygame.display.Info()
    return int(info.current_w), int(info.current_h)


def _build_resolutions_for_desktop() -> list[tuple[int, int]]:
    """
    Генерим список разрешений для ОКОННОГО режима:
    - сохраняем аспект игры
    - берём “типовые” высоты
    - отсекаем те, что не влезают на рабочий стол (с запасом под рамки/панель задач)
    """
    dw, dh = _desktop_size()

    # запас под рамки окна и панель задач (можешь увеличить, если нужно)
    max_w = max(320, dw - 160)
    max_h = max(320, dh - 160)

    # “игровые” высоты (плавная сетка)
    candidate_heights = [BASE_H, 720, 800, 900, 960, 1024, 1120, 1280, 1440, 1600, 1760, 1920]

    out: list[tuple[int, int]] = []
    for h in candidate_heights:
        w = int(round(h * ASPECT))
        if w <= max_w and h <= max_h:
            out.append((w, h))

    # если вдруг ничего не влезло — хотя бы базовое
    if not out:
        out = [(BASE_W, BASE_H)]

    # уникальные + сортировка
    out = sorted(list(dict.fromkeys(out)), key=lambda r: (r[0] * r[1], r[0]))

    # маленький лог для проверки
    print(f"[RES] desktop={dw}x{dh} -> options={len(out)}: {out}")

    return out


def run_settings_menu(
    screen: pygame.Surface,
    clock: pygame.time.Clock,
    font: pygame.font.Font,
    small_font: pygame.font.Font,
    music: MusicManager,
    sfx: SfxManager,
    *,
    fullscreen: bool,
    music_volume: int,
    sfx_volume: int,
    resolution: tuple[int, int],
    return_scene: str
):
    music.stop_music()
    music.reset_menu_flag()

    dragging_music = False
    dragging_sfx = False
    dropdown_open = False

    def apply_mode(new_fullscreen: bool, desired_res: tuple[int, int]) -> tuple[pygame.Surface, tuple[int, int], bool]:
        if new_fullscreen:
            dw, dh = _desktop_size()
            pygame.display.set_mode((dw, dh), pygame.FULLSCREEN)
            new_screen = pygame.display.get_surface()
            return new_screen, new_screen.get_size(), True
        else:
            pygame.display.set_mode(desired_res, 0)
            new_screen = pygame.display.get_surface()
            return new_screen, new_screen.get_size(), False

    # применяем то, что пришло, чтобы screen/resolution были реальными
    screen, resolution, fullscreen = apply_mode(fullscreen, resolution)

    RESOLUTIONS = _build_resolutions_for_desktop()
    if (not fullscreen) and (resolution not in RESOLUTIONS):
        RESOLUTIONS.append(resolution)
        RESOLUTIONS = sorted(list(dict.fromkeys(RESOLUTIONS)), key=lambda r: (r[0] * r[1], r[0]))

    while True:
        clock.tick(60)
        music.play_menu_music()

        W, H = screen.get_size()
        scale = min(W / BASE_W, H / BASE_H)

        def S(v: int) -> int:
            return max(1, int(v * scale))

        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()

        center_x = W // 2
        title_y = int(H * 0.25)

        fullscreen_button = pygame.Rect(center_x - S(180), int(H * 0.5) - S(170), S(360), S(46))
        resolution_button = pygame.Rect(center_x - S(180), int(H * 0.5) - S(115), S(360), S(46))

        item_h = S(34)
        list_w = resolution_button.width
        list_x = resolution_button.x
        list_y = resolution_button.bottom + S(6)
        visible_items = min(10, len(RESOLUTIONS))
        dropdown_rect = pygame.Rect(list_x, list_y, list_w, item_h * visible_items + S(8))

        music_bar_rect = pygame.Rect(center_x - S(180), int(H * 0.5) - S(20), S(360), S(20))
        sfx_bar_rect = pygame.Rect(center_x - S(180), int(H * 0.5) + S(70), S(360), S(20))
        back_button = pygame.Rect(center_x - S(110), int(H * 0.5) + S(170), S(220), S(46))

        music_slider = pygame.Rect(
            music_bar_rect.x + music_volume / 100 * music_bar_rect.width - S(10),
            music_bar_rect.y - S(5),
            S(20),
            S(30)
        )
        sfx_slider = pygame.Rect(
            sfx_bar_rect.x + sfx_volume / 100 * sfx_bar_rect.width - S(10),
            sfx_bar_rect.y - S(5),
            S(20),
            S(30)
        )

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "exit", fullscreen, music_volume, sfx_volume, resolution

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if dropdown_open:
                    # клик по кнопке разрешения — просто закрываем/открываем
                    if resolution_button.collidepoint(event.pos):
                        dropdown_open = False
                    # клик внутри списка — обработаем выбор (оставь твой существующий код выбора)
                    elif dropdown_rect.collidepoint(event.pos):
                        inner_y = event.pos[1] - (dropdown_rect.y + S(4))
                        idx = inner_y // item_h
                        if 0 <= idx < len(RESOLUTIONS[:visible_items]):
                            chosen = RESOLUTIONS[idx]
                            screen, resolution, fullscreen = apply_mode(False, chosen)
                            dropdown_open = False

                            RESOLUTIONS = _build_resolutions_for_desktop()
                            if resolution not in RESOLUTIONS:
                                RESOLUTIONS.append(resolution)
                                RESOLUTIONS = sorted(list(dict.fromkeys(RESOLUTIONS)), key=lambda r: (r[0] * r[1], r[0]))
                    else:
                        # клик мимо — закрыть
                        dropdown_open = False

                    # ВАЖНО: не даём обработать этот клик другими кнопками/слайдерами
                    continue

                if fullscreen_button.collidepoint(event.pos):
                    dropdown_open = False
                    screen, resolution, fullscreen = apply_mode(not fullscreen, resolution)

                    RESOLUTIONS = _build_resolutions_for_desktop()
                    if (not fullscreen) and (resolution not in RESOLUTIONS):
                        RESOLUTIONS.append(resolution)
                        RESOLUTIONS = sorted(list(dict.fromkeys(RESOLUTIONS)), key=lambda r: (r[0] * r[1], r[0]))

                elif resolution_button.collidepoint(event.pos):
                    dropdown_open = not dropdown_open

                elif dropdown_open and dropdown_rect.collidepoint(event.pos):
                    inner_y = event.pos[1] - (dropdown_rect.y + S(4))
                    idx = inner_y // item_h
                    if 0 <= idx < len(RESOLUTIONS[:visible_items]):
                        chosen = RESOLUTIONS[idx]

                        # как в играх: выбрали разрешение -> оконный режим
                        screen, resolution, fullscreen = apply_mode(False, chosen)
                        dropdown_open = False

                        # синхронизация списка (и чтобы текущее точно было там)
                        RESOLUTIONS = _build_resolutions_for_desktop()
                        if resolution not in RESOLUTIONS:
                            RESOLUTIONS.append(resolution)
                            RESOLUTIONS = sorted(list(dict.fromkeys(RESOLUTIONS)), key=lambda r: (r[0] * r[1], r[0]))

                else:
                    dropdown_open = False

                    if back_button.collidepoint(event.pos):
                        return return_scene, fullscreen, music_volume, sfx_volume, resolution

                    if music_bar_rect.collidepoint(event.pos) or music_slider.collidepoint(event.pos):
                        dragging_music = True
                    if sfx_bar_rect.collidepoint(event.pos) or sfx_slider.collidepoint(event.pos):
                        dragging_sfx = True

            if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                dragging_music = False
                dragging_sfx = False

        if mouse_pressed[0] and dragging_music:
            if music_bar_rect.x <= mouse_pos[0] <= music_bar_rect.right:
                relative_x = mouse_pos[0] - music_bar_rect.x
                music_volume = max(0, min(100, int((relative_x / music_bar_rect.width) * 100)))
                music.set_volume(music_volume)

        if mouse_pressed[0] and dragging_sfx:
            if sfx_bar_rect.x <= mouse_pos[0] <= sfx_bar_rect.right:
                relative_x = mouse_pos[0] - sfx_bar_rect.x
                sfx_volume = max(0, min(100, int((relative_x / sfx_bar_rect.width) * 100)))
                sfx.set_volume(sfx_volume)

        screen.fill(BG_COLOR)

        title_surf = font.render("Настройки", True, (255, 255, 0))
        screen.blit(title_surf, title_surf.get_rect(center=(center_x, title_y)))

        draw_button(fullscreen_button, f"Полный экран: {'Вкл' if fullscreen else 'Выкл'}", screen, small_font, mouse_pos)

        arrow = "▴" if dropdown_open else "▾"
        draw_button(resolution_button, f"Разрешение: {_fmt_res(resolution)} {arrow}", screen, small_font, mouse_pos)

        if dropdown_open:
            # ===== ПОЛНОСТЬЮ НЕПРОЗРАЧНЫЙ ФОН =====
            pygame.draw.rect(screen, (35, 35, 35), dropdown_rect)  # плотный фон
            pygame.draw.rect(screen, (0, 0, 0), dropdown_rect, max(2, S(2)))  # чёткая рамка

            pad_x = S(12)
            pad_y = S(8)

            y = dropdown_rect.y + pad_y
            shown = RESOLUTIONS[:visible_items]

            for res in shown:
                item_rect = pygame.Rect(
                    dropdown_rect.x + pad_x,
                    y,
                    dropdown_rect.width - pad_x * 2,
                    item_h
                )

                is_current = (not fullscreen) and (res == resolution)
                hover = item_rect.collidepoint(mouse_pos)

                if is_current:
                    bg = (80, 120, 80)     # выбранное — зелёный
                elif hover:
                    bg = (85, 85, 85)      # hover — светлее
                else:
                    bg = (55, 55, 55)      # обычный пункт

                pygame.draw.rect(screen, bg, item_rect)
                pygame.draw.rect(screen, (20, 20, 20), item_rect, 1)

                txt = small_font.render(_fmt_res(res), True, (255, 255, 255))
                screen.blit(txt, txt.get_rect(midleft=(item_rect.x + S(12), item_rect.centery)))

                y += item_h

        music_label = small_font.render(f"Музыка: {music_volume}%", True, (255, 255, 255))
        screen.blit(music_label, (music_bar_rect.x, music_bar_rect.y - S(25)))
        pygame.draw.rect(screen, (100, 100, 100), music_bar_rect)
        pygame.draw.rect(
            screen,
            (50, 200, 50),
            (music_bar_rect.x, music_bar_rect.y, int(music_bar_rect.width * music_volume / 100), music_bar_rect.height)
        )
        pygame.draw.rect(screen, (255, 255, 255), music_slider)

        sfx_label = small_font.render(f"Звуки (SFX): {sfx_volume}%", True, (255, 255, 255))
        screen.blit(sfx_label, (sfx_bar_rect.x, sfx_bar_rect.y - S(25)))
        pygame.draw.rect(screen, (100, 100, 100), sfx_bar_rect)
        pygame.draw.rect(
            screen,
            (50, 200, 50),
            (sfx_bar_rect.x, sfx_bar_rect.y, int(sfx_bar_rect.width * sfx_volume / 100), sfx_bar_rect.height)
        )
        pygame.draw.rect(screen, (255, 255, 255), sfx_slider)

        draw_button(back_button, "Назад", screen, small_font, mouse_pos)

        if dropdown_open:
            # необязательная "подложка", чтобы точно было видно и выглядело как модалка
            overlay = pygame.Surface((W, H))
            overlay.set_alpha(90)  # полупрозрачная тень на фоне
            overlay.fill((0, 0, 0))
            screen.blit(overlay, (0, 0))

            pygame.draw.rect(screen, (35, 35, 35), dropdown_rect)
            pygame.draw.rect(screen, (0, 0, 0), dropdown_rect, max(2, S(2)))

            pad_x = S(12)
            pad_y = S(8)

            y = dropdown_rect.y + pad_y
            shown = RESOLUTIONS[:visible_items]

            for res in shown:
                item_rect = pygame.Rect(
                    dropdown_rect.x + pad_x,
                    y,
                    dropdown_rect.width - pad_x * 2,
                    item_h
                )

                is_current = (not fullscreen) and (res == resolution)
                hover = item_rect.collidepoint(mouse_pos)

                if is_current:
                    bg = (80, 120, 80)
                elif hover:
                    bg = (85, 85, 85)
                else:
                    bg = (55, 55, 55)

                pygame.draw.rect(screen, bg, item_rect)
                pygame.draw.rect(screen, (20, 20, 20), item_rect, 1)

                txt = small_font.render(_fmt_res(res), True, (255, 255, 255))
                screen.blit(txt, txt.get_rect(midleft=(item_rect.x + S(12), item_rect.centery)))

                y += item_h

        pygame.display.flip()