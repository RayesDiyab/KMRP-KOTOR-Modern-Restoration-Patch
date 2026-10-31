// Shared by KMRP's module (kmrp.dll) and the controller patch's (kmrp-controller.dll).
// Until 2026-10-31 this lived in K1NativeJoystick.cpp, which kmrp.dll then compiled whole, with
// the rest of the controller code, for it (issue 82, F1:
// docs/cleanup-1.6/F1-kmrp-without-controller-code.md).

#include "K1MovieWindow.h"
#include "K1EngineMemory.h"

#include <windows.h>
#include <cstdint>

namespace {

// Movie geometry, for diagnosing the crash reported from play: a vision movie
// that rendered zoomed, ended on a black frame with only the HUD, and died.
//
// The engine sizes the picture at 0x004057AC, which KMRP replaces with the
// aspect-fit stub in .kmv. Vanilla derives the height from the requested width
// and the movie's aspect and never checks it against the window, which is the
// zoom bug the stub exists to fix. The stub instead picks its own target
// rectangle, and then the untouched tail at 0x0040581F-0x0040582C turns the
// result into the blit offsets:
//
//   00405819  mov [esi+0x84], eax    ; horizontal offset
//   0040582C  mov [esi+0x88], eax    ; vertical offset
//   00405867  call BinkBufferSetOffset
//
// Both are (window - picture)/2, so a picture computed LARGER than the window
// makes them negative and Bink blits outside its buffer. That is the shape of
// the reported failure, so these are what to measure. Read rather than assumed:
// this logs the engine's own numbers on the first frame of every movie.
constexpr std::size_t K1_MOVIE_INFO            = 0x48;   // -> {width, height}
constexpr std::size_t K1_MOVIE_WINDOW          = 0x50;   // the HWND Bink blits to

constexpr std::size_t K1_MOVIE_OFFSET_X        = 0x84;
constexpr std::size_t K1_MOVIE_OFFSET_Y        = 0x88;

}  // namespace

MovieStateK1 g_movie;

// Make the movie window black, and keep it black.
//
// The grey flash before and after a movie is the window CLASS, and the Ghidra
// archive says so outright. CExoMoviePlayerInternal::InitializeMovie registers
// "SWMovieWindow" at 0x004053E0, and the WNDCLASSA it fills in leaves
// hbrBackground NULL:
//
//   0040545C  mov dword ptr [esp+0x4c], ebx   ; ebx is 0 here -- no brush
//   00405464  mov dword ptr [esp+0x54], 0x73d7fc   ; "SWMovieWindow"
//
// Its window procedure at 0x00405190 handles WM_ACTIVATEAPP, WM_KEYDOWN,
// WM_SYSKEYDOWN and the mouse messages and hands everything else to
// DefWindowProc, so WM_ERASEBKGND is never handled either -- and with a NULL
// brush DefWindowProc erases nothing. The window is created WS_POPUP |
// WS_VISIBLE over the whole screen at 0x00405536, so from that moment until
// Bink's first blit, and again from the last blit until DestroyWindow in
// ShutDown at 0x00404C01, what is on screen is whatever was already in that
// memory. That is the flash, and it is grey because nothing ever painted it.
//
// The main game window does not have this problem: InitOpenGLWindow asks for
// GetStockObject(4) -- BLACK_BRUSH -- at 0x00403779. The movie window is the
// one class BioWare left without one.
//
// So give the class a brush. That is the whole fix rather than a patch over it:
// the class is registered once, on the first movie of the session, and every
// movie window afterwards is created with it. The FillRect is for the window
// that already exists by the time this first runs, since a class brush only
// affects the next erase.
//
// A stock brush is process-wide, is never deleted, and may be handed to a
// window class safely even though the class outlives every window on it.
void BlackenMovieWindowK1(void* player)
{
    if (!LooksLikePointerK1(player)) {
        return;
    }
    HWND const window = *FieldAt<HWND>(player, K1_MOVIE_WINDOW);
    if (!IsWindow(window)) {
        return;
    }
    HBRUSH const black = static_cast<HBRUSH>(GetStockObject(BLACK_BRUSH));
    if (!g_movie.classBlackened) {
        SetClassLongPtrA(window, GCLP_HBRBACKGROUND,
                         reinterpret_cast<LONG_PTR>(black));
        g_movie.classBlackened = true;
    }
    HDC const dc = GetDC(window);
    if (!dc) {
        return;
    }
    RECT client;
    if (GetClientRect(window, &client)) {
        FillRect(dc, &client, black);
        ++g_movie.windowsPainted;
    }
    ReleaseDC(window, dc);
}

