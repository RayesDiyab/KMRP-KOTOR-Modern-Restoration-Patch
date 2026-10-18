#pragma once
// KMRP's option sliders (HUD Size, Text Size) dragged by the mouse: the thumb stays
// under the pointer where it was taken, and the value is the one the thumb is drawn at,
// to the nearest step. So the thumb dragged to the end of the track is the maximum.
//
// The engine's drag (CSWGuiSlider's mouse move, 0x00419250) takes
// maximum * (x - left) / width, rounded down, from the pointer itself; the thumb is drawn
// with its left edge at left + (width - thumb) * value / maximum (its layout, 0x00418F20).
// The two disagree by up to a thumb's width: with the thumb drawn at the end of the track
// the pointer on it gives one step short (99% on a 25-100% slider, at any resolution),
// and only a drag carried past the track's end gave the maximum. Keys and the pad step
// by one up to the maximum (0x0041ADF0) and are not touched.
//
// Our sliders get their own copy of the slider's table (0x0073E9D0, 40 entries), with
// two entries replaced:
//   4  mouse move (0x00419250, __thiscall(this, int, int), `ret 8`, returns 1): ours for
//      a horizontal slider; the engine's for a vertical one.
//   6  left button down (0x004191D0, __thiscall(this), plain `ret`): the engine's, then
//      where on the thumb the press landed.
// Engine facts, read from swkotor.exe (1.03):
//   [0x007A39F4] the GUI manager; +0x0C bit 0 while the left button is down (the
//                engine's drag requires it too).
//   slider +0x04 rect (left, top, width, height) in its panel's coordinates; +0x34 its
//                panel; +0x6C the part pressed (1 the thumb, 2 left of it, 3 right of it,
//                from 0x00419060); +0x70 maximum; +0x74 value; +0x164 the thumb's border.
//   0x00417EE0   SetValue, __thiscall(this, int), `ret 4`: clamps to 0..maximum and lays
//                the thumb out again.
//   0x00415B30   the border's rect, __thiscall(border, int out[4]), `ret 4`.
//   0x0040BA20   the pointer in a panel's coordinates, __thiscall(panel, int* x, int* y),
//                `ret 8`.
#include <cstdint>
#include <cstring>

namespace KmrpSliderK1 {

inline int& Field(void* object, int offset) { return *reinterpret_cast<int*>(static_cast<char*>(object) + offset); }

inline int ThumbWidth(void* slider) {
    int rect[4] = {};
    reinterpret_cast<void(__thiscall*)(void*, int*)>(0x00415B30)(static_cast<char*>(slider) + 0x164, rect);
    return rect[2];
}
inline int PointerX(void* slider) {
    void* const panel = *reinterpret_cast<void**>(static_cast<char*>(slider) + 0x34);
    int x = 0, y = 0;
    if (panel) reinterpret_cast<void(__thiscall*)(void*, int*, int*)>(0x0040BA20)(panel, &x, &y);
    return x;
}
// Where the thumb's left edge is drawn for the slider's value (as 0x00418F20 places it).
inline int ThumbLeft(void* slider, int thumb) {
    const int travel = Field(slider, 0x0C) - thumb, maximum = Field(slider, 0x70);
    return Field(slider, 0x04) + (travel > 0 && maximum > 0 ? travel * Field(slider, 0x74) / maximum : 0);
}

// The value for the thumb's left edge `at` pixels along a track it can travel `travel`
// pixels on, of 0..maximum: the nearest step, the ends at the ends. Where the thumb is
// drawn for a value (travel * value / maximum, rounded down) gives that value back
// whenever the travel is at least twice the maximum (testing/regression/Test-HudOptions.py).
inline int DragValue(int at, int travel, int maximum) {
    if (travel <= 0 || maximum <= 0 || at <= 0) return 0;
    if (at >= travel) return maximum;
    return static_cast<int>((2LL * at * maximum + travel) / (2LL * travel));
}

// The press being dragged: its slider, and the pointer's distance from the thumb's left edge.
inline void*& GrabSlider() { static void* slider = nullptr; return slider; }
inline int& GrabOffset() { static int offset = 0; return offset; }

inline int __fastcall MouseDown(void* self, void*) {
    const int result = reinterpret_cast<int(__thiscall*)(void*)>(0x004191D0)(self);
    if (Field(self, 0x6C) == 1) {
        GrabSlider() = self;
        GrabOffset() = PointerX(self) - ThumbLeft(self, ThumbWidth(self));
    }
    return result;
}

inline int __fastcall MouseMove(void* self, void*, int a, int b) {
    if (Field(self, 0x10) > Field(self, 0x0C))            // vertical: the engine's own
        return reinterpret_cast<int(__thiscall*)(void*, int, int)>(0x00419250)(self, a, b);
    const auto gui = *reinterpret_cast<unsigned char* const*>(0x007A39F4);
    if (!gui || !(gui[0x0C] & 1) || Field(self, 0x6C) != 1) return 1;
    const int thumb = ThumbWidth(self), travel = Field(self, 0x0C) - thumb, maximum = Field(self, 0x70);
    if (travel <= 0 || maximum <= 0) return 1;
    const int grab = GrabSlider() == self ? GrabOffset() : thumb / 2;
    const int at = PointerX(self) - grab - Field(self, 0x04);
    const int value = DragValue(at, travel, maximum);
    if (value != Field(self, 0x74)) reinterpret_cast<void(__thiscall*)(void*, int)>(0x00417EE0)(self, value);
    return 1;
}

inline void* Table() {
    static std::uintptr_t table[40];
    static bool made = false;
    if (!made) {
        std::memcpy(table, reinterpret_cast<const void*>(0x0073E9D0), sizeof table);
        table[4] = reinterpret_cast<std::uintptr_t>(&MouseMove);
        table[6] = reinterpret_cast<std::uintptr_t>(&MouseDown);
        made = true;
    }
    return table;
}

}  // namespace KmrpSliderK1

// Give a slider made by the engine's constructor (0x0041BAA0) the drag above.
inline void KmrpSliderTakeMouseK1(void* slider) {
    if (slider && *reinterpret_cast<std::uintptr_t*>(slider) == 0x0073E9D0)
        *reinterpret_cast<void**>(slider) = KmrpSliderK1::Table();
}
