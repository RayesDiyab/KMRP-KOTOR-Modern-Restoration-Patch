// NVIDIA's "Vulkan/OpenGL present method" for the game, from inside the game.
//
// The installer makes this check when it installs (NvidiaPresentOperations in
// src/patcher/KmrpPatcher.cs). The standalone module has no installer, so it makes
// the same check itself, once, after the game's window exists: when swkotor.exe would
// inherit "Prefer layered on DXGI Swapchain" from NVIDIA's global profile, it says so
// in KMRP's log and sets "Prefer native" in the game's own profile. On the layered
// path KOTOR shows frames it has not finished drawing: the white flash of issue #14.
//
// The rules are the installer's, kept identical on purpose:
//   * a value the game's profile holds itself is left alone, whatever it is;
//   * the global profile is only read;
//   * a profile shared with other applications is left alone;
//   * a profile with KMRP's name that does not hold this game is not adopted;
//   * KMRP_NVIDIA.manifest beside the game records the change, in the installer's
//     format, written before the save and removed again if the save is refused.
//
// The driver reads the profile when the game starts, so a change made here applies
// from the next start. Entry points come from nvapi_QueryInterface by the ids in
// NVIDIA's nvapi_interface.h; the structures are filled by offset, as the installer
// fills them (every string is 2048 UTF-16 units, every other field 32-bit).

#include "K1RuntimeNvidia.h"
#include <windows.h>
#include <wincrypt.h>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

namespace {
const int kOk = 0;
const int kInvalidUserPrivilege = -137;
const int kSettingNotFound = -160;
const int kProfileNotFound = -163;
const int kExecutableNotFound = -166;
const int kLocationCurrentProfile = 0;      // NVDRS_CURRENT_PROFILE_LOCATION

const std::size_t kStringBytes = 4096;
const std::size_t kSettingSize = 12320, kSettingId = 4100, kSettingType = 4104,
                  kSettingLocation = 4108, kSettingCurrent = 8220;
const std::size_t kApplicationSize = 20492, kApplicationName = 8;
const std::size_t kProfileSize = 4116, kProfileName = 4, kProfileApps = 4108;

// NvApiDriverSettings.h: OGL_CPL_PREFER_DXPRESENT, "Vulkan/OpenGL present method".
const std::uint32_t kPresentMethod = 0x20D690F8;
const std::uint32_t kPreferNative = 0, kPreferLayered = 1;
const wchar_t kProfileNameText[] = L"KMRP - Star Wars: Knights of the Old Republic";
const char kWarning[] = "WARNING: NVIDIA would present swkotor.exe through a DXGI swap chain: its global "
    "Vulkan/OpenGL present method is Prefer layered on DXGI Swapchain, and nothing is set for the game. On that "
    "path KOTOR shows half-drawn frames (white flashes in the menus).";
const char kManualFix[] =" To do it by hand: NVIDIA Control Panel -> Manage 3D settings -> "
    "Program Settings -> swkotor.exe -> Vulkan/OpenGL present method -> Prefer native.";

using Handle = void*;
using QueryFn = void* (__cdecl*)(std::uint32_t);

struct Failure { std::string what; };

void Check(const char* function, int status)
{
    if (status != kOk) throw Failure{std::string(function) + " returned " + std::to_string(status) + "."};
}

std::vector<std::uint8_t> Struct(std::size_t size, std::uint32_t version)
{
    std::vector<std::uint8_t> block(size);
    const std::uint32_t word = static_cast<std::uint32_t>(size) | (version << 16);
    std::memcpy(block.data(), &word, 4);
    return block;
}

void PutString(std::vector<std::uint8_t>& block, std::size_t offset, const std::wstring& text)
{
    if (text.size() * 2 > kStringBytes - 2) throw Failure{"An NvAPI string is limited to 2047 characters."};
    std::memcpy(block.data() + offset, text.data(), text.size() * 2);
}

std::int32_t Int(const std::vector<std::uint8_t>& block, std::size_t offset)
{
    std::int32_t value;
    std::memcpy(&value, block.data() + offset, 4);
    return value;
}

std::string Utf8(const std::wstring& text)
{
    const int n = WideCharToMultiByte(CP_UTF8, 0, text.data(), static_cast<int>(text.size()), nullptr, 0, nullptr, nullptr);
    std::string out(n > 0 ? n : 0, '\0');
    if (n > 0) WideCharToMultiByte(CP_UTF8, 0, text.data(), static_cast<int>(text.size()), out.data(), n, nullptr, nullptr);
    return out;
}

// One driver-settings session. nvapi is loaded from System32 only, never from the
// game's folder or the module's.
class Session {
public:
    // False when there is no NVIDIA driver to talk to.
    bool Open()
    {
        HMODULE module = LoadLibraryExW(sizeof(void*) == 8 ? L"nvapi64.dll" : L"nvapi.dll",
                                        nullptr, LOAD_LIBRARY_SEARCH_SYSTEM32);
        if (!module) return false;
        query_ = reinterpret_cast<QueryFn>(GetProcAddress(module, "nvapi_QueryInterface"));
        if (!query_) return false;
        if (Call<int(__cdecl*)()>(0x0150E828)() != kOk) return false;        // NvAPI_Initialize
        initialized_ = true;
        Check("NvAPI_DRS_CreateSession", Call<int(__cdecl*)(Handle*)>(0x0694D52E)(&session_));
        Check("NvAPI_DRS_LoadSettings", Call<int(__cdecl*)(Handle)>(0x375DBD6B)(session_));
        return true;
    }

