// Shared by the kmrp-layout sources: a site is a run of KOTOR_Exe's code or data that the patch
// rewrites, with the bytes it must hold first; a group is sites that must change together.
#pragma once

#include <cstddef>
#include <cstdint>
#include <initializer_list>
#include <vector>

namespace kmrp {

struct Site {
    uintptr_t address;
    std::vector<uint8_t> expected, value;
};

struct Group {
    const char* name;
    std::vector<Site> sites;
};

std::vector<uint8_t> Bytes(std::initializer_list<uint8_t> bytes);
std::vector<uint8_t> Int32(int32_t value);
std::vector<uint8_t> Join(std::initializer_list<std::vector<uint8_t>> parts);

// The groups, one function per source file.
void AddResolutionSizes(std::vector<Group>& groups, int height);  // resolution_sizes.cpp
void AddListboxPadding(std::vector<Group>& groups);                // listbox_padding.cpp
// area_map.cpp. nearPage is a page within reach of a 5-byte call from the game's code, holding
// AreaMapPage(height); 0 when none could be placed, which leaves the map's positions vanilla.
void AddAreaMap(std::vector<Group>& groups, int width, int height, uintptr_t nearPage);
std::vector<uint8_t> AreaMapPage(int height);
// popup_fit.cpp: the message popup fitted to its contents, through the near page's thunk at
// kPopupThunk (AreaMapPage puts it there).
constexpr size_t kPopupThunk = 48;
void AddPopupFit(std::vector<Group>& groups, uintptr_t nearPage);

}  // namespace kmrp
