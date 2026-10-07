// KMRP for macOS: the patch's options, as the running module reads them (options.cpp). Windows'
// counterpart is src/controller-native/KmrpOptions.h.
#pragma once

namespace kmrp {

// An option of this module's patch, from [Patch Options] in configs/<patch id>.ini beside the game's
// executable; fallback when the file, the section or the key is not there, which is every
// install made by a manager without options.
int PatchOption(const char* id, int fallback);

// KMRP's patch: the map notes are on unless turned off, the diagnostic logs written only when
// turned on. The controller patch (KMRP_CONTROLLER_PATCH, its own options file): the
// Xbox-style HUD and its own diagnostic logs, both off unless turned on.
bool MapNotesOption();
bool HdIconsOption();   // the bundled HD icon pack: on unless turned off (since 2026-10-08)
bool XboxHudOption();
bool DebugLogs();

}  // namespace kmrp
