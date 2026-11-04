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
//   * SwapBuffers, through the game's import slot 0x0073D00C: copy, swap, copy, bind KMRP's
//     buffer for the next frame. K1DC 2.0.0 points the same slot at its own function, later
//     than this, at the end of InitExtensions, so K1DC's runs first and calls this one: its
//     brightness pass reads and draws KMRP's buffer, the reads resolved below, and is in the
//     frame this copies. Either order works, as whatever the slot held is called in turn.
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
// The six opengl32 functions are redirected with the system's hot-patch form (a short
// jump over `mov edi, edi` to a long jump in the five bytes before), only where the two
// bytes are still `8B FF` and the five before are padding: anything else is someone
// else's change, and the option then does nothing but say so in the log.
//
// Under Wine and Proton (issue 93, 2026-11-04) opengl32 has no such entries, so the same six
// are taken where they are called from instead: the import slots of the game and of every
// module in its folder that still hold opengl32's own function, and those modules' own
// GetProcAddress, which then answers with KMRP's for these six names on opengl32. That reaches
// K1DC too, which imports no GL: it finds opengl32 from the game's glEnable slot and asks it
// with GetProcAddress (its gl_loader.rs), and it later points the game's wglMakeCurrent,
// glDrawBuffer and SwapBuffers slots at its own functions, which call what the slots held.
// Taken once from DllMain and once more at the game's first wglMakeCurrent, for a patch
// loaded after this one; a slot holding anything else is someone else's and stays. Without
// the game's own slots for the copies and wglGetProcAddress, every slot taken is put back.
// `import-slots=1` in [Offscreen] of configs\kmrp.ini takes this path on Windows, to test it.
//
// If it goes wrong on a driver: a copy to the window that the driver refuses is seen on the
// first frame shown (glGetError) and the window is drawn into as before; and `window-drawn=1`
// in a section of its own, [Offscreen], of configs\kmrp.ini, which the installer leaves alone,
// keeps it out altogether (audit GFX-04, 2026-11-01). No player has needed either.
//
// Seen 2026-10-30 in the maintainer's game (RTX 3080, 3440x1440, anti-aliasing 8, K1DC 2.0.0):
// started on the layered path with this on, menus opened and closed, no flash ("it clearly
// worked"). Not measured frame by frame as issue 14 was; not seen with Windows HDR or RTX
// HDR on (the maintainer's display has no HDR), nor on AMD or Intel.
#include "KmrpOptions.h"
#include <windows.h>
#include <psapi.h>
#include <cstdio>
#include <cstring>
#include "K1RuntimeEngine.h"


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
using GetErrorFn = GLenum(WINAPI*)();
using DrawBufferFn = void(WINAPI*)(GLenum);

// opengl32's own, past their `mov edi, edi` (or whole, taken at the import slots).
GetProcFn realGetProc = nullptr;
MakeCurrentFn realMakeCurrent = nullptr;
CopyTexImageFn realCopyTexImage = nullptr;
CopyTexSubImageFn realCopyTexSubImage = nullptr;
ReadPixelsFn realReadPixels = nullptr;
DrawBufferFn realDrawBuffer = nullptr;
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
GetErrorFn getError = nullptr;

HGLRC context = nullptr;   // the window's context the buffer was made in
HWND window = nullptr;
GLuint frame = 0, colour = 0, depth = 0;      // KMRP's buffer
GLuint plain = 0, plainColour = 0;            // its resolved copy, when multisampled
int width = 0, height = 0, samples = 0;
bool refused = false;      // incomplete or unavailable: the window draws as before
bool swapping = false;     // inside the swap the slot held, with the window bound
bool checkedShow = false;  // this buffer's first copy to the window has been checked
unsigned long long swaps = 0, redirected = 0, resolved = 0;

