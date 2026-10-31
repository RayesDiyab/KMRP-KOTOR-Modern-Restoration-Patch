#pragma once
// Shared by KMRP's module (kmrp.dll) and the controller patch's (kmrp-controller.dll).
// The movie window: black from the moment it exists, its bars painted, the player
// followed from frame to frame.
// Until 2026-10-31 this lived in K1NativeJoystick.cpp, which kmrp.dll then compiled whole, with
// the rest of the controller code, for it (issue 82, F1:
// docs/cleanup-1.6/F1-kmrp-without-controller-code.md).
#include <cstdint>

// Movie playback state. Separate from the pad state because the movie loop owns
// the game loop: none of the other hooks run while it is up.
struct MovieStateK1 {
    void*         player = nullptr;   // the movie this state describes
    bool          armed = false;      // a release has been seen since it started
    unsigned long skips = 0;          // cancels actually issued
    unsigned long frames = 0;         // loop iterations observed
    unsigned long refused = 0;        // presses on a movie that may not be skipped
    unsigned long windowsPainted = 0;   // black-filled windows, one per entry
    bool          classBlackened = false;  // SWMovieWindow has a brush now
    // The last geometry logged. PlayMovieList loops over its entries reusing one
    // player object, so keying the log on the player alone logs the first entry
    // of a playlist and silently skips the rest -- which is how the first run of
    // this probe measured three startup logos and missed the movie under
    // investigation entirely. Geometry is recomputed per entry, so watch that.
    std::int32_t lastW = -1, lastH = -1, lastOffX = -1, lastOffY = -1;
};

extern MovieStateK1 g_movie;   // K1MovieWindow.cpp

void BlackenMovieWindowK1(void* player);
// The half of a movie frame that has nothing to do with the pad. False when there is no movie.
bool TrackMovieFrameK1(void* moviePlayer);
// Whether this module leaves the movie window as the game draws it: each module's own
// (K1KpmApplier.cpp for KMRP's, K1ControllerStandalone.cpp for the controller patch's).
bool KpmMoviesOffK1();

extern "C" void __cdecl NativeMovieWindowOpenK1(void* player);
extern "C" void __cdecl NativeMovieWindowCloseK1(void* player);
