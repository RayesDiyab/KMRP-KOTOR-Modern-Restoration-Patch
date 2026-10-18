#pragma once
#include <algorithm>
#include <array>
#include <cstring>
#include <cctype>

namespace KmrpTextOptions {
constexpr int Minimum = 25, Maximum = 100, Step = 1, Default = 50;
enum FontStyle { NewHd=0, OriginalSharpened=1, Original=2 };
constexpr int FontStyleCount=3;
inline int Style(int value) {return value>=0 && value<FontStyleCount?value:NewHd;}
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
struct Rect { int left, top, width, height; };
// Inherit the native button's dimensions and column. Leave a third of one
// button's height between the two, independent of screen resolution or skin.
inline Rect Entry(const Rect& advanced) {
    return {advanced.left, advanced.top - advanced.height - (std::max)(2, advanced.height / 3),
            advanced.width, advanced.height};
}
}
