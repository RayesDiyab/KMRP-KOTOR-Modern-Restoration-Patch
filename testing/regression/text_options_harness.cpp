// Production UI code against native-ABI mocks. This is not a game playtest.
#include <windows.h>
#include <cassert>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <map>
#include <set>
#include <string>
#include <vector>
#include <array>
#define KMRP_TEXT_OPTIONS_TEST
#include "../../src/controller-native/K1TextOptions.cpp"

namespace Mock {
std::map<void*,std::map<std::string,void*>> controls;
std::set<void*> active;
std::map<void*,std::string> captions;
std::map<void*,unsigned> sizes;
void* source=nullptr;
int resets=0,loads=0,images=0,reflows=0,applies=0,builds=0;
std::vector<void*> refresh;
bool fail=false;
bool held=false;
std::map<unsigned,void*> functions;
std::map<std::uintptr_t,std::array<unsigned char,65536>> pages;
const char* tags[]={"LBL_TITLE","SLI_GAMMA","LBL_GAMMA","LB_DESC","BTN_DEFAULT","BTN_BACK","BTN_RESOLUTION","BTN_ADVANCED","CB_SHADOWS"};
const int ids[]={0,1,2,3,4,5,6,13,9};

void* __fastcall DummyDtor(void* self,void*,unsigned) {
    captions.erase(static_cast<char*>(self)+0xE8);
    captions.erase(static_cast<char*>(self)+0x16C);
    assert(sizes.erase(self));std::free(self);return self;
}
void __fastcall SetRect(void* self,void*,const Rect* r){At<Rect>(self,4)=*r;}
void* Ctor(void* self,std::uintptr_t v) {
    At<std::uintptr_t>(self,0)=v;At<unsigned>(self,0x44)=0x0A;return self;
}
void* __fastcall ButtonCtor(void* self,void*){return Ctor(self,ButtonTable);}
void* __fastcall LabelCtor(void* self,void*){return Ctor(self,0x73E5B8);}
void* __fastcall ChoiceCtor(void* self,void*){return Ctor(self,0x758258);}
void* __fastcall SliderCtor(void* self,void*){return Ctor(self,0x73E9D0);}
void* __cdecl Allocate(unsigned n){void* p=std::calloc(1,n);assert(p);sizes[p]=n;return p;}
void __cdecl Free(void* p){assert(sizes.erase(p));std::free(p);}
void __fastcall String(void* p,void*,const char* value){At<char*>(p,0)=_strdup(value);}
void __fastcall FreeString(void* p,void*){std::free(At<void*>(p,0));}
void __fastcall Caption(void* p,void*,void* s){captions[p]=At<char*>(s,0);}
int fontSelections=0;
void __fastcall SetFont(void* mockSelf,void*,const char* base) {
    // SetBaseFont calls GetUpdatedFontName, which appends a resolution/user
    // suffix. A resource name already ending in that suffix requests a missing
    // atlas (the original crash used fnt_d16x16bb).
    const std::set<std::string> bases={"fnt_d16x16","dialogfont16x16","dialogfont10x10","fnt_console"};
    assert(bases.count(base));
    for(char suffix : {'a','b'}) {
        const std::string resolved=std::string(base)+suffix;
        assert(bases.count(base)); // canonical bases resolve via the native a/b policy (console is exempt)
    }
    ++fontSelections;
}
void __fastcall Clone(void* p,void*,const Rect* r,void* proto){At<Rect>(p,4)=*r;At<unsigned>(p,0x44)=At<unsigned>(proto,0x44);}
void __fastcall Add(void* panel,void*,void* c) {
    const int n=At<int>(panel,0x24);
    At<void**>(panel,0x20)[n]=c;At<int>(panel,0x24)=n+1;At<void*>(c,0x34)=panel;
}
void __fastcall BindControl(void* p,void*,void* c,void* name,int filed) {
    assert(!filed);
    auto at=controls[source].find(At<char*>(name,0));
    if(at==controls[source].end())return;
    At<Rect>(c,4)=At<Rect>(at->second,4);At<int>(c,0x50)=At<int>(at->second,0x50);
}
void* __fastcall PanelCtor(void* p,void*,void* m) {
    At<void*>(p,0x18)=m;At<void**>(p,0x20)=new void*[512]{};At<int>(p,0x24)=14;return p;
}
void __fastcall PanelDtor(void* p,void*) {
    KmrpTextOptionsDestroyedK1(p);delete[] At<void**>(p,0x20);controls.erase(p);
}
void __fastcall Start(void* p,void*,void*){At<void*>(p,0x2C)=p;}
void __fastcall Release(void* p,void*){At<void*>(p,0x2C)=nullptr;}
void __fastcall AddEvent(void* mockSelf,void*,int,void*,void*){}
void __fastcall SetFocus(void* p,void*,void* c,int){At<void*>(p,0x1C)=c;}
int __fastcall Exists(void* mockSelf,void*,void* p){return active.count(p)?1:0;}
int __fastcall Remove(void* mockSelf,void*,void* p){return active.erase(p)?1:0;}
void __fastcall AddPanel(void* mockSelf,void*,void* p,int,int){active.insert(p);}
void __fastcall SetSelected(void* self,void*,unsigned selected){At<unsigned>(self,0x1C8)=(At<unsigned>(self,0x1C8)&~1u)|(selected&1);}
void __fastcall SetMax(void* s,void*,int n){At<int>(s,0x70)=n;}
void __fastcall SetValue(void* s,void*,int n){At<int>(s,0x74)=n;}
void __fastcall Reset(void* self,void*){++resets;At<unsigned>(self,0x58)=0;At<void*>(self,0x40)=nullptr;At<unsigned char>(self,0xE0)=0;}
void __fastcall Load(void* mockSelf,void*,const char*){++loads;}
void __fastcall Image(void* self,void*){++images;At<unsigned char>(self,0xE0)=1;}
void __fastcall Enqueue(void* self,void*,void* texture) {
    assert(self==Native(0x7A4770));refresh.push_back(texture);
}
void __cdecl BuildAll() {
    for(void* texture:refresh) {
        if(!At<unsigned char>(texture,0xE0))Image(texture,nullptr);
        At<unsigned>(texture,0x58)=++builds;
        At<unsigned>(texture,0xFC)=builds;
        At<void*>(texture,0x40)=static_cast<char*>(texture)+0xFC;
    }
    refresh.clear();
}
void Jump(unsigned at,void* to) {
    functions[at]=to;
}
void Setup() {
    for(auto v:{0x73E010,0x73E658,0x73E5B8,0x73E9D0,0x758258}) {
        auto table=static_cast<void**>(Native(v));table[0]=reinterpret_cast<void*>(&DummyDtor);table[1]=reinterpret_cast<void*>(&SetRect);
    }
#define MAP(address,name) Jump(address,reinterpret_cast<void*>(&name))
    MAP(0x6FA7E6,Allocate);MAP(0x6FA390,Free);MAP(0x41C0F0,ButtonCtor);MAP(0x41ACD0,LabelCtor);MAP(0x41BAA0,SliderCtor);
    MAP(0x418D80,Clone);MAP(0x40B9A0,Add);MAP(0x5E5A90,String);MAP(0x5E5C20,FreeString);MAP(0x415E00,Caption);
    MAP(0x40B930,BindControl);MAP(0x40B570,PanelCtor);MAP(0x40CF70,PanelDtor);MAP(0x40A680,Start);MAP(0x40B8F0,Release);
    MAP(0x41AB20,AddEvent);MAP(0x40A630,SetFocus);MAP(0x40BD70,Exists);MAP(0x40C830,Remove);MAP(0x40BC70,AddPanel);
    MAP(0x6E00D0,ChoiceCtor);MAP(0x685540,SetSelected);
    MAP(0x417EC0,SetMax);MAP(0x417EE0,SetValue);MAP(0x415DD0,SetFont);
    MAP(0x420670,Reset);MAP(0x422AF0,Load);MAP(0x41FA30,Image);
    MAP(0x46BD10,Enqueue);MAP(0x4217F0,BuildAll);
#undef MAP
    auto texture=static_cast<char*>(std::calloc(1,0x100));At<void*>(texture,0x38)=texture;
    strcpy_s(texture+0x98,16,"fnt_console");At<unsigned>(texture,0x58)=At<unsigned>(texture,0xE8)=99;
    auto normal=static_cast<char*>(std::calloc(1,0x100));At<void*>(normal,0x38)=normal;
    strcpy_s(normal+0x98,16,"NormCubeMap");
    auto textures=new void*[2]{texture,normal};*static_cast<void***>(Native(0x7A4798))=textures;*static_cast<int*>(Native(0x7A479C))=2;
}
void CleanupFonts() {
    auto textures=*static_cast<void***>(Native(0x7A4798));std::free(textures[0]);std::free(textures[1]);delete[] textures;
}
}

