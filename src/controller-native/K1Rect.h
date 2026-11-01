#pragma once
// A GUI rectangle as the engine keeps it (CSWGuiExtent), and the one way to give one to a
// control: its SetExtent, slot 1 of every control's vtable. Each file had its own struct of
// these four ints, and most called the slot by hand (audit S-8). Where a file has a name of
// its own for the rectangle (Rect, Extent, Box) it is this type.
struct KmrpRect { int left, top, width, height; };

inline void KmrpSetExtent(void* control, const KmrpRect& rect)
{
    using SetExtentFn = void(__thiscall*)(void*, const KmrpRect*);
    reinterpret_cast<SetExtentFn>((*static_cast<void***>(control))[1])(control, &rect);
}
