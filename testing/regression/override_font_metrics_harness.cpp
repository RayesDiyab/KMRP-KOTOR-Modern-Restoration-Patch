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
int KmrpTextFontStyleK1() {return KmrpTextOptions::OldHd;}
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
int main(int argc,char** argv) {
    assert(argc==2);std::ifstream input(argv[1]);assert(input);
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
