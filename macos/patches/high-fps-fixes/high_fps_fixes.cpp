/*
  High FPS Fixes for the Steam Aspyr macOS build of KOTOR 1.

  A port of D3M0's High FPS Fixes 1.0.1 for Windows (MIT;
  https://github.com/gnw-d3m0/D3M0s-KPatches, HighFpsFixes/src/dll/src/HighFpsFixes.cpp), whose
  logic and constants these handlers keep. The engine does a number of things once a frame that
  assume 30 to 60 frames a second; each handler below makes one of them go by time instead.

  The Mac game is the same engine built for x86_64 with SSE, so every site is another
  instruction than on Windows and several fixes are cut differently: a handler of KotOR Patch
  Manager's x86_64 wrapper can leave a value in rax and write memory, and cannot set another
  register, an xmm register or the flags. Where Windows' handler set a register, the handler
  here writes the stack slot or object field the game reads next, or returns in rax. Each
  handler says which Windows handler it is and what differs. x87 long doubles are doubles here,
  and fprem is fmod (the same for the non-negative values used).

  The engine (KOTOR_Exe 1.4.0, C1FCB8D3...6D71):

      0x1005ca818  the frame's length in seconds (float)       Windows 0x0078E574
      0x100635bcc  the frame counter (uint32)                   Windows 0x007A46F4
      0x10002b19b  the engine's rand()

  The hook list is kotor1-steam-aspyr-macos.hooks.toml beside this file.
*/
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <xmmintrin.h>

#define HFPS_EXPORT extern "C" __attribute__((visibility("default")))

