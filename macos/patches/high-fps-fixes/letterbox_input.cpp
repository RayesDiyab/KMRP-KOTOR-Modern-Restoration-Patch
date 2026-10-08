/*
  High FPS Fixes for the Steam Aspyr macOS build of KOTOR 1: the dialogue letterbox and the
  movement delay after combat. A port of D3M0's High FPS Fixes 1.0.1 for Windows (MIT); see
  high_fps_fixes.cpp for what a handler can and cannot do here, which is why these two fixes
  are cut as they are.

  The letterbox (CSWGuiDialogLetterbox::Draw, 0x1002443b4; Windows 0x006A77A9 and 0x006A7842):
  a bar moved trunc(extent * 2 * dt) pixels a frame, which truncation makes nothing at a high
  frame rate. Below 1/60 s a frame the step is D3M0's, extent / 30 a sixtieth of a second with
  the fraction carried; at 1/60 s and above it is the game's own arithmetic, unchanged. Windows
  keeps the fraction in the object's fade delay; here it is in a table of this patch's own.

  After combat (CClientExoAppInternal::ProcessInput, 0x1002f8226; Windows 0x00623B54): while the
  leader is still in the combat state the game lets held movement through for one frame in
  every 0.1 s and leaves combat when the control has ramped past 0.25 on that frame, which one
  frame at a high rate is too short for. D3M0's cycle: movement passes for the first 1/60 s of
  every 7/60 s, whatever the frame rate. The timer's reset value marks that cycle
  (1.0 + 7/60 in place of 0.1; the simple hook at 0x1002f9e49).
*/
#include <cstdint>
#include <cstring>

#define HFPS_EXPORT extern "C" __attribute__((visibility("default")))

namespace {

template <typename T> T Read(const void* base, long offset) {
    T value;
    std::memcpy(&value, static_cast<const char*>(base) + offset, sizeof value);
    return value;
}
template <typename T> void Write(void* base, long offset, T value) {
    std::memcpy(static_cast<char*>(base) + offset, &value, sizeof value);
}
std::uint32_t Bits(float value) {
    std::uint32_t bits;
    std::memcpy(&bits, &value, sizeof bits);
    return bits;
}

// ---- Dialogue letterbox (CSWGuiDialogLetterbox::Draw, 0x1002443b4) ----

// One remainder per bar. The Windows patch keeps it in the object at +0x94, which is the
// fade delay there (+0xb8 here); a table keyed by the object leaves the object alone.
struct BarRemainder { void* owner; float remainder; };
BarRemainder g_bars[32];
unsigned g_nextVictim;

float& RemainderFor(void* bar) {
    for (auto& entry : g_bars) if (entry.owner == bar) return entry.remainder;
    for (auto& entry : g_bars) {
        if (!entry.owner) { entry.owner = bar; entry.remainder = 0.0f; return entry.remainder; }
    }
    BarRemainder& entry = g_bars[g_nextVictim];
    g_nextVictim = (g_nextVictim + 1) & 31u;
    entry.owner = bar;
    entry.remainder = 0.0f;
    return entry.remainder;
}

// The distance the bar moves this frame. `extent` is target minus start (negative for the
// lower bar), `dt` the frame's seconds as Draw clamped them (min(dt, 0.5), [rbp-0x14]).
int BarStep(void* bar, int extent, float dt) {
    // cmp dword [dt], 0x3C888889 ; jae original: unsigned on the bits, as the Windows patch.
    if (Bits(dt) >= 0x3C888889u) {
        // The game's own arithmetic (cvtsi2ss, addss, mulss, cvttss2si), in single precision.
        float distance = static_cast<float>(extent);
        distance += distance;
        distance *= dt;
        return static_cast<int>(distance);
    }
    float& remainder = RemainderFor(bar);
    const int referenceStep = extent / 30;
    const float total = static_cast<float>(
        static_cast<double>(referenceStep) * static_cast<double>(dt) * 60.0 +
        static_cast<double>(remainder));
    const int whole = static_cast<int>(total);
    remainder = static_cast<float>(static_cast<double>(total) - static_cast<double>(whole));
    return whole;
}

// ---- Post-combat movement delay (CClientExoAppInternal::ProcessInput, 0x1002f8226) ----

const long kMoveTimer = 0x3f0;          // float, CClientExoAppInternal (Windows +0x2A4)
std::uint32_t g_timerBeforeFrame;       // the timer's bits before this frame's subtraction

// What the game's "timer expired, creature not busy" exit (0x1002f9e4d) does before it
// joins 0x1002f9e63: the two movement inputs, zeroed at 0x1002f9d8c/0x1002f9d9c, are put back.
void RestoreMovementInputs(char* frame) {
    Write<float>(frame, -0x40, Read<float>(frame, -0x2c));
    const float restored[4] = { Read<float>(frame, -0x44), 0.0f, 0.0f, 0.0f };
    std::memcpy(frame - 0x60, restored, sizeof restored);
}

}  // namespace

