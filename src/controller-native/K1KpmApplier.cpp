// KMRP's executable patch, applied in memory -- the KPM edition.
//
// The standalone installer writes KMRP's changes into swkotor.exe: about eighty
// runs in the original code and data, and eleven new 4 KB sections at
// 0x0086D000-0x00877FFF (.kui ... .kmv). The KPM edition keeps the executable
// unmodified, because KOTOR Patch Manager recognises games by hash, so this
// module applies the same changes when the game starts instead.
//
// The sections cannot go back to their own addresses: in an unmodified process
// Windows maps other things over most of that range before any code of ours runs
// (measured 2026-09-28). So the eleven are copied as one block, layout intact,
// into memory allocated wherever it can be, and every address that names the
// block is moved by the difference -- the relocation table that
// tools/kpm_relocations.py computes from the gold executable, and proves.
//
// K1RuntimeEngine.cpp includes this file, and its data is built into the module: the bytes
// in kNativeEngine, with the size fields for the screen filled in, and the features from the
// patch's options. Until 2026-10-04 this was a module of its own in a four-patch edition, which
// read a kmrp-kpm.dat beside the game and the ticked patches from patch_config.toml; the parts
// only that needed went on 2026-11-01 (audit E-3). Format, all little-endian:
//
//   "KMRPKPM2"  u32 version (2)  u32 block VA  u32 block size
//   u32 page count, then one u32 page protection per page
//   the block, final bytes, the map-note flag cleared
//   u32 run count, then per run: u32 feature, u32 VA, u32 length,
//       original[len], final[len]
//   u32 edit count, then per block edit: u32 feature, u32 offset, u32 length,
//       bytes[len]
//   u32 relocation count, then per field: u32 kind (1 IN, 2 OUT, 3 ABS), u32 VA
//   u32 FNV-1a of every byte before it
//
// Features are bits: 1 core, 2 movies, 4 map notes, 8 the movie display mode (since
// 2026-10-20: the four operands that keep the game at its own size for a movie, apart
// from the rest of the movie changes so that they can be left out; issue 48).
//
// All or nothing. Every run's original bytes are checked in memory before
// anything is written, so an executable that is not the one the data was built
// for -- or bytes another patch changed first -- leaves the game untouched,
// and kmrp-kpm.log says why. It runs only in an unmodified image: the
// standalone edition's executable already carries all of this, and its fifteen
// sections tell the two apart.
//
// Two unmodified images: CD 1.03, and Steam's swkotor.exe, the same program
// behind SteamStub (see VanillaImage). Under KPM's CD launch this runs before any
// game code. On Steam KPM can load it only once the stub has decrypted the code,
// with the game already running -- measured at about 460 ms, after its window
// exists but before any screen KMRP changes is built -- so every other thread is
// paused while the runs are written (OtherThreads). The log records which image,
// when, and how many threads were paused.

#include <windows.h>
#include <tlhelp32.h>
#include "K1EngineAddresses.h"
#include "KmrpOptions.h"

#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <utility>
#include <vector>
#include "K1MovieWindow.h"

