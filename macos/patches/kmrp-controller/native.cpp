// KMRP for macOS, controller support: the engine's own joystick pipeline, fed by the pad.
//
// The Mac port of the native path in src/controller-native/K1NativeJoystick.cpp, whose
// design and reasoning are in docs/controller-native-path.md and
// reverse-engineering/retained-xbox-gui-events.md. Every address and offset below is the
// Aspyr build's (KOTOR_Exe 1.4.0, C1FCB8D3...6D71), found against the Windows ones on
// 2026-09-29; the Windows equivalent is named beside each.
//
// What the Mac build already has, and Windows lacked: Aspyr kept the whole retained joystick
// chain and connected it. CExoInputInternal::GetEvents computes the device count as the raw
// input's pad count + 2 and reads every pad through GetJoystickBuffer, which turns a
// DIJOYSTATE into DirectInput-style records. What it lacks, like Windows: no description
// binds a pad button to an event, so only the engine's own few (the sticks and Start) exist.
// And its pads come from SDL 2.0.7, which does not know a DualSense. Aspyr also added a pad
// mapping of its own at the end of GetEvents, which KMRP's hooks file switches off: it reads
// the records in another button layout and would add a second event to every press (see
// kotor1-steam-aspyr-macos.hooks.toml). So this module
//
//   1. registers the button descriptions the Windows module registers, with the same event
//      ids, control slots and input classes (Register);
//   2. keeps a pad device in the count (the tick);
//   3. replaces GetJoystickBuffer with one that reads the pad through GameController and
//      emits the same records (KmrpGetJoystickBuffer). Each record's control code is read
//      from the engine's own slot table, so no code is assumed.
#include "engine.h"
#include "gui.h"
#include "hud.h"
#include "pad.h"
#include "prompts.h"
#include "rumble.h"
#include "state.h"
#include "../kmrp-layout/options.h"

#include <mach/mach.h>
#include <time.h>
#include <mach/mach_vm.h>

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <initializer_list>
#include <new>

