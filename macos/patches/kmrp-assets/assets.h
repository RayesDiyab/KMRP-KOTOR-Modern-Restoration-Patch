// KMRP for macOS: the menu sets and artwork inside the module (assets.cpp).
#pragma once

#include <string>
#include <vector>

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

// A font's source from the bank, by its private name (fonts.cpp).
bool FontSource(const std::string& name, std::vector<unsigned char>& bytes);
// The pack's blocks kept unpacked while files are read one at a time, let go.
void ReleaseUnpacked();

// KMRP's menus are not to be used this run: Covers answers no from then on, so nothing is
// registered and the resolution list stays the game's.
void Disable();

// True once the artwork folder is registered with the game.
bool Registered();

// For kmrp-prepare (macos/tools/kmrp-prepare.cpp) only, which makes the cache at install, outside
// the game: the game's Assets folder and the art pack, which the module otherwise finds from the
// game's executable and beside itself. Called before anything else; the module never calls it.
// What is written is then said on stderr only, not in the game's log.
void SetPaths(const std::string& assets, const std::string& pack);

// The cache's common files (store/), and the caches of other builds removed: what Prepare makes
// first, without linking a view for a run.
bool PrepareStore();

// One size's set whole in the cache (sets/<W>x<H>/ and its marker), as Prepare makes it, without
// linking a view or registering anything. It does not need the store, so a size can be made in
// a process of its own beside the one making the store.
bool PrepareSet(int width, int height);

}  // namespace assets
}  // namespace kmrp
