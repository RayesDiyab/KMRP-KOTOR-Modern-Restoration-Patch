// K1OffscreenFrame.cpp's logic against a stand-in OpenGL driver, from the shipped source: the
// file is included whole, so this reaches what its anonymous namespace holds and sets its
// function pointers to the fakes below, as Install does to opengl32's. No driver draws
// anything: what is checked is what the module asks of a driver, in what order, and what it
// does with the answers. Whether a real AMD or Intel driver honours those calls is not
// something this can say. Test-OffscreenFrame.py builds and runs this.
#define WIN32_LEAN_AND_MEAN   // winsock has a bind of its own
#include "../../src/controller-native/K1OffscreenFrame.cpp"
#include <string>
#include <vector>

void KmrpRuntimeLog(const char* line) { std::printf("    log: %s\n", line); }

static int failures = 0;
static void Check(bool condition, const char* text)
{
    std::printf("%s  %s\n", condition ? "ok  " : "FAIL", text);
    if (!condition) ++failures;
}

// The fake driver.
static GLuint drawBound = 0, readBound = 0, renderbufferBound = 0, nextName = 1;
static int windowSamples = 0, givenSamples = -1;
static GLenum statusAnswer = kComplete, errorAnswer = 0;
static bool scissorOn = false, lacksBlit = false, lacksMultisample = false;
static HGLRC currentRc = reinterpret_cast<HGLRC>(1);
struct Blit { GLuint read, draw; int width, height; bool scissor; };
static std::vector<Blit> blits;
static std::vector<GLuint> swapDraws, readsFrom, deleted;
static int swapCount = 0;

static void WINAPI FakeBind(GLenum target, GLuint name)
{
    if (target == kFramebuffer || target == kDrawFramebuffer) drawBound = name;
    if (target == kFramebuffer || target == kReadFramebuffer) readBound = name;
}
static void WINAPI FakeGen(GLsizei count, GLuint* names) { for (int i = 0; i < count; ++i) names[i] = nextName++; }
static void WINAPI FakeBindRenderbuffer(GLenum, GLuint name) { renderbufferBound = name; }
static void WINAPI FakeStorage(GLenum, GLenum, GLsizei, GLsizei) {}
static void WINAPI FakeStorageMs(GLenum, GLsizei, GLenum, GLsizei, GLsizei) {}
static void WINAPI FakeAttach(GLenum, GLenum, GLenum, GLuint) {}
static GLenum WINAPI FakeCheck(GLenum) { return statusAnswer; }
static void WINAPI FakeDelete(GLsizei count, const GLuint* names) { for (int i = 0; i < count; ++i) deleted.push_back(names[i]); }
static void WINAPI FakeBlit(GLint, GLint, GLint w, GLint h, GLint, GLint, GLint, GLint, GLbitfield, GLenum)
{
    blits.push_back({readBound, drawBound, w, h, scissorOn});
}
static void WINAPI FakeGetIntegerv(GLenum name, GLint* out)
{
    if (name == kSamples) *out = drawBound == 0 ? windowSamples : (givenSamples >= 0 ? givenSamples : windowSamples);
    else if (name == kRenderbufferBinding) *out = static_cast<GLint>(renderbufferBound);
    else if (name == kDrawBinding) *out = static_cast<GLint>(drawBound);
    else if (name == kReadBinding) *out = static_cast<GLint>(readBound);
    else *out = 0;
}
static unsigned char WINAPI FakeIsEnabled(GLenum) { return scissorOn ? 1 : 0; }
static void WINAPI FakeEnable(GLenum) { scissorOn = true; }
static void WINAPI FakeDisable(GLenum) { scissorOn = false; }
static HGLRC WINAPI FakeContext() { return currentRc; }
static GLenum WINAPI FakeError() { const GLenum error = errorAnswer; errorAnswer = 0; return error; }
// Only once the copy has run, so this is the copy's error and not one from before it.
static GLenum WINAPI FakeErrorAfterBlit() { return blits.empty() ? 0 : FakeError(); }
static BOOL WINAPI FakeMakeCurrent(HDC, HGLRC) { return TRUE; }
static BOOL WINAPI FakeSwap(HDC) { swapDraws.push_back(drawBound); ++swapCount; return TRUE; }
static void WINAPI FakeRead(GLint, GLint, GLsizei, GLsizei, GLenum, GLenum, void*) { readsFrom.push_back(readBound); }
static void WINAPI FakeCopyImage(GLenum, GLint, GLenum, GLint, GLint, GLsizei, GLsizei, GLint) { readsFrom.push_back(readBound); }
static void WINAPI FakeCopySub(GLenum, GLint, GLint, GLint, GLint, GLint, GLsizei, GLsizei) { readsFrom.push_back(readBound); }

