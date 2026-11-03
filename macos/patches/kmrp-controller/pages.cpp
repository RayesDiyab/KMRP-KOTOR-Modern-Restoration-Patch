// KMRP for macOS, controller support: what KMRP's own option pages ask this patch. The HUD Size and
// Text Size pages and their entry buttons on Graphics Options are built at run time in KMRP's
// module, so they are in none of this patch's tables of the game's screens; they find these names
// through this module's handle (kmrp-assets/options_pad.h; items 59 and 67, Windows'
// K1NativeJoystick.cpp and K1XboxControls.cpp). Without KMRP nothing calls them.
#include "layout.h"
#include "pad.h"
#include "prompts.h"
#include "state.h"

#include <ApplicationServices/ApplicationServices.h>

// Whether the pad is the device in use.
extern "C" __attribute__((visibility("default"))) int KmrpPadInUseK1() {
    return kmrp::device::PadInUse() ? 1 : 0;
}

// The letter of the pad's art family (p Xbox, s PlayStation, n Nintendo, d Steam).
extern "C" __attribute__((visibility("default"))) char KmrpGlyphLetterK1() {
    return kmrp::prompts::FamilyLetter();
}

// A control kept off the pad's focus, or given back: the buttons the pad presses by itself.
extern "C" __attribute__((visibility("default"))) void KmrpPadFocusSkipK1(void* control, int skipped) {
    kmrp::layout::PadFocusExclude(control, skipped != 0);
}

// The A KMRP's two entry buttons wear while focused, which are Advanced Options' size: Advanced's
// badge, kmrpa_optgfxadvn (FocusOnly, as Advanced).
extern "C" __attribute__((visibility("default"))) void KmrpPaintGraphicsEntryPromptK1(void* button, int shown) {
    kmrp::prompts::PaintGraphicsEntry(button, shown != 0);
}

// Pad A, Return or Space held (ControllerConfirmHeldK1), as the Controller Layout's entry asks it.
extern "C" __attribute__((visibility("default"))) int KmrpControllerConfirmHeldK1() {
    return ((kmrp::g_padButtons & kmrp::kPadA) != 0 ||
            CGEventSourceKeyState(kCGEventSourceStateCombinedSessionState, 36) ||
            CGEventSourceKeyState(kCGEventSourceStateCombinedSessionState, 49)) ? 1 : 0;
}