namespace {

float* const kFrameSeconds = reinterpret_cast<float*>(0x1005ca818UL);
std::uint32_t* const kFrameCounter = reinterpret_cast<std::uint32_t*>(0x100635bccUL);
using GameRandFn = int (*)();
const GameRandFn GameRand = reinterpret_cast<GameRandFn>(0x10002b19bUL);

template <typename T> T& At(void* base, std::ptrdiff_t offset) {
    return *reinterpret_cast<T*>(static_cast<char*>(base) + offset);
}

bool PositiveFinite(float value) {
    std::uint32_t bits;
    std::memcpy(&bits, &value, 4);
    return bits > 0 && bits < 0x7F800000u;
}
double Positive(float value) { return PositiveFinite(value) ? static_cast<double>(value) : 0.0; }

// A float still below `interval` after rounding (D3M0's storeRemainder).
float StoreRemainder(double seconds, double interval) {
    float value = static_cast<float>(seconds);
    if (static_cast<double>(value) >= interval && value > 0) {
        std::uint32_t bits;
        std::memcpy(&bits, &value, 4);
        --bits;
        std::memcpy(&value, &bits, 4);
    }
    return value;
}

// ------------------------------------------------------------------- a 60 Hz gate for jitter
// K1AnimationUpdate: true on one frame in each sixtieth of a second, from the main loop's
// elapsed microseconds.
std::uint32_t g_jitterTicks = 50000;
bool g_allowJitter = true;

// ------------------------------------------------------------------------- per-object timers
struct TimerState { const void* owner; double fraction; std::uint32_t expected; };
template <unsigned N> struct TimerTable {
    TimerState states[N] = {};
    unsigned next = 0;
    void reset(const void* owner) {
        for (unsigned i = 0; i < N; ++i)
            if (states[i].owner == owner) states[i] = TimerState{nullptr, 0.0, 0};
    }
    TimerState& get(const void* owner) {
        for (unsigned i = 0; i < N; ++i)
            if (states[i].owner == owner) return states[i];
        for (unsigned i = 0; i < N; ++i)
            if (!states[i].owner) { states[i] = TimerState{owner, 0.0, 0}; return states[i]; }
        TimerState& state = states[next];
        next = (next + 1) % N;
        state = TimerState{owner, 0.0, 0};
        return state;
    }
};
TimerTable<64> g_shakeTimers;
TimerTable<64> g_previewTimers;

// Whole milliseconds of dt, the fraction carried to the next call.
std::uint32_t Milliseconds(TimerState& state, float dt) {
    if (!PositiveFinite(dt)) return 0;
    const double total = static_cast<double>(dt) * 1000.0 + state.fraction;
    const double fraction = std::fmod(total, 1.0);
    state.fraction = fraction;
    const double whole = total - fraction;
    return whole >= 1073741823.0 ? 0x3FFFFFFFu : static_cast<std::uint32_t>(whole);
}

// ------------------------------------------------------------------------------------- water
std::uint32_t g_waterLastFrame = 0xFFFFFFFFu;
bool g_waterAllow = true, g_waterHighFps = false;
float g_waterAccumulated = 0.0f;
const float kHighFpsThreshold = 0.015625f;                 // 1/64 s
const float kVirtualFrameSeconds = 1.0f / 60.0f;

void WaterUpdateFrame() {
    const std::uint32_t frame = *kFrameCounter;
    if (frame == g_waterLastFrame) return;
    g_waterLastFrame = frame;
    float seconds = *kFrameSeconds;
    if (!(seconds >= 0.0f)) seconds = 0.0f;
    if (seconds >= kHighFpsThreshold) { g_waterHighFps = false; g_waterAllow = true; return; }
    g_waterHighFps = true;
    g_waterAccumulated += seconds;
    if (g_waterAccumulated >= kVirtualFrameSeconds) {
        g_waterAccumulated -= kVirtualFrameSeconds;
        if (g_waterAccumulated > kVirtualFrameSeconds) g_waterAccumulated = kVirtualFrameSeconds;
        g_waterAllow = true;
    } else {
        g_waterAllow = false;
    }
}

// --------------------------------------------------------------------------------- particles
struct ParticleState { std::uintptr_t owner; double fraction; };
ParticleState g_particles[8192] = {};
std::uint32_t g_particleVictim = 0;

std::uint32_t ParticleHash(std::uintptr_t owner) {
    std::uint32_t hash = static_cast<std::uint32_t>(owner >> 4);
    hash ^= hash >> 11;
    hash *= 0x9E3779B1u;
    return hash >> 19;
}
ParticleState& ParticleFor(std::uintptr_t owner) {
    const std::uint32_t first = ParticleHash(owner);
    for (std::uint32_t n = 0; n < 8192; ++n) {
        ParticleState& state = g_particles[(first + n) & 8191u];
        if (state.owner == owner) return state;
        if (state.owner == 0) { state.owner = owner; state.fraction = 0; return state; }
    }
    ParticleState& state = g_particles[g_particleVictim];
    g_particleVictim = (g_particleVictim + 1) & 8191u;
    state.owner = owner;
    state.fraction = 0;
    return state;
}
void ResetParticle(std::uintptr_t owner) {
    if (owner == 0) return;
    const std::uint32_t first = ParticleHash(owner);
    for (std::uint32_t n = 0; n < 8192; ++n) {
        std::uint32_t hole = (first + n) & 8191u;
        if (g_particles[hole].owner == 0) return;
        if (g_particles[hole].owner != owner) continue;
        g_particles[hole].owner = 0;
        std::uint32_t scan = (hole + 1) & 8191u;
        for (std::uint32_t moved = 0; moved < 8191 && g_particles[scan].owner; ++moved) {
            const std::uint32_t home = ParticleHash(g_particles[scan].owner);
            if (((scan - home) & 8191u) >= ((scan - hole) & 8191u)) {
                g_particles[hole] = g_particles[scan];
                g_particles[scan].owner = 0;
                hole = scan;
            }
            scan = (scan + 1) & 8191u;
        }
        g_particles[hole].fraction = 0;
        return;
    }
}

}  // namespace

// CClientExoAppInternal::MainLoop, 0x100267cfe: eax the microseconds this pass took on the
// frame timer. Windows K1UpdateJitterTick (0x0060335D), unchanged: 50000 / 3 microseconds is a
// sixtieth of a second.
HFPS_EXPORT void HfpsUpdateJitterTick(std::int32_t elapsedMicroseconds) {
    if (elapsedMicroseconds <= 0) { g_allowJitter = false; return; }
    g_jitterTicks += static_cast<std::uint32_t>(elapsedMicroseconds) * 3u;
    g_allowJitter = false;
    if (static_cast<std::int32_t>(g_jitterTicks) >= 50000) {
        g_allowJitter = true;
        g_jitterTicks -= 50000u;
        if (static_cast<std::int32_t>(g_jitterTicks) > 50000) g_jitterTicks = 50000;
    }
}

// Global::ProceduralAnimateHierarchy, 0x1001ae676: r15 the mesh node, rbp the function's frame.
// Windows K1GateJitterBranch1..3 (0x004836C7, 0x00483916, 0x00483B72; the Mac has one loop
// where Windows has three): on a frame the gate does not allow, the random jitter of a node
// that has a jitter speed (+0x188; Windows +0x148) is not drawn. What is zeroed is the modulus
// of the engine's rand() at [rbp-0x2c], which makes its own test skip the jitter.
HFPS_EXPORT void HfpsGateUvJitter(char* node, char* frame) {
    std::uint32_t speedBits;
    std::memcpy(&speedBits, node + 0x188, 4);
    if (!g_allowJitter && speedBits != 0) At<std::int32_t>(frame, -0x2c) = 0;
}