    ~Session()
    {
        if (!query_) return;
        if (session_) {
            if (auto destroy = reinterpret_cast<int(__cdecl*)(Handle)>(query_(0xDAD9CFF8))) destroy(session_);
        }
        if (initialized_) {
            if (auto unload = reinterpret_cast<int(__cdecl*)()>(query_(0xD22BDD7E))) unload();
        }
    }

    // The profile the driver applies to this executable, or null when none names it.
    Handle ApplicationProfile(const std::wstring& executablePath)
    {
        auto name = std::vector<std::uint8_t>(kStringBytes);
        PutString(name, 0, executablePath);
        auto application = Struct(kApplicationSize, 4);
        Handle profile = nullptr;
        const int status = Call<int(__cdecl*)(Handle, void*, Handle*, void*)>(0xEEE566B2)(
            session_, name.data(), &profile, application.data());
        if (status == kExecutableNotFound) return nullptr;
        Check("NvAPI_DRS_FindApplicationByName", status);
        return profile;
    }

    Handle GlobalProfile()
    {
        Handle profile = nullptr;
        Check("NvAPI_DRS_GetCurrentGlobalProfile", Call<int(__cdecl*)(Handle, Handle*)>(0x617BFF9F)(session_, &profile));
        return profile;
    }

    Handle FindProfile(const std::wstring& profileName)
    {
        auto name = std::vector<std::uint8_t>(kStringBytes);
        PutString(name, 0, profileName);
        Handle profile = nullptr;
        const int status = Call<int(__cdecl*)(Handle, void*, Handle*)>(0x7E4A9A0B)(session_, name.data(), &profile);
        if (status == kProfileNotFound) return nullptr;
        Check("NvAPI_DRS_FindProfileByName", status);
        return profile;
    }

    Handle CreateProfile(const std::wstring& profileName)
    {
        auto info = Struct(kProfileSize, 1);
        PutString(info, kProfileName, profileName);
        Handle profile = nullptr;
        Check("NvAPI_DRS_CreateProfile", Call<int(__cdecl*)(Handle, void*, Handle*)>(0xCC176068)(session_, info.data(), &profile));
        return profile;
    }

    void ProfileInfo(Handle profile, std::wstring& name, int& applications)
    {
        auto info = Struct(kProfileSize, 1);
        Check("NvAPI_DRS_GetProfileInfo", Call<int(__cdecl*)(Handle, Handle, void*)>(0x61CD6FD6)(session_, profile, info.data()));
        name.assign(reinterpret_cast<const wchar_t*>(info.data() + kProfileName));
        applications = Int(info, kProfileApps);
    }

    void AddApplication(Handle profile, const std::wstring& applicationName)
    {
        auto application = Struct(kApplicationSize, 4);
        PutString(application, kApplicationName, applicationName);
        Check("NvAPI_DRS_CreateApplication", Call<int(__cdecl*)(Handle, Handle, void*)>(0x4347A9DE)(session_, profile, application.data()));
    }

    // The value as the driver resolves it for this profile, and where it comes from:
    // the profile itself, or the profile it inherits from. False when nothing holds it.
    bool Dword(Handle profile, std::uint32_t settingId, std::uint32_t& value, int& location)
    {
        auto setting = Struct(kSettingSize, 1);
        const int status = Call<int(__cdecl*)(Handle, Handle, std::uint32_t, void*)>(0x73BF8338)(
            session_, profile, settingId, setting.data());
        if (status == kSettingNotFound) return false;
        Check("NvAPI_DRS_GetSetting", status);
        value = static_cast<std::uint32_t>(Int(setting, kSettingCurrent));
        location = Int(setting, kSettingLocation);
        return true;
    }

