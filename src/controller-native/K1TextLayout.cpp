// Draw-compatible per-instance fitting for native K1 GUI strings.
// See docs/native-text-coverage.md and docs/text-layout-inventory.md.
#include "K1TextLayout.h"
#include "K1TextFitPolicy.h"
#include "K1TextRows.h"
#include "K1TextOptions.h"
#include "K1CaptionInk.h"
#include <algorithm>
#include <climits>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <limits>
#include <map>
#include <string>
#include <tuple>
#include <vector>

#ifdef KMRP_TEXT_LAYOUT_TEST
void* KmrpTextLayoutTestFunction(std::uintptr_t address);
void* KmrpTextLayoutTestAddress(std::uintptr_t address);
#endif

namespace {
template<class T> T& At(void* p, unsigned offset) {
    return *reinterpret_cast<T*>(static_cast<char*>(p) + offset);
}
void* Native(std::uintptr_t address) {
#ifdef KMRP_TEXT_LAYOUT_TEST
    return KmrpTextLayoutTestAddress(address);
#else
    return reinterpret_cast<void*>(address);
#endif
}
template<class T> T Fn(std::uintptr_t address) {
#ifdef KMRP_TEXT_LAYOUT_TEST
    return reinterpret_cast<T>(KmrpTextLayoutTestFunction(address));
#else
    return reinterpret_cast<T>(address);
#endif
}
std::uintptr_t* Table(void* object) {
    return static_cast<std::uintptr_t*>(Native(At<std::uintptr_t>(object, 0)));
}
struct Rect { int left, top, width, height; };
bool Same(const Rect& a, const Rect& b) {
    return a.left == b.left && a.top == b.top && a.width == b.width && a.height == b.height;
}
void Extent(void* control, const Rect& value) {
    if (!Same(At<Rect>(control, 4), value))
        Fn<void(__thiscall*)(void*, const Rect*)>(Table(control)[1])(control, &value);
}
enum class Mode { Bounded, Flow, Editable };
struct Metrics {
    void* font = nullptr;
    void* info = nullptr;
    const float* first = nullptr;
    const float* last = nullptr;
    double height = 0, textureWidth = 0, spacing = 0, leading = 0;
};
struct Key {
    void* font = nullptr;
    void* info = nullptr;
    const char* text = nullptr;
    const float* first = nullptr;
    const float* last = nullptr;
    std::uint64_t hash = 0;
    unsigned generation = 0;
    int width = 0, height = 0;
    float requested = 1;
    double lineHeight = 0, textureWidth = 0, spacing = 0, leading = 0;
    unsigned alignment = 0;
    Mode mode = Mode::Bounded;
    bool operator==(const Key& b) const {
        return std::tie(font,info,text,first,last,hash,generation,width,height,requested,
                        lineHeight,textureWidth,spacing,leading,alignment,mode) ==
               std::tie(b.font,b.info,b.text,b.first,b.last,b.hash,b.generation,b.width,b.height,b.requested,
                        b.lineHeight,b.textureWidth,b.spacing,b.leading,b.alignment,b.mode);
    }
};
struct StringState {
    float requested = 1, applied = 1;
    // The last fit's result, and whether a native wrap or measurement has put the
    // request back since (see Restore): the next draw re-applies it, one wrap.
    float fitted = 1;
    bool restored = false;
    Mode mode = Mode::Bounded;
    bool cached = false;
    Key key{};
    KmrpTextFit::Measurement measured{0,0,0,false};
    std::vector<int> drawWidths, drawLengths;
    // Its letters on its box's middle (CentreLetters): the top the layout gave it, the
    // one written, and what the move was worked out for.
    bool inkMoved = false;
    int inkFrom = 0, inkTo = 0;
    const void* inkInfo = nullptr;
    const char* inkText = nullptr;
    std::uint64_t inkHash = 0;
    float inkScale = 0;
    int inkShift = 0;
    bool inkRead = false;     // the font was read for inkShift; else it is asked again
    // The middle, on screen, of the art its control is drawn on (ArtCaptions), or
    // INT_MIN: its letters go there instead of its box's middle.
    int artMiddle = INT_MIN;
};
std::map<void*, StringState> strings;
unsigned generation = 1;
bool measuring = false;
struct Measuring {
    bool was;
    Measuring() : was(measuring) { measuring = true; }
    ~Measuring() { measuring = was; }
};
bool Scale(float value) { return std::isfinite(value) && value > 0 && value <= 128; }
void ObserveScale(void* object, StringState& state) {
    const float current = At<float>(object, 0x40);
    if (Scale(current) && current != state.applied) {
        state.requested = current;
        state.applied = current;
        state.cached = false;
    }
}
void WriteScale(void* object, StringState& state, float value) {
    At<float>(object, 0x40) = value;
    state.applied = value;
}
void Wrap(void* object) {
    Measuring guard;
    Fn<void(__thiscall*)(void*, int)>(0x45A2F0)(object, -1);
}
bool Font(void* object, Metrics& result) {
    result.font = At<void*>(object, 0x18);
    if (!result.font) return false;
    result.info = Fn<void*(__thiscall*)(void*)>(Table(result.font)[0x38 / 4])(result.font);
    if (!result.info) return false;
    result.height = At<float>(result.info, 4) * 100.0;
    result.textureWidth = At<float>(result.info, 0x0C);
    result.spacing = At<float>(result.info, 0x10);
    result.leading = At<float>(result.info, 0x14) * 100.0;
    result.first = At<const float*>(result.info, 0x18);
    result.last = At<const float*>(result.info, 0x24);
    return result.first && result.last && std::isfinite(result.height) && result.height > 0 &&
        result.height < 65536 && std::isfinite(result.textureWidth) && result.textureWidth > 0 &&
        result.textureWidth < 65536 && std::isfinite(result.spacing) && std::fabs(result.spacing) < 65536 &&
        std::isfinite(result.leading) && std::fabs(result.leading) < 65536;
}
bool MakeKey(void* object, const StringState& state, const Metrics& font, Key& key) {
    const char* text = At<const char*>(object, 0x14);
    if (!text || !*text) return false;
    // The game owns this buffer. Hash contents as well as its address: its
    // allocator and some setters reuse a buffer for a different HUD message.
    std::uint64_t hash = 1469598103934665603ull;
    unsigned length = 0;
    for (; length < 262144 && text[length]; ++length) {
        hash ^= static_cast<unsigned char>(text[length]);
        hash *= 1099511628211ull;
    }
    if (length == 262144) return false;
    key.font=font.font; key.info=font.info; key.text=text;
    key.first=font.first; key.last=font.last; key.hash=hash;
    key.generation=generation; key.width=At<int>(object,0x0C); key.height=At<int>(object,0x10);
    key.requested=state.requested; key.lineHeight=font.height; key.textureWidth=font.textureWidth;
    key.spacing=font.spacing; key.leading=font.leading; key.mode=state.mode;
    key.alignment=At<unsigned char>(object,0x46);
    return key.width > 0 && key.width <= 32767 && key.height >= 0 && key.height <= 32767;
}
KmrpTextFit::Measurement WrappedMeasurement(void* object, float scale, const Metrics& font,
                                           std::vector<int>* drawWidths=nullptr,
                                           std::vector<int>* drawLengths=nullptr) {
    const int count = At<int>(object, 0x38);
    const int widthsCount = At<int>(object, 0x2C);
    const int* lengths = At<const int*>(object, 0x34);
    const int* widths = At<const int*>(object, 0x28);
    const char* cursor = At<const char*>(object, 0x14);
    if (count < 0 || count > 262144 || widthsCount < count ||
        (count && (!lengths || !widths)) || !cursor) return {0,0,0,false};
    double widest = 0;
    std::size_t consumed = 0;
    if(drawWidths)drawWidths->clear();
    if(drawLengths)drawLengths->clear();
    for (int line=0; line<count; ++line) {
        const int signedLength=lengths[line];
        if (signedLength == (std::numeric_limits<int>::min)()) return {0,0,0,false};
        const unsigned length=static_cast<unsigned>(signedLength<0?-signedLength:signedLength);
        if (length > 262144 || consumed + length > 262144) return {0,0,0,false};
        double pen=0, right=0;
        const auto glyph = [&](unsigned char value) {
            const unsigned g=static_cast<unsigned>(value)*3;
            const double width=(font.last[g]-font.first[g])*font.textureWidth*100.0*scale;
            right=(std::max)(right,pen+width);
            pen+=width+font.spacing*100.0*scale;
        };
        for (unsigned i=0;i<length;++i) {
            if (!cursor[i]) return {0,0,0,false};
            glyph(static_cast<unsigned char>(cursor[i]));
        }
        if (signedLength<0) glyph('-');
        widest=(std::max)(widest,(std::max)(right,static_cast<double>(widths[line])));
        // Native centering/right alignment uses this integer array, while the
        // glyph quads use fractional advances (Draw 0x45AC40/0x45AC75). Round
        // outward so alignment cannot put a fitting last glyph beyond the box.
        if(drawWidths) {
            if(!std::isfinite(right) || right>(std::numeric_limits<int>::max)())
                return {0,0,0,false};
            drawWidths->push_back((std::max)(widths[line],static_cast<int>(std::ceil(right))));
        }
        if(drawLengths)drawLengths->push_back(signedLength);
        cursor+=length; consumed+=length;
        if (*cursor=='\n' || *cursor==' ') {++cursor;++consumed;}
    }
    const double line=font.height*scale;
    const double leading=count>1?(count-1)*(std::max)(0.0,font.leading*scale):0.0;
    // Draw centers by count*fontHeight, then advances lines by fontHeight plus
    // leading. A centered block therefore needs the leading on both sides of
    // its centering equation, not only in its total drawn height.
    const bool centered=(At<unsigned char>(object,0x46)&0x38)==0x10;
    const double height=count*line+(centered?2.0:1.0)*leading;
    return {widest,height,count,std::isfinite(widest) && widest>=0 && std::isfinite(height)};
}
KmrpTextFit::Measurement Measure(void* object, float scale, const Metrics& font) {
    At<float>(object, 0x40) = scale;
    Wrap(object);
    return WrappedMeasurement(object,scale,font);
}
void DrawWidths(void* object, const StringState& state) {
    if(state.mode!=Mode::Bounded || !state.cached ||
       At<int>(object,0x38)!=static_cast<int>(state.drawWidths.size()) ||
       At<int>(object,0x2C)<At<int>(object,0x38))return;
    int* widths=At<int*>(object,0x28);
    const int* lengths=At<const int*>(object,0x34);
    if(!widths || !lengths || state.drawLengths.size()!=state.drawWidths.size())return;
    for(std::size_t i=0;i<state.drawLengths.size();++i)
        if(lengths[i]!=state.drawLengths[i])return;
    for(std::size_t i=0;i<state.drawWidths.size();++i)widths[i]=state.drawWidths[i];
}
void Apply(void* object, bool outerWrap) {
    if (!object || measuring) return;
    const auto found=strings.find(object);
    if (found==strings.end()) return;  // construction has not completed yet
    StringState& state=found->second;
    ObserveScale(object,state);
    if (state.mode==Mode::Flow) {
        if (At<float>(object,0x40)!=state.requested) {
            WriteScale(object,state,state.requested);
            if (!outerWrap) Wrap(object);
        }
        return;
    }
    Metrics font;
    Key key;
    if (!Font(object,font) || !MakeKey(object,state,font,key) || key.height<=0) return;
    if (state.cached && state.key==key) {
        // Same text, box and font as the last fit: put its result back if a native
        // wrap or measurement restored the request since. One wrap, no search.
        if (state.restored && state.fitted!=At<float>(object,0x40)) {
            WriteScale(object,state,state.fitted);
            if (!outerWrap) Wrap(object);
        }
        state.restored=false;
        return;
    }
    state.restored=false;
    const auto measure=[&](float scale) {
        if (state.mode==Mode::Editable) {
            // The underscore caret is in this same string. Never shrink a
            // growing input by its length or change its native horizontal rules.
            return KmrpTextFit::Measurement{0,font.height*scale,1,true};
        }
        return Measure(object,scale,font);
    };
    const KmrpTextFit::Bounds bounds{static_cast<double>(key.width),static_cast<double>(key.height)};
    const float effective=KmrpTextFit::Fit(state.requested,bounds,measure);
    WriteScale(object,state,effective);
    state.fitted=effective;
    // The last solver trial might not have been its returned value (invalid
    // native measurement keeps the request). Finish with one consistent wrap.
    if (!outerWrap || state.mode!=Mode::Editable) Wrap(object);
    state.drawWidths.clear();state.drawLengths.clear();
    if(state.mode==Mode::Bounded) {
        const auto final=WrappedMeasurement(object,effective,font,&state.drawWidths,&state.drawLengths);
        if(!final.valid) {state.drawWidths.clear();state.drawLengths.clear();}
    }
    state.key=key; state.cached=true;
}
void* Internal(void* wrapper) {
    if (!wrapper) return nullptr;
    const auto table=At<std::uintptr_t>(wrapper,0);
    if (table!=0x73E3A4 && table!=0x73E444) return nullptr;
    void* object=At<void*>(wrapper,0x14);
    return object && At<std::uintptr_t>(object,0)==0x741878 ? object : nullptr;
}
void Policy(void* wrapper, Mode mode) {
    void* object=Internal(wrapper);
    const auto found=strings.find(object);
    if (found==strings.end()) return;
    StringState& state=found->second;
    ObserveScale(object,state);
    if (state.mode!=mode) {state.mode=mode;state.cached=false;}
    if (mode==Mode::Flow && At<float>(object,0x40)!=state.requested) {
        WriteScale(object,state,state.requested); Wrap(object);
    }
    if (mode!=Mode::Flow) Apply(object,false);
}
struct PanelState { std::string resource; std::map<void*,std::string> controls; };
std::map<void*,PanelState> panels;
struct PauseState {
    bool kept=false;
    int left=0,right=0,top=0,bottom=0,gap=2,underMenu=2;
    int reasonInset=0,pressInset=0;
    Rect lastPanel{},lastReason{},lastPress{},lastButton{};
    bool cached=false,pressShown=false;
    Key reasonKey{},pressKey{};
};
std::map<void*,PauseState> pauses;
int lastWidth=0,lastHeight=0;
void* Control(void* panel,const char* tag) {
    const auto found=panels.find(panel);
    if(found==panels.end())return nullptr;
    for(const auto& item:found->second.controls)if(item.second==tag)return item.first;
    return nullptr;
}
bool CurrentKey(void* object,Key& key) {
    const auto found=strings.find(object);
    if(found==strings.end())return false;
    ObserveScale(object,found->second);
    Metrics font;
    return Font(object,font) && MakeKey(object,found->second,font,key);
}

void Pause(void* panel, void* hud, int screenWidth, int screenHeight) {
    void* reason=Control(panel,"LBL_PAUSEREASON");
    void* press=Control(panel,"LBL_PRESS");
    void* button=Control(panel,"BTN_UNPAUSE");
    if(!reason || !press || !button)return;
    const char* const tags[]={"BTN_EQU","BTN_INV","BTN_CHAR","BTN_ABI","BTN_MSG","BTN_JOU","BTN_MAP","BTN_OPT"};
    int left=screenWidth,right=0,bottom=0;
    Rect rowFirst{},rowSecond{};
    for(const char* tag:tags) {
        void* c=Control(hud,tag);
        if(!c)return;
        const Rect r=At<Rect>(c,4);
        // The Xbox HUD parks this row. Its own pause adapter owns that layout.
        if(r.left<0 || r.top<0 || r.width<=0 || r.height<=0 || r.left+r.width>screenWidth)return;
        left=(std::min)(left,r.left);right=(std::max)(right,r.left+r.width);
        bottom=(std::max)(bottom,r.top+r.height);
        if(tag==tags[0])rowFirst=r; else if(tag==tags[1])rowSecond=r;
    }
    // Directly under the menu row, as far below it as its buttons stand apart (the
    // maintainer asked for it there, 2026-10-18; the game's own box sat about 150 px
    // lower at 1920x1080). Read from the live row, so any HUD layout or size keeps it.
    const int spacing=rowSecond.left-(rowFirst.left+rowFirst.width);
    const int underMenu=spacing>=0 && spacing<screenHeight/8?spacing:2;
    const Rect panelNow=At<Rect>(panel,4),rNow=At<Rect>(reason,4),pNow=At<Rect>(press,4);
    void* reasonText=Internal(static_cast<char*>(reason)+0xD0);
    void* pressText=Internal(static_cast<char*>(press)+0xD0);
    if(!reasonText || !pressText)return;
    PauseState& state=pauses[panel];
    const bool pressShown=(At<unsigned>(press,0x44)&2u)!=0;
    Key reasonKey,pressKey;
    if(state.cached && pressShown==state.pressShown &&
       left==state.lastPanel.left && right-left==state.lastPanel.width &&
       bottom+state.underMenu==state.lastPanel.top &&
       Same(panelNow,state.lastPanel) && Same(rNow,state.lastReason) &&
       Same(pNow,state.lastPress) && Same(At<Rect>(button,4),state.lastButton) &&
       CurrentKey(reasonText,reasonKey) && reasonKey==state.reasonKey &&
       (!pressShown || (CurrentKey(pressText,pressKey) && pressKey==state.pressKey)))return;
    if(!state.kept || (panelNow.width!=state.lastPanel.width && rNow.width!=state.lastReason.width)) {
        state.left=(std::max)(0,rNow.left);
        state.right=(std::max)(0,panelNow.width-rNow.left-rNow.width);
        state.top=(std::max)(0,rNow.top);
        // Label::SetExtent removes its border's client insets before giving
        // the text its bounds. NaturalHeight measures that inner text box.
        state.reasonInset=(std::max)(0,rNow.height-At<int>(reasonText,0x10));
        state.pressInset=(std::max)(0,pNow.height-At<int>(pressText,0x10));
        const bool shown=(At<unsigned>(press,0x44)&2u)!=0;
        const Rect& last=shown?pNow:rNow;
        state.bottom=(std::max)(0,panelNow.height-last.top-last.height);
        const int gap=pNow.top-rNow.top-rNow.height;
        state.gap=shown && gap>=0 && gap<screenHeight/4?gap:2; // native SetPauseReason gap
        state.kept=true;
    }
    state.underMenu=underMenu;
    const int width=right-left,contentWidth=width-state.left-state.right;
    if(contentWidth<1)return;
    KmrpTextFlowK1(static_cast<char*>(reason)+0xD0);
    KmrpTextFlowK1(static_cast<char*>(press)+0xD0);
    Extent(reason,{state.left,state.top,contentWidth,(std::max)(1,rNow.height)});
    Extent(press,{state.left,pNow.top,contentWidth,(std::max)(1,pNow.height)});
    const int reasonNatural=KmrpTextNaturalHeightK1(static_cast<char*>(reason)+0xD0);
    const bool shown=(At<unsigned>(press,0x44)&2u)!=0;
    const int pressNatural=shown?KmrpTextNaturalHeightK1(static_cast<char*>(press)+0xD0):0;
    if(reasonNatural<=0 || (shown && pressNatural<=0))return;
    const int reasonHeight=reasonNatural+state.reasonInset;
    const int pressHeight=shown?pressNatural+state.pressInset:0;
    const int top=bottom+state.underMenu;
    const int available=(std::max)(1,screenHeight-top);
    const int gap=shown?state.gap:0;
    int first=reasonHeight,second=pressHeight;
    const int content=(std::max)(1,available-state.top-state.bottom-gap);
    if(first+second>content) {
        first=(std::max)(1,static_cast<int>(double(content)*first/(first+second)));
        second=shown?(std::max)(1,content-first):0;
    }
    const Rect firstRect{state.left,state.top,contentWidth,first};
    const Rect secondRect{state.left,state.top+first+gap,contentWidth,shown?second:pNow.height};
    const int height=state.top+first+gap+second+state.bottom;
    Extent(panel,{left,top,width,height});
    Extent(reason,firstRect);
    if(shown)Extent(press,secondRect);
    Extent(button,{state.left,state.top,contentWidth,first+gap+second});
    if(first<reasonHeight)KmrpTextBoundedK1(static_cast<char*>(reason)+0xD0);
    if(shown && second<pressHeight)KmrpTextBoundedK1(static_cast<char*>(press)+0xD0);
    state.lastPanel=At<Rect>(panel,4);
    state.lastReason=At<Rect>(reason,4);
    state.lastPress=At<Rect>(press,4);
    state.lastButton=At<Rect>(button,4);
    state.pressShown=shown;
    state.cached=CurrentKey(reasonText,state.reasonKey) &&
        (!shown || CurrentKey(pressText,state.pressKey));
}
// The container panel (container.gui): its three buttons share the panel's width, and
// "Switch To Give Item" did not fit at a larger text size: drawn at 0.957 in a 601 px
// button at 100%, with the item names wrapped into 314 px (measured 2026-10-18). The
// panel widens by what its widest button text needs at the requested size, centred
// on its old place, and every control in it (title, list, buttons) widens with it, so
// the item names gain the room too. Measured from the game's own layout each time it
// lays the panel out, so it never accumulates; at most the screen's width.
struct Widened {
    bool known=false;
    Rect base{},applied{};
    std::vector<std::pair<void*,Rect>> controls;
};
std::map<void*,Widened> widened;
void Container(void* panel,int screenWidth) {
    Widened& s=widened[panel];
    const Rect now=At<Rect>(panel,4);
    if(!s.known || !Same(now,s.applied)) {
        void** const array=At<void**>(panel,0x20);
        const int count=At<int>(panel,0x24);
        if(!array || count<0 || count>256)return;
        s.base=now;s.controls.clear();
        for(int i=0;i<count;++i)if(array[i])s.controls.emplace_back(array[i],At<Rect>(array[i],4));
        s.known=true;s.applied=now;
    }
    int need=0;
    for(const char* tag:{"BTN_OK","BTN_GIVEITEMS","BTN_CANCEL"}) {
        void* const button=Control(panel,tag);
        if(!button)continue;
        void* const wrapper=static_cast<char*>(button)+0x154;
        Rect native{};
        for(const auto& c:s.controls)if(c.first==button)native=c.second;
        const double natural=KmrpTextNaturalWidthK1(wrapper);
        const int inset=At<Rect>(button,4).width-At<Rect>(wrapper,4).width;
        // Room around the text: one line's height, half on each side. Fitting the text
        // exactly left "Switch To Give Item" touching both ends of its button (the
        // panel grew 28 px at 100%; the maintainer: "too confined", 2026-10-18).
        const double margin=KmrpTextNaturalLineHeightK1(wrapper);
        if(native.width<=0 || !(natural>0) || natural>32767 || inset<0 || !(margin>=0) || margin>32767)continue;
        need=(std::max)(need,static_cast<int>(std::ceil(natural+margin))+inset-native.width);
    }
    int grow=(std::min)(need,(std::max)(0,screenWidth-s.base.width));
    grow+=grow&1;  // an even growth keeps the centre exact
    const Rect target{s.base.left-grow/2,s.base.top,s.base.width+grow,s.base.height};
    if(Same(target,now) && Same(target,s.applied))return;
    Extent(panel,target);
    for(const auto& c:s.controls) {Rect r=c.second;r.width+=grow;Extent(c.first,r);}
    s.applied=At<Rect>(panel,4);
}

// The conversation's lower panel (CSWGuiDialogCinematic, dialog.gui) inside the bottom
// black bar. The bars stay as they are; only the text's room inside the bottom one
// grows: down to the screen's bottom less the gap between the picture's lower edge and
// the panel's top, the same space below the text as above it (the maintainer's rule,
// 2026-10-18). Read in play at 3440x1440 at 100% text: the bar 1200..1440; the panel
// 1200 high at its top but only 100 tall while a line is spoken (KMRP's letterbox
// recipe gives it that old height, 0x006A7F71), so the second subtitle line was cut at
// 1300 although LBL_MESSAGE, 160 tall, held both; while replies are offered the panel
// is the bar's 240 but LB_REPLIES 192 (the recipe's bar less 48), so the third reply of
// 72 was cut. Panel, message and list each reach that limit, never past it and never
// shrunk: a longer subtitle is then fitted to its box (LBL_MESSAGE is a bounded text)
// and more replies scroll. The bar's top is the recipe's: height less (height + 3) / 6.
// The panel's own height is written in place, not through its SetExtent, which lays its
// children out again; the engine sets it again on every line, so this runs every frame.
void Dialogue(void* panel,int screenHeight) {
    if(At<std::uintptr_t>(panel,0)!=0x755800)return;
    Rect& box=At<Rect>(panel,4);
    const int barTop=screenHeight-(screenHeight+3)/6;
    if(box.top<barTop || box.top>=screenHeight || box.height<=0)return;
    const int limit=screenHeight-(box.top-barTop);
    if(box.top+box.height<limit)box.height=limit-box.top;
    for(const char* tag:{"LBL_MESSAGE","LB_REPLIES"}) {
        void* const control=Control(panel,tag);
        if(!control)continue;
        Rect r=At<Rect>(control,4);
        const int want=limit-(box.top+r.top);
        if(r.height>0 && want>r.height && want<=32767) {r.height=want;Extent(control,r);}
    }
}
} // namespace