// CSWCModule::UpdateCameraBumpAndShake, 0x100294b97: rbx the module, rbp its frame. Windows
// K1AccumulateShakeMilliseconds (0x00641827) returned the milliseconds in eax; the Mac wants
// them in esi, which a handler cannot set. The hook is on the load of the frame's seconds from
// [rbp-0x2c] instead, and the handler rewrites that slot so that the game's own multiplication
// by 1000 and truncation give exactly the whole milliseconds (the slot is not read as seconds
// again: it is overwritten at 0x100294be8 before any other read).
HFPS_EXPORT void HfpsShakeMilliseconds(char* module, char* frame) {
    float& slot = At<float>(frame, -0x2c);
    if (At<std::int32_t>(module, 0x10c) <= 0) {   // not reached here; kept as on Windows
        g_shakeTimers.reset(module);
        return;
    }
    std::uint32_t ms = Milliseconds(g_shakeTimers.get(module), slot);
    if (ms > 100000u) ms = 100000u;
    slot = static_cast<float>((static_cast<double>(ms) + 0.5) / 1000.0);
}

// CSWCModule::ShakeCamera, 0x100294a52: rdi the module. Windows K1ResetShakeNewEffect.
HFPS_EXPORT void HfpsResetShake(void* module) { g_shakeTimers.reset(module); }

// CSWCCreature::CGPauseCycle, 0x1002a4973: r15 the creature, rbp the function's frame. Windows
// K1AccumulatePreviewMilliseconds (0x0060F92E): the milliseconds added to the creature's
// counter (+0x4ec; Windows +0x390), in eax as there.
HFPS_EXPORT std::uint32_t HfpsPreviewMilliseconds(char* creature, char* frame) {
    const float dt = At<float>(frame, -0x50);
    TimerState& state = g_previewTimers.get(creature);
    const std::uint32_t elapsed = At<std::uint32_t>(creature, 0x4ec);
    if (elapsed != state.expected) state.fraction = 0;
    std::uint32_t amount = Milliseconds(state, dt);
    if (amount > 0xFFFFFFFFu - elapsed) amount = 0xFFFFFFFFu - elapsed;
    state.expected = elapsed + amount;
    return amount;
}

// CSWCCreature::CGPauseCycle, 0x1002a4d23 (r15), and CSWCCreature's constructor, 0x100298287
// (rbx): the counter is zeroed. Windows K1ResetPreviewIdle and K1ResetPreviewObject.
HFPS_EXPORT void HfpsResetPreview(void* creature) { g_previewTimers.reset(creature); }

// WaterTextureController::Control, entry (0x1001fc6a0): rdi the controller. Windows
// K1GateWaterControllerFrame (0x00461823): below 1/64 s a frame the controller runs sixty times
// a second, by being told it has already run this frame (+0x10; Windows +0x08).
HFPS_EXPORT void HfpsWaterGate(char* controller) {
    WaterUpdateFrame();
    if (g_waterHighFps && !g_waterAllow) At<std::uint32_t>(controller, 0x10) = *kFrameCounter;
}

// WaterTextureController::Control, 0x1001fc73e: in place of the address of the frame's seconds,
// which the next instruction reads. Windows K1FixWaterVirtualFrameDelta (0x004618BF) overwrote
// the product of the seconds with the controller's speed; here the game makes that product
// itself, from a sixtieth of a second while the gate is at work.
HFPS_EXPORT const float* HfpsWaterDelta() { return g_waterHighFps ? &kVirtualFrameSeconds : kFrameSeconds; }

