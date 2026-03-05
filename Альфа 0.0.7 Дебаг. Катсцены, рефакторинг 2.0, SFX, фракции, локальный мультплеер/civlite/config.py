# civlite/config.py

# --- Карта ---
TILE_SIZE = 10
MAP_WIDTH, MAP_HEIGHT = 50, 50

MAP_PIXEL_WIDTH = TILE_SIZE * MAP_WIDTH
MAP_PIXEL_HEIGHT = TILE_SIZE * MAP_HEIGHT

# --- UI панели (ВАЖНО: они НЕ перекрывают карту) ---
TOP_UI_HEIGHT = 50
BOTTOM_UI_HEIGHT = 50
EXTRA_DEBUG_HEIGHT = 40  # доп. панель выбора фракции (показывается только когда нужно)

# Общая высота экрана: верхняя панель + карта + нижняя панель + (место под доп. панель, даже если скрыта)
# Мы резервируем место, чтобы окно всегда было одного размера и ничего не "прыгало".
SCREEN_WIDTH = MAP_PIXEL_WIDTH
SCREEN_HEIGHT = TOP_UI_HEIGHT + MAP_PIXEL_HEIGHT + BOTTOM_UI_HEIGHT + EXTRA_DEBUG_HEIGHT

# --- Цвета тайлов ---
DEEP_WATER_COLOR = (0, 70, 120)
WATER_COLOR = (0, 105, 148)
LAND_COLOR = (124, 202, 0)
FOREST_COLOR = (0, 100, 0)
HILL_COLOR = (128, 128, 128)
SWAMP_COLOR = (101, 67, 33)
DESERT_COLOR = (237, 201, 175)

# --- Интерфейс ---
BG_COLOR = (0, 0, 0)
MENU_COLOR = (169, 169, 169)
BUTTON_COLOR = (200, 200, 200)
BUTTON_HOVER = (150, 150, 150)
TEXT_COLOR = (0, 0, 0)
