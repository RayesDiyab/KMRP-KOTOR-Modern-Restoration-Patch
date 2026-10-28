// Party Roster Limit 32 compatibility (issue #38). Geometry follows the centre /
// size mapping demonstrated by jryantomes' tools/kmrp_party32/party32.py. Keep the
// supplied roster's complete control records, including both 16-slot pages;
// replace presentation fields only. No game-derived layout is embedded here.
#include "K1PartyRosterGui.h"
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <map>
#include <stdexcept>
#include <utility>

namespace {
using Bytes = std::vector<unsigned char>;
using U = std::uint32_t;
void Require(bool ok, const char* why) { if (!ok) throw std::runtime_error(why); }
U Get(const Bytes& b, std::size_t at) {
    Require(at <= b.size() && b.size() - at >= 4, "GFF integer outside section");
    U v; std::memcpy(&v, b.data() + at, 4); return v;
}
void Put(Bytes& b, std::size_t at, U v) {
    Require(at <= b.size() && b.size() - at >= 4, "GFF write outside section");
    std::memcpy(b.data() + at, &v, 4);
}
struct Gff {
    Bytes header, structures, fields, labels, values, indices, lists;
    explicit Gff(const Bytes& data) {
        Require(data.size() >= 56 && data.size() <= (2u << 20) &&
                !std::memcmp(data.data(), "GUI V3.2", 8), "not a supported GUI GFF");
        header.assign(data.begin(), data.begin() + 56);
        Bytes* sections[] = {&structures, &fields, &labels, &values, &indices, &lists};
        const U stride[] = {12, 12, 16, 1, 1, 1};
        for (U i = 0; i < 6; ++i) {
            const U offset = Get(data, 8 + i * 8), count = Get(data, 12 + i * 8);
            const std::uint64_t size = std::uint64_t(count) * stride[i];
            Require(offset >= 56 && offset <= data.size() && size <= data.size() - offset,
                    "invalid GUI section extent");
            sections[i]->assign(data.begin() + offset, data.begin() + offset + static_cast<std::size_t>(size));
        }
        Require(!structures.empty(), "GUI has no root");
    }
    std::vector<U> members(U object) const {
        Require(object < structures.size() / 12, "invalid GUI structure index");
        const U at = Get(structures, object * 12 + 4), count = Get(structures, object * 12 + 8);
        Require(count <= fields.size() / 12, "invalid GUI field count");
        std::vector<U> result;
        for (U i = 0; i < count; ++i) {
            const U index = count == 1 ? at : Get(indices, std::size_t(at) + i * 4ull);
            Require(index < fields.size() / 12, "invalid GUI field index");
            result.push_back(index);
        }
        return result;
    }
    std::string label(U field) const {
        const U index = Get(fields, field * 12 + 4);
        Require(index < labels.size() / 16, "invalid GUI label index");
        char name[17]{}; std::memcpy(name, labels.data() + index * 16, 16); return name;
    }
    U find(U object, const char* name, bool required = true) const {
        for (U f : members(object)) if (label(f) == name) return f;
        Require(!required, "required GUI field missing"); return ~U(0);
    }
    U type(U field) const { return Get(fields, field * 12); }
    U value(U field) const { return Get(fields, field * 12 + 8); }
    U child(U object, const char* name) const {
        const U f = find(object, name); Require(type(f) == 14, "GUI field is not a structure"); return value(f);
    }
    int integer(U object, const char* name) const {
        const U f = find(object, name); Require(type(f) == 4 || type(f) == 5, "GUI integer has wrong type");
        return static_cast<int>(value(f));
    }
    void integer(U object, const char* name, int v) {
        const U f = find(object, name); Require(type(f) == 4 || type(f) == 5, "GUI integer has wrong type");
        Put(fields, f * 12 + 8, static_cast<U>(v));
    }
    std::string text(U object, const char* name) const {
        const U f = find(object, name); Require(type(f) == 10, "GUI tag has wrong type");
        const U at = value(f), n = Get(values, at);
        Require(n < 256 && at <= values.size() && n + 4ull <= values.size() - at, "invalid GUI tag");
        return std::string(reinterpret_cast<const char*>(values.data() + at + 4), n);
    }
    std::map<std::string,U> controls() const {
        const U f = find(0, "CONTROLS"); Require(type(f) == 15, "GUI controls are not a list");
        const U at = value(f), count = Get(lists, at); Require(count > 0 && count <= 512, "invalid control count");
        std::map<std::string,U> result;
        for (U i = 0; i < count; ++i) {
            const U object = Get(lists, std::size_t(at) + 4 + i * 4ull);
            Require(result.emplace(text(object, "TAG"), object).second, "duplicate GUI control tag");
        }
        return result;
    }
    // Copy a presentation value without changing any structure or field index.
    // Complex values are appended to field-data; pack() rebuilds section offsets.
    void copy(U target, const Gff& from, U source, unsigned depth = 0) {
        Require(depth < 12 && type(target) == from.type(source), "incompatible GUI style");
        const U t = type(target), v = from.value(source);
        if (t == 14) {
            for (U sf : from.members(v)) {
                const U tf = find(value(target), from.label(sf).c_str(), false);
                if (tf != ~U(0)) copy(tf, from, sf, depth + 1);
            }
            return;
        }
        if (t <= 5 || t == 8) { Put(fields, target * 12 + 8, v); return; }
        std::size_t n = 0;
        if (t == 6 || t == 7 || t == 9) n = 8;
        else if (t == 16) n = 16;
        else if (t == 17) n = 12;
        else if (t == 11) { Require(v < from.values.size(), "invalid GUI resref"); n = 1ull + from.values[v]; }
        else if (t == 10 || t == 12 || t == 13) n = 4ull + Get(from.values, v);
        else Require(false, "unsupported GUI style type");
        Require(v <= from.values.size() && n <= from.values.size() - v, "GUI style outside field-data");
        Require(values.size() + n <= (4u << 20), "adapted GUI field-data too large");
        const U offset = static_cast<U>(values.size());
        values.insert(values.end(), from.values.begin() + v, from.values.begin() + v + n);
        Put(fields, target * 12 + 8, offset);
    }
    void memberList(U object,const std::vector<U>& fs) {
        Put(structures,object*12+8,static_cast<U>(fs.size()));
        if(fs.size()==1)Put(structures,object*12+4,fs[0]);
        else {
            const U at=static_cast<U>(indices.size());
            for(U f:fs) {const auto n=indices.size();indices.resize(n+4);Put(indices,n,f);}
            Put(structures,object*12+4,at);
        }
    }
    U appendField(U object,const char* name,U kind,U data) {
        U labelIndex=~U(0);
        for(U i=0;i<labels.size()/16;++i)if(!std::strncmp(reinterpret_cast<const char*>(labels.data()+i*16),name,16))labelIndex=i;
        if(labelIndex==~U(0)) {
            Require(std::strlen(name)<16,"GUI label too long");
            labelIndex=static_cast<U>(labels.size()/16);const auto n=labels.size();labels.resize(n+16);
            std::memcpy(labels.data()+n,name,std::strlen(name));
        }
        auto fs=members(object);const U f=static_cast<U>(fields.size()/12);fields.resize(fields.size()+12);
        Put(fields,f*12,kind);Put(fields,f*12+4,labelIndex);Put(fields,f*12+8,data);
        fs.push_back(f);memberList(object,fs);return f;
    }
    U clone(U object,unsigned depth=0) {
        Require(depth<12 && structures.size()/12<4096,"GUI clone limit");
        const auto fs=members(object);const U result=static_cast<U>(structures.size()/12);
        const U kind=Get(structures,object*12);structures.resize(structures.size()+12);Put(structures,result*12,kind);
        std::vector<U> copied;
        for(U f:fs) {
            const U t=type(f),li=Get(fields,f*12+4);U data=value(f);
            if(t==14)data=clone(data,depth+1);
            if(t==15) {
                const U n=Get(lists,data);Require(n<=512,"GUI clone list limit");
                std::vector<U> objects;
                for(U i=0;i<n;++i)objects.push_back(Get(lists,data+4+i*4));
                for(auto& one:objects)one=clone(one,depth+1);
                data=static_cast<U>(lists.size());lists.resize(lists.size()+4+objects.size()*4);Put(lists,data,n);
                for(U i=0;i<n;++i)Put(lists,data+4+i*4,objects[i]);
            }
            const U nf=static_cast<U>(fields.size()/12);fields.resize(fields.size()+12);
            Put(fields,nf*12,t);Put(fields,nf*12+4,li);Put(fields,nf*12+8,data);copied.push_back(nf);
        }
        memberList(result,copied);return result;
    }
    void string(U object,const char* name,const std::string& text,U kind=10) {
        Require(text.size()<256,"generated GUI string too long");
        const U at=static_cast<U>(values.size());
        if(kind==11) {values.push_back(static_cast<unsigned char>(text.size()));}
        else {const auto n=values.size();values.resize(n+4);Put(values,n,static_cast<U>(text.size()));}
        values.insert(values.end(),text.begin(),text.end());
        const U f=find(object,name,false);
        if(f==~U(0))appendField(object,name,kind,at);
        else {Require(type(f)==kind,"GUI string type mismatch");Put(fields,f*12+8,at);}
    }
    void controlList(const std::vector<U>& objects) {
        Require(objects.size()<=512,"too many generated controls");
        const U at=static_cast<U>(lists.size());lists.resize(lists.size()+4+objects.size()*4);
        Put(lists,at,static_cast<U>(objects.size()));
        for(U i=0;i<objects.size();++i)Put(lists,at+4+i*4,objects[i]);
        Put(fields,find(0,"CONTROLS")*12+8,at);
    }
    Bytes pack() const {
        Bytes result = header;
        const Bytes* sections[] = {&structures, &fields, &labels, &values, &indices, &lists};
        const U stride[] = {12, 12, 16, 1, 1, 1};
        for (U i = 0; i < 6; ++i) {
            Require(result.size() < (4u << 20), "adapted GUI too large");
            Put(result, 8 + i * 8, static_cast<U>(result.size()));
            Put(result, 12 + i * 8, static_cast<U>(sections[i]->size() / stride[i]));
            result.insert(result.end(), sections[i]->begin(), sections[i]->end());
        }
        return result;
    }
};
struct Extent { int x,y,w,h; };
Extent Ext(const Gff& g, U object) {
    const U e = g.child(object, "EXTENT");
    Extent r{g.integer(e,"LEFT"),g.integer(e,"TOP"),g.integer(e,"WIDTH"),g.integer(e,"HEIGHT")};
    Require(r.w > 0 && r.h > 0 && r.w <= 32767 && r.h <= 32767 && std::abs(static_cast<long long>(r.x)) <= 32767 && std::abs(static_cast<long long>(r.y)) <= 32767,
            "invalid control geometry"); return r;
}
void Ext(Gff& g, U object, Extent e) {
    const U s = g.child(object,"EXTENT");
    g.integer(s,"LEFT",e.x);g.integer(s,"TOP",e.y);g.integer(s,"WIDTH",e.w);g.integer(s,"HEIGHT",e.h);
}
struct Map { double ax,bx,ay,by,sw,sh; };
using Pair = std::pair<Extent,Extent>;
Map Fit(const std::vector<Pair>& pairs) {
    double sx=0,sy=0,sxx=0,sxy=0,tx=0,ty=0,tyy=0,txy=0,ow=0,oh=0,nw=0,nh=0;
    for(const auto& p:pairs) {
        const double x=p.first.x+p.first.w/2.0,y=p.first.y+p.first.h/2.0;
        const double xx=p.second.x+p.second.w/2.0,yy=p.second.y+p.second.h/2.0;
        sx+=x;sy+=xx;sxx+=x*x;sxy+=x*xx;tx+=y;ty+=yy;tyy+=y*y;txy+=y*yy;
        ow+=p.first.w;oh+=p.first.h;nw+=p.second.w;nh+=p.second.h;
    }
    const double n=static_cast<double>(pairs.size()), dx=n*sxx-sx*sx,dy=n*tyy-tx*tx;
    Require(n>=2 && dx>0 && dy>0 && ow>0 && oh>0,"cannot fit GUI geometry");
    const double ax=(n*sxy-sx*sy)/dx,ay=(n*txy-tx*ty)/dy;
    return {ax,(sy-ax*sx)/n,ay,(ty-ay*tx)/n,nw/ow,nh/oh};
}
Extent Place(const Map& m,Extent e) {
    const int w=static_cast<int>(std::lround(m.sw*e.w)),h=static_cast<int>(std::lround(m.sh*e.h));
    return {static_cast<int>(std::lround(m.ax*(e.x+e.w/2.0)+m.bx-w/2.0)),
            static_cast<int>(std::lround(m.ay*(e.y+e.h/2.0)+m.by-h/2.0)),w,h};
}
// Within `tolerance` px: a pixel per 1440 rows of the panel (KmrpBuildPartyRosterGui). At
// 15360x8640 the bottom row's Done takes Character's Scripts, 3500 wide where one scale
// for it and Accept gives 3503 (tools/menu_bottom_row.py, 2026-10-28); a 1 px limit there
// refused the layout.
void CheckFit(const Map& m,const std::vector<Pair>& pairs,int tolerance) {
    for(const auto& p:pairs) {
        const Extent got=Place(m,p.first),want=p.second;
        Require(std::abs(got.x-want.x)<=tolerance && std::abs(got.y-want.y)<=tolerance &&
                std::abs(got.w-want.w)<=tolerance && std::abs(got.h-want.h)<=tolerance,"KMRP layout is outside the verified mapping");
    }
}
void Style(Gff& dst,U control,const Gff& source,U templateControl,bool keepFill = false) {
    for(const char* name:{"BORDER","HILIGHT","SELECTED","HILIGHTSELECTED"}) {
        const U a=dst.find(control,name,false), b=source.find(templateControl,name,false);
        if(a!=~U(0) && b!=~U(0)) {
            if (!keepFill) dst.copy(a,source,b);
            else {
                Require(dst.type(a)==14 && source.type(b)==14,"invalid border style");
                for (U sf : source.members(source.value(b))) {
                    if (source.label(sf)=="FILL") continue; // portraits, unavailable marks and page captions remain the mod's
                    const U tf=dst.find(dst.value(a),source.label(sf).c_str(),false);
                    if(tf!=~U(0))dst.copy(tf,source,sf);
                }
            }
        }
    }
    const U a=dst.find(control,"TEXT",false), b=source.find(templateControl,"TEXT",false);
    if(a!=~U(0) && b!=~U(0)) {
        Require(dst.type(a)==14 && source.type(b)==14,"invalid text style");
        for(const char* name:{"FONT","COLOR","ALIGNMENT","PULSING"}) {
            const U af=dst.find(dst.value(a),name,false),bf=source.find(source.value(b),name,false);
            if(af!=~U(0) && bf!=~U(0))dst.copy(af,source,bf);
        }
    }
}
} // namespace

