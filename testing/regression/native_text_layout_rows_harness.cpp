// Integrates both actual production services; mocks only native engine ABI.
#define KMRP_TEXT_LAYOUT_ROWS_TEST
#include "native_text_layout_harness.cpp"
namespace Integration {
int organizes=0;
unsigned TextOffset(void* row) {
    const auto vt=At<std::uintptr_t>(row,0);
    return vt==0x73E5B8 || vt==0x73E8E8 ? 0xD0 : 0x154;
}
unsigned AmountOffset(void* row) {
    const auto vt=At<std::uintptr_t>(row,0);
    return vt==0x757108?0x334:(vt==0x7568F8 || vt==0x756850?0x324:0);
}
void __fastcall WrapperExtent(void* wrapper,void*,const Rect* r) {
    At<Rect>(wrapper,4)=*r;
    if(void* object=Internal(wrapper)) {At<int>(object,0x0C)=r->width;At<int>(object,0x10)=r->height;}
}
void __fastcall RowExtent(void* row,void*,const Rect* r) {
    At<Rect>(row,4)=*r;
    const Rect inner{r->left+100,r->top+4,r->width-100,r->height-8};
    WrapperExtent(static_cast<char*>(row)+TextOffset(row),nullptr,&inner);
    const unsigned amount=AmountOffset(row);
    if(amount) {
        const unsigned iconOffset=amount==0x334?0x1D8:0x1C8;
        const Rect icon{r->left,r->top,84,84};
        At<Rect>(static_cast<char*>(row)+iconOffset,4)=icon;
        const Rect count{icon.left+52,icon.top+56,32,28};
        WrapperExtent(static_cast<char*>(row)+amount,nullptr,&count);
    }
}
void __fastcall Organize(void* list,void*) {
    ++organizes;
    auto rows=At<void**>(list,0x29C);const int count=At<int>(list,0x2A0);
    auto saved=At<Rect*>(list,0x2A8);auto& flags=At<unsigned>(list,0x2BC);
    if(flags&8) {
        At<short>(list,0x2C8)=0;
        int maximum=1;
        for(int i=0;i<count;++i) {
            if(!(flags&0x100))RowExtent(rows[i],nullptr,&saved[i]);
            maximum=(std::max)(maximum,At<Rect>(rows[i],4).height);
        }
        At<int>(list,0x2B4)=maximum;flags&=~8u;
    }
    int top=0;
    for(int i=0;i<count;++i) {
        Rect r=At<Rect>(rows[i],4);r.top=top;
        if(!(flags&0x100))r.height=At<int>(list,0x2B4);
        RowExtent(rows[i],nullptr,&r);top+=r.height;
    }
    At<short>(list,0x2C4)=static_cast<short>((std::max)(1,At<int>(list,0x298)/At<int>(list,0x2B4)));
}
void Attach(void* row,unsigned offset,Mock::Text& text) {std::memcpy(static_cast<char*>(row)+offset,text.wrapper.data,0x18);}
void InitRow(Mock::Bytes& row,unsigned vt,Mock::Text& name,Mock::Text* amount=nullptr) {
    At<std::uintptr_t>(row,0)=vt;
    Attach(row,TextOffset(row),name);
    if(amount)Attach(row,AmountOffset(row),*amount);
    const Rect initial{0,0,400,84};RowExtent(row,nullptr,&initial);
}
void InitList(Mock::Bytes& list,void** rows,Rect* saved,int count,bool unequal) {
    At<std::uintptr_t>(list,0)=0x73E840;At<Rect>(list,4)={0,0,500,200};
    At<void**>(list,0x29C)=rows;At<int>(list,0x2A0)=count;
    At<Rect*>(list,0x2A8)=saved;At<int>(list,0x2AC)=count;
    At<int>(list,0x298)=200;At<unsigned>(list,0x2BC)=unequal?0x100:0;
    At<short>(list,0x2C6)=static_cast<short>(count-1);At<short>(list,0x2C8)=0;
    for(int i=0;i<count;++i)saved[i]=At<Rect>(rows[i],4);
}
}
int KmrpTextSizePercentK1() {return 50;}  // the size before text options: icons stay native
void* KmrpTextRowsTestFunctionK1(std::uintptr_t address) {
    if(address==0x41B140)return reinterpret_cast<void*>(&Integration::Organize);
    if(address==0x416280)return reinterpret_cast<void*>(&Integration::WrapperExtent);
    if(address==0x7568F8 || address==0x756850 || address==0x757108 || address==0x73E5B8 || address==0x73E8E8 || address==0x73E658)
        return reinterpret_cast<void*>(&Integration::RowExtent);
    assert(false);return nullptr;
}
int main() {
    Mock::Init();
    {
        Mock::Text nameA("Alpha Beta Gamma Delta Epsilon Zeta Eta Theta",300,76),nameB("Short",300,76),nameC("Upgrade",300,76);
        Mock::Text amountA("9",32,28),amountB("12",32,28),amountC("3",32,28);
        Mock::Bytes a,b,c,list;
        Integration::InitRow(a,0x7568F8,nameA,&amountA);
        Integration::InitRow(b,0x756850,nameB,&amountB);
        Integration::InitRow(c,0x757108,nameC,&amountC);
        void* rows[]={a,b,c};Rect saved[3];Integration::InitList(list,rows,saved,3,false);
        KmrpTextStringDrawK1(nameA.object);KmrpTextStringDrawK1(amountA.object);
        assert(nameA.Size()<1 && amountA.Size()<1); // shared fitting catches original undersized controls
        KmrpTextRowsK1(list);
        assert(saved[0].height==103 && At<int>(list,0x2B4)==103);
        assert(At<Rect>(a,4).height==103 && At<Rect>(b,4).height==103);
        assert(nameA.Size()==1 && At<int>(nameA.object,0x38)==2);
        {
            // Bottom-right corner at 52/56 across (78) and 54/56 down (81) the live 84 px icon:
            // the digit's width, its
            // line height capped at half the icon (42 of 48), the glyphs fitted to that.
            const Rect countA=At<Rect>(static_cast<char*>(static_cast<void*>(a))+0x324,4);
            const Rect countC=At<Rect>(static_cast<char*>(static_cast<void*>(c))+0x334,4);
            const Rect iconA=At<Rect>(static_cast<char*>(static_cast<void*>(a))+0x1C8,4);
            assert(countA.width==11 && countA.height==42 && amountA.Size()<1);
            assert(countA.left==iconA.left+67 && countA.top==iconA.top+39);
            assert(countC.width==11 && countC.height==42 && amountC.Size()<1);
        }
        const int wraps=Mock::wrapCalls,organized=Integration::organizes;
        KmrpTextRowsK1(list);assert(Mock::wrapCalls==wraps && Integration::organizes==organized);
        At<float>(Mock::info,4)=0.24f;KmrpTextLayoutFontsChangedK1();KmrpTextRowsK1(list);
        assert(saved[0].height==84 && At<int>(list,0x2B4)==84);
        {
            // Smaller font: a smaller box in the same corner, glyphs unscaled.
            const Rect countA=At<Rect>(static_cast<char*>(static_cast<void*>(a))+0x324,4);
            const Rect iconA=At<Rect>(static_cast<char*>(static_cast<void*>(a))+0x1C8,4);
            assert(countA.height==24 && countA.top==iconA.top+57 && countA.left==iconA.left+67 && amountA.Size()==1);
        }
        // Content hashes must invalidate row and shared string caches at the same buffer address.
        nameA.Set("Alpha Beta Gamma Delta Epsilon Zeta Eta Theta Alpha Beta Gamma Delta Epsilon Zeta Eta Theta Alpha Beta Gamma Delta Epsilon Zeta Eta Theta");
        KmrpTextRowsK1(list);assert(saved[0].height>84 && nameA.Size()==1);
        nameA.Set("Short");KmrpTextRowsK1(list);assert(saved[0].height==84 && At<int>(list,0x2B4)==84);
        KmrpTextRowsForgetK1(list);
    }
    {
        At<float>(Mock::info,4)=0.4704f;KmrpTextLayoutFontsChangedK1();
        Mock::Text description("Alpha Beta Gamma Delta Epsilon Zeta Eta Theta Alpha Beta Gamma Delta Epsilon Zeta Eta Theta Alpha Beta Gamma Delta Epsilon Zeta Eta Theta",300,20);
        Mock::Bytes row,list;Integration::InitRow(row,0x73E5B8,description);
        void* rows[]={row};Rect saved[1];Integration::InitList(list,rows,saved,1,true);
        At<int>(list,0x298)=50;At<Rect>(list,4).height=50;
        KmrpTextRowsK1(list);
        const int natural=KmrpTextNaturalHeightK1(description.wrapper);
        assert(description.Size()==1 && natural>50);
        assert(At<Rect>(row,4).height==natural+8 && At<Rect>(row,4).height>At<Rect>(list,4).height);
        const int grown=At<Rect>(row,4).height;
        description.Set("Short");KmrpTextRowsK1(list);
        assert(description.Size()==1 && At<Rect>(row,4).height==56 && At<Rect>(row,4).height<grown);
        KmrpTextRowsForgetK1(list);
    }
    assert(strings.empty());
    std::cout<<"PASS: combined production fitting and native row services, counters, font shrink, reused text and scroll content.\n";
}
