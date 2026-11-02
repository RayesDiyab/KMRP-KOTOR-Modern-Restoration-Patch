#!/usr/bin/env python3
"""From a cold start to a loaded save, by pad alone, and what the module logged about it.

Shared by the trials that need the game world: `Session.boot` skips the movies, opens Load Game
and loads the newest save, reading the panels before each press because a blind A presses whatever
has the focus. `Session.events` returns the module's level 2 lines since a mark, which is how a
trial tells one press from two: set `debug-logs=2` in the game's `configs\\kmrp-controller.ini`.

Documentation standard: see `docs/documentation-standard.md`.
"""
from __future__ import annotations

import time
from pathlib import Path

from live_harness import PANEL_NAMES, Game, Pad, game_folder, wait_for

PANEL_NAMES.setdefault(0x00757650, "save-load")
INPUT_CLASS_OFFSET = 0x9C


class Session:
    def __init__(self, folder: Path | None = None):
        self.game = Game(folder or game_folder())
        self.logs = self.game.folder / "KMRP" / "logs"
        Pad.ensure_server()
        Pad.send("reset")

    # ------------------------------------------------------------------ the log

    def event_lines(self) -> list[str]:
        try:
            return (self.logs / "kmrp-controller-events.log").read_text(errors="replace").splitlines()
        except OSError:
            return []

    def mark(self) -> int:
        return len(self.event_lines())

    def events(self, since: int, *needles: str) -> list[str]:
        lines = self.event_lines()[since:]
        return [line for line in lines if not needles or any(n in line for n in needles)]

    # ------------------------------------------------------------------ state

    def input_class(self) -> int | None:
        game = self.game
        root = game.u32(0x007A39FC)
        app = game.u32(root + 4) if root else None
        internal = game.u32(app + 4) if app else None
        return game.u32(internal + INPUT_CLASS_OFFSET) if internal else None

    def hud(self) -> int:
        for panel in self.game.panels():
            if self.game.u32(panel) == 0x00753F50:
                return panel
        return 0

    # ------------------------------------------------------------------ getting there

    def boot(self, movies: int = 3):
        game = self.game
        for name in ("kmrp-movie.log", "kmrp-controller-events.log"):
            (self.logs / name).unlink(missing_ok=True)
        game.start()
        log = self.logs / "kmrp-movie.log"

        def seen() -> int:
            try:
                return sum(1 for line in log.read_text(errors="replace").splitlines() if "movie" in line)
            except OSError:
                return 0

        # A movie's line is written as it starts. The last can start late or be missed when it
        # is pressed on at once, so the menu ends this, not a count of movies.
        pressed = 0
        deadline = time.time() + 60
        while time.time() < deadline and game.top() != "main-menu":
            if seen() > pressed and pressed < movies:
                pressed += 1
                time.sleep(0.5)
                game.press("tap A 0.08")
            time.sleep(0.05)
        if game.top() != "main-menu":
            raise RuntimeError(f"no main menu: {game.panel_names()}, {seen()} movies seen")
        time.sleep(2.0)
        return self

    def load_newest_save(self, seconds: float = 90.0):
        game = self.game
        game.press("dpad down 0.1")
        time.sleep(0.5)
        game.press("tap A 0.1")
        if not wait_for(lambda: game.top() == "save-load", 10):
            raise RuntimeError(f"Load Game did not open: {game.panel_names()}")
        time.sleep(1.5)
        game.press("tap A 0.1")
        time.sleep(1.0)
        if game.top() == "save-load":
            game.press("tap A 0.1")
        if not wait_for(lambda: self.hud() != 0 and self.input_class() == 0, seconds, 0.1):
            raise RuntimeError(f"no gameplay: {game.panel_names()} class {self.input_class()}")
        time.sleep(1.0)
        return self

    def close(self):
        self.game.stop()
        Pad.send("reset")