bool KmrpBuildPartyRosterGui(const Bytes& roster,const Bytes& kmrp,Bytes& output,std::string& reason)
{
    output.clear();reason.clear();
    try {
        Gff out(roster), target(kmrp);
        const auto controls=out.controls(),templates=target.controls();
        auto control=[&](const std::map<std::string,U>& table,const std::string& tag) {
            const auto it=table.find(tag);Require(it!=table.end(),"required roster/template control missing");return it->second;
        };
        std::vector<Pair> slots,buttons;
        // Stock 640x480 geometry measured from the game's partyselection.gui:
        // 3x3, 85px controls, origin (54,109), spacing (91,88). All three slot
        // control kinds share this extent. These are geometry, never copied art.
        for(const char* prefix:{"BTN_NPC","LBL_CHAR","LBL_NA"}) for(int i=0;i<9;++i)
            slots.push_back({{54+91*(i%3),109+88*(i/3),85,85},Ext(target,control(templates,std::string(prefix)+std::to_string(i)))});
        buttons.push_back({{73,372,235,33},Ext(target,control(templates,"BTN_ACCEPT"))});
        buttons.push_back({{247,410,146,28},Ext(target,control(templates,"BTN_DONE"))});
        const Map slotMap=Fit(slots),buttonMap=Fit(buttons);
        const int tolerance=std::max(1,static_cast<int>(std::lround(Ext(target,0).h/1440.0)));
        CheckFit(slotMap,slots,tolerance);CheckFit(buttonMap,buttons,tolerance);
        std::map<int,bool> ids;
        for(const auto& item:controls) {
            const int id=out.integer(item.second,"ID");
            Require(ids.emplace(id,true).second,"duplicate roster control ID");
        }
        for(const char* prefix:{"BTN_NPC","LBL_CHAR","LBL_NA"}) for(int i=0;i<32;++i)
            control(controls,std::string(prefix)+std::to_string(i));
        control(controls,"BTN_PAGE_PREV");control(controls,"BTN_PAGE_NEXT");
        // Panel and every existing non-slot control use the target's geometry;
        // captions, IDs and navigation always remain the supplied roster's.
        Ext(out,0,Ext(target,0));Style(out,0,target,0);
        for(const auto& item:controls) {
            const std::string& tag=item.first;const U object=item.second;
            std::string base;
            for(const char* prefix:{"BTN_NPC","LBL_CHAR","LBL_NA"})
                if(tag.compare(0,std::strlen(prefix),prefix)==0)base=std::string(prefix)+"0";
            if(!base.empty()) {
                const Extent placed=Place(slotMap,Ext(out,object));Ext(out,object,placed);
                Style(out,object,target,control(templates,base),true);
            } else if(tag=="BTN_PAGE_PREV" || tag=="BTN_PAGE_NEXT") {
                Extent placed=Place(buttonMap,Ext(out,object));
                // These controls contain a single arrow. Keep its centre and
                // the bottom row's height, with a square hit target instead of
                // the supplied caption-width button.
                const int width=std::min(placed.w,placed.h);
                placed.x+=static_cast<int>(std::lround((placed.w-width)/2.0));
                placed.w=width;
                Ext(out,object,placed);
                Style(out,object,target,control(templates,"BTN_DONE"),true);
            } else {
                const auto it=templates.find(tag);
                if(it!=templates.end()){Ext(out,object,Ext(target,it->second));Style(out,object,target,it->second);}
            }
        }
        // Some authored narrow layouts already put their 3x3 controls closer
        // than their width. A 4x4 page must fit without overlapping hit boxes.
        // Keep centres and aspect ratio, shrinking every slot uniformly only
        // when the mapped page needs it. Both pages use the same factor.
        double shrink=1.0;
        const double gap=std::max(1.0,std::round(Ext(target,0).h/720.0));
        for(int page=0;page<2;++page)for(int i=0;i<16;++i)for(int j=i+1;j<16;++j) {
            const Extent a=Ext(out,control(controls,"BTN_NPC"+std::to_string(page*16+i)));
            const Extent b=Ext(out,control(controls,"BTN_NPC"+std::to_string(page*16+j)));
            const double dx=std::abs((a.x+a.w/2.0)-(b.x+b.w/2.0));
            const double dy=std::abs((a.y+a.h/2.0)-(b.y+b.h/2.0));
            Require(dx>0 || dy>0,"coincident roster slot centres");
            const double room=dx>=dy?(dx-gap)/((a.w+b.w)/2.0):(dy-gap)/((a.h+b.h)/2.0);
            shrink=std::min(shrink,room);
        }
        Require(shrink>0.25,"roster slots cannot fit this layout");
        if(shrink<1.0)for(const char* prefix:{"BTN_NPC","LBL_CHAR","LBL_NA"})for(int i=0;i<32;++i) {
            const U object=control(controls,std::string(prefix)+std::to_string(i));
            const Extent old=Ext(out,object);
            const int w=std::max(1,static_cast<int>(std::floor(old.w*shrink)));
            const int h=std::max(1,static_cast<int>(std::floor(old.h*shrink)));
            Ext(out,object,{static_cast<int>(std::lround(old.x+(old.w-w)/2.0)),
                            static_cast<int>(std::lround(old.y+(old.h-h)/2.0)),w,h});
        }
        // Reject unsupported geometry rather than registering clipped or
        // overlapping actions. Hidden second-page records are checked separately.
        const Extent panel=Ext(out,0);
        for(int page=0;page<2;++page) {
            std::vector<Extent> boxes;
            for(int i=0;i<16;++i)boxes.push_back(Ext(out,control(controls,"BTN_NPC"+std::to_string(page*16+i))));
            for(const char* tag:{"BTN_ACCEPT","BTN_DONE","BTN_BACK","BTN_PAGE_PREV","BTN_PAGE_NEXT"})
                boxes.push_back(Ext(out,control(controls,tag)));
            for(std::size_t i=0;i<boxes.size();++i) {
                const Extent a=boxes[i];
                Require(a.x>=0 && a.y>=0 && a.x+a.w<=panel.w && a.y+a.h<=panel.h,"adapted roster outside panel");
                for(std::size_t j=i+1;j<boxes.size();++j) {
                    const Extent b=boxes[j];
                    Require(a.x+a.w<=b.x || b.x+b.w<=a.x || a.y+a.h<=b.y || b.y+b.h<=a.y,"adapted roster actions overlap");
                }
            }
        }
        output=out.pack();return true;
    } catch(const std::exception& e) {reason=e.what();output.clear();return false;}
}

