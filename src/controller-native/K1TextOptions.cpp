// Native K1 settings, using the graphics screen's actual templates and geometry.
// No pre-authored .gui, fixed resolution, or dependency on controller support.
#include "K1TextOptions.h"
#include "K1TextOptionsPolicy.h"
#include "K1RuntimeAssets.h"
#include "K1RuntimeLayout.h"
#include "K1SliderGrip.h"
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
struct Entry { void* button=nullptr; void* advanced=nullptr; };
std::map<void*,Entry> entries;
void *pending=nullptr, *current=nullptr, *parent=nullptr, *returnFocus=nullptr;
std::uintptr_t table[27]{};
std::vector<void*> owned;
void* sizeLabels[TextGroupCount]{};
void* sliders[TextGroupCount]{};
void* linkSizes=nullptr;
void* previews[TextGroupCount]{};
void* help=nullptr;
const wchar_t* const groupKeys[]={L"MenuSize",L"BodySize",L"SmallSize",L"HudSize"};
const char* const groupLabels[]={"Menus & Replies","Subtitles & Body","Small Text","HUD Text"};
const char* const previewFonts[]={"dialogfont16x16","fnt_d16x16","dialogfont10x10","fnt_console"};
const char* const previewTexts[]={"Menus and reply choices","Subtitles and descriptions","Small text preview","HUD: 0123456789"};
void* fontChoices[FontStyleCount]{};
bool initialized=false, dirty=false;
int style=NewHd, requestedStyle=NewHd;
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

