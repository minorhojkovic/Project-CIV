import pygame, random, time, os
from config import SCREEN_WIDTH, SCREEN_HEIGHT, BG_COLOR, MENU_COLOR, TILE_SIZE
from draw_utils import draw_map, draw_button, draw_units, draw_grid, draw_highlight_tiles
from map_generator import generate_map
from units import Unit

pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Civilisation Lite")
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 36)
small_font = pygame.font.SysFont(None, 24)

# --- Настройки ---
fullscreen = False
volume = 50  # 0-100

# --- Сцены ---
SCENE_LOADING = "loading"
SCENE_MAIN_MENU = "main_menu"
SCENE_SETTINGS = "settings"
SCENE_GAME = "game"

# --- Советы для загрузки ---
LOADING_TIPS = [
    "Совет: исследуйте окружающие земли!",
    "Совет: стройте города рядом с ресурсами.",
    "Совет: леса замедляют движение юнитов.",
    "Совет: пустыня требует больше очков движения.",
    "Совет: глубокое море недоступно для обычных юнитов."
]

# --- Текст загрузки по прогрессу ---
LOAD_TEXTS = [
    (0, "Генерируем карту..."),
    (200, "Рассеиваем биомы..."),
    (450, "Вербуем юнитов..."),
    (620, "Расставляем ресурсы..."),
    (790, "Собираем данные о врагах..."),
    (990, "Подготовка завершена...")
]

# --- Музыка ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_PATH = os.path.join(BASE_DIR, "assets", "sounds", "music")

MENU_THEME = os.path.join(ASSETS_PATH, "Main Theme.mp3")
LOADING_THEME = os.path.join(ASSETS_PATH, "Menu Theme.mp3")
GAME_TRACKS = [
    "Gusto Della Vittoria.mp3","Hande Hoch.mp3","Johny the Peacemaker.mp3","Kousakuranoki.mp3",
    "Land in zicht!.mp3","Lianhuawan De Hongri.mp3","Nacionalna Garda.mp3","Ni Wakati Wa Taifa Letu.mp3",
    "Sultanin Zevk Yuruyusu.mp3","Viva la l'Ognion.mp3","Viviendo mi Vida Mas Plena.mp3","Yagodka Moya.mp3"
]
GAME_TRACKS = [os.path.join(ASSETS_PATH, t) for t in GAME_TRACKS]

menu_music_flag = 0  # 0 = музыка меню не играет, 1 = играет
current_game_track = None

def play_music(path, loop=True):
    pygame.mixer.music.load(path)
    pygame.mixer.music.set_volume(volume / 100)
    pygame.mixer.music.play(-1 if loop else 0)

def stop_music():
    pygame.mixer.music.stop()

def play_menu_music():
    global menu_music_flag
    if menu_music_flag == 0:
        pygame.mixer.music.load(MENU_THEME)
        pygame.mixer.music.set_volume(volume / 100)
        pygame.mixer.music.play(-1)
        menu_music_flag = 1

def play_random_game_music():
    global current_game_track
    current_game_track = random.choice(GAME_TRACKS)
    pygame.mixer.music.load(current_game_track)
    pygame.mixer.music.set_volume(volume / 100)
    pygame.mixer.music.play(0)

def check_game_music():
    if not pygame.mixer.music.get_busy():
        play_random_game_music()

# --- Глобальные переменные для игры ---
game_map = None
units = []
action_mode = None
current_menu = None
show_bottom = False

# --- Загрузка ---
def loading_screen():
    play_music(LOADING_THEME, loop=True)
    progress = 0
    max_progress = 1000
    tip_timer = 0
    tip_interval = random.randint(6,7)
    current_tip = random.choice(LOADING_TIPS)
    load_text = ""
    total_time = random.randint(10,25)
    start_time = time.time()

    while progress < max_progress:
        dt = clock.tick(60)/1000
        tip_timer += dt

        if tip_timer > tip_interval:
            current_tip = random.choice(LOADING_TIPS)
            tip_timer = 0
            tip_interval = random.randint(6,7)

        event_chance = random.random()
        if event_chance < 0.6:
            progress += random.randint(1,5)
        elif event_chance < 0.9:
            progress += random.randint(10,50)
        else:
            progress += random.randint(0,2)

        progress = min(progress, max_progress)

        load_text = ""
        for threshold, text in LOAD_TEXTS:
            if progress >= threshold:
                load_text = text

        screen.fill(BG_COLOR)
        tip_surf = small_font.render(current_tip, True, (255,255,255))
        screen.blit(tip_surf, tip_surf.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2-60)))

        bar_width = SCREEN_WIDTH - 200
        bar_height = 30
        bar_x = 100
        bar_y = SCREEN_HEIGHT//2
        pygame.draw.rect(screen, (100,100,100), (bar_x, bar_y, bar_width, bar_height))
        pygame.draw.rect(screen, (50,200,50), (bar_x, bar_y, int(bar_width*(progress/max_progress)), bar_height))

        load_surf = small_font.render(load_text, True, (255,255,255))
        screen.blit(load_surf, load_surf.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2+50)))

        pygame.display.flip()

    stop_music()
    play_menu_music()
    time.sleep(0.3)

