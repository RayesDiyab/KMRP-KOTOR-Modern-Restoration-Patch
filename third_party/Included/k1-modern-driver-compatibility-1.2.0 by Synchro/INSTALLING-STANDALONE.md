# Installing K1 Modern Driver Compatibility without the Patch Manager

**If you would like to use the KotOR Patch Manager, use [the ordinary install](INSTALLING.md).**
It leaves your game files alone and can be switched off from a list.

This one is for a single case: something else has already modified your `swkotor.exe`, so the
Patch Manager no longer recognises it and refuses to patch it. That covers an install given more
memory, patched for a widescreen resolution, or unpacked from a store wrapper. This build checks
only the eight places it is about to change, so it does not mind what happened everywhere else.

Two files are copied into your game folder. Nothing is renamed and nothing is overwritten.

## Steps

1. **Get the zip and unzip it**, if you have not already. It is on the
   [Releases](https://codeberg.org/Synchro/kotor-modern-driver-compatibility/releases) page.
2. **Copy both files out of `Copy into game folder` into your game folder**, the one holding
   `swkotor.exe`. They are `dinput8.dll` and `k1-modern-driver-compatibility.asi`.
3. **On Linux, set one environment variable.** See the section below. Windows needs nothing here.
4. **Start the game however you normally do.** Steam, a desktop shortcut, Proton. It makes no
   difference, which is the point of this build.

There is no manager to open and nothing to configure.

## On Linux, through Wine or Proton

**This step is not optional.** Wine ships its own `dinput8.dll` and prefers it over the one in
your game folder, so without telling it otherwise the game starts and the patch is simply never
loaded.

Set this when launching:

```
WINEDLLOVERRIDES="dinput8=n,b"
```

For a Steam game, put it in the launch options, keeping `%command%` on the end:

```
WINEDLLOVERRIDES="dinput8=n,b" %command%
```

Lutris and Heroic both have a DLL overrides screen instead, where the entry is `dinput8` set to
`native, builtin`. It means the same thing: try the file in the game folder first, and fall back
to Wine's own if it is not there.

## Checking it worked

`logs/K1DriverCompat.log` appears in your game folder the first time you run it. Two lines matter,
in this order:

```
hooks installed=8/8
capability ati_fragment_shader=accepted
```

The first says the patch was applied. The second says the game reached it in time. **The first
without the second** means it loaded too late to do anything, which is worth reporting.

`hooks nothing matched` means your executable is not one this patch knows how to change. The log
names each address it did not recognise.

## If nothing happens

No log at all is almost always one of two things. On Linux, the environment variable above. On
Windows, `dinput8.dll` sitting somewhere other than beside `swkotor.exe`, which includes leaving
it where the zip put it.

Do not run this alongside the managed install. Both would patch the same eight places, and
whichever ran second would find them already changed and decline.

## What appears in your game folder

Two files, the first time you run it, the same as the managed install creates.

`logs/K1DriverCompat.log` holds one session and is overwritten each run. That is the file to send
if something looks wrong.

`K1DriverCompat.ini` holds every setting the patch has, explained, with all of them switched off.
You do not need to touch either file to play. The readme describes the settings if you ever want
them.

## Uninstalling

Delete `dinput8.dll` and `k1-modern-driver-compatibility.asi`. Nothing else was added and nothing
was changed, so that is all of it.

## Compatibility

Works with the GOG, Steam and CD 1.0.3 releases, including ones another tool has already modified.

It supersedes the separate cube map fix and soft shadow fix. Both are included here, so do not run
them alongside it.

`dinput8.dll` is Ultimate ASI Loader and is not part of this patch. Its terms, and those of
everything built into it, are in `THIRD-PARTY-NOTICES`.
