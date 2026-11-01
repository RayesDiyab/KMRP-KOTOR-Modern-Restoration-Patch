#pragma once
// Shared by KMRP's module (kmrp.dll) and the controller patch's (kmrp-controller.dll).
// A GUI control's fields, extent and text width, as both modules' layout code reads them.
// Until 2026-10-31 this lived in K1ControllerLayout.cpp, which kmrp.dll then compiled whole, with
// the rest of the controller code, for it (issue 82, F1:
// docs/cleanup-1.6/F1-kmrp-without-controller-code.md). Inline, as they were inside that
// file: in a .cpp of their own, the layout's calls of them stopped being inlined
// (2026-10-31, measured function by function). (K1_PANEL_CONTROL_ARRAY and _COUNT were
// K1NativeJoystick.cpp's.)
#include "K1EngineMemory.h"
#include "KmrpOptions.h"

#include <windows.h>
#include <cstddef>
#include <cstdint>
#include <cstdio>

// CSWGuiPanel's control array and its count.
constexpr std::size_t K1_PANEL_CONTROL_ARRAY = 0x20;
constexpr std::size_t K1_PANEL_CONTROL_COUNT = 0x24;

namespace KmrpGui {
// Every control's slot 1 is SetExtent(const rect*): 0x00417780 for a label,
// 0x00417A20 for a button, both copying {left, top, width, height} to +4.
using SetExtent = void(__thiscall*)(void*, const int*);
inline void setExtent(void* c, const int* rect) {
    reinterpret_cast<SetExtent>(At<std::uintptr_t*>(c,0)[1])(c,rect);
}

// The width of a label's whole text on one line, in pixels, from the glyphs its
// font draws -- the measure lastReplyLine uses -- and that font's line height.
//
// Plus the font's spacingR after each glyph but the last, which that measure
// leaves out: Draw adds font information +0x10 to every glyph's width before
// scaling it (0x0045ABDF: (u width x texturewidth + spacingR) x scale), and
// KMRP's dialogfont16x16 has spacingR 0.005, half a pixel, at 1920x1080 and
// 3440x1440 alike (+0x10 read from the game's memory, 2026-09-25; +0x14 beside
// it is spacingB). Without it "Journal Entry Added" measured 262 px at 1920x1080
// and drew 273, 6 px from the box's edge (357 and 364 at 3440x1440).
// lastReplyLine keeps the short measure: the dialogue A's gap was tuned by eye
// on top of it.
// The width of a control's text in its own font: a label's CSWGuiText is at +0xD0
// (its text parameters, +0xE8, are 0x18 into it), a button's at +0x154 (parameters at
// +0x16C, as setText writes them).
inline int controlTextWidth(void* control, unsigned textAt, int& lineHeight) {
    char* const text=static_cast<char*>(control)+textAt;  // its CSWGuiText
    if (!IsReadableK1(text,0x18)) return 0;
    char* const object=At<char*>(text,0x14);
    if (!IsReadableK1(object,0x44)) return 0;
    const char* const string=At<const char*>(object,0x14);
    void* const font=At<void*>(object,0x18);
    if (!IsReadableK1(string,1) || !IsReadableK1(font,4)) return 0;
    void** const vtable=At<void**>(font,0);
    if (!IsReadableK1(vtable,0x3C)) return 0;
    using Info=char*(__thiscall*)(void*);
    char* const info=reinterpret_cast<Info>(vtable[0x38/4])(font);
    if (!IsReadableK1(info,0x28)) return 0;
    const char* const upperLeft=At<const char*>(info,0x18);
    const char* const lowerRight=At<const char*>(info,0x24);
    if (!IsReadableK1(upperLeft,256*12) || !IsReadableK1(lowerRight,256*12)) return 0;
    const float texels=At<float>(info,0x0C)*100.0f;
    const float spacing=At<float>(info,0x10)*100.0f;
    float width=0.0f;
    int glyphs=0;
    for (int i=0;i<256;++i) {
        if (!IsReadableK1(string+i,1) || string[i]=='\0') break;
        if (string[i]=='\n') continue;
        const int glyph=static_cast<unsigned char>(string[i])*12;
        width+=(*reinterpret_cast<const float*>(lowerRight+glyph)
               -*reinterpret_cast<const float*>(upperLeft+glyph))*texels;
        ++glyphs;
    }
    if (glyphs>1 && spacing>0.0f && spacing<8.0f) width+=spacing*(glyphs-1);
    lineHeight=static_cast<int>(At<float>(info,0x04)*100.0f+0.5f);
    return static_cast<int>(width+0.5f);
}
inline int labelTextWidth(void* label, int& lineHeight) { return controlTextWidth(label, 0xD0, lineHeight); }
inline int buttonTextWidth(void* button) { int lh = 0; return controlTextWidth(button, 0x154, lh); }

inline void setExtentIfChanged(void* control, const int* rect) {
    const int* now=reinterpret_cast<const int*>(static_cast<char*>(control)+4);
    if (now[0]!=rect[0] || now[1]!=rect[1] || now[2]!=rect[2] || now[3]!=rect[3])
        setExtent(control,rect);
}

// KMRP\logs\kmrp-layout-lifecycle.log, appended to; null when it cannot be opened.
inline FILE* openLog() {
    wchar_t path[MAX_PATH];
    FILE* f = nullptr;
    if (!KmrpLogPath(path, L"kmrp-layout-lifecycle.log") || _wfopen_s(&f, path, L"a")) return nullptr;
    return f;
}
}  // namespace KmrpGui
