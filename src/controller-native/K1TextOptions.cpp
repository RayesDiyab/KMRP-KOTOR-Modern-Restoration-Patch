// Native K1 settings, using the graphics screen's actual templates and geometry.
// No pre-authored .gui, fixed resolution, or dependency on controller support.
#include "K1TextOptions.h"
#include "K1TextOptionsPolicy.h"
#include "K1HudOptions.h"
#include "K1OptionsPad.h"
#include "K1RuntimeAssets.h"
#include "K1RuntimeLayout.h"
#include "K1SliderGrip.h"
#include "KmrpOptions.h"
#include "../../macos/tools/kmrp-iconsize.h"
#include <windows.h>
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cwchar>
#include <cstdlib>
#include <map>
#include <vector>

#ifdef KMRP_TEXT_OPTIONS_TEST
void* KmrpTextOptionsTestFunction(unsigned address);
void* KmrpTextOptionsTestAddress(std::uintptr_t address);
bool KmrpTextOptionsTestConfirmHeld();
#endif

namespace {
using namespace KmrpTextOptions;
template<class T> T& At(void* p, unsigned n) { return *reinterpret_cast<T*>(static_cast<char*>(p)+n); }
template<class T> T Fn(unsigned n) {
#ifdef KMRP_TEXT_OPTIONS_TEST
    return reinterpret_cast<T>(KmrpTextOptionsTestFunction(n));
#else
    return reinterpret_cast<T>(n);
#endif
}
void* Native(std::uintptr_t address) {
#ifdef KMRP_TEXT_OPTIONS_TEST
    return KmrpTextOptionsTestAddress(address);
#else
    return reinterpret_cast<void*>(address);
#endif
}
void** Vtable(void* p) {return static_cast<void**>(Native(At<std::uintptr_t>(p,0)));}
using Simple=void(__thiscall*)(void*);
using Ctor=void*(__thiscall*)(void*);
using New=void*(__cdecl*)(unsigned);
using Delete=void(__cdecl*)(void*);
using Event=void(__thiscall*)(void*,int,void*,void*);
using Focus=void(__thiscall*)(void*,void*,int);
using Exists=int(__thiscall*)(void*,void*);
using SetExtent=void(__thiscall*)(void*,const Rect*);
constexpr std::uintptr_t GraphicsTable=0x7586F8, ButtonTable=0x73E658;
struct Entry { void* button=nullptr; void* advanced=nullptr; int badged=-1; char family=0; };
std::map<void*,Entry> entries;
void *pending=nullptr, *current=nullptr, *parent=nullptr, *returnFocus=nullptr;
// Default and Close: the pad presses them itself (Y, B), so they are off its focus and
// wear its glyph while it is in use (K1OptionsPad.h).
void *defaultsButton=nullptr, *backButton=nullptr;
KmrpOptionsPad::Glyph defaultsGlyph, backGlyph;
void* NativeRoutine(std::uintptr_t address){return Fn<void*>(static_cast<unsigned>(address));}
std::uintptr_t table[27]{};
std::vector<void*> owned;
void* sizeLabels[TextGroupCount]{};
void* sliders[TextGroupCount]{};
void* linkSizes=nullptr;
void* previews[TextGroupCount]{};
void* help=nullptr;
// The Icon Size slider (issue 80, kmrp-iconsize.h): its caption and slider the left
// column's fifth pair, under HUD Text (the maintainer, 2026-10-31: not in the right-hand
// column, where the first build had it); on the right, under the text previews, one feat,
// one Force power and one skill icon at the size the lists show them. Saved as
// [KMRP Text] IconSize.
void* iconLabel=nullptr;
void* iconSlider=nullptr;
void* iconPreviews[3]{};
const char* const iconPreviewNames[]={"i_flurry01","ip_push","isk_stealth"};
int iconSize=KMRP_ICON_DEFAULT, requestedIcon=KMRP_ICON_DEFAULT, displayedIcon=-1, screenHeight=0;
Rect iconArea{};
// The engine draws the icons at the slider's size (K1RuntimeLayout.cpp), so a step costs
// four row heights written (KmrpRuntimeApplyIconSizeK1) and is applied at once, as a text
// size is. The first build made the icon files at every step: the game stalled at each 1%
// and the slider could not be dragged (the maintainer, 2026-10-31).
const wchar_t* const groupKeys[]={L"MenuSize",L"BodySize",L"SmallSize",L"HudSize"};
const char* const groupLabels[]={"Menus & Replies","Subtitles & Body","Small Text","HUD Text"};
const char* const previewFonts[]={"dialogfont16x16","fnt_d16x16","dialogfont10x10","fnt_console"};
const char* const previewTexts[]={"Menus and reply choices","Subtitles and descriptions","Small text preview","HUD: 0123456789"};
void* fontChoices[FontChoiceCount]{};
bool initialized=false, dirty=false;
int style=HdOriginal, requestedStyle=HdOriginal;
Sizes sizing, requestedSizing;
int releasedFrames=2;
bool blockReopen=false;
std::array<int,TextGroupCount> displayedSizes{{-1,-1,-1,-1}};
int displayedLinked=-1;
int displayedStyle=-1;

bool ConfirmHeld() {
#ifdef KMRP_TEXT_OPTIONS_TEST
    return KmrpTextOptionsTestConfirmHeld();
#else
    using Query=int(__cdecl*)();
    HMODULE controller=GetModuleHandleW(L"kmrp-controller.dll");
    auto query=controller?reinterpret_cast<Query>(GetProcAddress(controller,"KmrpControllerConfirmHeldK1")):nullptr;
    return (query && query()) || (GetAsyncKeyState(VK_LBUTTON)&0x8000) ||
        (GetAsyncKeyState(VK_RETURN)&0x8000) || (GetAsyncKeyState(VK_SPACE)&0x8000);
#endif
}
bool Armed(){return releasedFrames>=2;}

// The game's folder's, or the one KMRP's installer names when it makes the fonts ahead.
bool ConfigPath(wchar_t (&path)[MAX_PATH]) {
    return KmrpGamePath(path,L"swkotor.ini");
}
void Initialize() {
    if(initialized)return;
    initialized=true;
    wchar_t path[MAX_PATH];
    if(ConfigPath(path)) {
        const int legacySize=Percent(static_cast<int>(GetPrivateProfileIntW(L"KMRP Text",L"Size",Default,path)));
        for(int i=0;i<TextGroupCount;++i) {
            sizing.values[i]=Percent(static_cast<int>(GetPrivateProfileIntW(L"KMRP Text",groupKeys[i],legacySize,path)));
        }
        sizing.Link(GetPrivateProfileIntW(L"KMRP Text",L"LinkSizes",1,path)!=0);
        // OriginalFont, before FontStyle (pre-release builds only), named HD fonts only,
        // which are HD Font now (K1TextOptionsPolicy.h).
        style=Style(GetPrivateProfileIntW(L"KMRP Text",L"FontStyle",HdOriginal,path));
        iconSize=kmrp_icon_percent(static_cast<int>(GetPrivateProfileIntW(L"KMRP Text",L"IconSize",KMRP_ICON_DEFAULT,path)));
    }
    requestedSizing=sizing;requestedStyle=style;requestedIcon=iconSize;
}
bool Save() {
    wchar_t path[MAX_PATH],value[16];
    if(!ConfigPath(path))return false;
    swprintf_s(value,L"%d",sizing.values[Menus]);
    if(!WritePrivateProfileStringW(L"KMRP Text",L"Size",value,path))return false;
    for(int i=0;i<TextGroupCount;++i) {
        swprintf_s(value,L"%d",sizing.values[i]);
        if(!WritePrivateProfileStringW(L"KMRP Text",groupKeys[i],value,path))return false;
    }
    if(!WritePrivateProfileStringW(L"KMRP Text",L"LinkSizes",sizing.linked?L"1":L"0",path))return false;
    swprintf_s(value,L"%d",iconSize);
    if(!WritePrivateProfileStringW(L"KMRP Text",L"IconSize",value,path))return false;
    swprintf_s(value,L"%d",style);
    return WritePrivateProfileStringW(L"KMRP Text",L"FontStyle",value,path) &&
        WritePrivateProfileStringW(L"KMRP Text",L"OriginalFont",L"1",path);
}
void Extent(void* control,const Rect& rect) {
    reinterpret_cast<SetExtent>(Vtable(control)[1])(control,&rect);
}
void DestroyControl(void* c) {
    if(c)reinterpret_cast<void*(__thiscall*)(void*,unsigned)>(Vtable(c)[0])(c,1);
}
void Text(void* c,const char* text,bool button=false) {
    void* string[2]{};
    Fn<void(__thiscall*)(void*,const char*)>(0x5E5A90)(string,text);
    Fn<void(__thiscall*)(void*,void*)>(0x415E00)(static_cast<char*>(c)+(button?0x16C:0xE8),string);
    Fn<Simple>(0x5E5C20)(string);
}
bool AddControl(void* panel,void* control) {
    // Keep IDs equal to array indices, even when the loaded GUI contains holes.
    const int count=At<int>(panel,0x24);
    if(count<0 || count>=512)return false;
    At<int>(control,0x50)=count;
    Fn<void(__thiscall*)(void*,void*)>(0x40B9A0)(panel,control);
    return At<int>(panel,0x24)==count+1 && At<void**>(panel,0x20)[count]==control;
}
void* CloneButton(void* owner,void* prototype) {
    if(!prototype || At<std::uintptr_t>(prototype,0)!=ButtonTable)return nullptr;
    void* c=Fn<New>(0x6FA7E6)(0x1C4);
    if(!c)return nullptr;
    Fn<Ctor>(0x41C0F0)(c);
    const Rect rect=At<Rect>(prototype,4);
    Fn<void(__thiscall*)(void*,const Rect*,void*)>(0x418D80)(c,&rect,prototype);
    // Visibility, mouse-focus policy and enable state come from the original.
    At<unsigned>(c,0x44)=(At<unsigned>(c,0x44)&~0x2Eu)|(At<unsigned>(prototype,0x44)&0x2Eu);
    if(!AddControl(owner,c)){DestroyControl(c);return nullptr;}
    return c;
}
void* Bind(void* panel,const char* tag,unsigned size,unsigned ctor) {
    void* c=Fn<New>(0x6FA7E6)(size);
    if(!c)return nullptr;
    Fn<Ctor>(ctor)(c);
    At<int>(c,0x50)=-1;
    void* name[2]{};
    Fn<void(__thiscall*)(void*,const char*)>(0x5E5A90)(name,tag);
    Fn<void(__thiscall*)(void*,void*,void*,int)>(0x40B930)(panel,c,name,0);
    Fn<Simple>(0x5E5C20)(name);
    if(At<int>(c,0x50)<0 || !AddControl(panel,c)){DestroyControl(c);return nullptr;}
    owned.push_back(c);return c;
}
void Close() {
    if(current)At<unsigned>(current,0x44)=(At<unsigned>(current,0x44)&~0x700u)|0x400u;
}
// A bound control selectable as its live counterpart on the graphics screen is. The
// pad moves only to a control CSWGuiControl::GetIsSelectable (0x004189D0) accepts: bit
// 8 of its flags (+0x44) and its class's own test. Bound from the template
// (InitControl, its last argument 0) a control lacks the bit, so the sliders could not
// be reached with the pad (the maintainer, 2026-10-18). As CloneButton copies them for
// the entry button; visibility (bit 2) is left as it is.
void SelectableAs(void* control,void* owner,const char* tag) {
    void* original=KmrpRuntimeControlByTagK1(owner,tag);
    if(!control || !original)return;
    At<unsigned>(control,0x44)=(At<unsigned>(control,0x44)&~0x2Cu)|(At<unsigned>(original,0x44)&0x2Cu);
}
void __fastcall Back(void*,void*,void*) {if(Armed())Close();}
void __fastcall OnB(void*,void*,int value) {if(value)Close();}
void __fastcall Open(void* owner,void*,void*) {
    if(!current && !pending && !blockReopen)pending=owner;
}
void Dirty() {dirty=requestedSizing.values!=sizing.values || requestedSizing.linked!=sizing.linked || requestedStyle!=style;}
// A click is acted on once: the pad's A reaches a handler as it goes down and again as
// it comes up (the mouse only as it comes up), so a toggle flipped twice (the
// maintainer, 2026-10-18, on the HUD Size page). Each handler disarms the page, armed
// again once the confirm button has been up for two frames (Armed).
void Choose(int value) {if(Armed()){requestedStyle=Style(value);Dirty();releasedFrames=0;}}
void __fastcall ToggleLink(void*,void*,void*) {
    if(Armed()){requestedSizing.Link(!requestedSizing.linked);Dirty();releasedFrames=0;}
}
void __fastcall SelectOriginal(void*,void*,void*) {Choose(Original);}
void __fastcall SelectHdOriginal(void*,void*,void*) {Choose(HdOriginal);}
void __fastcall Defaults(void*,void*,void*) {
    if(Armed()){requestedSizing=Sizes{};requestedStyle=HdOriginal;requestedIcon=KMRP_ICON_DEFAULT;Dirty();releasedFrames=0;}
}
// A slider's events, as the graphics screen gives Brightness its own
// (CSWGuiOptionsGraphics's constructor, 0x006E2E70, through CSWGuiControl::AddEvent):
// entering and leaving (0x00, 0x01), its four movement events (0x2F, 0x30, 0x3F, 0x40),
// a click (0x27) and the Default command (0x2A). The controller patch takes a control
// with no events for decoration (the Main Menu's wallpaper rule, K1NativeJoystick.cpp),
// so the pad could not reach the sliders (the maintainer, 2026-10-18). The game's
// shape: the panel in ecx, one word on the stack, `ret 4`, as OnMoveGammaSlider
// (0x006DED30) is. The value is read every frame, so moving needs nothing more here.
void __fastcall SliderEvent(void*,void*,void*) {}
void SliderEvents(void* slider,void* panel) {
    for(const int event:{0x00,0x01,0x2F,0x30,0x3F,0x40,0x27})
        Fn<Event>(0x41AB20)(slider,event,panel,reinterpret_cast<void*>(&SliderEvent));
    Fn<Event>(0x41AB20)(slider,0x2A,panel,reinterpret_cast<void*>(&Defaults));
}
// B closes and Y restores the defaults wherever the focus is: Close and Default are off
// the pad's focus (the maintainer, 2026-10-19). Until then Y reached Defaults only from
// a slider, through the slider's own Default command (SliderEvents).
void __fastcall Input(void* self,void*,int event,int value) {
    if(value && event==0x28){Close();return;}
    if(event==0x2A){if(value)Defaults(nullptr,nullptr,nullptr);return;}
    Fn<void(__thiscall*)(void*,int,int)>(0x409E60)(self,event,value);
}
void* __fastcall Destroy(void* self,void*,unsigned flags) {
    void* manager=At<void*>(self,0x18);
    if(manager && Fn<Exists>(0x40BD70)(manager,self))Fn<Exists>(0x40C830)(manager,self);
    Fn<Focus>(0x40A630)(self,nullptr,0);
    auto array=At<void**>(self,0x20);
    for(int i=0;array && i<At<int>(self,0x24);++i)array[i]=nullptr;
    KmrpOptionsPad::SkipFocus(defaultsButton,false);KmrpOptionsPad::SkipFocus(backButton,false);
    for(void* c:owned)DestroyControl(c);
    owned.clear();help=linkSizes=defaultsButton=backButton=nullptr;
    defaultsGlyph=backGlyph=KmrpOptionsPad::Glyph{};
    for(void*& p:sizeLabels)p=nullptr;
    for(void*& p:sliders)p=nullptr;
    for(void*& p:previews)p=nullptr;
    for(void*& choice:fontChoices)choice=nullptr;
    iconLabel=iconSlider=nullptr;for(void*& icon:iconPreviews)icon=nullptr;displayedIcon=-1;
    Fn<Simple>(0x40CF70)(self);
    current=nullptr;
    if(parent && manager && Fn<Exists>(0x40BD70)(manager,parent))
        Fn<Focus>(0x40A630)(parent,returnFocus,0);
    parent=returnFocus=nullptr;
    blockReopen=true;releasedFrames=0;
    if(flags&1)Fn<Delete>(0x6FA390)(self);
    return self;
}
void Navigation(void* c,void* up,void* down,void* left=nullptr,void* right=nullptr) {
    At<void*>(c,0x5C)=up;At<void*>(c,0x60)=left;
    At<void*>(c,0x64)=down;At<void*>(c,0x68)=right;
}
void UpdateCaptions() {
    if(!current)return;
    for(int i=0;i<TextGroupCount;++i)if(displayedSizes[i]!=requestedSizing.values[i]) {
        char caption[64];sprintf_s(caption,"%s: %d%%",groupLabels[i],requestedSizing.values[i]);
        Text(sizeLabels[i],caption);
        Fn<void(__thiscall*)(void*,int)>(0x417EE0)(sliders[i],(requestedSizing.values[i]-Minimum)/Step);
        displayedSizes[i]=requestedSizing.values[i];
    }
    if(displayedIcon!=requestedIcon && iconLabel && iconSlider) {
        char caption[64];sprintf_s(caption,"Feat & Skill Icons: %d%%",requestedIcon);
        Text(iconLabel,caption);
        Fn<void(__thiscall*)(void*,int)>(0x417EE0)(iconSlider,(requestedIcon-Minimum)/Step);
        displayedIcon=requestedIcon;
    }
    if(displayedLinked!=int(requestedSizing.linked)) {
        Fn<void(__thiscall*)(void*,unsigned)>(0x685540)(linkSizes,requestedSizing.linked);
        displayedLinked=requestedSizing.linked;
    }
    if(displayedStyle!=requestedStyle) {
        for(int i=0;i<FontChoiceCount;++i)
            Fn<void(__thiscall*)(void*,unsigned)>(0x685540)(fontChoices[i],FontChoices[i]==requestedStyle);
        displayedStyle=requestedStyle;
        // Right (or left) from "Link Text Sizes" goes to the font chosen.
        if(linkSizes)At<void*>(linkSizes,0x60)=At<void*>(linkSizes,0x68)=fontChoices[ChoiceOf(requestedStyle)];
    }
}
// The preview's three icons at the size in force, side by side and centred in their area:
// the size the lists draw them at, one texel a pixel (kmrp-iconsize.h), smaller only where
// the area is shorter than the icon.
void PlaceIconPreviews(int percent) {
    if(!iconPreviews[0])return;
    // The preview's three icons are 32 px in the game, as kmrp_icon_drawn reads them.
    const double scale=kmrp_icon_scale(screenHeight);
    const int feat=kmrp_icon_drawn(kmrp_icon_feat_today(scale,KMRP_ICON_NATIVE),scale,percent);
    const int skill=kmrp_icon_drawn(kmrp_icon_skill_today(scale,KMRP_ICON_NATIVE),scale,percent);
    const int sizes[3]={(std::min)(feat,iconArea.height),(std::min)(feat,iconArea.height),(std::min)(skill,iconArea.height)};
    const int gap=(std::max)(4,iconArea.width/48);
    int left=iconArea.left+(iconArea.width-(sizes[0]+sizes[1]+sizes[2]+2*gap))/2;
    for(int i=0;i<3;++i) {
        Extent(iconPreviews[i],{left,iconArea.top+(iconArea.height-sizes[i])/2,sizes[i],sizes[i]});
        left+=sizes[i]+gap;
    }
}
void MakeScreen(void* manager,void* owner) {
    // All tags below were successfully bound by the real graphics constructor.
    const char* required[]={"LBL_TITLE","SLI_GAMMA","LBL_GAMMA","BTN_RESOLUTION","BTN_DEFAULT","BTN_BACK","LB_DESC","CB_SHADOWS","BTN_ADVANCED"};
    for(const char* tag:required)if(!KmrpRuntimeControlByTagK1(owner,tag))return;
    void* p=Fn<New>(0x6FA7E6)(0x64);
    if(!p)return;
    Fn<void*(__thiscall*)(void*,void*)>(0x40B570)(p,manager);
    std::memcpy(table,Native(0x73E010),sizeof(table));
    table[0]=reinterpret_cast<std::uintptr_t>(&Destroy);
    table[15]=reinterpret_cast<std::uintptr_t>(&Input);
    table[21]=reinterpret_cast<std::uintptr_t>(&OnB);
    At<std::uintptr_t*>(p,0)=table;
    current=p;parent=owner;returnFocus=At<void*>(owner,0x1C);owned.clear();
    char resref[16]="optgraphics";
    Fn<void(__thiscall*)(void*,void*)>(0x40A680)(p,resref);
    void* title=Bind(p,"LBL_TITLE",0x140,0x41ACD0);
    for(int i=0;i<TextGroupCount;++i) {
        sizeLabels[i]=Bind(p,"LBL_GAMMA",0x140,0x41ACD0);
        sliders[i]=Bind(p,"SLI_GAMMA",0x1B8,0x41BAA0);
#ifndef KMRP_TEXT_OPTIONS_TEST   // the harness's sliders have no engine table to copy
        KmrpSliderTakeMouseK1(sliders[i]);   // dragged to the end is the maximum (K1SliderGrip.h)
#endif
    }
    linkSizes=Bind(p,"CB_SHADOWS",0x2B4,0x6E00D0);
    if(linkSizes)At<int>(linkSizes,0x1C4)=-1;
    // Native round options controls, with automatic toggling disabled. The
    // group explicitly selects one style, including re-selecting the same row.
    for(void*& choice:fontChoices) {
        choice=Bind(p,"CB_SHADOWS",0x2B4,0x6E00D0);
        if(choice)At<int>(choice,0x1C4)=-1;
    }
    help=Bind(p,"LBL_GAMMA",0x140,0x41ACD0);
    for(void*& preview:previews)preview=Bind(p,"LBL_GAMMA",0x140,0x41ACD0);
    iconLabel=Bind(p,"LBL_GAMMA",0x140,0x41ACD0);
    iconSlider=Bind(p,"SLI_GAMMA",0x1B8,0x41BAA0);
#ifndef KMRP_TEXT_OPTIONS_TEST
    KmrpSliderTakeMouseK1(iconSlider);
#endif
    for(void*& icon:iconPreviews)icon=Bind(p,"LBL_GAMMA",0x140,0x41ACD0);
    void* defaults=Bind(p,"BTN_DEFAULT",0x1C4,0x41C0F0);
    void* back=Bind(p,"BTN_BACK",0x1C4,0x41C0F0);
    // The pad's Y and B beside Default's and Close's captions (K1OptionsPad.h).
    void* defaultsMark=Bind(p,"LBL_GAMMA",0x140,0x41ACD0);
    void* backMark=Bind(p,"LBL_GAMMA",0x140,0x41ACD0);
    Fn<Simple>(0x40B8F0)(p);
    bool complete=title && linkSizes && fontChoices[0] && fontChoices[1] && help && defaults && back &&
        defaultsMark && backMark;
    for(int i=0;i<TextGroupCount;++i)complete=complete && sizeLabels[i] && sliders[i] && previews[i];
    complete=complete && iconLabel && iconSlider && iconPreviews[0] && iconPreviews[1] && iconPreviews[2];
    if(!complete) {
        Destroy(p,nullptr,1);return;
    }
    // The sliders get the selectable bit outright (Brightness itself lacks it; the
    // controller patch reaches it through the graphics screen's own table) and
    // Brightness's events.
    for(void* slider:sliders){SelectableAs(slider,owner,"SLI_GAMMA");At<unsigned>(slider,0x44)|=8u;SliderEvents(slider,p);}
    SelectableAs(iconSlider,owner,"SLI_GAMMA");At<unsigned>(iconSlider,0x44)|=8u;SliderEvents(iconSlider,p);
    SelectableAs(linkSizes,owner,"CB_SHADOWS");
    for(void* choice:fontChoices)SelectableAs(choice,owner,"CB_SHADOWS");
    SelectableAs(defaults,owner,"BTN_DEFAULT");
    SelectableAs(back,owner,"BTN_BACK");
    Extent(p,At<Rect>(owner,4));
    const auto rect=[owner](const char* tag){return At<Rect>(KmrpRuntimeControlByTagK1(owner,tag),4);};
    Extent(title,rect("LBL_TITLE"));
    Extent(defaults,rect("BTN_DEFAULT"));Extent(back,rect("BTN_BACK"));
    const Rect label=rect("LBL_GAMMA"), track=rect("SLI_GAMMA"), checkbox=rect("CB_SHADOWS");
    const int gap=(std::max)(2,track.height/3);
    const Rect advanced=rect("BTN_ADVANCED");
    const int bottom=(std::min)(advanced.top+advanced.height,rect("BTN_DEFAULT").top-gap);
    // The four text sizes and, under them, the icon size: five pairs. Where five do not fit
    // with each slider as far under its caption as Brightness's is, the slider comes up to
    // just under its caption (1024x576: 30 px under it there, 29 tall, 58 a pair).
    const int step=(bottom-label.top-checkbox.height-gap)/(TextGroupCount+1);
    // At 1400x1050 and 1680x1050 a caption's box (53) and its slider (53) are one more than a
    // pair's share (105): there the box, taller than its text, gives up that pixel.
    const int captionHeight=(std::min)(label.height,step-track.height);
    const int pairOffset=(std::max)(captionHeight,(std::min)(track.top-label.top,step-track.height));
    // "Link Text Sizes" at the top of the column and the four pairs under it, so the
    // page opens on the link and right from it reaches the fonts without passing every
    // slider, whose own right moves it (the maintainer, 2026-10-19). Until then the
    // link stood under the pairs.
    Extent(linkSizes,{label.left,label.top,label.width,checkbox.height});
    const int first=checkbox.height+gap;
    for(int i=0;i<=TextGroupCount;++i) {
        Rect l=label,t=track;l.top+=first+i*step;l.height=captionHeight;t.top=l.top+pairOffset;
        void* caption=i<TextGroupCount?sizeLabels[i]:iconLabel;
        void* slider=i<TextGroupCount?sliders[i]:iconSlider;
        Extent(caption,l);Extent(slider,t);
        Fn<void(__thiscall*)(void*,int)>(0x417EC0)(slider,SliderMaximum);
    }

    Text(linkSizes,"Link Text Sizes",true);
    for(void* mark:{defaultsMark,backMark}){Text(mark,"");At<unsigned>(mark,0x44)&=~2u;}
    defaultsButton=defaults;backButton=back;
    defaultsGlyph=KmrpOptionsPad::Glyph{};defaultsGlyph.label=defaultsMark;defaultsGlyph.button=defaults;defaultsGlyph.code='y';
    backGlyph=KmrpOptionsPad::Glyph{};backGlyph.label=backMark;backGlyph.button=back;backGlyph.code='b';
    // On the pixels of Graphics Options' own Y and B: the same buttons, the same captions.
    defaultsGlyph.badge="kmrpy_optgfxdef";backGlyph.badge="kmrpb_optgfx";
    KmrpOptionsPad::SkipFocus(defaults,true);KmrpOptionsPad::SkipFocus(back,true);
    // The right-hand column, inside the frame the player sees round the description list:
    // the frame stands 23/86 of the list's scrollbar width left of the list and ends 13/86
    // of it short of the scrollbar's strip, which it does not cover (measured at 3440x1440
    // for the HUD Size page, K1HudOptions.cpp). The column keeps its left, a 32nd of the
    // list's width in from the list, and stays as far in from the frame on the right.
    // Until 2026-10-19 it ended a 32nd of the width short of the list's right edge, over
    // the strip: at 1440x1080 "(New) Original HD Font", "Subtitles and descriptions" and
    // "Small text preview" ran past the frame (the maintainer's capture).
    Rect desc=rect("LB_DESC");
    {
        const int bar=At<int>(KmrpRuntimeControlByTagK1(owner,"LB_DESC"),0x110);
        const int inset=desc.width/32;
        if(bar>0 && bar<desc.width/2) {
            const int outside=(bar*23+43)/86, shortOfStrip=(bar*13+43)/86;
            const int frameRight=desc.left+desc.width-bar-shortOfStrip;
            desc.left+=inset;
            desc.width=frameRight-(inset+outside)-desc.left;
        } else {desc.left+=inset;desc.width-=2*inset;}
    }
    const int margin=(std::max)(2,desc.height/32);
    Rect choiceRect={desc.left,desc.top+margin,desc.width,rect("BTN_RESOLUTION").height};
    for(int i=0;i<FontChoiceCount;++i) {
        Extent(fontChoices[i],choiceRect);choiceRect.top+=choiceRect.height+gap;
    }
    // The icons' preview at the bottom, as tall as the largest icon (100%) and never more than
    // half the column under the fonts; one short sample per font group above it, each in the
    // native renderer.
    screenHeight=At<short>(manager,0x6E);
    {
        const double scale=kmrp_icon_scale(screenHeight);
        const int biggest=kmrp_icon_drawn(kmrp_icon_feat_today(scale,KMRP_ICON_NATIVE),scale,KMRP_ICON_MAXIMUM);
        const int columnBottom=desc.top+desc.height-margin;
        const int room=(std::min)(biggest+2*margin,(columnBottom-choiceRect.top)/2);
        iconArea={desc.left,columnBottom-room,desc.width,room};
    }
    const int previewStep=(iconArea.top-choiceRect.top)/TextGroupCount;
    for(int i=0;i<TextGroupCount;++i) {
        Extent(previews[i],{desc.left,choiceRect.top+i*previewStep,desc.width,previewStep});
        char font[16]{};strcpy_s(font,previewFonts[i]);
        Fn<void(__thiscall*)(void*,const char*)>(0x415DD0)(static_cast<char*>(previews[i])+0xE8,font);
        Text(previews[i],previewTexts[i]);
    }
    // Preserve a native text control for save/application errors without consuming
    // the sliders' space. Hidden until an error message needs to be displayed.
    Extent(help,{desc.left,choiceRect.top,desc.width,desc.top+desc.height-choiceRect.top});
    for(void* icon:iconPreviews)Text(icon,"");   // a picture, not the template's "Brightness"
    PlaceIconPreviews(iconSize);
#ifndef KMRP_TEXT_OPTIONS_TEST   // the harness has no border images to set
    KmrpOptionsPad::Batch(true);
    for(int i=0;i<3;++i) {
        unsigned& flags=At<unsigned>(iconPreviews[i],KmrpOptionsPad::kLabelParams+KmrpOptionsPad::kParamsFlags);
        flags=(flags&~3u)|2u;   // drawn at the label's size, which is the icon's
        KmrpOptionsPad::SetPicture(static_cast<char*>(iconPreviews[i])+KmrpOptionsPad::kLabelParams,iconPreviewNames[i],&NativeRoutine);
    }
    KmrpOptionsPad::Batch(false);
#endif
    At<unsigned>(help,0x44)&=~2u;
    Text(title,"Text Size and Font");
    Text(fontChoices[ChoiceOf(Original)],"Original Font",true);
    Text(fontChoices[ChoiceOf(HdOriginal)],"HD Font",true);
    Fn<Event>(0x41AB20)(linkSizes,0x27,p,reinterpret_cast<void*>(&ToggleLink));
    Fn<Event>(0x41AB20)(fontChoices[ChoiceOf(Original)],0x27,p,reinterpret_cast<void*>(&SelectOriginal));
    Fn<Event>(0x41AB20)(fontChoices[ChoiceOf(HdOriginal)],0x27,p,reinterpret_cast<void*>(&SelectHdOriginal));
    Fn<Event>(0x41AB20)(defaults,0x27,p,reinterpret_cast<void*>(&Defaults));
    Fn<Event>(0x41AB20)(back,0x27,p,reinterpret_cast<void*>(&Back));
    // The pad's focus: the link and the four sliders under it, up and down and round;
    // the fonts, up and down and round; left and right between the link and the font
    // chosen (UpdateCaptions), and nothing from a slider, whose left and right move it.
    // Default and Close are off the pad's focus (Y and B, Input); their links are the
    // keys'.
    Navigation(linkSizes,iconSlider,sliders[0]);
    for(int i=0;i<TextGroupCount;++i)
        Navigation(sliders[i],i?sliders[i-1]:linkSizes,i+1<TextGroupCount?sliders[i+1]:iconSlider);
    Navigation(iconSlider,sliders[TextGroupCount-1],linkSizes);
    Navigation(fontChoices[0],fontChoices[1],fontChoices[1],linkSizes,linkSizes);
    Navigation(fontChoices[1],fontChoices[0],fontChoices[0],linkSizes,linkSizes);
    Navigation(defaults,iconSlider,linkSizes,back,back);
    Navigation(back,fontChoices[FontChoiceCount-1],fontChoices[0],defaults,defaults);
    Fn<Focus>(0x40A630)(p,linkSizes,0);
    displayedSizes.fill(-1);displayedLinked=displayedStyle=displayedIcon=-1;
    releasedFrames=0;UpdateCaptions();
    // The pad's Y and B before the page is shown, not on its next frame: they popped in
    // after it (the maintainer, 2026-10-28).
    KmrpOptionsPad::Batch(true);
    KmrpOptionsPad::Update(defaultsGlyph,KmrpOptionsPad::PadInUse(),KmrpOptionsPad::Family(),&NativeRoutine);
    KmrpOptionsPad::Update(backGlyph,KmrpOptionsPad::PadInUse(),KmrpOptionsPad::Family(),&NativeRoutine);
    KmrpOptionsPad::Batch(false);
    Fn<void(__thiscall*)(void*,void*,int,int)>(0x40BC70)(manager,p,3,1);
}
void UpdateEntry(void* owner,Entry& e) {
    void* advanced=KmrpRuntimeControlByTagK1(owner,"BTN_ADVANCED");
    if(!advanced || At<std::uintptr_t>(advanced,0)!=ButtonTable)return;
    if(!e.button) {
        e.button=CloneButton(owner,advanced);e.advanced=advanced;
        if(!e.button)return;
        Text(e.button,"Text Size and Font",true);
        Fn<Event>(0x41AB20)(e.button,0x27,owner,reinterpret_cast<void*>(&Open));
    }
    const Rect wanted=KmrpTextOptions::Entry(At<Rect>(advanced,4));
    if(std::memcmp(&At<Rect>(e.button,4),&wanted,sizeof wanted))Extent(e.button,wanted);
    // Follow the button's native focus policy, including skins that change it.
    At<unsigned>(e.button,0x44)=(At<unsigned>(e.button,0x44)&~4u)|(At<unsigned>(advanced,0x44)&4u);
    void* above=At<void*>(advanced,0x5C);
    if(above!=e.button) {
        Navigation(e.button,above,advanced,At<void*>(advanced,0x60),At<void*>(advanced,0x68));
        At<void*>(advanced,0x5C)=e.button;
        if(above && above!=advanced && At<void*>(above,0x64)==advanced)At<void*>(above,0x64)=e.button;
    }
}
// The entry's A, as Advanced Options' below it has, while the entry has its screen's
// focus, the pad is in use and neither KMRP page is open over the screen
// (K1OptionsPad.h; the maintainer, 2026-10-19). Painted only on a change.
void EntryBadge(void* owner,Entry& e,bool pad,char family) {
    if(!e.button)return;
    const bool want=pad && !current && !KmrpHudOptionsOpenK1() && At<void*>(owner,0x1C)==e.button;
    if(int(want)==e.badged && (!want || family==e.family))return;
    KmrpOptionsPad::EntryBadge(e.button,want);
    e.badged=want;e.family=family;
}
void Error(const char* message) {
    if(!help)return;
    At<unsigned>(help,0x44)=(At<unsigned>(help,0x44)&~2u)|(message?2u:0u);
    for(void* p:previews)if(p)At<unsigned>(p,0x44)=(At<unsigned>(p,0x44)&~2u)|(message?0u:2u);
    if(message)Text(help,message);
}
void ReloadFonts(bool images) {
    void** textures=*static_cast<void***>(Native(0x7A4798));
    const int count=*static_cast<int*>(Native(0x7A479C));
    if(!textures || count<0 || count>0x100000)return;
    for(int i=0;i<count;++i) {
        void* texture=textures[i];
        if(!texture || !At<void*>(texture,0x38))continue;
        char name[17]{};std::memcpy(name,static_cast<char*>(texture)+0x98,16);
        if(!KmrpRuntimeIsFontK1(name))continue;
        // All styles retain the same native texture/font objects.
        // Reset frees image/GL state, not the CAurFontInfo used by GUI strings.
        if(images)Fn<Simple>(0x420670)(texture);
        Fn<void(__thiscall*)(void*,const char*)>(0x422AF0)(texture,static_cast<char*>(texture)+0x98);
        if(images)Fn<void(__thiscall*)(void*,void*)>(0x46BD10)(Native(0x7A4770),texture);
    }
    // ConstructImage only decodes CPU pixels. The normal build queue also
    // uploads GL images and rebuilds the engine's texture-ID registry.
    if(images)Fn<void(__cdecl*)()>(0x4217F0)();
    KmrpReflowTextK1();
}
}

