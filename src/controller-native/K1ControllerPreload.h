#pragma once
#include "K1ClassSelectArt.h"
#include <functional>
void KmrpControllerGuiMovieK1();
void KmrpControllerGuiPreloadFrameK1();
bool KmrpPreloadedClassArtK1(const char*, const ClassBoxK1&, const ClassBoxK1&, ClassArtResultK1&);
void KmrpQueueControllerGuiWorkK1(std::function<void()> work);
void KmrpWarmControllerPictureK1(const char* name, int width, int height, bool later);
bool KmrpWritePreloadPictureK1(const char*, const std::vector<std::uint8_t>&, int, int);
bool KmrpPreloadPictureReadyK1(const char*);
extern "C" void __cdecl KmrpQueueTexturePreloadK1(const char*);
