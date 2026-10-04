// KMRP for macOS: the patch's options, as the running module reads them (options.cpp). Windows'
// counterpart is src/controller-native/KmrpOptions.h.
#pragma once

namespace kmrp {

// An option of the kmrp patch, from [Patch Options] in configs/kmrp.ini beside the game's
// executable; fallback when the file, the section or the key is not there, which is every
// install made by a manager without options.
int PatchOption(const char* id, int fallback);

// The three options. Controller support and the map notes are on unless turned off; the
// diagnostic logs are written only when turned on.
bool ControllerOption();
bool MapNotesOption();
bool DebugLogs();

}  // namespace kmrp
