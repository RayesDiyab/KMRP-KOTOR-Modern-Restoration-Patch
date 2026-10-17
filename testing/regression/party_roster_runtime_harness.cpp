#include <windows.h>
#include <vector>
#include <filesystem>
#include <fstream>
#include <cassert>
#include <iostream>
static std::vector<unsigned char> image(0x300000);
static HMODULE FakeModule(LPCWSTR) { return reinterpret_cast<HMODULE>(image.data()); }
#define GetModuleHandleW FakeModule
#include "../../src/controller-native/K1RuntimeAssets.cpp"
#undef GetModuleHandleW
extern "C" int KmrpGuiBlend(const char*,unsigned,unsigned,const char*,const char*) {return 1;}
extern "C" int KmrpGuiBlendCovers(const char*,unsigned,unsigned) {return 0;}
extern "C" int KmrpAbilityIcons(const char*,unsigned,const char*,const char*) {return 1;}
extern "C" int KmrpGameArt(const char*,const char*,unsigned,const char*) {return 1;}
extern "C" int KmrpSwoopHud(const char*,const char*,unsigned,unsigned) {return 1;}
bool KmrpXpressDecode(const unsigned char*,std::size_t,unsigned char*,std::size_t) {return false;}
void KmrpRuntimeLog(const char* line) {std::cout<<line<<'\n';}
int wmain(int argc,wchar_t** argv) {
    assert(argc==4); namespace fs=std::filesystem;
    wchar_t module[MAX_PATH];GetModuleFileNameW(nullptr,module,MAX_PATH);
    const fs::path root=fs::path(module).parent_path();
    fs::create_directories(root/L"override");fs::create_directories(root/L"cache");cache=(root/L"cache").wstring();
    auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(image.data());dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=0x80;
    auto nt=reinterpret_cast<IMAGE_NT_HEADERS*>(image.data()+0x80);nt->Signature=IMAGE_NT_SIGNATURE;
    nt->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;nt->OptionalHeader.SizeOfImage=static_cast<DWORD>(image.size());
    auto set=[](unsigned a,unsigned b){std::memcpy(image.data()+0x22DE20,&a,4);std::memcpy(image.data()+0x232E50,&b,4);};
    set(0x3A80,0x3A80);assert(!KmrpPartyRoster32ActiveK1());
    set(0xA194,0x3A80);assert(!KmrpPartyRoster32ActiveK1());
    set(0xA194,0xA194);assert(KmrpPartyRoster32ActiveK1());
    const fs::path original=root/L"override"/L"partyselection.gui",cached=root/L"cache"/L"partyselection.gui";
    fs::copy_file(argv[1],original,fs::copy_options::overwrite_existing);
    std::vector<unsigned char> source,layout,second,got;assert(Read(original.wstring(),source));assert(Read(argv[2],layout));assert(Read(argv[3],second));
    if(fs::exists(cached))fs::remove(cached);
    assert(Write("partyselection.gui",layout));
    set(0x3A80,0x3A80);assert(!AdaptPartyRosterK1());assert(YieldToOverride()==1);assert(!fs::exists(cached));
    assert(Write("partyselection.gui",layout));set(0xA194,0xA194);assert(AdaptPartyRosterK1());assert(YieldToOverride()==0);assert(Read(cached.wstring(),got));assert(got!=layout);
    assert(Write("partyselection.gui",second));assert(AdaptPartyRosterK1());assert(YieldToOverride()==0);
    std::vector<unsigned char> expected;std::string reason;assert(KmrpBuildPartyRosterGui(source,second,expected,reason));assert(Read(cached.wstring(),got)&&got==expected);
    assert(Write("partyselection.gui",layout));assert(AdaptPartyRosterK1());assert(YieldToOverride()==0);
    assert(Read(original.wstring(),got)&&got==source);
    {std::ofstream f(original,std::ios::binary);f<<"invalid supplied GUI";}
    assert(Write("partyselection.gui",layout));assert(!AdaptPartyRosterK1());assert(YieldToOverride()==1);assert(!fs::exists(cached));
    // No supplied GUI: generate from KMRP's current size, without writing Override.
    fs::remove(original);assert(Write("partyselection.gui",layout));assert(AdaptPartyRosterK1());
    assert(Read(cached.wstring(),got));assert(KmrpGeneratePartyRosterGui(layout,expected,reason));assert(got==expected);
    assert(!fs::exists(original));
    set(0x3A80,0x3A80);assert(Write("partyselection.gui",layout));assert(!AdaptPartyRosterK1());
    assert(Read(cached.wstring(),got)&&got==layout); // stock without mod keeps stock layout
    // Reset only our fixture's source, never the real mod input.
    fs::copy_file(argv[1],original,fs::copy_options::overwrite_existing);
    std::cout<<"PASS: backend absent/partial/active; Override precedence; managed cache; size round trip; unsupported fallback; original bytes preserved.\n";
}
