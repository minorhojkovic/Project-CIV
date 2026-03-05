from __future__ import annotations

import os
import random
from pathlib import Path
import pygame


class MusicManager:
    """Centralized music playback for menu/loading/game."""

    def __init__(self, volume: int = 50):
        self.volume = int(volume)
        self.menu_music_flag = 0
        self.current_game_track: str | None = None

        base_dir = Path(__file__).resolve().parents[2]  # project root (folder containing 'civlite')
        assets_path = base_dir / "assets" / "sounds" / "music"

        self.menu_theme = str(assets_path / "Main Theme.mp3")
        self.loading_theme = str(assets_path / "Menu Theme.mp3")

        game_tracks = [
            "Gusto Della Vittoria.mp3","Hande Hoch.mp3","Johny the Peacemaker.mp3","Kousakuranoki.mp3",
            "Land in zicht!.mp3","Lianhuawan De Hongri.mp3","Nacionalna Garda.mp3","Ni Wakati Wa Taifa Letu.mp3",
            "Sultanin Zevk Yuruyusu.mp3","Viva la l'Ognion.mp3","Viviendo mi Vida Mas Plena.mp3","Yagodka Moya.mp3"
        ]
        self.game_tracks = [str(assets_path / t) for t in game_tracks]

    def _apply_volume(self):
        pygame.mixer.music.set_volume(self.volume / 100)

    def set_volume(self, volume: int):
        self.volume = max(0, min(100, int(volume)))
        self._apply_volume()

    def play_music(self, path: str, loop: bool = True):
        pygame.mixer.music.load(path)
        self._apply_volume()
        pygame.mixer.music.play(-1 if loop else 0)

    def stop_music(self):
        pygame.mixer.music.stop()

    def play_menu_music(self):
        if self.menu_music_flag == 0:
            pygame.mixer.music.load(self.menu_theme)
            self._apply_volume()
            pygame.mixer.music.play(-1)
            self.menu_music_flag = 1

    def play_loading_music(self):
        self.play_music(self.loading_theme, loop=True)

    def reset_menu_flag(self):
        self.menu_music_flag = 0

    def play_random_game_music(self):
        self.current_game_track = random.choice(self.game_tracks)
        pygame.mixer.music.load(self.current_game_track)
        self._apply_volume()
        pygame.mixer.music.play(0)

    def check_game_music(self):
        if not pygame.mixer.music.get_busy():
            self.play_random_game_music()
