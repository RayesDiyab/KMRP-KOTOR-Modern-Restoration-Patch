#pragma once
// A button down when a movie ends was not pressed on the screen after it.
//
// The game does not poll input while a movie plays, so the records the pad speaks through stop,
// and lastButtons with them. NativeMovieFrameK1 reads the pad for itself, for the skip, and the
// next poll comes only after the screen behind the movie has been built: 1.2 s from the last start-up
// movie to the main menu. An A that skipped that movie and was still down by then was seen as a
// fresh press, on New Game, which has the focus. The maintainer's report, measured on the running
// game (docs/windows-verification-1.6.md, PAD-9).
//
// What is down at the first poll after a movie is taken out of the word until it is let go, so that
// press has neither a press nor a release in the game. A release alone would not do: a focused
// button's handler can run on it (reference: K1NativeJoystick.cpp, GuardPanelEchoK1). A press from
// before the movie is in lastButtons, and its release still goes out, as it must to clear the
// engine's description. Physical bits: this runs before the remap, as the press's meaning is
// decided there.
#include <cstdint>

struct KmrpPadCarry {
    std::uint16_t held = 0;
    bool afterMovie = false;

    void MovieFrame() { afterMovie = true; }

    std::uint16_t Filter(std::uint16_t word) {
        if (afterMovie) {
            afterMovie = false;
            held = word;
        }
        held &= word;
        return static_cast<std::uint16_t>(word & ~held);
    }
};
