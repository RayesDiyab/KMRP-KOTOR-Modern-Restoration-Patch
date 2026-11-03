// KMRP for macOS, controller support: Pazaak's two screens and class selection's Select with the
// pad (pazaak.cpp).
#pragma once

namespace kmrp {
namespace pazaak {

// A panel as it is built, with its layout still loaded (KmrpPanelReleaseGff): the table's two
// action buttons, the side deck's switch and glyphs, class selection's Select.
void Install(void* panel);

// A panel's end, before its labels are freed (KmrpPanelReleaseGff).
void Forget(void* panel);

// The GUI's frame: what those screens show for the device in use.
void Update();

// A press's pulse on the table's Play or Flip box, which the native handlers cannot reach: they
// flash the PC's own unused members (PazaakActionFlashK1).
void ActionFlash(void* panel, bool flip);

}  // namespace pazaak
}  // namespace kmrp
