// KMRP rumble: one mixer for BioWare's own patterns, the BioWare patterns whose
// triggers were cut, and KMRP's Enhanced haptics. See docs/controller-rumble.md.
//
// Every rumble is a LAYER: a pattern in BioWare's envelope format, a start time,
// a scale and a provenance. Layers come from three kinds of source -- the
// player's own actions, things done to the player, and events in the world,
// which are scaled by distance. Each frame the mixer takes the maximum per motor
// across all live layers, so two 60% effects stay 60%, and a quiet loop (the
// saber hum) is covered by a stronger transient and felt again when it ends. The
// result is scaled by the player's strength setting and sent. BioWare's patterns
// are never edited: distance and strength scale the OUTPUT, not the table.
//
//     output = pattern magnitude x distance scale x strength
//
// Provenance is kept on every layer and printed in every log line:
//   Original  BioWare's shipped mappings -- scripts, footstepsounds.2da and
//             visualeffects.2da. The only thing Original mode plays.
//   Restored  BioWare rows the shipped game never triggers (0 LightSaberOn,
//             21 Whirlwind), attached to the events their names describe.
//   Enhanced  KMRP's own patterns, KMRP_..., and KMRP's use of BioWare rows on
//             events BioWare never gave rumble. None of this existed on Xbox.
//
// Time is the engine's own: the clock advances by UpdateRumble's frame time, and
// only on the frames where UpdateRumble would have advanced its own patterns.
// Load screens, fades, pause and menus freeze it and silence the motors.
#include <windows.h>
#include <cmath>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include "K1Rumble.h"

// Shared with K1NativeJoystick.cpp.
bool LooksLikePointerK1(const void* p);
bool IsReadableK1(const void* p, std::size_t size);
void* ClientExoAppK1();
int InputClassK1();
std::uint32_t CurrentTargetK1();

