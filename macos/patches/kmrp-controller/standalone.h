// KMRP for macOS, the controller patch: its own files and what it knows of its neighbours
// (standalone.cpp).
#pragma once

#include <string>

namespace kmrp {
namespace standalone {

// Whether KMRP's own patch is installed beside this one (its module is loaded). Known once the
// game has added its resource directories.
bool BesideKmrp();

// The folder this patch's files are unpacked to, or null when the module carries none.
const char* FilesDirectory();

// This run's folder of links, which the game's resource manager is given: a picture the module
// draws is written there. Null until it exists.
const char* RunDirectory();

// The controller's settings file, KMRP/controller.ini in the game's settings folder (Windows'
// KmrpControllerSettingsPath), or empty without a HOME. The folder is made, and a
// kmrp-controller.ini left beside swkotor.ini by an earlier install is moved there.
std::string SettingsPath();

// Puts this patch's files in front of the game's resource search again, after another patch
// has added a directory (KMRP's menu set for a resolution chosen in the game).
void RegisterAgain();

// Lists this patch's folder anew where it stands, after a file was written into it (a drawn
// picture), so the game finds the file. Adds nothing to the search.
bool ListAgain();

}  // namespace standalone
}  // namespace kmrp