void KmrpGrantedPopupFrameK1();  // K1GrantedPopup.cpp

extern "C" void __cdecl KmrpTextStringCreatedK1(void* object) {
    if(!object || At<std::uintptr_t>(object,0)!=0x741878)return;
    const float scale=At<float>(object,0x40);
    if(Scale(scale)) {
        StringState state;
        state.requested=state.applied=scale;
        strings[object]=state;
    }
}
extern "C" void __cdecl KmrpTextStringDestroyedK1(void* object) {strings.erase(object);}
// Every native wrap (persistent, from SetText or a resize; or GetIdealHeight's trial
// at a width) lays out and measures at the requested scale. The fit belongs to the
// draw only.
//
// The game sizes some boxes from the text, every frame: SetNameLabel (0x00685AF0, the
// target's name and health bar) and SetActionDescription (0x00685560) each SetText,
// ask GetIdealHeight and SetExtent the box to the answer. GetIdealPixelHeight
// (0x0045B7A0) answers from the string's line count and its scale at +0x40 without
// wrapping. Fitting inside SetText's wrap shrank the text to the previous frame's
// box, the game then sized the box to that, and the shrink held itself in place: the
// target name was drawn small from launch until a text size change reset every scale
// (measured 2026-10-18: both callers about once a frame, wraps ~1000 a second). With
// the request in place the game measures the real text and sizes its box to it, and
// the draw fits whatever box it ends with: cheaply, from the stored result, while
// the text, box and font are unchanged.
static void Restore(void* object) {
    if(measuring || !object)return;
    const auto found=strings.find(object);
    if(found==strings.end())return;
    StringState& state=found->second;
    ObserveScale(object,state);
    if(At<float>(object,0x40)!=state.requested) {
        WriteScale(object,state,state.requested);
        state.restored=true;
    }
}
// GetIdealPixelHeight's entry (0x0045B7A0). Asked with -1 once lines exist, it
// answers from the stored line count and the scale at +0x40 and does not wrap; a
// caller that measures without setting the text first would read the fit. Put the
// request back and lay it out once at that scale; the next draw re-applies the fit.
//
// The HUD's action description (CSWGuiMainInterface +0xA1D4, a label) is measured so
// too, at the size asked for. Until 2026-10-18 it alone was measured at the original
// text size (50%), so that a description wrapping onto a second line at 100% could
// not make the Xbox-style HUD's action box taller ("text should only become as big as
// the action bar allows it"); the text was then squeezed into the box, and the mouse
// and keyboard HUD's description did not grow with the text size at all (the
// maintainer, the same day). Now SetActionDescription sizes both HUDs' description,
// and its background, to the text at its size, and the Xbox-style HUD keeps its box
// as tall as the tallest of its actions' descriptions (K1XboxHud.cpp).
extern "C" void __cdecl KmrpTextIdealHeightK1(void* object) {
    if(measuring || !object)return;
    const float before=At<float>(object,0x40);
    Restore(object);
    if(At<float>(object,0x40)!=before)Wrap(object);
}
void CentreLetters(void* object, StringState& state);
extern "C" void __cdecl KmrpTextStringWrapK1(void* object,int* width) {
    // GetIdealHeight(width) temporarily swaps its line arrays; its trial and its
    // answer must not become this control's persistent state either way.
    (void)width;
    Restore(object);
    // CSWGuiText::SetExtent (0x00416280) places the string and then rebuilds it, which
    // comes here: its letters go where they are drawn now, not at its next draw, so a
    // patch that sets a caption's rectangle reads the place it will have (the
    // controller's glyph was placed from the old top and moved a frame later, "as if it
    // gets drawn twice once with a pixel too high up then normal", 2026-10-28).
    if(!measuring && object) {
        const auto found=strings.find(object);
        if(found!=strings.end())CentreLetters(object,found->second);
    }
}
// A text centred top to bottom in its box is drawn with its letters' middle on the box's
// middle, not its lines' (the maintainer, 2026-10-28, of every caption on its button's
// art: "on all screens please, every single one"). The letters are low in a line: in the
// game's menu font the capitals run from 29% to 88% of it, so a centred line put them
// about 3 px below a 39 px button's middle at 3440x1440. Where they stand is read from
// the font's own picture (K1CaptionInk.h); Draw (0x0045A850) places the lines from the
// string's top at +0x08 when the alignment at +0x46 has 0x10, so that top is moved up by
// the letters' distance below the line's middle, for this draw on: kept while the layout
// leaves it, worked out again when the layout writes another (CSWGuiText::SetExtent), and
// given back when the text stops being centred. Its height, and so the lines Draw
// shows, are not touched.
#ifndef KMRP_TEXT_LAYOUT_TEST
// A caption whose control carries no art of its own is drawn on the art behind it,
// which the game's screens draw as part of the panel's picture (the Map screen's whole
// background is lbl_map, stretched over the panel; its Party Selection and Return rows
// are bars in it). The art's bars were not drawn on the controls' middles: on the Map
// and Journal screens the bars stand 1 to 3 px above their buttons at 3440x1440 (in
// the HD art the Party Selection bar fills texture rows 1229 to 1256, the button the
// screen rows 1230 to 1269), so a caption centred on its button stood below its bar
// (the maintainer, 2026-10-28: "still not centered on the art"). Its letters now go on
// the bar's middle, found in the picture itself, so a mod's art is followed too.
//
// What is behind a control: the last control before it in the panel's list (drawn
// before it) whose rectangle holds its middle and that shows a stretched fill of its
// own, else the panel's picture (its border at +0x5C, the parameters 0x14 into it: the
// fill's name at +0x40, the fill style's low two bits at +0x1C, 2 stretched;
// CSWGuiBorderParams, the swkotor1-reconstruction project). A control has no art of
// its own when its border has no corner, edge or fill (+0x20, +0x30, +0x40). Only a
// stretched picture is read; tiled and centred ones are left.
//
// The bar: the picture's rows under the middle three fifths of the control, each
// row's light the mean of its pixels' brightest channel; from the row at the control's
// middle, up and down to the first row whose light differs from the next by more than
// kArtEdge (the bars are smooth inside and bounded by lines: in lbl_map's rows the
// light changes by 1 to 4 a row inside a bar and by 14 to 31 at its lines). A bar
// under half the control's height or over half again its height, or whose middle is
// outside the control, is no bar, and the caption keeps its box's middle.
constexpr int kArtEdge = 10;
constexpr int kArtTopBorder = 2;    // rows of the art's top border counted into a box
struct ArtPicture { std::string name; int width = 0, height = 0; std::vector<unsigned char> light; bool read = false; };
std::vector<ArtPicture> artPictures;      // the last few read, newest last
struct ArtPlace { std::string name; Rect behind{}, control{}; int middle = INT_MIN; bool read = false; };
std::map<void*, ArtPlace> artPlaces;      // by control

