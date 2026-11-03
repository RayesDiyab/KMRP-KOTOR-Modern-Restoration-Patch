// KMRP for macOS: each native text string fitted to its own box as it is drawn (text_fit.cpp), and
// the list rows that grow with their text (text_rows.cpp). The port of Windows' K1TextLayout and
// K1TextRows. Font objects and the player's chosen sizes are never changed to make one control fit.
#pragma once

#include "../../../src/controller-native/K1TextFitPolicy.h"

namespace kmrp {
namespace textfit {

// The GUI's frame, from kmrp-assets/layout.cpp: the viewport watched, the lists and edit boxes of
// every panel kept to their rules, the pause notice and the conversation's panel placed.
void Frame(void* manager);
// The fonts' metrics changed (a text size, a font, a change of resolution): every string goes back
// to its request and is measured again at its next draw.
void FontsChanged();
// Panels and the controls bound to them by tag, as layout.cpp sees them made.
void TrackPanel(void* panel, const char* resource);
void TrackControl(void* panel, void* control, const char* tag);
void ForgetPanel(void* panel);
void ForgetControl(void* control);
// The control of a tracked panel with this tag, or null.
void* ControlByTag(void* panel, const char* tag);
// The width the container fit has added to a control of `panel` (0 if none), and the end of that
// record, for the layout that puts a panel back to its file.
int Widened(void* panel, void* control);
void ForgetWidened(void* panel);
// `control`'s caption stands on the line its art gives `like`'s.
void CaptionLike(void* control, void* like);
// A texture's picture has just been uploaded (caption_ink.cpp).
void PictureUploaded(const char* name, unsigned glName);

// `wrapper` is a CSWGuiText (or CSWGuiEditText), not its owning control. Scrollable or expanding
// content keeps the requested scale (Flow); a fixed box fits at its draw (Bounded, the default);
// an edit box never shrinks by its caret (Editable).
void Flow(void* wrapper);
void Bounded(void* wrapper);
void Editable(void* wrapper);
// At the requested scale: the wrapped text's height at its box's width, its one-line width, and
// one line's height. 0 where the string cannot be measured.
int NaturalHeight(void* wrapper);
double NaturalWidth(void* wrapper);
double NaturalLineHeight(void* wrapper);
// Changes whenever fonts change, for the row adapter's signatures.
unsigned Generation();

// Rows (text_rows.cpp).
void Rows(void* list);
void RowsForget(void* control);
void RowsViewport(int height);
// The granted popup: rows have just been handed to `list`, and the popup grows with them each frame.
void GrantedFilled(void* list);
void GrantedFrame(void* manager);

// The menu text size and the icon size, percent (text_options.cpp).
int TextSizePercent();
int TextSizeForFont(const char* font);
int IconSizePercent();

}  // namespace textfit
}  // namespace kmrp
