// Shared by KMRP's module (kmrp.dll) and the controller patch's (kmrp-controller.dll).
// Until 2026-10-31 this lived in K1NativeJoystick.cpp, which kmrp.dll then compiled whole, with
// the rest of the controller code, for it (issue 82, F1:
// docs/cleanup-1.6/F1-kmrp-without-controller-code.md).
// (Its counters were g_stick's, the pad state's, until then.)

#include "K1CursorConfinement.h"

#include <windows.h>

CursorConfinementK1 g_cursorConfinement;

// Keep the mouse inside the game window while KOTOR is the foreground window.
//
// Reported for multi-monitor setups: KOTOR turns the camera with mouse movement
// but never clips the cursor, so a wide enough sweep walks it onto the next
// display and the camera stops following. The game imports no ClipCursor at all
// -- SetCapture, ShowCursor and SetCursorPos are the only cursor calls in its
// import table -- so nothing in the engine is fighting this. Issue #20.
//
// The clip is re-applied every frame rather than once, because Windows drops it
// whenever the foreground window changes: that is also what releases it on
// Alt-Tab, on minimise, and if the process dies, so the cursor can never be
// left trapped by a crash. The explicit release below is for the case the
// system keeps it -- losing focus without a foreground change.
//
// It follows the window rather than the monitor, so a windowed game confines to
// its own client area, and moving the window or changing resolution is picked
// up on the next frame.
void UpdateCursorConfinementK1()
{
    HWND foreground = GetForegroundWindow();
    DWORD pid = 0;
    if (foreground) {
        GetWindowThreadProcessId(foreground, &pid);
    }
    const bool ours = foreground != nullptr
        && pid == GetCurrentProcessId()
        && !IsIconic(foreground);

    if (!ours) {
        if (g_cursorConfinement.confined) {
            ClipCursor(nullptr);
            g_cursorConfinement.confined = 0;
            ++g_cursorConfinement.releases;
        }
        return;
    }

    RECT client = {};
    if (!GetClientRect(foreground, &client)
            || client.right <= client.left
            || client.bottom <= client.top) {
        return;                      // mid-resize or zero-sized; try next frame
    }
    POINT corners[2] = {{client.left, client.top}, {client.right, client.bottom}};
    if (!ClientToScreen(foreground, &corners[0])
            || !ClientToScreen(foreground, &corners[1])) {
        return;
    }
    RECT screen = {corners[0].x, corners[0].y, corners[1].x, corners[1].y};
    // Fullscreen only: a window that does not cover its monitor is one the player
    // must be able to leave, to reach its border or another window. Confining a
    // windowed game trapped the cursor inside it (play-tested 2026-10-04).
    MONITORINFO monitor = {sizeof(monitor)};
    if (!GetMonitorInfoW(MonitorFromWindow(foreground, MONITOR_DEFAULTTONEAREST), &monitor)
            || screen.left > monitor.rcMonitor.left || screen.top > monitor.rcMonitor.top
            || screen.right < monitor.rcMonitor.right
            || screen.bottom < monitor.rcMonitor.bottom) {
        if (g_cursorConfinement.confined) {
            ClipCursor(nullptr);
            g_cursorConfinement.confined = 0;
            ++g_cursorConfinement.releases;
        }
        return;
    }
    if (ClipCursor(&screen)) {
        if (!g_cursorConfinement.confined) {
            ++g_cursorConfinement.confinements;
        }
        g_cursorConfinement.confined = 1;
    }
}