static PROC WINAPI FakeGetProc(LPCSTR name)
{
    const std::string text = name;
    if (text == "glBindFramebufferEXT" || text == "glBindFramebuffer") return reinterpret_cast<PROC>(&FakeBind);
    if (text == "glGenFramebuffersEXT" || text == "glGenRenderbuffersEXT") return reinterpret_cast<PROC>(&FakeGen);
    if (text == "glBindRenderbufferEXT") return reinterpret_cast<PROC>(&FakeBindRenderbuffer);
    if (text == "glRenderbufferStorageEXT") return reinterpret_cast<PROC>(&FakeStorage);
    if (text == "glRenderbufferStorageMultisampleEXT") return lacksMultisample ? nullptr : reinterpret_cast<PROC>(&FakeStorageMs);
    if (text == "glFramebufferRenderbufferEXT") return reinterpret_cast<PROC>(&FakeAttach);
    if (text == "glCheckFramebufferStatusEXT") return reinterpret_cast<PROC>(&FakeCheck);
    if (text == "glDeleteFramebuffersEXT" || text == "glDeleteRenderbuffersEXT") return reinterpret_cast<PROC>(&FakeDelete);
    if (text == "glBlitFramebufferEXT") return lacksBlit ? nullptr : reinterpret_cast<PROC>(&FakeBlit);
    return nullptr;
}

// A fresh module and driver, as at a game's start.
static void Start(int sampleCount = 0)
{
    realGetProc = &FakeGetProc;
    realMakeCurrent = &FakeMakeCurrent;
    realCopyTexImage = &FakeCopyImage;
    realCopyTexSubImage = &FakeCopySub;
    realReadPixels = &FakeRead;
    nextSwap = &FakeSwap;
    gameBind = gameBindExt = &FakeBind;
    bind = nullptr;
    genFramebuffers = genRenderbuffers = nullptr;
    bindRenderbuffer = nullptr;
    renderbufferStorage = nullptr;
    renderbufferStorageMs = nullptr;
    framebufferRenderbuffer = nullptr;
    checkStatus = nullptr;
    deleteFramebuffers = deleteRenderbuffers = nullptr;
    blit = nullptr;
    getIntegerv = &FakeGetIntegerv;
    isEnabled = &FakeIsEnabled;
    enable = &FakeEnable;
    disable = &FakeDisable;
    currentContext = &FakeContext;
    getError = &FakeError;
    context = nullptr;
    window = nullptr;
    frame = colour = depth = plain = plainColour = 0;
    width = height = samples = 0;
    refused = swapping = false;
    checkedShow = false;
    drawBound = readBound = renderbufferBound = 0;
    nextName = 1;
    windowSamples = sampleCount;
    givenSamples = -1;
    statusAnswer = kComplete;
    errorAnswer = 0;
    scissorOn = lacksBlit = lacksMultisample = false;
    currentRc = reinterpret_cast<HGLRC>(1);
    blits.clear();
    swapDraws.clear();
    readsFrom.clear();
    deleted.clear();
    swapCount = 0;
}

