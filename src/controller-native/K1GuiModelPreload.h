#pragma once
#include <windows.h>
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <vector>
#include "K1CaptionInk.h"

// The highest-priority graphics preload is the actual preview's first render.
// It runs on the GUI/GL owner thread, before its first visible draw. File-only
// work remains on the independent controller worker.
namespace K1GuiModelPreload {
using Draw = void(__thiscall*)(void*, float);
using Context = void*(WINAPI*)();
using GetInteger = void(WINAPI*)(unsigned, int*);
using DrawBuffer = void(WINAPI*)(unsigned);
struct Graphics { Context context = nullptr; GetInteger get = nullptr; DrawBuffer buffer = nullptr; };
static Graphics graphics;
static bool resolved = false;
struct Job { void* panel; void* view; const char* kind; };
struct Ready { Job job; int before, primed; bool hidden; };
static std::vector<Job> pending;
static std::vector<Ready> ready;

inline Graphics Api() {
    if (!resolved) {
        if (HMODULE gl = GetModuleHandleW(L"opengl32.dll")) {
            graphics.context = reinterpret_cast<Context>(GetProcAddress(gl, "wglGetCurrentContext"));
            graphics.get = reinterpret_cast<GetInteger>(GetProcAddress(gl, "glGetIntegerv"));
            graphics.buffer = reinterpret_cast<DrawBuffer>(GetProcAddress(gl, "glDrawBuffer"));
            resolved = true;
        }
    }
    return graphics;
}
inline unsigned char* Scene(void* view) {
    auto* p = static_cast<unsigned char*>(view);
    if (!K1CaptionInk::Readable(p, 0x78)) return nullptr;
    auto* scene = *reinterpret_cast<unsigned char**>(p + 0x70);
    return K1CaptionInk::Readable(scene, 0xD8) ? scene : nullptr;
}
inline void Forget(void* panel) {
    pending.erase(std::remove_if(pending.begin(), pending.end(), [=](const Job& j) { return j.panel == panel; }), pending.end());
    ready.erase(std::remove_if(ready.begin(), ready.end(), [=](const Ready& r) { return r.job.panel == panel; }), ready.end());
}
inline void Queue(void* panel) {
    Forget(panel);
    if (!K1CaptionInk::Readable(panel, sizeof(void*))) return;
    const auto vt = *static_cast<const std::uintptr_t*>(panel);
    const int count = vt == 0x00758020 ? 6 : vt == 0x00752F70 ? 1 : 0;
    const int first = count == 6 ? 0x230 : 0x360;
    for (int i = 0; i < count; ++i) {
        void* view = static_cast<unsigned char*>(panel) + first + i * 0x25C;
        if (K1CaptionInk::Readable(view, sizeof(void*)) && *static_cast<const std::uintptr_t*>(view) == 0x00752E30)
            pending.push_back({panel, view, count == 6 ? "class" : "main-menu"});
    }
}
inline bool Pending() {
    if (!*reinterpret_cast<const int*>(0x0078D1E4)) { pending.clear(); return false; }
    pending.erase(std::remove_if(pending.begin(), pending.end(), [](const Job& j) {
        return !K1CaptionInk::Readable(j.view, 0x48) ||
            !(*reinterpret_cast<const unsigned*>(static_cast<const unsigned char*>(j.view) + 0x44) & 2u);
    }), pending.end());
    return !pending.empty();
}
inline bool Prime(void* view, Draw draw) {
    auto found = std::find_if(pending.begin(), pending.end(), [=](const Job& j) { return j.view == view; });
    if (found == pending.end()) return false;
    auto* scene = Scene(view);
    if (!scene || !*reinterpret_cast<const int*>(0x0078D1E4) || *reinterpret_cast<int*>(scene + 0x50) != 0 ||
        *reinterpret_cast<int*>(scene + 0x58) <= 0) { pending.erase(found); return false; }
    const auto gl = Api();
    if (!gl.context || !gl.get || !gl.buffer || !gl.context()) return false;
    const Job job = *found;
    pending.erase(found);
    int oldBuffer = 0;
    gl.get(0x0C01, &oldBuffer); // GL_DRAW_BUFFER
    auto* effects = reinterpret_cast<int*>(scene + 0xD4);
    auto* frameTime = reinterpret_cast<float*>(0x0078E574);
    struct Restore {
        int* effects; int oldEffects; float* frameTime; float oldTime; DrawBuffer buffer; unsigned oldBuffer;
        ~Restore() { *effects = oldEffects; *frameTime = oldTime; buffer(oldBuffer); }
    } restore{effects, *effects, frameTime, *frameTime, gl.buffer, static_cast<unsigned>(oldBuffer)};
    // Postprocessing can select FRONT/BACK itself. Keep it off in this hidden
    // pass, then restore it before the normal draw. Depth/stencil are cleared by
    // the native GUI scene viewport again for the visible pass.
    *effects = 0;
    *frameTime = 0.0f; // native render-side animation also reads the global delta
    gl.buffer(0); // GL_NONE: no front/back color output
    int target = -1;
    gl.get(0x0C01, &target);
    if (target != 0) return false;
    draw(view, 0.0f);
    gl.get(0x0C01, &target);
    ready.push_back({job, 0, *reinterpret_cast<int*>(scene + 0x50), target == 0});
    return true;
}
inline void AfterDraw(void* view) {
    // Defer diagnostics until after four visible draws, preserving the first
    // three presentations without trace-file writes.
    auto* scene = Scene(view);
    if (!scene || *reinterpret_cast<int*>(scene + 0x50) < 5) return;
    for (auto it = ready.begin(); it != ready.end();) {
        if (it->job.view != view) { ++it; continue; }
        char line[220];
        std::snprintf(line, sizeof line, "model-preload priority=1 kind=%s view=%p renders=%d->%d hidden=%u",
                      it->job.kind, view, it->before, it->primed, it->hidden ? 1u : 0u);
        ControllerLogK1(line);
        it = ready.erase(it);
    }
}
}
