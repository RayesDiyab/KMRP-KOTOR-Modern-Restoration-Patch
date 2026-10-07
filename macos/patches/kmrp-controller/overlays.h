// KMRP for macOS, the controller patch: a badge drawn on a label of its own where its button
// has another shape than the badge was made for (overlays.cpp).
#pragma once

#include <cstdint>

namespace kmrp {
namespace overlays {

// Puts the badge `resref` (16 characters at most, the pad's family already in it) on a label
// beside the button's caption when the button's fill area is not the shape the badge was made
// for. True when it did: the button itself is then to carry no badge. False when the button has
// its made-for shape (any label it had is hidden) or the badge has no known shape.
bool Show(void* panel, void* button, const char* resref);

// Level Up and Auto Level Up, whose badges were their button's own box with the glyph on it.
// IsBacked says whether `resref` is one of the two; ShowBacked leaves the box to the button (the
// caller puts it on both borders), draws the glyph from a plain badge on a label at the button's
// left end, and makes the button wide enough for badge and caption. True when it did.
bool IsBacked(const char* resref);
bool ShowBacked(void* panel, void* button, const char* resref);

// The button's label hidden and its caption and its own rectangle put back as they were.
void Hide(void* button);

// What a badge's place depends on: the button's rectangle, whether it is drawn, and its caption.
std::uint32_t Signature(void* button);

// Each frame, for the panel in front: a label is drawn only while its button is.
void Sync(void* panel);

// A panel's end: its labels freed.
void Forget(void* panel);

void Status();

}  // namespace overlays
}  // namespace kmrp