// A line too long for sprintf_s's buffer ends the process (its invalid-parameter handler, with no
// crash dump): a GL error line of 600 characters ended the game at its first error
// (2026-11-04). Cut instead.
void Log(const char* text)
{
    char line[1024];
    _snprintf_s(line, sizeof line, _TRUNCATE, "[KMRP] offscreen frame: %s", text);
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

void WINAPI CopyTexImageForGame(GLenum, GLint, GLenum, GLint, GLint, GLsizei, GLsizei, GLint);
void WINAPI CopyTexSubImageForGame(GLenum, GLint, GLint, GLint, GLint, GLint, GLsizei, GLsizei);
void WINAPI ReadPixelsForGame(GLint, GLint, GLsizei, GLsizei, GLenum, GLenum, void*);

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

void WatchGlErrors(HGLRC rc);

PROC WINAPI GetProcForGame(LPCSTR name)
{
    PROC found = realGetProc(name);
    if (const HGLRC current = currentContext ? currentContext() : nullptr) WatchGlErrors(current);
    if (!found || !name || reinterpret_cast<ULONG_PTR>(name) < 0x10000) return found;
    if (!std::strcmp(name, "glBindFramebuffer")) {
        gameBind = reinterpret_cast<BindFramebufferFn>(found);
        return reinterpret_cast<PROC>(&BindForGame);
    }
    if (!std::strcmp(name, "glBindFramebufferEXT")) {
        gameBindExt = reinterpret_cast<BindFramebufferFn>(found);
        return reinterpret_cast<PROC>(&BindForGameExt);
    }
    // K1DC asks here first even for core functions, and NVIDIA answers with the driver's own,
    // past opengl32's redirection below. Its brightness pass then copied KMRP's multisampled
    // buffer unresolved, was refused, and drew a blank texture: a black screen at any brightness
    // but the default, with anti-aliasing on (2026-11-02).
    // A workaround for K1DC: remove these three lines once Synchro's K1DC reads core functions
    // from opengl32 first, or copies a multisampled framebuffer through a resolved one.
    if (!std::strcmp(name, "glCopyTexImage2D")) return reinterpret_cast<PROC>(&CopyTexImageForGame);
    if (!std::strcmp(name, "glCopyTexSubImage2D")) return reinterpret_cast<PROC>(&CopyTexSubImageForGame);
    if (!std::strcmp(name, "glReadPixels")) return reinterpret_cast<PROC>(&ReadPixelsForGame);
    return found;
}

// " name+offset" for ADDRESS, added to TEXT at USED.
int NameAddress(char* text, std::size_t size, int used, const void* address)
{
    HMODULE module = nullptr;
    char name[MAX_PATH] = "?";
    if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                           static_cast<const char*>(address), &module))
        GetModuleFileNameA(module, name, MAX_PATH);
    const char* const slash = std::strrchr(name, '\\');
    const int added = sprintf_s(text + used, size - used, " %s+%lX", slash ? slash + 1 : name,
                                static_cast<unsigned long>(static_cast<const char*>(address) - reinterpret_cast<char*>(module)));
    return added > 0 ? used + added : used;
}

// The game's folder's modules, as address ranges with their names, for reading return addresses
// off the stack. Listed before the driver is asked to report errors, never in its callback: the
// module list and file names wait on the loader's lock, and a thread holding that lock while it
// waited on the driver froze the game at its first error (2026-11-04).
struct Range {
    ULONG_PTR base, from, to;
    char name[48];
};
Range ranges[32] = {};
int rangeCount = 0;

void ListGameModules()
{
    rangeCount = 0;
    wchar_t folder[MAX_PATH];
    HMODULE modules[256];
    DWORD bytes = 0;
    if (!KmrpGameFolder(folder) || !K32EnumProcessModules(GetCurrentProcess(), modules, sizeof modules, &bytes)) return;
    const std::size_t length = std::wcslen(folder);
    for (DWORD i = 0; i < bytes / sizeof(HMODULE) && i < ARRAYSIZE(modules) && rangeCount < ARRAYSIZE(ranges); ++i) {
        wchar_t path[MAX_PATH];
        MODULEINFO info{};
        const DWORD named = GetModuleFileNameW(modules[i], path, MAX_PATH);
        if (!named || named >= MAX_PATH || named <= length || _wcsnicmp(path, folder, length) || path[length] != L'\\' ||
            !K32GetModuleInformation(GetCurrentProcess(), modules[i], &info, sizeof info))
            continue;
        Range& range = ranges[rangeCount++];
        range.base = reinterpret_cast<ULONG_PTR>(info.lpBaseOfDll);
        range.from = range.base + 0x1000;
        range.to = range.base + info.SizeOfImage;
        const wchar_t* slash = std::wcsrchr(path, L'\\');
        sprintf_s(range.name, "%.40ls", slash ? slash + 1 : path);
    }
}

