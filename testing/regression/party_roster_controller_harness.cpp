#include <windows.h>
#include <vector>
#include <cassert>
#include <cstring>
#include <cstdio>
static std::vector<unsigned char> image(0x300000);
static bool rosterLoaded=false;
static HMODULE FakeModule(LPCWSTR name) { return name && !rosterLoaded?nullptr:reinterpret_cast<HMODULE>(image.data()); }
static FARPROC FakeSymbol(HMODULE,LPCSTR) {return reinterpret_cast<FARPROC>(1);}
#define GetModuleHandleW FakeModule
#define GetProcAddress FakeSymbol
#include "../../src/controller-native/vendor/K1XboxControls.cpp"
#undef GetModuleHandleW
#undef GetProcAddress
int main() {
    SetErrorMode(SEM_NOGPFAULTERRORBOX | SEM_FAILCRITICALERRORS);
    auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(image.data());dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=0x80;
    auto nt=reinterpret_cast<IMAGE_NT_HEADERS*>(image.data()+0x80);nt->Signature=IMAGE_NT_SIGNATURE;
    nt->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;nt->OptionalHeader.SizeOfImage=static_cast<DWORD>(image.size());
    auto put=[](unsigned offset,unsigned value){std::memcpy(image.data()+offset,&value,4);};
    put(0x22DE20,0x3A80);put(0x232E50,0x3A80);assert(!KmrpPartyRoster32ActiveK1());
    put(0x22DE20,0xA194);assert(!KmrpPartyRoster32ActiveK1());
    put(0x232E50,0xA194);assert(KmrpPartyRoster32ActiveK1());
    put(0x22DE20,0x3A80);put(0x232E50,0x3A80);
    image[0x16554C]=image[0x1665DD]=32;image[0x2BFEF6]=0xE9;
    assert(!KmrpPartyRoster32ActiveK1());rosterLoaded=true;assert(KmrpPartyRoster32ActiveK1());
    image[0x1665DD]=9;assert(!KmrpPartyRoster32ActiveK1());image[0x1665DD]=32;
    // A small stock-sized panel with separately allocated controls, arbitrary
    // IDs read from tags, and no enlarged tail. No hardcoded offset may work.
    std::vector<unsigned char> panel(0x80,0xA5);
    std::array<std::array<unsigned char,0x1C4>,5> buttons{};
    std::array<void*,110> controls{};
    KmrpPartyIdsK1 ids{{7,33,60,92,109}};
    auto word=[](void* b,unsigned at)->unsigned&{return *reinterpret_cast<unsigned*>(static_cast<unsigned char*>(b)+at);};
    auto ptr=[](void* b,unsigned at)->void*&{return *reinterpret_cast<void**>(static_cast<unsigned char*>(b)+at);};
    word(panel.data(),0)=K1_PARTY_SELECT_PANEL_VTABLE;
    ptr(panel.data(),0x20)=controls.data();word(panel.data(),0x24)=static_cast<unsigned>(controls.size());
    for(unsigned i=0;i<5;++i) {
        buttons[i].fill(0xA5);word(buttons[i].data(),0)=0x73E658;
        ptr(buttons[i].data(),0x34)=panel.data();word(buttons[i].data(),0x50)=ids[i];controls[ids[i]]=buttons[i].data();
    }
    int count=0;auto prompts=GetK1ControllerPrompts(panel.data(),&count);assert(count==3);
    assert(!ResolveK1PromptControl(panel.data(),prompts[0])); // active backend, not bound yet
    KmrpPartyBindingsK1()[panel.data()]=ids;
    assert(ResolveK1PromptControl(panel.data(),prompts[0])==buttons[1].data());
    assert(ResolveK1PromptControl(panel.data(),prompts[1])==buttons[0].data());
    assert(ResolveK1PromptControl(panel.data(),prompts[2])==buttons[2].data());
    assert(KmrpPartyPagesBoundK1(panel.data()));
    // Real released backend compacts/reorders this list between pages. IDs
    // 108/109 can be greater than the number of currently attached controls.
    controls.fill(nullptr);
    for(unsigned i=0;i<5;++i)controls[4-i]=buttons[i].data();
    word(panel.data(),0x24)=5;
    assert(KmrpPartyPagesBoundK1(panel.data()));
    assert(ResolveK1PromptControl(panel.data(),prompts[0])==buttons[1].data());
    assert(ResolveK1PromptControl(panel.data(),prompts[1])==buttons[0].data());
    for(unsigned okFlags:{0x10U,0x15U,0x11U,0x14U}) {
        word(buttons[0].data(),0x44)=okFlags;word(buttons[3].data(),0x44)=0x17;word(buttons[4].data(),0x44)=0x12;
        auto expected=buttons;const auto beforePanel=panel;
        for(unsigned i:{3U,4U})word(expected[i].data(),0x44)=(word(expected[i].data(),0x44)&~4u)|(okFlags&4u);
        KmrpMirrorPartyPageFocusK1(panel.data());assert(buttons==expected && panel==beforePanel);
        KmrpMirrorPartyPageFocusK1(panel.data());assert(buttons==expected && panel==beforePanel);
    }
    controls[0]=nullptr;auto before=buttons;KmrpMirrorPartyPageFocusK1(panel.data());assert(buttons==before);
    assert(!KmrpPartyPagesBoundK1(panel.data()));controls[0]=buttons[4].data();
    ptr(buttons[3].data(),0x34)=nullptr;before=buttons;KmrpMirrorPartyPageFocusK1(panel.data());assert(buttons==before);
    ptr(buttons[3].data(),0x34)=panel.data();word(panel.data(),0x24)=513;
    assert(!KmrpPartyControlK1(panel.data(),0));word(panel.data(),0x24)=5;
    before=buttons;KmrpMirrorPartyPageFocusK1(nullptr);KmrpPartyBindingsK1().erase(panel.data());
    KmrpMirrorPartyPageFocusK1(panel.data());assert(buttons==before);
    rosterLoaded=false;image[0x16554C]=image[0x1665DD]=9;image[0x2BFEF6]=0xE8;
    assert(ResolveK1PromptControl(panel.data(),prompts[0])==panel.data()+0x38B8);
    std::array<unsigned char,0x454> record{};
    word(record.data(),0)=0x756BB8;ptr(record.data(),0x34)=panel.data();ptr(record.data(),0x58)=record.data();
    word(record.data(),0x448)=1;word(record.data(),0x450)=9;
    auto label=record.data()+0x308;word(label,0)=0x73E5B8;ptr(label,0x34)=panel.data();word(label,0x44)=2;
    bool canSelect=true;
    auto selectable=[&](int slot){assert(slot>=0 && slot<32);return canSelect;};
    unsigned gets=0,fills=0;
    auto getter=[&](int slot,char (&name)[16]){assert(slot==9);++gets;std::memcpy(name,"po_pcanderous",14);return true;};
    auto fill=[&](void* dst,const char* name){assert(dst==label);++fills;std::memcpy(static_cast<char*>(dst)+0xB0,name,16);};
    KmrpPresentPartyRecordK1(panel.data(),record.data(),selectable,getter,fill);assert(gets==1 && fills==1);
    KmrpPresentPartyRecordK1(panel.data(),record.data(),selectable,getter,fill);assert(gets==1 && fills==1); // no repeat loads
    // Unselected/selectable stays bright; selected/unselectable stays dim.
    // Selection, hover, colors and every other byte are owned by the engine.
    for(unsigned selected:{0U,1U})for(bool allowed:{false,true}) {
        word(record.data(),0x1C4)=selected;canSelect=allowed;
        *reinterpret_cast<float*>(record.data()+0x384)=0.5f;
        auto expected=record;*reinterpret_cast<float*>(expected.data()+0x384)=allowed?1.0f:0.25f;
        KmrpPresentPartyRecordK1(panel.data(),record.data(),selectable,getter,fill);
        assert(record==expected && gets==1 && fills==1);
    }
    word(record.data(),0x448)=0;word(record.data(),0x44)=0x27;
    KmrpPresentPartyRecordK1(panel.data(),record.data(),selectable,getter,fill);assert(word(record.data(),0x44)==0x25);
    word(record.data(),0x450)=3;word(record.data(),0x44)=0x27;
    *reinterpret_cast<float*>(record.data()+0x8C)=1.0f;
    auto expectedUnavailable=record;
    *reinterpret_cast<float*>(expectedUnavailable.data()+0x8C)=0.0f;
    KmrpPresentPartyRecordK1(panel.data(),record.data(),selectable,getter,fill);assert(record==expectedUnavailable);
    std::puts("PASS: released/embedded effects; named prompt targets on external controls/arbitrary IDs; OK policy only; every other byte and ownership preserved; lifecycle/partial/absent guards.");
}
void PollXInputK1() {}
bool IsControllerInputActiveK1() {return false;}
bool IsControllerGeneratedKeyK1(unsigned) {return false;}
unsigned long LastInjectedDeadlineK1(unsigned) {return 0;}
void MarkKeyboardMouseInputK1() {}
bool ConsumeMovieSkipK1() {return false;}
bool ControllerHeldRecentlyK1() {return false;}
bool ControllerTypesByItselfK1() {return false;}
void ControllerLogK1(const char*) {}
extern "C" void __cdecl KmrpLogPanelsK1(const char*) {}
extern "C" char __cdecl KmrpGlyphLetterK1() {return 'p';}

void KmrpPartyPortraitsK1(void*) {}
