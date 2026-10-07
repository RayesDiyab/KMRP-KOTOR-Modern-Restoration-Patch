// KMRP for macOS, controller support: which device the player is on, and what follows from it
// (prompts.cpp): the button badges on the screens, and the parked, hidden cursor.
#pragma once

#include <cstddef>

namespace kmrp {

struct PadState;

namespace device {

// The pad, from each input poll: whether one is answering, and whether it was used. Use is a
// button, a trigger past a light pull or a stick past 0.35, the Windows module's test; a pad
// at rest is not use, so its drift cannot hide the mouse.
void NotePad(bool present, const PadState& pad);

// Whether the pad is what the player is using (IsControllerInputActiveK1): the device last
// used, or, before any has been, whether a pad is there.
bool PadInUse();

}  // namespace device

namespace prompts {

// The GUI's frame (KmrpGuiFrame): the badges brought in step with the screen, the focus, the
// device and the pad's family, and the cursor parked or given back.
void Frame();

// One log line on what the prompt layer did.
void Status();

// The letter of the pad's art family (p Xbox, s PlayStation, n Nintendo, d Steam), which
// replaces the fourth letter of the Xbox art's resrefs.
char FamilyLetter();

// The Controller Layout entry's A (layout.cpp), painted as the tables' badges are
// (KmrpPaintLayoutEntryPromptK1).
void PaintLayoutEntry(void* button, bool shown);

}  // namespace prompts

namespace cues {

// The GUI cues (cues.cpp), from the prompt layer's frame: shown or hidden with the device.
void Update();

// The cue label bound to a panel that follows the control at `follow`, or null (KmrpGuiCueK1).
void* Following(void* panel, std::size_t follow);

// One log line on the cues.
void Status();

}  // namespace cues
}  // namespace kmrp
