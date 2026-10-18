#pragma once
// Controller remapping's rules, kept apart from the engine so they can be tested
// (testing/regression/Test-ButtonRemap.py). The runtime is K1ButtonRemap.cpp; the
// screen is the Controller Layout (K1ControllerLayout.cpp).
//
// What the maintainer decided (2026-10-18), from the mockups:
//   - Remappable: the four face buttons, both bumpers, both triggers and each stick's
//     click. Fixed: moving (left stick), the camera (right stick), the D-pad (the
//     action bar and navigation), Start and Back. Menus keep every button where it is;
//     only what a button does in the world follows the remap.
//   - No swapping: giving a button to an action takes it from the action that had it,
//     and that action is left without one until it gets another. A layout can be saved
//     only when every action has a button.
//
// An action is named by its default button, which is also the button the rest of the
// controller code knows it by: the HUD's activate is A's, disengaging is X's, and so
// on. So remapping is a translation of the pad's buttons into those default ones, in
// the world only (Translator, below), and nothing downstream changes.
#include <array>
#include <cstdint>
#include <cstring>

namespace KmrpRemap {

enum Button : int { A, B, X, Y, LB, RB, LT, RT, L3, R3, ButtonCount, None = -1 };

// Each button's bit in the pad's button word: XInput's own, with the two triggers
// folded into the two bits XInput leaves unused (0x0400, 0x0800), as the prompt layer
// folds them (vendor/K1XboxControlsXInput.cpp).
constexpr std::uint16_t Mask[ButtonCount] = {
    0x1000, 0x2000, 0x4000, 0x8000, 0x0100, 0x0200, 0x0400, 0x0800, 0x0040, 0x0080};
constexpr std::uint16_t TriggerBits = 0x0400 | 0x0800;
constexpr std::uint16_t RemappableBits =
    0x1000 | 0x2000 | 0x4000 | 0x8000 | 0x0100 | 0x0200 | 0x0400 | 0x0800 | 0x0040 | 0x0080;

// The names a layout is saved with (kmrp-controller.ini, [Controller Remap]): each
// action's key, and each button's value.
constexpr const char* ButtonNames[ButtonCount] = {"A", "B", "X", "Y", "LB", "RB", "LT", "RT", "L3", "R3"};
constexpr const char* ActionKeys[ButtonCount] = {
    "Interact", "ReleaseBar", "Disengage", "UndoAction", "PreviousTarget",
    "NextTarget", "SwitchAlly", "Pause", "Flourish", "FreeLook"};

inline int ButtonByName(const char* name) {
    for (int b = 0; b < ButtonCount; ++b)
        if (name && !_stricmp(name, ButtonNames[b])) return b;
    return None;
}

// Which button each action is on: `button[action]`, or None while it has none (only
// while the layout is being changed; a saved layout is always complete).
struct Mapping {
    std::array<int, ButtonCount> button{};
    Mapping() { for (int a = 0; a < ButtonCount; ++a) button[a] = a; }
    bool operator==(const Mapping& o) const { return button == o.button; }
    bool operator!=(const Mapping& o) const { return button != o.button; }

    // The action on a button, or None.
    int ActionOn(int physical) const {
        for (int a = 0; a < ButtonCount; ++a)
            if (button[a] == physical) return a;
        return None;
    }
    // Every action on a button of its own.
    bool Complete() const {
        bool used[ButtonCount] = {};
        for (int a = 0; a < ButtonCount; ++a) {
            const int b = button[a];
            if (b < 0 || b >= ButtonCount || used[b]) return false;
            used[b] = true;
        }
        return true;
    }
    bool IsDefault() const { return *this == Mapping{}; }
    // The action gets the button; the action that had it is left without one.
    // Returns that action, or None.
    int Assign(int action, int physical) {
        if (action < 0 || action >= ButtonCount || physical < 0 || physical >= ButtonCount) return None;
        int displaced = None;
        for (int a = 0; a < ButtonCount; ++a)
            if (a != action && button[a] == physical) { button[a] = None; displaced = a; }
        button[action] = physical;
        return displaced;
    }
};

// A layout being changed on the Controller Layout screen, whose rows are BUTTONS: each
// row's line on the pad's drawing points at one button, so a row always shows the
// action on its button, and an action moved to another button moves to that button's
// row (the maintainer's choice, 2026-10-18, so the drawing never contradicts itself).
// An action left without a button waits in the row of the button that came free, so
// there is somewhere to show it: the row the moving action left. There are as many
// actions as buttons, so every free button always has exactly one action waiting in
// its row, and the layout is complete again when none waits.
struct Editor {
    Mapping mapping;
    std::array<int, ButtonCount> waiting{};   // per button, the action waiting in its row, or None
    Editor() { waiting.fill(None); }
    explicit Editor(const Mapping& start) : mapping(start) { waiting.fill(None); }

