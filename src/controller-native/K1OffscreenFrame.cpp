// The game's frame drawn offscreen and shown only when finished (issue 14, issue 73).
//
// NVIDIA's "Vulkan/OpenGL present method: Prefer layered on DXGI Swapchain" shows the
// window's buffer while the game is still drawing into it: a frame that stalls between
// its clear and its menu shows the bare clear (the white flash), one that stalls inside
// the menu or the world shows it half drawn (reverse-engineering/experiments/
// white-flash-video-capture.md, Part 4, measured 2026-09-18/19). glFinish before every
// swap changed nothing there, so the frame is not shown unfinished by the GPU but by
// the driver presenting the buffer the game draws into. Since 2026-09-19 KMRP's installer
// keeps the game on the native path instead (docs/nvidia-present-method.md), which
// also takes away what that path is chosen for: Windows Auto HDR and NVIDIA RTX HDR for
// an OpenGL game (issue 73).
//
// Since 2026-10-30, always (a standard part of KMRP's engine changes; for one day an
// option, `offscreen-frame`, which KMRP no longer reads), the game draws each frame into a
// framebuffer object of KMRP's, the window's size and sample count, and the window's buffer is written only at SwapBuffers: the
// finished frame is copied in and swapped, and copied again into the next back buffer, so
// whatever the driver shows between two swaps is a finished frame. What keeps the game's
// drawing in KMRP's buffer:
//
//   * SwapBuffers, through the game's import slot 0x0073D00C (K1DC 2.0.0 points the same
//     slot at its own function; whichever is there is called in turn, with the window
//     bound, so K1DC's brightness pass draws into the window as before): copy, swap,
//     copy, bind KMRP's buffer for the next frame.
//   * glBindFramebuffer(EXT), as opengl32's wglGetProcAddress hands it out: binding 0, the
//     window, binds KMRP's buffer instead while the window's context is current. The
//     engine of 2003 binds no framebuffer object; K1DC does, for the effects it draws in
//     place of the engine's ATI render-to-texture, and returns to 0 after each.
//   * wglMakeCurrent: back to the window, KMRP's buffer is bound again; to another
//     surface of the same context (a pbuffer), the window's 0 is.
//
// With anti-aliasing the window's buffer is multisampled, and so is KMRP's, with the same
// number of samples (a multisampled window can only be copied into from a buffer of its own
// count). A multisampled framebuffer object cannot be read from, which the window can: the
// engine copies parts of the frame into textures for its effects. So glCopyTexImage2D,
// glCopyTexSubImage2D and glReadPixels, reading KMRP's buffer, first resolve it into a
// plain one of the same size and read that.
//
// The five opengl32 functions are redirected with the system's hot-patch form (a short
// jump over `mov edi, edi` to a long jump in the five bytes before), only where the two
// bytes are still `8B FF` and the five before are padding: anything else is someone
// else's change, and the option then does nothing but say so in the log.
//
// Seen 2026-10-30 in the maintainer's game (RTX 3080, 3440x1440, anti-aliasing 8, K1DC 2.0.0):
// started on the layered path with this on, menus opened and closed, no flash ("it clearly
// worked"). Not measured frame by frame as issue 14 was; not seen with Windows HDR or RTX
// HDR on (the maintainer's display has no HDR), nor on AMD or Intel.
#include "KmrpOptions.h"
#include <windows.h>
#include <cstdio>
#include <cstring>

void KmrpRuntimeLog(const char* line);

