// KMRP for macOS, controller support: the controller's preloads (preload.cpp): the screens' files
// read during the movies (Windows' K1ControllerPreload.h) and the 3D previews rendered once,
// unseen, before their first visible draw (Windows' K1GuiModelPreload.h).
#pragma once

namespace kmrp {
namespace preload {

// From CSWGuiPanel::StopLoadFromLayout (layout.cpp's ReleaseGff): a panel's previews are queued
// when it has finished loading (hasGui) and forgotten when it goes.
void PanelLoaded(void* panel, bool hasGui);

// Item 112: the movie frame (gameplay.cpp) and the GUI frame (layout.cpp) submit the controller's
// screens to be read on a thread of this module, once per pad family; the GUI frame then has the
// engine upload what was read, two textures a frame, with a GL context current.
void MovieFrame();
void GuiFrame();

}  // namespace preload
}  // namespace kmrp