namespace {

using kmrp::Log;

// ------------------------------------------------------------------------ engine ABI

// CExoInputInternal::CreateNewEvent(eventId, descType, device, slot, secondSlot); Windows
// 0x005E0E20. Returns 0 when the event already has a description or the device is past 5.
using CreateNewEventFn = int (*)(void* input, unsigned eventId, int type, int device, int slot, int slot2);
// CExoInputInternal::AddEvent(eventId, inputClass); Windows 0x005E0FA0.
using AddEventFn = int (*)(void* input, int eventId, unsigned inputClass);

const auto CreateNewEvent = reinterpret_cast<CreateNewEventFn>(0x10035562eUL);
const auto AddEvent = reinterpret_cast<AddEventFn>(0x1003557c4UL);

// GetJoystickBuffer(raw, padIndex, &buffer) at 0x100358cdc, CExoRawInputInternal's; Windows
// 0x005E30F6. Replaced whole (KmrpGetJoystickBuffer), by a jump over its prologue.
const std::uintptr_t kGetJoystickBuffer = 0x100358cdcUL;
const std::uint8_t kGetJoystickBufferPrologue[14] = {
    0x55, 0x48, 0x89, 0xe5, 0x41, 0x57, 0x41, 0x56, 0x41, 0x55, 0x41, 0x54, 0x53, 0x48};

// CExoInputInternal offsets, 64-bit.
const std::size_t kDescriptions = 0x220;     // description*[event id]
const std::size_t kDescriptionCount = 0x228;
const std::size_t kRawInput = 0x248;         // CExoRawInputInternal*
const std::size_t kDeviceCount = 0x268;      // keyboard + mouse + pads; Windows 0x158
const std::size_t kControlCodes = 0x27c;     // int[slot] -> the record's control code; Windows 0x164
const std::size_t kClassStride = 0x58;       // per input class: lists at +0x20 (any device),
const std::size_t kClassDeviceLists = 0x28;  //   +0x28 + device * 8, bitmap pointer at +0x58
const int kClasses = 6;

// CExoRawInputInternal: the per-pad state arrays, 0x134 bytes a pad, that its enumeration
// allocates only when it finds pads (0x1003588fe). GetEvents reads the previous state from
// +0x48 through 0x10035968a whenever a button description receives an axis code, and a null
// array there crashed the game on the first B press (2026-09-29).
const std::size_t kRawPadState = 0x40, kRawPadPrevious = 0x48, kRawPadStride = 0x134;
const int kPadStateSlots = 4;

// GetEvents' pad re-enumeration flag. Only GetEvents reads or writes it.
const std::uintptr_t kEnumerateFlag = 0x1005d425cUL;

// Devices, as SetEventDescriptions passes them (0x100572180..0x10057218c): -1 any,
// 0 keyboard, 1 mouse, 2 the first pad.
const int kDevicePad = 2;

// Input classes, keymap.2da's IC* columns (engine.h).
using kmrp::engine::kClassPC;
using kmrp::engine::kClassMiniGame;
using kmrp::engine::kClassPCGUI;
using kmrp::engine::kClassDialog;
using kmrp::engine::kClassFreeLook;

// Description types.
const int kDigital = 1;

// Control slots (indices into the table at +0x27c), as on Windows: the table maps
// 0x6E/0x6F to the left stick, 0x71/0x72 to the right (SetEventDescriptions binds the game's
// own events 8/7 and 0x0C/0x0D there; the right stick's are read by a debug camera only, so
// the right stick gets no records), 0x74..0x7E to buttons 0..10, 0x7F..0x82 to the four hat
// directions, and 0x84 is "no control".
const int kSlotLeftX = 0x6E, kSlotLeftY = 0x6F;
const int kSlotNone = 0x84;

// Where the Mac's slot table differs from Windows: slots 0x74 and 0x75, Windows'
// DIJOFS_BUTTON(0) and (1), hold the axis codes 0x0C and 0x10 here, so A and B arrived as
// axes. Nothing in the game binds either slot, so the module points them back at the two
// buttons (FixSlotTable), checking first that no description uses them.
const int kSlotButton0 = 0x74, kSlotButton1 = 0x75;
const int kCodeButton0 = 0x30, kCodeButton1 = 0x31;

// Retained console events, K1NativeJoystick.cpp's K1_EVENT_*.
const int kEventA = 0x27, kEventB = 0x28, kEventX = 0x29, kEventY = 0x2A, kEventBlack = 0x2B;
const int kEventLeft = 0x2F, kEventRight = 0x30, kEventUp = 0x31, kEventDown = 0x32;
const int kEventPrevScreen = 0x35, kEventNextScreen = 0x36;
const int kEventDescUp = 0x39, kEventDescDown = 0x3A;
const int kEventFreeLookEnter = 0x01, kEventFreeLookExit = 0x06;   // 0x06 is also SelectPrev
const int kEventPause = 0x02, kEventSelectNext = 0x05, kEventChangeChar = 0x09, kEventPartyActive = 0x0A;

struct Binding {
    int slot;
    int event;
    const char* name;
};

// K1_BUTTONS and K1_TRIGGERS: menus (ICPCGUI) and, unless a gameplay verb owns the slot,
// the world (ICPC).
const Binding kButtons[] = {
    {0x74, kEventA, "A"}, {0x75, kEventB, "B"}, {0x76, kEventX, "X"}, {0x77, kEventY, "Y"},
    {0x78, kEventDescUp, "LB"}, {0x79, kEventDescDown, "RB"}, {0x7A, kEventBlack, "Back"},
    {0x7B, kEventPrevScreen, "LT"}, {0x7D, kEventNextScreen, "RT"},
};
// K1_DPAD: menus and the world.
const Binding kDpad[] = {
    {0x7F, kEventUp, "Up"}, {0x81, kEventDown, "Down"}, {0x80, kEventLeft, "Left"}, {0x82, kEventRight, "Right"},
};
// K1_GAMEPLAY_ACTIONS: the world only. The bool is whether the slot keeps its menu event.
const struct { int slot; int event; bool guiInMenus; const char* name; } kVerbs[] = {
    {0x78, kEventFreeLookExit, false, "LB"},   // SelectPrev; its description is free look's exit
    {0x79, kEventSelectNext, false, "RB"},
    {0x7A, kEventPartyActive, true, "Back"},
    {0x7B, kEventChangeChar, true, "LT"},
    {0x7D, kEventPause, true, "RT"},
};
const int kSlotStart = 0x7C;   // the game's own event 0x0B, registered by the game
const int kSlotR3 = 0x7E;      // free look
const int kSlotDpadUp = 0x7F, kSlotDpadDown = 0x81, kSlotDpadRight = 0x82;   // Left is 0x80

bool VerbOwnsSlot(int slot) {
    for (const auto& v : kVerbs) if (v.slot == slot) return true;
    return false;
}
bool GuiEventWanted(int slot) {
    for (const auto& v : kVerbs) if (v.slot == slot) return v.guiInMenus;
    return true;
}

// ------------------------------------------------------------------------ state

void* g_input = nullptr;         // the CExoInputInternal the last tick saw
bool g_announced = false;
kmrp::PadState g_pad;            // read once per tick
bool g_padPresent = false;
std::uint32_t g_heldDigital = 0; // per-slot pressed state last read, bit (slot - 0x74)
int g_sentAs[15] = {};           // per slot: the slot whose code its press went out as, or 0
std::uint32_t g_dpadRepeatMask = 0;
std::uint64_t g_dpadRepeatDeadline = 0;
std::uint32_t g_navButtons = 0;  // the pad's buttons at the last navigation read
bool g_l3Held = false;
int g_bound = 0;

template <typename T> T& At(void* base, std::size_t offset) {
    return *reinterpret_cast<T*>(static_cast<char*>(base) + offset);
}

bool DescriptionPresent(void* input, int eventId) {
    auto* table = At<void**>(input, kDescriptions);
    return table && static_cast<unsigned>(eventId) < At<unsigned>(input, kDescriptionCount) && table[eventId];
}

int ControlCode(void* input, int slot) {
    return At<int>(input, kControlCodes + static_cast<std::size_t>(slot) * 4);
}

bool PadListsExist(void* input) {
    for (int c = 0; c < kClasses; ++c) {
        if (!At<void*>(input, kClassDeviceLists + c * kClassStride + kDevicePad * 8)) return false;
    }
    return true;
}

bool Create(void* input, int eventId, int slot) {
    return CreateNewEvent(input, static_cast<unsigned>(eventId), kDigital, kDevicePad, slot, kSlotNone) != 0 ||
           DescriptionPresent(input, eventId);
}

// True when any description of this input object is bound to `slot`, as its first or second
// control (+0x20, +0x34).
bool SlotInUse(void* input, int slot) {
    auto* table = At<char**>(input, kDescriptions);
    const unsigned n = At<unsigned>(input, kDescriptionCount);
    for (unsigned e = 0; table && e < n; ++e) {
        char* d = table[e];
        if (!d) continue;
        if (*reinterpret_cast<int*>(d + 0x20) == slot) return true;
        if (*reinterpret_cast<int*>(d + 0x18) == 4 && *reinterpret_cast<int*>(d + 0x34) == slot) return true;
    }
    return false;
}

bool FixSlotTable(void* input) {
    int& b0 = At<int>(input, kControlCodes + kSlotButton0 * 4);
    int& b1 = At<int>(input, kControlCodes + kSlotButton1 * 4);
    if (b0 == kCodeButton0 && b1 == kCodeButton1) return true;
    if (SlotInUse(input, kSlotButton0) || SlotInUse(input, kSlotButton1)) {
        Log("slots 0x74/0x75 are bound by the game; A and B stay unbound");
        return false;
    }
    Log("slots 0x74/0x75: codes 0x%x/0x%x -> 0x%x/0x%x (buttons 0 and 1)", b0, b1, kCodeButton0, kCodeButton1);
    b0 = kCodeButton0;
    b1 = kCodeButton1;
    return true;
}

// The per-pad state arrays, allocated as the enumeration would, with the engine's allocator
// (operator new[], the one its enumeration frees them with), zeroed, for four pads.
void EnsurePadState(void* input) {
    void* raw = At<void*>(input, kRawInput);
    if (!raw) return;
    for (std::size_t offset : {kRawPadState, kRawPadPrevious}) {
        void*& array = At<void*>(raw, offset);
        if (array) continue;
        const std::size_t bytes = kRawPadStride * kPadStateSlots;
        array = operator new[](bytes);
        std::memset(array, 0, bytes);
        Log("raw input +0x%zx: allocated the per-pad state (%zu bytes)", offset, bytes);
    }
}

// K1NativeJoystick.cpp's registration, for the pad's buttons. The sticks and Start need
// nothing: the game registers its own pad descriptions for them.
void Register(void* input) {
    g_bound = 0;
    for (const auto& b : kButtons) {
        if (!Create(input, b.event, b.slot)) { Log("%s: event 0x%x could not be created", b.name, b.event); continue; }
        if (GuiEventWanted(b.slot)) AddEvent(input, b.event, kClassPCGUI);
        if (!VerbOwnsSlot(b.slot)) AddEvent(input, b.event, kClassPC);
        ++g_bound;
    }
    for (const auto& b : kDpad) {
        if (!Create(input, b.event, b.slot)) { Log("%s: event 0x%x could not be created", b.name, b.event); continue; }
        AddEvent(input, b.event, kClassPCGUI);
        AddEvent(input, b.event, kClassPC);
        ++g_bound;
    }
    // Conversations: only the events the dialogue dispatchers implement.
    for (int e : {kEventA, kEventUp, kEventDown, kEventDescUp, kEventDescDown}) AddEvent(input, e, kClassDialog);
    // Pazaak, swoop and the turret: B, Y and the two screen changes, the events the minigame
    // dispatchers implement (K1NativeJoystick.cpp, "ICMiniGame"). Not A: neither implements it.
    for (int e : {kEventB, kEventY, kEventPrevScreen, kEventNextScreen}) AddEvent(input, e, kClassMiniGame);
    // Free look: entered with R3 in the world, left with LB in free look.
    if (Create(input, kEventFreeLookEnter, kSlotR3)) { AddEvent(input, kEventFreeLookEnter, kClassPC); ++g_bound; }
    if (Create(input, kEventFreeLookExit, 0x78)) { AddEvent(input, kEventFreeLookExit, kClassFreeLook); ++g_bound; }
    // The gameplay verbs, in the world only.
    for (const auto& v : kVerbs) {
        if (v.event != kEventFreeLookExit && !Create(input, v.event, v.slot)) continue;
        AddEvent(input, v.event, kClassPC);
        ++g_bound;
    }
    Log("registered %d pad bindings on input %p", g_bound, input);
}

void Announce(void* input) {
    void* raw = At<void*>(input, kRawInput);
    Log("input %p: device count %d, raw %p (pads %d), enumerate flag %d, pad lists %s",
        input, At<int>(input, kDeviceCount), raw, raw ? At<int>(raw, 0x18) : -1,
        *reinterpret_cast<int*>(kEnumerateFlag), PadListsExist(input) ? "present" : "MISSING");
    char line[512];
    int n = 0;
    for (int slot = 0x6E; slot <= 0x84; ++slot)
        n += std::snprintf(line + n, sizeof line - n, " %x:%x", slot, ControlCode(input, slot));
    Log("control codes%s", line);
    for (int e : {0x07, 0x08, 0x0B, 0x0C, 0x0D})
        Log("game's own event 0x%02x: %s", e, DescriptionPresent(input, e) ? "present" : "absent");
}

// ------------------------------------------------------------------------ routes

// Where a press goes, decided when it is made (the per-button routes of
// FillNativeJoystickBufferK1): the slot whose code goes out for it, or 0 when a bridge or a
// remap takes it and nothing goes out. Its release follows the same route, so a press and its
// release always go to the same place, and only ever one place.
//
//   Start, in the world: the Map (issue #18), through the router's own Map hotkey, instead of
//     the game's 0x0B, which opens Options. With the in-game menu open: B, the close that
//     works from every tab. Anywhere else the game's own Start.
//   R3, in free look: the router's exit, because free look's enter event is registered in the
//     world's class only. In a menu: the next party member, on the four screens about one. In
//     the world, free look's own enter event.
//   A, in the world: its native event still goes out (nothing in the world answers it), and it
//     also asks for the focused action-bar slot's action or, with none focused, the default
//     action on the target. B lets go of the action bar; X and Y press the HUD's Disengage and
//     remove-last-action buttons in combat. Their native events still go out too.
//   The D-pad, where KMRP's focus layer owns the direction (and in the world, where the action
//     bar does): nothing, the layer moves the focus.
//   A button a screen redefines (the Journal, Feats, Default, a focused button): nothing, the
//     GUI frame does what the screen means.
int Route(int slot, int inputClass, std::uint64_t now) {
    namespace gui = kmrp::gui;
    kmrp::g_lastPadPressMs = now;
    if (slot == kSlotStart) {
        if (inputClass == kClassPC) { kmrp::g_requests.mapOpen = now; return 0; }
        if (inputClass == kClassPCGUI && gui::TabBarOpen()) return kSlotButton1;
        return slot;
    }
    if (slot == kSlotR3) {
        if (inputClass == kClassFreeLook) { kmrp::g_requests.freeLookExit = now; return 0; }
        if (inputClass == kClassPCGUI) { kmrp::g_requests.partySwitch = now; return 0; }
        return slot;
    }
    if (slot >= kSlotDpadUp && slot <= kSlotDpadRight) {
        const bool vertical = slot == kSlotDpadUp || slot == kSlotDpadDown;
        return gui::OwnsDirections(vertical) ? 0 : slot;
    }
    if (slot <= 0x7A && gui::RemappedButtonEvent(slot) != 0) {   // A B X Y LB RB Back
        gui::RequestRemap(slot);
        return 0;
    }
    if (inputClass == kClassPC) {
        namespace hud = kmrp::hud;
        switch (slot) {
            case kSlotButton0:
                kmrp::g_requests.interact = now;
                hud::RequestActivate();
                break;
            case kSlotButton1: hud::RequestRelease(); break;
            case kSlotButton0 + 2: hud::RequestDisengage(); break;   // X
            case kSlotButton0 + 3: hud::RequestClearOne(); break;    // Y
        }
    }
    return slot;
}

// ------------------------------------------------------------------------ records

struct Record {             // DIDEVICEOBJECTDATA as the Mac engine lays it out: 0x18 bytes
    std::int32_t code;
    std::int32_t value;
    std::int32_t timestamp;
    std::int32_t sequence;
    std::int64_t appData;
};
static_assert(sizeof(Record) == 0x18, "record size");

const int kBufferBytes = 0x1800;   // what the engine's own GetJoystickBuffer allocates
const int kMaxRecords = kBufferBytes / static_cast<int>(sizeof(Record));

// A stick axis as DirectInput reports it: -32768..32767, Y growing downward. A radial
// deadzone replaces the engine's per-axis one, and what is left is rescaled across the full
// range so the first movement past it starts from a standstill. Returns that drive, 0..1.
const float kStickDeadzone = 0.15f;   // K1_STICK_DEADZONE
float StickToAxes(float x, float y, int* ax, int* ay) {
    const float m = std::sqrt(x * x + y * y);
    if (m <= kStickDeadzone) { *ax = *ay = 0; return 0; }
    const float drive = std::fmin(1.0f, (m - kStickDeadzone) / (1.0f - kStickDeadzone));
    *ax = static_cast<int>(std::lround(x * drive / m * 32767.0f));
    *ay = static_cast<int>(std::lround(-y * drive / m * 32767.0f));
    return drive;
}

bool SlotPressed(int slot, const kmrp::PadState& p) {
    using namespace kmrp;
    switch (slot) {
        case 0x74: return p.buttons & kPadA;
        case 0x75: return p.buttons & kPadB;
        case 0x76: return p.buttons & kPadX;
        case 0x77: return p.buttons & kPadY;
        case 0x78: return p.buttons & kPadLB;
        case 0x79: return p.buttons & kPadRB;
        case 0x7A: return p.buttons & kPadBack;
        case 0x7B: return p.lt > 0.25f;   // K1_TRIGGER_THRESHOLD, 60 of 255
        case kSlotStart: return p.buttons & kPadStart;
        case 0x7D: return p.rt > 0.25f;
        case 0x7E: return p.buttons & kPadR3;
        case 0x7F: return p.buttons & kPadUp;
        case 0x80: return p.buttons & kPadLeft;
        case 0x81: return p.buttons & kPadDown;
        case 0x82: return p.buttons & kPadRight;
    }
    return false;
}

}  // namespace

