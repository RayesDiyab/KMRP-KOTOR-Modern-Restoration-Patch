#include <cstdint>
#include <cstddef>
#include <cstring>
#include <cstdio>
#include <vector>
#include <utility>
struct Texture { char unused[0x98]{}; char name[16]{}; };
struct Ref { std::uintptr_t vtable = 0x0073F0A8; unsigned unused[3]{}; Texture* texture = nullptr; unsigned last = 0; };
constexpr int K1_CLASS_MINIGAME = 1;
struct Stick { bool padPresent = true; int glyphFamily = 0; } g_stick;
bool inputPad = false, glyphLoads = true, loadReturnsNull = false;
int inputClass = 1, loads = 0, assignments = 0, queries = 0, demands = 0, finds = 0;
unsigned long nowTick = 1000;
unsigned long GetTickCount() { return nowTick; }
Texture originals[3]{}, glyphTextures[4]{};
Ref originalRefs[3]{}, glyphRefs[4]{};
std::vector<std::pair<std::uintptr_t, std::size_t>> readable;
template<typename T> void Allow(T& object) { readable.push_back({reinterpret_cast<std::uintptr_t>(&object), sizeof(object)}); }
bool LooksLikePointerK1(const void* p) { return reinterpret_cast<std::uintptr_t>(p) >= 0x10000; }
bool IsReadableK1(const void* p, std::size_t n) {
    ++queries; const auto at = reinterpret_cast<std::uintptr_t>(p);
    for (const auto& r : readable) if (at >= r.first && n <= r.second && at - r.first <= r.second - n) return true;
    return false;
}
template<typename T> T* FieldAt(void* p, std::size_t at) { return reinterpret_cast<T*>(static_cast<char*>(p) + at); }
template<std::size_t N> struct Blob { alignas(void*) char bytes[N]{}; };
Blob<0xA0> fakeInternal;
Blob<0x4C> fakeModule;
Blob<0x268> fakeArea;
Blob<0x84> race;
Blob<0x70> fakePlayer;
Blob<0x110> fakeVtable;
Blob<0x6C> gobs[5];
Blob<0x18> fakeModels[5];
Blob<0x48> parts[2];
struct Attached { void* gob; unsigned rotating = 1; } attached[5];
static_assert(sizeof(Attached) == 8, "The production attached-model stride is x86-specific");
void* activeInternal = &fakeInternal;
void* activePart = &parts[0];
void* materials[2] = { &originalRefs[0], &originalRefs[0] };
void* unrelatedMaterial = &originalRefs[0];
void* ClientInternalK1() { return activeInternal; }
int InputClassK1() { return inputClass; }
bool IsControllerInputActiveK1() { return inputPad; }
void* __cdecl Load(const char* name, const char*) {
    ++loads;
    if (loadReturnsNull) return nullptr;
    for (int i=0; i<4; ++i) if (std::strcmp(name, glyphTextures[i].name)==0) return &glyphRefs[i];
    return nullptr;
}
void* __fastcall Assign(void* to, void*, void* from) { ++assignments; *static_cast<void**>(to)=from; return to; }
unsigned long __cdecl Id(void*) { ++demands; return glyphLoads ? 1 : 0; }
void* __fastcall FindPart(void* gob, void*, const char* name) {
    ++finds;
    if (std::strcmp(name, "Plane14") != 0) return nullptr;
    for (int i=0;i<5;++i) if (gob==&gobs[i] && std::strcmp(FieldAt<char>(&fakeModels[i],8),"m17mg_camera")==0) return activePart;
    return nullptr;
}
template<typename T> T EngineFn(std::uintptr_t address) {
    if (address==0x00423A60) return reinterpret_cast<T>(&Load);
    if (address==0x00447FA0) return reinterpret_cast<T>(&Assign);
    if (address==0x00420BF0) return reinterpret_cast<T>(&Id);
    if (address==0x004402F0) return reinterpret_cast<T>(&FindPart);
    return nullptr;
}
// KMRP_PRODUCTION_PROMPT_HELPER