    void SetDword(Handle profile, std::uint32_t settingId, std::uint32_t value)
    {
        auto setting = Struct(kSettingSize, 1);
        std::memcpy(setting.data() + kSettingId, &settingId, 4);
        const std::uint32_t dwordType = 0;                                   // NVDRS_DWORD_TYPE
        std::memcpy(setting.data() + kSettingType, &dwordType, 4);
        std::memcpy(setting.data() + kSettingCurrent, &value, 4);
        Check("NvAPI_DRS_SetSetting", Call<int(__cdecl*)(Handle, Handle, void*)>(0x577DD202)(session_, profile, setting.data()));
    }

    // Returned, not thrown: a refusal for want of privilege has its own answer.
    int Save() { return Call<int(__cdecl*)(Handle)>(0xFCBC7E14)(session_); }

private:
    template <typename Fn> Fn Call(std::uint32_t id)
    {
        void* address = query_(id);
        if (!address) {
            char text[80];
            sprintf_s(text, "This NVIDIA driver does not provide NvAPI function 0x%08X.", id);
            throw Failure{text};
        }
        return reinterpret_cast<Fn>(address);
    }

    QueryFn query_ = nullptr;
    Handle session_ = nullptr;
    bool initialized_ = false;
};

std::wstring ManifestPath(const std::wstring& executablePath)
{
    const std::size_t slash = executablePath.find_last_of(L"\\/");
    return (slash == std::wstring::npos ? std::wstring() : executablePath.substr(0, slash + 1)) + L"KMRP_NVIDIA.manifest";
}

// The installer's record, byte for byte: header, the path as base64 of its UTF-8,
// and whether KMRP made the profile. Its Restore reads this.
bool WriteManifest(const std::wstring& path, const std::wstring& executablePath, bool createdProfile)
{
    const std::string utf8 = Utf8(executablePath);
    DWORD length = 0;
    const DWORD flags = CRYPT_STRING_BASE64 | CRYPT_STRING_NOCRLF;
    if (!CryptBinaryToStringA(reinterpret_cast<const BYTE*>(utf8.data()), static_cast<DWORD>(utf8.size()), flags, nullptr, &length))
        return false;
    std::string base64(length, '\0');
    if (!CryptBinaryToStringA(reinterpret_cast<const BYTE*>(utf8.data()), static_cast<DWORD>(utf8.size()), flags, base64.data(), &length))
        return false;
    base64.resize(length);
    const std::string text = "KMRPNV1\r\n" + base64 + "\r\n" + (createdProfile ? "1" : "0") + "\r\n";
    HANDLE file = CreateFileW(path.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) return false;
    DWORD written = 0;
    const bool ok = WriteFile(file, text.data(), static_cast<DWORD>(text.size()), &written, nullptr) && written == text.size();
    CloseHandle(file);
    if (!ok) DeleteFileW(path.c_str());
    return ok;
}

// In a session of its own, so it reads what the driver saved and not what the
// writing session still holds.
bool HoldsPreferNative(const std::wstring& executablePath)
{
    Session drs;
    if (!drs.Open()) return false;
    Handle profile = drs.ApplicationProfile(executablePath);
    std::uint32_t value = 0;
    int location = -1;
    return profile && drs.Dword(profile, kPresentMethod, value, location) &&
           location == kLocationCurrentProfile && value == kPreferNative;
}
}

