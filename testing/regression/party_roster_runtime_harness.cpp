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
extern "C" int KmrpGalaxyMap(const char*,const char*,const char*,const char*) {return 1;}
extern "C" int KmrpMainMenuBars(const char*,const char*) {return 1;}
// The art pack is not read here (K1AssetPack.cpp, not in this harness).
namespace KmrpPack {
bool ReadHeader(const unsigned char*,std::size_t,Key&,std::uint32_t&) {return false;}
bool ReadIndex(const unsigned char*,std::size_t,std::uint64_t,Index&) {return false;}
bool Unpack(const Block&,const unsigned char*,unsigned char*) {return false;}
bool Unfilter(unsigned char,unsigned char*,std::size_t) {return false;}
std::string IdentityText(const Key&) {return std::string();}
}
void KmrpRuntimeLog(const char* line) {std::cout<<line<<'\n';}
// K1RuntimeAssets.cpp sizes and chooses fonts from the text options (K1TextOptions.cpp,
// not in this harness, since 2026-10-18): the default size and style.
int KmrpTextSizeForFontK1(const char*) {return 50;}
int KmrpTextFontStyleK1() {return 1;}
int wmain(int argc,wchar_t** argv) {
    assert(argc==4); namespace fs=std::filesystem;
    wchar_t module[MAX_PATH];GetModuleFileNameW(nullptr,module,MAX_PATH);
    const fs::path root=fs::path(module).parent_path();
    // A size's set in the cache and this run's folder for it, which the game is shown
    // (K1RuntimeAssets.cpp since 2026-10-19; until then one folder, written in place).
    const fs::path setDir=root/L"set",viewDir=root/L"view";
    fs::create_directories(root/L"override");fs::create_directories(setDir);
    auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(image.data());dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=0x80;
    auto nt=reinterpret_cast<IMAGE_NT_HEADERS*>(image.data()+0x80);nt->Signature=IMAGE_NT_SIGNATURE;
    nt->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;nt->OptionalHeader.SizeOfImage=static_cast<DWORD>(image.size());
    auto set=[](unsigned a,unsigned b){std::memcpy(image.data()+0x22DE20,&a,4);std::memcpy(image.data()+0x232E50,&b,4);};
    set(0x3A80,0x3A80);assert(!KmrpPartyRoster32ActiveK1());
    set(0xA194,0x3A80);assert(!KmrpPartyRoster32ActiveK1());
    set(0xA194,0xA194);assert(KmrpPartyRoster32ActiveK1());
    const fs::path original=root/L"override"/L"partyselection.gui",shipped=setDir/L"partyselection.gui",shown=viewDir/L"partyselection.gui";
    fs::copy_file(argv[1],original,fs::copy_options::overwrite_existing);
    std::vector<unsigned char> source,layout,second,got;assert(Read(original.wstring(),source));assert(Read(argv[2],layout));assert(Read(argv[3],second));
    // KMRP's layout in the set, the run's folder made as LinkSet makes it (Override read
    // afresh: the game reads it once a run, the fixture changes it between steps), then
    // the roster adapted into that folder.
    auto show=[&](const std::vector<unsigned char>& kmrp) {
        assert(WriteNew(shipped.wstring(),kmrp));
        fs::remove_all(viewDir);fs::create_directories(viewDir);
        overrideListed=false;overrideNames.clear();overrideTextures.clear();
        if(!OverrideHas(L"partyselection.gui"))assert(Link(shipped.wstring(),shown.wstring()));
        return AdaptPartyRosterK1(setDir.wstring(),viewDir.wstring());
    };
    set(0x3A80,0x3A80);assert(!show(layout));assert(!fs::exists(shown));
    set(0xA194,0xA194);assert(show(layout));assert(Read(shown.wstring(),got));assert(got!=layout);
    assert(Read(shipped.wstring(),got)&&got==layout);   // the set itself is never written
    assert(show(second));
    std::vector<unsigned char> expected;std::string reason;assert(KmrpBuildPartyRosterGui(source,second,expected,reason));assert(Read(shown.wstring(),got)&&got==expected);
    assert(show(layout));
    assert(Read(original.wstring(),got)&&got==source);
    {std::ofstream f(original,std::ios::binary);f<<"invalid supplied GUI";}
    assert(!show(layout));assert(!fs::exists(shown));
    // No supplied GUI: generate from KMRP's current size, without writing Override.
    fs::remove(original);assert(show(layout));
    assert(Read(shown.wstring(),got));assert(KmrpGeneratePartyRosterGui(layout,expected,reason));assert(got==expected);
    assert(!fs::exists(original));
    set(0x3A80,0x3A80);assert(!show(layout));
    assert(Read(shown.wstring(),got)&&got==layout); // stock without mod keeps stock layout
    // Reset only our fixture's source, never the real mod input.
    fs::copy_file(argv[1],original,fs::copy_options::overwrite_existing);
    std::cout<<"PASS: backend absent/partial/active; Override precedence; adapted in the run's folder, the set untouched; size round trip; unsupported fallback; original bytes preserved.\n";
}