void* KmrpTextOptionsTestFunction(unsigned address){assert(Mock::functions.count(address));return Mock::functions.at(address);}
void* KmrpTextOptionsTestAddress(std::uintptr_t address){
    if(address<0x400000 || address>=0x800000)return reinterpret_cast<void*>(address);
    const auto page=address&~std::uintptr_t(65535);return Mock::pages[page].data()+(address-page);
}
bool KmrpTextOptionsTestConfirmHeld(){return Mock::held;}
bool KmrpHudOptionsOpenK1(){return false;}

void* KmrpRuntimeControlByTagK1(void* p,const char* tag){
    const auto at=Mock::controls[p].find(tag);return at==Mock::controls[p].end()?nullptr:at->second;
}
std::vector<void*> KmrpRuntimePanelsK1(const char*) {
    std::vector<void*> result;for(auto& p:Mock::controls)result.push_back(p.first);return result;
}
void KmrpReflowTextK1(){++Mock::reflows;}
bool KmrpRuntimeIsFontK1(const char* name){return !_stricmp(name,"fnt_console");}
bool KmrpRuntimeApplyTextPreferencesK1(){++Mock::applies;if(Mock::fail){Mock::fail=false;return false;}return true;}

int main(int argc,char** argv) {
    assert(argc==2);Mock::Setup();initialized=true;
    std::ifstream input(argv[1]);assert(input);std::string name;unsigned cases=0;
    while(input>>name) {
        char manager[128]{};
        void* owner=Mock::Allocate(0x64);Mock::PanelCtor(owner,nullptr,manager);At<std::uintptr_t>(owner,0)=GraphicsTable;
        Mock::source=owner;Mock::active.insert(owner);
        for(unsigned i=0;i<9;++i) {
            Rect r{};input>>r.left>>r.top>>r.width>>r.height;assert(input);
            void* c=Mock::Allocate(0x300);Mock::Ctor(c,i==8?0x758258:i==1?0x73E9D0:i>=4?ButtonTable:0x73E5B8);
            At<Rect>(c,4)=r;At<int>(c,0x50)=Mock::ids[i];At<void*>(c,0x34)=owner;
            At<void**>(owner,0x20)[Mock::ids[i]]=c;Mock::controls[owner][Mock::tags[i]]=c;
            if(i==3)At<int>(c,0x110)=(std::max)(1,r.width*86/1381);   // LB_DESC's scrollbar, as at 3440x1440
        }
        sizing=requestedSizing=Sizes{};style=requestedStyle=HdOriginal;dirty=false;blockReopen=false;releasedFrames=2;
        auto adv=Mock::controls[owner]["BTN_ADVANCED"];auto above=Mock::controls[owner]["BTN_RESOLUTION"];
        At<void*>(adv,0x5C)=above;At<void*>(above,0x64)=adv;At<unsigned>(adv,0x44)|=4;
        KmrpTextOptionsFrameK1(manager);assert(entries[owner].button);
        void* entry=entries[owner].button;const Rect expected=KmrpTextOptions::Entry(At<Rect>(adv,4));
        assert(!std::memcmp(&At<Rect>(entry,4),&expected,sizeof expected));assert(At<int>(owner,0x24)==15);
        assert(At<void*>(adv,0x5C)==entry && At<void*>(above,0x64)==entry);
        At<unsigned>(adv,0x44)&=~4u;KmrpTextOptionsFrameK1(manager);assert(!(At<unsigned>(entry,0x44)&4));
        Mock::held=true;Open(owner,nullptr,nullptr);KmrpTextOptionsFrameK1(manager);assert(current && sliders[0] && fontChoices[OldHd]);
        // The right-hand column inside the frame round the list, as far from it on the
        // right as on the left, clear of the scrollbar's strip (since 2026-10-19).
        {
            void* list=Mock::controls[owner]["LB_DESC"];
            const Rect at=At<Rect>(list,4);const int bar=At<int>(list,0x110);
            const int frameLeft=at.left-(bar*23+43)/86, frameRight=at.left+at.width-bar-(bar*13+43)/86;
            std::vector<void*> column(std::begin(fontChoices),std::end(fontChoices));
            column.insert(column.end(),std::begin(previews),std::end(previews));
            for(void* c:column) {
                const Rect r=At<Rect>(c,4);
                assert(r.left-frameLeft>0 && r.left-frameLeft==frameRight-(r.left+r.width));
            }
        }
        assert(At<int>(sliders[0],0x74)==(Default-Minimum)/Step && At<int>(sliders[0],0x70)==SliderMaximum);
        assert(Mock::captions[static_cast<char*>(sizeLabels[0])+0xE8]=="Menus & Replies: 50%");
        assert(Mock::captions[static_cast<char*>(fontChoices[HdOriginal])+0x16C]=="(New) Original HD Font");
        assert(Mock::captions[static_cast<char*>(fontChoices[OldHd])+0x16C]=="(Old) HD Font");
        auto selected=[](int wanted){
            int count=0;for(int i=0;i<FontStyleCount;++i){
                assert(At<int>(fontChoices[i],0x1C4)==-1);
                const bool on=(At<unsigned>(fontChoices[i],0x1C8)&1)!=0;
                assert(on==(i==wanted));count+=on;
            }assert(count==1);
        };
        selected(HdOriginal);
        assert(owned.size()==22);   // with the glyphs beside Default's and Close's captions
        // "Link Text Sizes" at the top of the left column, the slider pairs under it, the
        // last above Default (since 2026-10-19; the link was under the pairs).
        {
            const auto link=At<Rect>(linkSizes,4);
            assert(link.top==At<Rect>(Mock::controls[owner]["LBL_GAMMA"],4).top);
            assert(link.top+link.height<=At<Rect>(sizeLabels[0],4).top);
        }
        for(int i=0;i<TextGroupCount;++i) {
            const auto label=At<Rect>(sizeLabels[i],4), track=At<Rect>(sliders[i],4);
            assert(label.left==track.left && label.width==track.width);
            assert(label.top+label.height<=track.top);
            if(i+1<TextGroupCount)assert(track.top+track.height<=At<Rect>(sizeLabels[i+1],4).top);
            else assert(track.top+track.height<=At<Rect>(Mock::controls[owner]["BTN_DEFAULT"],4).top);
        }
        // The page opens on the link; right from it is the font chosen; the sliders lead
        // nowhere left or right (their own left and right move them); Default and Close are
        // reached by no pad link from the link, the sliders or the fonts.
        assert(At<void*>(current,0x1C)==linkSizes);
        assert(At<void*>(linkSizes,0x68)==fontChoices[HdOriginal] && At<void*>(linkSizes,0x60)==fontChoices[HdOriginal]);
        assert(At<void*>(linkSizes,0x64)==sliders[0] && At<void*>(linkSizes,0x5C)==sliders[TextGroupCount-1]);
        for(void* slider:sliders)assert(!At<void*>(slider,0x60) && !At<void*>(slider,0x68));
        {
            std::vector<void*> reachable{linkSizes};
            for(void* c:sliders)reachable.push_back(c);
            for(void* c:fontChoices)reachable.push_back(c);
            for(void* c:reachable)for(unsigned at:{0x5Cu,0x60u,0x64u,0x68u}) {
                void* to=At<void*>(c,at);
                assert(to==nullptr || std::find(reachable.begin(),reachable.end(),to)!=reachable.end());
            }
        }
        // Y restores the defaults and B closes wherever the focus is (Input).
        assert(table[15]==reinterpret_cast<std::uintptr_t>(&Input));
        assert((At<unsigned>(linkSizes,0x1C8)&1) && At<int>(linkSizes,0x1C4)==-1);
        std::set<int> ids;
        for(void* c:owned){assert(ids.insert(At<int>(c,0x50)).second);assert(At<void**>(current,0x20)[At<int>(c,0x50)]==c);}
        // Ignore the confirm that opened the page, then accept subsequent presses.
        SelectHd(current,nullptr,nullptr);Back(current,nullptr,nullptr);
        assert(!dirty && !(At<unsigned>(current,0x44)&0x400));
        Mock::held=false;KmrpTextOptionsFrameK1(manager);assert(!Armed());
        KmrpTextOptionsFrameK1(manager);assert(Armed());
        Mock::held=true;At<int>(sliders[0],0x74)=0;KmrpTextOptionsFrameK1(manager);assert(sizing.values[Menus]==Minimum);
        for(int value:sizing.values)assert(value==Minimum);
        // Each slider works independently; re-linking matches the last changed group.
        const int beforeLinkLoads=Mock::loads;
        ToggleLink(current,nullptr,nullptr);KmrpTextOptionsFrameK1(manager);assert(!sizing.linked && Mock::loads==beforeLinkLoads);
        for(int i=0;i<TextGroupCount;++i) {
            At<int>(sliders[i],0x74)=(40+i*5-Minimum)/Step;KmrpTextOptionsFrameK1(manager);
            assert(sizing.values[i]==40+i*5);
        }
        assert(KmrpTextSizeForFontK1("dialogfont16x16b")==40);
        assert(KmrpTextSizeForFontK1("fnt_d16x16b")==45);
        assert(KmrpTextSizeForFontK1("dialogfont10x10b")==50);
        assert(KmrpTextSizeForFontK1("fnt_console")==55);
        // A click is acted on once: the second call of the same press (the pad's A
        // reaches the handler going down and coming up) is ignored until the confirm
        // button has been released for two frames.
        ToggleLink(current,nullptr,nullptr);KmrpTextOptionsFrameK1(manager);assert(!sizing.linked);
        Mock::held=false;KmrpTextOptionsFrameK1(manager);KmrpTextOptionsFrameK1(manager);
        ToggleLink(current,nullptr,nullptr);KmrpTextOptionsFrameK1(manager);assert(sizing.linked);
        Mock::held=true;
        for(int value:sizing.values)assert(value==55);
        At<int>(sliders[Body],0x74)=0;KmrpTextOptionsFrameK1(manager);
        for(int value:sizing.values)assert(value==Minimum);
        // Every percentage is reachable without snapping, with native one-position
        // moves in either direction and the other linked sliders synchronized.
        for(int value=Minimum;cases==0 && value<=Maximum;++value) {
            At<int>(sliders[Menus],0x74)=value-Minimum;KmrpTextOptionsFrameK1(manager);
            for(int group=0;group<TextGroupCount;++group) {
                assert(sizing.values[group]==value);
                assert(At<int>(sliders[group],0x74)==value-Minimum);
            }
        }
        At<int>(sliders[Hud],0x74)=SliderMaximum;KmrpTextOptionsFrameK1(manager);
        --At<int>(sliders[Hud],0x74);KmrpTextOptionsFrameK1(manager);
        for(int value:sizing.values)assert(value==Maximum-1);
        // Between clicks the confirm button is let go for two frames, as a player does:
        // a click is acted on once (the second call of the same press is ignored).
        const auto release=[&]{const bool was=Mock::held;Mock::held=false;KmrpTextOptionsFrameK1(manager);KmrpTextOptionsFrameK1(manager);Mock::held=was;};
        release();
        const int resetBefore=Mock::resets;const int buildBefore=Mock::builds;
        SelectHd(current,nullptr,nullptr);KmrpTextOptionsFrameK1(manager);assert(style==OldHd);
        auto texture=(*static_cast<void***>(Native(0x7A4798)))[0];
        assert(At<unsigned>(texture,0x58)!=0 && At<void*>(texture,0x40)!=nullptr);
        assert(Mock::resets==resetBefore+1 && Mock::builds==buildBefore+1 && Mock::refresh.empty());
        selected(OldHd);
        release();SelectOriginal(current,nullptr,nullptr);KmrpTextOptionsFrameK1(manager);assert(style==Original);selected(Original);
        release();const int sameBuild=Mock::builds;
        SelectOriginal(current,nullptr,nullptr);KmrpTextOptionsFrameK1(manager);assert(Mock::builds==sameBuild);selected(Original);
        release();SelectHdOriginal(current,nullptr,nullptr);KmrpTextOptionsFrameK1(manager);assert(style==HdOriginal);selected(HdOriginal);
        release();SelectOriginal(current,nullptr,nullptr);KmrpTextOptionsFrameK1(manager);selected(Original);
        release();ToggleLink(current,nullptr,nullptr);KmrpTextOptionsFrameK1(manager);assert(!sizing.linked);
        At<int>(sliders[Body],0x74)=(80-Minimum)/Step;KmrpTextOptionsFrameK1(manager);assert(sizing.values[Body]==80);
        Mock::held=false;KmrpTextOptionsFrameK1(manager);KmrpTextOptionsFrameK1(manager);
        Mock::held=true;KmrpTextOptionsFrameK1(manager);
        Defaults(current,nullptr,nullptr);KmrpTextOptionsFrameK1(manager);
        assert(sizing.values[Menus]==Default && style==HdOriginal && At<int>(sliders[0],0x74)==(Default-Minimum)/Step);selected(HdOriginal);
        for(int value:sizing.values)assert(value==Default);
        assert(sizing.linked && (At<unsigned>(linkSizes,0x1C8)&1));
        release();Mock::fail=true;SelectHd(current,nullptr,nullptr);KmrpTextOptionsFrameK1(manager);assert(style==HdOriginal && requestedStyle==HdOriginal);selected(HdOriginal);
        // Restoring the entry while A remains held must never reopen the modal.
        release();Mock::held=true;Back(current,nullptr,nullptr);
        assert((At<unsigned>(current,0x44)&0x700)==0x400);
        Destroy(current,nullptr,1);KmrpTextOptionsFrameK1(manager);
        Open(owner,nullptr,nullptr);assert(!pending && !current);
        KmrpTextOptionsFrameK1(manager);Open(owner,nullptr,nullptr);assert(!pending);
        Mock::held=false;KmrpTextOptionsFrameK1(manager);Open(owner,nullptr,nullptr);assert(!pending);
        KmrpTextOptionsFrameK1(manager);Open(owner,nullptr,nullptr);KmrpTextOptionsFrameK1(manager);assert(current);
        // Parent destruction while this modal exists must only queue its close.
        auto originals=Mock::controls[owner];KmrpTextOptionsDestroyedK1(owner);
        assert(!parent && (At<unsigned>(current,0x44)&0x700)==0x400);
        Destroy(current,nullptr,1);assert(!current && owned.empty());
        Mock::active.erase(owner);Mock::PanelDtor(owner,nullptr);
        for(auto c:originals)Mock::DummyDtor(c.second,nullptr,1);
        Mock::Free(owner);assert(entries.empty() && Mock::sizes.empty());++cases;
    }
    Mock::CleanupFonts();
    assert(Mock::fontSelections==2*TextGroupCount*cases);
    assert(cases>=66 && Mock::loads>0 && Mock::images>0 && Mock::reflows>0);
    wchar_t path[MAX_PATH];assert(ConfigPath(path));
    assert(GetPrivateProfileIntW(L"KMRP Text",L"Size",-1,path)==Default);
    assert(GetPrivateProfileIntW(L"KMRP Text",L"OriginalFont",-1,path)==1);
    assert(GetPrivateProfileIntW(L"KMRP Text",L"FontStyle",-1,path)==HdOriginal);
    // Existing two-style installs migrate, and all three explicit styles persist.
    assert(WritePrivateProfileStringW(L"KMRP Text",L"FontStyle",nullptr,path));
    assert(WritePrivateProfileStringW(L"KMRP Text",L"OriginalFont",L"1",path));
    for(const wchar_t* key:groupKeys)assert(WritePrivateProfileStringW(L"KMRP Text",key,nullptr,path));
    assert(WritePrivateProfileStringW(L"KMRP Text",L"LinkSizes",nullptr,path));
    assert(WritePrivateProfileStringW(L"KMRP Text",L"Size",L"85",path));
    sizing=Sizes{};initialized=false;assert(KmrpTextFontStyleK1()==HdOriginal);
    assert(WritePrivateProfileStringW(L"KMRP Text",L"OriginalFont",L"0",path));
    initialized=false;assert(KmrpTextFontStyleK1()==OldHd);
    // Nothing saved: the default, HD Original.
    assert(WritePrivateProfileStringW(L"KMRP Text",L"OriginalFont",nullptr,path));
    initialized=false;assert(KmrpTextFontStyleK1()==HdOriginal);
    for(int value:sizing.values)assert(value==85);
    assert(sizing.linked);
    sizing.values={{41,47,53,59}};sizing.linked=false;assert(Save());
    sizing=Sizes{};initialized=false;assert(KmrpTextSizePercentK1()==41);
    assert((!sizing.linked && sizing.values==std::array<int,TextGroupCount>{{41,47,53,59}}));
    sizing=Sizes{};assert(Save());
    for(int expected:{Original,HdOriginal,OldHd}) {
        style=expected;assert(Save());initialized=false;
        assert(KmrpTextFontStyleK1()==expected && KmrpTextSizePercentK1()==Default);
    }
    std::cout<<"PASS: "<<cases<<" native UI fixtures; cloned geometry/focus policy, unique IDs, navigation, 50% default, four independent/linked sliders, three exclusive fonts (HD Original by default), defaults, failed-style rollback and parent/modal cleanup. ABI is mocked; game execution remains a separate check.\n";
}
