// The standalone module's NVIDIA present-method step (src/controller-native/
// K1RuntimeNvidia.cpp), run outside the game on an executable path given on the
// command line:
//
//     Test-RuntimeNvidia.exe <path to an executable>
//
// Prints every line the step would log and its outcome, and exits 0 for Unavailable,
// AlreadyRight, LeftAlone and Set, 1 for Failed. It WRITES NVIDIA's settings for that
// executable's name when the step decides to, exactly as the module does, so give it
// a throwaway name (kmrp-nvapi-selftest.exe, as Test-NvidiaPresentMethod.ps1 uses) and
// undo it with the installer's own Restore: `NvidiaPresentSelfTest.exe restore <path>`.
// That the installer's Restore accepts the record this writes is part of the test.
//
// Build (x86, as the module is):
//     cl /nologo /std:c++17 /EHsc /MT testing\regression\Test-RuntimeNvidia.cpp
//        src\controller-native\K1RuntimeNvidia.cpp /Isrc\controller-native /link crypt32.lib
//
// Documentation standard: see docs/documentation-standard.md.
#include "K1RuntimeNvidia.h"
#include <cstdio>

static void Print(const char* line) { std::printf("LOG %s\n", line); }

int wmain(int argc, wchar_t** argv)
{
    if (argc != 2) {
        std::printf("usage: Test-RuntimeNvidia <executable path>\n");
        return 64;
    }
    static const char* const names[] = {"Unavailable", "AlreadyRight", "LeftAlone", "Set", "Failed"};
    const KmrpNvidiaPresent result = KmrpNvidiaPresentMethod(argv[1], &Print);
    std::printf("RESULT %s\n", names[static_cast<int>(result)]);
    return result == KmrpNvidiaPresent::Failed ? 1 : 0;
}
