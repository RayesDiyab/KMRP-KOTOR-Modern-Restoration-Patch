// Reapply authored geometry to existing native controls after a mode change.
// Text, event bindings, focus, list selection and control ownership remain native.
#include "K1RuntimeLayout.h"
#include "K1RuntimeAssets.h"
#include <windows.h>
#include <map>
#include <vector>
#include <string>
#include <cstring>
#include <cstdint>
#include <cmath>

namespace {
struct Extent { int left, top, width, height; };
bool operator==(const Extent& a, const Extent& b)
{
    return a.left == b.left && a.top == b.top && a.width == b.width && a.height == b.height;
}
// A control, the extent its layout file gave it for the size last applied, and
// what the engine's own code had added to that (`moved`, measured at `scale`).
struct Control {
    void* pointer; std::uintptr_t table;
    bool known = false; Extent file{};
    bool adjusted = false; Extent moved{}; double scale = 1;
};
struct Panel { std::string resource; std::map<std::string, Control> controls; std::map<std::string, Extent> file; };
std::map<void*, Panel> panels;
int previousWidth = 0, previousHeight = 0;
template<class T> T& Field(void* p, unsigned at) { return *reinterpret_cast<T*>(static_cast<char*>(p) + at); }

struct Gff {
    std::vector<unsigned char> data;
    unsigned structure = 0, structures = 0, fields = 0, fieldCount = 0;
    unsigned labels = 0, labelCount = 0, values = 0, indices = 0, lists = 0;
    bool integer(unsigned at, unsigned& value) const {
        if (at > data.size() || data.size() - at < 4) return false;
        std::memcpy(&value, data.data() + at, 4); return true;
    }
    bool range(unsigned at, unsigned count, unsigned size) const {
        return at <= data.size() && std::uint64_t(count) * size <= data.size() - at;
    }
    bool load(const std::wstring& path) {
        HANDLE file = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING, 0, nullptr);
        if (file == INVALID_HANDLE_VALUE) return false;
        DWORD size = GetFileSize(file, nullptr), got = 0;
        bool ok = size >= 56 && size < (16u << 20);
        if (ok) { data.resize(size); ok = ReadFile(file, data.data(), size, &got, nullptr) && got == size; }
        CloseHandle(file);
        if (!ok || std::memcmp(data.data(), "GUI V3.2", 8)) return false;
        return integer(8, structure) && integer(12, structures) && integer(16, fields) && integer(20, fieldCount) &&
            integer(24, labels) && integer(28, labelCount) && integer(32, values) && integer(40, indices) && integer(48, lists) &&
            range(structure, structures, 12) && range(fields, fieldCount, 12) && range(labels, labelCount, 16);
    }
    bool field(unsigned object, const char* name, unsigned type, unsigned& value) const {
        if (object >= structures) return false;
        unsigned count, start;
        if (!integer(structure + object * 12 + 4, start) || !integer(structure + object * 12 + 8, count) || count > fieldCount) return false;
        for (unsigned i = 0; i < count; ++i) {
            unsigned index = start, label, actualType;
            if (count > 1 && !integer(indices + start + i * 4, index)) return false;
            if (index >= fieldCount || !integer(fields + index * 12, actualType) || !integer(fields + index * 12 + 4, label) || label >= labelCount) return false;
            char text[17]{}; std::memcpy(text, data.data() + labels + label * 16, 16);
            if (!std::strcmp(text, name)) return actualType == type && integer(fields + index * 12 + 8, value);
        }
        return false;
    }
    bool extent(unsigned object, Extent& result) const {
        unsigned child, left, top, width, height;
        if (!field(object, "EXTENT", 14, child) || !field(child, "LEFT", 5, left) || !field(child, "TOP", 5, top) ||
            !field(child, "WIDTH", 5, width) || !field(child, "HEIGHT", 5, height)) return false;
        result = {static_cast<int>(left), static_cast<int>(top), static_cast<int>(width), static_cast<int>(height)};
        return result.width >= 0 && result.height >= 0 && result.width <= 32767 && result.height <= 32767;
    }
    bool tag(unsigned object, std::string& result) const {
        unsigned offset, size;
        if (!field(object, "TAG", 10, offset) || !integer(values + offset, size) || size > 255 || !range(values + offset + 4, size, 1)) return false;
        result.assign(reinterpret_cast<const char*>(data.data() + values + offset + 4), size); return true;
    }
};
struct Change { void* pointer; Extent extent; };

double Scale(int height) { return height > 720 ? height / 720.0 : 1.0; }

// `moved`, measured at one scale, at another: the shared rule, rounded to nearest.
Extent Scaled(const Extent& moved, double from, double to)
{
    const auto at = [from, to](int value) { return static_cast<int>(std::lround(value * to / from)); };
    return {at(moved.left), at(moved.top), at(moved.width), at(moved.height)};
}

// Every top-level control's extent in a layout file, by tag.
bool FileExtents(const Gff& gff, std::map<std::string, Extent>& result)
{
    unsigned offset, count;
    if (!gff.field(0, "CONTROLS", 15, offset) || !gff.integer(gff.lists + offset, count) || count > 512 ||
        !gff.range(gff.lists + offset + 4, count, 4)) return false;
    for (unsigned i = 0; i < count; ++i) {
        unsigned object; std::string tag; Extent extent;
        if (!gff.integer(gff.lists + offset + 4 + i * 4, object) || !gff.tag(object, tag) || !gff.extent(object, extent)) return false;
        result[tag] = extent;
    }
    return true;
}
}