bool ConfigPath(wchar_t (&path)[MAX_PATH]) {
    const DWORD n=GetModuleFileNameW(nullptr,path,MAX_PATH);
    wchar_t* slash=n && n<MAX_PATH?std::wcsrchr(path,L'\\'):nullptr;
    return slash && !wcscpy_s(slash+1,MAX_PATH-(slash+1-path),L"swkotor.ini");
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
        const int legacy=GetPrivateProfileIntW(L"KMRP Text",L"OriginalFont",0,path)?OriginalSharpened:NewHd;
        style=Style(GetPrivateProfileIntW(L"KMRP Text",L"FontStyle",legacy,path));
    }
    requestedSizing=sizing;requestedStyle=style;
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
    swprintf_s(value,L"%d",style);
    return WritePrivateProfileStringW(L"KMRP Text",L"FontStyle",value,path) &&
        WritePrivateProfileStringW(L"KMRP Text",L"OriginalFont",style==NewHd?L"0":L"1",path);
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
void __fastcall SelectSharpened(void*,void*,void*) {Choose(OriginalSharpened);}
void __fastcall SelectHd(void*,void*,void*) {Choose(NewHd);}
void __fastcall Defaults(void*,void*,void*) {
    if(Armed()){requestedSizing=Sizes{};requestedStyle=NewHd;Dirty();releasedFrames=0;}
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
void __fastcall Input(void* self,void*,int event,int value) {
    if(value && event==0x28){Close();return;}
    Fn<void(__thiscall*)(void*,int,int)>(0x409E60)(self,event,value);
}
void* __fastcall Destroy(void* self,void*,unsigned flags) {
    void* manager=At<void*>(self,0x18);
    if(manager && Fn<Exists>(0x40BD70)(manager,self))Fn<Exists>(0x40C830)(manager,self);
    Fn<Focus>(0x40A630)(self,nullptr,0);
    auto array=At<void**>(self,0x20);
    for(int i=0;array && i<At<int>(self,0x24);++i)array[i]=nullptr;
    for(void* c:owned)DestroyControl(c);
    owned.clear();help=linkSizes=nullptr;
    for(void*& p:sizeLabels)p=nullptr;
    for(void*& p:sliders)p=nullptr;
    for(void*& p:previews)p=nullptr;
    for(void*& choice:fontChoices)choice=nullptr;
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
    if(displayedLinked!=int(requestedSizing.linked)) {
        Fn<void(__thiscall*)(void*,unsigned)>(0x685540)(linkSizes,requestedSizing.linked);
        displayedLinked=requestedSizing.linked;
    }
    if(displayedStyle!=requestedStyle) {
        for(int i=0;i<FontStyleCount;++i)
            Fn<void(__thiscall*)(void*,unsigned)>(0x685540)(fontChoices[i],i==requestedStyle);
        displayedStyle=requestedStyle;
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
    void* defaults=Bind(p,"BTN_DEFAULT",0x1C4,0x41C0F0);
    void* back=Bind(p,"BTN_BACK",0x1C4,0x41C0F0);
    Fn<Simple>(0x40B8F0)(p);
    bool complete=title && linkSizes && fontChoices[0] && fontChoices[1] && fontChoices[2] && help && defaults && back;
    for(int i=0;i<TextGroupCount;++i)complete=complete && sizeLabels[i] && sliders[i] && previews[i];
    if(!complete) {
        Destroy(p,nullptr,1);return;
    }
    // The sliders get the selectable bit outright (Brightness itself lacks it; the
    // controller patch reaches it through the graphics screen's own table) and
    // Brightness's events.
    for(void* slider:sliders){SelectableAs(slider,owner,"SLI_GAMMA");At<unsigned>(slider,0x44)|=8u;SliderEvents(slider,p);}
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
    const int step=(bottom-label.top-checkbox.height-gap)/TextGroupCount;
    for(int i=0;i<TextGroupCount;++i) {
        Rect l=label,t=track;l.top+=i*step;t.top+=i*step;
        Extent(sizeLabels[i],l);Extent(sliders[i],t);
        Fn<void(__thiscall*)(void*,int)>(0x417EC0)(sliders[i],SliderMaximum);
    }
    Extent(linkSizes,{label.left,label.top+TextGroupCount*step+gap,label.width,checkbox.height});
    Text(linkSizes,"Link Text Sizes",true);
    Rect desc=rect("LB_DESC");desc.left+=desc.width/32;desc.width-=desc.width/16;
    const int margin=(std::max)(2,desc.height/32);
    Rect choiceRect={desc.left,desc.top+margin,desc.width,rect("BTN_RESOLUTION").height};
    for(int i=FontStyleCount-1;i>=0;--i) {
        Extent(fontChoices[i],choiceRect);choiceRect.top+=choiceRect.height+gap;
    }
    // One short sample per font group. All sizes use the same native renderer.
    const int previewStep=(desc.top+desc.height-choiceRect.top-margin)/TextGroupCount;
    for(int i=0;i<TextGroupCount;++i) {
        Extent(previews[i],{desc.left,choiceRect.top+i*previewStep,desc.width,previewStep});
        char font[16]{};strcpy_s(font,previewFonts[i]);
        Fn<void(__thiscall*)(void*,const char*)>(0x415DD0)(static_cast<char*>(previews[i])+0xE8,font);
        Text(previews[i],previewTexts[i]);
    }
    // Preserve a native text control for save/application errors without consuming
    // the sliders' space. Hidden until an error message needs to be displayed.
    Extent(help,{desc.left,choiceRect.top,desc.width,desc.top+desc.height-choiceRect.top});
    At<unsigned>(help,0x44)&=~2u;
    Text(title,"Text Size and Font");
    Text(fontChoices[Original],"Original Font",true);
    Text(fontChoices[OriginalSharpened],"Original Sharpened Font",true);
    Text(fontChoices[NewHd],"New HD Font",true);
    Fn<Event>(0x41AB20)(linkSizes,0x27,p,reinterpret_cast<void*>(&ToggleLink));
    Fn<Event>(0x41AB20)(fontChoices[Original],0x27,p,reinterpret_cast<void*>(&SelectOriginal));
    Fn<Event>(0x41AB20)(fontChoices[OriginalSharpened],0x27,p,reinterpret_cast<void*>(&SelectSharpened));
    Fn<Event>(0x41AB20)(fontChoices[NewHd],0x27,p,reinterpret_cast<void*>(&SelectHd));
    Fn<Event>(0x41AB20)(defaults,0x27,p,reinterpret_cast<void*>(&Defaults));
    Fn<Event>(0x41AB20)(back,0x27,p,reinterpret_cast<void*>(&Back));
    for(int i=0;i<TextGroupCount;++i)
        Navigation(sliders[i],i?sliders[i-1]:back,i+1<TextGroupCount?sliders[i+1]:linkSizes);
    Navigation(linkSizes,sliders[TextGroupCount-1],fontChoices[Original]);
    Navigation(fontChoices[Original],linkSizes,fontChoices[OriginalSharpened]);
    Navigation(fontChoices[OriginalSharpened],fontChoices[Original],fontChoices[NewHd]);
    Navigation(fontChoices[NewHd],fontChoices[OriginalSharpened],defaults);
    Navigation(defaults,fontChoices[NewHd],sliders[0],back,back);
    Navigation(back,fontChoices[NewHd],sliders[0],defaults,defaults);
    Fn<Focus>(0x40A630)(p,sliders[0],0);
    displayedSizes.fill(-1);displayedLinked=displayedStyle=-1;
    releasedFrames=0;UpdateCaptions();
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
int KmrpTextSizePercentK1(){Initialize();return sizing.values[Menus];}
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
    for(void* p:KmrpRuntimePanelsK1("optgraphics"))
        if(At<std::uintptr_t>(p,0)==GraphicsTable)UpdateEntry(p,entries[p]);
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
