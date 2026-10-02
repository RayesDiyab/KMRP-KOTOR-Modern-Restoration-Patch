// Executes the production layout with synthetic native wrapping and font objects.
#include "../../macos/patches/kmrp-layout/status_summary.cpp"
#include <cassert>
#include <cstring>
#include <cstdio>
using kmrp::At;
static char info[64], font[16], object[128], panel[0x2400], manager[256];
static uintptr_t fontvt[32], textvt[32], controlvt[8];
static char coords[256*12];
static void* controls[3];
static int wraps, threshold=482, minimumLines=1;
static char* GetInfo(void*) { return info; }
static void Wrap(void* o,int width) { ++wraps; At<int>(o,0x50)=width<16?0:(width<threshold?minimumLines+1:minimumLines); }
static void SetExtent(void* c,const int* r) {
    memcpy(static_cast<char*>(c)+8,r,16);
    if(c==panel+0x1220){memcpy(object+8,r,16);Wrap(object,r[2]);}
}
static void Setup(int width) {
    memset(panel,0,sizeof panel);memset(manager,0,sizeof manager);memset(object,0,sizeof object);
    kmrp::g_fit[0]={};wraps=0;
    fontvt[0x78/8]=(uintptr_t)GetInfo;At<uintptr_t>(font,0)=(uintptr_t)fontvt;
    At<float>(info,4)=0.27f;At<float>(info,12)=5.12f;At<float>(info,16)=0.005f;
    At<void*>(info,0x18)=coords;At<void*>(info,0x28)=coords;
    textvt[0xa0/8]=(uintptr_t)Wrap;At<uintptr_t>(object,0)=(uintptr_t)textvt;
    At<void*>(object,0x20)=font;At<const char*>(object,0x18)="Experience Points (XP) Received: 50";
    At<float>(object,0x58)=1;At<int>(object,0x50)=2;At<int>(object,0x10)=477;
    controlvt[2]=(uintptr_t)SetExtent;At<uintptr_t>(panel,0)=(uintptr_t)controlvt;
    for(int i=0;i<3;i++){controls[i]=panel+(i==0?0x3c8:i==1?0x1220:0x2078);At<uintptr_t>(controls[i],0)=(uintptr_t)controlvt;At<int>(controls[i],0x74)=i;}
    At<unsigned char>(controls[0],0x68)=2;At<void*>(controls[1],0x128)=object;
    At<void*>(panel,0x30)=controls;At<int>(panel,0x38)=3;
    At<short>(manager,0xa4)=width;At<short>(manager,0xa6)=1200;
}
int main(){
    Setup(1920);assert(kmrp::Layout(manager,panel,nullptr));assert(At<int>(controls[1],16)==482);assert(At<int>(object,0x50)==1);
    int once=wraps;assert(kmrp::Layout(manager,panel,nullptr));assert(wraps==once); // no rewrap on unchanged frames
    Setup(400);assert(kmrp::Layout(manager,panel,nullptr));assert(At<int>(object,0x50)==2);assert(At<int>(controls[1],20)==55);assert(At<int>(panel,16)<=400);
    assert(At<int>(controls[2],12)>At<int>(controls[1],12)+At<int>(controls[1],20));
    minimumLines=2;Setup(1920);assert(kmrp::Layout(manager,panel,nullptr));assert(At<int>(object,0x50)==2);assert(At<int>(controls[1],20)==55);
    static char hud[0xd200];
    void* desc=hud+0xce40;void* bg=hud+0xcfd8;void* hudControls[2]={desc,bg};
    At<void*>(hud,0x30)=hudControls;At<int>(hud,0x38)=2;
    for(int i=0;i<2;i++){At<uintptr_t>(hudControls[i],0)=(uintptr_t)controlvt;At<int>(hudControls[i],0x74)=i;}
    At<unsigned char>(desc,0x68)=2;At<void*>(desc,0x128)=object;
    const int baseline[4]={1617,1034,295,54};memcpy((char*)desc+8,baseline,16);memcpy((char*)bg+8,baseline,16);
    At<int>(object,0x50)=2;kmrp::FitActionDescription(manager,hud);
    assert(At<int>(desc,20)==55);assert(At<int>(desc,12)==1033);assert(At<int>(bg,20)==55);
    At<int>(object,0x50)=3;kmrp::FitActionDescription(manager,hud);
    assert(At<int>(desc,20)==82);assert(At<int>(desc,12)+At<int>(desc,20)==1088);
    At<int>(object,0x50)=1;kmrp::FitActionDescription(manager,hud);
    assert(At<int>(desc,20)==54);assert(At<int>(desc,12)==1034);assert(At<int>(bg,20)==54);
    puts("PASS native width, fractional height, capped multiline, explicit multiline, cached unchanged frames, dynamic HUD grow/shrink/anchor");
}
