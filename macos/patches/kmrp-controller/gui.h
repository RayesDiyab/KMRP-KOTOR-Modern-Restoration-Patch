// KMRP for macOS, controller support: menus (gui.cpp), as the input hook asks about them.
//
// Everything here that native.cpp calls from inside the input poll only reads memory; the
// engine is called from the GUI's own frame (KmrpGuiFrame), as K1NativeJoystick.cpp does.
#pragma once

namespace kmrp {
namespace gui {

// Whether KMRP's focus layer takes the D-pad on what is in front (KmrpOwnsDirectionsK1): when
// it does, the native direction codes must not also go out, or focus moves twice.
bool OwnsDirections(bool vertical);

// The event a screen redefines this pad slot to (RemappedButtonEventK1), or 0. A remapped
// press sends no native record; RequestRemap has the GUI frame act on it instead.
int RemappedButtonEvent(int slot);
void RequestRemap(int slot);

// Whether the in-game menu's tab strip is open (TabBarPanelK1): Start then closes it.
bool TabBarOpen();

// Whether this panel is the in-game menu's tab strip, which carries no prompts of its own:
// the prompts are the screen's behind it (prompts.cpp).
bool IsTabBar(void* panel);

// A direction for the focus layer, from the D-pad or the left stick (RequestNavigationK1):
// one move on the press, then a repeat while held.
void RequestNavigation(int dx, int dy, bool edge, bool fromDpad);

// The left stick's menu direction, latched with hysteresis (UpdateStickNavigationK1).
void StickNavigation(float x, float y, int* dx, int* dy, bool* edge);

// One log line on what the menus did.
void Status();

// The module's constructor: the echo guard and the confirm guards.
void Install();

}  // namespace gui
}  // namespace kmrp
