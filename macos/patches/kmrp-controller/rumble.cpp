// KMRP for macOS, controller support: rumble. One mixer for BioWare's own patterns, the BioWare
// patterns whose triggers were cut, and KMRP's Enhanced haptics.
//
// The Mac port of src/controller-native/K1Rumble.cpp; its design, the patterns and every rule
// are written there and in docs/controller-rumble.md, and are the same here. BioWare's table and
// KMRP's patterns below are copied from it unchanged. Every rumble is a layer; each frame the
// mixer takes the maximum per motor across the live layers, scales it by the player's strength
// and sends it to the pad through SDL.
//
// What differs on the Mac, all read from its code (KOTOR_Exe 1.4.0):
//   - Aspyr kept the rumble subsystem but stubbed its output: CExoInput::SetRumble, PauseRumble
//     and UnpauseRumble (0x10035738C, 0x10035739C, 0x1003573A2) do nothing. So the per-frame
//     hook replaces MainLoop's call to UpdateRumble (0x1002687F1) outright, rather than reading
//     the magnitudes on their way to SetRumble, and the rumble pause, which the engine no longer
//     keeps, is kept here from its two callers' wrappers (0x100359D86, 0x100359D94).
//   - PlayRumblePattern is taken after its prologue and returns 1, where Windows returns the
//     shipped PC game's 0: the consumed exit lands on the Mac function's own epilogue, which
//     returns what the handler left in eax. Only a script reads it.
//   - objects carry 64-bit ids at +0x08 and their position at +0x38; an item's own id is at
//     +0x20, its owner's at +0x1B8 and its base item at +0x10; the VFX list is at +0x88 and a
//     visual effect's id at +0x104; the server creature's hit points are vtable +0x140 (current)
//     and +0x138 (maximum); an attack record has the attacker at +0x08, the result at +0x14, the
//     target at +0x20 and the skip flag at +0x30.
//   - the settings file is kmrp-controller.ini in the game's settings folder, beside
//     swkotor.ini (~/Library/Application Support/Knights of the Old Republic); the debug log is
//     ~/Library/Logs/KMRP/rumble.log.
#include "rumble.h"

#include "engine.h"
#include "pad.h"
#include "state.h"

#include <mach/mach.h>
#include <mach/mach_vm.h>
#include <sys/stat.h>

#include <cmath>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <strings.h>

