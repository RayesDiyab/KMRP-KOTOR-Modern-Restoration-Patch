#include <windows.h>
#include <array>
#include <cassert>
#include <cmath>
#include <cstring>
#include <fstream>
#include <iostream>
#include <limits>
#include <string>
#include <vector>
#include "../../src/controller-native/K1RuntimeAssets.cpp"

extern "C" int KmrpGuiBlend(const char*,unsigned,unsigned,const char*,const char*) {return 1;}
extern "C" int KmrpGuiBlendCovers(const char*,unsigned,unsigned) {return 0;}
extern "C" int KmrpAbilityIcons(const char*,unsigned,const char*,const char*) {return 1;}
extern "C" int KmrpGameArt(const char*,const char*,unsigned,const char*) {return 1;}
extern "C" int KmrpSwoopHud(const char*,const char*,unsigned,unsigned) {return 1;}
extern "C" int KmrpGalaxyMap(const char*,const char*,const char*,const char*) {return 1;}
extern "C" int KmrpMainMenuBars(const char*,const char*) {return 1;}
extern "C" int KmrpLiveLayoutSet(const char*,const char*,const char*,int,int,const char*,const char*) {return 1;}
extern "C" int KmrpHudCues(const char*,const char*) {return 1;}
extern "C" const char* KmrpHudFileName(int) {return nullptr;}
extern "C" int KmrpLiveLayoutCount(void) {return 0;}
extern "C" const char* KmrpLiveLayoutName(int) {return nullptr;}
// The mod compatibility merges (kmrp-merge.c, kmrp-gameart.c, kmrp-swoophud.c,
// kmrp-guiadapt.c): never reached, as the harness's sets hold no kmrp_derive.txt.
extern "C" const char* KmrpLiveLayoutNotes(void) {return "";}
// The Icon Size slider (issue 80): at its default, nothing to apply.
int KmrpIconSizePercentK1() {return 50;}
bool KmrpRuntimeEngineRefreshK1() {return true;}
extern "C" int KmrpReadKeyedResource(const char*,const char*,int,unsigned char** data,std::size_t* size) {*data=nullptr;*size=0;return 1;}
extern "C" int KmrpMerge2da(const char*,const unsigned char*,std::size_t,const unsigned char*,std::size_t,const unsigned char*,
                            std::size_t,unsigned char** out,std::size_t* size,char** notes,int*) {*out=nullptr;*size=0;*notes=nullptr;return 3;}
extern "C" void KmrpMergeFree(void*) {}
extern "C" int KmrpDeriveImage(const char*,int,int,int,int,const char*,const char*) {return 1;}
extern "C" int KmrpSwoopHudModel(const char*,const char*,const char*,unsigned,unsigned) {return 1;}
// The art pack is not read here (K1AssetPack.cpp, not in this harness): the font callback
// takes its metrics from the fixture. Until 2026-10-28 this stubbed KmrpXpressDecode, the
// bank's decoder before the pack (b5cbd6a, 2026-10-19), and the harness no longer linked.
namespace KmrpPack {
bool ReadHeader(const unsigned char*,std::size_t,Key&,std::uint32_t&) {return false;}
bool ReadIndex(const unsigned char*,std::size_t,std::uint64_t,Index&) {return false;}
bool Unpack(const Block&,const unsigned char*,unsigned char*) {return false;}
bool Unfilter(unsigned char,unsigned char*,std::size_t) {return false;}
std::string IdentityText(const Key&) {return std::string();}
}
void KmrpRuntimeLog(const char*) {}
int testTextPercent=50;
bool testGrouped=false;
const std::array<int,4> mixedSizes{{35,80,60,95}};
int KmrpTextSizePercentK1() {return testTextPercent;}
int KmrpTextSizeForFontK1(const char* name) {return testGrouped?mixedSizes[KmrpTextOptions::FontGroup(name)]:testTextPercent;}
int KmrpTextFontStyleK1() {return KmrpTextOptions::HdOriginal;}
// Unrelated roster preparation is never reached by the font callback.
bool KmrpBuildPartyRosterGui(const std::vector<unsigned char>&,const std::vector<unsigned char>&,std::vector<unsigned char>&,std::string&) {assert(false);return false;}
bool KmrpGeneratePartyRosterGui(const std::vector<unsigned char>&,std::vector<unsigned char>&,std::string&) {assert(false);return false;}

struct FontFixture {
    std::array<float,12> info{};
    std::array<unsigned char,0xD0> texture{};
    FontFixture(const std::string& name) {
        texture.fill(0xA5);
        float* pointer=info.data();std::memcpy(texture.data()+0x38,&pointer,sizeof pointer);
        std::memset(texture.data()+0x98,0,16);std::memcpy(texture.data()+0x98,name.data(),name.size());
        for(unsigned i=0;i<12;++i) {unsigned value=0x12010000+i;std::memcpy(&info[i],&value,4);}
    }
    void loaded() {KmrpFontMetricsLoadedK1(texture.data());}
};
bool CloseEnough(float a,float b) {return std::fabs(a-b)<=(std::max)(1e-6f,std::fabs(b)*2e-6f);}