std::string ResRef(const char* at) {
    char name[17] = {};
    std::memcpy(name, at, 16);
    return name;
}
bool OwnArt(const char* params) {
    return !ResRef(params + 0x20).empty() || !ResRef(params + 0x30).empty() || !ResRef(params + 0x40).empty();
}
// A picture's light read from its uploaded texture `glName` into `p`.
bool ReadPicture(ArtPicture& p, unsigned glName) {
    int width = 0, height = 0;
    unsigned char* const pixels = K1CaptionInk::ReadUploaded(glName, &width, &height);
    if (!pixels) return false;
    p.width = width;
    p.height = height;
    p.light.resize(static_cast<std::size_t>(width) * height);
    for (std::size_t i = 0; i < p.light.size(); ++i) {
        const unsigned char* px = pixels + i * 4;
        p.light[i] = std::max(px[0], std::max(px[1], px[2]));
    }
    std::free(pixels);
    p.read = true;
    return true;
}
// A picture read once its texture is uploaded: now if it is, else as the game uploads it
// (KmrpTextureUploadedK1), which ArtCaptions finds on its next frame. Not read is not
// recorded as a failure.
const ArtPicture* Picture(const std::string& name) {
    for (const ArtPicture& p : artPictures) if (p.name == name) return p.read ? &p : nullptr;
    void* const texture = Fn<void*(__cdecl*)(const char*, int)>(0x00423A60)(name.c_str(), 0);   // AurTextureGetReference
    const unsigned glName = texture ? K1CaptionInk::UploadedName(texture) : 0;
    if (artPictures.size() >= 6) artPictures.erase(artPictures.begin());
    artPictures.push_back({name});
    if (!glName) return nullptr;              // waits for its upload
    return ReadPicture(artPictures.back(), glName) ? &artPictures.back() : nullptr;
}
// The screen row of the middle of the bar `at` is drawn on, in `picture` stretched over
// `behind`; INT_MIN when there is none. OpenGL's row 0 is v = 0, the picture's bottom
// as drawn (a quad's top takes v = 1).
int BarMiddle(const ArtPicture& p, const Rect& behind, const Rect& at) {
    if (behind.width <= 0 || behind.height <= 0 || at.height <= 0) return INT_MIN;
    const auto rowOf = [&](double y) {             // screen y to texture row, top to bottom
        return static_cast<int>(std::floor((1.0 - (y - behind.top) / behind.height) * p.height));
    };
    const auto screenOf = [&](int row) {           // a texture row's middle on screen
        return behind.top + (1.0 - (row + 0.5) / p.height) * behind.height;
    };
    int x0 = static_cast<int>((at.left + at.width * 0.2 - behind.left) * p.width / behind.width);
    int x1 = static_cast<int>((at.left + at.width * 0.8 - behind.left) * p.width / behind.width);
    x0 = std::max(0, x0);
    x1 = std::min(p.width, x1);
    if (x1 <= x0) return INT_MIN;
    const int step = std::max(1, (x1 - x0) / 64);
    const auto light = [&](int row) {
        if (row < 0 || row >= p.height) return -1000;
        int sum = 0, n = 0;
        for (int x = x0; x < x1; x += step, ++n) sum += p.light[static_cast<std::size_t>(row) * p.width + x];
        return n ? sum / n : -1000;
    };
    const int middle = rowOf(at.top + at.height / 2.0);
    // A row of a higher number is higher on screen: row + 1 is above.
    int above = middle, below = middle;
    const int reach = std::max(2, rowOf(at.top) - rowOf(at.top + at.height)) * 2;
    while (above - middle < reach && std::abs(light(above + 1) - light(above)) <= kArtEdge) ++above;
    while (middle - below < reach && std::abs(light(below - 1) - light(below)) <= kArtEdge) --below;
    // And out to a thin rim line beyond an edge, which is the bar's outline, to the rim's
    // brightest row: within an eighth of the control's rows (at least three), the first
    // row the light rises to and then falls from by twice kArtEdge. A wide bright band
    // (the Map's strip between its two rows) does not fall within that reach and ends the
    // bar where it starts. Without the rim the Map's Party Selection bar was found 3 px low
    // (its outline at texture rows 1227 to 1229). The first peak, not the brightest row in
    // reach: on the 84 px bottom row the reach holds the screen's frame line above the
    // tray, brighter than the tray's own top rim, so that rim was missed, the bottom one
    // taken, and the captions stood about 2 px low on every tab (the maintainer,
    // 2026-10-28, of Inventory's Use Item: "it should be centered"). From rim to rim
    // through their middles, both sides alike.
    const int rimRows = std::max(3, (rowOf(at.top) - rowOf(at.top + at.height)) / 8);
    const auto rim = [&](int edge, int direction) {
        int peak = 1;
        while (peak < rimRows && light(edge + direction * (peak + 1)) >= light(edge + direction * peak)) ++peak;
        const int peakLight = light(edge + direction * peak);
        for (int k = peak + 1; k <= rimRows; ++k)
            if (light(edge + direction * k) < peakLight - 2 * kArtEdge) return edge + direction * peak;
        return edge;
    };
    above = rim(above, 1);
    below = rim(below, -1);
    // And two more of the art's rows above, the top border's own (the maintainer,
    // 2026-10-28: "make it 1 pixel more up? maybe include 2 more pixels from the top
    // border of the art"): the box's middle a row higher.
    above += kArtTopBorder;
    const double top = screenOf(above), bottom = screenOf(below);
    const double span = bottom - top, centre = (top + bottom) / 2.0;
    if (span < at.height * 0.5 || span > at.height * 1.5 || centre < at.top || centre > at.top + at.height)
        return INT_MIN;
    return static_cast<int>(std::lround(centre));
}
void ArtCaptions(void* panel) {
    void** const array = At<void**>(panel, 0x20);
    const int count = At<int>(panel, 0x24);
    if (!array || count <= 0 || count > 4096) return;
    char* const panelBorder = At<char*>(panel, 0x5C);
    for (int i = 0; i < count; ++i) {
        void* const control = array[i];
        if (!control) continue;
        const std::uintptr_t table = At<std::uintptr_t>(control, 0);
        unsigned params = 0, text = 0;
        if (table == 0x0073E658 || table == 0x0073EB88) { params = 0x80; text = 0x154; }   // button, toggle
        else if (table == 0x0073E5B8) { params = 0x70; text = 0xD0; }                      // label
        else continue;
        void* const string = At<void*>(control, text + 0x14);
        const auto found = string ? strings.find(string) : strings.end();
        if (found == strings.end()) continue;
        int& artMiddle = found->second.artMiddle;
        artMiddle = INT_MIN;
        if (OwnArt(static_cast<char*>(control) + params)) continue;
        const Rect at = At<Rect>(control, 4);
        // What it is drawn on.
        std::string name;
        Rect behind{};
        for (int j = i - 1; j >= 0 && name.empty(); --j) {
            void* const under = array[j];
            if (!under || At<std::uintptr_t>(under, 0) != 0x0073E5B8) continue;
            const Rect r = At<Rect>(under, 4);
            const int mx = at.left + at.width / 2, my = at.top + at.height / 2;
            if (mx < r.left || mx >= r.left + r.width || my < r.top || my >= r.top + r.height) continue;
            const char* const p = static_cast<char*>(under) + 0x70;
            if ((At<unsigned>(const_cast<char*>(p), 0x1C) & 3u) != 2u || ResRef(p + 0x40).empty()) continue;
            name = ResRef(p + 0x40);
            behind = r;
        }
        if (name.empty() && panelBorder) {
            char* const p = panelBorder + 0x14;
            if ((At<unsigned>(p, 0x1C) & 3u) == 2u) {
                name = ResRef(p + 0x40);
                behind = At<Rect>(panel, 4);
            }
        }
        if (name.empty()) continue;
        ArtPlace& place = artPlaces[control];
        if (place.name != name || !Same(place.behind, behind) || !Same(place.control, at) || !place.read) {
            place.name = name;
            place.behind = behind;
            place.control = at;
            const ArtPicture* const picture = Picture(name);
            place.middle = picture ? BarMiddle(*picture, behind, at) : INT_MIN;
            place.read = picture != nullptr;     // else asked again once it is uploaded
        }
        artMiddle = place.middle;
        // Moved now, before the screen is drawn or a glyph is placed beside it.
        CentreLetters(string, found->second);
    }
}

