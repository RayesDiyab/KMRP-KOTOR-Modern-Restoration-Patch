// KMRP for macOS, the controller patch: its own files and what it knows of its neighbours
// (standalone.cpp).
#pragma once

namespace kmrp {
namespace standalone {

// Whether KMRP's own patch is installed beside this one (its module is loaded). Known once the
// game has added its resource directories.
bool BesideKmrp();

// The folder this patch's files are unpacked to, or null when the module carries none.
const char* FilesDirectory();

// Puts this patch's files in front of the game's resource search again, after another patch
// has added a directory (KMRP's menu set for a resolution chosen in the game).
void RegisterAgain();

}  // namespace standalone
}  // namespace kmrp