namespace kmrp {
namespace rumble {
namespace {

using engine::At;

// One pattern, in the engine's own envelope format (K1Rumble.h): per motor, `count` keyframes
// of (magnitude, time in seconds). "Heavy" is envelope A, the left, low-frequency motor; "light"
// is envelope B.
struct RumbleRowK1 {
    int index;   // BioWare 0-21; KMRP patterns are 100 and up
    const char* label;
    int loop;
    const float* heavyMagnitudes;
    const float* heavyTimes;
    int heavyCount;
    const float* lightMagnitudes;
    const float* lightTimes;
    int lightCount;
};
constexpr int K1_RUMBLE_PATTERN_COUNT = 22;

// ------------------------------------------------------------ BioWare's table

// Generated from the wiki's table; do not edit by hand.
const float K1_RUMBLE_00_BM[] = { 0.20f, 0.20f };
const float K1_RUMBLE_00_BT[] = { 0.00f, 1.00f };
const float K1_RUMBLE_01_AM[] = { 1.00f, 1.00f };
const float K1_RUMBLE_01_AT[] = { 0.00f, 5.00f };
const float K1_RUMBLE_01_BM[] = { 1.00f, 1.00f };
const float K1_RUMBLE_01_BT[] = { 0.00f, 5.00f };
const float K1_RUMBLE_02_AM[] = { 1.00f, 1.00f };
const float K1_RUMBLE_02_AT[] = { 0.00f, 5.00f };
const float K1_RUMBLE_03_BM[] = { 1.00f, 0.00f };
const float K1_RUMBLE_03_BT[] = { 0.00f, 5.00f };
const float K1_RUMBLE_04_AM[] = { 0.20f, 0.20f };
const float K1_RUMBLE_04_AT[] = { 0.00f, 5.00f };
const float K1_RUMBLE_04_BM[] = { 0.20f, 0.20f };
const float K1_RUMBLE_04_BT[] = { 0.00f, 5.00f };
const float K1_RUMBLE_05_AM[] = { 0.20f, 0.60f, 0.20f };
const float K1_RUMBLE_05_AT[] = { 0.00f, 0.50f, 2.00f };
const float K1_RUMBLE_05_BM[] = { 0.20f, 0.80f, 0.20f };
const float K1_RUMBLE_05_BT[] = { 0.00f, 1.00f, 2.00f };
const float K1_RUMBLE_06_AM[] = { 0.80f, 0.50f, 0.20f };
const float K1_RUMBLE_06_AT[] = { 0.00f, 0.25f, 1.00f };
const float K1_RUMBLE_06_BM[] = { 0.50f, 0.20f };
const float K1_RUMBLE_06_BT[] = { 0.50f, 1.00f };
const float K1_RUMBLE_07_BM[] = { 0.40f, 0.10f };
const float K1_RUMBLE_07_BT[] = { 0.00f, 0.50f };
const float K1_RUMBLE_08_AM[] = { 0.30f, 0.80f, 0.30f };
const float K1_RUMBLE_08_AT[] = { 0.00f, 1.00f, 2.00f };
const float K1_RUMBLE_08_BM[] = { 0.80f, 0.30f, 0.80f };
const float K1_RUMBLE_08_BT[] = { 0.00f, 1.00f, 2.00f };
const float K1_RUMBLE_09_AM[] = { 0.30f, 0.50f, 0.50f, 0.50f };
const float K1_RUMBLE_09_AT[] = { 0.00f, 1.00f, 2.00f, 3.00f };
const float K1_RUMBLE_09_BM[] = { 0.80f, 0.00f, 0.80f, 0.30f };
const float K1_RUMBLE_09_BT[] = { 0.00f, 1.00f, 2.00f, 3.00f };
const float K1_RUMBLE_10_AM[] = { 0.00f, 0.20f, 0.00f, 1.00f };
const float K1_RUMBLE_10_AT[] = { 0.00f, 1.00f, 2.00f, 3.00f };
const float K1_RUMBLE_10_BM[] = { 1.00f, 0.00f, 1.00f, 0.00f };
const float K1_RUMBLE_10_BT[] = { 0.00f, 1.00f, 2.00f, 3.00f };
const float K1_RUMBLE_11_AM[] = { 0.00f, 0.00f, 1.00f, 0.00f, 0.50f };
const float K1_RUMBLE_11_AT[] = { 0.00f, 0.80f, 1.20f, 2.00f, 2.20f };
const float K1_RUMBLE_11_BM[] = { 0.00f, 0.00f, 1.00f, 0.00f, 0.50f };
const float K1_RUMBLE_11_BT[] = { 0.00f, 1.00f, 1.40f, 2.00f, 2.40f };
const float K1_RUMBLE_12_AM[] = { 0.00f, 0.30f, 0.60f, 0.60f, 1.00f, 1.00f, 0.00f };
const float K1_RUMBLE_12_AT[] = { 0.00f, 0.80f, 1.00f, 1.50f, 1.80f, 3.50f, 4.00f };
const float K1_RUMBLE_12_BM[] = { 0.00f, 1.00f, 0.20f, 1.00f, 0.20f, 1.00f, 0.00f };
const float K1_RUMBLE_12_BT[] = { 0.00f, 1.80f, 2.30f, 2.80f, 3.40f, 3.80f, 4.00f };
const float K1_RUMBLE_13_AM[] = { 1.00f, 0.00f };
const float K1_RUMBLE_13_AT[] = { 0.00f, 1.00f };
const float K1_RUMBLE_13_BM[] = { 0.00f, 0.60f };
const float K1_RUMBLE_13_BT[] = { 0.00f, 1.00f };
const float K1_RUMBLE_14_AM[] = { 1.00f, 0.00f };
const float K1_RUMBLE_14_AT[] = { 0.00f, 1.00f };
const float K1_RUMBLE_14_BM[] = { 0.00f, 0.60f };
const float K1_RUMBLE_14_BT[] = { 0.00f, 1.00f };
const float K1_RUMBLE_15_AM[] = { 0.00f, 0.50f, 0.00f, 0.00f, 0.70f, 0.00f };
const float K1_RUMBLE_15_AT[] = { 5.50f, 7.00f, 7.50f, 10.00f, 11.50f, 12.00f };
const float K1_RUMBLE_15_BM[] = { 0.00f, 0.30f, 0.00f, 0.00f, 0.70f, 0.00f };
const float K1_RUMBLE_15_BT[] = { 1.50f, 2.50f, 3.00f, 10.00f, 11.50f, 12.00f };
const float K1_RUMBLE_16_AM[] = { 0.30f, 0.10f };
const float K1_RUMBLE_16_AT[] = { 0.00f, 1.00f };
const float K1_RUMBLE_16_BM[] = { 0.50f, 0.30f, 0.50f, 0.30f };
const float K1_RUMBLE_16_BT[] = { 0.00f, 0.50f, 1.00f, 1.50f };
const float K1_RUMBLE_17_AM[] = { 0.30f, 0.00f };
const float K1_RUMBLE_17_AT[] = { 0.00f, 0.50f };
const float K1_RUMBLE_17_BM[] = { 0.40f, 0.00f };
const float K1_RUMBLE_17_BT[] = { 0.00f, 0.60f };
const float K1_RUMBLE_18_AM[] = { 0.30f, 0.00f };
const float K1_RUMBLE_18_AT[] = { 0.00f, 0.50f };
const float K1_RUMBLE_18_BM[] = { 0.40f, 0.00f };
const float K1_RUMBLE_18_BT[] = { 0.00f, 0.60f };
const float K1_RUMBLE_19_AM[] = { 0.00f, 0.80f, 0.30f, 0.80f };
const float K1_RUMBLE_19_AT[] = { 2.50f, 3.00f, 3.50f, 4.00f };
const float K1_RUMBLE_19_BM[] = { 0.00f, 0.60f, 0.20f };
const float K1_RUMBLE_19_BT[] = { 2.50f, 2.80f, 4.00f };
const float K1_RUMBLE_20_AM[] = { 0.60f, 0.20f };
const float K1_RUMBLE_20_AT[] = { 0.00f, 0.50f };
const float K1_RUMBLE_21_AM[] = { 0.30f, 0.00f, 0.30f, 0.00f, 0.30f, 0.00f, 0.30f };
const float K1_RUMBLE_21_AT[] = { 0.00f, 0.75f, 1.50f, 2.25f, 3.00f, 3.75f, 4.50f };
const float K1_RUMBLE_21_BM[] = { 0.30f, 0.00f, 0.30f, 0.00f, 0.30f, 0.00f, 0.30f };
const float K1_RUMBLE_21_BT[] = { 0.75f, 1.50f, 2.25f, 3.00f, 3.75f, 4.50f, 5.25f };

const RumbleRowK1 K1_RUMBLE_2DA[] = {
    {  0, "LightSaberOn", 1, nullptr, nullptr, 0, K1_RUMBLE_00_BM, K1_RUMBLE_00_BT, 2 },
    {  1, "FullBoth-5secs", 0, K1_RUMBLE_01_AM, K1_RUMBLE_01_AT, 2, K1_RUMBLE_01_BM, K1_RUMBLE_01_BT, 2 },
    {  2, "FullLeft-5secs", 0, K1_RUMBLE_02_AM, K1_RUMBLE_02_AT, 2, nullptr, nullptr, 0 },
    {  3, "FullRight-5secs", 0, nullptr, nullptr, 0, K1_RUMBLE_03_BM, K1_RUMBLE_03_BT, 2 },
    {  4, "WeakBoth-5secs", 0, K1_RUMBLE_04_AM, K1_RUMBLE_04_AT, 2, K1_RUMBLE_04_BM, K1_RUMBLE_04_BT, 2 },
    {  5, "Sample1", 0, K1_RUMBLE_05_AM, K1_RUMBLE_05_AT, 3, K1_RUMBLE_05_BM, K1_RUMBLE_05_BT, 3 },
    {  6, "Sample2", 0, K1_RUMBLE_06_AM, K1_RUMBLE_06_AT, 3, K1_RUMBLE_06_BM, K1_RUMBLE_06_BT, 2 },
    {  7, "Sample3", 0, nullptr, nullptr, 0, K1_RUMBLE_07_BM, K1_RUMBLE_07_BT, 2 },
    {  8, "Sample4", 0, K1_RUMBLE_08_AM, K1_RUMBLE_08_AT, 3, K1_RUMBLE_08_BM, K1_RUMBLE_08_BT, 3 },
    {  9, "Sample5", 0, K1_RUMBLE_09_AM, K1_RUMBLE_09_AT, 4, K1_RUMBLE_09_BM, K1_RUMBLE_09_BT, 4 },
    { 10, "Sample6", 0, K1_RUMBLE_10_AM, K1_RUMBLE_10_AT, 4, K1_RUMBLE_10_BM, K1_RUMBLE_10_BT, 4 },
    { 11, "Rancor", 0, K1_RUMBLE_11_AM, K1_RUMBLE_11_AT, 5, K1_RUMBLE_11_BM, K1_RUMBLE_11_BT, 5 },
    { 12, "Ceiling", 0, K1_RUMBLE_12_AM, K1_RUMBLE_12_AT, 7, K1_RUMBLE_12_BM, K1_RUMBLE_12_BT, 7 },
    { 13, "Obilesk", 0, K1_RUMBLE_13_AM, K1_RUMBLE_13_AT, 2, K1_RUMBLE_13_BM, K1_RUMBLE_13_BT, 2 },
    { 14, "FragGenade", 0, K1_RUMBLE_14_AM, K1_RUMBLE_14_AT, 2, K1_RUMBLE_14_BM, K1_RUMBLE_14_BT, 2 },
    { 15, "Endar_01", 0, K1_RUMBLE_15_AM, K1_RUMBLE_15_AT, 6, K1_RUMBLE_15_BM, K1_RUMBLE_15_BT, 6 },
    { 16, "Endar_02", 0, K1_RUMBLE_16_AM, K1_RUMBLE_16_AT, 2, K1_RUMBLE_16_BM, K1_RUMBLE_16_BT, 4 },
    { 17, "Heavy_step", 0, K1_RUMBLE_17_AM, K1_RUMBLE_17_AT, 2, K1_RUMBLE_17_BM, K1_RUMBLE_17_BT, 2 },
    { 18, "Light_step", 0, K1_RUMBLE_18_AM, K1_RUMBLE_18_AT, 2, K1_RUMBLE_18_BM, K1_RUMBLE_18_BT, 2 },
    { 19, "Krayt_dying", 0, K1_RUMBLE_19_AM, K1_RUMBLE_19_AT, 4, K1_RUMBLE_19_BM, K1_RUMBLE_19_BT, 3 },
    { 20, "Critical_hit", 0, K1_RUMBLE_20_AM, K1_RUMBLE_20_AT, 2, nullptr, nullptr, 0 },
    { 21, "Whirlwind", 1, K1_RUMBLE_21_AM, K1_RUMBLE_21_AT, 7, K1_RUMBLE_21_BM, K1_RUMBLE_21_BT, 7 },
};
static_assert(sizeof(K1_RUMBLE_2DA) / sizeof(K1_RUMBLE_2DA[0]) == K1_RUMBLE_PATTERN_COUNT,
              "one row per pattern");

// ------------------------------------------------------------ KMRP's patterns
//
// Envelopes in BioWare's format. Most live in the lower half of the motor range:
// strength is kept for explosions, huge creatures and collapses, because if
// everything is strong nothing is. Heavy (left) carries mass, impacts and
// recoil; light (right) carries energy, electricity and saber buzz.

#define KMRP_ENV(name, ...) const float name[] = { __VA_ARGS__ }
#define KMRP_N(a) static_cast<int>(sizeof(a) / sizeof((a)[0]))

// Every one-shot pattern HOLDS its peak for 100-180 ms before it fades, and
// runs 0.3 s or more in all. The first versions (2026-09-25) fell away from the
// first frame and lasted 0.1-0.2 s: the module's own send counter shows they
// reached the pad at the intended strength, yet in a fight nothing was felt,
// and the user found a 100 ms vibration "only barely activates" the motor.
// An Xbox pad's motors are spinning weights that need time to get going;
// BioWare's own patterns are all half a second or longer for that reason.

// Lightsaber ignition: the light motor rises fast over a small heavy kick, holds,
// then falls away under the hum, whatever level SaberHum sets it to. (It once
// settled at LightSaberOn's full 0.2; the first pad test found that far too
// strong.) Retraction: a shorter, softer version.
KMRP_ENV(IGNITE_HM, 0.00f, 0.18f, 0.18f, 0.00f);  KMRP_ENV(IGNITE_HT, 0.00f, 0.03f, 0.12f, 0.20f);
KMRP_ENV(IGNITE_LM, 0.00f, 0.55f, 0.55f, 0.20f, 0.00f);
KMRP_ENV(IGNITE_LT, 0.00f, 0.05f, 0.15f, 0.25f, 0.40f);
KMRP_ENV(RETRACT_HM, 0.12f, 0.12f, 0.00f);        KMRP_ENV(RETRACT_HT, 0.00f, 0.10f, 0.20f);
KMRP_ENV(RETRACT_LM, 0.35f, 0.35f, 0.12f, 0.00f); KMRP_ENV(RETRACT_LT, 0.00f, 0.10f, 0.20f, 0.30f);
// A saber landing: energy over a solid impact.
KMRP_ENV(SABER_HIT_HM, 0.40f, 0.40f, 0.15f, 0.00f); KMRP_ENV(SABER_HIT_HT, 0.00f, 0.12f, 0.25f, 0.35f);
KMRP_ENV(SABER_HIT_LM, 0.60f, 0.60f, 0.25f, 0.00f); KMRP_ENV(SABER_HIT_LT, 0.00f, 0.12f, 0.25f, 0.35f);
// Any other melee weapon landing: more thud, less buzz.
KMRP_ENV(MELEE_HIT_HM, 0.50f, 0.50f, 0.20f, 0.00f); KMRP_ENV(MELEE_HIT_HT, 0.00f, 0.12f, 0.25f, 0.35f);
KMRP_ENV(MELEE_HIT_LM, 0.25f, 0.25f, 0.00f);        KMRP_ENV(MELEE_HIT_LT, 0.00f, 0.12f, 0.30f);
// A saber special (Critical Strike, Power Attack, Flurry): the hit, harder and longer.
KMRP_ENV(SABER_SPEC_HM, 0.55f, 0.55f, 0.25f, 0.00f); KMRP_ENV(SABER_SPEC_HT, 0.00f, 0.15f, 0.30f, 0.45f);
KMRP_ENV(SABER_SPEC_LM, 0.70f, 0.70f, 0.30f, 0.00f); KMRP_ENV(SABER_SPEC_LT, 0.00f, 0.15f, 0.30f, 0.45f);
// Blade on blade: light-motor dominant.
KMRP_ENV(CLASH_HM, 0.15f, 0.15f, 0.00f);          KMRP_ENV(CLASH_HT, 0.00f, 0.12f, 0.30f);
KMRP_ENV(CLASH_LM, 0.70f, 0.70f, 0.25f, 0.00f);   KMRP_ENV(CLASH_LT, 0.00f, 0.12f, 0.25f, 0.35f);
// A blaster bolt turned by a blade.
KMRP_ENV(DEFLECT_HM, 0.10f, 0.10f, 0.00f);        KMRP_ENV(DEFLECT_HT, 0.00f, 0.12f, 0.25f);
KMRP_ENV(DEFLECT_LM, 0.55f, 0.55f, 0.20f, 0.00f); KMRP_ENV(DEFLECT_LT, 0.00f, 0.12f, 0.22f, 0.30f);
// Recoil, restrained -- this is not a shooter. Shorter than the rest so rapid
// fire stays separate shots.
KMRP_ENV(PISTOL_HM, 0.35f, 0.35f, 0.00f);         KMRP_ENV(PISTOL_HT, 0.00f, 0.10f, 0.22f);
KMRP_ENV(PISTOL_LM, 0.20f, 0.20f, 0.00f);         KMRP_ENV(PISTOL_LT, 0.00f, 0.08f, 0.18f);
KMRP_ENV(RIFLE_HM, 0.50f, 0.50f, 0.15f, 0.00f);   KMRP_ENV(RIFLE_HT, 0.00f, 0.12f, 0.22f, 0.30f);
KMRP_ENV(RIFLE_LM, 0.20f, 0.20f, 0.00f);          KMRP_ENV(RIFLE_LT, 0.00f, 0.10f, 0.20f);
KMRP_ENV(REPEATER_HM, 0.35f, 0.35f, 0.00f);       KMRP_ENV(REPEATER_HT, 0.00f, 0.10f, 0.18f);
// Damage received: scaled by how much of the character's health the hit took
// (DamageIntensity), with a longer envelope for a fifth of the bar or more.
KMRP_ENV(DAMAGE_HM, 1.00f, 1.00f, 0.40f, 0.00f);  KMRP_ENV(DAMAGE_HT, 0.00f, 0.12f, 0.25f, 0.40f);
KMRP_ENV(DAMAGE_LM, 0.50f, 0.50f, 0.00f);         KMRP_ENV(DAMAGE_LT, 0.00f, 0.10f, 0.30f);
KMRP_ENV(HEAVY_DAMAGE_HM, 1.00f, 1.00f, 0.50f, 0.00f); KMRP_ENV(HEAVY_DAMAGE_HT, 0.00f, 0.18f, 0.35f, 0.55f);
KMRP_ENV(HEAVY_DAMAGE_LM, 0.60f, 0.60f, 0.00f);   KMRP_ENV(HEAVY_DAMAGE_LT, 0.00f, 0.15f, 0.35f);
// A blaster bolt striking the controlled character: impulse plus energy buzz.
KMRP_ENV(BOLT_HIT_HM, 0.50f, 0.50f, 0.20f, 0.00f); KMRP_ENV(BOLT_HIT_HT, 0.00f, 0.12f, 0.25f, 0.35f);
KMRP_ENV(BOLT_HIT_LM, 0.45f, 0.45f, 0.00f);       KMRP_ENV(BOLT_HIT_LT, 0.00f, 0.10f, 0.30f);
// The controlled character dying.
KMRP_ENV(DEATH_HM, 0.85f, 0.85f, 0.30f, 0.00f);   KMRP_ENV(DEATH_HT, 0.00f, 0.15f, 0.30f, 0.60f);
KMRP_ENV(DEATH_LM, 0.35f, 0.35f, 0.00f);          KMRP_ENV(DEATH_LT, 0.00f, 0.12f, 0.30f);
// Electricity: light-motor chatter at 4 Hz -- the fastest a spinning weight
// can follow; the first version's 20 Hz would have blurred into a steady buzz.
// The burst is the strike; the loop runs while lightning or a shock is on the
// character.
KMRP_ENV(ZAP_HM, 0.10f, 0.10f, 0.00f);            KMRP_ENV(ZAP_HT, 0.00f, 0.20f, 0.45f);
KMRP_ENV(ZAP_LM, 0.50f, 0.50f, 0.15f, 0.45f, 0.45f, 0.00f);
KMRP_ENV(ZAP_LT, 0.00f, 0.10f, 0.15f, 0.25f, 0.35f, 0.45f);
KMRP_ENV(ZAP_LOOP_HM, 0.06f, 0.06f);              KMRP_ENV(ZAP_LOOP_HT, 0.00f, 0.25f);
KMRP_ENV(ZAP_LOOP_LM, 0.45f, 0.45f, 0.10f, 0.10f); KMRP_ENV(ZAP_LOOP_LT, 0.00f, 0.12f, 0.15f, 0.25f);
KMRP_ENV(ZAP_CAST_LM, 0.30f, 0.30f, 0.10f, 0.00f); KMRP_ENV(ZAP_CAST_LT, 0.00f, 0.12f, 0.20f, 0.35f);
// Drain: a slow pull, not a shock. Loops while the drain is on the character.
KMRP_ENV(DRAIN_HM, 0.12f, 0.30f, 0.12f);          KMRP_ENV(DRAIN_HT, 0.00f, 0.60f, 1.20f);
KMRP_ENV(DRAIN_LM, 0.05f, 0.15f, 0.05f);          KMRP_ENV(DRAIN_LT, 0.00f, 0.60f, 1.20f);
// A Force buff taking hold, or a power leaving the hands: a short confirmation.
KMRP_ENV(BUFF_HM, 0.15f, 0.15f, 0.00f);           KMRP_ENV(BUFF_HT, 0.00f, 0.10f, 0.25f);
KMRP_ENV(BUFF_LM, 0.40f, 0.40f, 0.00f);           KMRP_ENV(BUFF_LT, 0.00f, 0.12f, 0.30f);
// Stunned.
KMRP_ENV(STUN_HM, 0.30f, 0.30f, 0.00f);           KMRP_ENV(STUN_HT, 0.00f, 0.12f, 0.25f);
KMRP_ENV(STUN_LM, 0.35f, 0.35f, 0.10f, 0.30f, 0.30f, 0.00f);
KMRP_ENV(STUN_LT, 0.00f, 0.10f, 0.15f, 0.25f, 0.35f, 0.45f);
// World events, scaled by distance.
KMRP_ENV(SONIC_HM, 0.40f, 0.10f, 0.35f, 0.00f);   KMRP_ENV(SONIC_HT, 0.00f, 0.10f, 0.20f, 0.35f);
KMRP_ENV(SONIC_LM, 0.10f, 0.40f, 0.10f, 0.00f);   KMRP_ENV(SONIC_LT, 0.00f, 0.10f, 0.20f, 0.35f);
KMRP_ENV(SOFT_BLAST_HM, 0.35f, 0.10f, 0.00f);     KMRP_ENV(SOFT_BLAST_HT, 0.00f, 0.15f, 0.40f);
KMRP_ENV(SOFT_BLAST_LM, 0.20f, 0.00f);            KMRP_ENV(SOFT_BLAST_LT, 0.00f, 0.20f);
KMRP_ENV(DROID_BLAST_HM, 0.45f, 0.10f, 0.00f);    KMRP_ENV(DROID_BLAST_HT, 0.00f, 0.20f, 0.40f);
KMRP_ENV(DROID_BLAST_LM, 0.30f, 0.00f);           KMRP_ENV(DROID_BLAST_LT, 0.00f, 0.15f);
KMRP_ENV(DEBRIS_HM, 0.50f, 0.25f, 0.35f, 0.00f);  KMRP_ENV(DEBRIS_HT, 0.00f, 0.20f, 0.40f, 0.80f);
KMRP_ENV(DEBRIS_LM, 0.15f, 0.00f);                KMRP_ENV(DEBRIS_LT, 0.00f, 0.30f);
KMRP_ENV(SHIP_HIT_HM, 0.80f, 0.40f, 0.00f);       KMRP_ENV(SHIP_HIT_HT, 0.00f, 0.25f, 1.00f);
KMRP_ENV(SHIP_HIT_LM, 0.30f, 0.00f);              KMRP_ENV(SHIP_HIT_LT, 0.00f, 0.30f);

#define KMRP_ROW(i, label, loop, h, l) \
    { i, label, loop, h##_HM, h##_HT, KMRP_N(h##_HM), l##_LM, l##_LT, KMRP_N(l##_LM) }
#define KMRP_ROW_HEAVY(i, label, h) { i, label, 0, h##_HM, h##_HT, KMRP_N(h##_HM), nullptr, nullptr, 0 }
#define KMRP_ROW_LIGHT(i, label, l) { i, label, 0, nullptr, nullptr, 0, l##_LM, l##_LT, KMRP_N(l##_LM) }

enum : int {
    P_SABER_IGNITE = 100, P_SABER_RETRACT, P_SABER_HIT, P_SABER_SPECIAL, P_SABER_CLASH,
    P_BLASTER_DEFLECT, P_PISTOL, P_RIFLE, P_REPEATER, P_DAMAGE, P_DAMAGE_HEAVY,
    P_BOLT_HIT, P_DEATH, P_LIGHTNING, P_ELECTRIC_LOOP, P_LIGHTNING_CAST, P_DRAIN_LOOP,
    P_BUFF, P_STUN, P_SONIC, P_SOFT_GRENADE, P_DROID_EXPLOSION, P_DEBRIS, P_SHIP_IMPACT,
    P_MELEE_HIT,
};

const RumbleRowK1 K1_RUMBLE_KMRP[] = {
    KMRP_ROW(P_SABER_IGNITE,    "KMRP_SABER_IGNITE",          0, IGNITE, IGNITE),
    KMRP_ROW(P_SABER_RETRACT,   "KMRP_SABER_RETRACT",         0, RETRACT, RETRACT),
    KMRP_ROW(P_SABER_HIT,       "KMRP_SABER_HIT",             0, SABER_HIT, SABER_HIT),
    KMRP_ROW(P_SABER_SPECIAL,   "KMRP_SABER_SPECIAL",         0, SABER_SPEC, SABER_SPEC),
    KMRP_ROW(P_SABER_CLASH,     "KMRP_SABER_CLASH",           0, CLASH, CLASH),
    KMRP_ROW(P_BLASTER_DEFLECT, "KMRP_BLASTER_DEFLECT",       0, DEFLECT, DEFLECT),
    KMRP_ROW(P_PISTOL,          "KMRP_BLASTER_PISTOL_RECOIL", 0, PISTOL, PISTOL),
    KMRP_ROW(P_RIFLE,           "KMRP_BLASTER_RIFLE_RECOIL",  0, RIFLE, RIFLE),
    KMRP_ROW_HEAVY(P_REPEATER,  "KMRP_REPEATER_RECOIL",       REPEATER),
    KMRP_ROW(P_DAMAGE,          "KMRP_PLAYER_DAMAGE",         0, DAMAGE, DAMAGE),
    KMRP_ROW(P_DAMAGE_HEAVY,    "KMRP_PLAYER_DAMAGE_HEAVY",   0, HEAVY_DAMAGE, HEAVY_DAMAGE),
    KMRP_ROW(P_BOLT_HIT,        "KMRP_BLASTER_HIT_RECEIVED",  0, BOLT_HIT, BOLT_HIT),
    KMRP_ROW(P_DEATH,           "KMRP_PLAYER_DEATH",          0, DEATH, DEATH),
    KMRP_ROW(P_LIGHTNING,       "KMRP_FORCE_LIGHTNING",       0, ZAP, ZAP),
    KMRP_ROW(P_ELECTRIC_LOOP,   "KMRP_ELECTRIC_LOOP",         1, ZAP_LOOP, ZAP_LOOP),
    KMRP_ROW_LIGHT(P_LIGHTNING_CAST, "KMRP_FORCE_LIGHTNING_CAST", ZAP_CAST),
    KMRP_ROW(P_DRAIN_LOOP,      "KMRP_FORCE_DRAIN_LOOP",      1, DRAIN, DRAIN),
    KMRP_ROW(P_BUFF,            "KMRP_FORCE_CONFIRM",         0, BUFF, BUFF),
    KMRP_ROW(P_STUN,            "KMRP_STUN",                  0, STUN, STUN),
    KMRP_ROW(P_SONIC,           "KMRP_SONIC",                 0, SONIC, SONIC),
    KMRP_ROW(P_SOFT_GRENADE,    "KMRP_SOFT_GRENADE",          0, SOFT_BLAST, SOFT_BLAST),
    KMRP_ROW(P_DROID_EXPLOSION, "KMRP_DROID_EXPLOSION",       0, DROID_BLAST, DROID_BLAST),
    KMRP_ROW(P_DEBRIS,          "KMRP_DEBRIS",                0, DEBRIS, DEBRIS),
    KMRP_ROW(P_SHIP_IMPACT,     "KMRP_SHIP_IMPACT",           0, SHIP_HIT, SHIP_HIT),
    KMRP_ROW(P_MELEE_HIT,       "KMRP_MELEE_HIT",             0, MELEE_HIT, MELEE_HIT),
};

const RumbleRowK1* Kmrp(int index)
{
    for (const RumbleRowK1& row : K1_RUMBLE_KMRP) {
        if (row.index == index) return &row;
    }
    return nullptr;
}

const RumbleRowK1* BioWare(int index)
{
    return index >= 0 && index < K1_RUMBLE_PATTERN_COUNT ? &K1_RUMBLE_2DA[index] : nullptr;
}

const RumbleRowK1* Pattern(int index)
{
    return index < K1_RUMBLE_PATTERN_COUNT ? BioWare(index) : Kmrp(index);
}

// ------------------------------------------------------------ settings

enum Mode : int { MODE_OFF = 0, MODE_ORIGINAL = 1, MODE_ENHANCED = 2 };
enum Provenance : int { ORIGINAL = 0, RESTORED = 1, ENHANCED = 2 };
const char* const PROVENANCE_NAME[] = {"Original", "Restored", "Enhanced"};
const char* const MODE_NAME[] = {"Off", "Original", "Enhanced"};

struct Settings {
    int mode = MODE_ENHANCED;
    float strength = 1.0f;
    float hum = 0.06f;
    float humPulse = 0.1f;       // seconds on, per period; 0 = steady
    float humPeriodMin = 0.5f;   // seconds from one pulse to the next,
    float humPeriodMax = 2.0f;   // drawn afresh for every pulse
    bool debug = false;
    long stamp = 0;
    std::uint64_t nextCheck = 0;
    bool loaded = false;
} g_settings;

void Log(const char* format, ...) __attribute__((format(printf, 1, 2)));

std::string SettingsPath() {
    const char* home = std::getenv("HOME");
    return home ? std::string(home) + "/Library/Application Support/Knights of the Old Republic/kmrp-controller.ini"
                : std::string();
}

// GetPrivateProfileString's part: the value of `key` in [section], or empty.
std::string IniValue(const std::string& text, const char* section, const char* key) {
    bool inSection = false;
    std::size_t at = 0;
    while (at <= text.size()) {
        std::size_t end = text.find('\n', at);
        if (end == std::string::npos) end = text.size();
        std::string line = text.substr(at, end - at);
        at = end + 1;
        while (!line.empty() && (line.back() == '\r' || line.back() == ' ' || line.back() == '\t')) line.pop_back();
        std::size_t first = line.find_first_not_of(" \t");
        if (first == std::string::npos || line[first] == ';' || line[first] == '#') continue;
        line = line.substr(first);
        if (line[0] == '[') {
            const std::size_t close = line.find(']');
            inSection = close != std::string::npos && strcasecmp(line.substr(1, close - 1).c_str(), section) == 0;
            continue;
        }
        if (!inSection) continue;
        const std::size_t eq = line.find('=');
        if (eq == std::string::npos) continue;
        std::string name = line.substr(0, eq);
        while (!name.empty() && (name.back() == ' ' || name.back() == '\t')) name.pop_back();
        if (strcasecmp(name.c_str(), key) != 0) continue;
        std::string value = line.substr(eq + 1);
        const std::size_t v = value.find_first_not_of(" \t");
        return v == std::string::npos ? std::string() : value.substr(v);
    }
    return std::string();
}

int IniInt(const std::string& text, const char* key, int fallback) {
    const std::string value = IniValue(text, "Rumble", key);
    return value.empty() ? fallback : std::atoi(value.c_str());
}

// kmrp-controller.ini, section [Rumble], with K1Rumble.cpp's keys, ranges and defaults:
//   Mode = Off | Original | Enhanced, Strength = 0-100, SaberHum = 0-100, SaberHumPulseMs = 0-1000,
//   SaberHumPeriodMinMs and SaberHumPeriodMaxMs = 50-5000, Debug = 0 | 1.
// Checked at most once a second and re-read when the file changes, so it can be tuned with the
// game running.
void LoadSettings() {
    const std::uint64_t now = NowMs();
    if (g_settings.loaded && now < g_settings.nextCheck) return;
    g_settings.nextCheck = now + 1000;
    const std::string path = SettingsPath();
    struct stat info {};
    const bool exists = !path.empty() && stat(path.c_str(), &info) == 0;
    if (g_settings.loaded) {
        if (!exists) return;   // keep what was read
        if (info.st_mtime == g_settings.stamp) return;
    }
    std::string text;
    if (exists) {
        g_settings.stamp = info.st_mtime;
        if (FILE* f = std::fopen(path.c_str(), "r")) {
            char buffer[4096];
            std::size_t n;
            while ((n = std::fread(buffer, 1, sizeof buffer, f)) > 0) text.append(buffer, n);
            std::fclose(f);
        }
    }
    const std::string mode = IniValue(text, "Rumble", "Mode");
    if (!strcasecmp(mode.c_str(), "Off")) g_settings.mode = MODE_OFF;
    else if (!strcasecmp(mode.c_str(), "Original")) g_settings.mode = MODE_ORIGINAL;
    else g_settings.mode = MODE_ENHANCED;
    int strength = IniInt(text, "Strength", 100);
    if (strength < 0) strength = 0;
    if (strength > 100) strength = 100;
    g_settings.strength = strength / 100.0f;
    int hum = IniInt(text, "SaberHum", 6);
    if (hum < 0) hum = 0;
    if (hum > 100) hum = 100;
    g_settings.hum = hum / 100.0f;
    int pulse = IniInt(text, "SaberHumPulseMs", 100);
    if (pulse < 0) pulse = 0;
    if (pulse > 1000) pulse = 1000;
    int periodMin = IniInt(text, "SaberHumPeriodMinMs", 500);
    int periodMax = IniInt(text, "SaberHumPeriodMaxMs", 2000);
    if (periodMin > periodMax) { const int swap = periodMin; periodMin = periodMax; periodMax = swap; }
    if (periodMin < 50) periodMin = 50;
    if (periodMin > 5000) periodMin = 5000;
    if (periodMax > 5000) periodMax = 5000;
    if (periodMax < periodMin) periodMax = periodMin;
    g_settings.humPulse = pulse / 1000.0f;
    g_settings.humPeriodMin = periodMin / 1000.0f;
    g_settings.humPeriodMax = periodMax / 1000.0f;
    g_settings.debug = IniInt(text, "Debug", 0) != 0;
    g_settings.loaded = true;
    kmrp::Log("rumble: mode %s, strength %d%%, saber hum %d%% (pulse %d ms every %d-%d ms), debug %d, from %s",
              MODE_NAME[g_settings.mode], strength, hum, pulse, periodMin, periodMax, g_settings.debug ? 1 : 0,
              exists ? "kmrp-controller.ini" : "defaults");
    Log("settings mode=%s strength=%d%% saberHum=%d%% pulse=%dms every %d-%dms debug=%d from=%s",
        MODE_NAME[g_settings.mode], strength, hum, pulse, periodMin, periodMax, g_settings.debug ? 1 : 0,
        exists ? "kmrp-controller.ini" : "defaults");
}

bool Enhanced() { return g_settings.mode == MODE_ENHANCED; }

// ~/Library/Logs/KMRP/rumble.log, when Debug = 1. One line per event, never one per frame, and
// at most 4000 lines a session.
void Log(const char* format, ...) {
    static int lines = 0;
    static FILE* file = nullptr;
    if (!g_settings.debug || lines >= 4000) return;
    if (!file) {
        const char* home = std::getenv("HOME");
        if (!home) return;
        file = std::fopen((std::string(home) + "/Library/Logs/KMRP/rumble.log").c_str(), "a");
        if (!file) return;
    }
    ++lines;
    va_list args;
    va_start(args, format);
    std::fprintf(file, "%llu [KMRP Rumble] ", static_cast<unsigned long long>(NowMs()));
    std::vfprintf(file, format, args);
    std::fputc('\n', file);
    std::fflush(file);
    va_end(args);
}

float Peak(const float* magnitudes, int count) {
    float peak = 0.0f;
    for (int i = 0; magnitudes && i < count; ++i) if (magnitudes[i] > peak) peak = magnitudes[i];
    return peak;
}

float Length(const RumbleRowK1& row) {
    const float a = row.heavyCount > 0 ? row.heavyTimes[row.heavyCount - 1] : 0.0f;
    const float b = row.lightCount > 0 ? row.lightTimes[row.lightCount - 1] : 0.0f;
    return a > b ? a : b;
}

void Name(const RumbleRowK1& row, char* out, std::size_t size) {
    if (row.index < K1_RUMBLE_PATTERN_COUNT) std::snprintf(out, size, "BioWare %d %s", row.index, row.label);
    else std::snprintf(out, size, "%s", row.label);
}

// ------------------------------------------------------------ the mixer

// A keyed layer is a state, not an event: at most one exists per key, and it is started and
// stopped by the code that owns the state.
enum Key : unsigned { KEY_NONE = 0, KEY_HUM, KEY_WHIRLWIND, KEY_ELECTRIC, KEY_DRAIN };

struct Layer {
    const RumbleRowK1* row;
    float start;   // on g_clock
    float scale;
    int provenance;
    unsigned key;
    bool active;
};
constexpr int K1_RUMBLE_LAYERS = 24;
Layer g_layers[K1_RUMBLE_LAYERS] = {};
float g_clock = 0.0f;   // seconds of unpaused, unfaded game time

// The engine's evaluator (CSWRumblePattern::GetMagnitude): linear between the keyframes that
// bracket t; 0 before the first keyframe and past the last; a looping pattern wraps by its last
// keyframe's time.
float Evaluate(const float* magnitudes, const float* times, int count, float t, bool loop, bool& done) {
    done = true;
    if (!magnitudes || !times || count <= 0) return 0.0f;
    const float last = times[count - 1];
    if (t > last) {
        if (!loop || last <= 0.0f) return 0.0f;
        t = std::fmod(t, last);
    }
    done = false;
    for (int i = 0; i + 1 < count; ++i) {
        if (t >= times[i] && t <= times[i + 1]) {
            const float span = times[i + 1] - times[i];
            if (span <= 0.0f) return magnitudes[i + 1];
            return magnitudes[i] + (magnitudes[i + 1] - magnitudes[i]) * (t - times[i]) / span;
        }
    }
    return 0.0f;
}

Layer* Find(unsigned key) {
    if (key == KEY_NONE) return nullptr;
    for (Layer& layer : g_layers) if (layer.active && layer.key == key) return &layer;
    return nullptr;
}

void Stop(unsigned key, const char* why) {
    if (Layer* const layer = Find(key)) {
        char name[64];
        Name(*layer->row, name, sizeof(name));
        Log("stop pattern=%s reason=%s", name, why);
        layer->active = false;
    }
}

void StopAll(const char* why) {
    int stopped = 0;
    for (Layer& layer : g_layers) if (layer.active) { layer.active = false; ++stopped; }
    if (stopped) Log("stop all=%d reason=%s", stopped, why);
}

struct Counters {
    unsigned long plays = 0, engineRows = 0, frames = 0, sent = 0;
} g_count;

// Start `row` as a layer. With `merge` > 0, a repeat of the same pattern that started within
// `merge` seconds joins the running layer (keeping the larger scale) instead of stacking.
void Play(const RumbleRowK1* row, float scale, int provenance, const char* event, float distanceScale,
          unsigned key = KEY_NONE, float merge = 0.0f) {
    if (!row || scale <= 0.0f || g_settings.mode == MODE_OFF) return;
    if (provenance != ORIGINAL && !Enhanced()) return;
    if (Layer* const same = Find(key)) same->active = false;
    if (merge > 0.0f) {
        for (Layer& layer : g_layers) {
            if (layer.active && layer.row == row && g_clock - layer.start < merge) {
                if (scale > layer.scale) layer.scale = scale;
                return;
            }
        }
    }
    Layer* slot = nullptr;
    for (Layer& layer : g_layers) if (!layer.active) { slot = &layer; break; }
    if (!slot) {   // full: replace the oldest unkeyed layer
        for (Layer& layer : g_layers)
            if (layer.key == KEY_NONE && (!slot || layer.start < slot->start)) slot = &layer;
        if (!slot) return;
    }
    *slot = {row, g_clock, scale, provenance, key, true};
    ++g_count.plays;
    char name[64];
    Name(*row, name, sizeof(name));
    const float s = scale * g_settings.strength;
    Log("event=\"%s\" source=%s pattern=%s distanceScale=%.2f strength=%.2f heavy=%.2f light=%.2f duration=%.2fs%s", event,
        PROVENANCE_NAME[provenance], name, distanceScale, g_settings.strength,
        Peak(row->heavyMagnitudes, row->heavyCount) * s, Peak(row->lightMagnitudes, row->lightCount) * s,
        Length(*row), row->loop ? " (loop)" : "");
}

// A looping layer that should exist exactly while `wanted` holds.
void Hold(unsigned key, bool wanted, const RumbleRowK1* row, float scale, int provenance, const char* startEvent,
          const char* stopEvent) {
    Layer* const layer = Find(key);
    if (wanted && !layer) Play(row, scale, provenance, startEvent, 1.0f, key);
    else if (wanted && layer) layer->scale = scale;
    else if (!wanted && layer) Stop(key, stopEvent);
}

// The hum's pulse timing, on g_clock. A new hum layer starts with a pulse; each pulse then draws
// the gap to the next one afresh.
struct HumPulse { float layerStart; float next; float onUntil; unsigned seed; } g_humPulse = {-1.0f, 0, 0, 0};

float RandomBetween(float low, float high) {
    if (g_humPulse.seed == 0) g_humPulse.seed = static_cast<unsigned>(NowMs()) | 1u;
    unsigned x = g_humPulse.seed;   // xorshift32
    x ^= x << 13; x ^= x >> 17; x ^= x << 5;
    g_humPulse.seed = x;
    return low + (high - low) * static_cast<float>(x % 10001u) / 10000.0f;
}

// Is the pulsed hum in the silent part of its cycle right now?
bool HumGatedOff(const Layer& layer) {
    const float pulse = g_settings.humPulse;
    if (pulse <= 0.0f || pulse >= g_settings.humPeriodMin) return false;   // steady
    if (g_humPulse.layerStart != layer.start) {
        g_humPulse.layerStart = layer.start;
        g_humPulse.next = layer.start;
    }
    if (g_clock >= g_humPulse.next) {
        g_humPulse.onUntil = g_clock + pulse;
        g_humPulse.next = g_clock + RandomBetween(g_settings.humPeriodMin, g_settings.humPeriodMax);
    }
    return g_clock >= g_humPulse.onUntil;
}

void Mix(float& heavy, float& light) {
    heavy = 0.0f;
    light = 0.0f;
    for (Layer& layer : g_layers) {
        if (!layer.active) continue;
        const RumbleRowK1& r = *layer.row;
        const float t = g_clock - layer.start;
        bool doneA = true, doneB = true;
        const float a = Evaluate(r.heavyMagnitudes, r.heavyTimes, r.heavyCount, t, r.loop != 0, doneA) * layer.scale;
        float b = Evaluate(r.lightMagnitudes, r.lightTimes, r.lightCount, t, r.loop != 0, doneB) * layer.scale;
        // The hum's pulse gates BioWare's row; LightSaberOn has no heavy motor.
        if (layer.key == KEY_HUM && HumGatedOff(layer)) b = 0.0f;
        if (a > heavy) heavy = a;
        if (b > light) light = b;
        if (doneA && doneB) layer.active = false;
    }
}

// ------------------------------------------------------------ the engine

// CAppManager (engine.h's 0x100677CF0): the client app at +0x08, the server app at +0x10.
// CSWRules at 0x100677D80, its 2DA holder at +0xE8: footstepsounds.2da at +0xB0, visualeffects.2da
// at +0x110 (LookUpAndPerformRumbleWithCutOff, 0x10027A892).
const std::uintptr_t kAppManager = 0x100677cf0UL, kRules = 0x100677d80UL;
const std::size_t kRulesTwoDas = 0xe8, kFootstepTable = 0xb0, kVfxTable = 0x110;

const std::size_t kObjectId = 0x08;          // CGameObject's id, 64-bit
const std::size_t kObjectPosition = 0x38;    // CSWCObject's position
const std::size_t kObjectVfxList = 0x88;     // CSWCObject's visual effects (HasVisualEffectApplied)
const std::size_t kVfxId = 0x104;            // CSWCVisualEffectOnObject's id, a word
const std::size_t kItemBaseItem = 0x10;      // read by CSWItem::GetBaseItem (0x1002FE470)
const std::size_t kItemObjectId = 0x20;      // compared with GetEquippedItemID (0x1002D150E)
const std::size_t kItemOwner = 0x1b8;        // read by ResolveCreaturePoweredAnimations
const std::size_t kInternalRumbleOff = 0x3b8, kInternalLoadScreen = 0x398;   // UpdateRumble's bails
const std::size_t kVtAsItem = 0x70;          // CGameObject::AsSWCItem
const std::size_t kVtMaxHitPoints = 0x138, kVtCurrentHitPoints = 0x140;   // CSWSObject's
const int K1_SLOT_MAIN_HAND = 0x10, K1_SLOT_OFF_HAND = 0x20;
const std::uint64_t K1_OBJECT_INVALID = 0x7f000000;

struct ExoString { char* text; std::uint64_t length; };
using PtrFn = void* (*)(void*);
using IntFn = int (*)(void*);
using ObjectByIdFn = void* (*)(void* app, std::uint64_t id);
using IdByIdFn = std::uint64_t (*)(void* app, std::uint64_t id);
using SlotIdFn = std::uint64_t (*)(void* creature, int slot);
using HitPointsFn = short (*)(void* object, int);
using PanelExistsFn = int (*)(void* manager, void* panel);
using StrTextFn = void (*)(ExoString*, const char*);
using StrIntFn = void (*)(ExoString*, int);
using StrFreeFn = void (*)(ExoString*);
using IntRowFn = int (*)(void* table, int row, ExoString* column, int* out);
using FloatRowFn = int (*)(void* table, int row, ExoString* column, float* out);
using IntLabelFn = int (*)(void* table, ExoString* label, ExoString* column, int* out);
using FloatLabelFn = int (*)(void* table, ExoString* label, ExoString* column, float* out);

template <typename T> T Fn(std::uintptr_t address) { return reinterpret_cast<T>(address); }

const std::uintptr_t kGetGameObject = 0x10028bc78UL;          // CClientExoApp::GetGameObject
const std::uintptr_t kGetEquippedItemId = 0x1002977b4UL;      // CSWCCreature::GetEquippedItemID
const std::uintptr_t kClientToServerId = 0x10043bf2eUL;       // CServerExoApp::ClientToServerObjectId
const std::uintptr_t kServerCreatureById = 0x10043bc5aUL;     // CServerExoApp::GetCreatureByGameObjectID
const std::uintptr_t kFadeObscuring = 0x1002607d4UL;          // CGuiInGame::IsGlobalFadeObscuring
const std::uintptr_t kFading = 0x1002607b0UL;                 // CGuiInGame::IsGlobalFading
const std::uintptr_t kPanelExists = 0x10049d9ceUL;            // CSWGuiManager::PanelExists
const std::uintptr_t kStringFromText = 0x10034cca8UL, kStringFromInt = 0x10034cde8UL, kStringFree = 0x10034cdf2UL;
const std::uintptr_t k2daIntByRow = 0x10035f6daUL, k2daFloatByRow = 0x10035f2a6UL;
const std::uintptr_t k2daIntByLabel = 0x10035f572UL, k2daFloatByLabel = 0x10035f1c8UL;

bool LooksLikePointer(const void* p) {
    const auto v = reinterpret_cast<std::uintptr_t>(p);
    return v >= 0x100000 && v < 0x800000000000ULL;
}

// IsReadableK1's part: a read that reports a hole instead of faulting.
bool SafeRead(const void* address, void* out, std::size_t size) {
    mach_vm_size_t got = 0;
    return LooksLikePointer(address) &&
           mach_vm_read_overwrite(mach_task_self(), reinterpret_cast<mach_vm_address_t>(address), size,
                                  reinterpret_cast<mach_vm_address_t>(out), &got) == KERN_SUCCESS &&
           got == size;
}

void* PlayerCreature() {
    void* const app = engine::ClientApp();
    if (!LooksLikePointer(app)) return nullptr;
    void* const creature = engine::GetPlayerCreature()(app);
    return LooksLikePointer(creature) ? creature : nullptr;
}

std::uint64_t IdOf(const void* object) { return At<std::uint64_t>(const_cast<void*>(object), kObjectId); }

std::uint64_t CurrentTarget() {
    void* const internal = engine::ClientInternal();
    return internal ? At<std::uint64_t>(internal, engine::kInternalTarget) : 0;
}

bool PositionOf(const void* object, float out[3]) {
    return SafeRead(static_cast<const std::uint8_t*>(object) + kObjectPosition, out, 12);
}

float Distance(const float a[3], const float b[3]) {
    const float x = a[0] - b[0], y = a[1] - b[1], z = a[2] - b[2];
    return std::sqrt(x * x + y * y + z * z);
}

// Full authored strength near the source, then a smooth fade to nothing at the 2DA's
// RumbleCutOff. The full-strength radius is a quarter of the cutoff, never under 2 m.
float Falloff(float distance, float cutoff) {
    if (cutoff <= 0.0f) return 1.0f;
    if (distance >= cutoff) return 0.0f;
    float inner = cutoff * 0.25f;
    if (inner < 2.0f) inner = 2.0f;
    if (inner >= cutoff || distance <= inner) return 1.0f;
    const float u = (distance - inner) / (cutoff - inner);
    return 1.0f - u * u * (3.0f - 2.0f * u);
}

// The lookups LookUpAndPerformRumbleWithCutOff makes, through the same accessors: category 0 is
// footstepsounds.2da by row number, category 1 is visualeffects.2da by row label (the VFX id).
bool LookUpRumble(int category, int row, int& pattern, float& cutoff) {
    void* const rules = *reinterpret_cast<void**>(kRules);
    if (!LooksLikePointer(rules)) return false;
    void* const tables = At<void*>(rules, kRulesTwoDas);
    if (!LooksLikePointer(tables)) return false;
    void* const table = At<void*>(tables, category == 0 ? kFootstepTable : kVfxTable);
    if (!LooksLikePointer(table)) return false;
    ExoString patternColumn{}, cutoffColumn{}, label{};
    Fn<StrTextFn>(kStringFromText)(&patternColumn, "RumblePattern");
    Fn<StrTextFn>(kStringFromText)(&cutoffColumn, "RumbleCutOff");
    bool found;
    cutoff = 10.0f;   // the engine's default
    if (category == 0) {
        found = Fn<IntRowFn>(k2daIntByRow)(table, row, &patternColumn, &pattern) != 0;
        if (found) Fn<FloatRowFn>(k2daFloatByRow)(table, row, &cutoffColumn, &cutoff);
    } else {
        Fn<StrIntFn>(kStringFromInt)(&label, row);
        found = Fn<IntLabelFn>(k2daIntByLabel)(table, &label, &patternColumn, &pattern) != 0;
        if (found) Fn<FloatLabelFn>(k2daFloatByLabel)(table, &label, &cutoffColumn, &cutoff);
        Fn<StrFreeFn>(kStringFree)(&label);
    }
    Fn<StrFreeFn>(kStringFree)(&cutoffColumn);
    Fn<StrFreeFn>(kStringFree)(&patternColumn);
    return found && pattern >= 0 && pattern < K1_RUMBLE_PATTERN_COUNT;
}

// The VFX ids `object` carries right now, at most `capacity` of them: CSWCObject's list at +0x88,
// a CExoLinkedList whose nodes are {prev, next, data}.
int VfxOn(void* object, int* ids, int capacity) {
    int count = 0;
    void* list = nullptr;
    if (!SafeRead(static_cast<char*>(object) + kObjectVfxList, &list, sizeof list)) return 0;
    void* node = nullptr;
    if (!SafeRead(list, &node, sizeof node)) return 0;   // the head
    for (int guard = 0; node && guard < 64 && count < capacity; ++guard) {
        void* links[3] = {};
        if (!SafeRead(node, links, sizeof links)) break;
        std::uint16_t id = 0;
        if (SafeRead(static_cast<char*>(links[2]) + kVfxId, &id, sizeof id)) ids[count++] = id;
        node = links[1];
    }
    return count;
}

bool AnyOf(const int* have, int haveCount, const int* want, int wantCount) {
    for (int i = 0; i < haveCount; ++i)
        for (int j = 0; j < wantCount; ++j) if (have[i] == want[j]) return true;
    return false;
}

std::uint64_t EquippedItemId(void* creature, int slot) {
    return Fn<SlotIdFn>(kGetEquippedItemId)(creature, slot);
}

int BaseItemOf(std::uint64_t itemId) {
    void* const app = engine::ClientApp();
    if (!LooksLikePointer(app) || itemId == 0 || itemId == K1_OBJECT_INVALID) return -1;
    void* const object = Fn<ObjectByIdFn>(kGetGameObject)(app, itemId);
    if (!LooksLikePointer(object)) return -1;
    const std::uintptr_t vtable = At<std::uintptr_t>(object, 0);
    void* const item = reinterpret_cast<PtrFn>(*reinterpret_cast<std::uintptr_t*>(vtable + kVtAsItem))(object);
    return LooksLikePointer(item) ? At<int>(item, kItemBaseItem) : -1;
}

// baseitems.2da rows. Sabers: 8 Lightsaber, 9 Double-Bladed, 10 Short.
// Recoil by weaponwield: 4 pistols, 5 rifles, 6 repeaters.
bool IsSaber(int base) { return base == 8 || base == 9 || base == 10; }
int RecoilFor(int base) {
    switch (base) {
        case 12: case 13: case 14: case 15: case 16: case 17: return P_PISTOL;
        case 18: case 19: case 20: case 21: case 22: case 77: return P_RIFLE;
        case 23: case 24: return P_REPEATER;
        default: return 0;
    }
}

// The rumble pause (CExoInput::PauseRumble and UnpauseRumble), set by the combat and auto pauses
// and by the autosave. The Mac's own are empty; KMRP keeps the flag from their callers.
bool g_rumblePaused = false;
bool RumblePaused() { return g_rumblePaused; }

// UpdateRumble's own bails (0x10026AEF6): no frame time, rumble switched off, a fade covering the
// screen or running, or a load screen up. On those frames the engine neither advances its
// patterns nor sends anything.
bool EngineSilent(void* owner, float dt) {
    if (!(dt > 0.0f) || !LooksLikePointer(owner)) return true;
    if (At<int>(owner, kInternalRumbleOff) != 0) return true;
    void* const gui = At<void*>(owner, engine::kInternalGuiInGame);
    if (!LooksLikePointer(gui)) return true;
    if (Fn<IntFn>(kFadeObscuring)(gui) || Fn<IntFn>(kFading)(gui)) return true;
    void* const loadScreen = At<void*>(owner, kInternalLoadScreen);
    void* const manager = At<void*>(owner, engine::kInternalGuiManager);
    return loadScreen && manager && Fn<PanelExistsFn>(kPanelExists)(manager, loadScreen) != 0;
}

// ------------------------------------------------------------ Enhanced rules

// VFX rows KMRP gives rumble to, in Enhanced mode, and only where BioWare's row has none. A rule
// fires on the controlled character, on its current target, or anywhere within `cutoff` metres,
// faded by Falloff; 0 means "not this way".
struct Rule { int vfx; int onPlayer; int onTarget; int world; float cutoff; const char* label; };
const Rule KMRP_VFX_RULES[] = {
    { 4004, P_SABER_CLASH,     P_SABER_CLASH,    0, 0.0f, "VFX_COM_SPARKS_LIGHTSABER" },
    { 4023, P_BLASTER_DEFLECT, 0,                0, 0.0f, "VFX_COM_BLASTER_DEFLECTION" },
    { 4024, P_BOLT_HIT,        0,                0, 0.0f, "VFX_COM_BLASTER_IMPACT" },
    { 4025, P_SABER_SPECIAL,   P_SABER_SPECIAL,  0, 0.0f, "VFX_COM_CRITICAL_STRIKE_IMPROVED_SABER" },
    { 4026, P_SABER_SPECIAL,   P_SABER_SPECIAL,  0, 0.0f, "VFX_COM_CRITICAL_STRIKE_MASTERY_SABER" },
    { 4027, P_SABER_SPECIAL,   P_SABER_SPECIAL,  0, 0.0f, "VFX_COM_POWER_ATTACK_IMPROVED_SABER" },
    { 4028, P_SABER_SPECIAL,   P_SABER_SPECIAL,  0, 0.0f, "VFX_COM_POWER_ATTACK_MASTERY_SABER" },
    { 4030, P_SABER_SPECIAL,   P_SABER_SPECIAL,  0, 0.0f, "VFX_COM_FLURRY_IMPROVED_SABER" },
    { 4031, P_SABER_SPECIAL,   P_SABER_SPECIAL,  0, 0.0f, "VFX_COM_WHIRLWIND_STRIKE_SABER" },
    { 4017, P_SABER_SPECIAL,   P_SABER_SPECIAL,  0, 0.0f, "VFX_COM_WHIRLWIND_STRIKE_STAFF" },
    { 4013, P_RIFLE,           P_RIFLE,          0, 0.0f, "VFX_COM_POWER_BLAST_IMPROVED" },
    { 4029, P_RIFLE,           P_RIFLE,          0, 0.0f, "VFX_COM_POWER_BLAST_MASTERY" },
    { 1021, P_LIGHTNING,       P_LIGHTNING_CAST, 0, 0.0f, "VFX_PRO_LIGHTNING_L" },
    { 1028, P_LIGHTNING,       P_LIGHTNING_CAST, 0, 0.0f, "VFX_PRO_LIGHTNING_S" },
    { 1035, P_LIGHTNING,       P_LIGHTNING_CAST, 0, 0.0f, "VFX_PRO_LIGHTNING_JEDI" },
    { 1036, P_LIGHTNING,       P_LIGHTNING_CAST, 0, 0.0f, "VFX_PRO_LIGHTNING_L_SOUND" },
    { 1009, 0,                 P_BUFF,           0, 0.0f, "VFX_PRO_DRAIN" },
    { 1018, 0,                 P_BUFF,           0, 0.0f, "VFX_IMP_FORCE_WHIRLWIND" },
    { 1010, P_BUFF,            0,                0, 0.0f, "VFX_PRO_FORCE_ARMOR" },
    { 1015, P_BUFF,            0,                0, 0.0f, "VFX_PRO_FORCE_SHIELD" },
    { 1020, P_BUFF,            0,                0, 0.0f, "VFX_IMP_SPEED_KNIGHT" },
    { 1022, P_BUFF,            0,                0, 0.0f, "VFX_IMP_SPEED_MASTERY" },
    { 1040, P_STUN,            0,                0, 0.0f, "VFX_IMP_STUN" },
    { 4034, 0, 0, P_DROID_EXPLOSION, 12.0f, "VFX_COM_DROID_EXPLOSION_1" },
    { 4035, 0, 0, P_DROID_EXPLOSION, 12.0f, "VFX_COM_DROID_EXPLOSION_2" },
    { 3006, 0, 0, P_SOFT_GRENADE,     5.0f, "VFX_FNF_GRENADE_POISON" },
    { 3008, 0, 0, P_SOFT_GRENADE,     5.0f, "VFX_FNF_GRENADE_ADHESIVE" },
    { 3002, 0, 0, P_SONIC,           12.0f, "VFX_FNF_PLOT_MAN_SONIC_WAVE" },
    { 3014, 0, 0, P_DEBRIS,          18.0f, "VFX_FNF_ROCK_FALL_1" },
    { 3015, 0, 0, P_DEBRIS,          18.0f, "VFX_FNF_ROCK_FALL_2" },
    { 3016, 0, 0, P_SHIP_IMPACT,     40.0f, "VFX_FNF_SPACE_LASER" },
    { 1045, 0, 0, 11,                30.0f, "VFX_PLOT_TAR_RANCOR_DEATH" },   // BioWare's Rancor row
};

// Effects that last, polled on the controlled character every frame.
const int WHIRLWIND_VFX[] = { 2007 };                        // VFX_DUR_FORCE_WHIRLWIND
const int ELECTRIC_VFX[]  = { 2037, 2038, 2061, 2066, 2065, 2052, 2049, 2050,
                              1021, 1028, 1035, 1036 };      // lightning, shock, stun and ion
const int DRAIN_VFX[]     = { 2029, 1009 };                  // VFX_BEAM_DRAIN_LIFE, VFX_PRO_DRAIN
#define KMRP_COUNT_OF(a) static_cast<int>(sizeof(a) / sizeof((a)[0]))

// ------------------------------------------------------------ player state

// Set by the positional observer for the play the engine makes a moment later. `handled`:
// Enhanced has already played the row itself, so the engine's own play of that same pattern is
// swallowed.
struct Positional { bool valid; int category; int row; int pattern; float distance; float cutoff; bool handled; } g_positional = {};

struct Health {
    std::uint64_t creature;
    int hp;
    bool valid;
    bool dead;
    float lastHit;   // on g_clock
    int burst;       // damage merged into the current hit
} g_health = {};

struct Saber { std::uint64_t item; std::uint64_t owner; bool on; };
Saber g_sabers[32] = {};

std::uint64_t g_controlled = 0;
bool g_wasMuted = false;
int g_shotsLogged = 0;

Saber* SaberSlot(std::uint64_t item) {
    for (Saber& s : g_sabers) if (s.item == item) return &s;
    for (Saber& s : g_sabers) if (s.item == 0) { s = {item, 0, false}; return &s; }
    for (Saber& s : g_sabers) if (s.owner != g_controlled) { s = {item, 0, false}; return &s; }
    return nullptr;
}

// Damage as a share of maximum health through a bounded curve: a scratch still registers, three
// tenths of the bar is the ceiling, and nothing exceeds 0.8.
float DamageIntensity(int damage, int maximum) {
    const float ratio = maximum > 0 ? static_cast<float>(damage) / maximum : 0.0f;
    float u = ratio / 0.3f;
    if (u > 1.0f) u = 1.0f;
    return 0.30f + 0.50f * u * u * (3.0f - 2.0f * u);
}

// The controlled character's server creature, whose hit points are the real ones (the HUD's).
void* ServerCreature(void* creature) {
    void* const manager = *reinterpret_cast<void**>(kAppManager);
    void* const server = LooksLikePointer(manager) ? At<void*>(manager, 0x10) : nullptr;
    if (!LooksLikePointer(server)) return nullptr;
    const std::uint64_t id = Fn<IdByIdFn>(kClientToServerId)(server, IdOf(creature));
    void* const object = Fn<ObjectByIdFn>(kServerCreatureById)(server, id);
    return LooksLikePointer(object) ? object : nullptr;
}

void PollHealth(void* creature, bool live) {
    void* const server = ServerCreature(creature);
    if (!server) return;
    const std::uintptr_t vtable = At<std::uintptr_t>(server, 0);
    if (!LooksLikePointer(reinterpret_cast<void*>(vtable))) return;
    const int hp = reinterpret_cast<HitPointsFn>(*reinterpret_cast<std::uintptr_t*>(vtable + kVtCurrentHitPoints))(server, 0);
    const int maximum = reinterpret_cast<HitPointsFn>(*reinterpret_cast<std::uintptr_t*>(vtable + kVtMaxHitPoints))(server, 1);
    const std::uint64_t id = IdOf(creature);
    if (!g_health.valid || g_health.creature != id) {
        g_health = {id, hp, true, hp <= 0, -1.0f, 0};
        return;   // a new character: a baseline, not a hit
    }
    // Not once dead: hit points can go on falling below zero, and the death impact is the last
    // thing felt.
    if (live && hp < g_health.hp && !g_health.dead && Enhanced()) {
        const int damage = g_health.hp - hp;
        if (g_health.lastHit >= 0.0f && g_clock - g_health.lastHit < 0.05f) {
            g_health.burst += damage;
        } else {
            g_health.burst = damage;
            g_health.lastHit = g_clock;
        }
        const bool heavy = maximum > 0 && g_health.burst * 5 >= maximum;
        char event[64];
        std::snprintf(event, sizeof event, "PlayerDamaged %d of %d", g_health.burst, maximum);
        Play(Kmrp(heavy ? P_DAMAGE_HEAVY : P_DAMAGE), DamageIntensity(g_health.burst, maximum), ENHANCED, event, 1.0f,
             KEY_NONE, 0.05f);
    }
    if (hp <= 0 && !g_health.dead) {
        g_health.dead = true;
        StopAll("controlled character died");
        Play(Kmrp(P_DEATH), 1.0f, ENHANCED, "PlayerDeath", 1.0f);
    } else if (hp > 0) {
        g_health.dead = false;
    }
    g_health.hp = hp;
}

// The hum is state, not an event: it exists while the controlled character has a lit blade in
// hand, and is re-derived every frame.
void UpdateSabers(void* creature) {
    const std::uint64_t id = IdOf(creature);
    const std::uint64_t main = EquippedItemId(creature, K1_SLOT_MAIN_HAND);
    const std::uint64_t off = EquippedItemId(creature, K1_SLOT_OFF_HAND);
    int lit = 0;
    for (const Saber& s : g_sabers)
        if (s.item && s.on && s.owner == id && (s.item == main || s.item == off)) ++lit;
    const float scale = (lit > 1 ? 1.15f : 1.0f) * g_settings.hum;
    Hold(KEY_HUM, lit > 0 && !g_health.dead && scale > 0.0f, BioWare(0), scale, RESTORED,
         lit > 1 ? "LightsaberHum dual" : "LightsaberHum", "LightsaberHumEnded");
}

// Whirlwind, electricity and drain are states too: each loop exists exactly while its VFX is on
// the controlled character.
void UpdatePersistent(void* creature) {
    int vfx[64];
    const int n = g_health.dead ? 0 : VfxOn(creature, vfx, 64);
    Hold(KEY_WHIRLWIND, AnyOf(vfx, n, WHIRLWIND_VFX, KMRP_COUNT_OF(WHIRLWIND_VFX)), BioWare(21), 1.0f, RESTORED,
         "WhirlwindOnPlayer", "WhirlwindEnded");
    Hold(KEY_ELECTRIC, AnyOf(vfx, n, ELECTRIC_VFX, KMRP_COUNT_OF(ELECTRIC_VFX)), Kmrp(P_ELECTRIC_LOOP), 1.0f,
         ENHANCED, "ElectricOnPlayer", "ElectricEnded");
    Hold(KEY_DRAIN, AnyOf(vfx, n, DRAIN_VFX, KMRP_COUNT_OF(DRAIN_VFX)), Kmrp(P_DRAIN_LOOP), 1.0f, ENHANCED,
         "DrainOnPlayer", "DrainEnded");
}

void StopStates(const char* why) {
    Stop(KEY_HUM, why);
    Stop(KEY_WHIRLWIND, why);
    Stop(KEY_ELECTRIC, why);
    Stop(KEY_DRAIN, why);
}

void LogPositional(int category, int row, int pattern, float cutoff, float reach, float distance) {
    static int logged = 0;
    if (!g_settings.debug || logged >= 300) return;
    ++logged;
    Log("positional %s %d pattern=BioWare %d cutoff=%.1fm reach=%.1fm player=%.1fm", category == 0 ? "footstep" : "VFX",
        row, pattern, cutoff, reach, distance);
}

void LogOutput(float heavy, float light, float dt, bool muted) {
    static int logged = 0;
    if (!g_settings.debug || logged >= 1500) return;
    bool transient = false;
    for (const Layer& layer : g_layers) if (layer.active && layer.key == KEY_NONE) { transient = true; break; }
    if (!transient) return;
    ++logged;
    Log("out heavy=%.3f light=%.3f dt=%.3f%s", muted ? 0.0f : heavy * g_settings.strength,
        muted ? 0.0f : light * g_settings.strength, dt, muted ? " muted" : "");
}

// KmrpRumbleTickK1: once a frame. Time runs exactly when the engine's own patterns would run; the
// rumble pause and the menus mute the motors without stopping time, as they do the engine's.
void Tick(void* owner, float dt, float& heavy, float& light) {
    LoadSettings();
    heavy = 0.0f;
    light = 0.0f;
    ++g_count.frames;
    g_positional.valid = false;   // context never outlives its own call
    void* const creature = PlayerCreature();
    if (!creature) {
        if (g_controlled) StopAll("no controlled character");
        g_controlled = 0;
        g_health.valid = false;
        return;
    }
    const std::uint64_t id = IdOf(creature);
    if (id != g_controlled) {
        if (g_controlled) Log("controlled character changed");
        g_controlled = id;
    }
    const bool frozen = EngineSilent(owner, dt);
    if (!frozen) g_clock += dt;
    const bool muted = frozen || RumblePaused() || engine::CurrentInputClass() == engine::kClassPCGUI;
    if (muted != g_wasMuted) Log(muted ? "muted" : "unmuted");
    g_wasMuted = muted;
    PollHealth(creature, !muted);
    if (Enhanced()) {
        UpdateSabers(creature);
        UpdatePersistent(creature);
    } else {
        StopStates("mode is not Enhanced");
    }
    Mix(heavy, light);   // also retires finished layers while muted
    LogOutput(heavy, light, dt, muted);
    if (muted || g_settings.mode == MODE_OFF) {
        heavy = 0.0f;
        light = 0.0f;
        return;
    }
    heavy *= g_settings.strength;
    light *= g_settings.strength;
    if (heavy > 1.0f) heavy = 1.0f;
    if (light > 1.0f) light = 1.0f;
}

}  // namespace

void Status() {
    int live = 0;
    for (const Layer& layer : g_layers) if (layer.active) ++live;
    kmrp::Log("rumble: mode %s, %lu patterns started (%lu from the engine), %d playing, %lu frames, %lu sends%s",
              MODE_NAME[g_settings.mode], g_count.plays, g_count.engineRows, live, g_count.frames, g_count.sent,
              g_rumblePaused ? ", paused" : "");
}

}  // namespace rumble
}  // namespace kmrp

using namespace kmrp::rumble;

// MainLoop's call to UpdateRumble (0x1002687F1), replaced: the mixer's frame, and the pad's
// motors. The engine's own UpdateRumble would only advance an empty queue and call a SetRumble
// that does nothing. Always consumes (a relative call). rdi, the internal, is r13 there.
extern "C" __attribute__((visibility("default"))) int KmrpRumbleFrame(void* internal) {
    float heavy = 0.0f, light = 0.0f;
    Tick(internal, kmrp::engine::FrameSeconds(), heavy, light);
    if (kmrp::SetRumble(heavy, light)) ++g_count.sent;
    return 1;
}

// CClientExoAppInternal::PlayRumblePattern, after its prologue (0x10027A106), with the index in
// esi. Every rumble the engine starts -- a script's PlayRumblePattern, a footstep, a VFX --
// arrives here, and the mixer plays it instead of the engine's queue.
extern "C" __attribute__((visibility("default"))) int KmrpRumblePlay(void* internal, int index) {
    (void)internal;
    LoadSettings();
    const RumbleRowK1* const row = BioWare(index);
    if (!row) return 1;
    ++g_count.engineRows;
    // As the engine: a looping row already playing is not started again; a one-shot row
    // overlaps its running copy freely.
    if (row->loop) {
        for (const Layer& layer : g_layers)
            if (layer.active && layer.provenance == ORIGINAL && layer.row == row) return 1;
    }
    char event[64];
    if (g_positional.valid && g_positional.pattern == index) {
        g_positional.valid = false;
        if (g_positional.handled) return 1;   // Enhanced played it already, from the observer
        std::snprintf(event, sizeof event, "%s %d at %.1fm", g_positional.category == 0 ? "Footstep" : "VFX",
                      g_positional.row, g_positional.distance);
    } else {
        std::snprintf(event, sizeof event, "Script");
    }
    Play(row, 1.0f, ORIGINAL, event, 1.0f);
    return 1;
}

// CClientExoAppInternal::StopRumblePattern (0x10027A1D2), at its entry: the engine's queue is
// empty, so stopping is the mixer's job. Observes.
extern "C" __attribute__((visibility("default"))) void KmrpRumbleStop(void* internal, int index) {
    (void)internal;
    int stopped = 0;
    for (Layer& layer : g_layers) {
        if (layer.active && layer.provenance == ORIGINAL && layer.row->index == index) {
            layer.active = false;
            ++stopped;
        }
    }
    if (stopped) Log("stop pattern=BioWare %d reason=script", index);
}

// CExoInput's PauseRumble and UnpauseRumble, at their wrappers' entries (0x100359D86, 0x100359D94).
extern "C" __attribute__((visibility("default"))) void KmrpRumblePause(void) {
    if (!g_rumblePaused) Log("paused");
    g_rumblePaused = true;
}
extern "C" __attribute__((visibility("default"))) void KmrpRumbleUnpause(void) {
    if (g_rumblePaused) Log("unpaused");
    g_rumblePaused = false;
}

// CClientExoAppInternal::LookUpAndPerformRumbleWithCutOff (0x10027A892), at its entry: the row,
// the category (0 footstepsounds, 1 visualeffects) and the position. An observer: the engine
// carries on either way. Where BioWare's row has a pattern, this leaves the context KmrpRumblePlay
// reads a moment later; where it has none, Enhanced mode applies KMRP's rules.
extern "C" __attribute__((visibility("default"))) void KmrpRumbleCutoff(void* internal, int row, int categoryByte,
                                                                         const float* position) {
    (void)internal;
    g_positional.valid = false;
    const int category = categoryByte & 0xff;
    float where[3];
    if ((category != 0 && category != 1) || !SafeRead(position, where, sizeof where)) return;
    LoadSettings();
    void* const creature = PlayerCreature();
    float listener[3];
    if (!creature || !PositionOf(creature, listener)) return;
    const float distance = Distance(listener, where);
    int pattern = -1;
    float cutoff = 10.0f;
    if (LookUpRumble(category, row, pattern, cutoff)) {
        // Enhanced reach: three times BioWare's cutoff when that is under 10 m, BioWare's own
        // beyond (K1Rumble.cpp).
        const float reach = cutoff < 10.0f ? cutoff * 3.0f : cutoff;
        LogPositional(category, row, pattern, cutoff, reach, distance);
        if (!Enhanced()) {
            if (distance * distance < cutoff * cutoff) g_positional = {true, category, row, pattern, distance, cutoff, false};
            return;
        }
        g_positional = {true, category, row, pattern, distance, cutoff, true};
        const float scale = Falloff(distance, reach);
        if (scale <= 0.0f) return;
        char event[64];
        std::snprintf(event, sizeof event, "%s %d at %.1fm", category == 0 ? "Footstep" : "VFX", row, distance);
        Play(BioWare(pattern), scale, distance < cutoff ? ORIGINAL : ENHANCED, event, scale);
        return;
    }
    if (category != 1 || !Enhanced()) return;
    for (const Rule& rule : KMRP_VFX_RULES) {
        if (rule.vfx != row) continue;
        // The engine passes the carrying object's own position field.
        const std::uint8_t* const object = reinterpret_cast<const std::uint8_t*>(position) - kObjectPosition;
        const bool onPlayer = object == creature;
        const std::uint64_t target = CurrentTarget();
        std::uint64_t objectId = 0;
        const bool onTarget = !onPlayer && target != 0 && target != K1_OBJECT_INVALID &&
                              SafeRead(object + kObjectId, &objectId, sizeof objectId) && objectId == target;
        char event[96];
        if (onPlayer && rule.onPlayer) {
            std::snprintf(event, sizeof event, "VFX %d %s on player", row, rule.label);
            Play(Pattern(rule.onPlayer), 1.0f, ENHANCED, event, 1.0f, KEY_NONE, 0.04f);
        } else if (onTarget && rule.onTarget) {
            std::snprintf(event, sizeof event, "VFX %d %s on target", row, rule.label);
            Play(Pattern(rule.onTarget), 1.0f, ENHANCED, event, 1.0f, KEY_NONE, 0.04f);
        } else if (rule.world) {
            const float scale = Falloff(distance, rule.cutoff);
            std::snprintf(event, sizeof event, "VFX %d %s at %.1fm", row, rule.label, distance);
            if (scale > 0.0f) Play(Pattern(rule.world), scale, ENHANCED, event, scale, KEY_NONE, 0.04f);
        }
        return;
    }
}

// CSWCItem::ResolveCreaturePoweredAnimations (0x1002D150E), at its entry: the item and the power
// state PowerItem settled on, including its forced "off", whenever any blade lights or goes out.
extern "C" __attribute__((visibility("default"))) void KmrpSaberPower(void* item, int power) {
    if (!LooksLikePointer(item) || !IsSaber(At<int>(item, kItemBaseItem))) return;
    const bool on = power != 0;
    const std::uint64_t id = At<std::uint64_t>(item, kItemObjectId);
    const std::uint64_t owner = At<std::uint64_t>(item, kItemOwner);
    Saber* const saber = SaberSlot(id);
    if (!saber) return;
    const bool was = saber->on && saber->owner == owner;
    saber->owner = owner;
    saber->on = on;
    if (was == on || g_controlled == 0 || owner != g_controlled) return;
    LoadSettings();
    // Both blades of a pair light together: one pulse, not two.
    Play(Kmrp(on ? P_SABER_IGNITE : P_SABER_RETRACT), 1.0f, ENHANCED, on ? "LightsaberIgnite" : "LightsaberRetract",
         1.0f, KEY_NONE, 0.15f);
}

// CSWCCreature::ShowLightSaberContactVisual (0x100295F16), at its entry, from the animation
// event "Contact": blade meeting blade, a clash.
extern "C" __attribute__((visibility("default"))) void KmrpSaberContact(void* creature) {
    if (g_controlled == 0 || !LooksLikePointer(creature) || IdOf(creature) != g_controlled) return;
    LoadSettings();
    Play(Kmrp(P_SABER_CLASH), 1.0f, ENHANCED, "LightsaberContact", 1.0f, KEY_NONE, 0.2f);
}

// The animation event "hit" (0x100296007, registered by CSWCCreature::RegisterCallbacks): the
// moment an attack's blow lands or fails. Results 1, 2, 3 and 5 take the engine's hit branch; 4
// and 8 its parry. So this fires when, and only when, the controlled character's blow connects.
extern "C" __attribute__((visibility("default"))) void KmrpMeleeHit(const std::uint8_t* attack) {
    std::uint8_t record[0x38];
    if (g_controlled == 0 || !SafeRead(attack, record, sizeof record)) return;
    std::uint64_t attacker = 0;
    int skip = 0;
    std::memcpy(&attacker, record + 0x08, sizeof attacker);
    std::memcpy(&skip, record + 0x30, sizeof skip);
    if (attacker != g_controlled || skip != 0) return;
    const int result = record[0x14];
    if (result != 1 && result != 2 && result != 3 && result != 5) return;
    void* const creature = PlayerCreature();
    if (!creature) return;
    const int base = BaseItemOf(EquippedItemId(creature, K1_SLOT_MAIN_HAND));
    if (RecoilFor(base)) return;
    LoadSettings();
    char event[48];
    std::snprintf(event, sizeof event, "%s result %d", IsSaber(base) ? "LightsaberHit" : "MeleeHit", result);
    Play(Kmrp(IsSaber(base) ? P_SABER_HIT : P_MELEE_HIT), 1.0f, ENHANCED, event, 1.0f, KEY_NONE, 0.08f);
}

// CSWCObject::AnimationParry (0x10033CB7E), at its entry: the object parrying. Felt when the
// controlled character parries, or when its target parries it.
extern "C" __attribute__((visibility("default"))) void KmrpParry(void* object) {
    if (g_controlled == 0 || !LooksLikePointer(object)) return;
    const std::uint64_t id = IdOf(object);
    if (id != g_controlled && id != CurrentTarget()) return;
    LoadSettings();
    Play(Kmrp(P_SABER_CLASH), 1.0f, ENHANCED, id == g_controlled ? "PlayerParried" : "TargetParried", 1.0f, KEY_NONE,
         0.2f);
}

// CSWCProjectile::CreateMuzzleFlash (0x1002DD810), at its entry: a shot leaving a weapon. A shot
// counts as the controlled character's when it starts within 1.6 m of them while they hold a
// ranged weapon; the first 40 are logged with their distance either way.
extern "C" __attribute__((visibility("default"))) void KmrpMuzzleFlash(void* projectile) {
    if (g_controlled == 0) return;
    void* const creature = PlayerCreature();
    float shot[3], player[3];
    if (!creature || !PositionOf(projectile, shot) || !PositionOf(creature, player)) return;
    LoadSettings();
    const float distance = Distance(shot, player);
    const int base = BaseItemOf(EquippedItemId(creature, K1_SLOT_MAIN_HAND));
    const int recoil = RecoilFor(base);
    if (g_shotsLogged < 40) {
        ++g_shotsLogged;
        Log("muzzle flash at %.2fm, player weapon baseitem %d%s", distance, base,
            distance <= 1.6f && recoil ? " -> recoil" : "");
    }
    if (distance > 1.6f || !recoil) return;
    Play(Kmrp(recoil), 1.0f, ENHANCED, "PlayerFired", 1.0f);
}
