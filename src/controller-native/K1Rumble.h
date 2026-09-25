// KMRP rumble: BioWare's pattern table, and the mixer every rumble goes through.
// See docs/controller-rumble.md.
#pragma once

// One pattern, in the engine's own envelope format: per motor, `count` keyframes
// of (magnitude, time in seconds), evaluated by linear interpolation. "Heavy" is
// envelope A, the left, low-frequency motor; "light" is envelope B, the right one.
struct RumbleRowK1 {
    int          index;             // BioWare 0-21; KMRP patterns are 100 and up
    const char*  label;             // the 2DA label, or KMRP_... for KMRP's own
    int          loop;
    const float* heavyMagnitudes;
    const float* heavyTimes;
    int          heavyCount;
    const float* lightMagnitudes;
    const float* lightTimes;
    int          lightCount;
};

// BioWare's rumble.2da has rows 0-21.
constexpr int K1_RUMBLE_PATTERN_COUNT = 22;

// BioWare's row `index`, or null.
const RumbleRowK1* KmrpBioWareRumbleRowK1(int index);

// Once per frame, from UpdateRumble's SetRumble call. `owner` is UpdateRumble's
// CClientExoAppInternal and `dt` its frame time in seconds. `engineHeavy` and
// `engineLight` are what the engine itself mixed (normally zero, since every
// engine pattern is routed to the mixer instead). Returns the motor strengths to
// send, 0..1 each, with mode, strength, pause and menus already applied.
void KmrpRumbleTickK1(void* owner, float dt, float engineHeavy, float engineLight,
                      float& heavy, float& light);