# --- Главное меню ---
def main_menu():
    global fullscreen
    menu_running = True
    while menu_running:
        dt = clock.tick(60)/1000
        mouse_pos = pygame.mouse.get_pos()
        play_menu_music()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "exit"
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if play_button.collidepoint(event.pos):
                    stop_music()
                    global menu_music_flag
                    menu_music_flag = 0
                    return "game"
                elif settings_button.collidepoint(event.pos):
                    return "settings"
                elif exit_button.collidepoint(event.pos):
                    return "exit"

        screen.fill(BG_COLOR)
        title_surf = font.render("Civilisation Lite", True, (255,255,0))
        screen.blit(title_surf, title_surf.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//4)))

        play_button = pygame.Rect(SCREEN_WIDTH//2-100, SCREEN_HEIGHT//2-60, 200, 50)
        settings_button = pygame.Rect(SCREEN_WIDTH//2-100, SCREEN_HEIGHT//2, 200, 50)
        exit_button = pygame.Rect(SCREEN_WIDTH//2-100, SCREEN_HEIGHT//2+60, 200, 50)

        draw_button(play_button, "Играть", screen, small_font, mouse_pos)
        draw_button(settings_button, "Настройки", screen, small_font, mouse_pos)
        draw_button(exit_button, "Выйти", screen, small_font, mouse_pos)

        pygame.display.flip()

# --- Настройки ---
def settings_menu():
    global fullscreen, volume
    menu_running = True
    fullscreen_button = pygame.Rect(SCREEN_WIDTH//2-100, SCREEN_HEIGHT//2-80, 200, 50)
    back_button = pygame.Rect(SCREEN_WIDTH//2-100, SCREEN_HEIGHT//2+80, 200, 50)
    volume_bar_rect = pygame.Rect(SCREEN_WIDTH//2-100, SCREEN_HEIGHT//2, 200, 20)
    slider_rect = pygame.Rect(volume_bar_rect.x + volume/100*volume_bar_rect.width - 10, volume_bar_rect.y-5, 20, 30)

    while menu_running:
        dt = clock.tick(60)/1000
        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()
        play_menu_music()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "exit"
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if fullscreen_button.collidepoint(event.pos):
                    fullscreen = not fullscreen
                    if fullscreen:
                        pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN)
                    else:
                        pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
                elif back_button.collidepoint(event.pos):
                    return "main_menu"

        if mouse_pressed[0] and volume_bar_rect.collidepoint(mouse_pos):
            relative_x = mouse_pos[0] - volume_bar_rect.x
            volume = max(0, min(100, int((relative_x / volume_bar_rect.width) * 100)))
            slider_rect.x = volume_bar_rect.x + relative_x - 10
            # обновляем громкость текущей музыки
            pygame.mixer.music.set_volume(volume / 100)

        screen.fill(BG_COLOR)
        title_surf = font.render("Настройки", True, (255,255,0))
        screen.blit(title_surf, title_surf.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//4)))

        draw_button(fullscreen_button, f"Полный экран: {'Вкл' if fullscreen else 'Выкл'}", screen, small_font, mouse_pos)
        pygame.draw.rect(screen, (100,100,100), volume_bar_rect)
        pygame.draw.rect(screen, (50,200,50), (volume_bar_rect.x, volume_bar_rect.y, volume_bar_rect.width*volume/100, volume_bar_rect.height))
        pygame.draw.rect(screen, (255,255,255), slider_rect)
        vol_surf = small_font.render(f"Громкость: {volume}%", True, (255,255,255))
        screen.blit(vol_surf, (volume_bar_rect.x, volume_bar_rect.y-25))

        draw_button(back_button, "Назад", screen, small_font, mouse_pos)
        pygame.display.flip()

# --- Игровая сцена ---
def game_scene():
    global game_map, units, action_mode, current_menu, show_bottom
    if game_map is None:
        game_map = generate_map(50,50)
        units = []

    stop_music()
    global menu_music_flag
    menu_music_flag = 0
    play_random_game_music()

    running = True

    top_button_game = pygame.Rect(10,10,80,30)
    top_button_debug = pygame.Rect(100,10,80,30)

    bottom_gen = pygame.Rect(10, SCREEN_HEIGHT-40, 150, 30)
    bottom_exit = pygame.Rect(170, SCREEN_HEIGHT-40, 100, 30)
    bottom_next_turn = pygame.Rect(340, SCREEN_HEIGHT-40, 150, 30)

    bottom_add_unit = pygame.Rect(10, SCREEN_HEIGHT-40, 150, 30)
    bottom_remove_unit = pygame.Rect(170, SCREEN_HEIGHT-40, 150, 30)
    bottom_exit_action = pygame.Rect(340, SCREEN_HEIGHT-40, 150, 30)

    while running:
        dt = clock.tick(60)/1000
        mouse_pos = pygame.mouse.get_pos()
        check_game_music()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "exit"
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if top_button_game.collidepoint(event.pos):
                    show_bottom = True
                    current_menu = "game"
                    action_mode = None
                elif top_button_debug.collidepoint(event.pos):
                    show_bottom = True
                    current_menu = "debug"
                    action_mode = None

                if show_bottom:
                    if current_menu == "game":
                        if bottom_gen.collidepoint(event.pos):
                            game_map = generate_map(50,50)
                            units.clear()
                        elif bottom_exit.collidepoint(event.pos):
                            stop_music()
                            return "main_menu"
                        elif bottom_next_turn.collidepoint(event.pos):
                            for u in units:
                                u.reset_move()
                    elif current_menu == "debug":
                        if bottom_add_unit.collidepoint(event.pos):
                            action_mode = "add_unit"
                        elif bottom_remove_unit.collidepoint(event.pos):
                            action_mode = "remove_unit"
                        elif bottom_exit_action.collidepoint(event.pos):
                            action_mode = None

                if event.pos[1] < SCREEN_HEIGHT-50:
                    tile_x = event.pos[0]//TILE_SIZE
                    tile_y = event.pos[1]//TILE_SIZE
                    tile = game_map[tile_y][tile_x]

                    if action_mode=="add_unit" and tile!="deep_water":
                        units.append(Unit(tile_x,tile_y))
                    elif action_mode=="remove_unit":
                        for u in units:
                            if u.x==tile_x and u.y==tile_y:
                                units.remove(u)
                                break
                    elif action_mode is None:
                        clicked_unit = None
                        for u in units:
                            if u.x==tile_x and u.y==tile_y and not u.moving:
                                clicked_unit = u
                                break
                        if clicked_unit:
                            for u in units:
                                u.selected = False
                            clicked_unit.selected = True
                        else:
                            selected_unit = next((u for u in units if u.selected and not u.moving), None)
                            if selected_unit and selected_unit.can_move():
                                reachable = selected_unit.get_reachable_tiles(game_map)
                                if (tile_x,tile_y) in reachable:
                                    selected_unit.move_to(tile_x,tile_y,game_map)

        for u in units:
            u.update(dt)

        screen.fill(BG_COLOR)
        draw_map(game_map, screen)
        draw_units(units, screen)

        if action_mode in ("add_unit","remove_unit"):
            draw_grid(screen)
        else:
            selected_unit = next((u for u in units if u.selected and not u.moving), None)
            if selected_unit and selected_unit.can_move():
                highlight_tiles = selected_unit.get_reachable_tiles(game_map)
                draw_highlight_tiles(screen, highlight_tiles)

        # Верхняя панель
        pygame.draw.rect(screen, MENU_COLOR, (0, 0, SCREEN_WIDTH, 50))
        draw_button(top_button_game, "Игра", screen, small_font, mouse_pos)
        draw_button(top_button_debug, "Дебаг", screen, small_font, mouse_pos)

        # Нижняя панель
        if show_bottom:
            pygame.draw.rect(screen, MENU_COLOR, (0, SCREEN_HEIGHT - 50, SCREEN_WIDTH, 50))
            if current_menu == "game":
                draw_button(bottom_gen, "Генерация мира", screen, small_font, mouse_pos)
                draw_button(bottom_exit, "Выход в меню", screen, small_font, mouse_pos)
                draw_button(bottom_next_turn, "Следующий ход", screen, small_font, mouse_pos)
            elif current_menu == "debug":
                draw_button(bottom_add_unit, "Добавить юнита", screen, small_font, mouse_pos)
                draw_button(bottom_remove_unit, "Удалить юнита", screen, small_font, mouse_pos)
                if action_mode in ("add_unit", "remove_unit"):
                    draw_button(bottom_exit_action, "Выйти из режима", screen, small_font, mouse_pos)

        pygame.display.flip()


def main():
    scene = SCENE_LOADING
    while True:
        if scene == SCENE_LOADING:
            loading_screen()
            scene = SCENE_MAIN_MENU
        elif scene == SCENE_MAIN_MENU:
            result = main_menu()
            if result == "exit":
                break
            scene = result
        elif scene == SCENE_SETTINGS:
            result = settings_menu()
            if result == "exit":
                break
            scene = result
        elif scene == SCENE_GAME:
            result = game_scene()
            if result == "exit":
                break
            scene = result

    pygame.quit()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        traceback.print_exc()
        # Ждем, чтобы окно консоли не закрылось мгновенно
        input("\nПроизошла ошибка! Нажмите Enter для выхода...")