#endif

// CAurTextureBasic::BuildAndStoreTexture (0x004216A0), just after glImage (0x00420970)
// has uploaded the picture (hook at 0x004216F1, kotor1-native-runtime.hooks.toml): a
// font's letters are read here, once each time it is loaded (its information, +0x38, has
// characters), and a picture a caption's art waits for (Picture). The texture's own name
// is at +0x78, its OpenGL name at +0x58. The maintainer, 2026-10-28, of reading a font
// again a quarter second after it failed: "Instead of retry shouldn't hook the correct
// spot in the chain once?"
#if !defined(KMRP_TEXT_LAYOUT_TEST) && defined(KMRP_NATIVE_RUNTIME)
void CorrectHardwareMipmapsK1();   // K1NativeJoystick.cpp: once, after the first upload
#endif
extern "C" void __cdecl KmrpTextureUploadedK1(void* texture) {
#ifndef KMRP_TEXT_LAYOUT_TEST
#ifdef KMRP_NATIVE_RUNTIME
    CorrectHardwareMipmapsK1();
#endif
    if (!texture) return;
    const unsigned glName = At<unsigned>(texture, 0x58);
    if (!glName) return;
    const char* const info = At<const char*>(texture, 0x38);
    if (info && At<int>(const_cast<char*>(info), 0) > 0 && At<const float*>(const_cast<char*>(info), 0x18))
        K1CaptionInk::FontUploaded(texture, glName, info);
    char name[33] = {};
    std::memcpy(name, static_cast<char*>(texture) + 0x78, 32);
    for (ArtPicture& p : artPictures)
        if (!p.read && !_stricmp(p.name.c_str(), name)) ReadPicture(p, glName);
#else
    (void)texture;
#endif
}

