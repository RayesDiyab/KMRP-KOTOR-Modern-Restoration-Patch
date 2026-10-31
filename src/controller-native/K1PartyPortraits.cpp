// Shared by KMRP's module (kmrp.dll) and the controller patch's (kmrp-controller.dll).
// Until 2026-10-31 this lived in K1NativeJoystick.cpp, which kmrp.dll then compiled whole, with
// the rest of the controller code, for it (issue 82, F1:
// docs/cleanup-1.6/F1-kmrp-without-controller-code.md).

// Each module finds the page's buttons its own way: KMRP's from its records of the panel's
// controls (CapturePartyRoster, K1RuntimeLayout.cpp, since 2026-11-01), the controller
// patch's by binding a probe per tag (CapturePartyRosterBindingsK1, K1NativeJoystick.cpp).
// Until 2026-11-01 only the controller patch did, so KMRP alone never repaired the
// portraits. With both, the second pass finds each portrait already filled and leaves it.

#include "K1PartyRosterState.h"
#include "K1EngineMemory.h"
#include "K1GuiControls.h"

#include <windows.h>
#include <cstring>

// UI repair for the released external roster's empty portrait labels. Query
// object IDs through its exported API (no mod-state offsets), then use the
// creature's native portrait getter rather than the base object's empty field.
void KmrpPartyPortraitsK1(void* panel)
{
    if(!KmrpPartyPagesBoundK1(panel))return;
    HMODULE roster=GetModuleHandleW(L"party-roster-limit-32-k1.dll");
    if(!roster)return;
    using NpcObject=DWORD(__cdecl*)(void*,const int*,const int*,const int*);
    auto objectId=reinterpret_cast<NpcObject>(GetProcAddress(roster,"GetNPCObject32"));
    using Selectability=int(__cdecl*)(void*,const int*);
    auto selectable=reinterpret_cast<Selectability>(GetProcAddress(roster,"GetNPCSelectability32"));
    if(!objectId || !selectable)return;
    // These are the supported K1 native getters, not addresses inside the mod.
    constexpr unsigned char creatureGetter[]={0x8B,0x81,0x74,0x0A,0x00,0x00};
    if(std::memcmp(reinterpret_cast<const void*>(0x004F8370),creatureGetter,sizeof creatureGetter))return;
    void* app=*reinterpret_cast<void**>(0x007A39FC);
    if(!IsReadableK1(app,12))return;
    void* server=*FieldAt<void*>(app,8);
    if(!IsReadableK1(server,8))return;
    using Party=void*(__thiscall*)(void*);
    void* party=EngineFn<Party>(0x004AEE70)(server);
    void** controls=*FieldAt<void**>(panel,K1_PANEL_CONTROL_ARRAY);
    const int count=*FieldAt<int>(panel,K1_PANEL_CONTROL_COUNT);
    if(!controls || count<=0 || count>512)return;
    for(int i=0;i<count;++i) {
        void* record=controls[i];
        if(!IsReadableK1(record,4) || *FieldAt<std::uintptr_t>(record,0)!=0x00756BB8 ||
           !IsReadableK1(record,0x454))continue;
        KmrpPresentPartyRecordK1(panel,record,
            [&](int slot) { return selectable(party,&slot)!=0; },
            [&](int slot,char (&portrait)[16]) {
                const int no=0;
                const DWORD id=objectId(party,&slot,&no,&no); // never create/recover a creature
                if(id==0x7F000000u)return false;
                using Creature=void*(__thiscall*)(void*,DWORD);
                void* creature=EngineFn<Creature>(0x004AE770)(server,id);
                if(!creature)return false;
                using Portrait=void*(__thiscall*)(void*,void*);
                EngineFn<Portrait>(0x004F8370)(creature,portrait);
                return portrait[0]!=0;
            },
            [](void* label,const char* portrait) {
                using Fill=void(__thiscall*)(void*,const void*,int);
                EngineFn<Fill>(0x00414C00)(static_cast<unsigned char*>(label)+0x70,portrait,0);
            });
    }
}
