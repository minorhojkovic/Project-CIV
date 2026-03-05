import pygame
from config import (
    TILE_SIZE, MAP_WIDTH, MAP_HEIGHT,
    WATER_COLOR, DEEP_WATER_COLOR,
    LAND_COLOR, FOREST_COLOR, HILL_COLOR,
    SWAMP_COLOR, DESERT_COLOR,
    BUTTON_COLOR, BUTTON_HOVER, TEXT_COLOR
)

def draw_map(game_map, screen):
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            tile = game_map[y][x]
            color = {
                "deep_water": DEEP_WATER_COLOR,
                "water": WATER_COLOR,
                "forest": FOREST_COLOR,
                "hill": HILL_COLOR,
                "swamp": SWAMP_COLOR,
                "desert": DESERT_COLOR
            }.get(tile, LAND_COLOR)
            pygame.draw.rect(screen, color, (x*TILE_SIZE, y*TILE_SIZE, TILE_SIZE, TILE_SIZE))

def draw_button(rect, text, screen, font, mouse_pos):
    color = BUTTON_HOVER if rect.collidepoint(mouse_pos) else BUTTON_COLOR
    pygame.draw.rect(screen, color, rect)
    pygame.draw.rect(screen, (0, 0, 0), rect, 2)
    surf = font.render(text, True, TEXT_COLOR)
    screen.blit(surf, surf.get_rect(center=rect.center))

def draw_units(units, screen):
    for u in units:
        center = (u.x * TILE_SIZE + TILE_SIZE // 2, u.y * TILE_SIZE + TILE_SIZE // 2)
        color = (255, 0, 0) if not u.selected else (0, 255, 0)
        pygame.draw.circle(screen, color, center, TILE_SIZE // 2)

def draw_grid(screen):
    # Серые сетки для карты
    for x in range(MAP_WIDTH + 1):
        pygame.draw.line(screen, (200, 200, 200), (x*TILE_SIZE, 0), (x*TILE_SIZE, MAP_HEIGHT*TILE_SIZE))
    for y in range(MAP_HEIGHT + 1):
        pygame.draw.line(screen, (200, 200, 200), (0, y*TILE_SIZE), (MAP_WIDTH*TILE_SIZE, y*TILE_SIZE))

def draw_highlight_tiles(screen, tiles):
    # Тонкая желтая рамка для подсветки доступных клеток движения
    for (x, y) in tiles:
        rect = (x*TILE_SIZE, y*TILE_SIZE, TILE_SIZE, TILE_SIZE)
        pygame.draw.rect(screen, (255, 255, 0), rect, 1)