// OverrideFontFitted (2026-11-08) on the fixture Test-OverrideFontMetrics.py puts in the
// Override folder beside this program: dialogfont10x10 a KMRP HD atlas (1024 square,
// fontheight 0.6, as the KMRP Font Converter writes), fnt_console the same with a .tpc,
// dialogfont12x16 a .tga without .txi, dialogfont16x16 a 24-bit .tga, fnt_credits none.
std::string Text(const std::wstring& path) {std::vector<unsigned char> b;assert(Read(path,b));return std::string(b.begin(),b.end());}
double Field(const std::string& text,const char* key) {
    const auto at=text.find(std::string("\n")+key+" ");assert(at!=std::string::npos);
    return std::atof(text.c_str()+at+std::strlen(key)+2);
}
unsigned long long AlphaSum(const std::vector<unsigned char>& tga) {
    const size_t pixels=static_cast<size_t>(tga[12]|(tga[13]<<8))*(tga[14]|(tga[15]<<8));
    unsigned long long sum=0;for(size_t i=0;i<pixels;++i)sum+=tga[18+tga[0]+i*4+3];return sum;
}
void TestOverrideFit() {
    wchar_t exe[MAX_PATH];GetModuleFileNameW(nullptr,exe,MAX_PATH);*wcsrchr(exe,L'\\')=0;
    const std::wstring folder(exe),source=folder+L"\\override\\dialogfont10x10";
    root=folder+L"\\cache";CreateDirectoryW(root.c_str(),nullptr);CreateDirectoryW((root+L"\\fonts").c_str(),nullptr);
    // Override as listed once (Modded Font, 2026-11-08): which names it has, which of them KMRP
    // can show itself (a .tga with its .txi and no .tpc), and a number for the set.
    const std::uint64_t set=OverrideFontSet();
    assert(set && overrideAtStart[0] && overrideAtStart[8] && overrideAtStart[3] && overrideAtStart[4] && !overrideAtStart[9]);
    assert(OverridePair(0) && !OverridePair(8) && !OverridePair(3) && OverridePair(4) && !OverridePair(9));
    std::wstring txi,tga,txi2,tga2;
    assert(OverrideFontFitted(0,0.24f,txi,tga));                 // factor 0.4
    std::vector<unsigned char> in,out;assert(Read(source+L".tga",in)&&Read(tga,out));
    assert(out[2]==2 && out[16]==32 && out[17]==in[17]);
    assert((out[12]|(out[13]<<8))==410 && (out[14]|(out[15]<<8))==410);
    // Coverage kept: each new texel the area average of the old ones it covers.
    const double kept=static_cast<double>(AlphaSum(out))/(AlphaSum(in)*0.4*0.4);
    assert(kept>0.99 && kept<1.01);
    const std::string before=Text(source+L".txi"),after=Text(txi);
    assert(std::fabs(Field(after,"fontheight")-0.24)<1e-6 && std::fabs(Field(after,"texturewidth")-4.10)<1e-6);
    assert(std::fabs(Field(after,"baselineheight")-Field(before,"baselineheight")*0.4)<1e-5);
    assert(before.substr(before.find("upperleftcoords"))==after.substr(after.find("upperleftcoords")));   // UVs untouched
    // Made once: a second call finds the same copy and writes nothing.
    WIN32_FILE_ATTRIBUTE_DATA first,second;GetFileAttributesExW(tga.c_str(),GetFileExInfoStandard,&first);
    Sleep(20);assert(OverrideFontFitted(0,0.24f,txi2,tga2) && txi2==txi && tga2==tga);
    GetFileAttributesExW(tga.c_str(),GetFileExInfoStandard,&second);
    assert(!CompareFileTime(&first.ftLastWriteTime,&second.ftLastWriteTime));
    // Another size is another copy; the mod's own files are never written.
    assert(OverrideFontFitted(0,0.36f,txi2,tga2) && tga2!=tga);
    std::vector<unsigned char> again;assert(Read(source+L".tga",again) && again==in && Text(source+L".txi")==before);
    // A changed Override file is a new copy.
    HANDLE h=CreateFileW((source+L".txi").c_str(),FILE_WRITE_ATTRIBUTES,FILE_SHARE_READ,nullptr,OPEN_EXISTING,0,nullptr);
    FILETIME later=first.ftLastWriteTime;later.dwHighDateTime+=1;assert(SetFileTime(h,nullptr,nullptr,&later));CloseHandle(h);
    assert(OverrideFontFitted(0,0.24f,txi2,tga2) && tga2!=tga);
    // Left to Override, as before: not larger than drawn, a .tpc, no .txi, not 32-bit, none.
    assert(!OverrideFontFitted(0,0.6f,txi2,tga2) && !OverrideFontFitted(0,0.8f,txi2,tga2));
    assert(!OverrideFontFitted(8,0.24f,txi2,tga2));   // fnt_console
    assert(!OverrideFontFitted(3,0.24f,txi2,tga2));   // dialogfont12x16
    assert(!OverrideFontFitted(4,0.24f,txi2,tga2));   // dialogfont16x16
    assert(!OverrideFontFitted(9,0.24f,txi2,tga2));   // fnt_credits
    assert(OverrideFontSet()!=set);   // a changed file is a new set: Modded Font is chosen again
    std::cout<<"PASS: Override font fitted to its size (1024 to 410, coverage "<<kept<<"), UVs and the mod's files untouched, made once, a new copy for a new size or file; .tpc, no .txi, 24-bit, not larger and absent left to Override; Override's font names listed, the pairs KMRP can show, a new set number for a changed file.\n";
}