// Build the definitions the roster's own native binder needs, from this size's
// ordinary party controls. No additional GUI asset or roster object layout is
// required. IDs/navigation follow the public 32-slot GUI contract.
bool KmrpGeneratePartyRosterGui(const Bytes& kmrp,Bytes& output,std::string& reason)
{
    output.clear();reason.clear();
    try {
        Gff base(kmrp);auto controls=base.controls();std::vector<U> objects;
        for(const auto& entry:controls)objects.push_back(entry.second);
        auto get=[&](const std::string& tag) {
            auto it=controls.find(tag);Require(it!=controls.end(),"missing generation template");return it->second;
        };
        auto buttonId=[](int i){return i<9?9+i:40+3*(i-9);};
        for(int i=0;i<32;++i) {
            const int physical=i%16;
            for(const char* prefix:{"BTN_NPC","LBL_CHAR","LBL_NA"}) {
                const std::string tag=std::string(prefix)+std::to_string(i);
                U object;
                if(i<9)object=get(tag);
                else {
                    object=base.clone(get(std::string(prefix)+"0"));
                    base.string(object,"TAG",tag);objects.push_back(object);controls[tag]=object;
                    const int id=39+3*(i-9)+(std::strcmp(prefix,"BTN_NPC")==0?1:std::strcmp(prefix,"LBL_NA")==0?2:0);
                    base.integer(object,"ID",id);
                }
                Ext(base,object,{54+68*(physical%4),109+65*(physical/4),63,63});
                if(std::strcmp(prefix,"BTN_NPC")==0) {
                    const int page=(i/16)*16,row=physical/4,col=physical%4;
                    U nav=base.child(object,"MOVETO");
                    base.integer(nav,"UP",buttonId(page+((row+3)%4)*4+col));
                    base.integer(nav,"RIGHT",buttonId(page+row*4+(col+1)%4));
                    base.integer(nav,"LEFT",buttonId(page+row*4+(col+3)%4));
                    base.integer(nav,"DOWN",row==3?(col<2?108:109):buttonId(i+4));
                }
            }
        }
        for(int i=0;i<2;++i) {
            const U object=base.clone(get("BTN_DONE"));objects.push_back(object);
            base.string(object,"TAG",i?"BTN_PAGE_NEXT":"BTN_PAGE_PREV");base.integer(object,"ID",108+i);
            Ext(base,object,{73+80*i,410,74,28});
            const U text=base.child(object,"TEXT");base.integer(text,"STRREF",-1);base.string(text,"TEXT",i?">":"<");
            for(const char* name:{"BORDER","HILIGHT","SELECTED","HILIGHTSELECTED"}) {
                const U f=base.find(object,name,false);
                if(f!=~U(0))base.string(base.value(f),"FILL","",11);
            }
            const U nav=base.child(object,"MOVETO");
            base.integer(nav,"UP",buttonId(i?15:12));base.integer(nav,"DOWN",38);
            base.integer(nav,"LEFT",i?108:37);base.integer(nav,"RIGHT",i?36:109);
        }
        const U accept=base.child(get("BTN_ACCEPT"),"MOVETO");
        base.integer(accept,"UP",buttonId(13));base.integer(accept,"DOWN",buttonId(1));
        base.controlList(objects);
        return KmrpBuildPartyRosterGui(base.pack(),kmrp,output,reason);
    } catch(const std::exception& e) {reason=e.what();output.clear();return false;}
}
