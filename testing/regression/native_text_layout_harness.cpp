// Production service exercised against native ABI mocks; not a game playtest.
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <map>
#include <vector>
#ifndef KMRP_TEXT_LAYOUT_TEST
#define KMRP_TEXT_LAYOUT_TEST
#endif
#include "../../src/controller-native/K1TextLayout.cpp"
#ifndef KMRP_TEXT_LAYOUT_ROWS_TEST
void KmrpTextRowsK1(void*) {}
void KmrpTextRowsForgetK1(void*) {}
void KmrpTextRowsViewportK1(int) {}
#endif
void KmrpGrantedPopupFrameK1() {}  // K1GrantedPopup.cpp: the popup is not part of these mocks
int hudTextSize=50;  // K1TextOptions.cpp's size for a font; 50 is the original size
int KmrpTextSizeForFontK1(const char*) {return hudTextSize;}
namespace Mock {
struct Bytes {
    alignas(8) unsigned char data[1024]{};
    operator void*() {return data;}
};
struct Lines {std::vector<int> lengths,widths;};
std::map<void*,Lines> lines;
std::uintptr_t fontTable[20]{},controlTable[4]{};
Bytes font,info;
float starts[768]{},ends[768]{};
int wrapCalls=0,extentCalls=0;
void* __fastcall FontInfo(void*,void*) {return info;}
void __fastcall SetExtent(void* control,void*,const Rect* r) {
    ++extentCalls;At<Rect>(control,4)=*r;
    void* object=Internal(static_cast<char*>(control)+0xD0);
    if(object) {At<int>(object,0x0C)=r->width;At<int>(object,0x10)=r->height;}
}
void __fastcall NativeWrap(void* object,void*,int) {
    ++wrapCalls;
    auto& result=lines[object];result.lengths.clear();result.widths.clear();
    const char* cursor=At<const char*>(object,0x14);
    const double glyph=10.0*At<float>(object,0x40);
    const int width=At<int>(object,0x0C);
    while(cursor && *cursor) {
        int length=0,lastSpace=-1;
        while(cursor[length] && cursor[length]!='\n' && (length+1)*glyph<=width) {
            if(cursor[length]==' ')lastSpace=length;
            ++length;
        }
        if(cursor[length] && cursor[length]!='\n' && cursor[length]!=' ') {
            if(lastSpace<0) {result.lengths.clear();result.widths.clear();break;}
            length=lastSpace;
        }
        if(length==0) {result.lengths.clear();result.widths.clear();break;}
        result.lengths.push_back(length);
        result.widths.push_back(static_cast<int>(length*glyph));
        cursor+=length;
        if(*cursor==' ' || *cursor=='\n')++cursor;
    }
    At<int*>(object,0x28)=result.widths.data();At<int>(object,0x2C)=static_cast<int>(result.widths.size());
    At<int*>(object,0x34)=result.lengths.data();At<int>(object,0x38)=static_cast<int>(result.lengths.size());
}
void Init() {
    fontTable[0x38/4]=1;controlTable[1]=2;
    At<std::uintptr_t>(font,0)=reinterpret_cast<std::uintptr_t>(fontTable);
    for(int i=0;i<256;++i)ends[i*3]=0.1f;
    At<float>(info,4)=0.4704f;At<float>(info,0x0C)=1;
    At<const float*>(info,0x18)=starts;At<const float*>(info,0x24)=ends;
}
struct Text {
    Bytes object,wrapper;
    char content[4096]{};
    Text(const char* text,int width,int height,float scale=1) {
        At<std::uintptr_t>(object,0)=0x741878;
        At<int>(object,0x0C)=width;At<int>(object,0x10)=height;
        At<const char*>(object,0x14)=content;At<void*>(object,0x18)=font;
        At<float>(object,0x40)=scale;
        At<std::uintptr_t>(wrapper,0)=0x73E3A4;At<void*>(wrapper,0x14)=object;
        Set(text);KmrpTextStringCreatedK1(object);
    }
    ~Text(){KmrpTextStringDestroyedK1(object);lines.erase(object);}
    void Set(const char* s){assert(std::strlen(s)<sizeof(content));std::memcpy(content,s,std::strlen(s)+1);}
    float Size(){return At<float>(object,0x40);}
    void Attach(Bytes& control){std::memcpy(control.data+0xD0,wrapper.data,0x18);}
};
void Control(Bytes& c,Rect r) {At<std::uintptr_t>(c,0)=reinterpret_cast<std::uintptr_t>(controlTable);At<Rect>(c,4)=r;}
}
void* KmrpTextLayoutTestAddress(std::uintptr_t address) {
    if(address==0x753F50)return Mock::controlTable;
    return reinterpret_cast<void*>(address);
}
void* KmrpTextLayoutTestFunction(std::uintptr_t address) {
    if(address==1)return reinterpret_cast<void*>(&Mock::FontInfo);
    if(address==2)return reinterpret_cast<void*>(&Mock::SetExtent);
    if(address==0x45A2F0)return reinterpret_cast<void*>(&Mock::NativeWrap);
    assert(false);return nullptr;
}
#ifndef KMRP_TEXT_LAYOUT_ROWS_TEST
int main() {
    Mock::Init();
    {
        Mock::Text t("Title",400,47);
        KmrpTextStringDrawK1(t.object);
        const float fitted=t.Size();assert(fitted<1 && fitted>0.99f);
        assert(KmrpTextNaturalLineHeightK1(t.wrapper)>47);
        const int count=Mock::wrapCalls;
        for(int i=0;i<100;++i)KmrpTextStringDrawK1(t.object);
        assert(t.Size()==fitted && Mock::wrapCalls==count);
        At<int>(t.object,0x10)=60;KmrpTextStringDrawK1(t.object);assert(t.Size()==1);
        At<int>(t.object,0x10)=47;KmrpTextStringDrawK1(t.object);assert(t.Size()==fitted);
        At<float>(Mock::info,4)=0.40f;
        KmrpTextStringDrawK1(t.object);assert(t.Size()==1);
        At<float>(Mock::info,4)=0.4704f;
        KmrpTextLayoutFontsChangedK1();assert(t.Size()==1);
        KmrpTextStringDrawK1(t.object);assert(t.Size()==fitted);
        At<float>(t.object,0x40)=0.5f;KmrpTextStringDrawK1(t.object);assert(t.Size()==0.5f);
        At<float>(t.object,0x40)=1.25f;KmrpTextStringDrawK1(t.object);
        At<int>(t.object,0x10)=100;KmrpTextStringDrawK1(t.object);assert(t.Size()==1.25f);
    }
    {
        Mock::Text t("A",70,50);
        KmrpTextStringDrawK1(t.object);assert(t.Size()==1);
        t.Set("LongWord");KmrpTextStringDrawK1(t.object);assert(t.Size()<0.88f);
        t.Set("A");KmrpTextStringDrawK1(t.object);assert(t.Size()==1);
        At<int>(t.object,0x10)=20;
        int explicitWidth=200;const int calls=Mock::wrapCalls;
        KmrpTextStringWrapK1(t.object,&explicitWidth);assert(t.Size()==1 && Mock::wrapCalls==calls);
        // A native persistent wrap (SetText, resize) lays out at the request; the
        // fit belongs to the draw, which then fits the box (see the block below).
        int persistentWidth=-1;KmrpTextStringWrapK1(t.object,&persistentWidth);assert(t.Size()==1);
        KmrpTextStringDrawK1(t.object);assert(t.Size()<0.43f);
        KmrpTextStringWrapK1(t.object,&persistentWidth);assert(t.Size()==1);
        {   // Re-applied from the stored fit: one wrap, no new search.
            const int before=Mock::wrapCalls;KmrpTextStringDrawK1(t.object);
            assert(t.Size()<0.43f && Mock::wrapCalls==before+1);
        }
        {   // A native ideal-height query without SetText first: the request, laid out
            // once at that scale; then the draw re-applies the fit.
            const int before=Mock::wrapCalls;KmrpTextIdealHeightK1(t.object);
            assert(t.Size()==1 && Mock::wrapCalls==before+1);
            KmrpTextIdealHeightK1(t.object);assert(Mock::wrapCalls==before+1);  // nothing to restore
            KmrpTextStringDrawK1(t.object);assert(t.Size()<0.43f);
        }
        // The native ideal-height trial (GetIdealHeight(width)) measures the size the
        // player chose, not a fit left from the box's earlier size: otherwise a box the
        // game sizes from that answer stays at the fitted height (the target name drawn
        // small after launch). No wrap of ours; the next draw fits the box it then has.
        {
            const int before=Mock::wrapCalls;int trialWidth=200;
            KmrpTextStringWrapK1(t.object,&trialWidth);assert(t.Size()==1 && Mock::wrapCalls==before);
            KmrpTextStringDrawK1(t.object);assert(t.Size()<0.43f);
            At<int>(t.object,0x10)=100;KmrpTextStringWrapK1(t.object,&trialWidth);
            KmrpTextStringDrawK1(t.object);assert(t.Size()==1);
        }
        KmrpTextStringDestroyedK1(t.object);
        At<float>(t.object,0x40)=0.75f;KmrpTextStringCreatedK1(t.object);
        At<int>(t.object,0x10)=100;KmrpTextStringDrawK1(t.object);assert(t.Size()==0.75f);
    }
    {
        Mock::Text t("Alpha Beta Gamma Delta",90,1);
        KmrpTextFlowK1(t.wrapper);
        const int height=KmrpTextNaturalHeightK1(t.wrapper);
        assert(t.Size()==1 && At<int>(t.object,0x38)==4);
        assert(height==static_cast<int>(std::ceil(4.0*At<float>(Mock::info,4)*100)));
        assert(height>At<int>(t.object,0x10));
        KmrpTextStringDrawK1(t.object);assert(t.Size()==1);
        At<int>(t.object,0x0C)=300;assert(KmrpTextNaturalHeightK1(t.wrapper)==48);
    }
    {
        Mock::Text t("A really long saved game name_",20,47);
        KmrpTextEditableK1(t.wrapper);const float scale=t.Size();assert(scale>0.99f && scale<1);
        t.Set("An even longer saved game name with its caret_");
        KmrpTextStringDrawK1(t.object);assert(t.Size()==scale);
        At<int>(t.object,0x0C)=1000;KmrpTextStringDrawK1(t.object);assert(t.Size()==scale);
        At<int>(t.object,0x10)=100;KmrpTextStringDrawK1(t.object);assert(t.Size()==1);
    }
    {
        const float original=Mock::ends['A'*3];
        Mock::ends['A'*3]=0.1015f; // 10.15 px, native mock's cached advance is 10
        Mock::Text t("AAAAAAAAAA",102,100);
        At<unsigned char>(t.object,0x46)=0x12;
        KmrpTextStringDrawK1(t.object);assert(t.Size()==1);
        const double drawn=10.0*Mock::ends['A'*3]*100.0;
        int* widths=At<int*>(t.object,0x28);
        assert(widths[0]==static_cast<int>(std::ceil(drawn)));
        const double centered=(102-widths[0])*0.5+drawn;
        assert(centered<=102);
        // The original width100 would put this centered line at102.5 pixels.
        assert((102-100)*0.5+drawn>102);
        int persistent=-1;
        KmrpTextStringWrapK1(t.object,&persistent);
        Mock::NativeWrap(t.object,nullptr,-1); // native body runs after entry hook
        assert(At<int*>(t.object,0x28)[0]==100);
        const int calls=Mock::wrapCalls;
        KmrpTextStringDrawK1(t.object);
        assert(Mock::wrapCalls==calls); // cache hit still repairs overwritten widths
        widths=At<int*>(t.object,0x28);
        assert(widths[0]==static_cast<int>(std::ceil(drawn)));
        At<unsigned char>(t.object,0x46)=0x24;
        KmrpTextStringDrawK1(t.object);
        assert(102-At<int*>(t.object,0x28)[0]+drawn<=102);
        assert(Mock::ends['A'*3]==0.1015f); // no shared font changes while fitting
        // The signed native byte count requests an additional hyphen glyph.
        Mock::Text hyphen("A",100,100);
        Mock::NativeWrap(hyphen.object,nullptr,-1);
        At<int*>(hyphen.object,0x34)[0]=-1;
        At<int*>(hyphen.object,0x28)[0]=19;
        Metrics font;assert(Font(hyphen.object,font));
        std::vector<int> corrected,lengths;
        const auto measured=WrappedMeasurement(hyphen.object,1,font,&corrected,&lengths);
        assert(measured.valid && corrected.size()==1 && corrected[0]==21);
        assert(lengths[0]==-1 && measured.width>20);
        Mock::ends['A'*3]=original;
    }
    {
        const float originalHeight=At<float>(Mock::info,4);
        const float originalLeading=At<float>(Mock::info,0x14);
        At<float>(Mock::info,4)=0.1f;At<float>(Mock::info,0x14)=0.02f;
        Mock::Text t("A\nA",100,22);
        At<unsigned char>(t.object,0x46)=0x09;
        KmrpTextStringDrawK1(t.object);assert(t.Size()>0.999f);
        const float topScale=t.Size();
        // Changing alignment alone must invalidate the otherwise identical key.
        At<unsigned char>(t.object,0x46)=0x11;
        KmrpTextStringDrawK1(t.object);assert(t.Size()<0.917f && t.Size()>0.916f);
        const double line=At<float>(Mock::info,4)*100.0*t.Size();
        const double leading=At<float>(Mock::info,0x14)*100.0*t.Size();
        const double start=(22-2*line)*0.5;
        assert(start>=0 && start+2*line+leading<=22);
        At<unsigned char>(t.object,0x46)=0x09;
        KmrpTextStringDrawK1(t.object);assert(t.Size()==topScale);
        assert(At<float>(Mock::info,4)==0.1f && At<float>(Mock::info,0x14)==0.02f);
        At<float>(Mock::info,4)=originalHeight;At<float>(Mock::info,0x14)=originalLeading;
    }
    {
        Mock::Text reason("Combat paused",280,60),press("Press SPACE to resume",280,30);
        // The HUD is a CSWGuiMainInterface: large enough for its action description
        // label at +0xA1D4, which the frame reads (KmrpTextIdealHeightK1).
        struct Hud { alignas(8) unsigned char data[0xA400]{}; operator void*() {return data;} };
        static Hud hud;
        Mock::Bytes panel,manager,r,p,b,menu[8];
        Mock::Control(panel,{100,80,300,110});At<Rect>(hud,4)={0,0,1920,1080};
        Mock::Control(r,{10,8,280,60});Mock::Control(p,{10,70,280,30});Mock::Control(b,{10,8,280,92});
        reason.Attach(r);press.Attach(p);At<unsigned>(p,0x44)=2;
        At<void*>(panel,0x18)=manager;At<void*>(hud,0x18)=manager;
        At<std::uintptr_t>(hud,0)=0x753F50;
        At<short>(manager,0x6C)=1920;At<short>(manager,0x6E)=1080;
        KmrpTextLayoutTrackPanelK1(panel,"pause");KmrpTextLayoutTrackPanelK1(hud,"maininterface");
        KmrpTextLayoutTrackControlK1(panel,r,"LBL_PAUSEREASON");
        KmrpTextLayoutTrackControlK1(panel,p,"LBL_PRESS");KmrpTextLayoutTrackControlK1(panel,b,"BTN_UNPAUSE");
        const char* tags[]={"BTN_EQU","BTN_INV","BTN_CHAR","BTN_ABI","BTN_MSG","BTN_JOU","BTN_MAP","BTN_OPT"};
        for(int i=0;i<8;++i) {Mock::Control(menu[i],{100+i*69,10,64,64});KmrpTextLayoutTrackControlK1(hud,menu[i],tags[i]);}
        KmrpTextLayoutFrameK1(manager);
        Rect panelRect=At<Rect>(panel,4),reasonRect=At<Rect>(r,4),pressRect=At<Rect>(p,4),buttonRect=At<Rect>(b,4);
        assert(panelRect.left==100 && panelRect.width==547);
        // Directly under the menu row (bottom 74), as far below it as the buttons
        // stand apart (5), not at the game's own distance (the panel started at 80).
        assert(panelRect.top==79);
        assert(reasonRect.height>=48 && pressRect.height>=48);
        assert(panelRect.height>=pressRect.top+pressRect.height);
        assert(buttonRect.height>=pressRect.top+pressRect.height-buttonRect.top);
        assert(reason.Size()==1 && press.Size()==1);
        const int calls=Mock::extentCalls;
        for(int i=0;i<100;++i)KmrpTextLayoutFrameK1(manager);
        assert(Same(At<Rect>(panel,4),panelRect) && Mock::extentCalls==calls);
        At<unsigned>(p,0x44)=0;KmrpTextLayoutFrameK1(manager);
        assert(At<Rect>(panel,4).height<panelRect.height);
        assert(At<Rect>(b,4).height==At<Rect>(r,4).height);
        At<unsigned>(p,0x44)=2;KmrpTextLayoutFrameK1(manager);
        assert(Same(At<Rect>(panel,4),panelRect));
        At<Rect>(menu[0],4).left=-1000;
        Mock::Control(panel,{10,10,200,100});KmrpTextLayoutFrameK1(manager);
        assert(Same(At<Rect>(panel,4),Rect{10,10,200,100}));
        // The HUD's action description is measured at the size asked for, as any
        // text is (until 2026-10-18 it alone was asked at the original 50% size, so it
        // did not grow with the text size): its height is asked at the requested scale
        // at 100% and at 50%.
        {
            char* const label=static_cast<char*>(static_cast<void*>(hud))+0xA1D4;
            Mock::Text description("Adrenal Stamina (Self)",354,64);
            std::memcpy(label+0xD0,description.wrapper.data,0x18);
            std::memcpy(label+0xD0+0x24,"dialogfont10x10b",17);
            hudTextSize=100;KmrpTextLayoutFrameK1(manager);
            KmrpTextIdealHeightK1(description.object);
            assert(description.Size()==1.0f);
            hudTextSize=50;KmrpTextLayoutFrameK1(manager);
            KmrpTextIdealHeightK1(description.object);
            assert(description.Size()==1.0f);
            std::memset(label+0xD0,0,0x40);KmrpTextLayoutFrameK1(manager);
        }
        KmrpTextLayoutForgetPanelK1(panel);KmrpTextLayoutForgetPanelK1(hud);
        assert(panels.empty() && pauses.empty());
    }
    assert(strings.empty());
    std::cout<<"PASS: production text fitting lifecycle, caching, native wrap, flow/edit policies and PC pause layout.\n";
}



#endif
