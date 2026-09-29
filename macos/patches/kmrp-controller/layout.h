// KMRP for macOS, controller support: the Controller Layout screen, the confirm and dialogue A,
// and the status summary's layout (layout.cpp), as the frame hooks drive them.
#pragma once

namespace kmrp {
namespace layout {

// From CSWGuiPanel::StopLoadFromLayout (cues.cpp's hook): binds the entry and the badges while
// their panels still have their .gui, and frees them when their panels are destroyed.
void ReleaseGff(void* panel);

// From the GUI's frame: opens the screen the entry asked for, and keeps the badges in step.
void Frame(void* manager);

}  // namespace layout
}  // namespace kmrp
