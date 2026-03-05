import pygame, random, math
from collections import deque

TILE_SIZE, MAP_WIDTH, MAP_HEIGHT = 10, 50, 50
SCREEN_WIDTH, SCREEN_HEIGHT = TILE_SIZE*MAP_WIDTH, TILE_SIZE*MAP_HEIGHT+60

# Цвета
WATER_COLOR = (0,105,148)
LAND_COLOR = (124,202,0)
FOREST_COLOR = (0,100,0)
HILL_COLOR = (128,128,128)
MOUNTAIN_COLOR = (64,64,64)
SWAMP_COLOR = (101,67,33)
DESERT_COLOR = (237,201,175)
BG_COLOR = (0,0,0)
MENU_COLOR = (169,169,169)
BUTTON_COLOR = (200,200,200)
BUTTON_HOVER = (150,150,150)
TEXT_COLOR = (0,0,0)

pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Civilisation Lite - Map Generator")
clock = pygame.time.Clock()
font = pygame.font.SysFont(None,24)

def distance(p1,p2): return math.sqrt((p1[0]-p2[0])**2+(p1[1]-p2[1])**2)

def draw_map(game_map):
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            tile = game_map[y][x]
            color = {
                "water": WATER_COLOR,
                "forest": FOREST_COLOR,
                "hill": HILL_COLOR,
                "mountain": MOUNTAIN_COLOR,
                "swamp": SWAMP_COLOR,
                "desert": DESERT_COLOR
            }.get(tile, LAND_COLOR)
            pygame.draw.rect(screen,color,(x*TILE_SIZE,y*TILE_SIZE,TILE_SIZE,TILE_SIZE))

def draw_button(rect,text,mouse_pos):
    color = BUTTON_HOVER if rect.collidepoint(mouse_pos) else BUTTON_COLOR
    pygame.draw.rect(screen,color,rect)
    pygame.draw.rect(screen,(0,0,0),rect,2)
    surf = font.render(text,True,TEXT_COLOR)
    screen.blit(surf,surf.get_rect(center=rect.center))

