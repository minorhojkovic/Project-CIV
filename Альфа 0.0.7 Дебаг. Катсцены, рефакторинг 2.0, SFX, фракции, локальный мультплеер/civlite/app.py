from __future__ import annotations

from pathlib import Path
import pygame

from civlite.config import SCREEN_WIDTH, SCREEN_HEIGHT
from civlite.audio.music import MusicManager
from civlite.audio.sfx import SfxManager

from civlite.scenes.loading import run_loading_screen
from civlite.scenes.menu import run_main_menu
from civlite.scenes.settings import run_settings_menu
from civlite.scenes.setup import run_setup_scene
from civlite.scenes.game import run_game_scene


def _find_project_root() -> Path:
    here = Path(__file__).resolve()
    candidates = [Path.cwd().resolve()] + list(here.parents)
    for p in candidates:
        has_pkg = (p / "civlite").is_dir()
        has_assets = (p / "assets").is_dir()
        has_runner = (p / "run_game.py").is_file()
        if (has_pkg and has_assets) or (has_runner and has_assets) or (has_runner and has_pkg):
            return p
    return here.parents[1]


def _pick_ttf(fonts_dir: Path) -> Path | None:
    if not fonts_dir.exists():
        return None

    preferred = fonts_dir / "DejaVuSans.ttf"
    if preferred.exists():
        return preferred

    ttf_list = sorted(fonts_dir.glob("*.ttf"))
    if ttf_list:
        return ttf_list[0]

    return None


def _load_font(size: int) -> pygame.font.Font:
    root = _find_project_root()
    fonts_dir = root / "assets" / "fonts"
    font_path = _pick_ttf(fonts_dir)

    if font_path and font_path.exists():
        print(f"[FONT] Using TTF: {font_path}")
        return pygame.font.Font(str(font_path), size)

    print(f"[FONT] No .ttf found in: {fonts_dir} -> fallback SysFont")
    return pygame.font.SysFont(None, size)


class GameApp:
    def __init__(self):
        pygame.init()

        # ✅ текущее разрешение окна (по умолчанию — твой базовый размер из config)
        self.resolution = (SCREEN_WIDTH, SCREEN_HEIGHT)

        self.screen = pygame.display.set_mode(self.resolution)
        pygame.display.set_caption("Civilisation Lite")
        self.clock = pygame.time.Clock()

        self.font = _load_font(36)
        self.small_font = _load_font(24)

        self.fullscreen = False

        self.music_volume = 50
        self.sfx_volume = 60

        self.music = MusicManager(volume=self.music_volume)
        self.sfx = SfxManager(volume=self.sfx_volume)

        self.settings_return_scene = "main_menu"
        self.faction_roles = None

        self.game_state: dict = {
            "game_map": None,
            "units": [],
            "action_mode": None,
            "current_menu": None,
            "show_bottom": False,

            "bases": None,

            "faction_roles": None,

            "active_factions": None,
            "turn_order": None,
            "turn_index": 0,
            "major_turn": 1,
            "current_faction": None,

            "economy": None,
        }

    def run(self):
        scene = "loading"

        while True:
            if scene == "loading":
                scene = run_loading_screen(self.screen, self.clock, self.small_font, self.music)
                if scene == "exit":
                    break

            elif scene == "main_menu":
                result = run_main_menu(self.screen, self.clock, self.font, self.small_font, self.music)
                if result == "exit":
                    break

                if result == "settings":
                    self.settings_return_scene = "main_menu"

                scene = result

            elif scene == "setup":
                result_scene, self.faction_roles = run_setup_scene(
                    self.screen,
                    self.clock,
                    self.font,
                    self.small_font,
                    self.music,
                    faction_roles=self.faction_roles
                )

                if result_scene == "exit":
                    break

                if result_scene == "game":
                    self.game_state["game_map"] = None
                    self.game_state["units"] = []
                    self.game_state["bases"] = None

                    self.game_state["faction_roles"] = self.faction_roles

                    self.game_state["active_factions"] = None
                    self.game_state["turn_order"] = None
                    self.game_state["turn_index"] = 0
                    self.game_state["major_turn"] = 1
                    self.game_state["current_faction"] = None

                    self.game_state["economy"] = None

                scene = result_scene

            elif scene == "settings":
                # ✅ добавили resolution в параметры и в return
                scene, self.fullscreen, self.music_volume, self.sfx_volume, self.resolution = run_settings_menu(
                    self.screen,
                    self.clock,
                    self.font,
                    self.small_font,
                    self.music,
                    self.sfx,
                    fullscreen=self.fullscreen,
                    music_volume=self.music_volume,
                    sfx_volume=self.sfx_volume,
                    resolution=self.resolution,
                    return_scene=self.settings_return_scene,
                )

                # ✅ после set_mode внутри settings нужно обновить self.screen
                self.screen = pygame.display.get_surface()

                if scene == "exit":
                    break

            elif scene == "game":
                result = run_game_scene(
                    self.screen,
                    self.clock,
                    font=self.font,
                    small_font=self.small_font,
                    music=self.music,
                    sfx=self.sfx,
                    game_state=self.game_state
                )

                if result == "exit":
                    break

                if result == "settings":
                    self.settings_return_scene = "game"

                scene = result

            else:
                break

        pygame.quit()