namespace {
using GLenum = unsigned;
using GLuint = unsigned;
using GLint = int;
using GLsizei = int;
using GLbitfield = unsigned;

const GLenum kFramebuffer = 0x8D40, kReadFramebuffer = 0x8CA8, kDrawFramebuffer = 0x8CA9,
             kDrawBinding = 0x8CA6, kReadBinding = 0x8CAA,
             kRenderbuffer = 0x8D41, kColorAttachment0 = 0x8CE0, kDepthAttachment = 0x8D00,
             kStencilAttachment = 0x8D20, kDepth24Stencil8 = 0x88F0, kRgba8 = 0x8058,
             kComplete = 0x8CD5, kSamples = 0x80A9, kScissorTest = 0x0C11,
             kRenderbufferBinding = 0x8CA7, kColorBufferBit = 0x4000, kNearest = 0x2600;

using BindFramebufferFn = void(WINAPI*)(GLenum, GLuint);
using GenFn = void(WINAPI*)(GLsizei, GLuint*);
using BindRenderbufferFn = void(WINAPI*)(GLenum, GLuint);
using RenderbufferStorageFn = void(WINAPI*)(GLenum, GLenum, GLsizei, GLsizei);
using RenderbufferStorageMsFn = void(WINAPI*)(GLenum, GLsizei, GLenum, GLsizei, GLsizei);
using FramebufferRenderbufferFn = void(WINAPI*)(GLenum, GLenum, GLenum, GLuint);
using CheckFn = GLenum(WINAPI*)(GLenum);
using DeleteFn = void(WINAPI*)(GLsizei, const GLuint*);
using BlitFn = void(WINAPI*)(GLint, GLint, GLint, GLint, GLint, GLint, GLint, GLint, GLbitfield, GLenum);
using GetIntegervFn = void(WINAPI*)(GLenum, GLint*);
using IsEnabledFn = unsigned char(WINAPI*)(GLenum);
using CapFn = void(WINAPI*)(GLenum);
using GetProcFn = PROC(WINAPI*)(LPCSTR);
using MakeCurrentFn = BOOL(WINAPI*)(HDC, HGLRC);
using SwapFn = BOOL(WINAPI*)(HDC);
using CurrentContextFn = HGLRC(WINAPI*)();
using CopyTexImageFn = void(WINAPI*)(GLenum, GLint, GLenum, GLint, GLint, GLsizei, GLsizei, GLint);
using CopyTexSubImageFn = void(WINAPI*)(GLenum, GLint, GLint, GLint, GLint, GLint, GLsizei, GLsizei);
using ReadPixelsFn = void(WINAPI*)(GLint, GLint, GLsizei, GLsizei, GLenum, GLenum, void*);

// opengl32's own, past their `mov edi, edi`.
GetProcFn realGetProc = nullptr;
MakeCurrentFn realMakeCurrent = nullptr;
CopyTexImageFn realCopyTexImage = nullptr;
CopyTexSubImageFn realCopyTexSubImage = nullptr;
ReadPixelsFn realReadPixels = nullptr;
SwapFn nextSwap = nullptr;                 // what the import slot held
BindFramebufferFn gameBind = nullptr, gameBindExt = nullptr;   // the driver's, as handed out
BindFramebufferFn bind = nullptr;          // the driver's, for KMRP's own binds
GenFn genFramebuffers = nullptr, genRenderbuffers = nullptr;
BindRenderbufferFn bindRenderbuffer = nullptr;
RenderbufferStorageFn renderbufferStorage = nullptr;
RenderbufferStorageMsFn renderbufferStorageMs = nullptr;
FramebufferRenderbufferFn framebufferRenderbuffer = nullptr;
CheckFn checkStatus = nullptr;
DeleteFn deleteFramebuffers = nullptr, deleteRenderbuffers = nullptr;
BlitFn blit = nullptr;
GetIntegervFn getIntegerv = nullptr;
IsEnabledFn isEnabled = nullptr;
CapFn enable = nullptr, disable = nullptr;
CurrentContextFn currentContext = nullptr;

HGLRC context = nullptr;   // the window's context the buffer was made in
HWND window = nullptr;
GLuint frame = 0, colour = 0, depth = 0;      // KMRP's buffer
GLuint plain = 0, plainColour = 0;            // its resolved copy, when multisampled
int width = 0, height = 0, samples = 0;
bool refused = false;      // incomplete or unavailable: the window draws as before
bool swapping = false;     // inside the swap: K1DC's brightness pass draws into the window itself
unsigned long long swaps = 0, redirected = 0, resolved = 0;

void Log(const char* text)
{
    char line[300];
    sprintf_s(line, "[KMRP] offscreen frame: %s", text);
    KmrpRuntimeLog(line);
}

bool Ours() { return frame && !swapping && currentContext && currentContext() == context; }

// Hot-patch FUNCTION to jump to TARGET; the original continues at FUNCTION + 2.
bool HotPatch(void* function, void* target)
{
    auto at = static_cast<unsigned char*>(function);
    static const unsigned char pad1[5] = { 0xCC, 0xCC, 0xCC, 0xCC, 0xCC }, pad2[5] = { 0x90, 0x90, 0x90, 0x90, 0x90 };
    if (!at || at[0] != 0x8B || at[1] != 0xFF || (std::memcmp(at - 5, pad1, 5) && std::memcmp(at - 5, pad2, 5))) return false;
    DWORD old = 0;
    if (!VirtualProtect(at - 5, 7, PAGE_EXECUTE_READWRITE, &old)) return false;
    at[-5] = 0xE9;
    const long relative = static_cast<long>(reinterpret_cast<unsigned char*>(target) - at);
    std::memcpy(at - 4, &relative, 4);
    const unsigned short shortJump = 0xF9EB;            // EB F9: back 7 bytes, to the long jump
    *reinterpret_cast<volatile unsigned short*>(at) = shortJump;
    VirtualProtect(at - 5, 7, old, &old);
    FlushInstructionCache(GetCurrentProcess(), at - 5, 7);
    return true;
}

bool WindowTarget(GLenum target)
{
    return target == kFramebuffer || target == kDrawFramebuffer || target == kReadFramebuffer;
}

void WINAPI BindForGame(GLenum target, GLuint framebuffer)
{
    if (framebuffer == 0 && !refused && Ours() && WindowTarget(target)) { framebuffer = frame; ++redirected; }
    gameBind(target, framebuffer);
}

void WINAPI BindForGameExt(GLenum target, GLuint framebuffer)
{
    if (framebuffer == 0 && !refused && Ours() && WindowTarget(target)) { framebuffer = frame; ++redirected; }
    gameBindExt(target, framebuffer);
}

PROC WINAPI GetProcForGame(LPCSTR name)
{
    PROC found = realGetProc(name);
    if (!found || !name || reinterpret_cast<ULONG_PTR>(name) < 0x10000) return found;
    if (!std::strcmp(name, "glBindFramebuffer")) {
        gameBind = reinterpret_cast<BindFramebufferFn>(found);
        return reinterpret_cast<PROC>(&BindForGame);
    }
    if (!std::strcmp(name, "glBindFramebufferEXT")) {
        gameBindExt = reinterpret_cast<BindFramebufferFn>(found);
        return reinterpret_cast<PROC>(&BindForGameExt);
    }
    return found;
}

BOOL WINAPI MakeCurrentForGame(HDC dc, HGLRC rc)
{
    const BOOL ok = realMakeCurrent(dc, rc);
    if (ok && rc && rc == context && frame && !refused && bind)
        bind(kFramebuffer, dc && WindowFromDC(dc) == window ? frame : 0);
    return ok;
}

// A read of KMRP's multisampled buffer reads its resolved copy instead. Returns whether it
// did, so the caller binds KMRP's buffer for reading again after.
bool ReadPlain()
{
    if (!samples || !plain || !Ours()) return false;
    GLint reading = 0, drawing = 0;
    getIntegerv(kReadBinding, &reading);
    if (static_cast<GLuint>(reading) != frame) return false;
    getIntegerv(kDrawBinding, &drawing);
    const bool scissor = isEnabled(kScissorTest) != 0;
    if (scissor) disable(kScissorTest);
    bind(kDrawFramebuffer, plain);
    blit(0, 0, width, height, 0, 0, width, height, kColorBufferBit, kNearest);
    if (scissor) enable(kScissorTest);
    bind(kDrawFramebuffer, static_cast<GLuint>(drawing));
    bind(kReadFramebuffer, plain);
    ++resolved;
    return true;
}

void WINAPI CopyTexImageForGame(GLenum target, GLint level, GLenum format, GLint x, GLint y, GLsizei w, GLsizei h, GLint border)
{
    const bool swapped = ReadPlain();
    realCopyTexImage(target, level, format, x, y, w, h, border);
    if (swapped) bind(kReadFramebuffer, frame);
}

void WINAPI CopyTexSubImageForGame(GLenum target, GLint level, GLint dx, GLint dy, GLint x, GLint y, GLsizei w, GLsizei h)
{
    const bool swapped = ReadPlain();
    realCopyTexSubImage(target, level, dx, dy, x, y, w, h);
    if (swapped) bind(kReadFramebuffer, frame);
}

void WINAPI ReadPixelsForGame(GLint x, GLint y, GLsizei w, GLsizei h, GLenum format, GLenum type, void* pixels)
{
    const bool swapped = ReadPlain();
    realReadPixels(x, y, w, h, format, type, pixels);
    if (swapped) bind(kReadFramebuffer, frame);
}

template <typename T> bool Resolve(T& out, const char* name)
{
    out = reinterpret_cast<T>(realGetProc(name));
    return out != nullptr;
}

void Delete()
{
    const GLuint framebuffers[2] = { frame, plain }, renderbuffers[3] = { colour, depth, plainColour };
    deleteFramebuffers(plain ? 2 : 1, framebuffers);
    deleteRenderbuffers(plainColour ? 3 : 2, renderbuffers);
    frame = colour = depth = plain = plainColour = 0;
}

void Storage(GLuint renderbuffer, GLenum format, int count)
{
    bindRenderbuffer(kRenderbuffer, renderbuffer);
    if (count > 0) renderbufferStorageMs(kRenderbuffer, count, format, width, height);
    else renderbufferStorage(kRenderbuffer, format, width, height);
}

void Refuse(const char* text)
{
    if (frame) Delete();
    refused = true;
    Log(text);
}

// KMRP's buffer for the window's client area, in the current context. False: not used.
bool Make(HDC dc)
{
    if (refused) return false;
    RECT client{};
    HWND owner = WindowFromDC(dc);
    if (!owner || !GetClientRect(owner, &client) || client.right <= 0 || client.bottom <= 0) return false;
    const HGLRC now = currentContext();
    if (frame && now == context && owner == window && client.right == width && client.bottom == height) return true;
    if (!bind && !(Resolve(bind, "glBindFramebufferEXT") && Resolve(genFramebuffers, "glGenFramebuffersEXT") &&
                   Resolve(genRenderbuffers, "glGenRenderbuffersEXT") && Resolve(bindRenderbuffer, "glBindRenderbufferEXT") &&
                   Resolve(renderbufferStorage, "glRenderbufferStorageEXT") &&
                   Resolve(framebufferRenderbuffer, "glFramebufferRenderbufferEXT") &&
                   Resolve(checkStatus, "glCheckFramebufferStatusEXT") && Resolve(deleteFramebuffers, "glDeleteFramebuffersEXT") &&
                   Resolve(deleteRenderbuffers, "glDeleteRenderbuffersEXT") && Resolve(blit, "glBlitFramebufferEXT"))) {
        bind = nullptr;
        refused = true;
        Log("the driver lacks EXT_framebuffer_object or EXT_framebuffer_blit; the window is drawn into as before");
        return false;
    }
    // The window's own sample count, read with the window bound.
    bind(kFramebuffer, 0);
    GLint count = 0;
    getIntegerv(kSamples, &count);
    if (count > 0 && !renderbufferStorageMs && !Resolve(renderbufferStorageMs, "glRenderbufferStorageMultisampleEXT")) {
        Refuse("anti-aliasing is on and the driver lacks EXT_framebuffer_multisample; the window is drawn into as before");
        return false;
    }
    // The same context at a new size keeps nothing; a new context (the game made its window
    // again) has none of the old objects to delete.
    if (frame && now == context) Delete();
    frame = colour = depth = plain = plainColour = 0;
    width = client.right;
    height = client.bottom;
    samples = count;
    GLint previous = 0;
    getIntegerv(kRenderbufferBinding, &previous);
    genFramebuffers(1, &frame);
    genRenderbuffers(1, &colour);
    genRenderbuffers(1, &depth);
    Storage(colour, kRgba8, samples);
    Storage(depth, kDepth24Stencil8, samples);
    if (samples) {
        genFramebuffers(1, &plain);
        genRenderbuffers(1, &plainColour);
        Storage(plainColour, kRgba8, 0);
    }
    bindRenderbuffer(kRenderbuffer, static_cast<GLuint>(previous));
    bind(kFramebuffer, frame);
    framebufferRenderbuffer(kFramebuffer, kColorAttachment0, kRenderbuffer, colour);
    framebufferRenderbuffer(kFramebuffer, kDepthAttachment, kRenderbuffer, depth);
    framebufferRenderbuffer(kFramebuffer, kStencilAttachment, kRenderbuffer, depth);
    GLenum status = checkStatus(kFramebuffer);
    GLint got = 0;
    getIntegerv(kSamples, &got);
    if (status == kComplete && plain) {
        bind(kFramebuffer, plain);
        framebufferRenderbuffer(kFramebuffer, kColorAttachment0, kRenderbuffer, plainColour);
        status = checkStatus(kFramebuffer);
    }
    bind(kFramebuffer, 0);
    char text[200];
    if (status != kComplete) {
        sprintf_s(text, "the buffer is incomplete (0x%X); the window is drawn into as before", status);
        Refuse(text);
        return false;
    }
    if (got != samples) {
        sprintf_s(text, "the driver gave %d samples for the window's %d; the window is drawn into as before", got, samples);
        Refuse(text);
        return false;
    }
    context = now;
    window = owner;
    sprintf_s(text, "on, %dx%d, %d samples: each frame is drawn offscreen and shown when finished", width, height, samples);
    Log(text);
    return true;
}

// KMRP's buffer copied into the window's current back buffer.
void Show()
{
    const bool scissor = isEnabled(kScissorTest) != 0;
    if (scissor) disable(kScissorTest);
    bind(kReadFramebuffer, frame);
    bind(kDrawFramebuffer, 0);
    blit(0, 0, width, height, 0, 0, width, height, kColorBufferBit, kNearest);
    bind(kFramebuffer, 0);
    if (scissor) enable(kScissorTest);
}

BOOL WINAPI SwapForGame(HDC dc)
{
    // The frame just drawn was drawn into KMRP's buffer when it is bound in this context.
    const bool drawnOffscreen = Ours() && WindowFromDC(dc) == window;
    if (drawnOffscreen) Show();
    swapping = true;
    const BOOL ok = nextSwap(dc);
    swapping = false;
    ++swaps;
    if (!refused && currentContext && currentContext() && Make(dc)) {
        // The next back buffer holds the frame just shown too, so an early present of it
        // shows a finished frame; then the game draws the next one offscreen.
        if (drawnOffscreen) Show();
        bind(kFramebuffer, frame);
    }
    if (KmrpDebugLevel() >= 2 && swaps % 600 == 0) {
        char text[200];
        sprintf_s(text, "%llu swaps, %llu binds of the window redirected to KMRP's buffer, %llu reads resolved",
                  swaps, redirected, resolved);
        Log(text);
    }
    return ok;
}

template <typename T> bool Patch(HMODULE gl, const char* name, T wrapper, T& real)
{
    auto function = reinterpret_cast<unsigned char*>(GetProcAddress(gl, name));
    if (!function || !HotPatch(function, reinterpret_cast<void*>(wrapper))) return false;
    real = reinterpret_cast<T>(function + 2);
    return true;
}
}