void CentreLetters(void* object, StringState& state) {
    int& top = At<int>(object, 0x08);
    const int from = state.inkMoved && top == state.inkTo ? state.inkFrom : top;
    const auto giveBack = [&] {
        if (state.inkMoved && top == state.inkTo) top = state.inkFrom;
        state.inkMoved = false;
    };
    if ((At<unsigned char>(object, 0x46) & 0x38u) != 0x10u) return giveBack();
    // On its art's bar instead of its box's middle, where it has one (ArtCaptions).
    const int height = At<int>(object, 0x10);
    const int target = state.artMiddle != INT_MIN ? state.artMiddle - height / 2 : from;
    Metrics font;
    const char* text = At<const char*>(object, 0x14);
    if (!text || !Font(object, font)) return giveBack();
    std::uint64_t hash = 1469598103934665603ull;
    for (int i = 0; i < 4096 && text[i]; ++i) hash = (hash ^ static_cast<unsigned char>(text[i])) * 1099511628211ull;
    const float scale = At<float>(object, 0x40);
    if (font.info != state.inkInfo || text != state.inkText || hash != state.inkHash || scale != state.inkScale ||
            !state.inkRead) {
        state.inkInfo = font.info;
        state.inkText = text;
        state.inkHash = hash;
        state.inkScale = scale;
        state.inkShift = 0;
        const K1CaptionInk::Font* letters = K1CaptionInk::FontFor(font.font, static_cast<const char*>(font.info));
        state.inkRead = letters != nullptr;
        double middle = 0.5;
        if (letters && Scale(scale) && K1CaptionInk::Middle(*letters, text, &middle))
            state.inkShift = K1CaptionInk::Shift(middle, font.height * scale);
    }
    if (state.inkShift == 0 && target == from) return giveBack();
    top = target - state.inkShift;
    state.inkFrom = from;
    state.inkTo = top;
    state.inkMoved = true;
}