namespace {

constexpr std::uint32_t kVanillaSections = 4;
constexpr std::uint32_t kVanillaSizeOfImage = 0x46D000;   // ends at the block
constexpr std::uint32_t kBlockVa = 0x0086D000;
constexpr std::uint32_t kBlockSize = 0xB000;
constexpr std::uint32_t kKindIn = 1, kKindOut = 2, kKindAbs = 3;
constexpr std::uint32_t kCore = 1, kMovies = 2, kMapNotes = 4, kMovieMode = 8;

wchar_t g_folder[MAX_PATH];

void LogLine(const char* format, va_list args)
{
    // KMRP\logs\kmrp-kpm.log in the game folder since 2026-10-20 (KmrpLogPath,
    // KmrpOptions.h); the game folder itself until then.
    wchar_t path[MAX_PATH];
    path[0] = 0;
    if (!KmrpAppendPath(path, g_folder) || !KmrpAppendPath(path, L"\\KMRP")) {
        return;
    }
    CreateDirectoryW(path, nullptr);
    if (!KmrpAppendPath(path, L"\\logs")) {
        return;
    }
    CreateDirectoryW(path, nullptr);
    if (!KmrpAppendPath(path, L"\\kmrp-kpm.log")) {
        return;
    }
    FILE* f = nullptr;
    if (_wfopen_s(&f, path, L"a") || !f) {
        return;
    }
    SYSTEMTIME now;
    GetLocalTime(&now);
    fprintf(f, "%04u-%02u-%02u %02u:%02u:%02u ", now.wYear, now.wMonth, now.wDay,
            now.wHour, now.wMinute, now.wSecond);
    vfprintf(f, format, args);
    fputc('\n', f);
    fclose(f);
}

// Progress: what was applied and for which size. Written only with the debug-logs
// option on (KmrpOptions.h).
void Info(const char* format, ...)
{
    if (!KmrpDebugLogs()) {
        return;
    }
    va_list args;
    va_start(args, format);
    LogLine(format, args);
    va_end(args);
}

// An error or a warning: why nothing was applied, or what KMRP changed on its own.
// Always written, so kmrp-kpm.log exists only when there is something to read.
void Log(const char* format, ...)
{
    va_list args;
    va_start(args, format);
    LogLine(format, args);
    va_end(args);
}

struct Reader {
    const std::uint8_t* p;
    const std::uint8_t* end;
    bool ok = true;

