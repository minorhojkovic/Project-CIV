import random, math
from collections import deque

# --- Вспомогательная функция ---
def distance(p1, p2):
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)

def is_map_playable(game_map):
    """Проверка, что вся суша (кроме deep_water и mountain) связна."""
    height, width = len(game_map), len(game_map[0])
    visited = [[False]*width for _ in range(height)]

    def is_passable(tile):
        return tile not in ("deep_water", "mountain")

    # Находим стартовую проходимую клетку
    start = None
    total_passable = 0
    for y in range(height):
        for x in range(width):
            if is_passable(game_map[y][x]):
                total_passable += 1
                if not start:
                    start = (x, y)

    if not start or total_passable == 0:
        return False  # нет ни одной суши

    # BFS для обхода всех проходимых тайлов
    queue = deque([start])
    visited[start[1]][start[0]] = True
    reachable = 1

    while queue:
        x, y = queue.popleft()
        for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
            nx, ny = x+dx, y+dy
            if 0 <= nx < width and 0 <= ny < height:
                if not visited[ny][nx] and is_passable(game_map[ny][nx]):
                    visited[ny][nx] = True
                    reachable += 1
                    queue.append((nx, ny))

    # Проверяем связность
    return reachable >= total_passable * 0.95  # допускаем мелкие изолированные острова

# --- Основная генерация ---
def generate_map(MAP_WIDTH, MAP_HEIGHT):
    while True:  # перегенерируем пока карта не пройдет проверку
        game_map = [["water"] * MAP_WIDTH for _ in range(MAP_HEIGHT)]

        # Континенты
        points = []
        while len(points) < 5:
            x, y = random.randint(0, MAP_WIDTH-1), random.randint(0, MAP_HEIGHT-1)
            if all(distance((x, y), p) >= 10 for p in points):
                points.append((x, y))
                game_map[y][x] = "land"

        total_tiles = MAP_WIDTH * MAP_HEIGHT
        target_land = random.randint(int(total_tiles * 0.4), int(total_tiles * 0.8))
        remaining_tiles = target_land - len(points)
        growth_limits = [max(5, remaining_tiles // 5 + random.randint(-5, 5)) for _ in range(5)]

        for idx, (x, y) in enumerate(points):
            growth = [(x, y)]
            tiles = 1
            while growth and tiles < growth_limits[idx]:
                cx, cy = random.choice(growth)
                neighbors = [
                    (cx+dx, cy+dy)
                    for dx in [-1, 0, 1]
                    for dy in [-1, 0, 1]
                    if 0 <= cx+dx < MAP_WIDTH and 0 <= cy+dy < MAP_HEIGHT and game_map[cy+dy][cx+dx] == "water"
                ]
                if neighbors:
                    nx, ny = random.choice(neighbors)
                    game_map[ny][nx] = "land"
                    growth.append((nx, ny))
                    tiles += 1
                else:
                    growth.remove((cx, cy))

        # Биомы
        land_cells = [(x, y) for y in range(MAP_HEIGHT) for x in range(MAP_WIDTH) if game_map[y][x] == "land"]
        random.shuffle(land_cells)
        biome_settings = [
            ("forest", 8, (40, 80)),
            ("hill", 5, (15, 35)),
            ("swamp", 2, (5, 15)),
            ("desert", 3, (25, 50))
        ]

        for biome, clusters, (min_s, max_s) in biome_settings:
            for _ in range(clusters):
                if not land_cells:
                    break
                lx, ly = random.choice(land_cells)
                growth_limit = random.randint(min_s, max_s)
                growth_points = [(lx, ly)]
                tiles = 0
                while growth_points and tiles < growth_limit:
                    cx, cy = random.choice(growth_points)
                    if game_map[cy][cx] == "land":
                        game_map[cy][cx] = biome
                        tiles += 1
                    neighbors = [
                        (cx+dx, cy+dy)
                        for dx in [-1, 0, 1]
                        for dy in [-1, 0, 1]
                        if 0 <= cx+dx < MAP_WIDTH and 0 <= cy+dy < MAP_HEIGHT and game_map[cy+dy][cx+dx] == "land"
                    ]
                    if neighbors:
                        growth_points.append(random.choice(neighbors))
                    else:
                        growth_points.remove((cx, cy))

        # Сглаживание
        new_map = [row[:] for row in game_map]
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                tile = game_map[y][x]
                if tile == "water":
                    continue
                neighbors = [
                    game_map[y+dy][x+dx]
                    for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]
                    if 0 <= x+dx < MAP_WIDTH and 0 <= y+dy < MAP_HEIGHT
                ]
                if tile not in neighbors:
                    new_map[y][x] = game_map[y-1][x] if y > 0 else "water"
                    if new_map[y][x] not in ["land","forest","hill","swamp","desert"]:
                        new_map[y][x] = "water"
        game_map = new_map

        # Глубокое море
        deep_map = [row[:] for row in game_map]
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                if game_map[y][x] == "water":
                    nearest_land = min(
                        (abs(x - lx) + abs(y - ly))
                        for ly in range(MAP_HEIGHT)
                        for lx in range(MAP_WIDTH)
                        if game_map[ly][lx] != "water"
                    )
                    if nearest_land > 5:
                        deep_map[y][x] = "deep_water"

        # ✅ Проверка проходимости
        if is_map_playable(deep_map):
            return deep_map
        else:
            print("⚠️ Карта непроходима — перегенерация...")