// CycleTIDTextureController::Control, 0x1001fe28a: rbx the controller, past its once-a-frame
// test. Windows K1UpdateCycleTexture (0x00460981): as many frames of the texture as the time
// that has passed, the remainder kept; the game advanced one and dropped the remainder. Always
// returns 1: the function is left through its epilogue.
HFPS_EXPORT int HfpsCycleTexture(char* owner) {
    float& accumulated = At<float>(owner, 0x58);
    const float dt = *kFrameSeconds;
    const float fps = At<float>(owner, 0x50);
    if (!PositiveFinite(dt) || !PositiveFinite(fps)) return 1;
    const double seconds = Positive(accumulated) + dt;
    const double progress = seconds * fps;
    const double whole = std::floor(progress);
    const double fraction = progress - whole;
    if (whole < 1.0) {
        accumulated = StoreRemainder(seconds, 1.0 / fps);
        return 1;
    }
    void* texture = At<void*>(owner, 0x08);
    if (!texture) return 1;
    void** table = *reinterpret_cast<void***>(texture);
    if (!table) return 1;
    using Dimension = int (*)(void*);
    using SelectFrame = void (*)(void*, int);
    const int a = reinterpret_cast<Dimension>(table[0xb8 / 8])(texture);
    const int b = reinterpret_cast<Dimension>(table[0xc0 / 8])(texture);
    if (a <= 0 || b <= 0 || a > 0x7FFFFFFF / b) return 1;
    const std::uint32_t frames = static_cast<std::uint32_t>(a * b);
    const std::int32_t current = At<std::int32_t>(owner, 0x54);
    const std::uint32_t start = current < 0 ? 0u : static_cast<std::uint32_t>(current) % frames;
    const std::uint32_t advance = static_cast<std::uint32_t>(std::fmod(whole, static_cast<double>(frames)));
    const std::uint32_t next = (start + advance) % frames;
    accumulated = StoreRemainder(fraction / fps, 1.0 / fps);
    At<std::uint32_t>(owner, 0x54) = next;
    reinterpret_cast<SelectFrame>(table[0x158 / 8])(texture, static_cast<int>(next));
    return 1;
}

// FountainEmitter::Update, 0x10018f9de: r15 the emitter, rbp the function's frame. Windows
// K1AccumulateParticleTime and K1CalculateParticleBudget (0x004973F7, 0x004974AB) in one,
// because the randomised rate lives in xmm3 between the two on the Mac: the time is
// accumulated (+0xe4; Windows +0xCC), the rate is spread by the game's own two rand() calls in
// their order, and the budget is D3M0's, with a fraction carried per emitter. Returns 1 for no
// particle this frame (the function is left through its epilogue) and 0 with the budget in
// [rbp-0x40], which the patched loop tail (0x10018fb5d) counts down.
HFPS_EXPORT int HfpsFountainEmit(char* emitter, char* frame) {
    const float dt = At<float>(frame, -0x2c);
    float rate = At<float>(frame, -0x40);
    float& accumulated = At<float>(emitter, 0xe4);
    if (!PositiveFinite(dt) || !PositiveFinite(rate)) return 1;
    const double total = Positive(accumulated) + dt;
    const float stored = static_cast<float>(total > 3.0e38 ? 3.0e38 : total);
    accumulated = stored;
    if (!(static_cast<double>(stored) * rate >= 1.0)) return 1;

    const int spread = _mm_cvttss_si32(_mm_set_ss(At<float>(emitter, 0x108)));
    if (spread > 0) {
        const int sign = GameRand();
        const int roll = GameRand();
        float offset = static_cast<float>(roll % spread);
        if ((sign & 1) == 0) offset = -offset;
        rate += offset;
        if (0.0f > rate) rate = 0.0f;
    }

    const double seconds = Positive(accumulated);
    const float baseRate = At<float>(emitter, 0x70);
    std::int32_t budget = 0;
    if (PositiveFinite(baseRate)) {
        const double baseProgress = seconds * baseRate;
        const double pending = std::fmod(baseProgress, 1.0);
        const double opportunities = baseProgress - pending;
        accumulated = StoreRemainder(pending / baseRate, 1.0 / baseRate);
        ParticleState& state = ParticleFor(reinterpret_cast<std::uintptr_t>(emitter));
        if (PositiveFinite(rate)) {
            const double credit = opportunities * rate / baseRate + state.fraction;
            const double fraction = std::fmod(credit, 1.0);
            const double whole = credit - fraction;
            state.fraction = fraction;
            const std::int32_t limit = rate >= 4095.0f ? 4096 : static_cast<std::int32_t>(rate) + 1;
            budget = whole >= limit ? limit : static_cast<std::int32_t>(whole);
        }
    }
    if (budget <= 0) return 1;
    At<std::int32_t>(frame, -0x40) = budget;
    return 0;
}

// PartEmitter::Initialize, 0x10018df5e (rbx), and PartEmitter's destructor, 0x1001876f6 (rdi).
// Windows K1ResetParticleInit and K1ResetParticleDestroy.
HFPS_EXPORT void HfpsResetParticle(char* emitter) { ResetParticle(reinterpret_cast<std::uintptr_t>(emitter)); }