int checks=0;
#define CHECK(condition) do { ++checks; if (!(condition)) { std::printf("FAIL line %d: %s\n", __LINE__, #condition); return 1; } } while(0)
void CameraAt(int index) {
    for (int i=0;i<5;++i) std::strcpy(FieldAt<char>(&fakeModels[i],8),i==index?"m17mg_camera":"v_superbike");
    for (auto& part : parts) *FieldAt<void*>(&part,0x40)=&gobs[index];
}
int main() {
    Allow(fakeInternal);Allow(fakeModule);Allow(fakeArea);Allow(race);Allow(fakePlayer);Allow(fakeVtable);
    Allow(gobs);Allow(fakeModels);Allow(parts);Allow(attached);Allow(materials);Allow(originalRefs);Allow(originals);Allow(glyphRefs);Allow(glyphTextures);
    std::strcpy(originals[0].name,"abutton");std::strcpy(originals[1].name,"other");std::strcpy(originals[2].name,"abutton_custom");
    for(int i=0;i<3;++i) originalRefs[i].texture=&originals[i];
    const char letters[]="psnd";
    for(int i=0;i<4;++i) { std::strcpy(glyphTextures[i].name,"kmrpp_swoop");glyphTextures[i].name[3]=letters[i];glyphRefs[i].texture=&glyphTextures[i]; }
    *FieldAt<void*>(&fakeInternal,0x18)=&fakeModule; *FieldAt<void*>(&fakeModule,0x48)=&fakeArea;
    *FieldAt<void*>(&fakeArea,0x264)=&race; *FieldAt<int>(&race,0x80)=1;
    *FieldAt<void*>(&race,0x24)=&fakePlayer; *FieldAt<void*>(&fakePlayer,0x68)=attached; *FieldAt<int>(&fakePlayer,0x6C)=4;
    *FieldAt<std::uintptr_t>(&fakeVtable,0x10C)=0x004402F0;
    for(int i=0;i<5;++i) { attached[i].gob=&gobs[i]; *FieldAt<void*>(&gobs[i],0)=&fakeVtable; *FieldAt<void*>(&gobs[i],0x58)=&fakeModels[i]; }
    for(int i=0;i<2;++i) *FieldAt<void*>(&parts[i],0x44)=&materials[i];
    // Real tracks place the camera at different attached-model indices.
    CameraAt(1);
    UpdateSwoopPromptK1();CHECK(materials[0]==&originalRefs[0] && assignments==1);
    inputPad=true;loadReturnsNull=true;g_stick.glyphFamily=1;
    UpdateSwoopPromptK1();CHECK(materials[0]==&originalRefs[0]);const int failedLoads=loads;
    UpdateSwoopPromptK1();CHECK(loads==failedLoads);loadReturnsNull=false;nowTick+=500;
    for(int i=0;i<4;++i) {
        g_stick.glyphFamily=i;UpdateSwoopPromptK1();CHECK(materials[0]==&glyphRefs[i]);
        const int a=assignments,d=demands,l=loads,f=finds,q=queries;
        for(int frame=0;frame<100;++frame) UpdateSwoopPromptK1();
        CHECK(assignments==a && demands==d && loads==l);
        CHECK(finds-f==100 && queries-q<=2200);
        inputPad=false;UpdateSwoopPromptK1();CHECK(materials[0]==&originalRefs[0]);inputPad=true;
    }
    CHECK(unrelatedMaterial==&originalRefs[0]);
    for(int count=4;count<=5;++count) for(int index=0;index<count;++index) {
        *FieldAt<int>(&fakePlayer,0x6C)=count;CameraAt(index);materials[0]=&originalRefs[0];
        UpdateSwoopPromptK1();CHECK(materials[0]==&glyphRefs[3]);
    }
    // A fresh Part/material on the same Gob must be followed immediately.
    activePart=&parts[1];materials[1]=&originalRefs[0];UpdateSwoopPromptK1();CHECK(materials[1]==&glyphRefs[3]);
    materials[0]=&originalRefs[2];inputPad=false;UpdateSwoopPromptK1();CHECK(materials[1]==&originalRefs[0]);CHECK(materials[0]==&originalRefs[2]);
    inputPad=true;UpdateSwoopPromptK1();g_stick.padPresent=false;UpdateSwoopPromptK1();CHECK(materials[1]==&originalRefs[0]);g_stick.padPresent=true;
    UpdateSwoopPromptK1();inputClass=2;UpdateSwoopPromptK1();CHECK(materials[1]==&originalRefs[0]);inputClass=1;
    // No weak target survives a vanished part or race; removed storage is untouched.
    activePart=nullptr;UpdateSwoopPromptK1();CHECK(materials[1]==&originalRefs[0]);activePart=&parts[1];
    const int before=finds;*FieldAt<void*>(&fakeArea,0x264)=nullptr;UpdateSwoopPromptK1();CHECK(finds==before);*FieldAt<void*>(&fakeArea,0x264)=&race;
    *FieldAt<int>(&race,0x80)=2;UpdateSwoopPromptK1();CHECK(finds==before);*FieldAt<int>(&race,0x80)=1;
    *FieldAt<int>(&fakePlayer,0x6C)=65;UpdateSwoopPromptK1();CHECK(finds==before);*FieldAt<int>(&fakePlayer,0x6C)=5;
    activeInternal=nullptr;UpdateSwoopPromptK1();CHECK(finds==before);activeInternal=&fakeInternal;
    *FieldAt<void*>(&parts[1],0x40)=&gobs[0];UpdateSwoopPromptK1();CHECK(materials[1]==&originalRefs[0]);CameraAt(4);
    materials[1]=&originalRefs[1];UpdateSwoopPromptK1();CHECK(materials[1]==&originalRefs[1]);
    materials[1]=&originalRefs[2];UpdateSwoopPromptK1();CHECK(materials[1]==&originalRefs[2]);
    materials[1]=&originalRefs[0];originalRefs[0].vtable=0;UpdateSwoopPromptK1();CHECK(materials[1]==&glyphRefs[3]); // retained original identity remains valid
    originalRefs[0].vtable=0x0073F0A8;
    // A failed family demand restores Space and throttles retries.
    inputPad=false;UpdateSwoopPromptK1();inputPad=true;glyphLoads=false;g_stick.glyphFamily=0;
    UpdateSwoopPromptK1();CHECK(materials[1]==&originalRefs[0]);const int d=demands;
    for(int i=0;i<10;++i) UpdateSwoopPromptK1();CHECK(demands==d);
    glyphLoads=true;nowTick+=500;g_stick.glyphFamily=99;UpdateSwoopPromptK1();CHECK(materials[1]==&glyphRefs[0]);
    // Thousands of foreign abutton materials are unreachable by design.
    void* foreign[5000];for(auto& ref:foreign)ref=&originalRefs[0];UpdateSwoopPromptK1();
    bool foreignUntouched=true;for(auto ref:foreign) foreignUntouched &= ref==&originalRefs[0];CHECK(foreignUntouched);
    std::printf("PASS: %d direct race/model prompt checks; live target rebuild/unload, all families and activity transitions, no steady texture work.\n",checks);
}
