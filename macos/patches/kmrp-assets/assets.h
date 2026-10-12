// KMRP for macOS: the menu sets and artwork inside the module (assets.cpp).
#pragma once

#include <string>

namespace kmrp {
namespace assets {

// True when the bank has a set for the size or can blend one (kmrp-guiblend's rule, the
// installer's): the sizes KMRP's menu layouts exist for.
bool Covers(int width, int height);

// Unpacks what the size needs into the cache, once, and names the two folders the game is given:
// this run's artwork and this run's view of the size's set, both links to the cache without what
// the player's override folder has. Register does this itself; the regression test calls it
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

// The game's own override folder, the player's, which comes before both: a file there is left
// out of the two folders above (assets.cpp, PlayerHas). Empty when the game's folders are not
// found.
std::string OverrideDirectory();

// Gives the fonts the player's override supplies the size KMRP's own fonts of those names have.
// Asked every GUI frame and as a panel starts loading; `again` after the fonts' metrics were
// read again. Does nothing when the override has no font of KMRP's.
void ScaleOverrideFonts(bool again);

// KMRP's menus are not to be used this run: Covers answers no from then on, so nothing is
// registered and the resolution list stays the game's.
void Disable();

// True once the artwork folder is registered with the game.
bool Registered();

}  // namespace assets
}  // namespace kmrp
