import pygame
from config import SCREEN_WIDTH, SCREEN_HEIGHT, BG_COLOR, MENU_COLOR, TILE_SIZE
from draw_utils import draw_map, draw_button, draw_units, draw_grid, draw_highlight_tiles
from map_generator import generate_map
from units import Unit

pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Civilisation Lite - Map Generator")
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 24)

def main():
    game_map = generate_map(50, 50)
    running = True
    show_bottom = False
    current_menu = None
    action_mode = None
    units = []

    # Верхние кнопки
    top_button_game = pygame.Rect(10, 10, 80, 30)
    top_button_debug = pygame.Rect(100, 10, 80, 30)

    # Нижние кнопки (game menu)
    bottom_gen = pygame.Rect(10, SCREEN_HEIGHT - 40, 150, 30)
    bottom_exit = pygame.Rect(170, SCREEN_HEIGHT - 40, 100, 30)
    bottom_next_turn = pygame.Rect(340, SCREEN_HEIGHT - 40, 150, 30)

    # Нижние кнопки (debug menu)
    bottom_add_unit = pygame.Rect(10, SCREEN_HEIGHT - 40, 150, 30)
    bottom_remove_unit = pygame.Rect(170, SCREEN_HEIGHT - 40, 150, 30)
    bottom_exit_action = pygame.Rect(340, SCREEN_HEIGHT - 40, 150, 30)

    while running:
        dt = clock.tick(60) / 1000  # секунды
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.MOUSEBUTTONDOWN:
                # --- Верхние кнопки ---
                if top_button_game.collidepoint(event.pos):
                    show_bottom = True
                    current_menu = "game"
                    action_mode = None
                elif top_button_debug.collidepoint(event.pos):
                    show_bottom = True
                    current_menu = "debug"
                    action_mode = None

                # --- Нижние кнопки ---
                if show_bottom:
                    if current_menu == "game":
                        if bottom_gen.collidepoint(event.pos):
                            game_map = generate_map(50, 50)
                            units.clear()
                        elif bottom_exit.collidepoint(event.pos):
                            running = False
                        elif bottom_next_turn.collidepoint(event.pos):
                            for u in units:
                                u.reset_move()
                            print("➡️ Следующий ход: очки движения всех юнитов восстановлены")
                    elif current_menu == "debug":
                        if bottom_add_unit.collidepoint(event.pos):
                            action_mode = "add_unit"
                            print("Режим: добавление юнитов")
                        elif bottom_remove_unit.collidepoint(event.pos):
                            action_mode = "remove_unit"
                            print("Режим: удаление юнитов")
                        elif bottom_exit_action.collidepoint(event.pos):
                            action_mode = None
                            print("Выход из режима действия")

                # --- Клик по карте ---
                if event.pos[1] < SCREEN_HEIGHT - 50:
                    tile_x = event.pos[0] // TILE_SIZE
                    tile_y = event.pos[1] // TILE_SIZE
                    tile = game_map[tile_y][tile_x]

                    if action_mode == "add_unit":
                        if tile != "deep_water":
                            units.append(Unit(tile_x, tile_y))
                            print(f"Юнит добавлен: ({tile_x}, {tile_y})")
                    elif action_mode == "remove_unit":
                        for u in units:
                            if u.x == tile_x and u.y == tile_y:
                                units.remove(u)
                                print(f"Юнит удалён: ({tile_x}, {tile_y})")
                                break
                    elif action_mode is None:
                        # выбор юнита
                        clicked_unit = None
                        for u in units:
                            if u.x == tile_x and u.y == tile_y and not u.moving:
                                clicked_unit = u
                                break
                        if clicked_unit:
                            for u in units:
                                u.selected = False
                            clicked_unit.selected = True
                            print(f"Юнит выбран: ({clicked_unit.x}, {clicked_unit.y})")
                        else:
                            # движение выбранного юнита
                            selected_unit = next((u for u in units if u.selected), None)
                            if selected_unit and not selected_unit.moving and selected_unit.can_move():
                                reachable = selected_unit.get_reachable_tiles(game_map)
                                if (tile_x, tile_y) in reachable:
                                    if selected_unit.move_to(tile_x, tile_y, game_map):
                                        print(f"Юнит начинает движение к ({tile_x}, {tile_y})")

        # --- Обновление юнитов для анимации ---
        for u in units:
            u.update(dt)

        # --- Отрисовка ---
        screen.fill(BG_COLOR)
        draw_map(game_map, screen)
        draw_units(units, screen)

        # Сетка для режима add/remove или подсветка для выбранного юнита
        if action_mode in ("add_unit", "remove_unit"):
            draw_grid(screen)
        else:
            selected_unit = next((u for u in units if u.selected and not u.moving), None)
            if selected_unit and selected_unit.can_move():
                highlight_tiles = selected_unit.get_reachable_tiles(game_map)
                draw_highlight_tiles(screen, highlight_tiles)

        # Верхняя панель
        pygame.draw.rect(screen, MENU_COLOR, (0, 0, SCREEN_WIDTH, 50))
        draw_button(top_button_game, "Игра", screen, font, mouse_pos)
        draw_button(top_button_debug, "Дебаг", screen, font, mouse_pos)

        # Нижняя панель
        if show_bottom:
            pygame.draw.rect(screen, MENU_COLOR, (0, SCREEN_HEIGHT - 50, SCREEN_WIDTH, 50))
            if current_menu == "game":
                draw_button(bottom_gen, "Генерация мира", screen, font, mouse_pos)
                draw_button(bottom_exit, "Выход", screen, font, mouse_pos)
                draw_button(bottom_next_turn, "Следующий ход", screen, font, mouse_pos)
            elif current_menu == "debug":
                draw_button(bottom_add_unit, "Добавить юнита", screen, font, mouse_pos)
                draw_button(bottom_remove_unit, "Удалить юнита", screen, font, mouse_pos)
                if action_mode in ("add_unit", "remove_unit"):
                    draw_button(bottom_exit_action, "Выйти из режима", screen, font, mouse_pos)

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