// The detour at CExoInputInternal::GetEvents' entry (0x100356276), once per input poll.
extern "C" __attribute__((visibility("default"))) void KmrpControllerTick(void* input) {
    if (!input) return;
    if (input != g_input) {
        g_input = input;
        g_announced = false;
        g_heldDigital = 0;
        std::memset(g_sentAs, 0, sizeof g_sentAs);
    }
    if (!g_announced) {
        g_announced = true;
        Announce(input);
    }
    // Registered again whenever the A description is gone: the engine rebuilds its input
    // object after a movie (docs/controller-native-path.md), and a new object has none.
    if (!DescriptionPresent(input, kEventA)) {
        FixSlotTable(input);
        Register(input);
    }
    EnsurePadState(input);

    int& count = At<int>(input, kDeviceCount);
    if (count < kDevicePad + 1 && PadListsExist(input)) {
        count = kDevicePad + 1;
        Log("device count raised to %d", count);
    }

    // A status line every five seconds by the clock, and one at the start.
    timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    static long polls = 0, lastStatus = -1;
    ++polls;
    if (lastStatus < 0 || now.tv_sec - lastStatus >= 5) {
        lastStatus = now.tv_sec;
        kmrp::Status();
        kmrp::GameplayStatus();
        kmrp::gui::Status();
        kmrp::hud::Status();
        kmrp::prompts::Status();
        kmrp::cues::Status();
        kmrp::rumble::Status();
        Log("polls so far %ld", polls);
    }

    const std::uint32_t before = g_pad.buttons;
    const bool present = kmrp::ReadPad(&g_pad);
    kmrp::device::NotePad(present, g_pad);
    kmrp::g_padButtons = present ? g_pad.buttons : 0;
    if (present != g_padPresent) {
        g_padPresent = present;
        if (present) Log("pad connected: %s", kmrp::PadName());
        else Log("no pad");
    }
    // Every press and release, by name: whether the pad's input reaches the module at all.
    if (present && g_pad.buttons != before) {
        static const struct { std::uint32_t bit; const char* name; } kNames[] = {
            {kmrp::kPadA, "A"}, {kmrp::kPadB, "B"}, {kmrp::kPadX, "X"}, {kmrp::kPadY, "Y"},
            {kmrp::kPadLB, "LB"}, {kmrp::kPadRB, "RB"}, {kmrp::kPadBack, "Back"}, {kmrp::kPadStart, "Start"},
            {kmrp::kPadL3, "L3"}, {kmrp::kPadR3, "R3"}, {kmrp::kPadUp, "Up"}, {kmrp::kPadDown, "Down"},
            {kmrp::kPadLeft, "Left"}, {kmrp::kPadRight, "Right"}};
        char line[256];
        int n = 0;
        for (const auto& k : kNames) {
            if ((g_pad.buttons ^ before) & k.bit)
                n += std::snprintf(line + n, sizeof line - n, " %s %s", k.name, (g_pad.buttons & k.bit) ? "down" : "up");
        }
        Log("pad:%s (sticks %.2f %.2f / %.2f %.2f, triggers %.2f %.2f)", line, g_pad.lx, g_pad.ly, g_pad.rx, g_pad.ry,
            g_pad.lt, g_pad.rt);
    }
}

