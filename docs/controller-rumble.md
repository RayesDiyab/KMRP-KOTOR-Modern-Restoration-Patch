# Controller rumble and haptics

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](documentation-standard.md). Read it before editing
> this file, and check the result still meets it — measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.

**Kind: reference**, for the rumble mixer in
[`src/controller-native/K1Rumble.cpp`](../src/controller-native/K1Rumble.cpp) as
of 2026-09-25. The lab record behind the engine side is
[`reverse-engineering/retained-xbox-gui-events.md`](../reverse-engineering/retained-xbox-gui-events.md#rumble-complete-running-and-starved-of-one-field),
and the controller as a whole is described in
[`controller-support.md`](controller-support.md).

**Status: felt on an Xbox pad, 2026-09-25, and judged right.** Four pad tests
that day tuned it; the last, with the defaults below, logged and felt saber
ignition, the pulsed hum and retraction, saber hits landing, blade-on-blade
clashes and a parry, damage taken, blaster bolts striking, and a frag grenade
1.0 m away. **Not yet felt:** a grenade past BioWare's 5 m (the Enhanced reach),
recoil from the controlled character's own shots, Force powers, the Stomp
footsteps, Whirlwind, lightning and drain, droid explosions, the scripted
Endar Spire tremors, Original mode, and any PlayStation, Switch or Steam Deck
pad. Everything else below was read out of the clean executable or checked by
the build tools. The checklist at the end is the test that was run.

## Three kinds of rumble, never mixed up

| Name used here | What it is | Existed on Xbox? | Plays in mode |
| --- | --- | --- | --- |
| **Original BioWare rumble** | BioWare's `rumble.2da` rows, fired where the shipped PC content fires them: scripts, `footstepsounds.2da`, `visualeffects.2da`. | The table did. The PC triggers are the PC game's own. | Original, Enhanced |
| **Restored cut BioWare rumble** | Two BioWare rows nothing shipped ever fires, attached by KMRP to the events their names describe: 0 `LightSaberOn` to a lit lightsaber, 21 `Whirlwind` to being caught in Force Whirlwind. | The rows did. What triggered them there is **not known**; the attachments are KMRP's. | Enhanced |
| **KMRP Enhanced Haptics** | KMRP's own patterns, named `KMRP_…` and numbered from 100, plus KMRP's use of BioWare's Rancor row on the Rancor's death. | **No.** None of this existed on Xbox. | Enhanced |

BioWare's rows 0–21 are never edited and never reused for KMRP patterns. Every
line in the debug log says which of the three a rumble is.

## Settings

`kmrp-controller.ini`, beside `swkotor.exe`. The installer writes it when it is
absent. Once you edit it, it is yours: the installer never overwrites it, an
edited copy never stops an install, and Restore leaves it in place.
`Test-ControllerSupport.ps1` Case 7 checked all three until the test was removed
with the four-patch layout on 2026-10-04; no test checks them now.

```ini
[Rumble]
Mode=Enhanced     ; Off | Original | Enhanced
Strength=100      ; 0-100 percent
SaberHum=6        ; the lightsaber hum, 0-100 percent of BioWare's level; 0 is off
SaberHumPulseMs=100       ; the hum pulses: on this long (0 is a steady hum)...
SaberHumPeriodMinMs=500   ; ...then off until the next pulse, a gap drawn at
SaberHumPeriodMaxMs=2000  ;    random between these two, afresh every pulse;
                          ;    equal values give a fixed rhythm
Debug=0           ; 1 writes kmrp-rumble.log beside swkotor.exe
```

The module checks the file at most once a second and re-reads it when it
changes, so it can be tuned with the game running. The defaults are what the
pad tests of 2026-09-25 settled on (`DefaultSettings` in `KmrpPatcher.cs`, and
the same values in `LoadSettings` for a file missing a key). `Debug` was 1 in
the hardware-test builds and is 0 since they passed. There is no in-game or
installer control for these yet.

| Mode | Plays |
| --- | --- |
| Off | Nothing. The motors are sent zero every frame. |
| Original | BioWare's shipped mappings only, each at full strength inside its 2DA cutoff, exactly as the PC content asks. |
| Enhanced | Original, faded with distance, plus the restored rows and KMRP's haptics. |

## How it works

### One mixer

Every rumble is a **layer**: a pattern in BioWare's envelope format, a start
time, a scale and its provenance. Each frame, every live layer is evaluated and
the **maximum per motor** is kept. Heavy (left, envelope A) and light (right,
envelope B) are mixed separately. The result is then scaled:

```
output = pattern magnitude × distance scale × strength
```

Taking the maximum means two effects at 60% stay at 60% instead of adding up
to 120%. A quiet loop, such as the saber hum, is covered by any stronger
transient and comes back when that transient ends.

| Rule | Where | Why |
| --- | --- | --- |
| The evaluator reproduces `CSWRumblePattern::GetMagnitude` (`0x0068FCB0`) | `Evaluate` | BioWare's rows must feel as authored: linear between keyframes, 0 before the first and after the last, loops wrapped by the last keyframe's time |
| Repeats of one pattern inside a short window merge, keeping the larger scale | `Play`, `merge` | five damage events in 50 ms are one hit, not five. Windows: damage 50 ms, VFX rules and saber hits 40 ms, ignition 150 ms (both blades of a pair) |
| Recoil and electricity never merge | `merge` = 0 | a repeater is supposed to repeat |
| A keyed layer is a state, not an event | `Hold` | the hum and the Whirlwind, electric and drain loops are re-derived every frame from what is true, so every way a state can end (retract, unequip, switching character, death, loading) ends the loop without a case of its own |
| Most KMRP patterns stay in the lower half of the range | the `KMRP_ENV` tables | strength is kept for explosions, collapses and huge creatures |

### The clock is the engine's

The mixer's clock advances by `UpdateRumble`'s frame-time argument, and only on
frames where `UpdateRumble` would have advanced its own patterns. The engine
skips them on its own bail paths, read from the clean executable:

```
005F7503  fld   dword ptr [esp+0x14]      frame time
005F7508  fcomp dword ptr [0x73D700]      <= 0.0 -> bail
005F752B  mov   eax, [ebp+0x288]          non-zero -> bail
005F753C  call  CGuiInGame::IsGlobalFadeObscuring   -> bail
005F754C  call  CGuiInGame::IsGlobalFading          -> bail
005F755B  call  CClientExoAppInternal::LoadScreenExists -> bail
```

The motors are also **muted**, with time left running, while `CExoInput`'s
rumble pause is set and while a menu is open (input class 2). The combat pause,
the auto-pause and the autosave call `PauseRumble` (`0x005DF570`) and
`UnpauseRumble` (`0x005DF580`). None of `UpdateRumble`'s bails tests that pause,
so the engine's own patterns keep advancing through it. The mixer does the
same: a scripted tremor that outlasts a pause has finished when the pause ends,
as vanilla. The hum, being a state, is simply felt again.

*Corrected before any test:* the first builds of this mixer (`13ADCC63…`,
`F328A18A…`) froze the clock and dropped one-shot layers on the pause and in
menus as well. That would have cut short, or held back, an Original pattern
that the engine lets run on.

With no player creature, which means loading, the main menu or a module
change, every layer is stopped and the health baseline forgotten.

### Hooks

Build: the clean executable, `build-inputs/swkotornopatch.exe`, 4,042,752
bytes, SHA-256 `761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886`.
All sites are in `.text`, so `FILE = VA − 0x400000`. None of them changes a byte
on disk. KPM detours them in memory from `patch_config.toml`, and
`Test-ControllerSupport.ps1` checks that the stolen bytes are intact in the
patched executable.

| VA | FILE | Stolen bytes | Function | Handler | Kind |
| --- | --- | --- | --- | --- | --- |
| `0x005F7617` | `0x001F7617` | `68 C0 27 09 00` | `UpdateRumble`, before `SetRumble` | `NativeRumbleK1` → `KmrpRumbleTickK1` | observer, per frame (existed; gains `esp+24`) |
| `0x005FB49F` | `0x001FB49F` | `3B A9 44 03 00 00` | `PlayRumblePattern`, index test | `NativeRumblePlayK1` | **consumed**, exit `0x005FB536` |
| `0x005F74B0` | `0x001F74B0` | `56 8B B1 50 03 00 00` | `StopRumblePattern`, entry | `NativeRumbleStopK1` | observer |
| `0x005FB98E` | `0x001FB98E` | `0F B6 45 0C 83 E8 00` | `LookUpAndPerformRumbleWithCutOff`, after its prologue | `NativeRumbleCutoffK1` | observer |
| `0x00646BA0` | `0x00246BA0` | `A1 FC 39 7A 00 56` | `CSWCItem::ResolveCreaturePoweredAnimations`, entry | `NativeSaberPowerK1` | observer |
| `0x0060DE20` | `0x0020DE20` | `83 EC 1C 56 8B F1` | `CSWCCreature::ShowLightSaberContactVisual`, entry | `NativeSaberContactK1` | observer |
| `0x00617EB0` | `0x00217EB0` | `64 A1 00 00 00 00` | `HitEvent`, the animation event "hit", entry | `NativeMeleeHitK1` | observer |
| `0x0063C4F0` | `0x0023C4F0` | `51 8B 49 68 85 C9` | `CSWCObject::AnimationParry`, entry | `NativeParryK1` | observer |
| `0x006D4440` | `0x002D4440` | `53 8B 5C 24 08 56` | `CSWCProjectile::CreateMuzzleFlash`, entry | `NativeMuzzleFlashK1` | observer |

The annotated disassembly for each is in
[`src/controller-native/kotor1.hooks.toml`](../src/controller-native/kotor1.hooks.toml).
`tools/check_hook_stolen_bytes.py` passes for all of them, and
`tools/check_patcher_hook_table.py` finds the patcher's table and the TOML in
agreement: 26 native hooks and 4 byte patches when the mixer shipped
(2026-09-25). That count has since grown -- 35 native hooks and 4 byte patches
on 2026-09-28, with the character-creation and echo guards and the no-controller
stand-ins -- and the eight hooks above are unchanged.

**The play hook is the only one that declines the original.** It returns 1,
and KPM exits to `0x005FB536`, the function's own `pop edi / pop esi / xor
eax,eax / pop ebp / ret 4`. So the engine's instance list stays empty, and the
mixer is the one thing driving the motors. `return 0` is what the shipped PC
game returned for every call, because its pattern count was zero. The only
caller that reads the value is the script command, which pushes it as the
script's result. The handler keeps the engine's one refusal: a *looping* row
that is already playing is not started again (`0x005FB4BB` tests the row's
loop flag, `0x005FB4D0` searches the queue), while a one-shot row overlaps its
running copy freely. The engine's pattern table is still installed
(`EnsureRumbleTableK1`), so that without this hook the engine plays BioWare's
rows itself, as the previous build did.

### Positional rumble: vanilla's gate, Enhanced's fade

`LookUpAndPerformRumbleWithCutOff` reads `RumblePattern` and `RumbleCutOff`
from `footstepsounds.2da` (category 0, by row) or `visualeffects.2da` (category
1, by row label, which is the VFX id). It plays the pattern only when the
listener is inside the cutoff. The observer makes the same lookups through the
same accessors (`C2DA::GetINTEntry` `0x00413660`/`0x00414110`,
`GetFLOATEntry` `0x00413430`/`0x00413FA0`, argument order read from the calls
at `0x005FBA30`–`0x005FBAF9`):

- **A row BioWare authored.** In **Original** mode the engine decides, exactly
  as vanilla: it measures from its own listener and calls `PlayRumblePattern`
  synchronously from `0x005FBBC4` when inside the cutoff, and the play handler
  labels the rumble with the distance the observer recorded. In **Enhanced**
  mode the observer plays the row itself, measured from the controlled
  character, and the engine's own play of it is swallowed. It reaches three
  times BioWare's cutoff where that is under 10 m (grenades and Force Wave
  15 m, Push and Choke 6 m) and BioWare's own beyond, and fades:

  ```
  inner = max(cutoff / 4, 2 m)
  scale = 1                               distance <= inner
        = 1 - smoothstep((d - inner) / (cutoff - inner))   inner < d < cutoff
        = 0                               distance >= cutoff
  ```

  | Row | BioWare's cutoff | Enhanced reach | Full to | Half at | Silent at |
  | --- | --- | --- | --- | --- | --- |
  | Force Choke, Force Push (20) | 2 m | 6 m | 2 m | 4 m | 6 m |
  | Grenades, Force Wave (14, 20) | 5 m | 15 m | 3.75 m | 9.4 m | 15 m |
  | Terentatek death (11) | 5 m | 15 m | 3.75 m | 9.4 m | 15 m |
  | Stomp footsteps (17) | 20 m | 20 m | 5 m | 12.5 m | 20 m |
  | `VFX_IMP_SCREEN_SHAKE` (16) | 30 m | 30 m | 7.5 m | 18.75 m | 30 m |

  Inside BioWare's cutoff the rumble is labelled Original; past it, where
  vanilla plays nothing, Enhanced. **Why the reach, from the first combat
  test:** not one positional rumble was logged, grenades included. A grenade
  thrown at an enemy lands well past 5 m, and the engine measures from the
  sound listener -- `CExoSound::GetListenerPosition`, the camera, behind the
  player -- whenever the in-game GUI's `+0xB4` is set:

  ```
  005FBB41  call CClientExoApp::GetInGameGui
  005FBB46  mov  ecx, [eax+0xB4]          non-zero ->
  005FBB5B  call CExoSound::GetListenerPosition
  005FBB62  mov  ecx, [esp+0x20]          else the player creature...
  005FBB66  add  ecx, 0x24                ...its position
  005FBBA4  fld  [cutoff] / fmul / fcompp  play only if d^2 <= cutoff^2
  ```

  Which one it uses in play is not yet measured; every lookup now logs it.

  The 2 m floor on "full to" is there because Force Push and Choke land on
  the *target*: a push at an enemy 1.8 m away is as close as melee gets.

- **A row BioWare left empty.** In Enhanced mode, KMRP's VFX rules apply
  (next section).

**On the player, by identity rather than distance.**
`CSWCVisualEffectOnObject::StartVisualEffect` passes the carrying object's own
position field:

```
006A6514  call CClientExoApp::GetGameObject     the object the VFX is on
006A6521  call dword ptr [edx+0xC]              as a CSWCObject
006A6538  add  eax, 0x24                        -> &object->position
006A653B  push eax
```

So `position − 0x24` *is* the object. A VFX is on the controlled character
when that equals the player creature, and on its target when that object's id
equals `CurrentTargetK1()`. A companion standing close by never counts as the
player.

### Enhanced: the rules

These apply only to VFX rows whose `RumblePattern` is empty. A rule can fire
on the controlled character, on its current target (the player's own attack or
power landing), or anywhere in a radius with the fade above.

| VFX | Label | On player | On target | World |
| --- | --- | --- | --- | --- |
| 4004 | `VFX_COM_SPARKS_LIGHTSABER` | `KMRP_SABER_CLASH` | `KMRP_SABER_CLASH` | — |
| 4023 | `VFX_COM_BLASTER_DEFLECTION` | `KMRP_BLASTER_DEFLECT` | — | — |
| 4024 | `VFX_COM_BLASTER_IMPACT` | `KMRP_BLASTER_HIT_RECEIVED` | — | — |
| 4025–4028, 4030, 4031, 4017 | Critical Strike, Power Attack, Flurry, Whirlwind Strike (saber) | `KMRP_SABER_SPECIAL` | `KMRP_SABER_SPECIAL` | — |
| 4013, 4029 | `VFX_COM_POWER_BLAST_*` | `KMRP_BLASTER_RIFLE_RECOIL` | same | — |
| 1021, 1028, 1035, 1036 | `VFX_PRO_LIGHTNING_*` | `KMRP_FORCE_LIGHTNING` | `KMRP_FORCE_LIGHTNING_CAST` | — |
| 1009 | `VFX_PRO_DRAIN` | (the drain loop) | `KMRP_FORCE_CONFIRM` | — |
| 1018 | `VFX_IMP_FORCE_WHIRLWIND` | (the Whirlwind loop) | `KMRP_FORCE_CONFIRM` | — |
| 1010, 1015, 1020, 1022 | Force Armor, Force Shield, Knight and Master Speed | `KMRP_FORCE_CONFIRM` | — | — |
| 1040 | `VFX_IMP_STUN` | `KMRP_STUN` | — | — |
| 4034, 4035 | `VFX_COM_DROID_EXPLOSION_*` | — | — | `KMRP_DROID_EXPLOSION`, 12 m |
| 3006, 3008 | poison and adhesive grenades | — | — | `KMRP_SOFT_GRENADE`, 5 m |
| 3002 | `VFX_FNF_PLOT_MAN_SONIC_WAVE` | — | — | `KMRP_SONIC`, 12 m |
| 3014, 3015 | `VFX_FNF_ROCK_FALL_*` | — | — | `KMRP_DEBRIS`, 18 m |
| 3016 | `VFX_FNF_SPACE_LASER` | — | — | `KMRP_SHIP_IMPACT`, 40 m |
| 1045 | `VFX_PLOT_TAR_RANCOR_DEATH` | — | — | BioWare 11 `Rancor`, 30 m |

The 5 m cutoff for the two soft grenades is the one BioWare gave their five
explosive siblings. The other cutoffs are KMRP's choice. They are marked for
tuning on hardware.

### Enhanced: states and events outside the VFX table

| Event | Source | Pattern | Provenance |
| --- | --- | --- | --- |
| Saber lit, held | `NativeSaberPowerK1` tracks every saber's state by item id and owner. The tick counts the controlled character's lit blades that are also in its main or off hand (`GetEquippedItemID` `0x10`/`0x20`). | BioWare 0 `LightSaberOn` looped, at `SaberHum` percent (default 6), pulsed by default: 100 ms on, then a random 500–2000 ms gap, drawn again for every pulse. Two blades: ×1.15. | Restored |
| Saber ignites / retracts | the same hook, on a state change of a controlled character's blade | `KMRP_SABER_IGNITE` / `KMRP_SABER_RETRACT` | Enhanced |
| Your blow lands | `NativeMeleeHitK1`: the attack record's attacker is the controlled character and its result is 1, 2, 3 or 5, the engine's hit branch | `KMRP_SABER_HIT` with a saber, `KMRP_MELEE_HIT` with any other melee weapon | Enhanced |
| Blade meets blade | `NativeSaberContactK1`: the animation event "Contact", which puts `VFX_COM_SPARKS_PARRY_METAL` on the blade | `KMRP_SABER_CLASH`, merged with the parry within 0.2 s | Enhanced |
| Parry | `NativeParryK1`, the parrying object is the controlled character or its target | `KMRP_SABER_CLASH` | Enhanced |
| Shot fired | `NativeMuzzleFlashK1`: the projectile starts within 1.6 m of the controlled character, who holds a ranged weapon | pistol (baseitems 12–17), rifle (18–22, 77) or repeater (23–24) recoil | Enhanced |
| Damage taken | HP polled every frame (below) | `KMRP_PLAYER_DAMAGE`, or `…_HEAVY` for a fifth of the bar or more | Enhanced |
| Death | HP reaches 0 | everything stops, then `KMRP_PLAYER_DEATH` once | Enhanced |
| Caught in Whirlwind | `VFX_DUR_FORCE_WHIRLWIND` (2007) on the controlled character | BioWare 21 `Whirlwind` looped, until the VFX goes | Restored |
| Lightning, shock, stun or ion beam on the character | VFX 2037, 2038, 2049, 2050, 2052, 2061, 2065, 2066, 1021, 1028, 1035, 1036 | `KMRP_ELECTRIC_LOOP` | Enhanced |
| Drained | VFX 2029, 1009 | `KMRP_FORCE_DRAIN_LOOP` | Enhanced |

**Why the saber is read at `ResolveCreaturePoweredAnimations`, not
`PowerItem`.** `CSWCItem::PowerItem` (`0x00647130`) receives the requested
state. It can then force the blade off while the area is not ready
(`0x006471CA`–`0x006471F7`), or return without doing anything
(`0x00647166`, `0x006471BB`). It calls `ResolveCreaturePoweredAnimations`
with the state it settled on, from `0x006471F7` (forced off) and `0x00647204`
(as requested). That function reads the owner id at `[item+0x160]` and
compares `[item+0x14]` with `GetEquippedItemID`, which confirms both offsets
the handler uses.

**Damage.** Current and maximum HP are read through the server creature's
vtable, the same way the HUD reads them: slot `0x9C` with 0, and slot `0x98`
with 1 (`0x006879D0`, `0x006879E0`). A drop becomes one hit. Drops inside 50 ms
of that hit join it. The intensity is
`0.30 + 0.50 × smoothstep(0, 0.3, damage / max HP)` (the floor was 0.12 until the
first combat test): a scratch still registers,
three tenths of the bar is the ceiling, and nothing exceeds 0.8. A new
controlled character sets a new baseline instead of counting as a hit, and
nothing registers once the character is dead: hit points can go on falling
below zero, and the death impact is the last thing felt.

**Recoil identifies the shooter by position.** No owner field on
`CSWCProjectile` has been identified. The 1.6 m threshold is a guess, and the
first 40 muzzle flashes of a session are logged with their distance and the
player's weapon either way, so one test shows whether it holds.

**First pad test, 2026-09-25: the hum was far too strong.** It played BioWare's
`LightSaberOn` as authored: a constant 0.20 on the light motor, 0.23 with two
blades (the log read `light=0.23`), held for as long as a blade was lit. The
row is unchanged. The hum now plays at `SaberHum` percent of it, default 30:
0.06, or 0.07 with two blades. Ignition used to settle at 0.20 before handing
over; it now falls to 0 and the hum shows through underneath. The lifecycle
itself behaved in that test: ignite, hum, retract, the hum stopping, and the
motors muting in a menu, all in the order expected.

**Second pad test, same day, an Xbox pad over XInput: even the weakest steady
hum was too strong.** Tuned live, the log records SaberHum 30, 15, 1, 5, 10, 7
and 6, all with two blades, and 6 was still too strong. The reason is the pad,
not the setting: an Xbox One or Series controller takes each motor as a whole
percentage, so 1 (0.23% of full) plays as nothing while 5, 6 and 7 (1.15%,
1.38%, 1.61%) all land on the lowest step, 1%. That is the weakest vibration
the pad can make. SDL's own Xbox One driver converts this way (16-bit value to
0–100). Windows' driver is undocumented, and the test is consistent with it.
An Xbox 360 pad takes 0–255 instead, so its floor is lower, about SaberHum 2.

So the hum is now **pulsed** by default: the lowest step, on for 50 ms in every
500 ms, weaker on average than any steady level. `SaberHumPulseMs` and
`SaberHumPeriodMs` tune it live. The pulse gates BioWare's row in the mixer
(`Mix`, the `KEY_HUM` layer's light output) rather than replacing it, and
`SaberHumPulseMs=0` gives the steady hum back.

**Third pad test, same day: the pulse, tuned live.** It was felt, and settled
at `SaberHum=6`, `SaberHumPulseMs=100`, `SaberHumPeriodMs=1500`. The user then
asked for the gap to vary, drawn at random between 1000 and 2000 ms for every
pulse, so the blade flickers rather than ticks, and for both ends of that
range to be editable: `SaberHumPeriodMinMs` and `SaberHumPeriodMaxMs`, which
replace the single `SaberHumPeriodMs` of the pulse's first build. Tuned live
after that, the user settled the shortest gap at 500 ms. So the defaults are
100 ms pulses with a gap between 500 and 2000 ms (`HumGatedOff` in
`K1Rumble.cpp`). The first build's 50 ms every 500 ms was
never tried as such. **The random gap itself is untested on a pad.** Not done: driving the Xbox One and Series trigger
motors, the subtlest actuators on the pad, which XInput cannot reach.

**First combat test, same day, Xbox pad: "nothing at all triggered", not even
a grenade.** The log and the module's own send counter
(`kmrp-native-joystick.log`, `rum=calls/sends/last`) told three different
stories:

- The patterns that played reached the pad at the strength intended. At the
  moment of a parry the counter held heavy `0x10CB` and light `0x7EC6`, which
  is 6.6% and 49.5% of full power, and a damage hit showed 10.7% heavy. But
  every KMRP one-shot pattern then lasted 0.10–0.22 s, and started fading from
  its first frame. The user found that even a 100 ms vibration "only barely
  activates" the motor. BioWare's own patterns are all half a second or
  longer. Every one-shot pattern now holds its peak for 100–180 ms and runs
  0.3–0.6 s in all. The electric chatter slowed from 20 Hz to 4 Hz, and the
  damage floor rose from 0.12 to 0.30.
- **No saber hit could ever fire.** The hook read the animation event
  "Contact" as the blade connecting. That event puts
  `VFX_COM_SPARKS_PARRY_METAL` on the blade's `LightSaberHook` node
  (`0x0060DE67`–`0x0060DEB2`): blade meeting blade. A blow landing is the event
  "hit", `HitEvent` (`0x00617EB0`), and that is now the hit hook. "Contact" is
  now a clash.
- Not one positional rumble was logged, grenade included. See the reach above.

`CSWCCreature::RegisterCallbacks` (`0x0061AB40`) lists every animation event a
creature answers, read out of its pushes: `snd_Footstep`, `hit`,
`snd_hitground`, `SwingShort`, `SwingLong`, `SwingTwirl`, `Clash`, `Contact`,
`HitParry`, `blur_start`, `blur_end`, `doneattack01`, `doneattack02`.

**Fourth pad test, same day: "works perfectly".** With the longer patterns and
the hit hook, one session logged 7 saber hits (`LightsaberHit result N`), 6
blade contacts and a parry as clashes, 7 damage hits, 2 blaster bolts and a
frag grenade, and 575 frames of motor output while they played. The grenade's
line read `positional VFX 3003 … player=1.0m engineMeasuresFrom=player`. So
that time the engine measured from the player, not the sound listener, and the
grenade was well inside BioWare's own 5 m. The first combat test's missing
grenade was therefore more likely out of range than mis-measured. The 15 m
reach beyond 5 m is still unfelt. The random 500-2000 ms gap in the hum was
felt in this test too.

### KMRP's patterns

Keyframes are (magnitude, seconds), linear between them, as BioWare's are.
Heavy is the left motor, light the right.

| # | Name | Heavy | Light |
| --- | --- | --- | --- |
| 100 | `KMRP_SABER_IGNITE` | 0 → 0.18 @0.03, held → 0 @0.20 | 0 → 0.55 @0.05, held to 0.15 → 0.20 @0.25 → 0 @0.40 |
| 101 | `KMRP_SABER_RETRACT` | 0.12 held to 0.10 → 0 @0.20 | 0.35 held to 0.10 → 0.12 @0.20 → 0 @0.30 |
| 102 | `KMRP_SABER_HIT` | 0.40 held to 0.12 → 0.15 @0.25 → 0 @0.35 | 0.60 held to 0.12 → 0.25 @0.25 → 0 @0.35 |
| 103 | `KMRP_SABER_SPECIAL` | 0.55 held to 0.15 → 0.25 @0.30 → 0 @0.45 | 0.70 held to 0.15 → 0.30 @0.30 → 0 @0.45 |
| 104 | `KMRP_SABER_CLASH` | 0.15 held to 0.12 → 0 @0.30 | 0.70 held to 0.12 → 0.25 @0.25 → 0 @0.35 |
| 105 | `KMRP_BLASTER_DEFLECT` | 0.10 held to 0.12 → 0 @0.25 | 0.55 held to 0.12 → 0.20 @0.22 → 0 @0.30 |
| 106 | `KMRP_BLASTER_PISTOL_RECOIL` | 0.35 held to 0.10 → 0 @0.22 | 0.20 held to 0.08 → 0 @0.18 |
| 107 | `KMRP_BLASTER_RIFLE_RECOIL` | 0.50 held to 0.12 → 0.15 @0.22 → 0 @0.30 | 0.20 held to 0.10 → 0 @0.20 |
| 108 | `KMRP_REPEATER_RECOIL` | 0.35 held to 0.10 → 0 @0.18 | — |
| 109 | `KMRP_PLAYER_DAMAGE` (× intensity) | 1.0 held to 0.12 → 0.40 @0.25 → 0 @0.40 | 0.50 held to 0.10 → 0 @0.30 |
| 110 | `KMRP_PLAYER_DAMAGE_HEAVY` (× intensity) | 1.0 held to 0.18 → 0.50 @0.35 → 0 @0.55 | 0.60 held to 0.15 → 0 @0.35 |
| 111 | `KMRP_BLASTER_HIT_RECEIVED` | 0.50 held to 0.12 → 0.20 @0.25 → 0 @0.35 | 0.45 held to 0.10 → 0 @0.30 |
| 112 | `KMRP_PLAYER_DEATH` | 0.85 held to 0.15 → 0.30 @0.30 → 0 @0.60 | 0.35 held to 0.12 → 0 @0.30 |
| 113 | `KMRP_FORCE_LIGHTNING` | 0.10 held to 0.20 → 0 @0.45 | 0.50 to 0.10, 0.15 @0.15, 0.45 @0.25–0.35, 0 @0.45 |
| 114 | `KMRP_ELECTRIC_LOOP` (loops, 4 Hz) | 0.06 | 0.45 held to 0.12 → 0.10 @0.15, held to 0.25 |
| 115 | `KMRP_FORCE_LIGHTNING_CAST` | — | 0.30 held to 0.12 → 0.10 @0.20 → 0 @0.35 |
| 116 | `KMRP_FORCE_DRAIN_LOOP` (loops) | 0.12 → 0.30 @0.6 → 0.12 @1.2 | 0.05 → 0.15 @0.6 → 0.05 @1.2 |
| 117 | `KMRP_FORCE_CONFIRM` | 0.15 held to 0.10 → 0 @0.25 | 0.40 held to 0.12 → 0 @0.30 |
| 118 | `KMRP_STUN` | 0.30 held to 0.12 → 0 @0.25 | 0.35 to 0.10, 0.10 @0.15, 0.30 @0.25–0.35, 0 @0.45 |
| 119 | `KMRP_SONIC` | 0.40 → 0.10 @0.10 → 0.35 @0.20 → 0 @0.35 | 0.10 → 0.40 @0.10 → 0.10 @0.20 → 0 @0.35 |
| 120 | `KMRP_SOFT_GRENADE` | 0.35 → 0.10 @0.15 → 0 @0.40 | 0.20 → 0 @0.20 |
| 121 | `KMRP_DROID_EXPLOSION` | 0.45 → 0.10 @0.20 → 0 @0.40 | 0.30 → 0 @0.15 |
| 122 | `KMRP_DEBRIS` | 0.50 → 0.25 @0.20 → 0.35 @0.40 → 0 @0.80 | 0.15 → 0 @0.30 |
| 123 | `KMRP_SHIP_IMPACT` | 0.80 → 0.40 @0.25 → 0 @1.00 | 0.30 → 0 @0.30 |
| 124 | `KMRP_MELEE_HIT` | 0.50 held to 0.12 → 0.20 @0.25 → 0 @0.35 | 0.25 held to 0.12 → 0 @0.30 |

## The debug log

With `Debug=1`, `kmrp-rumble.log` in the game folder gets one line per event,
never one per frame, up to 4000 lines a session:

```
event="VFX 3004 at 3.1m" source=Original pattern=BioWare 14 FragGenade distanceScale=0.70 strength=1.00 heavy=0.70 light=0.42 duration=1.00s
event="LightsaberHum" source=Restored pattern=BioWare 0 LightSaberOn distanceScale=1.00 strength=1.00 heavy=0.00 light=0.20 duration=1.00s (loop)
event="PlayerDamaged 14 of 90" source=Enhanced pattern=KMRP_PLAYER_DAMAGE distanceScale=1.00 strength=1.00 heavy=0.48 light=0.19 duration=0.22s
stop pattern=BioWare 0 LightSaberOn reason=LightsaberHumEnded
```

`heavy` and `light` are the pattern's peaks after distance and strength. The
lines above show the format, not a recorded run. Since the first combat test
there are two more kinds of line, each bounded:

```
positional VFX 3004 pattern=BioWare 14 cutoff=5.0m reach=15.0m player=8.2m engineMeasuresFrom=soundListener
out heavy=0.720 light=0.000 dt=0.016
```

The first comes from every footstep or VFX lookup with a BioWare pattern, in
range or not, up to 300 a session. The second gives, frame by frame, what the
motors are sent while any one-shot pattern plays, up to 1500 lines a session.

## Deliberately not done yet

| Item | Why not yet |
| --- | --- |
| Critical hits landed or received (BioWare 20 `Critical_hit`, or a variant) | No stable hook found: the combat round's attack data has not been read. The saber-special VFX rules cover the feats. BioWare's `Critical_hit` is kept for Force Choke, Push and Wave, as shipped. |
| Krayt dragon death, BioWare 19 `Krayt_dying` | Attaching it reliably needs the Krayt's death event or VFX identified, which has not been done. |
| Doors, machinery, environmental destruction | Needs per-module work to find large doors without firing on every small one. |
| Swoop racing and the turret minigame | `CSWMiniGame::AddBullet` (`0x00672FA0`), `CSWMiniGameObject::OnHitBullet` (`0x0066C190`) and `BumpPlane` (`0x00670BB0`) are the candidates, not yet hooked. The minigames run under input class 1, which is not silenced. |
| Damage-type identity (fire, cold, sonic, ion feel different) | Needs the damage event rather than the HP delta. |
| `Droid_Heavy` footsteps | HK-47 walks on them, and as a companion he would buzz the pad constantly. |
| An installer or in-game control for Mode and Strength | The hardware test should settle the defaults first. |

## What was rejected

- **A consumed-exit hook at the positional lookup** (so that Enhanced could
  replace the engine's cutoff test). Every candidate site's stolen bytes write
  EAX, the first being `movzx eax, byte ptr [ebp+0xC]` at `0x005FB98E`, and
  KPM tests EAX *after* running the stolen bytes, so the handler's answer
  would be lost. (`tools/check_hook_stolen_bytes.py` refuses that shape.) The
  hook there observes. The fade is applied at the play hook, which the engine
  calls synchronously a few instructions later.
- **"On the player" as "within half a metre"**. A companion hugging the
  player, or an enemy in melee, would have counted. Pointer identity through
  `StartVisualEffect`'s position argument has no such case.
- **The saber at `PowerItem`'s entry**, for the forced-off and early-return
  reasons above.
- **`esp+0x18` for the frame time.** KPM parses a stack offset with
  `std::stoi` (`wrapper_x86.cpp`), which reads `0x18` as 0. So the parameter
  is written in decimal, `esp+24`. Both the patcher and the TOML say why.
- **Polling the creature's powered-hand bits** (`[[creature+0x68]+0xDC]`,
  written at `0x00646C7E`) instead of hooking. They read as a hand mask, but
  whether they accumulate or replace depends on `[item+0x19C]` in a way not
  worth guessing at. The hook sees the decided state directly.

## Hardware-test checklist

With `Mode=Enhanced`, `Strength=100`, `Debug=1`. After each item, the log
should show the matching line.

| # | Where | Do | Expect | Log line |
| --- | --- | --- | --- | --- |
| 1 | Endar Spire | play from the start; its scripts `k_pend_rumble01`, `k_pend_area02` and `k_pend_1b_area2` fire the tremors | BioWare 15, 16 and 5 at full strength | `event="Script" source=Original pattern=BioWare 15 Endar_01` |
| 2 | Any fight | throw a frag grenade near, then far | a strong thump near, weaker further off, nothing past 15 m | `positional VFX 300x …`, then `VFX 300x at N m … distanceScale` |
| 3 | Any fight | Force Push an enemy near and one further away; be pushed | BioWare 20 `Critical_hit`, full strength within 2 m, fading to nothing at 6 m | `VFX 1014 … BioWare 20` |
| 4 | Anywhere with a saber | draw, start combat, end combat | ignition pulse, then a faint light-motor hum while lit; a short fall and silence on retract | `LightsaberIgnite`, `LightsaberHum`, `LightsaberRetract`, `stop … LightsaberHumEnded` |
| 5 | Melee fight, saber or not | swing, hit, get parried | nothing on a miss, a solid pulse on a hit, a buzzing click on a parry | `LightsaberHit result N` or `MeleeHit result N`, `PlayerParried` / `TargetParried` |
| 6 | Blaster | fire a pistol, a rifle, a repeater | light kick, stronger kick, repeating low pulses | `muzzle flash at X m … -> recoil` |
| 7 | Any fight | take a small hit and a big one | small is faint, big is heavy, a flurry of hits is one pulse | `PlayerDamaged a of b` |
| 8 | a large creature -- which appearances use the two Stomp footstep rows has not been checked | stand near and far from it walking | footfalls fade with distance; humanoids never rumble | `Footstep 5` or `Footstep 10 at N m … BioWare 17 Heavy_step` |
| 9 | Anywhere | open the pause menu mid-hum, then close it | silence in the menu, the hum back after | — |
| 10 | Anywhere | die | one heavy impact, then nothing through the death screen | `PlayerDeath`, `stop all … died` |

Also worth reporting: the `SaberHum` level that feels right; whether
recoil fires for companions' shots (the 1.6 m guess); and anything that keeps
buzzing when it should not.