// Installed from DllMain, before the game makes its window or anything asks the driver
// for a function.
void KmrpInstallOffscreenFrame()
{
    HMODULE gl = GetModuleHandleW(L"opengl32.dll");
    if (!gl) { Log("opengl32.dll is not loaded; not used"); return; }
    getIntegerv = reinterpret_cast<GetIntegervFn>(GetProcAddress(gl, "glGetIntegerv"));
    isEnabled = reinterpret_cast<IsEnabledFn>(GetProcAddress(gl, "glIsEnabled"));
    enable = reinterpret_cast<CapFn>(GetProcAddress(gl, "glEnable"));
    disable = reinterpret_cast<CapFn>(GetProcAddress(gl, "glDisable"));
    currentContext = reinterpret_cast<CurrentContextFn>(GetProcAddress(gl, "wglGetCurrentContext"));
    auto slot = reinterpret_cast<SwapFn*>(0x0073D00C);
    MEMORY_BASIC_INFORMATION info{};
    HMODULE holder = nullptr;   // the slot must already hold a function of a loaded module
    if (!getIntegerv || !isEnabled || !enable || !disable || !currentContext ||
        !VirtualQuery(slot, &info, sizeof info) || info.State != MEM_COMMIT || !*slot ||
        !GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                            reinterpret_cast<LPCWSTR>(*slot), &holder)) {
        Log("the functions it needs are not there; not used");
        return;
    }
    // The copies first: once wglGetProcAddress is redirected the buffer can be made, and a
    // multisampled one must never be read unresolved.
    if (!Patch(gl, "glCopyTexImage2D", &CopyTexImageForGame, realCopyTexImage) ||
        !Patch(gl, "glCopyTexSubImage2D", &CopyTexSubImageForGame, realCopyTexSubImage) ||
        !Patch(gl, "glReadPixels", &ReadPixelsForGame, realReadPixels)) {
        // A redirected copy is harmless: it only resolves while KMRP's buffer exists, which
        // it now never will.
        Log("opengl32's copy functions are already changed by something else; not used");
        return;
    }
    if (!Patch(gl, "wglGetProcAddress", &GetProcForGame, realGetProc)) {
        Log("opengl32's wglGetProcAddress is already changed by something else; not used");
        return;
    }
    if (!Patch(gl, "wglMakeCurrent", &MakeCurrentForGame, realMakeCurrent))
        Log("opengl32's wglMakeCurrent is already changed by something else; a pbuffer would be drawn into KMRP's buffer");
    DWORD old = 0;
    if (!VirtualProtect(slot, sizeof *slot, PAGE_READWRITE, &old)) { Log("the SwapBuffers slot cannot be written; not used"); return; }
    nextSwap = *slot;
    *slot = &SwapForGame;
    VirtualProtect(slot, sizeof *slot, old, &old);
}
