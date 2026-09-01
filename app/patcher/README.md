# KOTOR Universal UI patcher

`KMRP.exe` is the single-file installer for all 48
supported resolutions. It contains the executable update, shared interface
artwork, and every matching GUI set, so no companion folders need to be
shipped. The earlier 3440 × 1440-only gold patcher remains frozen under
`releases\3440x1440-gold-final`.

The patcher accepts the supported editable `swkotor.exe`, creates recoverable
backups, updates the game executable, and configures `swkotor.ini`. Under
`[Graphics Options]`, it removes duplicate resolution keys and writes the
selected values, for example:

```ini
Height=1440
Width=3440
```

All other INI sections and settings are preserved.

The shared artwork is generated from:

```text
C:\Program Files (x86)\Star Wars - KotOR\Override
```

The per-resolution GUI layouts come from the preserved KOTOR High Resolution
Menus source package, with the exact final 3440 × 1440 GUI collection used for
that gold selection. During installation the selected files are written to the
game's `Override` directory and replace files with the same names. Existing
conflicting files are backed up first. **Restore Original** restores replaced
files and removes files introduced by the patcher.

At startup, a missing or unsupported executable opens a compatibility guide.
It links directly to the required
[KOTOR Editable Executable](https://deadlystream.com/files/file/1320-kotor-editable-executable/)
on Deadly Stream. **Patch Game** remains disabled until a compatible executable
and `swkotor.ini` are available. **Restore Original** remains disabled until
the required backups exist.

The executable uses `app\patcher\favicon.ico` for its Windows application and
window icon. The main window is resizable; its path and status areas expand,
while the action row remains anchored to the bottom. Horizontal growth is
capped so the utility remains readable on ultrawide desktops.

Build from the project directory:

```powershell
.\build_gold_patcher.ps1
.\build_universal_patcher.ps1
```

Automation-only command-line modes are also available:

```text
KMRP.exe --apply clean.exe output.exe 1920x1080
KMRP.exe --in-place swkotor.exe 1920x1080
KMRP.exe --restore swkotor.exe
```

`--in-place` performs the complete installation. `--restore` restores the EXE,
INI, and Override files. `--apply` creates only a patched executable and does
not change the INI or Override directory.
