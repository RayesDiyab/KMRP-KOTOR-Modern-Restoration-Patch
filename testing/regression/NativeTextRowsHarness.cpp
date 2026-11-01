// Native row adapter behavior without a running game. Stubs reproduce verified
// restore/dirty/height side effects, not native rendering or unknown row classes.
#define KMRP_TEXT_LAYOUT_TEST
#include "../../src/controller-native/K1TextRows.cpp"
#include <cassert>
#include <cstdlib>
#include <cstring>
#include <iostream>
namespace {
unsigned generation = 1;
int measured = 0, organized = 0, bounded = 0;
int nativeIcon = 84;
struct Object { alignas(4) unsigned char data[0x600]{}; void* ptr() { return data; } };
void __fastcall Set(void* p, void*, const Rect* r) {
    At<Rect>(p, 4) = *r;
    Kind k = Type(p);
    if (k.text && !k.frame) { Rect inner = *r; inner.top += 4; inner.height -= 8; At<Rect>(Part(p,k.text),4) = inner; }
    if (k.frame) {
        // As the entry classes' SetExtent (0x6B5270/0x6C2650/0x6AB8E0): border,
        // highlight and text right of the icon, at the ICON's fixed height, whatever
        // height the row is given.
        const Rect frame{r->left+nativeIcon,r->top,r->width-nativeIcon,nativeIcon};
        At<Rect>(Part(p,k.frame),4)=frame; At<Rect>(Part(p,k.hilight),4)=frame;
        for(unsigned part=0;part<3;++part)At<Rect>(Part(p,k.icon+part*0x74),4)={r->left,r->top,nativeIcon,nativeIcon};
        At<Rect>(Part(p,k.text),4)={frame.left,frame.top+4,frame.width,frame.height-8};
    }
    if (k.chart) {
        // As CSWGuiSkillFlow::SetExtent (0x6CCE30): three cells as tall as the row,
        // each icon drawn at its 64 px texture centred (draw style 1), and two
        // 32 px arrows centred between them.
        const int h=r->height, lefts[3]={r->left,r->left+(r->width-h)/2,r->left+r->width-h};
        for(int i=0;i<3;++i){
            void* image=Part(p,0x5C+i*0x128+0x74); const Rect cell{lefts[i],r->top,h,h};
            At<Rect>(Part(p,0x5C+i*0x128),4)=cell; At<Rect>(image,4)=cell;
            At<Rect>(image,0x14)={cell.left+(h-64)/2,cell.top+(h-64)/2,64,64};
        }
        const int arrowTop=(h-32)/2+r->top;
        At<Rect>(Part(p,0x3D4),4)=At<Rect>(Part(p,0x3D4),0x14)={(r->width+h)/4-16+r->left,arrowTop,32,32};
        At<Rect>(Part(p,0x428),4)=At<Rect>(Part(p,0x428),0x14)={(r->width*3-h)/4-16+r->left,arrowTop,32,32};
    }
    if (k.amount) {
        Rect icon{r->left,r->top,nativeIcon,nativeIcon};
        At<Rect>(Part(p,k.amount == 0x334 ? 0x1D8 : 0x1C8),4)=icon;
        const int countWidth=static_cast<int>(std::lround(nativeIcon*32.0/84));
        const int countHeight=static_cast<int>(std::lround(nativeIcon*28.0/84));
        At<Rect>(Part(p,k.amount),4)={icon.left+nativeIcon-countWidth,icon.top+nativeIcon-countHeight,countWidth,countHeight};
        At<float>(Part(p,k.amount),0x64) = -1; // native geometry reset marker
    }
}
int __fastcall Pages(void* p, void*) {
    return std::max(1, static_cast<int>(std::ceil((At<int>(p,0x2B4)-At<int>(p,0x298))/24.0))+1);
}
void __fastcall Oversized(void* p, void*) {
    auto rows=At<void**>(p,0x29C);Rect r=At<Rect>(rows[0],4);
    r.top=-24*(At<short>(p,0x2C2)-1);Set(rows[0],nullptr,&r);
}
void __fastcall Arrange(void* p, void*) {
    ++organized;
    const int n = At<int>(p,0x2A0); auto rows = At<void**>(p,0x29C);
    auto saved = At<Rect*>(p,0x2A8); auto& flags = At<unsigned>(p,0x2BC);
    int maxHeight = 1;
    if (flags & 8) {
        At<short>(p,0x2C8) = 0;
        for (int i=0;i<n;++i) {
            if (!(flags&0x100)) Set(rows[i],nullptr,&saved[i]);
            maxHeight=std::max(maxHeight,At<Rect>(rows[i],4).height);
        }
        At<int>(p,0x2B4)=maxHeight; flags&=~8u;
    }
    int top=0;
    for (int i=0;i<n;++i) {
        Rect r=At<Rect>(rows[i],4); r.top=top;
        if (!(flags&0x100)) r.height=At<int>(p,0x2B4);
        Set(rows[i],nullptr,&r); top+=r.height;
    }
    At<short>(p,0x2C4)=static_cast<short>(std::max(1,At<int>(p,0x298)/At<int>(p,0x2B4)));
    if(!(flags&0x100) && At<int>(p,0x2B4)>At<int>(p,0x298))Oversized(p,nullptr);
}
void Init(Object& p, std::uintptr_t vt, int height, int natural) {
    std::memset(p.data,0,sizeof p.data);
    At<std::uintptr_t>(p.ptr(),0)=vt; At<Rect>(p.ptr(),4)={0,0,400,height};
    Kind k=Type(p.ptr());
    if(k.text) {At<Rect>(Part(p.ptr(),k.text),4)={0,4,300,height-8}; At<int>(Part(p.ptr(),k.text),0x60)=natural; At<void*>(Part(p.ptr(),k.text),0x14)=nullptr;At<int>(Part(p.ptr(),k.text),0x5C)=0;}
    if(k.amount) {
        Set(p.ptr(),nullptr,&At<Rect>(p.ptr(),4));
        At<float>(Part(p.ptr(),k.amount),0x54)=48; At<float>(Part(p.ptr(),k.amount),0x58)=47.04f;
    }
}
void InitList(Object& p, void** rows, Rect* saved, int count, bool unequal) {
    At<std::uintptr_t>(p.ptr(),0)=0x73E840;At<Rect>(p.ptr(),4)={0,0,500,200};
    At<void**>(p.ptr(),0x29C)=rows;At<int>(p.ptr(),0x2A0)=count;
    At<Rect*>(p.ptr(),0x2A8)=saved;At<int>(p.ptr(),0x2AC)=count;
    At<int>(p.ptr(),0x298)=200;At<unsigned>(p.ptr(),0x2BC)=unequal?0x100:0;
    At<short>(p.ptr(),0x2C6)=2; At<short>(p.ptr(),0x2C8)=1;
}
}
void* KmrpTextRowsTestFunctionK1(std::uintptr_t a) {
    if (a==0x41B140) return reinterpret_cast<void*>(&Arrange);
    if (a==0x4182B0) return reinterpret_cast<void*>(&Pages);
    if (a==0x41A2D0) return reinterpret_cast<void*>(&Oversized);
    // Adapter reads native vtable entries, so test Type stays native while real
    // hardcoded vtables are mapped below by the test seam in Extent.
    if(a==0x123456) return reinterpret_cast<void*>(&Set);
    return reinterpret_cast<void*>(&Set);
}
void KmrpTextFlowK1(void* p) { At<float>(p,0x64)=1; }
void KmrpTextBoundedK1(void* p) {
    ++bounded; const Rect r=At<Rect>(p,4);
    const double line=At<float>(p,0x58);
    At<float>(p,0x64)=line>0?static_cast<float>(std::min(1.0,r.height/line)):1;
}
int KmrpTextNaturalHeightK1(void* p) {
    ++measured;
    void* text=At<void*>(p,0x14);
    if(text && At<char*>(text,0x14)[0]=='W')return 120;
    if(At<int>(p,0x5C)==1)return At<Rect>(p,4).width<350?120:95;
    return At<int>(p,0x60);
}
double KmrpTextNaturalWidthK1(void* p) { return At<float>(p,0x54); }
double KmrpTextNaturalLineHeightK1(void* p) { return At<float>(p,0x58); }
unsigned KmrpTextLayoutGenerationK1() { return generation; }
int textPercent = 50;
int KmrpTextSizePercentK1() { return textPercent; }
// The Icon Size slider, as far as a row sees it: 40 px in the box it is given.
bool skillOwned = false;
int skillSized = 0;
bool KmrpSkillIconOwnedK1() { return skillOwned; }
void KmrpSizeSkillIconK1(void* icon, const void* cell) {
    ++skillSized;
    const Rect box = *static_cast<const Rect*>(cell);
    At<unsigned>(icon, 0x30) = (At<unsigned>(icon, 0x30) & ~3u) | 2u;
    At<Rect>(icon, 4) = {box.left + (box.width - 40) / 2, box.top + (box.height - 40) / 2, 40, 40};
}
int main() {
    Object a,b,c,list;
    Init(a,0x7568F8,84,95); Init(b,0x756850,84,30); Init(c,0x757108,84,48);
    void* rows[]={a.ptr(),b.ptr(),c.ptr()}; Rect saved[3];
    for(int i=0;i<3;++i)saved[i]=At<Rect>(rows[i],4);
    InitList(list,rows,saved,3,false);
    KmrpTextRowsK1(list.ptr());
    assert(saved[0].height==103 && saved[1].height==84);
    assert(At<int>(list.ptr(),0x2B4)==103 && At<short>(list.ptr(),0x2C8)==1);
    assert(At<short>(list.ptr(),0x2C6)==2 && bounded==3);
    // The entry classes keep border/highlight/text at the icon's height; the grown
    // row's text box must reach the row's bottom, or a two-line name loses a line.
    assert(At<Rect>(Part(a.ptr(),0x6C),4).height==103 && At<Rect>(Part(a.ptr(),0xE0),4).height==103);
    assert(At<Rect>(Part(a.ptr(),0x154),4).height==95);
    // A fixed-height list lays every row out at the tallest one's height (as the
    // inventory does in play), so a one-line row's box spans its row as well.
    assert(At<Rect>(b.ptr(),4).height==103 && At<Rect>(Part(b.ptr(),0x154),4).height==95);
    // A native layout pass (scrolling) resets the box, and the counter with it;
    // the next draw restores both.
    {
        Rect same=At<Rect>(a.ptr(),4); Set(a.ptr(),nullptr,&same);
        assert(At<Rect>(Part(a.ptr(),0x154),4).height==76);
        KmrpTextRowsK1(list.ptr());
        assert(At<Rect>(Part(a.ptr(),0x154),4).height==95 && At<Rect>(Part(a.ptr(),0x6C),4).height==103);
        assert(At<Rect>(Part(a.ptr(),0xE0),4).height==103 && At<Rect>(a.ptr(),4).height==103);
    }
    // At the size before text options the icon keeps its native square, centred.
    assert(At<Rect>(Part(a.ptr(),0x1C8),4).width==84 && At<Rect>(Part(a.ptr(),0x1C8),4).top==9);
    // Larger text: the same icon art drawn larger, x1.3 at 65%, in all three of its
    // borders. Rows grow to hold it; text and frame start right of it; the counter
    // keeps to the icon's corner. Back at 50% everything returns.
    {
        textPercent=65;++generation;KmrpTextRowsK1(list.ptr());
        const Rect icon=At<Rect>(Part(a.ptr(),0x1C8),4);
        assert(icon.width==109 && icon.height==109 && icon.left==0);
        for(unsigned part=1;part<3;++part)assert(At<Rect>(Part(a.ptr(),0x1C8+part*0x74),4).width==109);
        // The frames' fill stretches in the larger box instead of tiling.
        for(unsigned part=0;part<3;++part)assert((At<unsigned>(Part(a.ptr(),0x1C8+part*0x74),0x30)&3)==2);
        assert(At<Rect>(Part(c.ptr(),0x1D8),4).width==109);
        assert(At<Rect>(a.ptr(),4).height==109 && saved[0].height==109);
        const Rect frame=At<Rect>(Part(a.ptr(),0x6C),4), text=At<Rect>(Part(a.ptr(),0x154),4);
        assert(frame.left==109 && frame.width==400-109 && frame.height==109);
        assert(text.left==109 && text.width==400-109 && text.top==frame.top+4 && text.height==109-8);
        // A box the size of its digits, its bottom-right corner at 52/56 across (101) and
        // 54/56 down (105) the icon.
        const Rect count=At<Rect>(Part(a.ptr(),0x324),4);
        assert(count.width==48 && count.height==48 && count.left==53 && count.top==57);
        textPercent=50;++generation;KmrpTextRowsK1(list.ptr());
        assert(At<Rect>(Part(a.ptr(),0x1C8),4).width==84 && At<Rect>(a.ptr(),4).height==103);
        assert(At<Rect>(Part(a.ptr(),0x154),4).left==84 && At<Rect>(Part(a.ptr(),0x154),4).height==95);
        for(unsigned part=0;part<3;++part)assert((At<unsigned>(Part(a.ptr(),0x1C8+part*0x74),0x30)&3)==0);
    }
    // Back at 50%: the 48 px line is capped at half the 84 px icon, in its corner.
    assert(At<Rect>(Part(a.ptr(),0x324),4).left==36 && At<Rect>(Part(a.ptr(),0x324),4).top==48);
    assert(At<Rect>(Part(a.ptr(),0x324),4).width==42 && At<Rect>(Part(a.ptr(),0x324),4).height==42);
    assert(std::fabs(At<float>(Part(a.ptr(),0x324),0x64)-42.0f/47.04f)<1e-4f); // glyphs fitted to the cap
    int before=measured; KmrpTextRowsK1(list.ptr()); assert(measured==before);
    // Same CExoString buffer/length/line count, changed content must invalidate.
    Object internal; char reusedText[]="A";
    At<std::uintptr_t>(internal.ptr(),0)=0x741878; At<char*>(internal.ptr(),0x14)=reusedText;
    At<void*>(Part(a.ptr(),0x154),0x14)=internal.ptr();
    KmrpTextRowsK1(list.ptr()); before=measured;
    reusedText[0]='W'; KmrpTextRowsK1(list.ptr());
    assert(measured>before && saved[0].height==128);
    At<void*>(Part(a.ptr(),0x154),0x14)=nullptr;
    // Native item relayout resets the count box, even with unchanged font size.
    Set(a.ptr(),nullptr,&At<Rect>(a.ptr(),4)); KmrpTextRowsK1(list.ptr());
    assert(At<Rect>(Part(a.ptr(),0x324),4).height==42 && At<Rect>(Part(a.ptr(),0x324),4).top==48);
    // A smaller font: a smaller box in the same corner (right 78, bottom 90).
    At<float>(Part(a.ptr(),0x324),0x54)=20;At<float>(Part(a.ptr(),0x324),0x58)=24;++generation;
    KmrpTextRowsK1(list.ptr());
    assert(At<Rect>(Part(a.ptr(),0x324),4).width==20 && At<Rect>(Part(a.ptr(),0x324),4).height==24);
    assert(At<Rect>(Part(a.ptr(),0x324),4).left==58 && At<Rect>(Part(a.ptr(),0x324),4).top==66);
    // Font larger than the icon is capped at half the live icon each way, still
    // in its corner, then fitted locally.
    At<float>(Part(a.ptr(),0x324),0x54)=120;At<float>(Part(a.ptr(),0x324),0x58)=100;++generation;
    KmrpTextRowsK1(list.ptr());
    assert(At<Rect>(Part(a.ptr(),0x324),4).width==42 && At<Rect>(Part(a.ptr(),0x324),4).height==42);
    assert(At<float>(Part(a.ptr(),0x324),0x64)<1);

    // A GUI width-only reflow must retain the original minimum when shrinking.
    At<Rect>(a.ptr(),4).width -= 20;
    At<int>(Part(a.ptr(),0x154),0x60)=24; ++generation;
    KmrpTextRowsK1(list.ptr());assert(saved[0].height==84 && At<int>(list.ptr(),0x2B4)==84);
    KmrpTextRowsForgetK1(list.ptr());
    Init(a,0x73E5B8,47,95);Init(b,0x73E8E8,47,130);
    InitList(list,rows,saved,2,true);KmrpTextRowsK1(list.ptr());
    assert((At<unsigned>(list.ptr(),0x2BC)&0x100)!=0);
    assert(At<Rect>(a.ptr(),4).height==103 && At<Rect>(b.ptr(),4).height==138);
    At<int>(Part(a.ptr(),0xD0),0x60)=24;At<int>(Part(b.ptr(),0xD0),0x60)=30;++generation;
    KmrpTextRowsK1(list.ptr());assert(At<Rect>(a.ptr(),4).height==32 && At<Rect>(b.ptr(),4).height==38);
    KmrpTextRowsForgetK1(a.ptr()); KmrpTextRowsForgetK1(list.ptr());
    // Unknown row subclasses are left entirely to the native layout contract.
    Init(c,0x123450,88,0); void* unknown[]={c.ptr()}; Rect unknownSaved[]={At<Rect>(c.ptr(),4)};
    InitList(list,unknown,unknownSaved,1,false);
    before=measured; int beforeOrganized=organized;
    KmrpTextRowsK1(list.ptr());
    assert(measured==before && organized==beforeOrganized && At<Rect>(c.ptr(),4).height==88);
    KmrpTextRowsForgetK1(list.ptr());
    // Native SetExtent can change usable width. Re-measure until the resulting
    // wrap and requested row height agree instead of caching the first width.
    Init(c,0x73E658,84,95); At<int>(Part(c.ptr(),0x154),0x5C)=1;
    At<Rect>(Part(c.ptr(),0x154),4).width=300;
    void* widthRows[]={c.ptr()}; Rect widthSaved[]={At<Rect>(c.ptr(),4)};
    InitList(list,widthRows,widthSaved,1,false); KmrpTextRowsK1(list.ptr());
    assert(widthSaved[0].height==103 && At<int>(list.ptr(),0x2B4)==103);
    KmrpTextRowsForgetK1(list.ptr());
    // Persistent authored rows follow the shared viewport scale, with no need
    // to destroy/repopulate them. Keep reference geometry to avoid roundtrip drift.
    KmrpTextRowsViewportK1(1080);nativeIcon=84;
    Init(c,0x7568F8,84,20); void* persistent[]={c.ptr()};Rect persistentSaved[]={At<Rect>(c.ptr(),4)};
    InitList(list,persistent,persistentSaved,1,false); KmrpTextRowsK1(list.ptr());
    assert(persistentSaved[0].height==84);
    for(int repeat=0;repeat<3;++repeat) {
        KmrpTextRowsViewportK1(720);nativeIcon=56;++generation;
        Set(c.ptr(),nullptr,&At<Rect>(c.ptr(),4));KmrpTextRowsK1(list.ptr());
        assert(persistentSaved[0].height==56);
        KmrpTextRowsViewportK1(1080);nativeIcon=84;++generation;
        Set(c.ptr(),nullptr,&At<Rect>(c.ptr(),4));KmrpTextRowsK1(list.ptr());
        assert(persistentSaved[0].height==84);
    }
    // When native code supplies replacement extents at the new size, adopt
    // those directly instead of scaling an already refreshed minimum twice.
    KmrpTextRowsViewportK1(720);nativeIcon=56;++generation;
    persistentSaved[0].height=56;Set(c.ptr(),nullptr,&persistentSaved[0]);
    KmrpTextRowsK1(list.ptr());assert(persistentSaved[0].height==56);
    KmrpTextRowsViewportK1(1080);nativeIcon=84;++generation;
    KmrpTextRowsK1(list.ptr());assert(persistentSaved[0].height==84);
    KmrpTextRowsForgetK1(list.ptr());KmrpTextRowsViewportK1(720);
    // Long bodies keep full scroll content height. Shrinking clamps the
    // separate one-based oversized page index; returning to fit resets it.
    Init(c,0x73E5B8,1008,1000);Rect bodySaved[]={At<Rect>(c.ptr(),4)};
    InitList(list,persistent,bodySaved,1,false);At<short>(list.ptr(),0x2C2)=30;
    KmrpTextRowsK1(list.ptr());assert(bodySaved[0].height==1008);
    assert(At<short>(list.ptr(),0x2C2)==30);
    At<int>(Part(c.ptr(),0xD0),0x60)=400;++generation;
    KmrpTextRowsK1(list.ptr());assert(bodySaved[0].height==408);
    assert(At<short>(list.ptr(),0x2C2)==10 && At<Rect>(c.ptr(),4).top==-216);
    At<int>(Part(c.ptr(),0xD0),0x60)=24;++generation;
    KmrpTextRowsK1(list.ptr());assert(At<short>(list.ptr(),0x2C2)==1);
    KmrpTextRowsForgetK1(list.ptr());
    // Feat and power chart rows: taller with the icon scale, the cells following
    // natively; the icons and arrows drawn larger about their own centres. At 50%
    // nothing changes and no text is measured.
    {
        Init(a,0x7578A8,100,0);Init(b,0x7578A8,100,0);
        Set(a.ptr(),nullptr,&At<Rect>(a.ptr(),4));Set(b.ptr(),nullptr,&At<Rect>(b.ptr(),4));
        void* chart[]={a.ptr(),b.ptr()};Rect chartSaved[2]={At<Rect>(a.ptr(),4),At<Rect>(b.ptr(),4)};
        InitList(list,chart,chartSaved,2,false);
        before=measured;KmrpTextRowsK1(list.ptr());
        assert(measured==before && chartSaved[0].height==100 && At<Rect>(a.ptr(),4).height==100);
        assert(At<Rect>(Part(a.ptr(),0xD0),0x14).width==64 && At<Rect>(Part(a.ptr(),0x3D4),0x14).width==32);
        textPercent=65;++generation;KmrpTextRowsK1(list.ptr());
        assert(measured==before && chartSaved[0].height==130 && chartSaved[1].height==130);
        assert(At<Rect>(a.ptr(),4).height==130 && At<Rect>(b.ptr(),4).height==130 && At<int>(list.ptr(),0x2B4)==130);
        for(unsigned image : {0xD0u,0x1F8u,0x320u}) {
            const Rect cell=At<Rect>(Part(a.ptr(),image),4), icon=At<Rect>(Part(a.ptr(),image),0x14);
            assert(cell.width==130 && icon.width==83 && icon.height==83); // 64 x 1.3
            assert(std::abs(2*icon.left+icon.width-(2*cell.left+cell.width))<=1);
            assert(std::abs(2*icon.top+icon.height-(2*cell.top+cell.height))<=1);
        }
        assert(At<Rect>(Part(a.ptr(),0x3D4),0x14).width==42 && At<Rect>(Part(a.ptr(),0x428),0x14).height==42);
        // A native SetExtent (scrolling) resets the drawn sizes; the next draw restores them.
        Set(a.ptr(),nullptr,&At<Rect>(a.ptr(),4));assert(At<Rect>(Part(a.ptr(),0xD0),0x14).width==64);
        KmrpTextRowsK1(list.ptr());assert(At<Rect>(Part(a.ptr(),0xD0),0x14).width==83);
        textPercent=50;++generation;KmrpTextRowsK1(list.ptr());
        assert(chartSaved[0].height==100 && At<Rect>(a.ptr(),4).height==100);
        assert(At<Rect>(Part(a.ptr(),0xD0),0x14).width==64 && At<Rect>(Part(a.ptr(),0x428),0x14).width==32);
        KmrpTextRowsForgetK1(a.ptr());KmrpTextRowsForgetK1(b.ptr());KmrpTextRowsForgetK1(list.ptr());
    }
    {
        // A skill row. At the default the three icon parts move together, as an item's.
        Object skill;
        Init(skill,0x755ED0,84,95);Set(skill.ptr(),nullptr,&At<Rect>(skill.ptr(),4));
        void* skillRows[]={skill.ptr()};Rect skillSaved[]={At<Rect>(skill.ptr(),4)};
        InitList(list,skillRows,skillSaved,1,false);
        textPercent=65;++generation;KmrpTextRowsK1(list.ptr());
        assert(skillSized==0 && At<Rect>(Part(skill.ptr(),0x29C),4).width==109);
        // With the slider moved it owns the third, in the box the row gives the icon, and
        // Text Size neither resizes it nor resets its fill, whichever order they run in.
        skillOwned=true;++generation;KmrpTextRowsK1(list.ptr());
        assert(skillSized>0 && At<Rect>(Part(skill.ptr(),0x29C),4).width==40);
        const Rect first=At<Rect>(Part(skill.ptr(),0x1B4),4), third=At<Rect>(Part(skill.ptr(),0x29C),4);
        assert(first.width==109 && std::abs(2*third.left+third.width-(2*first.left+first.width))<=1);
        assert((At<unsigned>(Part(skill.ptr(),0x29C),0x30)&3)==2);
        ++generation;KmrpTextRowsK1(list.ptr());
        assert(At<Rect>(Part(skill.ptr(),0x29C),4).width==40 && (At<unsigned>(Part(skill.ptr(),0x29C),0x30)&3)==2);
        skillOwned=false;textPercent=50;++generation;KmrpTextRowsK1(list.ptr());
        KmrpTextRowsForgetK1(skill.ptr());KmrpTextRowsForgetK1(list.ptr());
    }
    std::cout<<"Native row adapter: expansion, shrink, counters, cache, scroll, selection, unequal mode and charts passed\n";
}
