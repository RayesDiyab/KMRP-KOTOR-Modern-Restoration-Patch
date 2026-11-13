#pragma once
// KMRP's module (kmrp.dll) only. Keyboard and mouse lost after a movie list, in vanilla too:
// the movie thread forwards a deactivation the game never had (K1MovieActivation.cpp).

// Installs the filter on the thread that owns the render window (0x007A39D8), once. Does
// nothing before that window exists, so it can be called at every movie: K1MovieWindow.cpp's
// NativeMovieWindowOpenK1, a "kmrp-movies" hook KMRP always installs, which runs on the movie
// thread before the first movie list can end.
void KmrpInstallMovieActivationFilterK1();
