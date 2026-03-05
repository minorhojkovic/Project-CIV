from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import pygame


def _find_project_root() -> Path:
    here = Path(__file__).resolve()
    candidates = [Path.cwd().resolve()] + list(here.parents)
    for p in candidates:
        has_pkg = (p / "civlite").is_dir()
        has_runner = (p / "run_game.py").is_file()
        has_assets = (p / "assets").is_dir()
        if (has_pkg and has_assets) or (has_runner and has_assets) or (has_runner and has_pkg):
            return p
    return here.parents[2] if len(here.parents) >= 3 else Path.cwd().resolve()


@dataclass
class SfxManager:
    volume: int = 60  # 0-100

    def __post_init__(self):
        self.project_root = _find_project_root()
        self.sfx_path = self.project_root / "assets" / "sounds" / "sfx"

        if not self.sfx_path.exists():
            raise FileNotFoundError(
                "Не найдена папка SFX.\n"
                f"Ожидалось: {self.sfx_path}\n"
                "Создай её и положи туда звуки."
            )

        # Базовые звуки
        self.unit_select_file = self.sfx_path / "unit_select.wav"
        self.unit_move_file = self.sfx_path / "unit_move.wav"

        # Катсцена порядка хода
        self.drum_start_file = self.sfx_path / "drumroll_start.wav"
        self.drum_loop_file = self.sfx_path / "drumroll.wav"
        self.drum_end_file = self.sfx_path / "drumroll_end.wav"

        self.dice1_file = self.sfx_path / "dice1.wav"
        self.dice2_file = self.sfx_path / "dice2.wav"
        self.dice3_file = self.sfx_path / "dice3.wav"
        self.dice4_file = self.sfx_path / "dice4.wav"

        required = (
            self.unit_select_file,
            self.unit_move_file,
            self.drum_start_file,
            self.drum_loop_file,
            self.drum_end_file,
            self.dice1_file,
            self.dice2_file,
            self.dice3_file,
            self.dice4_file,
        )
        for f in required:
            if not f.exists():
                raise FileNotFoundError(
                    f"Не найден SFX файл: {f}\n"
                    f"Положи его сюда: {self.sfx_path}"
                )

        # Загружаем
        self.unit_select = pygame.mixer.Sound(str(self.unit_select_file))
        self.unit_move = pygame.mixer.Sound(str(self.unit_move_file))

        self.drum_start = pygame.mixer.Sound(str(self.drum_start_file))
        self.drum_loop = pygame.mixer.Sound(str(self.drum_loop_file))
        self.drum_end = pygame.mixer.Sound(str(self.drum_end_file))

        self.dice1 = pygame.mixer.Sound(str(self.dice1_file))
        self.dice2 = pygame.mixer.Sound(str(self.dice2_file))
        self.dice3 = pygame.mixer.Sound(str(self.dice3_file))
        self.dice4 = pygame.mixer.Sound(str(self.dice4_file))

        # Выделенный канал под drumroll (важно для "дождаться конца цикла")
        try:
            self._drum_channel = pygame.mixer.Channel(5)
        except Exception:
            self._drum_channel = None

        # Состояние драмролла
        self._looping = False
        self._stop_after_cycle = False
        self._pending_end = False

        self.set_volume(self.volume)

    def set_volume(self, volume: int):
        self.volume = max(0, min(100, int(volume)))
        v = self.volume / 100.0

        self.unit_select.set_volume(v)
        self.unit_move.set_volume(v)

        self.drum_start.set_volume(v)
        self.drum_loop.set_volume(v)
        self.drum_end.set_volume(v)

        self.dice1.set_volume(v)
        self.dice2.set_volume(v)
        self.dice3.set_volume(v)
        self.dice4.set_volume(v)

        if self._drum_channel is not None:
            self._drum_channel.set_volume(v)

    def play_unit_select(self):
        self.unit_select.play()

    def play_unit_move(self):
        self.unit_move.play()

    def play_dice(self, idx: int):
        if idx == 1:
            self.dice1.play()
        elif idx == 2:
            self.dice2.play()
        elif idx == 3:
            self.dice3.play()
        else:
            self.dice4.play()

    # ----------------- Drumroll sequence -----------------
    def drum_play_start(self):
        """Сыграть старт драмролла (один раз)."""
        self._looping = False
        self._stop_after_cycle = False
        self._pending_end = False

        if self._drum_channel is not None:
            self._drum_channel.play(self.drum_start)
        else:
            self.drum_start.play()

    def drum_start_loop(self):
        """
        Запустить drumroll.wav "по циклам" (каждый раз loops=0),
        чтобы можно было корректно остановить ПОСЛЕ полного цикла.
        """
        self._looping = True
        self._stop_after_cycle = False
        self._pending_end = False

        # если канал свободен — стартуем сразу
        self.drum_update()

    def drum_request_stop_after_cycle(self):
        """Попросить остановиться после текущего цикла и затем сыграть drumroll_end."""
        self._stop_after_cycle = True

    def drum_is_busy(self) -> bool:
        if self._drum_channel is not None:
            return self._drum_channel.get_busy()
        return False

    def drum_update(self):
        """
        Вызывать каждый кадр во время катсцены.
        - если looping и канал свободен -> играем drumroll.wav (1 цикл)
        - если запросили stop_after_cycle и канал свободен -> играем drumroll_end и заканчиваем
        """
        if self._drum_channel is None:
            return

        if self._drum_channel.get_busy():
            return

        # канал свободен
        if self._pending_end:
            # end уже поставили — ничего не делаем
            return

        if self._looping:
            if self._stop_after_cycle:
                # цикл закончился, теперь играем end
                self._pending_end = True
                self._looping = False
                self._drum_channel.play(self.drum_end)
                return

            # продолжаем лупить циклы
            self._drum_channel.play(self.drum_loop)
