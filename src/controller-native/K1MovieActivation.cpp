// Keyboard and mouse lost after a movie list, until the game is minimised and restored. Vanilla
// does it too; found and fixed in KCRP (its docs/m2-play-endar-spire.md, run 25, 2026-11-11).
//
// The cause, in the public reconstruction TeamGizka/Odyssey and confirmed in the executable
// (CD 1.03, 761F9466..., and GOG's v1.03, 9C10E045..., the same bytes at every site here;
// reverse-engineering/movie-activation.md):
//
//   - Each movie plays in SWMovieWindow, a window of the movie thread. Activation moving between
//     it and the render window is, to Windows, activation moving between two threads, so each
//     window gets WM_ACTIVATEAPP as movies open and close, the game never having lost the user.
//   - The movie window's procedure (MovieMessageHandler, 0x00405190) takes any
//     WM_ACTIVATEAPP(0) as the game losing activation: OnDeactivation(0) (0x00404C20) stores 1 at
//     the player's +0x1C, and the movie is cancelled.
//   - At the end of the list, the movie thread forwards that to the render window (its worker,
//     0x00405CC0): with +0x1C at 1 and +0x20 at 0,
//
//       00405CC0  mov edx, [0x7A39D8]        ; the render window
//       00405CC6  push ebp / push ebp        ; lParam 0, wParam 0
//       00405CC8  push 0x1C                  ; WM_ACTIVATEAPP
//       00405CCB  call [PostMessageA]
//
//   - The main window procedure handles a WM_ACTIVATEAPP(0) for the render window with
//     DeactivateRenderWindow, which switches input off (CExoRawInputInternal::SetActive(0),
//     0x005E3C20). In full screen it first minimises the window and puts the desktop's display
//     mode back (ShowWindow(SW_MINIMIZE), RestoreDesktopDisplayMode): the movie thread has
//     cleared its playing flag before the post, so the "a movie is playing" exception does not
//     apply. That part is read from the source, not measured.
//
// When the posted message arrives after Windows has already handed activation back to the render
// window, the game switches its input off while its window is in front. Nothing activates it
// again: no further WM_ACTIVATEAPP comes until the window is minimised and restored. It is a
// race, so it happens only on some starts. Measured in KCRP with every SetActive call and every
// activation message logged: SetActive(0) from DeactivateRenderWindow with focus and foreground
// both the render window.
//
// The fix: drop that one message as the game's thread takes it from its queue, when the render
// window really is the foreground window and not minimised. A real WM_ACTIVATEAPP is sent, not
// posted, and names the other thread in lParam; this one is posted with lParam 0. When the user
// really has left during a movie, the render window is not in front, the message goes through and
// the game deactivates as it always did.
//
// A WH_GETMESSAGE hook on the game's thread: it sees every message GetMessage or PeekMessage
// removes from that thread's queue, before the window procedure, and may turn it into WM_NULL.
// It sees posted messages only, never sent ones, so neither Windows' own WM_ACTIVATEAPP nor the
// one NotifyModeChangeActivate (0x00401E90) sends can reach it. No engine code is patched.

#include "K1MovieActivation.h"
#include "K1EngineAddresses.h"
#include "K1RuntimeEngine.h"
#include "KmrpOptions.h"

#include <windows.h>

namespace {

HHOOK g_filter = nullptr;

LRESULT CALLBACK FilterPostedActivation(int code, WPARAM removal, LPARAM lParam)
{
    if (code == HC_ACTION && removal == PM_REMOVE) {
        MSG* const message = reinterpret_cast<MSG*>(lParam);
        const HWND render = *reinterpret_cast<const HWND*>(K1_MAIN_WINDOW);
        if (message->message == WM_ACTIVATEAPP && message->wParam == 0 && message->lParam == 0 &&
            render && message->hwnd == render && GetForegroundWindow() == render && !IsIconic(render)) {
            message->message = WM_NULL;   // the window stays active, and so does input
            if (KmrpDebugLogs())
                KmrpRuntimeLog("[KMRP] dropped the movie thread's WM_ACTIVATEAPP(0, 0): the game window is in front");
        }
    }
    return CallNextHookEx(g_filter, code, removal, lParam);
}

}  // namespace

void KmrpInstallMovieActivationFilterK1()
{
    static bool tried = false;   // one caller, the movie thread: no lock needed
    const HWND window = *reinterpret_cast<const HWND*>(K1_MAIN_WINDOW);
    if (tried || !window) return;
    tried = true;
    // The thread that owns the render window is the one that takes its messages, the game's
    // main thread. A rebuilt window (0x007A3A2C = 2) is made by that same thread, and the filter
    // reads the window afresh for every message, so one hook serves every window the game makes.
    // Windows removes a hook when the thread that set it ends; the movie thread lives until the
    // game exits (its worker, 0x00405B30, loops until asked to stop, then ExitThread at 0x00405D09).
    const DWORD thread = GetWindowThreadProcessId(window, nullptr);
    // This module's handle, for the hook procedure: KCRP's measured fix passed its own DLL's.
    HMODULE self = nullptr;
    GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                       reinterpret_cast<LPCWSTR>(&FilterPostedActivation), &self);
    g_filter = thread ? SetWindowsHookExW(WH_GETMESSAGE, FilterPostedActivation, self, thread) : nullptr;
    if (!g_filter) {
        char line[160];
        wsprintfA(line, "[KMRP] movie activation filter not installed (error %lu): input may still be lost after movies",
                  GetLastError());
        KmrpRuntimeLog(line);
    }
}