def generate_map():
    game_map = [["water"]*MAP_WIDTH for _ in range(MAP_HEIGHT)]

    # Создание континентов
    points=[]
    while len(points)<5:
        x,y=random.randint(0,MAP_WIDTH-1),random.randint(0,MAP_HEIGHT-1)
        if all(distance((x,y),p)>=10 for p in points):
            points.append((x,y))
            game_map[y][x]="land"

    total_tiles=MAP_WIDTH*MAP_HEIGHT
    target_land=random.randint(int(total_tiles*0.4),int(total_tiles*0.8))
    remaining_tiles=target_land-len(points)
    growth_limits=[max(5,remaining_tiles//5+random.randint(-5,5)) for _ in range(5)]

    for idx,(x,y) in enumerate(points):
        growth=[(x,y)]
        tiles=1
        while growth and tiles<growth_limits[idx]:
            cx,cy=random.choice(growth)
            neighbors=[(cx+dx,cy+dy) for dx in [-1,0,1] for dy in [-1,0,1]
                       if 0<=cx+dx<MAP_WIDTH and 0<=cy+dy<MAP_HEIGHT and game_map[cy+dy][cx+dx]=="water"]
            if neighbors:
                nx,ny=random.choice(neighbors)
                game_map[ny][nx]="land"
                growth.append((nx,ny))
                tiles+=1
            else: growth.remove((cx,cy))

    # Континенты
    visited=[[False]*MAP_WIDTH for _ in range(MAP_HEIGHT)]
    continents=[]
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            if game_map[y][x]=="land" and not visited[y][x]:
                queue=deque([(x,y)])
                visited[y][x]=True
                cont=[(x,y)]
                while queue:
                    cx,cy=queue.popleft()
                    for dx in [-1,0,1]:
                        for dy in [-1,0,1]:
                            nx,ny=cx+dx,cy+dy
                            if 0<=nx<MAP_WIDTH and 0<=ny<MAP_HEIGHT:
                                if game_map[ny][nx]=="land" and not visited[ny][nx]:
                                    visited[ny][nx]=True
                                    queue.append((nx,ny))
                                    cont.append((nx,ny))
                if len(cont)>=50: continents.append(cont)

    # Озёра
    for cont in continents:
        for _ in range(random.randint(1,2)):
            lx,ly=random.choice(cont)
            growth_points=[(lx,ly)]
            tiles=0
            limit=random.randint(5,15)
            while growth_points and tiles<limit:
                cx,cy=random.choice(growth_points)
                neighbors=[(cx+dx,cy+dy) for dx in [-1,0,1] for dy in [-1,0,1]
                           if 0<=cx+dx<MAP_WIDTH and 0<=cy+dy<MAP_HEIGHT and game_map[cy+dy][cx+dx]=="land"]
                if neighbors:
                    nx,ny=random.choice(neighbors)
                    game_map[ny][nx]="water"
                    growth_points.append((nx,ny))
                    tiles+=1
                else: growth_points.remove((cx,cy))

    # Биомы
    land_cells=[(x,y) for y in range(MAP_HEIGHT) for x in range(MAP_WIDTH) if game_map[y][x]=="land"]
    random.shuffle(land_cells)
    biome_settings=[("forest",8,(40,80)),("hill",5,(15,35)),("swamp",2,(5,15)),("desert",3,(25,50))]

    for biome,clusters,(min_s,max_s) in biome_settings:
        for _ in range(clusters):
            if not land_cells: break
            lx,ly=random.choice(land_cells)
            growth_limit=random.randint(min_s,max_s)
            growth_points=[(lx,ly)]
            tiles=0
            while growth_points and tiles<growth_limit:
                cx,cy=random.choice(growth_points)
                if game_map[cy][cx]=="land":
                    game_map[cy][cx]=biome
                    tiles+=1
                neighbors=[(cx+dx,cy+dy) for dx in [-1,0,1] for dy in [-1,0,1]
                           if 0<=cx+dx<MAP_WIDTH and 0<=cy+dy<MAP_HEIGHT and game_map[cy+dy][cx+dx]=="land"]
                if neighbors: growth_points.append(random.choice(neighbors))
                else: growth_points.remove((cx,cy))

    # Сглаживание
    new_map=[row[:] for row in game_map]
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            tile=game_map[y][x]
            if tile=="water": continue
            neighbors=[game_map[y+dy][x+dx] for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]
                       if 0<=x+dx<MAP_WIDTH and 0<=y+dy<MAP_HEIGHT]
            if tile not in neighbors:
                new_map[y][x]=game_map[y-1][x] if y>0 else "water"
                if new_map[y][x] not in ["land","forest","hill","swamp","desert","mountain"]:
                    new_map[y][x]="water"
    return new_map

def main():
    game_map=generate_map()
    running=True
    show_bottom=False
    top_button=pygame.Rect(10,10,80,30)
    bottom_gen=pygame.Rect(10,SCREEN_HEIGHT-40,150,30)
    bottom_exit=pygame.Rect(170,SCREEN_HEIGHT-40,100,30)

    while running:
        mouse_pos=pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type==pygame.QUIT: running=False
            if event.type==pygame.MOUSEBUTTONDOWN:
                if top_button.collidepoint(event.pos): show_bottom=True
                if show_bottom:
                    if bottom_gen.collidepoint(event.pos): game_map=generate_map()
                    elif bottom_exit.collidepoint(event.pos): running=False

        screen.fill(BG_COLOR)
        draw_map(game_map)
        pygame.draw.rect(screen,MENU_COLOR,(0,0,SCREEN_WIDTH,50))
        draw_button(top_button,"Игра",mouse_pos)
        if show_bottom:
            pygame.draw.rect(screen,MENU_COLOR,(0,SCREEN_HEIGHT-50,SCREEN_WIDTH,50))
            draw_button(bottom_gen,"Генерация мира",mouse_pos)
            draw_button(bottom_exit,"Выход",mouse_pos)
        pygame.display.flip()
        clock.tick(30)
    pygame.quit()

if __name__=="__main__":
    main()