// Replaces CExoRawInputInternal::GetJoystickBuffer (0x100358cdc): same arguments, same
// buffer, same records. Buttons are sent when they change, as the engine's are; both sticks
// every poll, as the engine's are.
extern "C" __attribute__((visibility("default"))) std::uint64_t KmrpGetJoystickBuffer(void* raw, int index, std::int64_t* buffer) {
    (void)raw;
    if (buffer[0]) operator delete[](reinterpret_cast<void*>(buffer[0]));
    auto* records = static_cast<Record*>(operator new[](kBufferBytes));
    std::memset(records, 0, 0x100);
    buffer[0] = reinterpret_cast<std::int64_t>(records);
    std::int32_t& count = *reinterpret_cast<std::int32_t*>(buffer + 1);
    count = 0;
    if (index != 0 || !g_input) return 0;

    const kmrp::PadState pad = g_padPresent ? g_pad : kmrp::PadState();
    auto emit = [&](int slot, int value) {
        if (count >= kMaxRecords) return;
        Record& r = records[count++];
        r.code = ControlCode(g_input, slot);
        r.value = value;
        r.timestamp = 0;
        r.sequence = 0;
        r.appData = 0;
    };
    const int inputClass = kmrp::engine::CurrentInputClass();
    const std::uint64_t now = kmrp::NowMs();
    for (int slot = 0x74; slot <= 0x82; ++slot) {
        const int i = slot - 0x74;
        const std::uint32_t bit = 1u << i;
        const bool pressed = SlotPressed(slot, pad);
        if (pressed == ((g_heldDigital & bit) != 0)) continue;
        g_heldDigital = pressed ? (g_heldDigital | bit) : (g_heldDigital & ~bit);
        if (pressed) {
            g_sentAs[i] = Route(slot, inputClass, now);
            if (g_sentAs[i]) emit(g_sentAs[i], 1);
        } else if (g_sentAs[i]) {
            emit(g_sentAs[i], 0);
            g_sentAs[i] = 0;
        }
    }
    // A held direction repeats on the screens the ENGINE navigates: its list boxes act on the
    // press only. Released and pressed again, because a second press with no release between
    // is not a new press. Where KMRP owns the direction its own repeat moves the focus.
    std::uint32_t nativeDpad = 0;
    for (int slot = kSlotDpadUp; slot <= kSlotDpadRight; ++slot)
        if (g_sentAs[slot - 0x74]) nativeDpad |= 1u << (slot - 0x74);
    if (nativeDpad) {
        if (nativeDpad != g_dpadRepeatMask) {
            g_dpadRepeatMask = nativeDpad;
            g_dpadRepeatDeadline = now + 400;   // K1_NAV_HOLD_DELAY_MS
        } else if (now >= g_dpadRepeatDeadline) {
            for (int slot = kSlotDpadUp; slot <= kSlotDpadRight; ++slot) {
                if (!(nativeDpad & (1u << (slot - 0x74)))) continue;
                emit(g_sentAs[slot - 0x74], 0);
                emit(g_sentAs[slot - 0x74], 1);
            }
            g_dpadRepeatDeadline = now + 120;   // K1_NAV_REPEAT_MS
        }
    } else {
        g_dpadRepeatMask = 0;
    }
    // The focus layer's direction: the D-pad, else the left stick, one move per press and a
    // repeat while held. Exactly one of the two navigates any screen: where the engine does,
    // the codes above went out and the layer declines.
    {
        static const struct { std::uint32_t bit; int dx, dy; } kDirs[] = {
            {kmrp::kPadUp, 0, -1}, {kmrp::kPadDown, 0, 1}, {kmrp::kPadLeft, -1, 0}, {kmrp::kPadRight, 1, 0}};
        int dx = 0, dy = 0;
        bool edge = false, fromDpad = false;
        for (const auto& d : kDirs) {
            if (!(pad.buttons & d.bit)) continue;
            dx = d.dx;
            dy = d.dy;
            fromDpad = true;
            if (!(g_navButtons & d.bit)) edge = true;
        }
        if (!fromDpad) kmrp::gui::StickNavigation(pad.lx, pad.ly, &dx, &dy, &edge);
        kmrp::gui::RequestNavigation(dx, dy, edge, fromDpad);
        g_navButtons = pad.buttons;
    }
    // L3 has no slot: its flourish is a bridge, asked for here and made on the world's frame.
    const bool l3 = (pad.buttons & kmrp::kPadL3) != 0;
    if (l3 && !g_l3Held) kmrp::g_requests.flourish = now;
    g_l3Held = l3;

    int x, y;
    kmrp::g_analogMagnitude = StickToAxes(pad.lx, pad.ly, &x, &y);
    kmrp::g_leftX = x / 32767.0f;
    kmrp::g_leftY = y / 32767.0f;
    emit(kSlotLeftX, x);
    emit(kSlotLeftY, y);
    // The right stick turns the camera through the engine (gameplay.cpp), as on Windows; its
    // own events, 0x0C and 0x0D, are read only by a debug camera (mode 7) and get no records.
    kmrp::g_rightX = pad.rx;
    kmrp::g_rightY = pad.ry;
    kmrp::g_lastBufferMs = now;
    return g_padPresent ? 1 : 0;
}

