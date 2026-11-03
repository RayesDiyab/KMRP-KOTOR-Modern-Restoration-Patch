// KMRP for macOS: KMRP's option sliders (HUD Size, Text Size) dragged by the mouse: the thumb stays
// under the pointer where it was taken, and the value is the one the thumb is drawn at, to the
// nearest step, so the thumb dragged to the end of the track is the maximum. The port of Windows'
// src/controller-native/K1SliderGrip.h, whose DragValue this is.
//
// The engine's drag (CSWGuiSlider::HandleMouseCapturedMovement, 0x1004a6c8a, Windows 0x00419250)
// takes maximum * (x - left) / width, rounded down, from the pointer itself; the thumb is drawn
// with its left edge at left + (width - thumb) * value / maximum (CSWGuiSlider::SetExtent,
// 0x1004a6644, Windows 0x00418F20). The two disagree by up to a thumb's width: with the thumb
// drawn at the end of the track the pointer on it gives one step short, and only a drag carried
// past the track's end gave the maximum. Keys and the pad step by one (HandleInputEvent,
// 0x1004a694c) and are not touched.
//
// Our sliders get their own copy of the slider's table (0x1005b3f10, 41 entries here: the Mac's
// destructor takes two), with two entries replaced:
//   +0x28  mouse move (HandleMouseCapturedMovement, Windows' entry 4), rdi the slider, returns 1:
//          ours for a horizontal slider; the engine's for a vertical one.
//   +0x38  left button down (HandleLMouseDown, 0x1004a6c06, Windows' entry 6): the engine's, then
//          where on the thumb the press landed.
// Engine facts, read from KOTOR_Exe 1.4.0:
//   [0x100677ce0] the GUI manager; +0x10 bit 0 while the left button is down, which the engine's
//                 drag requires too.
//   slider +0x08 rect (left, top, width, height) in its panel's coordinates; +0x50 its panel;
//                +0xA8 the part pressed (1 the thumb, 2 left of it, 3 right of it, from
//                HitCheckSlider, 0x1004a6aae); +0xAC maximum; +0xB0 value; +0x1C8 the thumb's
//                CSWGuiImage. Windows: +0x04, +0x34, +0x6C, +0x70, +0x74, +0x164.
//   0x1004a6920  CSWGuiSlider::SetCurValue(slider, int): clamps to 0..maximum and lays the thumb
//                out again (Windows 0x00417EE0).
//   0x1004a2b82  CSWGuiImage::GetImageExtent(image): the rect, in rax and rdx (Windows 0x00415B30).
//   0x10049e80c  CSWGuiPanel::GetLocalMouseCoords(panel, int* x, int* y) (Windows 0x0040BA20).
//
// A header, with no state of its own outside the functions, so the HUD Size and Text Size pages
// share the code; no global needs initialising at load (kmrp_layout.cpp's rule).
#pragma once

#include <cstdint>
#include <cstring>

namespace kmrp {
namespace slider {

const std::uintptr_t kSliderVtable = 0x1005b3f10UL;
const std::size_t kTableEntries = 41;
const std::size_t kEntryMouseMove = 0x28 / 8, kEntryMouseDown = 0x38 / 8;
const std::size_t kExtent = 0x08, kPanel = 0x50, kPart = 0xA8, kMaximum = 0xAC, kValue = 0xB0, kThumb = 0x1C8;

inline int& Field(void* object, std::size_t offset) { return *reinterpret_cast<int*>(static_cast<char*>(object) + offset); }

struct ImageRect { int left, top, width, height; };

inline int ThumbWidth(void* slider) {
    return reinterpret_cast<ImageRect (*)(void*)>(0x1004a2b82)(static_cast<char*>(slider) + kThumb).width;
}
inline int PointerX(void* slider) {
    void* const panel = *reinterpret_cast<void**>(static_cast<char*>(slider) + kPanel);
    int x = 0, y = 0;
    if (panel) reinterpret_cast<void (*)(void*, int*, int*)>(0x10049e80c)(panel, &x, &y);
    return x;
}
// Where the thumb's left edge is drawn for the slider's value (as CSWGuiSlider::SetExtent has it).
inline int ThumbLeft(void* slider, int thumb) {
    const int travel = Field(slider, kExtent + 8) - thumb, maximum = Field(slider, kMaximum);
    return Field(slider, kExtent) + (travel > 0 && maximum > 0 ? travel * Field(slider, kValue) / maximum : 0);
}

// The value for the thumb's left edge `at` pixels along a track it can travel `travel` pixels on,
// of 0..maximum: the nearest step, the ends at the ends. Where the thumb is drawn for a value
// (travel * value / maximum, rounded down) gives that value back whenever the travel is at least
// twice the maximum (testing/regression/Test-HudOptions.py tests Windows' copy).
inline int DragValue(int at, int travel, int maximum) {
    if (travel <= 0 || maximum <= 0 || at <= 0) return 0;
    if (at >= travel) return maximum;
    return static_cast<int>((2LL * at * maximum + travel) / (2LL * travel));
}

// The press being dragged: its slider, and the pointer's distance from the thumb's left edge.
inline void*& GrabSlider() { static void* slider = nullptr; return slider; }
inline int& GrabOffset() { static int offset = 0; return offset; }

inline void MouseDown(void* self) {
    reinterpret_cast<void (*)(void*)>(0x1004a6c06)(self);
    if (Field(self, kPart) == 1) {
        GrabSlider() = self;
        GrabOffset() = PointerX(self) - ThumbLeft(self, ThumbWidth(self));
    }
}

inline std::uint64_t MouseMove(void* self) {
    if (Field(self, kExtent + 12) > Field(self, kExtent + 8))    // vertical: the engine's own
        return reinterpret_cast<std::uint64_t (*)(void*)>(0x1004a6c8a)(self);
    const auto gui = *reinterpret_cast<unsigned char* const*>(0x100677ce0);
    if (!gui || !(gui[0x10] & 1) || Field(self, kPart) != 1) return 1;
    const int thumb = ThumbWidth(self), travel = Field(self, kExtent + 8) - thumb, maximum = Field(self, kMaximum);
    if (travel <= 0 || maximum <= 0) return 1;
    const int grab = GrabSlider() == self ? GrabOffset() : thumb / 2;
    const int at = PointerX(self) - grab - Field(self, kExtent);
    const int value = DragValue(at, travel, maximum);
    if (value != Field(self, kValue)) reinterpret_cast<void (*)(void*, int)>(0x1004a6920)(self, value);
    return 1;
}

inline void* Table() {
    static std::uintptr_t table[kTableEntries];
    static bool made = false;
    if (!made) {
        std::memcpy(table, reinterpret_cast<const void*>(0x1005b3f10), sizeof table);
        table[kEntryMouseMove] = reinterpret_cast<std::uintptr_t>(&MouseMove);
        table[kEntryMouseDown] = reinterpret_cast<std::uintptr_t>(&MouseDown);
        made = true;
    }
    return table;
}

// Gives a slider made by the engine's constructor (0x1004a646e) the drag above.
inline void TakeMouse(void* slider) {
    if (slider && *reinterpret_cast<std::uintptr_t*>(slider) == kSliderVtable)
        *reinterpret_cast<void**>(slider) = Table();
}

}  // namespace slider
}  // namespace kmrp
