#!/usr/bin/env python3
"""One A on the last start-up movie must not press New Game: measured on the running game.

The maintainer's report: "when I press A to skip the game's intro movie, the movie skips but the
game also automatically activates New Game". Each trial starts the game, skips the movies before
the last with short presses, presses A once on the last, for a set time, and then reads which
screen the game is on. No further press is sent, so a screen past the main menu is the bug.

With `debug-logs=2` in the game's `configs\\kmrp-controller.ini` it also counts what the module
sent the game: `pad 1000 press` in `kmrp-controller-events.log`. The A that skipped the movie
should show as none. Sending one is the defect even in a run where the race goes the safe way and
the press reaches no screen.

    python testing/controller/trial_movie_skip.py --holds 0.1 0.2 0.5 --delays 0.3 1 --repeat 5

Writes `build/verify/movie-skip-<label>.json`. Needs the virtual pad, and nobody at the PC: it
starts the game full screen again and again. Documentation standard:
`docs/documentation-standard.md`.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from live_harness import VERIFY, Game, Pad, game_folder, wait_for


def movie_lines(folder: Path) -> int:
    log = folder / "KMRP" / "logs" / "kmrp-movie.log"
    try:
        return sum(1 for line in log.read_text(errors="replace").splitlines() if line.startswith("movie") or " movie " in line)
    except OSError:
        return 0


def sent_presses(folder: Path) -> int:
    log = folder / "KMRP" / "logs" / "kmrp-controller-events.log"
    try:
        return sum(1 for line in log.read_text(errors="replace").splitlines() if " pad 1000 press" in line)
    except OSError:
        return 0


def trial(game: Game, hold: float, delay: float, movies: int) -> dict:
    logs = game.folder / "KMRP" / "logs"
    (logs / "kmrp-movie.log").unlink(missing_ok=True)
    (logs / "kmrp-controller-events.log").unlink(missing_ok=True)
    timeline = []
    start = time.time()
    game.start()
    try:
        for number in range(1, movies + 1):
            if not wait_for(lambda: movie_lines(game.folder) >= number, 40):
                return {"hold": hold, "delay": delay, "error": f"movie {number} did not start",
                        "final": game.panel_names(), "movie_player": game.movie_player(),
                        "alive": game.alive()}
            timeline.append((round(time.time() - start, 2), f"movie {number}"))
            time.sleep(delay if number == movies else 0.3)
            if not game.alive():
                return {"hold": hold, "delay": delay, "error": "the game went away"}
            game.press(f"tap A {hold if number == movies else 0.08}")
            timeline.append((round(time.time() - start, 2), f"pressed {number}"))
        reached = wait_for(lambda: "main-menu" in game.panel_names(), 30)
        timeline.append((round(time.time() - start, 2), "main menu" if reached else "no main menu"))
        seen = []
        until = time.time() + 4
        while time.time() < until:
            names = game.panel_names()
            if names and (not seen or seen[-1] != names):
                seen.append(names)
            time.sleep(0.02)
        final = game.panel_names()
        return {"hold": hold, "delay": delay, "timeline": timeline, "panels": seen, "final": final,
                "past_menu": final[-1:] != ["main-menu"], "sent": sent_presses(game.folder)}
    finally:
        game.stop()
        Pad.send("reset")
        time.sleep(0.5)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--holds", type=float, nargs="+", default=[0.1, 0.2, 0.5, 1.0])
    parser.add_argument("--delays", type=float, nargs="+", default=[0.3, 1.0], help="seconds into the last movie")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--movies", type=int, default=3)
    parser.add_argument("--label", default="run")
    args = parser.parse_args()
    Pad.ensure_server()
    game = Game(game_folder())
    results = []
    for _ in range(args.repeat):
        for hold in args.holds:
            for delay in args.delays:
                row = trial(game, hold, delay, args.movies)
                results.append(row)
                print(json.dumps({k: row.get(k) for k in ("hold", "delay", "final", "past_menu", "sent", "error")}), flush=True)
                (VERIFY / f"movie-skip-{args.label}.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    bad = [r for r in results if r.get("past_menu")]
    sent = [r for r in results if r.get("sent")]
    print(f"{len(results)} trials: {len(bad)} past the main menu, {len(sent)} with the press sent to the game, "
          f"{sum(1 for r in results if 'error' in r)} errors")
    return 1 if bad or sent else 0


if __name__ == "__main__":
    raise SystemExit(main())