    // The action a row shows: the one on its button, else the one waiting there.
    int ActionInRow(int row) const {
        const int on = mapping.ActionOn(row);
        return on != None ? on : waiting[row];
    }
    bool Waiting(int row) const { return mapping.ActionOn(row) == None && waiting[row] != None; }
    bool Complete() const { return mapping.Complete(); }

    // The action in `row` is given `button`. The action that had `button` (on it, or
    // waiting in its row) waits in `row`, which its own action has left.
    void Assign(int row, int button) {
        if (row < 0 || row >= ButtonCount || button < 0 || button >= ButtonCount) return;
        const int action = ActionInRow(row);
        if (action == None) return;
        if (button == row) {                       // its own button: no longer waiting
            mapping.button[action] = row;
            waiting[row] = None;
            return;
        }
        int displaced = mapping.ActionOn(button);
        if (displaced == None) displaced = waiting[button];
        waiting[row] = None;
        waiting[button] = None;
        mapping.button[action] = button;
        if (displaced != None && displaced != action) {
            mapping.button[displaced] = None;
            waiting[row] = displaced;
        }
    }
    void Reset() { *this = Editor{}; }
};

// The pad's buttons as the rest of the controller code should see them. In the
// world each pressed button becomes the default button of the action it carries; in
// menus, conversations and minigames every button is itself. Decided at the press
// and kept until the release, so a press that opens a menu (or closes one) releases
// the same button it pressed: deciding again at the release would leave a button
// held that nothing lets go of.
struct Translator {
    std::array<int, ButtonCount> held{};   // per pad button, the button it was pressed as
    std::uint16_t last = 0;
    Translator() { held.fill(None); }

    std::uint16_t Apply(std::uint16_t pad, bool world, const Mapping& mapping) {
        std::uint16_t out = static_cast<std::uint16_t>(pad & ~RemappableBits);
        const bool usable = mapping.Complete();
        for (int p = 0; p < ButtonCount; ++p) {
            const bool down = (pad & Mask[p]) != 0, was = (last & Mask[p]) != 0;
            if (down && !was) held[p] = world && usable ? mapping.ActionOn(p) : p;
            if (!down) held[p] = None;
            if (down && held[p] != None) out |= Mask[held[p]];
        }
        last = pad;
        return out;
    }
};

// Each button's picture wherever a prompt in the world names it: kmr?rm<code>, the
// family's letter in place of ?, made for every family by
// tools/build_controller_layout.py (REMAP_GLYPHS, in build_art, which KMRP's resources
// and the controller patch both run) with the same art as the HUD's other cues; a stick
// click as the pack's click drawing, not the bare stick.
constexpr const char* GlyphCodes[ButtonCount] = {"a", "b", "x", "y", "lb", "rb", "lt", "rt", "l3", "r3"};

// The Controller Layout screen's row for each button (its GLYPH_nn and TEXT_nn); a
// stick click is its stick's row. Must follow LAYOUT in tools/build_controller_layout.py
// (Test-ButtonRemap.py checks it).
constexpr int LayoutRow[ButtonCount] = {11, 10, 9, 8, 1, 6, 0, 5, 3, 12};

}  // namespace KmrpRemap