namespace {

template <typename T> T& At(const void* base, std::size_t offset)
{
    return *reinterpret_cast<T*>(reinterpret_cast<std::uintptr_t>(base) + offset);
}
template <typename T> T Fn(std::uintptr_t address) { return reinterpret_cast<T>(address); }

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
const char* const PROVENANCE_NAME[] = { "Original", "Restored", "Enhanced" };
const char* const MODE_NAME[] = { "Off", "Original", "Enhanced" };

struct Settings {
    int      mode = MODE_ENHANCED;
    float    strength = 1.0f;
    float    hum = 0.06f;
    float    humPulse = 0.1f;          // seconds on, per period; 0 = steady
    float    humPeriodMin = 0.5f;      // seconds from one pulse to the next,
    float    humPeriodMax = 2.0f;      // drawn afresh for every pulse
    bool     debug = false;
    FILETIME stamp{};
    DWORD    nextCheck = 0;
    bool     loaded = false;
} g_settings;

void Log(const char* format, ...);

// kmrp-controller.ini beside swkotor.exe, section [Rumble]:
//   Mode     = Off | Original | Enhanced   (default Enhanced)
//   Strength = 0-100                        (default 100)
//   SaberHum = 0-100                        (default 6; percent of LightSaberOn)
//   SaberHumPulseMs  = 0-1000               (default 100; 0 = a steady hum)
//   SaberHumPeriodMinMs = 50-5000           (default 500) the gap from one pulse
//   SaberHumPeriodMaxMs = 50-5000           (default 2000) to the next, drawn at
//                                           random between them for every pulse;
//                                           equal values give a fixed rhythm
//   Debug    = 0 | 1                        (default 0; 1 writes kmrp-rumble.log)
// Checked at most once a second and re-read when the file changes, so it can be
// tuned with the game running.
void LoadSettings()
{
    const DWORD now = GetTickCount();
    if (g_settings.loaded && static_cast<LONG>(now - g_settings.nextCheck) < 0) return;
    g_settings.nextCheck = now + 1000;
    char path[MAX_PATH] = {};
    const DWORD length = GetModuleFileNameA(nullptr, path, MAX_PATH);
    if (length == 0 || length >= MAX_PATH) return;
    char* const slash = std::strrchr(path, '\\');
    if (!slash || (slash - path) + 21 >= MAX_PATH) return;
    std::strcpy(slash + 1, "kmrp-controller.ini");
    WIN32_FILE_ATTRIBUTE_DATA info{};
    const bool exists = GetFileAttributesExA(path, GetFileExInfoStandard, &info) != 0;
    if (g_settings.loaded) {
        if (!exists) return;                                    // keep what was read
        if (CompareFileTime(&info.ftLastWriteTime, &g_settings.stamp) == 0) return;
    }
    if (exists) g_settings.stamp = info.ftLastWriteTime;
    char mode[32] = {};
    GetPrivateProfileStringA("Rumble", "Mode", "Enhanced", mode, sizeof(mode), path);
    if (!_stricmp(mode, "Off")) g_settings.mode = MODE_OFF;
    else if (!_stricmp(mode, "Original")) g_settings.mode = MODE_ORIGINAL;
    else g_settings.mode = MODE_ENHANCED;
    int strength = static_cast<int>(GetPrivateProfileIntA("Rumble", "Strength", 100, path));
    if (strength < 0) strength = 0;
    if (strength > 100) strength = 100;
    g_settings.strength = strength / 100.0f;
    // The hum's own level. BioWare's LightSaberOn is a constant 0.2 on the light
    // motor, and on the first pad test (2026-09-25) that was far too strong held
    // for as long as a blade is lit. The row is left as authored; this scales
    // its output, as distance and Strength do.
    //
    // Default 6: on an Xbox One or Series pad a motor takes whole percentages,
    // so the smallest vibration it can make is 1% of full power, and 6 is the
    // lowest setting that reaches it with one blade (0.2 x 0.06 = 1.2%) or two
    // (1.38%). The same test found even that too strong held steady, so by
    // default the hum is also PULSED: on for SaberHumPulseMs, then silent until
    // the next pulse, which is weaker on average than any steady level the pad
    // can play. The defaults, 100 ms every 500-2000 ms with a fresh random gap
    // each time, are what the user settled on in that test (2026-09-25): a
    // blade that flickers now and then rather than one that ticks like a clock.
    // A pulse as long as the shortest gap, or 0, is a steady hum.
    int hum = static_cast<int>(GetPrivateProfileIntA("Rumble", "SaberHum", 6, path));
    if (hum < 0) hum = 0;
    if (hum > 100) hum = 100;
    g_settings.hum = hum / 100.0f;
    int pulse = static_cast<int>(GetPrivateProfileIntA("Rumble", "SaberHumPulseMs", 100, path));
    if (pulse < 0) pulse = 0;
    if (pulse > 1000) pulse = 1000;
    int periodMin = static_cast<int>(GetPrivateProfileIntA("Rumble", "SaberHumPeriodMinMs", 500, path));
    int periodMax = static_cast<int>(GetPrivateProfileIntA("Rumble", "SaberHumPeriodMaxMs", 2000, path));
    if (periodMin > periodMax) { const int swap = periodMin; periodMin = periodMax; periodMax = swap; }
    if (periodMin < 50) periodMin = 50;
    if (periodMin > 5000) periodMin = 5000;
    if (periodMax > 5000) periodMax = 5000;
    if (periodMax < periodMin) periodMax = periodMin;
    g_settings.humPulse = pulse / 1000.0f;
    g_settings.humPeriodMin = periodMin / 1000.0f;
    g_settings.humPeriodMax = periodMax / 1000.0f;
    g_settings.debug = GetPrivateProfileIntA("Rumble", "Debug", 0, path) != 0;
    g_settings.loaded = true;
    Log("settings mode=%s strength=%d%% saberHum=%d%% pulse=%dms every %d-%dms debug=%d from=%s",
        MODE_NAME[g_settings.mode], strength, hum, pulse, periodMin, periodMax,
        g_settings.debug ? 1 : 0, exists ? "kmrp-controller.ini" : "defaults");
}

bool Enhanced() { return g_settings.mode == MODE_ENHANCED; }

// kmrp-rumble.log in the game folder, when Debug = 1. One line per event, never
// one per frame, and at most 4000 lines a session.
void Log(const char* format, ...)
{
    static int lines = 0;
    if (!g_settings.debug || lines >= 4000) return;
    ++lines;
    FILE* f = nullptr;
    if (fopen_s(&f, "kmrp-rumble.log", "a") || !f) return;
    va_list args;
    va_start(args, format);
    std::fprintf(f, "%lu [KMRP Rumble] ", GetTickCount());
    std::vfprintf(f, format, args);
    std::fputc('\n', f);
    va_end(args);
    std::fclose(f);
}

float Peak(const float* magnitudes, int count)
{
    float peak = 0.0f;
    for (int i = 0; magnitudes && i < count; ++i) if (magnitudes[i] > peak) peak = magnitudes[i];
    return peak;
}

float Length(const RumbleRowK1& row)
{
    const float a = row.heavyCount > 0 ? row.heavyTimes[row.heavyCount - 1] : 0.0f;
    const float b = row.lightCount > 0 ? row.lightTimes[row.lightCount - 1] : 0.0f;
    return a > b ? a : b;
}

void Name(const RumbleRowK1& row, char* out, std::size_t size)
{
    if (row.index < K1_RUMBLE_PATTERN_COUNT) sprintf_s(out, size, "BioWare %d %s", row.index, row.label);
    else sprintf_s(out, size, "%s", row.label);
}

// ------------------------------------------------------------ the mixer

// A keyed layer is a state, not an event: at most one exists per key, and it is
// started and stopped by the code that owns the state.
enum Key : unsigned { KEY_NONE = 0, KEY_HUM, KEY_WHIRLWIND, KEY_ELECTRIC, KEY_DRAIN };

struct Layer {
    const RumbleRowK1* row;
    float    start;                 // on g_clock
    float    scale;
    int      provenance;
    unsigned key;
    bool     active;
};
constexpr int K1_RUMBLE_LAYERS = 24;
Layer g_layers[K1_RUMBLE_LAYERS] = {};
float g_clock = 0.0f;               // seconds of unpaused, unfaded game time

// The engine's evaluator (CSWRumblePattern::GetMagnitude, 0x0068FCB0): linear
// between the keyframes that bracket t; 0 before the first keyframe and past the
// last; a looping pattern wraps by its last keyframe's time.
float Evaluate(const float* magnitudes, const float* times, int count, float t, bool loop, bool& done)
{
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

Layer* Find(unsigned key)
{
    if (key == KEY_NONE) return nullptr;
    for (Layer& layer : g_layers) if (layer.active && layer.key == key) return &layer;
    return nullptr;
}

void Stop(unsigned key, const char* why)
{
    if (Layer* const layer = Find(key)) {
        char name[64];
        Name(*layer->row, name, sizeof(name));
        Log("stop pattern=%s reason=%s", name, why);
        layer->active = false;
    }
}

void StopAll(const char* why)
{
    int stopped = 0;
    for (Layer& layer : g_layers) if (layer.active) { layer.active = false; ++stopped; }
    if (stopped) Log("stop all=%d reason=%s", stopped, why);
}

// Start `row` as a layer. With `merge` > 0, a repeat of the same pattern that
// started within `merge` seconds joins the running layer (keeping the larger
// scale) instead of stacking: five hits in 50 ms are one hit. Patterns built to
// repeat -- recoil, electricity -- pass 0.
void Play(const RumbleRowK1* row, float scale, int provenance, const char* event,
          float distanceScale, unsigned key = KEY_NONE, float merge = 0.0f)
{
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
    if (!slot) {                            // full: replace the oldest unkeyed layer
        for (Layer& layer : g_layers) {
            if (layer.key == KEY_NONE && (!slot || layer.start < slot->start)) slot = &layer;
        }
        if (!slot) return;
    }
    *slot = { row, g_clock, scale, provenance, key, true };
    char name[64];
    Name(*row, name, sizeof(name));
    const float s = scale * g_settings.strength;
    Log("event=\"%s\" source=%s pattern=%s distanceScale=%.2f strength=%.2f heavy=%.2f light=%.2f duration=%.2fs%s",
        event, PROVENANCE_NAME[provenance], name, distanceScale, g_settings.strength,
        Peak(row->heavyMagnitudes, row->heavyCount) * s, Peak(row->lightMagnitudes, row->lightCount) * s,
        Length(*row), row->loop ? " (loop)" : "");
}

// A looping layer that should exist exactly while `wanted` holds.
void Hold(unsigned key, bool wanted, const RumbleRowK1* row, float scale, int provenance,
          const char* startEvent, const char* stopEvent)
{
    Layer* const layer = Find(key);
    if (wanted && !layer) Play(row, scale, provenance, startEvent, 1.0f, key);
    else if (wanted && layer) layer->scale = scale;
    else if (!wanted && layer) Stop(key, stopEvent);
}

// The hum's pulse timing, on g_clock. A new hum layer (a new start time) starts
// with a pulse; each pulse then draws the gap to the next one afresh.
struct HumPulse { float layerStart; float next; float onUntil; unsigned seed; } g_humPulse = { -1.0f, 0, 0, 0 };

float RandomBetween(float low, float high)
{
    if (g_humPulse.seed == 0) g_humPulse.seed = GetTickCount() | 1u;
    // xorshift32: no shared CRT state, and quality is irrelevant at this scale.
    unsigned x = g_humPulse.seed;
    x ^= x << 13; x ^= x >> 17; x ^= x << 5;
    g_humPulse.seed = x;
    return low + (high - low) * static_cast<float>(x % 10001u) / 10000.0f;
}

// Is the pulsed hum in the silent part of its cycle right now?
bool HumGatedOff(const Layer& layer)
{
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

void Mix(float& heavy, float& light)
{
    heavy = 0.0f;
    light = 0.0f;
    for (Layer& layer : g_layers) {
        if (!layer.active) continue;
        const RumbleRowK1& r = *layer.row;
        const float t = g_clock - layer.start;
        bool doneA = true, doneB = true;
        const float a = Evaluate(r.heavyMagnitudes, r.heavyTimes, r.heavyCount, t, r.loop != 0, doneA) * layer.scale;
        float b = Evaluate(r.lightMagnitudes, r.lightTimes, r.lightCount, t, r.loop != 0, doneB) * layer.scale;
        // The hum's pulse gates BioWare's row rather than replacing it.
        // LightSaberOn has no heavy motor, so only the light output is gated.
        if (layer.key == KEY_HUM && HumGatedOff(layer)) b = 0.0f;
        if (a > heavy) heavy = a;
        if (b > light) light = b;
        if (doneA && doneB) layer.active = false;
    }
}

// ------------------------------------------------------------ the engine

constexpr std::uintptr_t K1_EXO_INPUT            = 0x007A39E4;  // CExoInput*
constexpr std::uintptr_t K1_RULES                = 0x007A3A28;  // CSWRules*
constexpr std::uintptr_t K1_GET_PLAYER_CREATURE  = 0x005ED540;  // CClientExoApp::GetPlayerCreature
constexpr std::uintptr_t K1_GET_ITEM_BY_ID       = 0x005ED5A0;  // CClientExoApp::GetItemByGameObjectID
constexpr std::uintptr_t K1_GET_SERVER_CREATURE  = 0x0060FB20;  // CSWCCreature::GetServerCreature
constexpr std::uintptr_t K1_GET_EQUIPPED_ITEM_ID = 0x0060CA80;  // CSWCCreature::GetEquippedItemID
constexpr std::uintptr_t K1_STRING_FROM_TEXT     = 0x005E5A90;  // CExoString::CExoString(char const*)
constexpr std::uintptr_t K1_STRING_FROM_INT      = 0x005E5BC0;  // CExoString::CExoString(int)
constexpr std::uintptr_t K1_STRING_FREE          = 0x005E5C20;  // CExoString::~CExoString
constexpr std::uintptr_t K1_2DA_INT_BY_ROW       = 0x00413660;  // C2DA::GetINTEntry(int, CExoString const&, int*)
constexpr std::uintptr_t K1_2DA_FLOAT_BY_ROW     = 0x00413430;  // C2DA::GetFLOATEntry(int, ...)
constexpr std::uintptr_t K1_2DA_INT_BY_LABEL     = 0x00414110;  // C2DA::GetINTEntry(CExoString const&, ...)
constexpr std::uintptr_t K1_2DA_FLOAT_BY_LABEL   = 0x00413FA0;  // C2DA::GetFLOATEntry(CExoString const&, ...)
constexpr std::uintptr_t K1_FADE_OBSCURING       = 0x0062DED0;  // CGuiInGame::IsGlobalFadeObscuring
constexpr std::uintptr_t K1_FADING               = 0x0062AC60;  // CGuiInGame::IsGlobalFading
constexpr std::uintptr_t K1_LOAD_SCREEN_EXISTS   = 0x005F2AE0;  // CClientExoAppInternal::LoadScreenExists
constexpr std::uintptr_t K1_GET_IN_GAME_GUI      = 0x005ED690;  // CClientExoApp::GetInGameGui
constexpr std::size_t    K1_GUI_SOUND_LISTENER   = 0xB4;        // non-zero: the cutoff test uses the sound listener (0x005FBB46)
constexpr std::size_t    K1_INTERNAL_IN_GAME_GUI = 0x40;        // UpdateRumble reads it at 0x005F7539
constexpr std::size_t    K1_INTERNAL_RUMBLE_OFF  = 0x288;       // UpdateRumble's first bail, 0x005F752B
constexpr std::size_t    K1_OBJECT_ID            = 0x04;        // CGameObject::id
constexpr std::size_t    K1_OBJECT_POSITION      = 0x24;        // CSWCObject::position
constexpr std::size_t    K1_OBJECT_VFX_LIST      = 0x6C;        // CSWCObject::vis_effects
constexpr std::size_t    K1_VFX_ON_OBJECT_ID     = 0xC4;        // word, read by StartVisualEffect at 0x006A6528
constexpr std::size_t    K1_ITEM_BASE_ITEM       = 0x0C;        // read by CSWItem::GetBaseItem at 0x005B4790
constexpr std::size_t    K1_ITEM_OBJECT_ID       = 0x14;        // compared with GetEquippedItemID at 0x00646BD2
constexpr std::size_t    K1_ITEM_OWNER           = 0x160;       // read by ResolveCreaturePoweredAnimations at 0x00646BA8
constexpr int            K1_SLOT_MAIN_HAND       = 0x10;
constexpr int            K1_SLOT_OFF_HAND        = 0x20;
constexpr int            K1_CLASS_PCGUI          = 2;           // menus; see K1NativeJoystick.cpp
constexpr std::uint32_t  K1_OBJECT_INVALID       = 0x7F000000;

struct ExoString { char* text; int length; };
using ThisIntFn    = int(__thiscall*)(void*);
using ThisPtrFn    = void*(__thiscall*)(void*);
using ItemByIdFn   = void*(__thiscall*)(void*, std::uint32_t);
using SlotIdFn     = std::uint32_t(__thiscall*)(void*, int);
using HitPointsFn  = short(__thiscall*)(void*, int);
using StrTextFn    = void*(__thiscall*)(ExoString*, const char*);
using StrIntFn     = void*(__thiscall*)(ExoString*, int);
using StrFreeFn    = void(__thiscall*)(ExoString*);
using IntRowFn     = int(__thiscall*)(void*, int, ExoString*, int*);
using FloatRowFn   = int(__thiscall*)(void*, int, ExoString*, float*);
using IntLabelFn   = int(__thiscall*)(void*, ExoString*, ExoString*, int*);
using FloatLabelFn = int(__thiscall*)(void*, ExoString*, ExoString*, float*);

void* PlayerCreature()
{
    void* const app = ClientExoAppK1();
    if (!LooksLikePointerK1(app)) return nullptr;
    void* const creature = Fn<ThisPtrFn>(K1_GET_PLAYER_CREATURE)(app);
    return IsReadableK1(creature, 0x250) ? creature : nullptr;
}

std::uint32_t IdOf(const void* object) { return At<std::uint32_t>(object, K1_OBJECT_ID); }

bool PositionOf(const void* object, float out[3])
{
    if (!IsReadableK1(object, K1_OBJECT_POSITION + 12)) return false;
    std::memcpy(out, reinterpret_cast<const std::uint8_t*>(object) + K1_OBJECT_POSITION, 12);
    return true;
}

float Distance(const float a[3], const float b[3])
{
    const float x = a[0] - b[0], y = a[1] - b[1], z = a[2] - b[2];
    return std::sqrt(x * x + y * y + z * z);
}

// Full authored strength near the source, then a smooth fade to nothing at the
// 2DA's RumbleCutOff -- the same distance at which vanilla stops playing it at
// all. The full-strength radius is a quarter of the cutoff, never under 2 m:
// Force Push and Choke have a cutoff of 2 and land on the TARGET, and a push at
// an enemy 1.8 m away is as close as melee gets, so it plays as vanilla does.
float Falloff(float distance, float cutoff)
{
    if (cutoff <= 0.0f) return 1.0f;
    if (distance >= cutoff) return 0.0f;
    float inner = cutoff * 0.25f;
    if (inner < 2.0f) inner = 2.0f;
    if (inner >= cutoff || distance <= inner) return 1.0f;
    const float u = (distance - inner) / (cutoff - inner);
    return 1.0f - u * u * (3.0f - 2.0f * u);
}

// The lookups LookUpAndPerformRumbleWithCutOff makes (0x005FB9A6-0x005FBAF9),
// through the same accessors: category 0 is footstepsounds.2da by row number,
// category 1 is visualeffects.2da by row label, which is the VFX id.
bool LookUpRumble(int category, int row, int& pattern, float& cutoff)
{
    void* const rules = *reinterpret_cast<void**>(K1_RULES);
    if (!IsReadableK1(rules, 0xBC)) return false;
    void* const tables = At<void*>(rules, 0xB8);
    if (!IsReadableK1(tables, 0x8C)) return false;
    void* const table = At<void*>(tables, category == 0 ? 0x58 : 0x88);
    if (!LooksLikePointerK1(table)) return false;
    ExoString patternColumn{}, cutoffColumn{}, label{};
    Fn<StrTextFn>(K1_STRING_FROM_TEXT)(&patternColumn, "RumblePattern");
    Fn<StrTextFn>(K1_STRING_FROM_TEXT)(&cutoffColumn, "RumbleCutOff");
    bool found;
    cutoff = 10.0f;                         // the engine's default
    if (category == 0) {
        found = Fn<IntRowFn>(K1_2DA_INT_BY_ROW)(table, row, &patternColumn, &pattern) != 0;
        if (found) Fn<FloatRowFn>(K1_2DA_FLOAT_BY_ROW)(table, row, &cutoffColumn, &cutoff);
    } else {
        Fn<StrIntFn>(K1_STRING_FROM_INT)(&label, row);
        found = Fn<IntLabelFn>(K1_2DA_INT_BY_LABEL)(table, &label, &patternColumn, &pattern) != 0;
        if (found) Fn<FloatLabelFn>(K1_2DA_FLOAT_BY_LABEL)(table, &label, &cutoffColumn, &cutoff);
        Fn<StrFreeFn>(K1_STRING_FREE)(&label);
    }
    Fn<StrFreeFn>(K1_STRING_FREE)(&cutoffColumn);
    Fn<StrFreeFn>(K1_STRING_FREE)(&patternColumn);
    return found && pattern >= 0 && pattern < K1_RUMBLE_PATTERN_COUNT;
}

// The VFX ids `object` carries right now, at most `capacity` of them. Walks
// CSWCObject::vis_effects, a CExoLinkedList of {prev, next, data} nodes.
int VfxOn(void* object, int* ids, int capacity)
{
    int count = 0;
    void* const list = At<void*>(object, K1_OBJECT_VFX_LIST);
    if (!IsReadableK1(list, 4)) return 0;
    void* const internal = At<void*>(list, 0);
    if (!IsReadableK1(internal, 12)) return 0;
    void* node = At<void*>(internal, 0);
    for (int guard = 0; node && guard < 64 && count < capacity; ++guard) {
        if (!IsReadableK1(node, 12)) break;
        void* const effect = At<void*>(node, 8);
        if (IsReadableK1(effect, K1_VFX_ON_OBJECT_ID + 2)) {
            ids[count++] = At<std::uint16_t>(effect, K1_VFX_ON_OBJECT_ID);
        }
        node = At<void*>(node, 4);
    }
    return count;
}

bool AnyOf(const int* have, int haveCount, const int* want, int wantCount)
{
    for (int i = 0; i < haveCount; ++i) {
        for (int j = 0; j < wantCount; ++j) if (have[i] == want[j]) return true;
    }
    return false;
}

int BaseItemOf(std::uint32_t itemId)
{
    void* const app = ClientExoAppK1();
    if (!LooksLikePointerK1(app) || itemId == 0 || itemId == K1_OBJECT_INVALID) return -1;
    void* const item = Fn<ItemByIdFn>(K1_GET_ITEM_BY_ID)(app, itemId);
    return IsReadableK1(item, K1_ITEM_BASE_ITEM + 4) ? At<int>(item, K1_ITEM_BASE_ITEM) : -1;
}

// baseitems.2da rows. Sabers: 8 Lightsaber, 9 Double-Bladed, 10 Short.
// Recoil by weaponwield: 4 pistols, 5 rifles, 6 repeaters.
bool IsSaber(int base) { return base == 8 || base == 9 || base == 10; }
int RecoilFor(int base)
{
    switch (base) {
    case 12: case 13: case 14: case 15: case 16: case 17: return P_PISTOL;
    case 18: case 19: case 20: case 21: case 22: case 77: return P_RIFLE;
    case 23: case 24: return P_REPEATER;
    default: return 0;
    }
}

// CExoInput's rumble pause (PauseRumble 0x005DF570, UnpauseRumble 0x005DF580),
// set by the combat and auto pauses and by the autosave.
bool RumblePaused()
{
    void* const input = *reinterpret_cast<void**>(K1_EXO_INPUT);
    if (!IsReadableK1(input, 8)) return false;
    void* const internal = At<void*>(input, 4);
    if (!IsReadableK1(internal, 0x144)) return false;
    void* const state = At<void*>(internal, 0x140);
    return IsReadableK1(state, 0x14) && At<int>(state, 0x10) != 0;
}

// UpdateRumble's own bails (0x005F7503-0x005F7562): no frame time, rumble
// switched off, a fade covering the screen or running, or a load screen. On
// those frames the engine neither advances its patterns nor sends anything.
bool EngineSilent(void* owner, float dt)
{
    if (!(dt > 0.0f) || !IsReadableK1(owner, K1_INTERNAL_RUMBLE_OFF + 4)) return true;
    if (At<int>(owner, K1_INTERNAL_RUMBLE_OFF) != 0) return true;
    void* const gui = At<void*>(owner, K1_INTERNAL_IN_GAME_GUI);
    if (!LooksLikePointerK1(gui)) return true;
    if (Fn<ThisIntFn>(K1_FADE_OBSCURING)(gui) || Fn<ThisIntFn>(K1_FADING)(gui)) return true;
    return Fn<ThisIntFn>(K1_LOAD_SCREEN_EXISTS)(owner) != 0;
}

// ------------------------------------------------------------ Enhanced rules

// VFX rows KMRP gives rumble to, in Enhanced mode, and only where BioWare's row
// has none -- a row BioWare authored always keeps its own pattern. A rule can
// fire three ways, tried in order:
//   onPlayer  the VFX is on the controlled character (the engine passes the
//             object's own position, so this is pointer identity, not distance);
//   onTarget  the VFX is on the controlled character's current target -- the
//             player's own attack or power landing;
//   world     anywhere within `cutoff` metres, faded by Falloff.
// 0 means "not this way".
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

// Set by the positional observer for the play the engine makes a moment later.
// `handled`: Enhanced has already played the row itself, so the engine's own
// play of that same pattern is swallowed.
struct Positional { bool valid; int category; int row; int pattern; float distance; float cutoff; bool handled; } g_positional = {};

struct Health {
    std::uint32_t creature;
    int   hp;
    bool  valid;
    bool  dead;
    float lastHit;                           // on g_clock
    int   burst;                             // damage merged into the current hit
} g_health = {};

struct Saber { std::uint32_t item; std::uint32_t owner; bool on; };
Saber g_sabers[32] = {};

std::uint32_t g_controlled = 0;
bool g_wasMuted = false;
int  g_shotsLogged = 0;

Saber* SaberSlot(std::uint32_t item)
{
    for (Saber& s : g_sabers) if (s.item == item) return &s;
    for (Saber& s : g_sabers) if (s.item == 0) { s = { item, 0, false }; return &s; }
    // Full: reuse a slot that is not the controlled character's.
    for (Saber& s : g_sabers) if (s.owner != g_controlled) { s = { item, 0, false }; return &s; }
    return nullptr;
}

// Damage as a share of maximum health through a bounded curve: a scratch still
// registers, three tenths of the bar is the ceiling, and nothing exceeds 0.8.
// (The floor was 0.12 until the first combat test, where hits of 5-9% of the
// bar produced 17-26% on the heavy motor and were not felt.)
float DamageIntensity(int damage, int maximum)
{
    const float ratio = maximum > 0 ? static_cast<float>(damage) / maximum : 0.0f;
    float u = ratio / 0.3f;
    if (u > 1.0f) u = 1.0f;
    return 0.30f + 0.50f * u * u * (3.0f - 2.0f * u);
}

void PollHealth(void* creature, bool live)
{
    void* const server = Fn<ThisPtrFn>(K1_GET_SERVER_CREATURE)(creature);
    if (!IsReadableK1(server, 4)) return;
    void** const vtable = At<void**>(server, 0);
    if (!IsReadableK1(vtable, 0xA0)) return;
    // The HUD's own reads (0x006879D0, 0x006879E0): current hit points are slot
    // 0x9C called with 0, maximum hit points slot 0x98 called with 1.
    const int hp = Fn<HitPointsFn>(reinterpret_cast<std::uintptr_t>(vtable[0x9C / 4]))(server, 0);
    const int maximum = Fn<HitPointsFn>(reinterpret_cast<std::uintptr_t>(vtable[0x98 / 4]))(server, 1);
    const std::uint32_t id = IdOf(creature);
    if (!g_health.valid || g_health.creature != id) {
        g_health = { id, hp, true, hp <= 0, -1.0f, 0 };
        return;                              // a new character: a baseline, not a hit
    }
    // Not once dead: hit points can go on falling below zero, and the death
    // impact is the last thing felt.
    if (live && hp < g_health.hp && !g_health.dead && Enhanced()) {
        const int damage = g_health.hp - hp;
        // Damage inside 50 ms of the last hit joins that hit.
        if (g_health.lastHit >= 0.0f && g_clock - g_health.lastHit < 0.05f) {
            g_health.burst += damage;
        } else {
            g_health.burst = damage;
            g_health.lastHit = g_clock;
        }
        const bool heavy = maximum > 0 && g_health.burst * 5 >= maximum;
        char event[64];
        sprintf_s(event, "PlayerDamaged %d of %d", g_health.burst, maximum);
        Play(Kmrp(heavy ? P_DAMAGE_HEAVY : P_DAMAGE), DamageIntensity(g_health.burst, maximum),
             ENHANCED, event, 1.0f, KEY_NONE, 0.05f);
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

// The hum is state, not an event: it exists while the controlled character has
// a lit blade in hand, and is re-derived every frame, so retracting, unequipping,
// switching character, dying or loading all end it without a special case each.
void UpdateSabers(void* creature)
{
    const std::uint32_t id = IdOf(creature);
    const std::uint32_t main = Fn<SlotIdFn>(K1_GET_EQUIPPED_ITEM_ID)(creature, K1_SLOT_MAIN_HAND);
    const std::uint32_t off = Fn<SlotIdFn>(K1_GET_EQUIPPED_ITEM_ID)(creature, K1_SLOT_OFF_HAND);
    int lit = 0;
    for (const Saber& s : g_sabers) {
        if (s.item && s.on && s.owner == id && (s.item == main || s.item == off)) ++lit;
    }
    // One blade is BioWare's hum at SaberHum percent; a second adds a little,
    // never double. SaberHum=0 turns it off. Hold re-applies the scale every
    // frame, so an edit to the setting is felt within a second.
    const float scale = (lit > 1 ? 1.15f : 1.0f) * g_settings.hum;
    Hold(KEY_HUM, lit > 0 && !g_health.dead && scale > 0.0f, BioWare(0), scale, RESTORED,
         lit > 1 ? "LightsaberHum dual" : "LightsaberHum", "LightsaberHumEnded");
}

// Whirlwind, electricity and drain are states too: each loop exists exactly
// while its VFX is on the controlled character, so it ends the frame the effect
// does, however the effect ends.
void UpdatePersistent(void* creature)
{
    int vfx[64];
    const int n = g_health.dead ? 0 : VfxOn(creature, vfx, 64);
    Hold(KEY_WHIRLWIND, AnyOf(vfx, n, WHIRLWIND_VFX, KMRP_COUNT_OF(WHIRLWIND_VFX)),
         BioWare(21), 1.0f, RESTORED, "WhirlwindOnPlayer", "WhirlwindEnded");
    Hold(KEY_ELECTRIC, AnyOf(vfx, n, ELECTRIC_VFX, KMRP_COUNT_OF(ELECTRIC_VFX)),
         Kmrp(P_ELECTRIC_LOOP), 1.0f, ENHANCED, "ElectricOnPlayer", "ElectricEnded");
    Hold(KEY_DRAIN, AnyOf(vfx, n, DRAIN_VFX, KMRP_COUNT_OF(DRAIN_VFX)),
         Kmrp(P_DRAIN_LOOP), 1.0f, ENHANCED, "DrainOnPlayer", "DrainEnded");
}

void StopStates(const char* why)
{
    Stop(KEY_HUM, why);
    Stop(KEY_WHIRLWIND, why);
    Stop(KEY_ELECTRIC, why);
    Stop(KEY_DRAIN, why);
}

// Every positional lookup that has a BioWare pattern, in range or not, with
// where the engine would measure from. Up to 300 lines a session.
void LogPositional(int category, int row, int pattern, float cutoff, float reach, float distance)
{
    static int logged = 0;
    if (!g_settings.debug || logged >= 300) return;
    ++logged;
    bool camera = false;
    void* const app = ClientExoAppK1();
    if (LooksLikePointerK1(app)) {
        void* const gui = Fn<ThisPtrFn>(K1_GET_IN_GAME_GUI)(app);
        camera = IsReadableK1(gui, K1_GUI_SOUND_LISTENER + 4) && At<int>(gui, K1_GUI_SOUND_LISTENER) != 0;
    }
    Log("positional %s %d pattern=BioWare %d cutoff=%.1fm reach=%.1fm player=%.1fm engineMeasuresFrom=%s",
        category == 0 ? "footstep" : "VFX", row, pattern, cutoff, reach, distance,
        camera ? "soundListener" : "player");
}

// What the motors are sent, frame by frame, while any one-shot pattern plays --
// the check that a pattern reaches the pad at the strength and length intended.
// Up to 1500 lines a session.
void LogOutput(float heavy, float light, float dt, bool muted)
{
    static int logged = 0;
    if (!g_settings.debug || logged >= 1500) return;
    bool transient = false;
    for (const Layer& layer : g_layers) if (layer.active && layer.key == KEY_NONE) { transient = true; break; }
    if (!transient) return;
    ++logged;
    Log("out heavy=%.3f light=%.3f dt=%.3f%s", muted ? 0.0f : heavy * g_settings.strength,
        muted ? 0.0f : light * g_settings.strength, dt, muted ? " muted" : "");
}

}  // namespace

// ------------------------------------------------------------ engine hooks

// CClientExoAppInternal::PlayRumblePattern at 0x005FB49F, its index test, with
// the index in EBP. Every rumble the engine starts -- a script's
// PlayRumblePattern, a footstep, a VFX -- arrives here, and the mixer plays it
// instead of the engine's instance list. Returning 1 takes the consumed exit to
// 0x005FB536, which returns 0 as the shipped PC game always has (its table was
// empty); the only caller that reads it, the script command, pushes it as the
// script's result.
extern "C" int __cdecl NativeRumblePlayK1(void* internal, int index)
{
    (void)internal;
    LoadSettings();
    const RumbleRowK1* const row = BioWare(index);
    if (!row) return 1;
    // As the engine: a looping row already playing is not started again
    // (0x005FB4BB tests the row's loop flag, 0x005FB4D0 searches the queue);
    // a one-shot row overlaps its running copy freely.
    if (row->loop) {
        for (const Layer& layer : g_layers) {
            if (layer.active && layer.provenance == ORIGINAL && layer.row == row) return 1;
        }
    }
    char event[64];
    if (g_positional.valid && g_positional.pattern == index) {
        g_positional.valid = false;
        // Enhanced played this footstep or VFX already, from the observer.
        if (g_positional.handled) return 1;
        // Original: within the cutoff, gated by the engine exactly as vanilla.
        sprintf_s(event, "%s %d at %.1fm", g_positional.category == 0 ? "Footstep" : "VFX",
                  g_positional.row, g_positional.distance);
    } else {
        sprintf_s(event, "Script");
    }
    Play(row, 1.0f, ORIGINAL, event, 1.0f);
    return 1;
}

// CClientExoAppInternal::StopRumblePattern at its entry; `argument` points at the
// index. The engine's list is empty, so stopping is the mixer's job.
extern "C" void __cdecl NativeRumbleStopK1(void* internal, int* argument)
{
    (void)internal;
    if (!IsReadableK1(argument, 4)) return;
    const int index = *argument;
    int stopped = 0;
    for (Layer& layer : g_layers) {
        if (layer.active && layer.provenance == ORIGINAL && layer.row->index == index) {
            layer.active = false;
            ++stopped;
        }
    }
    if (stopped) Log("stop pattern=BioWare %d reason=script", index);
}

// LookUpAndPerformRumbleWithCutOff at 0x005FB98E, with its frame in EBP:
// [ebp+8] the row, [ebp+0xC] the category byte, [ebp+0x10] the position. An
// observer -- the engine carries on either way. Where BioWare's row has a
// pattern, this leaves the context NativeRumblePlayK1 reads a moment later
// (the engine calls it from 0x005FBBC4, synchronously); where it has none,
// Enhanced mode applies KMRP's rules.
extern "C" void __cdecl NativeRumbleCutoffK1(std::uint8_t* frame)
{
    g_positional.valid = false;
    if (!IsReadableK1(frame + 8, 12)) return;
    const int row = At<int>(frame, 8);
    const int category = At<std::uint8_t>(frame, 0xC);
    const float* const position = At<const float*>(frame, 0x10);
    if ((category != 0 && category != 1) || !IsReadableK1(position, 12)) return;
    LoadSettings();
    void* const creature = PlayerCreature();
    float listener[3];
    if (!creature || !PositionOf(creature, listener)) return;
    const float distance = Distance(listener, position);
    int pattern = -1;
    float cutoff = 10.0f;
    if (LookUpRumble(category, row, pattern, cutoff)) {
        // Enhanced reach: three times BioWare's cutoff when that is under 10 m
        // (grenades and Force Wave 5 -> 15 m, Push and Choke 2 -> 6 m), BioWare's
        // own beyond (Stomp 20, screen shake 30). A thrown grenade lands well past
        // 5 m, and the engine measures from the sound listener -- the camera,
        // behind the player -- whenever the in-game GUI's +0xB4 is set
        // (0x005FBB46), so vanilla often plays nothing for one. The first combat
        // test logged not one positional rumble.
        const float reach = cutoff < 10.0f ? cutoff * 3.0f : cutoff;
        LogPositional(category, row, pattern, cutoff, reach, distance);
        if (!Enhanced()) {
            // Original: the engine decides, from its own listener, as vanilla.
            if (distance * distance < cutoff * cutoff) {
                g_positional = { true, category, row, pattern, distance, cutoff, false };
            }
            return;
        }
        g_positional = { true, category, row, pattern, distance, cutoff, true };
        const float scale = Falloff(distance, reach);
        if (scale <= 0.0f) return;
        char event[64];
        sprintf_s(event, "%s %d at %.1fm", category == 0 ? "Footstep" : "VFX", row, distance);
        // Inside BioWare's cutoff it is BioWare's rumble; past it, KMRP's reach.
        Play(BioWare(pattern), scale, distance < cutoff ? ORIGINAL : ENHANCED, event, scale);
        return;
    }
    if (category != 1 || !Enhanced()) return;
    for (const Rule& rule : KMRP_VFX_RULES) {
        if (rule.vfx != row) continue;
        const std::uint8_t* const object = reinterpret_cast<const std::uint8_t*>(position) - K1_OBJECT_POSITION;
        const bool onPlayer = object == creature;
        const std::uint32_t target = CurrentTargetK1();
        const bool onTarget = !onPlayer && target != 0 && target != K1_OBJECT_INVALID &&
                              IsReadableK1(object, 8) && IdOf(object) == target;
        char event[96];
        if (onPlayer && rule.onPlayer) {
            sprintf_s(event, "VFX %d %s on player", row, rule.label);
            Play(Pattern(rule.onPlayer), 1.0f, ENHANCED, event, 1.0f, KEY_NONE, 0.04f);
        } else if (onTarget && rule.onTarget) {
            sprintf_s(event, "VFX %d %s on target", row, rule.label);
            Play(Pattern(rule.onTarget), 1.0f, ENHANCED, event, 1.0f, KEY_NONE, 0.04f);
        } else if (rule.world) {
            const float scale = Falloff(distance, rule.cutoff);
            sprintf_s(event, "VFX %d %s at %.1fm", row, rule.label, distance);
            if (scale > 0.0f) Play(Pattern(rule.world), scale, ENHANCED, event, scale, KEY_NONE, 0.04f);
        }
        return;
    }
}

// CSWCItem::ResolveCreaturePoweredAnimations at its entry: `item` is the item,
// `argument` points at the power flag. PowerItem (0x00647130) calls it with the
// state it has actually decided on -- including its forced "off" -- whenever any
// blade lights or goes out: combat (SetCombatState), weapon switching, the
// flourish, SetLightsaberPowered, equipping.
extern "C" void __cdecl NativeSaberPowerK1(void* item, int* argument)
{
    if (!IsReadableK1(item, K1_ITEM_OWNER + 4) || !IsReadableK1(argument, 4)) return;
    if (!IsSaber(At<int>(item, K1_ITEM_BASE_ITEM))) return;
    const bool on = *argument != 0;
    const std::uint32_t id = At<std::uint32_t>(item, K1_ITEM_OBJECT_ID);
    const std::uint32_t owner = At<std::uint32_t>(item, K1_ITEM_OWNER);
    Saber* const saber = SaberSlot(id);
    if (!saber) return;
    const bool was = saber->on && saber->owner == owner;
    saber->owner = owner;
    saber->on = on;
    if (was == on || g_controlled == 0 || owner != g_controlled) return;
    LoadSettings();
    // Both blades of a pair light together: one pulse, not two.
    Play(Kmrp(on ? P_SABER_IGNITE : P_SABER_RETRACT), 1.0f, ENHANCED,
         on ? "LightsaberIgnite" : "LightsaberRetract", 1.0f, KEY_NONE, 0.15f);
}

// CSWCCreature::ShowLightSaberContactVisual at its entry, reached from the
// animation event "Contact" (HitContactEvent, 0x00610E90; registered by
// CSWCCreature::RegisterCallbacks at 0x0061AC49): `creature` is the wielder. It
// puts VFX 4011, VFX_COM_SPARKS_PARRY_METAL, on the blade's LightSaberHook node
// -- blade meeting blade, so this is a clash, merged with the parry that
// usually comes with it. Until the first combat test it played the saber HIT,
// which is why no hit was ever felt: blows landing are the "hit" event, below.
extern "C" void __cdecl NativeSaberContactK1(void* creature)
{
    if (g_controlled == 0 || !IsReadableK1(creature, 8) || IdOf(creature) != g_controlled) return;
    LoadSettings();
    Play(Kmrp(P_SABER_CLASH), 1.0f, ENHANCED, "LightsaberContact", 1.0f, KEY_NONE, 0.2f);
}

// HitEvent (0x00617EB0), the animation event "hit": the moment an attack's blow
// lands or fails. `slot` points at its third argument, the attack record, read
// at 0x00617ECC: +0x04 the attacker's id, +0x14 the target's, +0x0C the result,
// +0x20 set when the engine is to skip it (0x00617F26). Results 1, 2, 3 and 5
// take the engine's hit branch (0x0061801C: the hit sound, the target's
// flinch); 4 and 8 its parry animation instead. So this fires when, and only
// when, the controlled character's blow connects. Ranged weapons are left to
// the recoil.
extern "C" void __cdecl NativeMeleeHitK1(std::uint8_t** slot)
{
    if (g_controlled == 0 || !IsReadableK1(slot, 4)) return;
    const std::uint8_t* const attack = *slot;
    if (!IsReadableK1(attack, 0x24)) return;
    if (At<std::uint32_t>(attack, 4) != g_controlled || At<int>(attack, 0x20) != 0) return;
    const int result = attack[0xC];
    if (result != 1 && result != 2 && result != 3 && result != 5) return;
    void* const creature = PlayerCreature();
    if (!creature) return;
    const int base = BaseItemOf(Fn<SlotIdFn>(K1_GET_EQUIPPED_ITEM_ID)(creature, K1_SLOT_MAIN_HAND));
    if (RecoilFor(base)) return;
    LoadSettings();
    char event[48];
    sprintf_s(event, "%s result %d", IsSaber(base) ? "LightsaberHit" : "MeleeHit", result);
    Play(Kmrp(IsSaber(base) ? P_SABER_HIT : P_MELEE_HIT), 1.0f, ENHANCED, event, 1.0f, KEY_NONE, 0.08f);
}

// CSWCObject::AnimationParry at its entry: `object` is the one parrying. Felt when
// the controlled character parries, or when its target parries it.
extern "C" void __cdecl NativeParryK1(void* object)
{
    if (g_controlled == 0 || !IsReadableK1(object, 8)) return;
    const std::uint32_t id = IdOf(object);
    if (id != g_controlled && id != CurrentTargetK1()) return;
    LoadSettings();
    Play(Kmrp(P_SABER_CLASH), 1.0f, ENHANCED, id == g_controlled ? "PlayerParried" : "TargetParried",
         1.0f, KEY_NONE, 0.2f);
}

// CSWCProjectile::CreateMuzzleFlash at its entry: a shot leaving a weapon. No
// owner field on the projectile has been identified, so a shot counts as the
// controlled character's when it starts within 1.6 m of them while they hold a
// ranged weapon. The first 40 shots are logged with their distance either way,
// so the threshold can be checked against a real run.
extern "C" void __cdecl NativeMuzzleFlashK1(void* projectile)
{
    if (g_controlled == 0) return;
    void* const creature = PlayerCreature();
    float shot[3], player[3];
    if (!creature || !PositionOf(projectile, shot) || !PositionOf(creature, player)) return;
    LoadSettings();
    const float distance = Distance(shot, player);
    const std::uint32_t main = Fn<SlotIdFn>(K1_GET_EQUIPPED_ITEM_ID)(creature, K1_SLOT_MAIN_HAND);
    const int base = BaseItemOf(main);
    const int recoil = RecoilFor(base);
    if (g_shotsLogged < 40) {
        ++g_shotsLogged;
        Log("muzzle flash at %.2fm, player weapon baseitem %d%s", distance, base,
            distance <= 1.6f && recoil ? " -> recoil" : "");
    }
    if (distance > 1.6f || !recoil) return;
    Play(Kmrp(recoil), 1.0f, ENHANCED, "PlayerFired", 1.0f);
}

// ------------------------------------------------------------ once per frame

void KmrpRumbleTickK1(void* owner, float dt, float engineHeavy, float engineLight,
                      float& heavy, float& light)
{
    LoadSettings();
    heavy = 0.0f;
    light = 0.0f;
    g_positional.valid = false;              // context never outlives its own call
    void* const creature = PlayerCreature();
    if (!creature) {
        // Loading, the main menu, a module change: nothing carries over.
        if (g_controlled) StopAll("no controlled character");
        g_controlled = 0;
        g_health.valid = false;
        return;
    }
    const std::uint32_t id = IdOf(creature);
    if (id != g_controlled) {
        if (g_controlled) Log("controlled character changed");
        g_controlled = id;
    }
    // Time runs exactly when the engine's own patterns would run: it stops only
    // on UpdateRumble's bails (fades, load screens, no frame time). The rumble
    // pause and the menus mute the motors without stopping time, as they do the
    // engine's -- SetRumble is still called, UpdateRumble still advances -- so a
    // scripted tremor that outlasts a pause has finished when the pause ends,
    // as vanilla, and the hum, being state, is simply felt again.
    const bool frozen = EngineSilent(owner, dt);
    if (!frozen) g_clock += dt;
    const bool muted = frozen || RumblePaused() || InputClassK1() == K1_CLASS_PCGUI;
    if (muted != g_wasMuted) Log(muted ? "muted" : "unmuted");
    g_wasMuted = muted;
    PollHealth(creature, !muted);
    if (Enhanced()) {
        UpdateSabers(creature);
        UpdatePersistent(creature);
    } else {
        StopStates("mode is not Enhanced");
    }
    Mix(heavy, light);                       // also retires finished layers while muted
    LogOutput(heavy, light, dt, muted);
    if (muted || g_settings.mode == MODE_OFF) {
        heavy = 0.0f;
        light = 0.0f;
        return;
    }
    // Whatever the engine mixed itself: nothing, unless the play hook is absent.
    if (engineHeavy > heavy) heavy = engineHeavy;
    if (engineLight > light) light = engineLight;
    heavy *= g_settings.strength;
    light *= g_settings.strength;
    if (heavy > 1.0f) heavy = 1.0f;
    if (light > 1.0f) light = 1.0f;
}

const RumbleRowK1* KmrpBioWareRumbleRowK1(int index)
{
    return BioWare(index);
}
