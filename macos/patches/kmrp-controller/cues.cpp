// KMRP for macOS, controller support: the GUI cues, the pad's button drawn beside a control
// that has no button of its own to carry a badge: LT and RT on the in-game menu's tab strip, R3
// on the four screens about a party member, X on Abilities' sub-tabs, X and Y beside the HUD's
// combat buttons.
//
// The Mac port of K1NativeJoystick.cpp's cues (K1_GUI_CUES, BindOneCueK1, ForgetGuiCuesK1,
// UpdateGuiCuesK1), with the same rules. Each cue is a CSWGuiLabel that KMRP's resource build
// adds to the panel's .gui (LBL_KMRP*: tools/prepare_universal_resources.py), bound by its tag
// while the panel still has the .gui, as the panel's own controls are, and shown only while the
// pad is the device in use. The art is the Xbox set's; the pad's family letter replaces its
// fourth letter, as for the badges.
//
// On the Mac: CSWGuiPanel::StopLoadFromLayout is 0x10049D986 (Windows 0x0040B8F0, "ReleaseGff"),
// called last by every panel constructor and first by the base destructor; the panel's .gui is at
// +0x40 (Windows +0x2C); InitControl is 0x10049E476 and keeps the control's id at +0x74 (Windows
// +0x50); a CSWGuiLabel is 0x198 bytes (Windows 0x140), built by 0x1004A54AA, its border at +0x88
// with its params 0x18 in, whose fill resref is at +0x3D (a CResRef is 17 bytes here); and its
// deleting destructor is the vtable's second entry (the Itanium ABI's D0).
#include "overlays.h"
#include "prompts.h"

#include "layout.h"

#include "engine.h"
#include "pad.h"
#include "xbox_hud.h"

#include <mach/mach.h>
#include <mach/mach_vm.h>

#include <cstdint>
#include <cstring>
#include <new>

