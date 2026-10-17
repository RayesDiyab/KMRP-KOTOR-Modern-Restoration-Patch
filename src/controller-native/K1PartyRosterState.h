#pragma once
#include <windows.h>
#include <cstdint>
#include <cstring>
#include <initializer_list>
#include <array>
#include <map>

// Read-only activation evidence from applied roster hooks. The released build
// also requires its loaded implementation/export; a config entry alone is not
// enough. This identifies availability, never the layout of native objects.
inline bool KmrpPartyRoster32ActiveK1()
{
    const auto base = reinterpret_cast<std::uintptr_t>(GetModuleHandleW(nullptr));
    if (!base) return false;
    const auto dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(base);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew <= 0 || dos->e_lfanew > 0x1000) return false;
    const auto nt = reinterpret_cast<const IMAGE_NT_HEADERS*>(base + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE || nt->FileHeader.Machine != IMAGE_FILE_MACHINE_I386 ||
        nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR32_MAGIC || nt->OptionalHeader.SizeOfImage < 0x2BFEFB) return false;
    unsigned first=0,second=0;
    std::memcpy(&first,reinterpret_cast<const void*>(base+0x22DE20),4);
    std::memcpy(&second,reinterpret_cast<const void*>(base+0x232E50),4);
    if (first==0xA194 && second==0xA194) return true;
    // Official 0.7.3 uses external view controls, leaving the panel stock-sized.
    // Require a loaded roster implementation AND its applied count/layout hooks.
    const HMODULE roster=GetModuleHandleW(L"party-roster-limit-32-k1.dll");
    return *reinterpret_cast<const unsigned char*>(base+0x16554C)==32 &&
        *reinterpret_cast<const unsigned char*>(base+0x1665DD)==32 &&
        *reinterpret_cast<const unsigned char*>(base+0x2BFEF6)==0xE9 &&
        roster && GetProcAddress(roster,"FinishPartySelectionLayout");
}

// IDs come from the native tag binder while the layout still exists. Never
// retain a control pointer after construction: resolve within this live panel's
// own ID array. This works with embedded and separately allocated view controls.
using KmrpPartyIdsK1 = std::array<int,5>; // OK, Add/Remove, Back, previous, next
inline std::map<void*,KmrpPartyIdsK1>& KmrpPartyBindingsK1()
{
    static std::map<void*,KmrpPartyIdsK1> bindings;
    return bindings;
}
inline const char* KmrpPartyTagK1(unsigned index)
{
    static const char* tags[]={"BTN_DONE","BTN_ACCEPT","BTN_BACK","BTN_PAGE_PREV","BTN_PAGE_NEXT"};
    return index<5?tags[index]:nullptr;
}
inline void* KmrpPartyControlK1(void* panel,unsigned index)
{
    const auto found=KmrpPartyBindingsK1().find(panel);
    if(found==KmrpPartyBindingsK1().end() || index>=5 || !panel ||
       *static_cast<const std::uintptr_t*>(panel)!=0x00756D28) return nullptr;
    auto bytes=static_cast<unsigned char*>(panel);
    void** controls=*reinterpret_cast<void***>(bytes+0x20);
    const int count=*reinterpret_cast<const int*>(bytes+0x24),id=found->second[index];
    if(!controls || count<=0 || count>512 || id<0 || id>=512) return nullptr;
    // KPM's external view removes/reinserts controls with DeleteAt/AddControl.
    // The ID is stable; its position in this compact render list is not.
    for(int i=0;i<count;++i) {
        auto control=static_cast<unsigned char*>(controls[i]);
        if(!control || *reinterpret_cast<const int*>(control+0x50)!=id)continue;
        if(*reinterpret_cast<const std::uintptr_t*>(control)!=0x0073E658 ||
           *reinterpret_cast<void**>(control+0x34)!=panel)continue;
        return control;
    }
    return nullptr;
}
inline bool KmrpPartyPagesBoundK1(void* panel)
{
    return KmrpPartyControlK1(panel,3) && KmrpPartyControlK1(panel,4);
}
inline void KmrpMirrorPartyPageFocusK1(void* panel)
{
    auto done=static_cast<unsigned char*>(KmrpPartyControlK1(panel,0));
    auto prev=static_cast<unsigned char*>(KmrpPartyControlK1(panel,3));
    auto next=static_cast<unsigned char*>(KmrpPartyControlK1(panel,4));
    if(!done || !prev || !next) return;
    const unsigned policy=*reinterpret_cast<const unsigned*>(done+0x44)&4u;
    for(auto button:{prev,next}) {
        auto& flags=*reinterpret_cast<unsigned*>(button+0x44);
        flags=(flags&~4u)|policy;
    }
}

// Presentation only, after the caller verifies this native record is readable.
// The release's base-object portrait getter can leave a valid creature's label
// empty. Populate that label through the caller's native creature getter.
template<class Selectable,class Portrait,class Fill>
inline void KmrpPresentPartyRecordK1(void* panel,void* record,Selectable selectable,Portrait portrait,Fill fill)
{
    auto bytes=static_cast<unsigned char*>(record);
    if(!bytes || *reinterpret_cast<const std::uintptr_t*>(bytes)!=0x00756BB8 ||
       *reinterpret_cast<void**>(bytes+0x34)!=panel ||
       *reinterpret_cast<void**>(bytes+0x58)!=record)return;
    const int slot=*reinterpret_cast<const int*>(bytes+0x450);
    const unsigned available=*reinterpret_cast<const unsigned*>(bytes+0x448)&1u;
    if(slot<0 || slot>=32)return;
    if(!available) {
        // Native SetSelected(0) hides the normal selection border. The release
        // overwrites it with alpha 1, exposing a white frame on missing NPCs.
        *reinterpret_cast<float*>(bytes+0x8C)=0.0f;
        // Keep the original crew's unavailable silhouettes. Extra empty slots
        // have no portrait and no action; their default white frame is noise.
        if(slot>=9)*reinterpret_cast<unsigned*>(bytes+0x44)&=~2u;
        return;
    }
    auto label=bytes+0x308; // native CSWGuiPartySelectionData::character_label
    if(*reinterpret_cast<const std::uintptr_t*>(label)!=0x0073E5B8 ||
       *reinterpret_cast<void**>(label+0x34)!=panel ||
       !(*reinterpret_cast<const unsigned*>(label+0x44)&2u))return;
    // Native OnPanelAdded dims portraits by selectability, independently of
    // selection. The released view incorrectly uses its selected-state bit.
    *reinterpret_cast<float*>(bytes+0x384)=selectable(slot)?1.0f:0.25f;
    if(label[0xB0])return;
    char resref[16]={};
    if(portrait(slot,resref) && resref[0])fill(label,resref);
}

void KmrpPartyPortraitsK1(void* panel);