int main()
{
    WNDCLASSW type{};
    type.lpfnWndProc = DefWindowProcW;
    type.hInstance = GetModuleHandleW(nullptr);
    type.lpszClassName = L"KmrpOffscreenFrameTest";
    RegisterClassW(&type);
    HWND host = CreateWindowExW(0, type.lpszClassName, L"", WS_POPUP, 0, 0, 640, 480, nullptr, nullptr, type.hInstance, nullptr);
    HDC dc = GetDC(host);
    Check(host && dc, "a window to stand for the game's");

    // A plain window.
    Start();
    SwapForGame(dc);
    Check(swapCount == 1 && frame != 0 && drawBound == frame, "the first swap makes the buffer and binds it");
    Check(width == 640 && height == 480 && !refused, "at the window's size");
    Check(blits.empty(), "and copies nothing, as nothing was drawn into it");
    const GLuint made = frame;
    blits.clear();
    SwapForGame(dc);
    Check(swapDraws.back() == 0, "the swap happens with the window bound, for K1DC's brightness pass");
    Check(blits.size() == 2, "a frame is copied in before the swap and again into the next back buffer");
    Check(blits.size() == 2 && blits[0].read == made && blits[0].draw == 0 && blits[0].width == 640 && blits[0].height == 480,
          "from KMRP's buffer to the window, the whole size");
    Check(drawBound == made && readBound == made, "and the game draws into KMRP's buffer after it");
    scissorOn = true;
    SwapForGame(dc);
    Check(scissorOn && blits.size() == 4 && !blits[2].scissor, "the copy is not cut by the game's scissor, which comes back");
    scissorOn = false;

    // Binds.
    BindForGame(kFramebuffer, 0);
    Check(drawBound == made, "the game's bind of the window goes to KMRP's buffer");
    BindForGameExt(kFramebuffer, 77);
    Check(drawBound == 77, "a bind of anything else is the game's");
    BindForGameExt(kFramebuffer, 0);
    Check(drawBound == made, "the EXT form the same");
    swapping = true;
    BindForGame(kFramebuffer, 0);
    Check(drawBound == 0, "inside the swap the window is the window");
    swapping = false;
    currentRc = reinterpret_cast<HGLRC>(2);
    BindForGame(kFramebuffer, 0);
    Check(drawBound == 0, "in another context so is it");
    currentRc = reinterpret_cast<HGLRC>(1);

    // A frame not drawn into KMRP's buffer is not shown from it (audit GFX-05).
    Start();
    SwapForGame(dc);
    blits.clear();
    drawBound = 55;
    SwapForGame(dc);
    Check(blits.empty(), "with another buffer bound at the swap, nothing stale is copied over the window");
    Check(drawBound == frame, "and KMRP's buffer is bound for the next frame");

    // The window's buffer and pbuffers.
    Start();
    SwapForGame(dc);
    MakeCurrentForGame(nullptr, reinterpret_cast<HGLRC>(1));
    Check(drawBound == 0, "the context on another surface has the window's 0");
    MakeCurrentForGame(dc, reinterpret_cast<HGLRC>(1));
    Check(drawBound == frame, "and back on the window KMRP's buffer");

    // A new size.
    Start();
    SwapForGame(dc);
    const GLuint before = frame;
    SetWindowPos(host, nullptr, 0, 0, 800, 600, SWP_NOMOVE | SWP_NOZORDER);
    SwapForGame(dc);
    Check(frame != before && width == 800 && height == 600, "a new window size makes a new buffer");
    Check(!deleted.empty() && deleted[0] == before, "and the old one is deleted");
    SetWindowPos(host, nullptr, 0, 0, 640, 480, SWP_NOMOVE | SWP_NOZORDER);

    // Anti-aliasing.
    Start(8);
    SwapForGame(dc);
    Check(samples == 8 && plain != 0, "a multisampled window gets a buffer of its count and a plain one to read");
    const GLuint resolvedInto = plain, msFrame = frame;
    blits.clear();
    char pixels[4];
    ReadPixelsForGame(0, 0, 1, 1, 0, 0, pixels);
    Check(blits.size() == 1 && blits[0].read == msFrame && blits[0].draw == resolvedInto, "a read resolves into the plain buffer");
    Check(readsFrom.back() == resolvedInto, "and reads that");
    Check(readBound == msFrame && drawBound == msFrame, "and both bindings come back");
    scissorOn = true;
    blits.clear();
    CopyTexImageForGame(0, 0, 0, 0, 0, 1, 1, 0);
    Check(blits.size() == 1 && !blits[0].scissor && scissorOn && readsFrom.back() == resolvedInto, "glCopyTexImage2D the same, past the scissor");
    scissorOn = false;
    CopyTexSubImageForGame(0, 0, 0, 0, 0, 0, 1, 1);
    Check(readsFrom.back() == resolvedInto, "glCopyTexSubImage2D the same");
    blits.clear();
    BindForGame(kReadFramebuffer, 33);
    ReadPixelsForGame(0, 0, 1, 1, 0, 0, pixels);
    Check(blits.empty() && readsFrom.back() == 33, "a read of another buffer is left alone");
    Start(0);
    SwapForGame(dc);
    blits.clear();
    ReadPixelsForGame(0, 0, 1, 1, 0, 0, pixels);
    Check(blits.empty() && readsFrom.back() == frame, "without anti-aliasing nothing needs resolving");

    // What a driver can refuse: the window is then drawn into as before.
    Start();
    lacksBlit = true;
    SwapForGame(dc);
    Check(refused && frame == 0 && drawBound == 0, "no blit: refused, and nothing bound");
    Start(4);
    lacksMultisample = true;
    SwapForGame(dc);
    Check(refused && frame == 0 && drawBound == 0, "anti-aliasing with no multisampled buffers: refused");
    Start();
    statusAnswer = 0x8CD6;
    SwapForGame(dc);
    Check(refused && frame == 0 && drawBound == 0, "an incomplete buffer: refused");
    Start(8);
    givenSamples = 4;
    SwapForGame(dc);
    Check(refused && frame == 0 && drawBound == 0, "fewer samples than the window: refused");
    BindForGame(kFramebuffer, 0);
    Check(drawBound == 0, "and the game's binds are left alone");

    // The copy that fails only when tried (audit GFX-04): the check on the first frame shown.
    Start(8);
    SwapForGame(dc);
    blits.clear();
    errorAnswer = 0x0502;
    getError = &FakeErrorAfterBlit;
    SwapForGame(dc);
    Check(refused && frame == 0, "a copy the driver refuses: refused, not a black screen");
    Check(drawBound == 0, "and the game draws into the window from then on");
    const int shown = swapCount;
    SwapForGame(dc);
    Check(swapCount == shown + 1 && !frame, "and the swaps go on");

    Start();
    SwapForGame(dc);
    errorAnswer = 0x0501;      // left by the game before the copy
    getError = &FakeError;
    SwapForGame(dc);
    Check(!refused && frame != 0, "an error the game left behind is not taken for the copy's");

    std::printf("%d failed\n", failures);
    ReleaseDC(host, dc);
    DestroyWindow(host);
    return failures ? 1 : 0;
}
