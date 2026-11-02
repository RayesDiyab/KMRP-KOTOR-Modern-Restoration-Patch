#pragma once
// What K1XboxControls.cpp gives the rest of the controller module. Each caller had its own
// copy of these (audit S-8), so a changed signature only showed in the running game.
#include <cstddef>
#include <cstdint>
#include <vector>

// The frame's work and what it hears of the keyboard and mouse.
extern "C" void __cdecl KmrpUpdatePromptsK1();
extern "C" void __cdecl KmrpUpdateCursorK1();
extern "C" void __cdecl KmrpNoteKeyboardK1(void* record, int inputDevice);
extern "C" void __cdecl KmrpNoteMouseK1(int mouseX, int mouseY);

// The HUD's action bar.
extern "C" void __cdecl KmrpActionBarApplyK1(void* mainInterface, int dx, int dy, int activate);
extern "C" int __cdecl KmrpActionBarFocusedK1(void* mainInterface);
extern "C" int __cdecl KmrpActionBarHeldK1(void* mainInterface);
extern "C" void __cdecl KmrpActionBarReleaseK1(void* mainInterface);
extern "C" int __cdecl KmrpActionBarStateK1(void* mainInterface);
// Which of the seven slots has the focus (0-2 the target's, 3-6 personal), or -1, whether or
// not another screen is in front of the HUD.
int KmrpHeldActionSlotK1(void* mainInterface);

// The screens.
extern "C" void* __cdecl KmrpDescriptionPaneK1(void* panel);
// A button whose glyph is always shown on its panel, a hint the pad presses by its own button
// and never lands on.
extern "C" int __cdecl KmrpPadHintControlK1(void* panel, void* control);
extern "C" void __cdecl KmrpPaintLayoutEntryPromptK1(void* button, int shown);
bool MessageBoxCancelHasFocusK1(void* panel);
void KmrpQueueLayoutControlK1(void* control);
bool KmrpQueueLayoutPanelK1(void* panel);   // the screen's pictures for the background

// The pictures and the prompts on them.
extern "C" int __cdecl KmrpGlyphPictureK1(const char* glyphName, int* rect, char* out);
const char* KmrpLogicalFillK1(const char* fill);                     // the picture a fill stands for
const char* KmrpDrawnFillK1(const void* params, const char* fill);   // the drawing made of it for a border
// The swoop prompt drawn for this screen's size, its name in `out`.
bool KmrpDrawnPictureK1(const char* name, char out[17]);
bool KmrpWriteDrawnPictureK1(const char* name, const std::vector<std::uint8_t>& sheet, int width, int height);
bool KmrpPicturesSettledK1();   // a frame went by with nothing left to draw
void KmrpStampPictureK1(void* control, std::ptrdiff_t paramsOffset, const char* name);
void KmrpBadgeCentreK1(void* button, bool on);   // glyph and caption centred together
int KmrpCaptionLineWidthK1(void* button);          // the caption on one line, at its scale now; 0 unknown
float KmrpCaptionScaleK1(void* button);            // the scale its string is drawn at; 0 unknown
void KmrpSetCaptionScaleK1(void* button, float scale);
void KmrpForgetBadgeOverlaysK1(void* panel);
void KmrpPromptDimK1(void* button, bool dim);
void KmrpPromptFillK1(void* control, const char* value);
