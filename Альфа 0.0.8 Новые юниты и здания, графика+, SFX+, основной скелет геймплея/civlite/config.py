# civlite/config.py

from __future__ import annotations

from pathlib import Path

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

# =========================================================
#                   ЭКОНОМИКА / ПРАВИЛА
# =========================================================

# Стартовые ресурсы "на складе" в начале игры (для каждой фракции)
START_GOLD = 5
START_FOOD = 5

# Разрешено уходить в минус по ресурсам
ALLOW_NEGATIVE_RESOURCES = True

# Ограничение действий при минусе:
# - если food < 0: запрещены любые действия, которые ТРЕБУЮТ трату еды
# - если gold < 0: запрещены любые действия, которые ТРЕБУЮТ трату золота
BLOCK_SPEND_WHEN_NEGATIVE = True

# Дебафф при отрицательной еде: юниты теряют X% боеспособности (урон/сила/эффективность — как ты решишь в логике)
NEGATIVE_FOOD_COMBAT_MULT = 0.50  # 50% боеспособности

# =========================================================
#                         ИКОНКИ
# =========================================================

# Путь: Civilisation Lite/assets/icons
PROJECT_ROOT = Path(__file__).resolve().parents[1]  # .../Civilisation Lite
ICONS_DIR = PROJECT_ROOT / "assets" / "icons"

# Какие фракции ожидаем в файлах иконок
ICON_FACTIONS = ("red", "yellow", "blue", "black")

def _icon_path(icon_key: str, faction: str) -> str:
    """
    icon_key: 'infantry', 'citadel', ...
    faction: 'red'/'yellow'/'blue'/'black'
    Файл: <icon_key>_<faction>.png
    """
    return str(ICONS_DIR / f"{icon_key}_{faction}.png")

def build_faction_icons(icon_key: str) -> dict[str, str]:
    """Возвращает dict: faction -> filepath."""
    return {f: _icon_path(icon_key, f) for f in ICON_FACTIONS}

# =========================================================
#                        ЗДАНИЯ
# =========================================================
# Добавлено поле:
#   "icon_key": str  # базовое имя файла без _faction.png
#   "icons": dict[str, str]  # готовые пути для всех фракций

BUILDINGS: dict[str, dict] = {
    # 1) Цитадель (База)
    "citadel": {
        "icon_key": "citadel",
        "icons": build_faction_icons("citadel"),

        "name": "Цитадель",
        "hp": 200,
        "unique": True,
        "buildable": False,
        "cost": {"gold": 0, "food": 0},
        "upkeep": {"gold": 0, "food": 0},
        "yield": {"gold": 5, "food": 5},
        "pop_cap": 5,
        "train_units": ["worker", "scout"],
        "vision": 5,
    },

    # 2) Жилое здание
    "housing": {
        "icon_key": "housing",
        "icons": build_faction_icons("housing"),

        "name": "Жилое здание",
        "hp": 40,
        "unique": False,
        "buildable": True,
        "cost": {"gold": 4, "food": 0},
        "upkeep": {"gold": 2, "food": 2},
        "yield": {"gold": 0, "food": 0},
        "pop_cap": 4,
        "train_units": [],
        "vision": 3,
    },

    # 3) Ферма
    "farm": {
        "icon_key": "farm",
        "icons": build_faction_icons("farm"),

        "name": "Ферма",
        "hp": 20,
        "unique": False,
        "buildable": True,
        "cost": {"gold": 4, "food": 0},
        "upkeep": {"gold": 2, "food": 0},
        "yield": {"gold": 0, "food": 4},
        "pop_cap": 0,
        "train_units": [],
        "vision": 3,
    },

    # 4) Шахта
    "mine": {
        "icon_key": "mine",
        "icons": build_faction_icons("mine"),

        "name": "Шахта",
        "hp": 20,
        "unique": False,
        "buildable": True,
        "cost": {"gold": 4, "food": 0},
        "upkeep": {"gold": 0, "food": 2},
        "yield": {"gold": 4, "food": 0},
        "pop_cap": 0,
        "train_units": [],
        "vision": 3,
    },

    # 5) Казармы
    "barracks": {
        "icon_key": "barracks",
        "icons": build_faction_icons("barracks"),

        "name": "Казармы",
        "hp": 50,
        "unique": False,
        "buildable": True,
        "cost": {"gold": 10, "food": 0},
        "upkeep": {"gold": 5, "food": 5},
        "yield": {"gold": 0, "food": 0},
        "pop_cap": 0,
        "vision": 3,
        "train_units": [
            "infantry",
            "heavy_infantry",
            "knight",
            "heavy_knight",
            "archer",
            "longbowman",
        ],
    },
}

