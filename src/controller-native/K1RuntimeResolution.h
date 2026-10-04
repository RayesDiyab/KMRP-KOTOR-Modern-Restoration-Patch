#pragma once

// A layout-independent dimension guard. The driver's mode enumeration and
// SetVideoMode still decide whether a fullscreen mode can actually be used.
inline bool KmrpRuntimeDimensions(int width, int height)
{
    // CSWGuiManager stores signed 16-bit viewport dimensions. Reject dimensions
    // which would wrap there; retain the game's 640x480 minimum usable canvas.
    return width >= 640 && height >= 480 && width <= 32767 && height <= 32767;
}

// One row per resolution and refresh rate in the Screen Resolution dialog.
void KmrpInstallModeListFilter();

// A size the display does not offer runs in a window of that size (the standalone
// module answers the display change itself); this keeps that window centred.
void KmrpCentreAddedSizeK1();
// Whether a window of this size is that window: the game is in what it takes for a
// fullscreen mode, so the mouse is confined to it as in fullscreen.
bool KmrpAddedSizeWindowK1(int width, int height);

// Stack arguments arrive as the address of their slot (KPM's "esp+N").
extern "C" int __cdecl KmrpAllowRuntimeResolutionK1(const int* width, const int* height);
extern "C" void __cdecl KmrpResolutionRequestedK1(void* manager, const int* width, const int* height);
extern "C" void __cdecl KmrpResolutionObservedK1(void* manager);