void* KmrpTextOptionsEntryK1(void* owner){
    const auto found=entries.find(owner);
    return found==entries.end()?nullptr:found->second.button;
}
bool KmrpTextOptionsOpenK1(){return current!=nullptr;}
int KmrpTextSizePercentK1(){Initialize();return sizing.values[Menus];}
int KmrpIconSizePercentK1(){Initialize();return iconSize;}
int KmrpTextSizeForFontK1(const char* font){Initialize();return sizing.values[FontGroup(font)];}
int KmrpTextFontStyleK1(){Initialize();return style;}
bool KmrpSetTextPreferencesK1(int size,int fontStyle) {
    Initialize();requestedSizing.Set(Menus,size);requestedStyle=Style(fontStyle);
    Dirty();return true;
}
void KmrpTextOptionsDestroyedK1(void* panel) {
    const auto found=entries.find(panel);
    if(found!=entries.end()) {
        void* button=found->second.button;
        void** array=At<void**>(panel,0x20);
        for(int i=0;array && i<At<int>(panel,0x24);++i)if(array[i]==button)array[i]=nullptr;
        entries.erase(found);DestroyControl(button);
    }
    if(pending==panel)pending=nullptr;
    if(parent==panel){parent=returnFocus=nullptr;Close();}
}
void KmrpTextOptionsFrameK1(void* manager) {
    if(!manager)return;
    Initialize();
    // Latch after the opening press has been released. Resetting on every new
    // press would block the button callback while that very click/A is held.
    if(!Armed()) {
        if(ConfirmHeld())releasedFrames=0;
        else ++releasedFrames;
    }
    if(blockReopen && Armed())blockReopen=false;
    const bool pad=KmrpOptionsPad::PadInUse();
    const char family=KmrpOptionsPad::Family();
    for(void* p:KmrpRuntimePanelsK1("optgraphics"))
        if(At<std::uintptr_t>(p,0)==GraphicsTable){UpdateEntry(p,entries[p]);EntryBadge(p,entries[p],pad,family);}
    if(current) {
        // The two pictures listed in one go by the controller patch (K1OptionsPad.h).
        KmrpOptionsPad::Batch(true);
        KmrpOptionsPad::Update(defaultsGlyph,pad,family,&NativeRoutine);
        KmrpOptionsPad::Update(backGlyph,pad,family,&NativeRoutine);
        KmrpOptionsPad::Batch(false);
    }
    if(pending) {
        void* owner=pending;pending=nullptr;
        if(!current && Fn<Exists>(0x40BD70)(manager,owner))MakeScreen(manager,owner);
    }
    if(current && sliders[0] && !dirty) {
        for(int i=0;i<TextGroupCount;++i) {
            const int moved=Minimum+(std::max)(0,(std::min)(SliderMaximum,At<int>(sliders[i],0x74)))*Step;
            if(moved!=requestedSizing.values[i]){requestedSizing.Set(i,moved);Dirty();break;}
        }
    }
    // The Icon Size slider: its caption, preview and size follow it at once.
    if(current && iconSlider) {
        const int moved=Minimum+(std::max)(0,(std::min)(SliderMaximum,At<int>(iconSlider,0x74)))*Step;
        if(moved!=requestedIcon){requestedIcon=moved;UpdateCaptions();PlaceIconPreviews(requestedIcon);}
    }
    if(requestedIcon!=iconSize) {
        iconSize=requestedIcon;
        KmrpRuntimeApplyIconSizeK1();
        if(Save())Error(nullptr);else Error("Could not save settings.\nChanges apply this session.");
        PlaceIconPreviews(iconSize);
        UpdateCaptions();
    }
    if(dirty) {
        const Sizes previous=sizing;const int previousFont=style;
        sizing=requestedSizing;style=requestedStyle;dirty=false;
        if(previousFont==style || KmrpRuntimeApplyTextPreferencesK1()) {
            if(previous.values!=sizing.values || previousFont!=style)ReloadFonts(previousFont!=style);
            if(Save())Error(nullptr);else Error("Could not save settings.\nChanges apply this session.");
        } else {
            sizing=requestedSizing=previous;style=requestedStyle=previousFont;
            KmrpRuntimeApplyTextPreferencesK1();
            Error("Font could not be changed.\nPrevious selection kept.");
        }
        UpdateCaptions();
    }
}
