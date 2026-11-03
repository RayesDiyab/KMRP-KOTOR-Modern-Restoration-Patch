// KMRP for macOS: panels and their controls as layout.cpp keeps them, for KMRP's parts that work
// on a screen by its tags (Windows' KmrpRuntimeControlByTagK1 and KmrpRuntimePanelsK1,
// K1RuntimeLayout.cpp). Every panel loaded from a layout file is known from
// CSWGuiPanel::StartLoadFromLayout until its destructor; every control bound by its tag from
// CSWGuiPanel::InitControl.
#pragma once

#include <cstdint>
#include <vector>

namespace kmrp {
namespace panels {

// The control bound to `panel` by `tag`, or null: no such tag, or the control is gone.
void* ControlByTag(void* panel, const char* tag);

// The known panels of the class with that vtable on this manager, into `out`.
void WithVtable(std::uintptr_t vtable, void* manager, std::vector<void*>& out);

}  // namespace panels

namespace hud {

// Called by layout.cpp: the GUI's frame, after a change of size has been laid out; and the
// start of a panel's destructor (hud_options.cpp).
void Frame(void* manager);
void PanelDestroyed(void* panel);

}  // namespace hud
}  // namespace kmrp
