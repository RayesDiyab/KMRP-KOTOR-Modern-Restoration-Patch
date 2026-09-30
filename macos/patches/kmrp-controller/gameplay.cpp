// KMRP for macOS, controller support: the world. Analog movement, the right-stick camera, and
// the engine bridges a press in the world asks for (L3's flourish, Start's Map, A on the
// target, R3 out of free look).
//
// The Mac port of K1NativeJoystick.cpp's gameplay half: NativeJoystickMovementK1 and
// NativeJoystickSkipNormalizeK1, FeedNativeCameraK1, and the PerformPending* bridges, with
// the same guards. Two differences, both from the Mac engine:
//
//   - The bridges run from the camera frame, not the movement heartbeat. MainLoop calls
//     UpdateCamera once a frame in the world, in free look as well as in play, and skips it in
//     menus, minigames and movies (0x10026840c..0x100268414): the same "only in the world"
//     test the Windows hooks make, provided by the engine.
//   - Aspyr's AcclTurnCamera takes no frame time: in the normal camera it adds its argument to
//     the camera's turn rate. UpdateCamera passes it the keyboard's turn axis, -1..1, every
//     frame, so the stick's deflection goes in as it is, as on Windows.
#include "engine.h"
#include "hud.h"
#include "pad.h"
#include "prompts.h"
#include "state.h"

#include <cmath>
#include <time.h>

