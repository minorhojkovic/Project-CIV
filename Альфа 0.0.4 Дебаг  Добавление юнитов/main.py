import pygame
from config import SCREEN_WIDTH, SCREEN_HEIGHT, BG_COLOR, MENU_COLOR, TILE_SIZE
from draw_utils import draw_map, draw_button, draw_units, draw_grid
from map_generator import generate_map

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
    action_mode = None  # "add_unit", "remove_unit" или None
    units = []  # список юнитов [(x, y), ...]

    # Верхние кнопки
    top_button_game = pygame.Rect(10, 10, 80, 30)
    top_button_debug = pygame.Rect(100, 10, 80, 30)

    # Нижние кнопки (game menu)
    bottom_gen = pygame.Rect(10, SCREEN_HEIGHT - 40, 150, 30)
    bottom_exit = pygame.Rect(170, SCREEN_HEIGHT - 40, 100, 30)

    # Нижние кнопки (debug menu)
    bottom_add_unit = pygame.Rect(10, SCREEN_HEIGHT - 40, 150, 30)
    bottom_remove_unit = pygame.Rect(170, SCREEN_HEIGHT - 40, 150, 30)
    bottom_exit_action = pygame.Rect(340, SCREEN_HEIGHT - 40, 150, 30)  # выход из режима

    while running:
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
                if event.pos[1] < SCREEN_HEIGHT - 50:  # не на нижней панели
                    tile_x = event.pos[0] // TILE_SIZE
                    tile_y = event.pos[1] // TILE_SIZE
                    if 0 <= tile_x < 50 and 0 <= tile_y < 50:
                        tile = game_map[tile_y][tile_x]

                        # Добавление юнита
                        if action_mode == "add_unit":
                            if tile != "deep_water":  # нельзя ставить в глубокое море
                                units.append((tile_x, tile_y))
                                print(f"Юнит добавлен: ({tile_x}, {tile_y})")
                            else:
                                print("❌ Нельзя разместить юнита на deep_water")

                        # Удаление юнита
                        elif action_mode == "remove_unit":
                            for u in units:
                                if u[0] == tile_x and u[1] == tile_y:
                                    units.remove(u)
                                    print(f"Юнит удалён: ({tile_x}, {tile_y})")
                                    break

        # --- Отрисовка ---
        screen.fill(BG_COLOR)
        draw_map(game_map, screen)
        draw_units(units, screen)

        # Сетка при нахождении в режиме действия
        if action_mode in ("add_unit", "remove_unit"):
            draw_grid(screen)

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
            elif current_menu == "debug":
                draw_button(bottom_add_unit, "Добавить юнита", screen, font, mouse_pos)
                draw_button(bottom_remove_unit, "Удалить юнита", screen, font, mouse_pos)
                if action_mode in ("add_unit", "remove_unit"):
                    draw_button(bottom_exit_action, "Выйти из режима", screen, font, mouse_pos)

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()

if __name__ == "__main__":
    main()
