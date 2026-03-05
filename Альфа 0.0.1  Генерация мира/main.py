import pygame
import random
import math
from collections import deque

# Настройки
TILE_SIZE = 10
MAP_WIDTH = 50
MAP_HEIGHT = 50
SCREEN_WIDTH = TILE_SIZE * MAP_WIDTH
SCREEN_HEIGHT = TILE_SIZE * MAP_HEIGHT + 60  # для меню

# Цвета
WATER_COLOR = (0, 0, 255)
LAND_COLOR = (34, 139, 34)
BG_COLOR = (0, 0, 0)
MENU_COLOR = (169, 169, 169)
BUTTON_COLOR = (200, 200, 200)
BUTTON_HOVER = (150, 150, 150)
TEXT_COLOR = (0, 0, 0)

# Инициализация Pygame
pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Civilisation Lite")
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 24)

def distance(p1, p2):
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)

def draw_map(game_map):
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            color = LAND_COLOR if game_map[y][x] == "land" else WATER_COLOR
            pygame.draw.rect(screen, color, (x*TILE_SIZE, y*TILE_SIZE, TILE_SIZE, TILE_SIZE))

def draw_button(rect, text, mouse_pos):
    color = BUTTON_HOVER if rect.collidepoint(mouse_pos) else BUTTON_COLOR
    pygame.draw.rect(screen, color, rect)
    pygame.draw.rect(screen, (0,0,0), rect, 2)
    text_surf = font.render(text, True, TEXT_COLOR)
    text_rect = text_surf.get_rect(center=rect.center)
    screen.blit(text_surf, text_rect)

def generate_map():
    """Генерация карты с континентами и озерами"""
    game_map = [["water" for _ in range(MAP_WIDTH)] for _ in range(MAP_HEIGHT)]

    # --- 1. Создаем стартовые континенты ---
    points = []
    while len(points) < 5:
        x, y = random.randint(0, MAP_WIDTH-1), random.randint(0, MAP_HEIGHT-1)
        if all(distance((x, y), p) >= 10 for p in points):
            points.append((x, y))
            game_map[y][x] = "land"

    total_tiles = MAP_WIDTH * MAP_HEIGHT
    min_land_pct, max_land_pct = 0.4, 0.8
    target_land_tiles = random.randint(int(total_tiles * min_land_pct), int(total_tiles * max_land_pct))
    remaining_tiles = target_land_tiles - len(points)
    growth_limits = [max(5, remaining_tiles // 5 + random.randint(-5,5)) for _ in range(5)]

    for idx, (x, y) in enumerate(points):
        growth_points = [(x, y)]
        tiles_grown = 1
        while growth_points and tiles_grown < growth_limits[idx]:
            cx, cy = random.choice(growth_points)
            neighbors = []
            for dx in [-1,0,1]:
                for dy in [-1,0,1]:
                    nx, ny = cx+dx, cy+dy
                    if 0 <= nx < MAP_WIDTH and 0 <= ny < MAP_HEIGHT:
                        if game_map[ny][nx] == "water":
                            neighbors.append((nx, ny))
            if neighbors:
                nx, ny = random.choice(neighbors)
                game_map[ny][nx] = "land"
                growth_points.append((nx, ny))
                tiles_grown += 1
            else:
                growth_points.remove((cx, cy))

    # --- 2. Находим большие континенты ---
    visited = [[False]*MAP_WIDTH for _ in range(MAP_HEIGHT)]
    continents = []

    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            if game_map[y][x] == "land" and not visited[y][x]:
                # BFS для поиска связной суши
                queue = deque()
                queue.append((x,y))
                visited[y][x] = True
                continent = [(x,y)]
                while queue:
                    cx, cy = queue.popleft()
                    for dx in [-1,0,1]:
                        for dy in [-1,0,1]:
                            nx, ny = cx+dx, cy+dy
                            if 0 <= nx < MAP_WIDTH and 0 <= ny < MAP_HEIGHT:
                                if game_map[ny][nx] == "land" and not visited[ny][nx]:
                                    visited[ny][nx] = True
                                    queue.append((nx, ny))
                                    continent.append((nx, ny))
                if len(continent) >= 50:  # считаем континент большим
                    continents.append(continent)

    # --- 3. Генерация озер ---
    for cont in continents:
        lakes_count = random.randint(1,2)
        for _ in range(lakes_count):
            lx, ly = random.choice(cont)
            lake_growth = random.randint(5,15)  # размер озера
            growth_points = [(lx, ly)]
            tiles_grown = 0
            while growth_points and tiles_grown < lake_growth:
                cx, cy = random.choice(growth_points)
                neighbors = []
                for dx in [-1,0,1]:
                    for dy in [-1,0,1]:
                        nx, ny = cx+dx, cy+dy
                        if 0 <= nx < MAP_WIDTH and 0 <= ny < MAP_HEIGHT:
                            if game_map[ny][nx] == "land":
                                neighbors.append((nx, ny))
                if neighbors:
                    nx, ny = random.choice(neighbors)
                    game_map[ny][nx] = "water"
                    growth_points.append((nx, ny))
                    tiles_grown += 1
                else:
                    growth_points.remove((cx, cy))

    return game_map

def main():
    game_map = generate_map()
    running = True
    show_bottom_menu = False

    top_button_rect = pygame.Rect(10, 10, 80, 30)
    bottom_gen_rect = pygame.Rect(10, SCREEN_HEIGHT-40, 150, 30)
    bottom_exit_rect = pygame.Rect(170, SCREEN_HEIGHT-40, 100, 30)

    while running:
        mouse_pos = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.MOUSEBUTTONDOWN:
                if top_button_rect.collidepoint(event.pos):
                    show_bottom_menu = True
                if show_bottom_menu:
                    if bottom_gen_rect.collidepoint(event.pos):
                        game_map = generate_map()
                    elif bottom_exit_rect.collidepoint(event.pos):
                        running = False

        screen.fill(BG_COLOR)
        draw_map(game_map)

        pygame.draw.rect(screen, MENU_COLOR, (0, 0, SCREEN_WIDTH, 50))
        draw_button(top_button_rect, "Игра", mouse_pos)

        if show_bottom_menu:
            pygame.draw.rect(screen, MENU_COLOR, (0, SCREEN_HEIGHT-50, SCREEN_WIDTH, 50))
            draw_button(bottom_gen_rect, "Генерация мира", mouse_pos)
            draw_button(bottom_exit_rect, "Выход", mouse_pos)

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()

if __name__ == "__main__":
    main()