# Какие здания доступны из меню "Постройки"
BUILD_MENU_ORDER: list[str] = ["housing", "farm", "mine", "barracks"]

# =========================================================
#                         ЮНИТЫ
# =========================================================
# Добавлено поле:
#   "icon_key": str
#   "icons": dict[str, str]

UNITS: dict[str, dict] = {
    # 1) Рабочий
    "worker": {
        "icon_key": "worker",
        "icons": build_faction_icons("worker"),

        "name": "Рабочий",
        "hp": 3,
        "attack": 1,
        "move_mult": 1.0,
        "vision_mult": 1.0,
        "range": 1,
        "cost": {"gold": 2, "food": 0},
        "upkeep": {"gold": 0, "food": 1},
        "pop_used": 1,
        "requires": {"building": "citadel"},
    },

    # 2) Разведчик
    "scout": {
        "icon_key": "scout",
        "icons": build_faction_icons("scout"),

        "name": "Разведчик",
        "hp": 1,
        "attack": 0,
        "move_mult": 2.0,
        "vision_mult": 2.0,
        "range": 1,
        "cost": {"gold": 4, "food": 0},
        "upkeep": {"gold": 1, "food": 1},
        "pop_used": 1,
        "requires": {"building": "citadel"},
    },

    # 3) Пехотинец (казармы)
    "infantry": {
        "icon_key": "infantry",
        "icons": build_faction_icons("infantry"),

        "name": "Пехотинец",
        "hp": 10,
        "attack": 5,
        "move_mult": 1.0,
        "vision_mult": 1.0,
        "range": 1,
        "cost": {"gold": 5, "food": 0},
        "upkeep": {"gold": 1, "food": 2},
        "pop_used": 1,
        "requires": {"building": "barracks"},
    },

    # 4) Тяжелый пехотинец (казармы)
    "heavy_infantry": {
        "icon_key": "heavy_infantry",
        "icons": build_faction_icons("heavy_infantry"),

        "name": "Тяжёлый пехотинец",
        "hp": 25,
        "attack": 10,
        "move_mult": 0.5,
        "vision_mult": 0.5,
        "range": 1,
        "cost": {"gold": 15, "food": 0},
        "upkeep": {"gold": 4, "food": 4},
        "pop_used": 2,
        "requires": {"building": "barracks"},
    },

    # 5) Рыцарь (казармы)
    "knight": {
        "icon_key": "knight",
        "icons": build_faction_icons("knight"),

        "name": "Рыцарь",
        "hp": 5,
        "attack": 10,
        "move_mult": 1.5,
        "vision_mult": 1.5,
        "range": 1,
        "cost": {"gold": 10, "food": 0},
        "upkeep": {"gold": 2, "food": 3},
        "pop_used": 1,
        "requires": {"building": "barracks"},
    },

    # 6) Тяжелый рыцарь (казармы)
    "heavy_knight": {
        "icon_key": "heavy_knight",
        "icons": build_faction_icons("heavy_knight"),

        "name": "Тяжёлый рыцарь",
        "hp": 15,
        "attack": 20,
        "move_mult": 1.0,
        "vision_mult": 1.0,
        "range": 1,
        "cost": {"gold": 30, "food": 0},
        "upkeep": {"gold": 5, "food": 4},
        "pop_used": 2,
        "requires": {"building": "barracks"},
    },

    # 7) Лучник (казармы)
    "archer": {
        "icon_key": "archer",
        "icons": build_faction_icons("archer"),

        "name": "Лучник",
        "hp": 3,
        "attack": 10,
        "move_mult": 1.0,
        "vision_mult": 1.5,
        "range": 3,
        "cost": {"gold": 10, "food": 0},
        "upkeep": {"gold": 1, "food": 1},
        "pop_used": 1,
        "requires": {"building": "barracks"},
    },

    # 8) Длинный лучник (казармы)
    "longbowman": {
        "icon_key": "longbowman",
        "icons": build_faction_icons("longbowman"),

        "name": "Длинный лучник",
        "hp": 3,
        "attack": 15,
        "move_mult": 1.0,
        "vision_mult": 1.0,
        "range": 6,
        "cost": {"gold": 20, "food": 0},
        "upkeep": {"gold": 4, "food": 3},
        "pop_used": 2,
        "requires": {"building": "barracks"},
    },
}

# Подсказка/порядок отображения в UI найма (если надо)
TRAIN_MENU_ORDER_CITADEL: list[str] = ["worker", "scout"]
TRAIN_MENU_ORDER_BARRACKS: list[str] = [
    "infantry",
    "heavy_infantry",
    "knight",
    "heavy_knight",
    "archer",
    "longbowman",
]