// 0x100244206 and 0x1002442bb: SetTop and SetBottom start an animation.
HFPS_EXPORT void HfpsLetterboxReset(void* bar) {
    RemainderFor(bar) = 0.0f;
}

// 0x1002444a1: the upper bar grows. Replaces the step and the store of the new height.
HFPS_EXPORT void HfpsLetterboxTopStep(void* bar, char* frame) {
    const int extent = Read<int>(bar, 0x88) - Read<int>(bar, 0x98);
    const int step = BarStep(bar, extent, Read<float>(frame, -0x14));
    Write<int>(frame, -0x1c, Read<int>(bar, 0x14) + step);
}

// 0x1002444e9: the lower bar rises. Replaces the step and the stores of the new y and height.
HFPS_EXPORT void HfpsLetterboxBottomStep(void* bar, char* frame) {
    const int extent = Read<int>(bar, 0x80) - Read<int>(bar, 0x90);
    const int step = BarStep(bar, extent, Read<float>(frame, -0x14));
    Write<int>(frame, -0x24, Read<int>(bar, 0x0c) + step);
    Write<int>(frame, -0x1c, Read<int>(bar, 0x14) - step);
}

// 0x1002f9d43, before the game stores timer - dt: the value the timer had.
HFPS_EXPORT void HfpsPostCombatBefore(void* internal) {
    g_timerBeforeFrame = Read<std::uint32_t>(internal, kMoveTimer);
}

// 0x1002f9da3, in place of `jb 0x1002f9e63 / test eax,eax / je 0x1002f9e4d`.
// Returns 1 to leave through 0x1002f9e63 (consumed_exit_address), 0 to go on to the game's
// re-check at 0x1002f9db1. `busy` is eax: the server creature's field +0x130, or 1.
HFPS_EXPORT int HfpsPostCombatGate(void* internal, char* frame, int busy) {
    const std::int32_t before = static_cast<std::int32_t>(g_timerBeforeFrame);
    const std::int32_t now = Read<std::int32_t>(internal, kMoveTimer);

    if (before <= 0x3F800000) {                 // not the marked 1.0 + 7/60 countdown
        if (now > 0) return 1;                  // still waiting: inputs stay zeroed
        if (busy == 0) { RestoreMovementInputs(frame); return 1; }
        return 0;
    }

    const float dt = Read<float>(frame, -0x48);
    const float half = static_cast<float>(static_cast<double>(dt) * 0.5);
    const float waitEnds = static_cast<float>(static_cast<double>(dt) * 0.5 + 1.0);
    if (now <= static_cast<std::int32_t>(Bits(waitEnds))) {
        Write<std::uint32_t>(internal, kMoveTimer, 0u);
        if (busy == 0) { RestoreMovementInputs(frame); return 1; }
        return 0;
    }
    const float moveEnds = static_cast<float>(
        static_cast<double>(half) + static_cast<double>(1.10000002384185791015625f));
    if (now > static_cast<std::int32_t>(Bits(moveEnds))) {
        RestoreMovementInputs(frame);           // the first 1/60 s: movement passes
        return 1;
    }
    return 1;                                   // the next 0.1 s: inputs stay zeroed
}