// Stack arguments arrive as the address of their slot (KPM's "esp+N").
extern "C" void __cdecl KmrpPanelLayoutStartK1(void* panel, const char** slot)
{
    const char* resource = slot ? *slot : nullptr;
    if (!panel || !resource) return;
    std::string name(resource, strnlen_s(resource, 16));
    if (name.empty() || name.find_first_of("/\\:") != std::string::npos) return;
    Panel& entry = panels[panel];
    entry = Panel{};
    entry.resource = name;
    // The file the engine is about to load, for the size in force: the baseline
    // each control's later position is compared with.
    Gff gff;
    if (gff.load(KmrpRuntimeAssetDirectory() + L"\\" + std::wstring(name.begin(), name.end()) + L".gui"))
        FileExtents(gff, entry.file);
}
extern "C" void __cdecl KmrpPanelControlK1(void* panel, void** controlSlot, void** labelSlot)
{
    if (!controlSlot || !labelSlot) return;
    void* control = *controlSlot;
    void* label = *labelSlot;
    // Native InitControl is (CSWGuiControl* control, CExoString* label, int active).
    auto found = panels.find(panel);
    if (found == panels.end() || !control || !label) return;
    const char* name = Field<const char*>(label, 0);
    unsigned size = Field<unsigned>(label, 4);
    // CExoString's allocation length includes the terminator (5E5ABE/5E5AC0).
    // GFF TAG stores only the characters, so never include that terminator in keys.
    if (name && size && size <= 256 && name[size - 1] == '\0') {
        const auto length = strnlen_s(name, size);
        if (length) {
            const std::string tag(name, length);
            Control entry{control, Field<std::uintptr_t>(control, 0)};
            const auto file = found->second.file.find(tag);
            if (file != found->second.file.end()) { entry.known = true; entry.file = file->second; }
            found->second.controls[tag] = entry;
        }
    }
}
extern "C" void __cdecl KmrpPanelDestroyedK1(void* panel) { panels.erase(panel); }
extern "C" void __cdecl KmrpControlDestroyedK1(void* control)
{
    for (auto& panel : panels) for (auto at = panel.second.controls.begin(); at != panel.second.controls.end();) {
        if (at->second.pointer == control) at = panel.second.controls.erase(at); else ++at;
    }
}

bool KmrpRuntimeLayoutDimensions(void* manager, int width, int height)
{
    if (!previousWidth) { previousWidth = width; previousHeight = height; return true; }
    if (width == previousWidth && height == previousHeight) return true;
    std::vector<Change> changes;
    const double oldScale = Scale(previousHeight), newScale = Scale(height);
    for (auto& item : panels) {
        void* panel = item.first;
        if (Field<void*>(panel, 0x18) != manager) continue;
        Gff gff;
        std::wstring name(item.second.resource.begin(), item.second.resource.end());
        if (!gff.load(KmrpRuntimeAssetDirectory() + L"\\" + name + L".gui")) continue;
        Extent root;
        if (!gff.extent(0, root)) return false;
        const Extent old = Field<Extent>(panel, 4);
        if (old.width != previousWidth && old.left == (previousWidth - old.width) / 2) root.left = (width - root.width) / 2;
        if (old.height != previousHeight && old.top == (previousHeight - old.height) / 2) root.top = (height - root.height) / 2;
        changes.push_back({panel, root});
        std::map<std::string, Extent> file;
        if (!FileExtents(gff, file)) return false;
        for (const auto& entry : file) {
            auto found = item.second.controls.find(entry.first);
            if (found == item.second.controls.end()) continue;
            Control& tracked = found->second;
            void* control = tracked.pointer;
            if (Field<void*>(control, 0x34) != panel || Field<std::uintptr_t>(control, 0) != tracked.table) return false;
            const Extent now = Field<Extent>(control, 4);
            Extent target = entry.second;
            if (now == target) {
                // The engine has already laid this one out for the new size.
                tracked.adjusted = false;
            } else if (tracked.known) {
                // What the engine's code added to the file after loading it is kept,
                // at the new scale. The Options screen moves its five buttons down
                // after the load; reapplying the bare file put them 20 px high at
                // 1080 lines (measured 2026-10-04). `moved` is remembered at the
                // scale it was measured, so a round trip returns the same pixels.
                const Extent moved = {now.left - tracked.file.left, now.top - tracked.file.top,
                                      now.width - tracked.file.width, now.height - tracked.file.height};
                if (moved == Extent{0, 0, 0, 0}) {
                    tracked.adjusted = false;
                } else if (!tracked.adjusted || !(moved == Scaled(tracked.moved, tracked.scale, oldScale))) {
                    tracked.adjusted = true; tracked.moved = moved; tracked.scale = oldScale;
                }
                if (tracked.adjusted) {
                    const Extent add = Scaled(tracked.moved, tracked.scale, newScale);
                    target = {target.left + add.left, target.top + add.top, target.width + add.width, target.height + add.height};
                    if (target.width < 0) target.width = 0;
                    if (target.height < 0) target.height = 0;
                }
            }
            tracked.known = true; tracked.file = entry.second;
            if (!(now == target)) changes.push_back({control, target});
        }
        item.second.file.swap(file);
    }
    for (const auto& change : changes) {
        auto table = Field<std::uintptr_t*>(change.pointer, 0);
        reinterpret_cast<void(__thiscall*)(void*, const Extent*)>(table[1])(change.pointer, &change.extent);
    }
    previousWidth = width; previousHeight = height;
    return true;
}
