#pragma once
#include <windows.h>
#include <cstdio>
#include <cstring>
#include <vector>
#include <utility>
#include "K1CaptionInk.h"
#include "K1GuiModelPreload.h"

// Level 2 only: snapshots around the native Draw, without an external debugger.
// The engine's texture build queue is separate from the controller picture worker.
namespace K1ClassModelTrace {
using Draw = void(__thiscall*)(void*, float);
constexpr std::uintptr_t DrawAddress = 0x006DC030;
constexpr std::uintptr_t DrawSlot = 0x00758054;
static void* owner = nullptr;
static unsigned frame = 0;
constexpr std::uintptr_t ViewDrawAddress = 0x0067ACB0;
constexpr std::uintptr_t ViewDrawSlot = 0x00752E68;
static bool drawing = false;

struct Scene {
    void* object = nullptr;
    int renders = -1, children = -1, animated = -1, lights = -1;
    float ambient[3] = {};
    float firstLight[3] = {};
};
struct View {
    unsigned index;
    Scene before, after;
};
static std::vector<View> views;
inline Scene CaptureScene(void* view) {
    Scene out;
    const auto* control = static_cast<const unsigned char*>(view);
    if (!K1CaptionInk::Readable(control, 0x78)) return out;
    const auto* scene = *reinterpret_cast<const unsigned char* const*>(control + 0x70);
    if (!K1CaptionInk::Readable(scene, 0xF8)) return out;
    out.object = const_cast<unsigned char*>(scene);
    std::memcpy(&out.renders, scene + 0x50, 4);
    std::memcpy(&out.children, scene + 0x58, 4);
    std::memcpy(&out.animated, scene + 0xF0, 4);
    std::memcpy(out.ambient, scene + 0x88, 12);
    const auto* manager = *reinterpret_cast<const unsigned char* const*>(scene + 0x80);
    if (K1CaptionInk::Readable(manager, 0x14)) {
        std::memcpy(&out.lights, manager + 0x0C, 4);
        const auto* list = *reinterpret_cast<const unsigned char* const* const*>(manager + 8);
        if (out.lights > 0 && out.lights < 1024 && K1CaptionInk::Readable(list, sizeof(void*)) &&
            K1CaptionInk::Readable(list[0], 0x58)) std::memcpy(out.firstLight, list[0] + 0x4C, 12);
    }
    return out;
}
inline void __fastcall TracedViewDraw(void* view, void*, float delta) {
    int index = -1;
    if (drawing) for (int i = 0; i < 6; ++i) {
        if (static_cast<unsigned char*>(owner) + 0x230 + i * 0x25C == view) { index = i; break; }
    }
    Scene before;
    K1GuiModelPreload::Prime(view, reinterpret_cast<Draw>(ViewDrawAddress));
    if (index >= 0) before = CaptureScene(view);
    reinterpret_cast<Draw>(ViewDrawAddress)(view, delta);
    if (index >= 0) views.push_back({static_cast<unsigned>(index), before, CaptureScene(view)});
    K1GuiModelPreload::AfterDraw(view);
}

struct Texture {
    void* object;
    unsigned gl;
    int width, height;
    unsigned built;
    char name[33];
};
struct Snapshot {
    int pending = -1, total = -1;
    unsigned locked = 0;
    std::vector<Texture> textures;
};
struct Frame {
    Snapshot before, after;
    std::vector<View> models;
};
static std::vector<Frame> recorded;
inline Snapshot Capture() {
    Snapshot out;
    out.pending = *reinterpret_cast<const int*>(0x007A4774);
    out.locked = *reinterpret_cast<const unsigned*>(0x007A4714);
    void** const list = *reinterpret_cast<void***>(0x007A4798);
    out.total = *reinterpret_cast<const int*>(0x007A479C);
    if (out.total < 0 || out.total > 16384 || !K1CaptionInk::Readable(list, out.total * sizeof(void*))) return out;
    for (int i = 0; i < out.total; ++i) {
        const auto* p = static_cast<const unsigned char*>(list[i]);
        if (!K1CaptionInk::Readable(p, 0xE8)) continue;
        Texture t{};
        t.object = list[i];
        std::memcpy(&t.gl, p + 0x58, 4);
        std::memcpy(&t.width, p + 0x68, 4);
        std::memcpy(&t.height, p + 0x6C, 4);
        t.built = p[0xE0];
        std::memcpy(t.name, p + 0x78, 32);
        out.textures.push_back(t);
    }
    return out;
}
inline void Log(const Snapshot& before, const Snapshot& after, void* panel, unsigned number) {
    char line[300];
    std::snprintf(line, sizeof line, "class-model frame=%u panel=%p pending=%d->%d textures=%d->%d locked=%u->%u",
                  number, panel, before.pending, after.pending, before.total, after.total, before.locked, after.locked);
    ControllerLogK1(line);
    unsigned printed = 0;
    for (const auto& t : after.textures) {
        const Texture* old = nullptr;
        for (const auto& was : before.textures) if (was.object == t.object) { old = &was; break; }
        if (old && old->gl == t.gl && old->built == t.built && t.gl) continue;
        if (printed++ == 64) { ControllerLogK1("class-model: remaining texture rows omitted"); break; }
        std::snprintf(line, sizeof line, "class-model texture=%.32s object=%p new=%u gl=%u->%u built=%u->%u size=%dx%d",
                      t.name, t.object, old ? 0u : 1u, old ? old->gl : 0u, t.gl,
                      old ? old->built : 0u, t.built, t.width, t.height);
        ControllerLogK1(line);
    }
}
inline void Flush(void* panel) {
    unsigned number = 0;
    for (const auto& f : recorded) {
        Log(f.before, f.after, panel, ++number);
        for (const auto& v : f.models) {
            char line[400];
            const auto& a = v.before; const auto& b = v.after;
            std::snprintf(line, sizeof line,
                "class-scene frame=%u model=%u scene=%p renders=%d->%d children=%d->%d animated=%d->%d lights=%d->%d ambient=(%.3f,%.3f,%.3f)->(%.3f,%.3f,%.3f) light0=(%.3f,%.3f,%.3f)->(%.3f,%.3f,%.3f)",
                number, v.index + 1, b.object, a.renders, b.renders, a.children, b.children,
                a.animated, b.animated, a.lights, b.lights,
                a.ambient[0], a.ambient[1], a.ambient[2], b.ambient[0], b.ambient[1], b.ambient[2],
                a.firstLight[0], a.firstLight[1], a.firstLight[2], b.firstLight[0], b.firstLight[1], b.firstLight[2]);
            ControllerLogK1(line);
        }
    }
    recorded.clear();
}
inline void __fastcall TracedDraw(void* panel, void*, float delta) {
    const bool trace = KmrpDebugLevel() >= 2 && panel == owner && frame < 4;
    Snapshot before;
    if (trace) { ++frame; views.clear(); before = Capture(); drawing = true; }
    reinterpret_cast<Draw>(DrawAddress)(panel, delta);
    if (trace) {
        drawing = false;
        recorded.push_back({std::move(before), Capture(), std::move(views)});
        if (frame == 4) Flush(panel);
    }
}
inline bool Replace(void** slot, void* traced, void* native) {
    if (!K1CaptionInk::Readable(slot, sizeof(void*))) return false;
    if (*slot == traced) return true;
    if (*slot != native) return false;
    DWORD protection = 0;
    if (!VirtualProtect(slot, sizeof(void*), PAGE_READWRITE, &protection)) return false;
    void* previous = InterlockedCompareExchangePointer(slot, traced, native);
    DWORD unused = 0;
    VirtualProtect(slot, sizeof(void*), protection, &unused);
    return previous == native;
}
inline void QueuePanel(void* panel) {
    K1GuiModelPreload::Forget(panel);
    if (!K1CaptionInk::Readable(panel, sizeof(void*))) return;
    const auto vt = *static_cast<const std::uintptr_t*>(panel);
    if (vt != 0x00758020 && vt != 0x00752F70) return;
    if (Replace(reinterpret_cast<void**>(ViewDrawSlot), reinterpret_cast<void*>(&TracedViewDraw),
                reinterpret_cast<void*>(ViewDrawAddress))) K1GuiModelPreload::Queue(panel);
}
inline void Install(void* panel) {
    if (KmrpDebugLevel() < 2) return;
    auto** slot = reinterpret_cast<void**>(DrawSlot);
    void* const native = reinterpret_cast<void*>(DrawAddress);
    void* const traced = reinterpret_cast<void*>(&TracedDraw);
    if (!Replace(slot, traced, native)) {
        ControllerLogK1("class-model: Draw slot belongs to another patch; trace skipped");
        return;
    }
    if (!Replace(reinterpret_cast<void**>(ViewDrawSlot), reinterpret_cast<void*>(&TracedViewDraw),
                 reinterpret_cast<void*>(ViewDrawAddress)))
        ControllerLogK1("class-model: 3D view Draw belongs to another patch; scene trace skipped");
    owner = panel;
    frame = 0;
    recorded.clear();
    ControllerLogK1("class-model: first four native draws buffered; texture and scene trace follows after draw four");
}
}