    std::uint32_t U32()
    {
        if (end - p < 4) { ok = false; return 0; }
        std::uint32_t v;
        std::memcpy(&v, p, 4);
        p += 4;
        return v;
    }
    const std::uint8_t* Bytes(std::uint32_t n)
    {
        if (static_cast<std::uint32_t>(end - p) < n) { ok = false; return nullptr; }
        const std::uint8_t* at = p;
        p += n;
        return at;
    }
};

struct Run {
    std::uint32_t feature;
    std::uint32_t va;
    std::uint32_t length;
    const std::uint8_t* original;
    std::vector<std::uint8_t> final_;
};

struct Edit {
    std::uint32_t feature;
    std::uint32_t offset;
    std::uint32_t length;
    const std::uint8_t* bytes;
};

std::uint32_t Fnv1a(const std::uint8_t* data, std::size_t n)
{
    std::uint32_t h = 2166136261u;
    for (std::size_t i = 0; i < n; ++i) {
        h ^= data[i];
        h *= 16777619u;
    }
    return h;
}

// Steam's swkotor.exe (34E6D971...) is the same program behind SteamStub: once the
// stub has decrypted .text it is byte for byte CD 1.03's, measured 2026-09-28, and
// the stub adds one section, .bind, where gold's block would be. Its code is
// encrypted until then, so KPM loads KMRP there only after decryption, from a
// worker thread, with the game already running (KPM's DeferredApply).
constexpr std::uint32_t kSteamSections = 5;
constexpr std::uint32_t kSteamSizeOfImage = 0x4C3000;
bool g_steam = false;

bool VanillaImage()
{
    const auto* base = reinterpret_cast<const std::uint8_t*>(GetModuleHandleW(nullptr));
    const auto* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(base);
    const auto* nt = reinterpret_cast<const IMAGE_NT_HEADERS32*>(base + dos->e_lfanew);
    if (reinterpret_cast<std::uintptr_t>(base) != 0x400000) {
        return false;
    }
    if (nt->FileHeader.NumberOfSections == kVanillaSections &&
        nt->OptionalHeader.SizeOfImage == kVanillaSizeOfImage) {
        return true;
    }
    const auto* sections = IMAGE_FIRST_SECTION(nt);
    if (nt->FileHeader.NumberOfSections == kSteamSections &&
        nt->OptionalHeader.SizeOfImage == kSteamSizeOfImage &&
        std::memcmp(sections[4].Name, ".bind", 6) == 0) {
        g_steam = true;
        return true;
    }
    return false;
}

// Milliseconds since this process was created, for the log.
double ProcessAgeMs()
{
    FILETIME created{}, exited{}, kernel{}, user{}, now{};
    GetProcessTimes(GetCurrentProcess(), &created, &exited, &kernel, &user);
    GetSystemTimeAsFileTime(&now);
    const auto ticks = [](const FILETIME& f) {
        return (static_cast<unsigned long long>(f.dwHighDateTime) << 32) | f.dwLowDateTime;
    };
    return static_cast<double>(ticks(now) - ticks(created)) / 10000.0;
}

BOOL CALLBACK FindOwnWindow(HWND window, LPARAM found)
{
    DWORD pid = 0;
    GetWindowThreadProcessId(window, &pid);
    if (pid == GetCurrentProcessId()) {
        *reinterpret_cast<bool*>(found) = true;
        return FALSE;
    }
    return TRUE;
}

bool GameHasWindow()
{
    bool found = false;
    EnumWindows(FindOwnWindow, reinterpret_cast<LPARAM>(&found));
    return found;
}

// Every other thread of the game, suspended while the runs are written. Under
// KPM's CD launch only the loader runs, but on Steam the game's main thread is
// already executing, and could be inside a run as it changes. A thread stopped
// with its instruction pointer strictly inside a run is let go, and the attempt
// repeated a moment later. No heap use while threads are stopped: one of them may
// hold the heap lock.
class OtherThreads {
public:
    bool Suspend(const std::vector<std::pair<std::uint32_t, std::uint32_t>>& ranges)
    {
        const DWORD self = GetCurrentThreadId();
        HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
        if (snap == INVALID_HANDLE_VALUE) {
            return false;
        }
        THREADENTRY32 entry{};
        entry.dwSize = sizeof(entry);
        for (BOOL ok = Thread32First(snap, &entry); ok; ok = Thread32Next(snap, &entry)) {
            if (entry.th32OwnerProcessID != GetCurrentProcessId() || entry.th32ThreadID == self ||
                count_ == kMax) {
                continue;
            }
            HANDLE thread = OpenThread(THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT, FALSE,
                                       entry.th32ThreadID);
            if (!thread) {
                continue;
            }
            if (SuspendThread(thread) == static_cast<DWORD>(-1)) {
                CloseHandle(thread);
                continue;
            }
            threads_[count_++] = thread;
            CONTEXT context{};
            context.ContextFlags = CONTEXT_CONTROL;
            if (GetThreadContext(thread, &context)) {
                for (const auto& range : ranges) {
                    if (context.Eip > range.first && context.Eip < range.first + range.second) {
                        busy_ = true;
                    }
                }
            }
        }
        CloseHandle(snap);
        return !busy_;
    }
    void Resume()
    {
        for (std::size_t i = 0; i < count_; ++i) {
            ResumeThread(threads_[i]);
            CloseHandle(threads_[i]);
        }
        count_ = 0;
        busy_ = false;
    }
    std::size_t Count() const { return count_; }

private:
    static constexpr std::size_t kMax = 256;
    HANDLE threads_[kMax]{};
    std::size_t count_ = 0;
    bool busy_ = false;
};

bool WriteMemory(std::uint32_t va, const void* data, std::uint32_t n)
{
    void* at = reinterpret_cast<void*>(static_cast<std::uintptr_t>(va));
    DWORD old = 0;
    if (!VirtualProtect(at, n, PAGE_EXECUTE_READWRITE, &old)) {
        return false;
    }
    std::memcpy(at, data, n);
    DWORD ignored = 0;
    VirtualProtect(at, n, old, &ignored);
    FlushInstructionCache(GetCurrentProcess(), at, n);
    return true;
}

std::uint8_t* g_nativeBlock = nullptr;

void Apply(std::uint32_t features, const std::vector<std::uint8_t>* embedded = nullptr)
{
    std::vector<std::uint8_t> file;
    if (embedded) file = *embedded;
    if (file.size() < 12 || std::memcmp(file.data(), "KMRPKPM2", 8) != 0) {
        Log("kmrp-kpm.dat is not this version's data file: run KMRP's "
            "installer again. Nothing applied.");
        return;
    }
    std::uint32_t stored = 0;
    std::memcpy(&stored, file.data() + file.size() - 4, 4);
    if (Fnv1a(file.data(), file.size() - 4) != stored) {
        Log("kmrp-kpm.dat is damaged (checksum). Nothing applied.");
        return;
    }

    Reader r{file.data() + 8, file.data() + file.size() - 4};
    const std::uint32_t version = r.U32();
    const std::uint32_t blockVa = r.U32();
    const std::uint32_t blockSize = r.U32();
    if (!r.ok || version != 2 || blockVa != kBlockVa || blockSize != kBlockSize) {
        Log("kmrp-kpm.dat has an unexpected layout (version %u, block %08X+%X). "
            "Nothing applied.", version, blockVa, blockSize);
        return;
    }
    const std::uint32_t pages = r.U32();
    if (pages != blockSize / 0x1000) {
        Log("kmrp-kpm.dat: %u page protections for a %X-byte block. Nothing applied.",
            pages, blockSize);
        return;
    }
    std::vector<DWORD> protect(pages);
    for (auto& p : protect) {
        p = r.U32();
    }
    const std::uint8_t* blockBytes = r.Bytes(blockSize);

    std::vector<Run> runs(r.U32());
    for (auto& run : runs) {
        run.feature = r.U32();
        run.va = r.U32();
        run.length = r.U32();
        run.original = r.Bytes(run.length);
        const std::uint8_t* fin = r.Bytes(run.length);
        if (!r.ok) {
            break;
        }
        run.final_.assign(fin, fin + run.length);
        if (run.va < K1_GAME_TEXT_START || run.va + run.length > kBlockVa || run.length == 0) {
            Log("run at %08X+%u lies outside the game's original image. Nothing applied.",
                run.va, run.length);
            return;
        }
    }
    std::vector<Edit> edits(r.U32());
    for (auto& edit : edits) {
        edit.feature = r.U32();
        edit.offset = r.U32();
        edit.length = r.U32();
        edit.bytes = r.Bytes(edit.length);
        if (r.ok && (edit.offset + edit.length > blockSize || edit.length == 0)) {
            Log("a block edit at +%X lies outside the block. Nothing applied.", edit.offset);
            return;
        }
    }
    const std::uint32_t relocCount = r.U32();
    std::vector<std::uint32_t> kinds(relocCount), fields(relocCount);
    for (std::uint32_t i = 0; i < relocCount && r.ok; ++i) {
        kinds[i] = r.U32();
        fields[i] = r.U32();
    }
    if (!r.ok || r.p != r.end) {
        Log("kmrp-kpm.dat is truncated or has trailing bytes. Nothing applied.");
        return;
    }

    auto wanted = [features](std::uint32_t feature) { return (feature & features) != 0; };

    // 1. Check every original byte this will write, before touching anything.
    std::size_t chosen = 0;
    for (const auto& run : runs) {
        if (!wanted(run.feature)) {
            continue;
        }
        ++chosen;
        const void* at = reinterpret_cast<const void*>(static_cast<std::uintptr_t>(run.va));
        if (std::memcmp(at, run.original, run.length) != 0) {
            Log("the game's bytes at %08X (%u) are not the unmodified 1.03 executable's -- "
                "another patch may have changed them. Nothing applied.",
                run.va, run.length);
            return;
        }
    }

    // 2. The block, somewhere it can live, with the chosen features' edits.
    auto* block = static_cast<std::uint8_t*>(
        VirtualAlloc(nullptr, blockSize, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE));
    if (!block) {
        Log("could not allocate %X bytes for KMRP's code (error %lu). Nothing applied.",
            blockSize, GetLastError());
        return;
    }
    std::memcpy(block, blockBytes, blockSize);
    for (const auto& edit : edits) {
        if (wanted(edit.feature)) {
            std::memcpy(block + edit.offset, edit.bytes, edit.length);
        }
    }
    const std::uint32_t delta =
        static_cast<std::uint32_t>(reinterpret_cast<std::uintptr_t>(block)) - kBlockVa;

    // 3. Relocate. An IN field lies in a run; one in a run not applied is skipped.
    for (std::uint32_t i = 0; i < relocCount; ++i) {
        const std::uint32_t field = fields[i];
        if (kinds[i] == kKindOut || kinds[i] == kKindAbs) {
            if (field < kBlockVa || field + 4 > kBlockVa + blockSize) {
                Log("relocation %08X lies outside the block. Nothing applied.", field);
                VirtualFree(block, 0, MEM_RELEASE);
                return;
            }
            std::uint32_t v;
            std::memcpy(&v, block + (field - kBlockVa), 4);
            v = kinds[i] == kKindOut ? v - delta : v + delta;
            std::memcpy(block + (field - kBlockVa), &v, 4);
        } else if (kinds[i] == kKindIn) {
            Run* owner = nullptr;
            for (auto& run : runs) {
                if (field >= run.va && field + 4 <= run.va + run.length) {
                    owner = &run;
                    break;
                }
            }
            if (!owner) {
                Log("relocation %08X is not inside a run. Nothing applied.", field);
                VirtualFree(block, 0, MEM_RELEASE);
                return;
            }
            std::uint32_t v;
            std::memcpy(&v, owner->final_.data() + (field - owner->va), 4);
            v += delta;
            std::memcpy(owner->final_.data() + (field - owner->va), &v, 4);
        } else {
            Log("unknown relocation kind %u. Nothing applied.", kinds[i]);
            VirtualFree(block, 0, MEM_RELEASE);
            return;
        }
    }

    // 4. The block's page protections, then the runs that lead into it.
    for (std::uint32_t p = 0; p < pages; ++p) {
        DWORD old = 0;
        if (!VirtualProtect(block + p * 0x1000, 0x1000, protect[p], &old)) {
            Log("could not protect KMRP's code page %u (error %lu). Nothing applied.",
                p, GetLastError());
            VirtualFree(block, 0, MEM_RELEASE);
            return;
        }
    }
    FlushInstructionCache(GetCurrentProcess(), block, blockSize);
    std::vector<const Run*> written;
    written.reserve(runs.size());            // no allocation while threads are stopped
    std::vector<std::pair<std::uint32_t, std::uint32_t>> ranges;
    for (const auto& run : runs) {
        if (wanted(run.feature)) {
            ranges.emplace_back(run.va, run.length);
        }
    }
    const double startedMs = ProcessAgeMs();
    const bool hadWindow = GameHasWindow();
    OtherThreads others;
    for (int attempt = 0; !others.Suspend(ranges); ++attempt) {
        others.Resume();
        if (attempt == 200) {
            Log("a game thread stayed inside the code KMRP changes for 200 attempts. "
                "Nothing applied.");
            VirtualFree(block, 0, MEM_RELEASE);
            return;
        }
        Sleep(1);
    }
    std::uint32_t bytes = 0;
    const Run* failed = nullptr;
    DWORD error = 0;
    for (const auto& run : runs) {
        if (!wanted(run.feature)) {
            continue;
        }
        if (!WriteMemory(run.va, run.final_.data(), run.length) ||
            std::memcmp(reinterpret_cast<const void*>(run.va), run.final_.data(), run.length) != 0) {
            // Put back what was written; the block stays allocated, unreferenced.
            failed = &run;
            error = GetLastError();
            WriteMemory(run.va, run.original, run.length);   // a read-back that differed wrote it
            for (const Run* done : written) {
                WriteMemory(done->va, done->original, done->length);
            }
            break;
        }
        written.push_back(&run);
        bytes += run.length;
    }
    const std::size_t paused = others.Count();
    others.Resume();
    if (failed) {
        Log("could not write %08X (error %lu); the %zu runs already written were "
            "put back. Nothing applied.", failed->va, error, written.size());
        return;
    }
    g_nativeBlock = block;
    Info("applied: KMRP%s%s -- %zu of %zu runs (%u bytes) and KMRP's code at %p "
        "(moved by %+ld), %u relocations.",
        (features & kMovies) ? ((features & kMovieMode) ? " + Movies" : " + Movies at 640x480") : "",
        (features & kMapNotes) ? " + Map Notes" : "",
        chosen, runs.size(), bytes, static_cast<void*>(block),
        static_cast<long>(delta), relocCount);
    Info("  %s executable; %.0f ms after the game started, %s its window; %zu other "
        "thread(s) paused while writing.", g_steam ? "Steam" : "CD 1.03", startedMs,
        hadWindow ? "after" : "before", paused);
}

bool g_moviesOff = false;

}  // namespace

// The KPM edition without KMRP Movies: the movie window is left as the game draws
// it (K1NativeJoystick.cpp). Always false in the standalone edition, whose
// executable carries the movie changes.
bool KpmMoviesOffK1()
{
    return g_moviesOff;
}
