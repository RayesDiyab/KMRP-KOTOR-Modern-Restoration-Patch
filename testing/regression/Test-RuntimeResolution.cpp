// Exercise the shipped x86 callback from its DLL, including its calling convention.
#include <windows.h>
#include <cstdio>

int main(int argc, char** argv)
{
    if (argc != 2) return 2;
    HMODULE module = LoadLibraryA(argv[1]);
    if (!module) return 3;
    auto allow = reinterpret_cast<int(__cdecl*)(int,int)>(
        GetProcAddress(module, "KmrpAllowRuntimeResolutionK1"));
    if (!allow) return 4;
    struct Case { int width, height, expected; };
    const Case cases[] = {
        {640,480,1}, {800,600,1}, {1280,720,1}, {1920,1200,1},
        {2560,1440,1}, {3440,1440,1}, {5120,1440,1}, {1237,813,1},
        {32767,32767,1}, {639,480,0}, {640,479,0}, {32768,720,0},
        {1280,32768,0}, {-1,720,0}, {1280,-1,0}, {0,0,0},
        {2147483647,720,0}, {1280,2147483647,0}
    };
    for (const auto& c : cases) {
        unsigned before, after;
        __asm mov before, esp
        const int actual = allow(c.width, c.height);
        __asm mov after, esp
        if (actual != c.expected || before != after) {
            printf("FAIL %dx%d: result=%d expected=%d ESP=%08X/%08X\n",
                   c.width, c.height, actual, c.expected, before, after);
            return 1;
        }
    }
    FreeLibrary(module);
    puts("PASS: 18 shipped x86 callback cases, cdecl stack balanced");
}