const Range* GameModuleAt(ULONG_PTR address)
{
    for (int i = 0; i < rangeCount; ++i)
        if (address >= ranges[i].from && address < ranges[i].to) return &ranges[i];
    return nullptr;
}

// Whether VALUE, in a module of the game's folder, points just past a call: E8 rel32, or FF /2
// through a register, memory or a slot. A page of a module that cannot be read (a protector's)
// is no call.
bool AfterCall(ULONG_PTR value)
{
    if (!GameModuleAt(value)) return false;
    __try {
        const auto code = reinterpret_cast<const unsigned char*>(value);
        return code[-5] == 0xE8 || code[-6] == 0xFF || code[-2] == 0xFF || code[-3] == 0xFF;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

// What KMRP's own frame was doing when the driver raised an error: null when it was not
// drawing, so the call was the game's, K1DC's or another patch's.
const char* busy = nullptr;

// With debug logs at level 2: every error the driver raises, in its own words, with the modules
// and offsets that called it, from the first GL call of a context. K1DC's log says only that a
// pass ended with INVALID_OPERATION, and it cannot name the call.
//
// Under Proton the callback runs with only Wine's frames above it, so the walk names nothing of
// the caller (`ntdll.dll+48319`, 2026-11-04). The caller's return addresses are still on this
// thread's stack further up: the first eight values there that point just past a call into a
// module of the game's folder are named too, which is what a stack walk would have named, with
// perhaps a stale one among them. With what KMRP's frame was doing, and the swap.
void WINAPI GlErrorMessage(GLenum, GLenum type, GLuint id, GLenum, GLsizei, const char* message, const void*)
{
    static int left = 30;
    if (type != 0x824C || left <= 0) return;    // GL_DEBUG_TYPE_ERROR
    --left;
    char text[900];
    int used = sprintf_s(text, "GL error 0x%X: %.300s; swap %llu, %s; from", id, message ? message : "", swaps,
                         busy ? busy : "not in KMRP's frame");
    void* frames[10] = {};
    const USHORT count = RtlCaptureStackBackTrace(1, 10, frames, nullptr);
    for (USHORT i = 0; i < count && used > 0 && used < 560; ++i)
        used = NameAddress(text, sizeof text, used, frames[i]);
    if (used > 0 && used < 600) used += sprintf_s(text + used, sizeof text - used, "; on the stack");
    // Only on this thread's own stack, and at most 64 KB of it: a driver may call this on a stack
    // of its own, where reading on up to the thread's would leave mapped memory.
    const NT_TIB* tib = reinterpret_cast<const NT_TIB*>(NtCurrentTeb());
    const auto here = reinterpret_cast<const ULONG_PTR*>(&tib);
    const auto top = static_cast<const ULONG_PTR*>(tib->StackBase);
    if (here >= static_cast<const ULONG_PTR*>(tib->StackLimit) && here < top) {
        const auto end = top - here > 16384 ? here + 16384 : top;
        int named = 0;
        for (auto at = here; at < end && named < 8 && used > 0 && used < 820; ++at) {
            if (!AfterCall(*at)) continue;
            const Range* module = GameModuleAt(*at);
            const int added = sprintf_s(text + used, sizeof text - used, " %s+%lX", module->name,
                                        static_cast<unsigned long>(*at - module->base));
            if (added > 0) used += added;
            ++named;
        }
    }
    Log(text);
}

void WatchGlErrors(HGLRC rc)
{
    static HGLRC watched = nullptr;
    if (rc == watched || KmrpDebugLevel() < 2 || !enable) return;
    watched = rc;
    using CallbackFn = void(WINAPI*)(GLenum, GLenum, GLuint, GLenum, GLsizei, const char*, const void*);
    using SetCallbackFn = void(WINAPI*)(CallbackFn, const void*);
    const auto set = reinterpret_cast<SetCallbackFn>(realGetProc("glDebugMessageCallback"));
    if (!set) { Log("the driver has no glDebugMessageCallback; GL errors are not named"); return; }
    ListGameModules();
    enable(0x92E0);     // GL_DEBUG_OUTPUT
    enable(0x8242);     // GL_DEBUG_OUTPUT_SYNCHRONOUS: on the calling thread, so the stack is the caller's
    set(&GlErrorMessage, nullptr);
    Log("GL errors are named here from now on");
}

void TakeImports();
bool takeAgain = false;    // taken at the import slots: once more at the game's first wglMakeCurrent

BOOL WINAPI MakeCurrentForGame(HDC dc, HGLRC rc)
{
    if (takeAgain) { takeAgain = false; TakeImports(); }
    const BOOL ok = realMakeCurrent(dc, rc);
    if (ok && rc && rc == context && frame && !refused && bind)
        bind(kFramebuffer, dc && WindowFromDC(dc) == window ? frame : 0);
    return ok;
}

// Names KMRP's own GL work for the error log while it runs.
struct Busy {
    const char* was;
    explicit Busy(const char* what) : was(busy) { busy = what; }
    ~Busy() { busy = was; }
};

// A read of KMRP's multisampled buffer reads its resolved copy instead. Returns whether it
// did, so the caller binds KMRP's buffer for reading again after.
bool ReadPlain()
{
    if (!samples || !plain || !Ours()) return false;
    Busy marked("resolving a read of its buffer");
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

// The game asks for the back or front buffer through a frame (0x0042CB34, and more), which a
// framebuffer object does not have: with KMRP's bound the driver refused every one with
// INVALID_OPERATION, found with the error log above on 2026-11-02. K1DC translates these only for
// its own targets and passes the rest on. On KMRP's buffer they mean its one colour attachment.
void WINAPI DrawBufferForGame(GLenum mode)
{
    if ((mode == 0x0404 || mode == 0x0405) && Ours()) {     // GL_FRONT, GL_BACK
        GLint drawing = 0;
        getIntegerv(kDrawBinding, &drawing);
        if (static_cast<GLuint>(drawing) == frame) mode = kColorAttachment0;
    }
    realDrawBuffer(mode);
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
    Busy marked("making its buffer");
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
    checkedShow = false;
    sprintf_s(text, "on, %dx%d, %d samples: each frame is drawn offscreen and shown when finished", width, height, samples);
    Log(text);
    return true;
}

// KMRP's buffer copied into the window's current back buffer. The first copy of each buffer
// is checked: a multisampled copy into the window has run only on NVIDIA, and a driver that
// refused it would leave the screen black with nothing to say why. Only on that one frame,
// as glGetError can stall a driver, and errors the game left are cleared first.
void Show()
{
    Busy marked("copying its buffer to the window");
    const bool check = !checkedShow && getError;
    if (check) {
        checkedShow = true;
        for (int left = 16; left > 0 && getError(); --left) {}
    }
    const bool scissor = isEnabled(kScissorTest) != 0;
    if (scissor) disable(kScissorTest);
    bind(kReadFramebuffer, frame);
    bind(kDrawFramebuffer, 0);
    blit(0, 0, width, height, 0, 0, width, height, kColorBufferBit, kNearest);
    bind(kFramebuffer, 0);
    if (scissor) enable(kScissorTest);
    if (check) {
        if (const GLenum error = getError()) {
            char text[120];
            sprintf_s(text, "the driver refused the copy to the window (0x%X); the window is drawn into as before", error);
            Refuse(text);
        }
    }
}

BOOL WINAPI SwapForGame(HDC dc)
{
    // The frame just drawn was drawn into KMRP's buffer when it is bound in this context. Bound,
    // not only made: the game may have left something else bound at the swap (audit GFX-05).
    GLint drawing = 0;
    if (Ours()) getIntegerv(kDrawBinding, &drawing);
    const bool drawnOffscreen = Ours() && WindowFromDC(dc) == window && static_cast<GLuint>(drawing) == frame;
    if (drawnOffscreen) Show();
    swapping = true;
    BOOL ok;
    {
        Busy marked("in the SwapBuffers the slot held");
        ok = nextSwap(dc);
    }
    swapping = false;
    ++swaps;
    if (!refused && currentContext && currentContext() && Make(dc)) {
        // The next back buffer holds the frame just shown too, so an early present of it
        // shows a finished frame; then the game draws the next one offscreen.
        if (drawnOffscreen) Show();
        if (!refused) bind(kFramebuffer, frame);
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
    if (!function) return false;
    // Before the jump goes live: on Steam the game's thread is running (audit GFX-02).
    real = reinterpret_cast<T>(function + 2);
    if (HotPatch(function, reinterpret_cast<void*>(wrapper))) return true;
    real = nullptr;
    return false;
}

void LogNotPatched(const char* functions, const char* outcome)
{
    char text[200];
    sprintf_s(text, "opengl32's %s: already changed by something else; %s", functions, outcome);
    Log(text);
}

// Taken at the import slots (see the header): each function, opengl32's own, and KMRP's.
struct Taken {
    const char* name;
    void* genuine;
    void* wrapper;
};
Taken taken[6] = {};
HMODULE opengl = nullptr;
decltype(&GetProcAddress) realGetProcAddress = nullptr;
// Every slot taken and what it held, to put back when the game's own could not be taken.
struct Held {
    void** slot;
    void* was;
};
Held held[96] = {};
int heldCount = 0;

FARPROC WINAPI GetProcAddressForGame(HMODULE module, LPCSTR name)
{
    if (module && module == opengl && name && reinterpret_cast<ULONG_PTR>(name) >= 0x10000)
        for (const Taken& each : taken)
            if (!std::strcmp(name, each.name)) return reinterpret_cast<FARPROC>(each.wrapper);
    return realGetProcAddress(module, name);
}

bool WriteSlot(void** slot, void* value)
{
    DWORD old = 0;
    if (!VirtualProtect(slot, sizeof *slot, PAGE_READWRITE, &old)) return false;
    *slot = value;
    VirtualProtect(slot, sizeof *slot, old, &old);
    return true;
}

// The slots of MODULE's import tables that hold one of opengl32's six or GetProcAddress, now
// KMRP's. Returns how many.
int TakeSlots(HMODULE module)
{
    auto base = reinterpret_cast<unsigned char*>(module);
    const auto dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(base);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) return 0;
    const auto nt = reinterpret_cast<const IMAGE_NT_HEADERS*>(base + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE) return 0;
    const IMAGE_DATA_DIRECTORY& imports = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
    if (!imports.VirtualAddress || !imports.Size) return 0;
    int count = 0;
    for (auto entry = reinterpret_cast<const IMAGE_IMPORT_DESCRIPTOR*>(base + imports.VirtualAddress); entry->Name; ++entry) {
        for (auto slot = reinterpret_cast<void**>(base + entry->FirstThunk); *slot; ++slot) {
            void* wrapper = *slot == reinterpret_cast<void*>(realGetProcAddress) ? reinterpret_cast<void*>(&GetProcAddressForGame) : nullptr;
            for (const Taken& each : taken)
                if (*slot == each.genuine) wrapper = each.wrapper;
            if (!wrapper || heldCount == ARRAYSIZE(held)) continue;
            void* const was = *slot;
            if (!WriteSlot(slot, wrapper)) continue;
            held[heldCount++] = { slot, was };
            ++count;
        }
    }
    return count;
}

// The game's and every module's in its folder, as they are now loaded.
void TakeImports()
{
    wchar_t folder[MAX_PATH];
    HMODULE modules[256];
    DWORD bytes = 0;
    if (!KmrpGameFolder(folder) || !K32EnumProcessModules(GetCurrentProcess(), modules, sizeof modules, &bytes)) return;
    const std::size_t length = std::wcslen(folder);
    int slots = 0, owners = 0;
    for (DWORD i = 0; i < bytes / sizeof(HMODULE) && i < ARRAYSIZE(modules); ++i) {
        wchar_t path[MAX_PATH];
        const DWORD named = GetModuleFileNameW(modules[i], path, MAX_PATH);
        if (!named || named >= MAX_PATH || named <= length || _wcsnicmp(path, folder, length) || path[length] != L'\\') continue;
        if (const int count = TakeSlots(modules[i])) { slots += count; ++owners; }
    }
    if (slots) {
        char text[160];
        sprintf_s(text, "%d import slots in %d modules of the game's folder now call KMRP's", slots, owners);
        Log(text);
    }
}

// The game's import slot for opengl32's NAME holds KMRP's function.
bool GameSlotTaken(const char* name)
{
    const auto base = reinterpret_cast<const unsigned char*>(GetModuleHandleW(nullptr));
    const auto nt = reinterpret_cast<const IMAGE_NT_HEADERS*>(base + reinterpret_cast<const IMAGE_DOS_HEADER*>(base)->e_lfanew);
    for (int i = 0; i < heldCount; ++i)
        for (const Taken& each : taken)
            if (!std::strcmp(each.name, name) && held[i].was == each.genuine &&
                static_cast<ULONG_PTR>(reinterpret_cast<const unsigned char*>(held[i].slot) - base) < nt->OptionalHeader.SizeOfImage)
                return true;
    return false;
}

// Under Wine: the six at the import slots. False, with every slot put back, when the game's own
// for the copies and wglGetProcAddress could not be taken.
bool TakeAtImports(HMODULE gl)
{
    opengl = gl;
    realGetProcAddress = &GetProcAddress;
    const Taken six[6] = {
        { "glCopyTexImage2D", nullptr, reinterpret_cast<void*>(&CopyTexImageForGame) },
        { "glCopyTexSubImage2D", nullptr, reinterpret_cast<void*>(&CopyTexSubImageForGame) },
        { "glReadPixels", nullptr, reinterpret_cast<void*>(&ReadPixelsForGame) },
        { "glDrawBuffer", nullptr, reinterpret_cast<void*>(&DrawBufferForGame) },
        { "wglGetProcAddress", nullptr, reinterpret_cast<void*>(&GetProcForGame) },
        { "wglMakeCurrent", nullptr, reinterpret_cast<void*>(&MakeCurrentForGame) },
    };
    for (int i = 0; i < 6; ++i) {
        taken[i] = six[i];
        taken[i].genuine = reinterpret_cast<void*>(GetProcAddress(gl, six[i].name));
        if (!taken[i].genuine) return false;
    }
    // Before any slot goes live: the game's thread may be running (audit GFX-02).
    realCopyTexImage = reinterpret_cast<CopyTexImageFn>(taken[0].genuine);
    realCopyTexSubImage = reinterpret_cast<CopyTexSubImageFn>(taken[1].genuine);
    realReadPixels = reinterpret_cast<ReadPixelsFn>(taken[2].genuine);
    realDrawBuffer = reinterpret_cast<DrawBufferFn>(taken[3].genuine);
    realGetProc = reinterpret_cast<GetProcFn>(taken[4].genuine);
    realMakeCurrent = reinterpret_cast<MakeCurrentFn>(taken[5].genuine);
    TakeImports();
    if (GameSlotTaken("glCopyTexImage2D") && GameSlotTaken("glCopyTexSubImage2D") && GameSlotTaken("glReadPixels") &&
        GameSlotTaken("wglGetProcAddress")) {
        if (!GameSlotTaken("glDrawBuffer")) LogNotPatched("glDrawBuffer", "the driver will refuse the game's own requests");
        if (!GameSlotTaken("wglMakeCurrent")) LogNotPatched("wglMakeCurrent", "a pbuffer would be drawn into KMRP's buffer");
        else takeAgain = true;
        return true;
    }
    while (heldCount > 0) {
        --heldCount;
        WriteSlot(held[heldCount].slot, held[heldCount].was);
    }
    return false;
}
}

// Installed from DllMain, before the game makes its window or anything asks the driver
// for a function.
void KmrpInstallOffscreenFrame()
{
    wchar_t options[MAX_PATH];
    const bool named = KmrpGamePath(options, L"configs\\kmrp.ini");
    // With window-drawn=1 the frame stays out. At debug logs 2 its functions are taken all the
    // same and the buffer is never made, so GL errors are named without the frame too: under
    // Proton the only way to tell whether an error comes from it (issue 93, 2026-11-04).
    const bool windowDrawn = named && GetPrivateProfileIntW(L"Offscreen", L"window-drawn", 0, options) != 0;
    if (windowDrawn && KmrpDebugLevel() < 2) {
        Log("window-drawn=1 in configs\\kmrp.ini: not used");
        return;
    }
    const HMODULE ntdll = GetModuleHandleW(L"ntdll.dll");
    const bool wine = ntdll && GetProcAddress(ntdll, "wine_get_version");
    const bool atImports = wine || (named && GetPrivateProfileIntW(L"Offscreen", L"import-slots", 0, options) != 0);
    HMODULE gl = GetModuleHandleW(L"opengl32.dll");
    if (!gl) { Log("opengl32.dll is not loaded; not used"); return; }
    getIntegerv = reinterpret_cast<GetIntegervFn>(GetProcAddress(gl, "glGetIntegerv"));
    isEnabled = reinterpret_cast<IsEnabledFn>(GetProcAddress(gl, "glIsEnabled"));
    enable = reinterpret_cast<CapFn>(GetProcAddress(gl, "glEnable"));
    disable = reinterpret_cast<CapFn>(GetProcAddress(gl, "glDisable"));
    currentContext = reinterpret_cast<CurrentContextFn>(GetProcAddress(gl, "wglGetCurrentContext"));
    getError = reinterpret_cast<GetErrorFn>(GetProcAddress(gl, "glGetError"));
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
    if (atImports) {
        if (!TakeAtImports(gl)) {
            Log("the game's own opengl32 imports could not be taken; not used, the game draws to the window");
            return;
        }
        Log(wine ? "under Wine or Proton: opengl32 is reached at the import slots"
                 : "import-slots=1 in configs\\kmrp.ini: opengl32 is reached at the import slots, as under Wine");
    } else {
        // The copies first: once wglGetProcAddress is redirected the buffer can be made, and a
        // multisampled one must never be read unresolved.
        if (!Patch(gl, "glCopyTexImage2D", &CopyTexImageForGame, realCopyTexImage) ||
            !Patch(gl, "glCopyTexSubImage2D", &CopyTexSubImageForGame, realCopyTexSubImage) ||
            !Patch(gl, "glReadPixels", &ReadPixelsForGame, realReadPixels)) {
            // A redirected copy is harmless: it only resolves while KMRP's buffer exists, which
            // it now never will.
            LogNotPatched("copy functions", "not used, the game draws to the window");
            return;
        }
        if (!Patch(gl, "glDrawBuffer", &DrawBufferForGame, realDrawBuffer))
            LogNotPatched("glDrawBuffer", "the driver will refuse the game's own requests");
        if (!Patch(gl, "wglGetProcAddress", &GetProcForGame, realGetProc)) {
            LogNotPatched("wglGetProcAddress", "not used, the game draws to the window");
            return;
        }
        if (!Patch(gl, "wglMakeCurrent", &MakeCurrentForGame, realMakeCurrent))
            LogNotPatched("wglMakeCurrent", "a pbuffer would be drawn into KMRP's buffer");
    }
    if (windowDrawn) {
        // Every function taken passes the game's calls on untouched while no buffer exists.
        refused = true;
        Log("window-drawn=1 in configs\\kmrp.ini: not used; at debug logs 2 GL errors are named all the same");
        return;
    }
    DWORD old = 0;
    if (!VirtualProtect(slot, sizeof *slot, PAGE_READWRITE, &old)) { Log("the SwapBuffers slot cannot be written; not used"); return; }
    nextSwap = *slot;
    *slot = &SwapForGame;
    VirtualProtect(slot, sizeof *slot, old, &old);
}