int main(int argc,char** argv) {
    assert(argc==2);std::ifstream input(argv[1]);assert(input);
    TestOverrideFit();
    for(const char* font:fontNames)assert(KmrpRuntimeIsFontK1(font));
    assert(KmrpRuntimeIsFontK1("FNT_CONSOLE"));
    assert(!KmrpRuntimeIsFontK1(nullptr) && !KmrpRuntimeIsFontK1("") && !KmrpRuntimeIsFontK1("NormCubeMap"));
    const int expectedGroups[]={2,2,2,0,0,0,0,0,3,1,1,1,1,1,1,1,1,0};
    std::map<std::string,int> groupsByName;
    for(unsigned i=0;i<18;++i){assert(KmrpTextOptions::FontGroup(fontNames[i])==expectedGroups[i]);groupsByName[fontNames[i]]=expectedGroups[i];}
    std::string name;float target,shared;int screenHeight;std::array<float,5> metrics;unsigned cases=0;
    while(input>>name>>target>>metrics[0]>>metrics[1]>>metrics[2]>>metrics[3]>>metrics[4]>>screenHeight>>shared) {
        assert(FontTargetHeight(shared,screenHeight)==target);
        for(int selectedPercent:{25,50,75,100,-1}) for(float translationSize:{1.0f,0.8f}) {
            testGrouped=selectedPercent<0;
            const int sizePercent=testGrouped?mixedSizes[groupsByName.at(name)]:selectedPercent;
            testTextPercent=sizePercent;
            const float sizedTarget=target*(sizePercent/50.0f);
            FontFixture font(name);
            for(unsigned i=0;i<5;++i)font.info[i+1]=metrics[i]*translationSize;
            const auto original=font.info;const auto texture=font.texture;
            overrideFontHeights.clear();overrideFontHeights[name]=target;
            // This newly parsed texture is not registered in any global array.
            // A caller's first measurement must already see the target size.
            font.loaded();
            const float factor=sizedTarget/original[1];
            for(unsigned i=1;i<=5;++i)assert(CloseEnough(font.info[i],original[i]*factor));
            assert(font.info[1]==sizedTarget);
            assert(!std::memcmp(font.info.data(),original.data(),4));
            assert(!std::memcmp(font.info.data()+6,original.data()+6,6*4));
            assert(font.texture==texture);
            const auto adjusted=font.info;font.loaded();assert(font.info==adjusted);
            // A mode switch reparses the source TXI, then finalizes that new
            // target before the next caller; switching back must not compound.
            for(float next:{target*1.25f,target*0.75f,target}) {
                font.info=original;overrideFontHeights[name]=next;font.loaded();
                assert(font.info[1]==next*(sizePercent/50.0f));
                for(unsigned i=1;i<=5;++i)assert(CloseEnough(font.info[i],original[i]*next*(sizePercent/50.0f)/original[1]));
            }
            // Unknown/unoverridden fonts are completely unchanged.
            overrideFontHeights.clear();font.info=original;font.loaded();assert(font.info==original);
            ++cases;
        }
    }
    assert(cases>=18*4*2);
    testGrouped=false;testTextPercent=50;
    FontFixture font("FNT_D16X16B");font.info[1]=0.19f;overrideFontHeights["fnt_d16x16b"]=0.27f;
    font.loaded();assert(font.info[1]==0.27f); // native names are case-insensitive
    for(float invalid:{0.0f,-1.0f,std::numeric_limits<float>::quiet_NaN(),std::numeric_limits<float>::infinity()}) {
        font.info[1]=invalid;const auto before=font.info;font.loaded();assert(!std::memcmp(font.info.data(),before.data(),sizeof before));
    }
    font.info[1]=0.19f;overrideFontHeights["fnt_d16x16b"]=100.0f;
    const auto before=font.info;font.loaded();assert(font.info==before); // unsupported ratios
    overrideFontHeights["fnt_d16x16b"]=0.27f;
    float* missing=nullptr;std::memcpy(font.texture.data()+0x38,&missing,sizeof missing);
    const auto texture=font.texture;font.loaded();assert(font.texture==texture && font.info==before);
    KmrpFontMetricsLoadedK1(nullptr);
    std::cout<<"PASS: "<<cases<<" original/translation font cases, including independently sized groups; first-use metrics, reload and mode round trip; no double scaling; UV/pointer/texture bytes preserved; absent/invalid guards.\n";
}
