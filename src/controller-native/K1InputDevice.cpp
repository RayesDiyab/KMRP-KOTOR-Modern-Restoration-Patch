// Which device the player is on. Began as Saul0097's KPM Xbox Controls for KOTOR 1, MIT, used with
// permission (THIRD_PARTY_NOTICES.md); what polled XInput went on 2026-11-01.
#include "K1InputDevice.h"

#include <cstdint>
#include <windows.h>
#include "K1ControllerBackend.h"

namespace {

volatile LONG g_controllerInputActive = 0;
volatile LONG g_controllerConnected = 0;
// Whether either device has actually been used yet. Until one has, the question
// of which the player is on is open, and a connected pad answers it -- a pad
// plugged in is a statement of intent, a keyboard sitting there is not. Without
// this a player who launches with a pad, and skips the intro movies with it,
// still meets a main menu with no badges on it.
volatile LONG g_inputDeviceChosen = 0;
// Diagnostics for the opening state, which is not behaving as reasoned.
volatile LONG g_keyboardMouseMarks = 0;
volatile LONG g_keyboardMouseLastTick = 0;

} // namespace

bool IsControllerInputActiveK1()
{
    if (InterlockedCompareExchange(&g_controllerInputActive, 0, 0) != 0) {
        return true;
    }
    if (InterlockedCompareExchange(&g_inputDeviceChosen, 0, 0) != 0) {
        return false;           // asked and answered: it is not the pad
    }
    // Nothing has been used yet, so a pad being present decides it.
    return InterlockedCompareExchange(&g_controllerConnected, 0, 0) != 0;
}

void MarkKeyboardMouseInputK1()
{
    InterlockedExchange(&g_controllerInputActive, 0);
    InterlockedExchange(&g_inputDeviceChosen, 1);
    InterlockedIncrement(&g_keyboardMouseMarks);
    InterlockedExchange(&g_keyboardMouseLastTick,
                        static_cast<LONG>(GetTickCount()));
}

// The native path reads the pad, so it reports device activity.
extern "C" void __cdecl KmrpMarkControllerActiveK1()
{
    if (InterlockedExchange(&g_controllerInputActive, 1) == 0) {
        ControllerLogK1("the game goes to the pad");
    }
    InterlockedExchange(&g_inputDeviceChosen, 1);
}

// The native path is the only thing that knows whether a pad is answering.
extern "C" void __cdecl KmrpNotePadPresentK1(int present)
{
    InterlockedExchange(&g_controllerConnected, present ? 1 : 0);
}

// The opening-state machinery, packed for the diagnostic line: bit 0 a pad is
// connected, bit 1 the question has been closed, bit 2 the pad is the live
// device. The high bits carry how many times keyboard-or-mouse closed it.
extern "C" unsigned long __cdecl KmrpDeviceStateK1()
{
    unsigned long state = 0;
    if (InterlockedCompareExchange(&g_controllerConnected, 0, 0) != 0) {
        state |= 1u;
    }
    if (InterlockedCompareExchange(&g_inputDeviceChosen, 0, 0) != 0) {
        state |= 2u;
    }
    if (InterlockedCompareExchange(&g_controllerInputActive, 0, 0) != 0) {
        state |= 4u;
    }
    const unsigned long marks = static_cast<unsigned long>(
        InterlockedCompareExchange(&g_keyboardMouseMarks, 0, 0));
    return state | (marks << 8);
}

