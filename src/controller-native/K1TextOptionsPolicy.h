#pragma once
#include "K1Rect.h"
#include <algorithm>
#include <array>
#include <cstring>
#include <cctype>

namespace KmrpTextOptions {
constexpr int Minimum = 25, Maximum = 100, Step = 1, Default = 50;
// The font choices, by the number swkotor.ini keeps ([KMRP Text] FontStyle). Until
// 2026-10-18 1 was "Original Sharpened" (the original atlases enlarged and sharpened)
// and 0 "New HD": the maintainer had HD Original take 1's place, as the default
// ("(New) Original HD Font"), and 0 renamed "(Old) HD Font", so a saved choice keeps
// its number. On 2026-10-31 the maintainer removed the old HD font: the page offers
// "Original Font" and "HD Font" (HD Original) only, and a saved 0 (or anything else
// unknown) is read as HD Font, the default. Its TXI files stay in the art pack as every
// style's size reference (K1RuntimeAssets.cpp, FontSizes); its atlases are gone.
// On 2026-11-08 the maintainer added 3, "Modded Font": the fonts the game's Override holds,
// KMRP's HD Font for the names it lacks. It is offered only while Override has a font, and
// chosen by itself when the fonts there are new (K1TextOptions.cpp, Initialize); a saved 3
// with none there is read as HD Font.
enum FontStyle { HdOriginal=1, Original=2, Modded=3 };
// The choices on the page, top to bottom; Modded Font's row only while it is offered.
constexpr FontStyle FontChoices[]={Original,HdOriginal,Modded};
constexpr int FontChoiceCount=3;
inline int Style(int value, bool modded=false) {return value==Original?Original:value==Modded && modded?Modded:HdOriginal;}
inline int ChoiceOf(int style) {return style==Original?0:style==Modded?2:1;}
constexpr int SliderMaximum = (Maximum - Minimum) / Step;
inline int Percent(int value) {
    value = (std::max)(Minimum, (std::min)(Maximum, value));
    return Minimum + ((value - Minimum + Step / 2) / Step) * Step;
}
enum TextGroup { Menus=0, Body=1, Small=2, Hud=3, TextGroupCount=4 };
inline int FontGroup(const char* name) {
    char lower[17]{};
    for(int i=0;name && i<16 && name[i];++i)lower[i]=static_cast<char>(std::tolower(static_cast<unsigned char>(name[i])));
    if(!std::strncmp(lower,"fnt_d",5) || !std::strncmp(lower,"fnt_credits",11))return Body;
    if(!std::strncmp(lower,"dialogfont10x10",sizeof("dialogfont10x10")-1))return Small;
    if(!std::strcmp(lower,"fnt_console"))return Hud;
    return Menus;
}
struct Sizes {
    std::array<int,TextGroupCount> values{{Default,Default,Default,Default}};
    bool linked=true;
    int anchor=Menus;
    void Set(int group,int value) {
        if(group<0 || group>=TextGroupCount)return;
        anchor=group;value=Percent(value);
        if(linked)values.fill(value);else values[group]=value;
    }
    void Link(bool value) {
        linked=value;
        if(linked)values.fill(values[anchor]);
    }
};
// What the page saves. Its controls show a change at once, and it is written only by Save
// (the maintainer, 2026-11-01), so the page always knows if it differs from what is saved.
struct Settings {
    Sizes sizing;
    int style = HdOriginal;
    int icon = 0;
};
inline bool SameSettings(const Settings& a, const Settings& b) {
    return a.sizing.values == b.sizing.values && a.sizing.linked == b.sizing.linked &&
           a.style == b.style && a.icon == b.icon;
}
using Rect = KmrpRect;
// Inherit the native button's dimensions and column. Leave a third of one
// button's height between the two, independent of screen resolution or skin.
inline Rect Entry(const Rect& advanced) {
    return {advanced.left, advanced.top - advanced.height - (std::max)(2, advanced.height / 3),
            advanced.width, advanced.height};
}
}
