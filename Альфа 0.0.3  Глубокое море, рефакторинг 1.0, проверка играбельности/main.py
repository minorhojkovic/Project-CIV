import pygame
from config import SCREEN_WIDTH, SCREEN_HEIGHT, BG_COLOR, MENU_COLOR
from draw_utils import draw_map, draw_button
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

    top_button = pygame.Rect(10, 10, 80, 30)
    bottom_gen = pygame.Rect(10, SCREEN_HEIGHT - 40, 150, 30)
    bottom_exit = pygame.Rect(170, SCREEN_HEIGHT - 40, 100, 30)

    while running:
        mouse_pos = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.MOUSEBUTTONDOWN:
                if top_button.collidepoint(event.pos):
                    show_bottom = True
                if show_bottom:
                    if bottom_gen.collidepoint(event.pos):
                        game_map = generate_map(50, 50)
                    elif bottom_exit.collidepoint(event.pos):
                        running = False

        screen.fill(BG_COLOR)
        draw_map(game_map, screen)
        pygame.draw.rect(screen, MENU_COLOR, (0, 0, SCREEN_WIDTH, 50))
        draw_button(top_button, "Игра", screen, font, mouse_pos)
        if show_bottom:
            pygame.draw.rect(screen, MENU_COLOR, (0, SCREEN_HEIGHT - 50, SCREEN_WIDTH, 50))
            draw_button(bottom_gen, "Генерация мира", screen, font, mouse_pos)
            draw_button(bottom_exit, "Выход", screen, font, mouse_pos)

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()

if __name__ == "__main__":
    main()