KmrpNvidiaPresent KmrpNvidiaPresentMethod(const wchar_t* executablePath, void (*report)(const char* line))
{
    const std::wstring path = executablePath ? executablePath : L"";
    const std::wstring manifest = ManifestPath(path);
    if (path.empty()) return KmrpNvidiaPresent::Unavailable;
    if (GetFileAttributesW(manifest.c_str()) != INVALID_FILE_ATTRIBUTES)
        return KmrpNvidiaPresent::AlreadyRight;              // KMRP's already, from an earlier run or the installer

    try {
        std::wstring profileName;
        {
            Session drs;
            if (!drs.Open()) return KmrpNvidiaPresent::Unavailable;   // not an NVIDIA machine: nothing to say

            Handle profile = drs.ApplicationProfile(path);
            std::uint32_t value = 0;
            int location = -1;
            const bool found = drs.Dword(profile ? profile : drs.GlobalProfile(), kPresentMethod, value, location);
            if (profile && found && location == kLocationCurrentProfile) {
                if (value == kPreferLayered)
                    report("NVIDIA is set to present swkotor.exe through a DXGI swap chain in the game's own "
                           "profile; left as chosen. If menus flash or show half-drawn frames, set its "
                           "Vulkan/OpenGL present method to Auto or Prefer native.");
                return value == kPreferLayered ? KmrpNvidiaPresent::LeftAlone : KmrpNvidiaPresent::AlreadyRight;
            }
            if (!found || value != kPreferLayered) return KmrpNvidiaPresent::AlreadyRight;   // Auto or native, inherited

            // From here the game would be presented through DXGI. Every line below
            // starts with that warning, and then says what KMRP did about it.
            if (profile) {
                int applications = 0;
                drs.ProfileInfo(profile, profileName, applications);
                if (applications != 1) {
                    report((std::string(kWarning) + " KMRP left the shared NVIDIA profile \"" + Utf8(profileName) +
                            "\" alone; its present method also affects other applications." + kManualFix).c_str());
                    return KmrpNvidiaPresent::LeftAlone;
                }
            }

            bool createdProfile = false;
            if (!profile) {
                if (drs.FindProfile(kProfileNameText)) {
                    report((std::string(kWarning) + " KMRP left the existing NVIDIA profile named \"" +
                            Utf8(kProfileNameText) + "\" alone: it is not associated with this game." + kManualFix).c_str());
                    return KmrpNvidiaPresent::LeftAlone;
                }
                profile = drs.CreateProfile(kProfileNameText);
                createdProfile = true;
                profileName = kProfileNameText;
                const std::size_t slash = path.find_last_of(L"\\/");
                drs.AddApplication(profile, slash == std::wstring::npos ? path : path.substr(slash + 1));
            }
            // Before the write, so the log has the warning whatever happens next.
            report((std::string(kWarning) + " KMRP now sets Prefer native for swkotor.exe in NVIDIA's profile \"" +
                    Utf8(profileName) + "\"; the global setting is not touched.").c_str());
            drs.SetDword(profile, kPresentMethod, kPreferNative);
            // The record first: a saved value with no record could never be told
            // from the player's own, while a record whose save failed is removed.
            if (!WriteManifest(manifest, path, createdProfile)) throw Failure{"KMRP_NVIDIA.manifest could not be written beside the game."};
            const int saved = drs.Save();
            if (saved != kOk) DeleteFileW(manifest.c_str());
            if (saved == kInvalidUserPrivilege) {
                report((std::string("Windows did not allow the change to NVIDIA's settings.") + kManualFix).c_str());
                return KmrpNvidiaPresent::Failed;
            }
            Check("NvAPI_DRS_SaveSettings", saved);
        }

        if (!HoldsPreferNative(path)) throw Failure{"the setting did not read back after saving."};
        report((std::string("Done: NVIDIA's present method for swkotor.exe is Prefer native, in the profile \"") +
                Utf8(profileName) + "\". It applies from the next start of the game. To undo it: NVIDIA Control "
                "Panel -> Manage 3D settings -> Program Settings -> swkotor.exe -> Vulkan/OpenGL present method -> "
                "Use global setting. KMRP_NVIDIA.manifest beside the game records the change.").c_str());
        return KmrpNvidiaPresent::Set;
    } catch (const Failure& failure) {
        report((std::string("NVIDIA's present method for swkotor.exe could not be checked or set: ") +
                failure.what + kManualFix).c_str());
        return KmrpNvidiaPresent::Failed;
    }
}

#ifdef KMRP_NATIVE_RUNTIME
void KmrpRuntimeLog(const char* line);       // K1RuntimeEngine.cpp: one line into kmrp-kpm.log

namespace {
DWORD WINAPI PresentThread(LPVOID)
{
    wchar_t path[MAX_PATH];
    const DWORD n = GetModuleFileNameW(nullptr, path, MAX_PATH);
    if (n && n < MAX_PATH) KmrpNvidiaPresentMethod(path, &KmrpRuntimeLog);
    return 0;
}
}

// A thread of its own: the driver-settings calls load a DLL and read NVIDIA's
// database, which is no work for the game's GUI thread or for DllMain.
void KmrpNvidiaPresentOnce()
{
    static bool started = false;
    if (started) return;
    started = true;
    if (HANDLE thread = CreateThread(nullptr, 0, &PresentThread, nullptr, 0, nullptr)) CloseHandle(thread);
}
#endif