namespace kmrp {

Requests g_requests;
float g_rightX = 0, g_rightY = 0;
std::uint64_t g_lastPadPressMs = 0;
std::uint32_t g_padButtons = 0;
float g_analogMagnitude = 0;
float g_leftX = 0, g_leftY = 0;
std::uint64_t g_lastBufferMs = 0;

std::uint64_t NowMs() {
    timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return static_cast<std::uint64_t>(t.tv_sec) * 1000u + static_cast<std::uint64_t>(t.tv_nsec) / 1000000u;
}

bool TakeRequest(std::uint64_t& request) {
    if (request == 0) return false;
    const bool fresh = NowMs() - request <= kRequestWindowMs;
    request = 0;
    return fresh;
}

namespace {

using namespace engine;

// K1NativeJoystick.cpp's camera constants.
const float kCameraSpeed = 1.0f;
const float kCameraDeadzone = 0.12f;

bool g_analogOverride = false;   // set by the movement heartbeat, read at the Normalize call

struct Counters {
    unsigned long flourishes = 0, flourishesDeclined = 0, mapOpens = 0, freeLookExits = 0;
    unsigned long interacts = 0, interactsDeclined = 0, cameraTurns = 0;
    unsigned long normalizeSkipped = 0, normalizeRun = 0;
} g_count;

bool HasTarget(void* internal) {
    const std::uint64_t target = At<std::uint64_t>(internal, kInternalTarget);
    return target != kObjectInvalid && target != 0;
}

// PerformPendingFreeLookExitK1: the router's own exit (0x06), whose handler tests the camera
// mode itself; that test is what separates "leave free look" from "select the previous target".
void PerformFreeLookExit(void* internal) {
    if (!TakeRequest(g_requests.freeLookExit)) return;
    if (At<int>(internal, kInternalInputClass) != kClassFreeLook) return;
    HandleInputEvent()(internal, kEventFreeLookExit, 1);
    ++g_count.freeLookExits;
    Log("R3: left free look");
}

// PerformPendingMapOpenK1: Start in the world opens the Map through the engine's own Map
// hotkey, with every guard it applies (a dead player, no party, a modal already up).
void PerformMapOpen(void* internal) {
    if (!TakeRequest(g_requests.mapOpen)) return;
    if (At<int>(internal, kInternalInputClass) != kClassPC) return;
    HandleInputEvent()(internal, kEventMenuMap, 1);
    ++g_count.mapOpens;
    Log("Start: opened the Map");
}

// PerformPendingStickActionsK1: L3's flourish, in the world only, with a player, and not in
// free look, where the stick drives the camera rather than the character.
void PerformFlourish(void* internal) {
    if (!TakeRequest(g_requests.flourish)) return;
    void* app = ClientApp();
    if (!app || At<int>(internal, kInternalInputClass) != kClassPC || !GetPlayerCreature()(app) ||
        GetInFreeLook()(app)) {
        ++g_count.flourishesDeclined;
        return;
    }
    PlayerFlourishWeapons()(app);
    ++g_count.flourishes;
    Log("L3: flourish");
}

// PerformPendingInteractionK1: A in the world does the default action on the target, through
// the router's 0xEF, and nothing at all without a target, or while a slot of the HUD's action
// bar has the focus, when A is that slot's (hud.cpp).
void PerformInteraction(void* internal) {
    if (!TakeRequest(g_requests.interact)) return;
    if (At<int>(internal, kInternalInputClass) != kClassPC || !HasTarget(internal) || hud::ActionBarFocused()) {
        ++g_count.interactsDeclined;
        return;
    }
    HandleInputEvent()(internal, kEventDefaultAction, 1);
    ++g_count.interacts;
}

// FeedNativeCameraK1: the right stick's horizontal deflection turns the camera, radially dead-
// zoned and rescaled so the first movement past the deadzone starts from a standstill. Not
// negated, as on Windows: the keyboard's axis runs opposite to the stick, and UpdateCamera's
// negation is for that axis. In play and in free look only; UpdateCamera is not called in
// menus, which is also when this does not run.
void FeedCamera(void* internal) {
    const int inputClass = At<int>(internal, kInternalInputClass);
    if (inputClass != kClassPC && inputClass != kClassFreeLook) return;
    const float nx = g_rightX, ny = g_rightY;
    const float magnitude = std::sqrt(nx * nx + ny * ny);
    if (magnitude <= kCameraDeadzone) return;
    void* module = At<void*>(internal, kInternalModule);
    if (!module) return;
    float scaled = (magnitude - kCameraDeadzone) / (1.0f - kCameraDeadzone);
    if (scaled > 1.0f) scaled = 1.0f;
    AcclTurnCamera()(nx * (scaled / magnitude) * kCameraSpeed, module);
    ++g_count.cameraTurns;
}

}  // namespace

// Whether the left stick is driving this frame: in play, with a buffer filled in the last
// quarter second, and past the deadzone. NativeAnalogDrivingK1.
bool AnalogDriving() {
    if (engine::CurrentInputClass() != engine::kClassPC) return false;
    if (g_lastBufferMs == 0 || NowMs() - g_lastBufferMs > kRequestWindowMs) return false;
    return g_analogMagnitude > 0.0f;
}

void GameplayStatus() {
    Log("world: %lu flourishes (%lu declined), %lu Map opens, %lu free-look exits, %lu interactions (%lu "
        "declined), camera turned on %lu frames, movement normalised %lu times and left analog %lu times",
        g_count.flourishes, g_count.flourishesDeclined, g_count.mapOpens, g_count.freeLookExits, g_count.interacts,
        g_count.interactsDeclined, g_count.cameraTurns, g_count.normalizeRun, g_count.normalizeSkipped);
}

// CSWPlayerControlCamRelative::Control, entry (0x1002249b2; Windows 0x00679940): the movement
// heartbeat. It decides once a frame, just before Control reaches its Normalize call, whether
// the stick's magnitude survives.
extern "C" __attribute__((visibility("default"))) void KmrpMovementFrame(void* playerControl) {
    (void)playerControl;
    g_analogOverride = AnalogDriving();
}

// Control's call to Vector::Normalize (0x100224c56; Windows 0x00679B71). Control builds the
// movement vector from the two axes, normalises it when both are non-zero, and halves it when
// walking, so a stick past the deadzone only ever chose a direction and always ran at full
// speed. While the stick drives, the call is skipped and the speed follows the deflection;
// otherwise Normalize runs as the game's own call would, so keyboard diagonals are unchanged.
//
// Always consumes: the stolen bytes are a relative call, which cannot run from the wrapper.
extern "C" __attribute__((visibility("default"))) int KmrpSkipNormalize(void* vector) {
    if (!g_analogOverride && vector) {
        engine::VectorNormalize()(vector);
        ++g_count.normalizeRun;
    } else {
        // The Mac engine's analog axes are not the stick's: each comes back as sign(v) x (0.5 +
        // 0.5 |v|) (measured 2026-10-01 at the Normalize call: a stick 1,668/32,767 right of centre
        // gave -0.525, 386 left gave +0.506, 20,133 gave -0.807), so any drift from straight up
        // steered half sideways and diagonals bent up to 27 degrees. Windows' engine passes the
        // axes through. While the stick drives, the vector is the stick's own, in Control's
        // convention (-LeftRight, UpDown), UpDown growing downward as the buffer sends it: the
        // direction and the deflection as sent, as on Windows.
        if (vector) {
            float* v = static_cast<float*>(vector);
            v[0] = -g_leftX;
            v[1] = g_leftY;
        }
        ++g_count.normalizeSkipped;
    }
    return 1;
}

// MainLoop's call to UpdateCamera (0x100268424), made in play and in free look only. The call
// is made here, then the right stick is added to the turn (FeedNativeCameraK1, which Windows
// runs at the same point, MainLoop after UpdateCamera: in free look AcclTurnCamera sets the
// camera's turn rather than adding to it, so a stick turn made before UpdateCamera would be
// overwritten by its own), then the world's pending bridges run.
//
// Always consumes, for the same reason as KmrpSkipNormalize.
extern "C" __attribute__((visibility("default"))) int KmrpCameraFrame(void* internal) {
    engine::UpdateCamera()(engine::FrameSeconds(), internal);
    if (!internal) return 1;
    FeedCamera(internal);
    PerformFreeLookExit(internal);
    PerformMapOpen(internal);
    PerformFlourish(internal);
    PerformInteraction(internal);
    return 1;
}

// Aspyr's movie loop (0x1000139e4), at the top of each frame (0x100014566; Windows hooks
// CExoMoviePlayerInternal::PlayMovieLoop, NativeMovieFrameK1). A movie owns the game loop, so
// the input poll does not run and the pad is read here. The loop keeps its state in a block on
// its stack, which it also hands to its SDL event callback (0x1000152d8): byte 0 is set by a
// key, mouse or controller button's release there, and stops the movie once its unskippable
// start has passed; byte 1 is set only on quitting. A and Start set byte 0, as a key does, and
// only when pressed during the movie: a press held from before it (the Start that began a new
// game) does not count until it has been let go.
extern "C" __attribute__((visibility("default"))) void KmrpMovieFrame(std::uint8_t* state) {
    static std::uint8_t* movie = nullptr;
    static bool armed = false;
    static unsigned long skips = 0;
    if (!state) return;
    PadState pad;
    const bool present = ReadPad(&pad);
    device::NotePad(present, pad);
    const bool skip = present && (pad.buttons & (kPadA | kPadStart)) != 0;
    if (state != movie) {
        movie = state;
        armed = !skip;
    }
    if (!skip) {
        armed = true;
        return;
    }
    if (armed && state[0] == 0) {
        state[0] = 1;
        armed = false;
        Log("movie: skipped with the pad (%lu)", ++skips);
    }
}

}  // namespace kmrp