namespace {

// Writes `size` bytes at `address` in the game's code, or nothing if `expected` is not there.
bool Patch(std::uintptr_t address, const std::uint8_t* expected, const std::uint8_t* value, std::size_t size) {
    if (std::memcmp(reinterpret_cast<const void*>(address), expected, size) != 0) return false;
    const std::uintptr_t first = address & ~std::uintptr_t(0xFFF);
    const std::uintptr_t last = (address + size + 0xFFF) & ~std::uintptr_t(0xFFF);
    if (vm_protect(mach_task_self(), first, last - first, FALSE,
                   VM_PROT_READ | VM_PROT_WRITE | VM_PROT_COPY) != KERN_SUCCESS) return false;
    std::memcpy(reinterpret_cast<void*>(address), value, size);
    vm_protect(mach_task_self(), first, last - first, FALSE, VM_PROT_READ | VM_PROT_EXECUTE);
    return true;
}

__attribute__((constructor)) void InstallController() {
    // The module is linked whole whatever the player chose; with the controller option off its
    // hooks are not installed, and what it installs on its own is left out here.
    if (!kmrp::ControllerOption()) { Log("the controller option is off"); return; }
    // jmp qword ptr [rip+0]; <KmrpGetJoystickBuffer>
    std::uint8_t jump[14] = {0xFF, 0x25, 0, 0, 0, 0};
    const std::uint64_t target = reinterpret_cast<std::uint64_t>(&KmrpGetJoystickBuffer);
    std::memcpy(jump + 6, &target, 8);
    if (Patch(kGetJoystickBuffer, kGetJoystickBufferPrologue, jump, sizeof jump))
        Log("GetJoystickBuffer replaced");
    else
        Log("GetJoystickBuffer at 0x%lx holds other bytes; the pad stays with the game's own reader",
            static_cast<unsigned long>(kGetJoystickBuffer));
    kmrp::gui::Install();
}

}  // namespace