extern "C" void __cdecl KmrpTextStringDrawK1(void* object) {
    Apply(object,false);
    const auto found=strings.find(object);
    // An outer native wrap runs after our entry callback and rewrites widths.
    // Reinstall only this instance's verified final widths immediately before
    // drawing, including cache hits, without another wrap or shared-font write.
    if(found!=strings.end())DrawWidths(object,found->second);
    if(found!=strings.end())CentreLetters(object,found->second);
}
extern "C" void __cdecl KmrpTextListDrawK1(void* list) {KmrpTextRowsK1(list);}

void KmrpTextFlowK1(void* wrapper) {Policy(wrapper,Mode::Flow);}
void KmrpTextBoundedK1(void* wrapper) {Policy(wrapper,Mode::Bounded);}
void KmrpTextEditableK1(void* wrapper) {Policy(wrapper,Mode::Editable);}
unsigned KmrpTextLayoutGenerationK1() {return generation;}
int KmrpTextNaturalHeightK1(void* wrapper) {
    void* object=Internal(wrapper);
    const auto found=strings.find(object);
    if(found==strings.end())return 0;
    Policy(wrapper,Mode::Flow);
    StringState& state=found->second;
    Metrics font;Key key;
    if(!Font(object,font) || !MakeKey(object,state,font,key))return 0;
    if(!state.cached || !(state.key==key)) {
        state.measured=Measure(object,state.requested,font);
        state.applied=state.requested;
        state.key=key;state.cached=true;
    }
    const double height=state.measured.height;
    return state.measured.valid && height>0 && height<=32767?static_cast<int>(std::ceil(height)):0;
}
double KmrpTextNaturalWidthK1(void* wrapper) {
    void* object=Internal(wrapper);
    const auto found=strings.find(object);
    if(found==strings.end())return 0;
    ObserveScale(object,found->second);
    Metrics font;
    if(!Font(object,font))return 0;
    const char* text=At<const char*>(object,0x14);
    if(!text)return 0;
    const double scale=found->second.requested;
    double pen=0,right=0,widest=0;
    for(unsigned i=0;i<262144;++i) {
        const unsigned char value=static_cast<unsigned char>(text[i]);
        if(!value || value=='\n') {
            widest=(std::max)(widest,right);
            if(!value)return std::isfinite(widest)?widest:0;
            pen=right=0;continue;
        }
        const unsigned glyph=static_cast<unsigned>(value)*3;
        const double width=(font.last[glyph]-font.first[glyph])*font.textureWidth*100.0*scale;
        right=(std::max)(right,pen+width);
        pen+=width+font.spacing*100.0*scale;
    }
    return 0;
}
double KmrpTextNaturalLineHeightK1(void* wrapper) {
    void* object=Internal(wrapper);
    const auto found=strings.find(object);
    if(found==strings.end())return 0;
    ObserveScale(object,found->second);
    Metrics font;
    return Font(object,font)?font.height*found->second.requested:0;
}
void KmrpTextLayoutFontsChangedK1() {
    if(++generation==0)++generation;
    for(auto& item:strings) {
        if(At<std::uintptr_t>(item.first,0)!=0x741878)continue;
        ObserveScale(item.first,item.second);
        WriteScale(item.first,item.second,item.second.requested);
        item.second.cached=false;
    }
}
void KmrpTextLayoutTrackPanelK1(void* panel,const char* resource) {
    if(!panel || !resource)return;
    panels[panel]=PanelState{resource,{}};
    pauses.erase(panel);
}
void KmrpTextLayoutTrackControlK1(void* panel,void* control,const char* tag) {
    if(!panel || !control || !tag)return;
    const auto found=panels.find(panel);
    if(found!=panels.end())found->second.controls[control]=tag;
}
void KmrpTextLayoutForgetControlK1(void* control) {
    KmrpTextRowsForgetK1(control);
    for(auto& item:panels)item.second.controls.erase(control);
}
void KmrpTextLayoutForgetPanelK1(void* panel) {
    const auto found=panels.find(panel);
    if(found!=panels.end()) {
        for(const auto& item:found->second.controls)KmrpTextRowsForgetK1(item.first);
        panels.erase(found);
    }
    pauses.erase(panel);
    widened.erase(panel);
}
void KmrpTextLayoutFrameK1(void* manager) {
    if(!manager)return;
    const int width=At<short>(manager,0x6C),height=At<short>(manager,0x6E);
    if(width<=0 || height<=0)return;
    if(width!=lastWidth || height!=lastHeight) {
        // A font object may keep its address while its metrics change with
        // resolution. Rows and cached strings must remeasure that same object.
        KmrpTextLayoutFontsChangedK1();
        pauses.clear();lastWidth=width;lastHeight=height;
    }
    KmrpTextRowsViewportK1(height);
    void* hud=nullptr;
    for(auto& item:panels) {
        if(At<void*>(item.first,0x18)!=manager)continue;
        if(At<std::uintptr_t>(item.first,0)==0x753F50)hud=item.first;
        for(const auto& c:item.second.controls) {
            const auto table=At<std::uintptr_t>(c.first,0);
            if(table==0x73E840)KmrpTextRowsK1(c.first);
            else if(table==0x73EAC8 || table==0x7575B0)
                KmrpTextEditableK1(static_cast<char*>(c.first)+0xE0);
        }
    }
    if(hud)for(auto& item:panels) {
        if(item.second.resource=="pause" && At<void*>(item.first,0x18)==manager)
            Pause(item.first,hud,width,height);
    }
#ifndef KMRP_TEXT_LAYOUT_TEST
    // Captions on the art behind them (ArtCaptions); before the draws that use it.
    for(auto& item:panels)
        if(At<void*>(item.first,0x18)==manager)ArtCaptions(item.first);
#endif
    for(auto& item:panels) {
        if(At<void*>(item.first,0x18)!=manager)continue;
        if(item.second.resource=="container")Container(item.first,width);
        else if(item.second.resource=="dialog")Dialogue(item.first,height);
    }
    KmrpGrantedPopupFrameK1();
}
