#!/usr/bin/env python3
"""A save beside two enemies that last, for pad trials in combat.

Takes a save of the Endar Spire's first room and moves two hostile Sith soldiers next to the player,
with hit points enough for a long fight and the player unable to die. Writes only into the test
game's folder, and leaves the source save as it is. Saves are game data: nothing here is committed.

    python testing/controller/build_combat_fixture.py <game folder> <source save folder name>

Needs pykotor. Documentation standard: see `docs/documentation-standard.md`.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from pykotor.resource.formats.erf import bytes_erf, read_erf
from pykotor.resource.formats.gff import bytes_gff, read_gff
from pykotor.resource.type import ResourceType

TARGET = "000990 - Game989"
OFFSETS = ((3.0, 2.0), (3.0, -2.0))


def main() -> int:
    game, source = Path(sys.argv[1]), sys.argv[2]
    saves = next(p for p in (game / "Saves", game / "saves") if p.exists())
    origin = next(f for f in saves.iterdir() if f.name.startswith(source))
    target = saves / TARGET
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(origin, target)

    save_path = target / "SAVEGAME.sav"
    save = read_erf(save_path.read_bytes())
    entry = next(r for r in save if r.restype == ResourceType.SAV)
    module = read_erf(entry.data)
    git_entry = next(r for r in module if r.restype == ResourceType.GIT)
    ifo_entry = next(r for r in module if r.restype == ResourceType.IFO)
    git = read_gff(git_entry.data)
    ifo = read_gff(ifo_entry.data)

    player = ifo.root.get_list("Mod_PlayerList").at(0)
    px, py = player.get_single("XPosition"), player.get_single("YPosition")
    player.set_uint8("Min1HP", 1)
    creatures = git.root.get_list("Creature List")
    moved = 0
    for creature in creatures:
        if creature.get_string("Tag", "") == "sithsoldier" and moved < len(OFFSETS):
            dx, dy = OFFSETS[moved]
            creature.set_single("XPosition", px + dx)
            creature.set_single("YPosition", py + dy)
            creature.set_int16("CurrentHitPoints", 2000)
            creature.set_int16("HitPoints", 2000)
            creature.set_int16("MaxHitPoints", 2000)
            moved += 1
    if moved != len(OFFSETS):
        print("FAIL no hostile soldiers in that save")
        return 1

    module.set_data(str(git_entry.resref), ResourceType.GIT, bytes_gff(git))
    module.set_data(str(ifo_entry.resref), ResourceType.IFO, bytes_gff(ifo))
    save.set_data(str(entry.resref), ResourceType.SAV, bytes_erf(module))
    save_path.write_bytes(bytes_erf(save))

    info_path = target / "savenfo.res"
    info = read_gff(info_path.read_bytes())
    info.root.set_string("SAVEGAMENAME", "KMRP combat trial")
    info_path.write_bytes(bytes_gff(info))
    print(f"written {target}, player at {px:.1f},{py:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