// The movie window has just been created, inside InitializeMovie and before the
// message pump has had a chance to show anything. This is the earliest point the
// handle exists -- CreateWindowExA returns at 0x00405536 and the handle is
// stored to player+0x50 immediately after.
extern "C" void __cdecl NativeMovieWindowOpenK1(void* player)
{
    g_movie.lastW = -1;                // a fresh window: repaint on frame one
    BlackenMovieWindowK1(player);
}

// CExoMoviePlayerInternal::ShutDown, before it closes the Bink buffer and
// destroys the window. Bink has stopped drawing by now, so without this the
// window shows its last frame or nothing at all until it goes away.
extern "C" void __cdecl NativeMovieWindowCloseK1(void* player)
{
    BlackenMovieWindowK1(player);
}

// Has this playlist entry's geometry changed since the last frame?
//
// MoviePlaybackWorker (0x00405B30) loops over its entries reusing one player
// object, and each entry gets its own InitializeMovie: a new window, buffer and
// picture size. NativeMovieWindowOpenK1 resets lastW for each, so this repaints
// on the first frame of every entry, and again only if the size or offsets
// change (reverse-engineering/movies.md, "How the window is made").
void PaintMovieWindowK1(void* player)
{
    const void* const info = *FieldAt<void*>(player, K1_MOVIE_INFO);
    if (!LooksLikePointerK1(info)) {
        return;
    }
    const std::int32_t movieW = *FieldAt<std::int32_t>(const_cast<void*>(info), 0);
    const std::int32_t movieH = *FieldAt<std::int32_t>(const_cast<void*>(info), 4);
    const std::int32_t offX = *FieldAt<std::int32_t>(player, K1_MOVIE_OFFSET_X);
    const std::int32_t offY = *FieldAt<std::int32_t>(player, K1_MOVIE_OFFSET_Y);
    if (movieW == g_movie.lastW && movieH == g_movie.lastH &&
        offX == g_movie.lastOffX && offY == g_movie.lastOffY) {
        return;                        // same entry still playing
    }
    g_movie.lastW = movieW;
    g_movie.lastH = movieH;
    g_movie.lastOffX = offX;
    g_movie.lastOffY = offY;

    // Black the WINDOW, not the Bink buffer.
    //
    // Two earlier attempts got this wrong and both are worth remembering:
    //
    //   * Clearing the Bink buffer does nothing. The buffer is allocated at the
    //     MOVIE's size, so it holds only pixels BinkCopyToBuffer rewrites every
    //     frame. The bars are screen OUTSIDE the blit, which the buffer cannot
    //     reach.
    //   * Padding the buffer to the window's aspect and centring the picture
    //     inside it broke playback outright. The engine blits dirty rectangles
    //     from BinkGetRects, and those are in the movie's coordinate space --
    //     so offsetting the picture desynced the blit from it, and the intro
    //     logos rendered with only their left portion on screen.
    //
    // The bars are unpainted window, and so is the flash at either end. Both
    // are the same defect, so both get the same answer.
    BlackenMovieWindowK1(player);
}

// True in the KPM edition when KMRP Movies is not installed (K1KpmApplier.cpp).
bool KpmMoviesOffK1();

// The half of a movie frame that has nothing to do with the pad: follow the
// player, and black the window's bars. False when there is no movie.
bool TrackMovieFrameK1(void* moviePlayer)
{
    if (!LooksLikePointerK1(moviePlayer)) {
        g_movie.player = nullptr;      // no movie: nothing can be pending
        g_movie.armed = false;
        return false;
    }
    ++g_movie.frames;
    if (moviePlayer != g_movie.player) {
        g_movie.player = moviePlayer;  // a different movie: start again
        g_movie.armed = false;
        g_movie.lastW = -1;            // a new player: report its first entry
    }
    // Every frame, not just on a new player: the function itself suppresses
    // repeats, and only a per-frame check catches the second and later entries
    // of a playlist. Before the pad is read, so a movie is measured whether or
    // not a controller is connected. The bars are KMRP Movies' in the KPM
    // edition: without it, KMRP leaves the movie window as the game draws it.
    if (!KpmMoviesOffK1()) {
        PaintMovieWindowK1(moviePlayer);
    }
    return true;
}
