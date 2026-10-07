// KMRP for macOS: the menu sets and artwork inside the module (assets.cpp).
#pragma once

#include <string>

namespace kmrp {
namespace assets {

// True when the bank has a set for the size or can blend one (kmrp-guiblend's rule, the
// installer's): the sizes KMRP's menu layouts exist for.
bool Covers(int width, int height);

// Unpacks what the size needs into the cache, once, and names the two folders the game is given:
// this run's artwork and the size's set. Register does this itself; the regression test calls it
// without a game.
bool Prepare(int width, int height, std::string* artDirectory, std::string* setDirectory);

// Unpacks what the size needs into the cache, once, and registers the cache with the game's
// resource manager. False when the module carries no bank, the size is not covered or the cache
// could not be written; the game then keeps its own files.
bool Register(void* resourceManager, int width, int height);

// The folder of the set registered last, which the game searches first, and this run's artwork
// folder; empty before they are registered.
const std::string& NewestSetDirectory();
const std::string& ArtworkDirectory();

// KMRP's menus are not to be used this run: Covers answers no from then on, so nothing is
// registered and the resolution list stays the game's.
void Disable();

// True once the artwork folder is registered with the game.
bool Registered();

}  // namespace assets
}  // namespace kmrp