namespace kmrp {
namespace cues {
namespace {

using engine::At;

using LabelCtorFn = void (*)(void* label);
using InitControlFn = void (*)(void* panel, void* control, void* tag, int add);
using ExoStringCtorFn = void (*)(void* string, const char* text);
using ExoStringDtorFn = void (*)(void* string);
using SetFillImageFn = void (*)(void* params, const void* resref, int force);
using DeletingDtorFn = void (*)(void* object);

const auto LabelCtor = reinterpret_cast<LabelCtorFn>(0x1004a54aaUL);
const auto InitControl = reinterpret_cast<InitControlFn>(0x10049e476UL);
const auto ExoStringCtor = reinterpret_cast<ExoStringCtorFn>(0x10034cca8UL);
const auto ExoStringDtor = reinterpret_cast<ExoStringDtorFn>(0x10034cdf2UL);
const auto SetFillImage = reinterpret_cast<SetFillImageFn>(0x1004a17c2UL);

const std::size_t kLabelSize = 0x198;
const std::size_t kLabelBorderParams = 0x88 + 0x18, kParamsFill = 0x3d, kResRefBytes = 17;
const std::uintptr_t kBasePanelVtable = 0x1005b3730UL;   // CSWGuiPanel
const std::size_t kPanelGff = 0x40, kPanelControls = 0x30, kPanelControlCount = 0x38;
const std::size_t kControlId = 0x74, kControlFlags = 0x68;
const std::uint8_t kControlVisible = 0x02;
// CSWGuiMainInterface: BTN_CLEARALL, which the X cue follows, and LBL_CMBTMODEMSG, which it
// follows with the Xbox-style HUD (the HUD's constructor, 0x100232DA0, binds it at +0x9300).
const std::size_t kHudClearAll = 0x8f28, kHudCombatMessage = 0x9300;

// K1_GUI_CUES: which cue belongs on which panel, by class, and the control whose visibility it
// copies (0 for a cue shown whenever the pad is in use).
// `reference` is the control of the game's own layout the build placed the cue beside: the cue
// is put where its layout file has it relative to that control, as the control is now.
struct Binding {
    std::uintptr_t vtable;
    const char* tag;
    std::size_t follow;
    const char* reference;
};
const Binding kBindings[] = {
    // R3 changes the party member these four are about.
    {0x1005a5f80UL, "LBL_KMRPR3", 0, "BTN_CHANGE1"},     // CSWGuiInGameAbilities
    {0x1005a5f80UL, "LBL_KMRPSWAP", 0, "BTN_EXIT"},   //   X cycles its Skills / Powers / Feats
    {0x1005ad790UL, "LBL_KMRPR3", 0, "BTN_CHANGE1"},     // CSWGuiInGameCharacter
    {0x1005ab508UL, "LBL_KMRPR3", 0, "BTN_CHANGE1"},     // CSWGuiInGameEquip
    {0x1005a75c0UL, "LBL_KMRPR3", 0, "BTN_CHANGE1"},     // CSWGuiInGameInventory
    // LT and RT move along the in-game menu's tab strip (top.gui).
    {0x1005ae6a0UL, "LBL_KMRPLT", 0, "BTN_EQU"},     // CSWGuiInGameMenu
    {0x1005ae6a0UL, "LBL_KMRPRT", 0, "BTN_OPT"},
    // Y and X beside the HUD's combat buttons, each shown only while its button is:
    // BTN_CLEARONE (+0x8AA8) and BTN_CLEARALL (+0x8F28), hud.cpp's.
    {0x1005a6220UL, "LBL_KMRPY", 0x8aa8, nullptr}, // CSWGuiMainInterface
    {0x1005a6220UL, "LBL_KMRPX", 0x8f28, nullptr},
};

struct Cue {
    void* panel;
    void* control;
    int id;
    std::size_t follow;
};
Cue g_cues[16] = {};

struct Counters {
    unsigned long installed = 0, rejected = 0, forgotten = 0, toggles = 0, recoloured = 0;
} g_count;

bool LooksLikePointer(const void* p) {
    const auto v = reinterpret_cast<std::uintptr_t>(p);
    return v >= 0x100000 && v < 0x800000000000ULL;
}

std::uintptr_t VtableOf(void* object) {
    return LooksLikePointer(object) ? *reinterpret_cast<std::uintptr_t*>(object) : 0;
}

// A read that reports a hole instead of faulting (IsReadableK1's part).
bool SafeRead(const void* address, void* out, std::size_t size) {
    mach_vm_size_t got = 0;
    return mach_vm_read_overwrite(mach_task_self(), reinterpret_cast<mach_vm_address_t>(address), size,
                                  reinterpret_cast<mach_vm_address_t>(out), &got) == KERN_SUCCESS &&
           got == size;
}

// GuiCueStillLiveK1: the panel still holds this control at its id. A second line of defence:
// cues are forgotten when their panel is destroyed (Forget), and nothing is read here until the
// memory is known to be there.
bool StillLive(const Cue& cue) {
    if (!cue.panel || !cue.control || cue.id < 0) return false;
    void** controls = nullptr;
    int count = 0;
    if (!SafeRead(static_cast<char*>(cue.panel) + kPanelControls, &controls, sizeof controls) ||
        !SafeRead(static_cast<char*>(cue.panel) + kPanelControlCount, &count, sizeof count) || cue.id >= count)
        return false;
    void* held = nullptr;
    return SafeRead(controls + cue.id, &held, sizeof held) && held == cue.control;
}

struct Rect { int left, top, width, height; };
const std::size_t kControlExtent = 0x08;

void SetExtent(void* control, const Rect& rect) {
    const std::uintptr_t vtable = VtableOf(control);
    if (vtable) reinterpret_cast<void (*)(void*, const Rect*)>(*reinterpret_cast<std::uintptr_t*>(vtable + 0x10))(control, &rect);
}

// PlaceCueByReferenceK1: a cue's rectangle is its layout file's, and the screen may have been
// laid out again since by another patch. The control the build placed the cue beside is loaded
// once more into a label the panel never holds (InitControl's last argument 0 files nothing),
// which gives that control's rectangle in the file and its id, and so the live control; the cue
// is put where the file has it relative to that control, as the control is now, scaled by the
// smaller of the two factors so that it keeps its shape. Returns the live control, or null.
void* PlaceByReference(void* panel, void* cue, const char* reference) {
    void* probe = ::operator new(kLabelSize, std::nothrow);
    if (!probe) return nullptr;
    std::memset(probe, 0, kLabelSize);
    LabelCtor(probe);
    At<int>(probe, kControlId) = -1;
    void* name[2] = {nullptr, nullptr};
    ExoStringCtor(name, reference);
    InitControl(panel, probe, name, 0);
    ExoStringDtor(name);
    const int id = At<int>(probe, kControlId);
    void** const controls = At<void**>(panel, kPanelControls);
    const int count = At<int>(panel, kPanelControlCount);
    void* live = nullptr;
    if (LooksLikePointer(controls) && id >= 0 && id < count && controls[id] != probe && controls[id] != cue &&
        LooksLikePointer(controls[id]))
        live = controls[id];
    if (live) {
        const Rect file = At<Rect>(probe, kControlExtent), now = At<Rect>(live, kControlExtent), was = At<Rect>(cue, kControlExtent);
        const bool moved = file.left != now.left || file.top != now.top || file.width != now.width || file.height != now.height;
        if (moved && file.width > 0 && file.height > 0 && now.width > 0 && now.height > 0) {
            const double sx = double(now.width) / file.width, sy = double(now.height) / file.height;
            const double scale = sx < sy ? sx : sy;
            const double cx = now.left + (was.left + was.width / 2.0 - file.left) * sx;
            const double cy = now.top + (was.top + was.height / 2.0 - file.top) * sy;
            const int width = static_cast<int>(was.width * scale + 0.5), height = static_cast<int>(was.height * scale + 0.5);
            if (width > 0 && height > 0)
                SetExtent(cue, {static_cast<int>(cx - width / 2.0 + 0.5), static_cast<int>(cy - height / 2.0 + 0.5), width, height});
        }
    }
    const std::uintptr_t vtable = VtableOf(probe);
    if (vtable) reinterpret_cast<DeletingDtorFn>(*reinterpret_cast<std::uintptr_t*>(vtable + 8))(probe);
    return live;
}

// Where three of the cues stand, as the maintainer set them on Windows (2026-10-05 and 06,
// BindOneCueK1): nothing is a fixed place, each is worked out from the live controls.
void Adjust(void* panel, void* cue, const char* tag, void* beside) {
    Rect at = At<Rect>(cue, kControlExtent);
    if (std::strcmp(tag, "LBL_KMRPSWAP") == 0) {
        // The sub-tab cue: 1.2 times its size about the middle of its right edge.
        const int width = (at.width * 12 + 5) / 10, height = (at.height * 12 + 5) / 10;
        at = {at.left + at.width - width, at.top - (height - at.height) / 2, width, height};
    } else if (std::strcmp(tag, "LBL_KMRPR3") == 0) {
        // The party cue: an eighth of its size from the portrait on its left, or in the middle
        // of the gap where the next portrait leaves less room, on the portraits' middle line.
        if (beside) {
            const Rect portrait = At<Rect>(beside, kControlExtent);
            const int middle = at.left + at.width / 2;
            int leftEdge = 0, rightEdge = 0;
            bool hasLeft = false, hasRight = false;
            void** const controls = At<void**>(panel, kPanelControls);
            const int count = At<int>(panel, kPanelControlCount);
            for (int i = 0; LooksLikePointer(controls) && i < count && i < 512; ++i) {
                void* control = controls[i];
                if (!LooksLikePointer(control) || control == cue) continue;
                const Rect r = At<Rect>(control, kControlExtent);
                if (r.width != portrait.width || r.height != portrait.height) continue;
                const int off = r.top - portrait.top;
                if ((off < 0 ? -off : off) > portrait.height / 4) continue;
                if (r.left + r.width / 2 <= middle) {
                    if (!hasLeft || r.left + r.width > leftEdge) leftEdge = r.left + r.width;
                    hasLeft = true;
                } else {
                    if (!hasRight || r.left < rightEdge) rightEdge = r.left;
                    hasRight = true;
                }
            }
            if (hasLeft) {
                int gap = at.width / 8;
                const int room = rightEdge - leftEdge;
                if (hasRight && room >= at.width && (room - at.width) / 2 < gap) gap = (room - at.width) / 2;
                if (!hasRight || room >= at.width) at.left = leftEdge + gap;
            }
            at.top = portrait.top + (portrait.height - at.height + 1) / 2;
        } else {
            at.left -= at.width / 3 - at.width / 8;
        }
    } else if (beside && (std::strcmp(tag, "LBL_KMRPLT") == 0 || std::strcmp(tag, "LBL_KMRPRT") == 0)) {
        // LT and RT, arrows since 2026-10-05 (tools/build_tab_arrows.py): the arrow's flat side
        // as tall as a tab's box (35 of the tab's 40 units; the flat side is 76% of the cue's
        // square, so the square is 1.15 times the tab's height), level with the box (its
        // middle is 21.5 units down the tab), and as far from the strip as two tabs are from
        // each other (a tab is 52 wide and the next begins 62 on, each frame one unit inside
        // its rectangle; the arrow's flat side is 3% inside its square).
        const Rect tab = At<Rect>(beside, kControlExtent);
        const int size = (tab.height * 115 + 50) / 100;
        at.top = tab.top + (tab.height * 43 + 40) / 80 - size / 2;
        at.width = at.height = size;
        const int gap = (tab.width * 10 + 26) / 52 + (tab.width + 26) / 52;
        const int edge = (at.width * 3 + 50) / 100;
        at.left = tag[8] == 'L' ? tab.left - gap + edge - at.width : tab.left + tab.width + gap - edge;
    } else {
        return;
    }
    if (at.width > 0 && at.height > 0) SetExtent(cue, at);
}

// BindOneCueK1: a label, bound by tag onto a panel that still has its .gui, hidden until the pad
// is in use. A tag the .gui does not have leaves the label unreachable, and it is not freed: the
// panel may hold it.
void BindOne(void* panel, const char* tag, std::size_t follow, const char* reference) {
    void* control = ::operator new(kLabelSize, std::nothrow);
    if (!control) return;
    std::memset(control, 0, kLabelSize);
    LabelCtor(control);
    void* name[2] = {nullptr, nullptr};   // CExoString: { char* data; length }
    ExoStringCtor(name, tag);
    InitControl(panel, control, name, 1);
    ExoStringDtor(name);

    const int id = At<int>(control, kControlId);
    void** controls = At<void**>(panel, kPanelControls);
    const int count = At<int>(panel, kPanelControlCount);
    if (!LooksLikePointer(controls) || id < 0 || id >= count || controls[id] != control) {
        ++g_count.rejected;
        return;
    }
    Adjust(panel, control, tag, reference ? PlaceByReference(panel, control, reference) : nullptr);
    At<std::uint8_t>(control, kControlFlags) &= static_cast<std::uint8_t>(~kControlVisible);
    for (int pass = 0; pass < 2; ++pass) {
        for (Cue& cue : g_cues) {
            if (pass == 0 ? cue.panel != nullptr : StillLive(cue)) continue;
            cue = {panel, control, id, follow};
            ++g_count.installed;
            return;
        }
    }
    ++g_count.rejected;   // the table is full: drawn as the .gui has it, never toggled
}

// ForgetGuiCuesK1: a panel's end. The base destructor calls StopLoadFromLayout with CSWGuiPanel's
// own vtable back in place and the .gui long released, before the control array goes; the
// labels are KMRP's, which the array refers to but does not own, so they are freed here, and
// only while the panel still holds each at its id (anything else means the slot was reused, and
// a leak is safer than a double free).
void Forget(void* panel) {
    if (VtableOf(panel) != kBasePanelVtable || At<void*>(panel, kPanelGff) != nullptr) return;
    for (Cue& cue : g_cues) {
        if (cue.panel != panel) continue;
        void** controls = At<void**>(panel, kPanelControls);
        const int count = At<int>(panel, kPanelControlCount);
        if (LooksLikePointer(controls) && cue.id >= 0 && cue.id < count && controls[cue.id] == cue.control) {
            controls[cue.id] = nullptr;
            const std::uintptr_t vtable = VtableOf(cue.control);
            if (vtable) reinterpret_cast<DeletingDtorFn>(*reinterpret_cast<std::uintptr_t*>(vtable + 8))(cue.control);
        }
        cue = {};
        ++g_count.forgotten;
    }
}

// InstallGuiCuesK1: whatever cues this panel is owed, while it still has its .gui.
void Install(void* panel) {
    const std::uintptr_t vtable = VtableOf(panel);
    if (!vtable || !LooksLikePointer(At<void*>(panel, kPanelGff))) return;
    for (const Binding& b : kBindings) {
        if (b.vtable != vtable) continue;
        std::size_t follow = b.follow;
        // With the Xbox-style HUD the X cue is the button in the combat-mode message
        // (xbox_hud.cpp), so it is shown while that message is.
        if (follow == kHudClearAll && xboxhud::Enabled()) follow = kHudCombatMessage;
        BindOne(panel, b.tag, follow, b.reference);
    }
}

// MatchCueFamilyK1: the .gui names the Xbox art; the pad's family letter goes in its place.
void MatchFamily(void* label) {
    char* params = static_cast<char*>(label) + kLabelBorderParams;
    char resref[32] = {};
    std::memcpy(resref, params + kParamsFill, kResRefBytes);
    const char wanted = prompts::FamilyLetter();
    if (std::strncmp(resref, "kmr", 3) != 0 || resref[3] == wanted) return;
    resref[3] = wanted;
    SetFillImage(params, resref, 1);
    ++g_count.recoloured;
}

}  // namespace

// UpdateGuiCuesK1: shown while the pad is in use, and a cue that follows a control only while
// that control is drawn too.
void Update() {
    const bool visible = device::PadInUse();
    for (Cue& cue : g_cues) {
        if (!cue.panel) continue;
        if (!StillLive(cue)) { cue = {}; continue; }
        bool shown = visible;
        if (shown && cue.follow != 0)
            shown = (At<std::uint8_t>(cue.panel, cue.follow + kControlFlags) & kControlVisible) != 0;
        std::uint8_t& flags = At<std::uint8_t>(cue.control, kControlFlags);
        const std::uint8_t wanted = shown ? (flags | kControlVisible) : (flags & ~kControlVisible);
        if (wanted != flags) {
            flags = wanted;
            ++g_count.toggles;
        }
        if (shown) MatchFamily(cue.control);
    }
}

void* Following(void* panel, std::size_t follow) {
    for (const Cue& cue : g_cues)
        if (cue.panel == panel && cue.follow == follow && StillLive(cue)) return cue.control;
    return nullptr;
}

void Status() {
    int live = 0;
    for (const Cue& cue : g_cues) if (cue.panel) ++live;
    Log("cues: %lu bound (%lu rejected), %d held, %lu forgotten with their panels, %lu shown or hidden, "
        "%lu recoloured",
        g_count.installed, g_count.rejected, live, g_count.forgotten, g_count.toggles, g_count.recoloured);
}

}  // namespace cues
}  // namespace kmrp

// CSWGuiPanel::StopLoadFromLayout, entry (0x10049D986; Windows NativePanelReleaseGffK1 at
// 0x0040B8F0): the last instant a panel under construction can take a control by tag, and the
// first thing its base destructor does. The Controller Layout entry and the confirm A are bound
// here too (layout.cpp), before the cues, in Windows' order.
extern "C" __attribute__((visibility("default"))) void KmrpPanelReleaseGff(void* panel) {
    if (!kmrp::cues::LooksLikePointer(panel)) return;
    kmrp::layout::ReleaseGff(panel);
    kmrp::xboxhud::Forget(panel);
    kmrp::cues::Forget(panel);
    kmrp::overlays::Forget(panel);
    kmrp::cues::Install(panel);
}
