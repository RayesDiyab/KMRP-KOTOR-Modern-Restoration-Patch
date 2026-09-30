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
#include "prompts.h"

#include "layout.h"

#include "engine.h"
#include "pad.h"

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

// K1_GUI_CUES: which cue belongs on which panel, by class, and the control whose visibility it
// copies (0 for a cue shown whenever the pad is in use).
struct Binding {
    std::uintptr_t vtable;
    const char* tag;
    std::size_t follow;
};
const Binding kBindings[] = {
    // R3 changes the party member these four are about.
    {0x1005a5f80UL, "LBL_KMRPR3", 0},     // CSWGuiInGameAbilities
    {0x1005a5f80UL, "LBL_KMRPSWAP", 0},   //   X cycles its Skills / Powers / Feats
    {0x1005ad790UL, "LBL_KMRPR3", 0},     // CSWGuiInGameCharacter
    {0x1005ab508UL, "LBL_KMRPR3", 0},     // CSWGuiInGameEquip
    {0x1005a75c0UL, "LBL_KMRPR3", 0},     // CSWGuiInGameInventory
    // LT and RT move along the in-game menu's tab strip (top.gui).
    {0x1005ae6a0UL, "LBL_KMRPLT", 0},     // CSWGuiInGameMenu
    {0x1005ae6a0UL, "LBL_KMRPRT", 0},
    // Y and X beside the HUD's combat buttons, each shown only while its button is:
    // BTN_CLEARONE (+0x8AA8) and BTN_CLEARALL (+0x8F28), hud.cpp's.
    {0x1005a6220UL, "LBL_KMRPY", 0x8aa8}, // CSWGuiMainInterface
    {0x1005a6220UL, "LBL_KMRPX", 0x8f28},
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

// BindOneCueK1: a label, bound by tag onto a panel that still has its .gui, hidden until the pad
// is in use. A tag the .gui does not have leaves the label unreachable, and it is not freed: the
// panel may hold it.
void BindOne(void* panel, const char* tag, std::size_t follow) {
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
    for (const Binding& b : kBindings)
        if (b.vtable == vtable) BindOne(panel, b.tag, b.follow);
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
    kmrp::cues::Forget(panel);
    kmrp::cues::Install(panel);
}
