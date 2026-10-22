# Product

<!-- impeccable:product-schema 1 -->

## Platform

adaptive

A desktop app, native on Windows, Linux and macOS (one design language on all three; it
does not adopt each OS's own look).

## Stack

Rust and Slint, chosen by the maintainer (2026-10-22) over C++/SDL3, .NET and Tauri: a
native toolkit with no web view, small, quick to start, and it also runs under Wine/Proton.

## Users

Players of KotOR 1 and KotOR 2 (TSL) first: someone stuck on a quest, short of credits or
XP, unhappy with a build, missing a party member, or wanting to change an appearance. They
open the editor between play sessions with the game closed. Modders debugging scripts and
globals are a second audience, served in a separate area of the app.

## Product Purpose

KMRP Save Editor opens any KotOR 1 or 2 save, shows it in plain language, and changes it
without breaking it. It replaces the ageing KotOR Savegame Editor (KSE) for people on
today's platforms. Success: a player finds their save without configuring anything, makes
the change, and the game loads it.

## Positioning

Finds saves wherever the game keeps them (game folder, Steam Cloud, Aspyr ports on Linux
and macOS, Switch, Android) without an ini; edits safely, with a backup of every save it
writes and only well-formed changes; and fixes the edits KSE gets wrong (removing one Force
power removed all of them, level changes added the wrong Vitality, Max HP and FP edits the
game threw away).

KSE is inspiration for what to offer, never a source of code or architecture.

## Capabilities and Constraints

- Standalone: works with or without KMRP installed; no "needs KMRP" pop-up.
- KotOR 1 and KotOR 2. KotOR 2 was installed and tested on 2026-10-22 (German Steam
  release with TSLRCM): its saves read, edited and loaded in the game.
- Player-first edits: credits, XP and level, attributes, skills, feats, Force powers,
  inventory, party, appearance and portrait, influence (KotOR 2).
- Modder area: globals (and comparing two saves' globals), area objects (doors,
  containers, stores, creatures), player position.
- Lightweight and not animated (the maintainer, 2026-10-22).
- Every write keeps a backup first.

## Brand Commitments

- Name: "KMRP Save Editor", by RaymanGT, in the KMRP family next to the KMRP installer and
  the KMRP Font Converter.
- It must look like the KMRP Font Converter (`font-converter/FontConverter.cs`,
  screenshots in `build/font-converter/screenshots/`): same colours and type, and the
  same KMRP logo header (the maintainer: "Copy how the kmrp logo in the converter is").
  Not tiles (the maintainer turned a tile layout down, 2026-10-22): the editor is shaped
  like the game's in-game menu, tabs with the party down the left.
- Plain, short language; no em dashes.

## Evidence on Hand

- Real KotOR 1 saves in the maintainer's Steam game (`swkotor\saves`), read only for tests.
- Four KotOR 2 saves (Steam Cloud); no Switch, Android or Xbox saves on hand.
- The Save Editor's mark: a holocron with a datapad in front (`save-editor/assets/icon`, 2026-10-22);
  `save-editor-icon.png` for the window and the header, `save-editor.ico` for the program file.

## Product Principles

1. Never break a save: only well-formed changes, a backup before every write.
2. Find everything without setup.
3. Players first, in plain words; raw data stays in the modder area.
4. Say what the game will do: if the game recalculates a value, edit what it is made from
   and say so.
5. Small, quick and calm: no animation, no clutter.
