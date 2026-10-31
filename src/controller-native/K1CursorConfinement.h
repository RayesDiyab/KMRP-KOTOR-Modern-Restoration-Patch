#pragma once
// Shared by KMRP's module (kmrp.dll) and the controller patch's (kmrp-controller.dll).
// The mouse kept inside a fullscreen game's window (issue 20).
// Until 2026-10-31 this lived in K1NativeJoystick.cpp, which kmrp.dll then compiled whole, with
// the rest of the controller code, for it (issue 82, F1:
// docs/cleanup-1.6/F1-kmrp-without-controller-code.md).

struct CursorConfinementK1 {
    int           confined = 0;        // is the mouse clipped right now
    unsigned long confinements = 0;    // times the clip was taken
    unsigned long releases = 0;        // times it was given back
};
extern CursorConfinementK1 g_cursorConfinement;

void UpdateCursorConfinementK1();
