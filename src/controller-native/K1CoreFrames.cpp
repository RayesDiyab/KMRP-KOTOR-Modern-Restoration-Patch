// KMRP's module (kmrp.dll) only: its GUI and movie frame hooks, the save-game memory fix
// and the hardware mipmap correction.
// Until 2026-10-31 this lived in K1NativeJoystick.cpp, which kmrp.dll then compiled whole, with
// the rest of the controller code, for it (issue 82, F1:
// docs/cleanup-1.6/F1-kmrp-without-controller-code.md).
// (The save buffer counter it kept for the controller's state dump is gone: no module both
// hooks the save and writes that dump.)

#include "K1MovieWindow.h"
#include "K1CursorConfinement.h"
#include "K1StatusSummary.h"
#include "K1EngineMemory.h"
#include "K1RuntimeResolution.h"
#include "K1RuntimeLayout.h"
#include "K1TextLayout.h"
#include "K1TextOptions.h"
#include "K1HudOptions.h"

#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <cstring>

namespace {
constexpr std::uintptr_t K1_FREE = 0x006FB7B2;   // the game's free()
using FreeFn = void(__cdecl*)(void*);
}  // namespace

// Every save leaks one buffer per resource written.
//
// CERFFile::WriteResource hands a buffer to CExoFile::Write (0x005E69A0) and
// then abandons it -- the pointer in esi is never freed. Adopted from the Kotor
// Patch Manager project's SaveGameMemoryLeak patch (Lane Dibello); the
// ownership analysis is theirs and was reviewed there, not re-derived here.
extern "C" void __cdecl NativeFreeSaveBufferK1(void* buffer)
{
    if (!buffer) {
        return;
    }
    EngineFn<FreeFn>(K1_FREE)(buffer);
}

void KmrpRuntimeLog(const char* line);   // K1RuntimeEngine.cpp: one line into kmrp-kpm.log

// Hardware mipmaps where only K1 Modern Driver Compatibility's ATI emulation turned them
// off (2026-10-30). The game builds a texture's mipmaps on the graphics card only when
// AurSGIMipmapAvailable (0x0045F910) says so: GL_SGIS_generate_mipmap in its extension
// mask (0x007BB85C, that extension's bit at 0x0078E4CC) and not GL_ATI_fragment_shader
// (bit at 0x0078E4D0), a rule for the ATI drivers of 2003. K1DC answers yes to the ATI
// extension, which no current driver has, to emulate the ATI shader path, so the rule
// sent every uncompressed texture through gluBuild2DMipmaps on the CPU: 93 to 96% of the
// 0.9 s the workbench took to open, its 768x768 pictures rescaled and mipmapped each time
// (in-process samples, Steam game at 3440x1440, NVIDIA 616.56). Where the driver itself
// has the SGIS extension and not the ATI one, the rule's reason is absent: the cached
// answer (0x0078E538, -1 until the game first asks) is set to 1. Nothing else changes; a
// real ATI driver of the period, or one without the SGIS extension, keeps the game's.
// Called after each texture upload (KmrpTextureUploadedK1), the OpenGL context current,
// until it has decided once: from the first texture the game loads.
// A workaround for K1DC, reported to its author on 2026-10-30: remove it once K1DC fixes
// this, by the steps in docs/third-party-driver-compat.md, section 5.
void CorrectHardwareMipmapsK1()
{
    static bool done = false;
    static int frames = 0;   // uploads seen before the extension mask was there
    if (done) return;
    unsigned* const mask = reinterpret_cast<unsigned*>(0x007BB85C);
    const unsigned* const sgis = reinterpret_cast<const unsigned*>(0x0078E4CC);
    const unsigned* const ati = reinterpret_cast<const unsigned*>(0x0078E4D0);
    int* const answer = reinterpret_cast<int*>(0x0078E538);
    if (!IsReadableK1(mask, 4) || !IsReadableK1(sgis, 8) || !IsReadableK1(answer, 4)) { done = true; return; }
    using GetString = const unsigned char*(WINAPI*)(unsigned);
    static GetString getString = nullptr;
    if (!getString) {
        const HMODULE gl = GetModuleHandleA("opengl32.dll");
        getString = gl ? reinterpret_cast<GetString>(GetProcAddress(gl, "glGetString")) : nullptr;
    }
    const char* const extensions = getString ? reinterpret_cast<const char*>(getString(0x1F03)) : nullptr;  // GL_EXTENSIONS
    // Until the renderer has asked the driver: no extension mask or string yet.
    if (*mask == 0 || !extensions) {
        if (++frames > 600) done = true;
        return;
    }
    done = true;
    const bool gameSgis = *sgis != 0 && (*mask & *sgis) == *sgis;
    const bool gameAti = *ati != 0 && (*mask & *ati) != 0;
    const bool driverSgis = std::strstr(extensions, "GL_SGIS_generate_mipmap") != nullptr;
    const bool driverAti = std::strstr(extensions, "GL_ATI_fragment_shader") != nullptr;
    if (!(gameSgis && gameAti && driverSgis && !driverAti)) return;   // the game's own answer stands
    const int before = *answer;
    *answer = 1;
    char line[200];
    std::snprintf(line, sizeof line, "[KMRP] hardware mipmaps on: the driver has GL_SGIS_generate_mipmap and not "
                  "GL_ATI_fragment_shader, which only K1DC's emulation reports (the game's answer was %d)", before);
    KmrpRuntimeLog(line);
}

// KMRP's own share of the GUI frame and of the movie frame, hooked at sites of
// KMRP's own since 2026-10-05 (tools/build_native_kpatch.py, OWN_FRAME_HOOKS): the
// controller patch has the frames' usual sites, KOTOR Patch Manager allows one patch
// per address, and each patch must work without the other. (For some hours that day
// the controller patch's module called these from its frames instead, which made
// KMRP require it.) The resolution sampled, the cursor kept to the picture and the
// status summary laid out; the movie window centred, tracked and given its bars.
extern "C" void __cdecl KmrpCoreGuiWorkK1(void* guiManager)
{
    KmrpResolutionObservedK1(guiManager);
    KmrpTextOptionsFrameK1(guiManager);
    KmrpHudOptionsFrameK1(guiManager);  // the HUD Size page, its button above Text Size's (K1HudOptions.cpp)
    KmrpPcHudFrameK1(guiManager);       // the mouse and keyboard HUD placed and sized (K1PcHud.cpp)
    KmrpListRowsFrame(guiManager);      // the lists of newly loaded panels (K1RuntimeLayout.cpp, "List rows")
    UpdateCursorConfinementK1();
    StatusSummaryFrameK1(guiManager);
    KmrpTextLayoutFrameK1(guiManager);
    KmrpPreloadHudPagesK1();            // the HUD Size page's pictures, two a frame (K1HudOptions.cpp)
}

extern "C" void __cdecl KmrpCoreMovieWorkK1(void* moviePlayer)
{
    TrackMovieFrameK1(moviePlayer);
}

// The status summary's A badge is the pad's, the controller patch's: KMRP's module has none.
bool StatusSummaryBadgeK1(void*, const int*) { return false; }
