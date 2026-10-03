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

namespace {
struct Extent { int left, top, width, height; };
struct Control { void* pointer; std::uintptr_t table; };
struct Panel { std::string resource; std::map<std::string, Control> controls; };
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
}

extern "C" void __cdecl KmrpPanelLayoutStartK1(void* panel, const char* resource)
{
    if (!panel || !resource) return;
    std::string name(resource, strnlen_s(resource, 16));
    if (name.empty() || name.find_first_of("/\\:") != std::string::npos) return;
    panels[panel] = {name, {}};
}
extern "C" void __cdecl KmrpPanelControlK1(void* panel, void* control, void* label)
{
    // Native InitControl is (CSWGuiControl* control, CExoString* label, int active).
    // At 40B935, PUSH EBP has shifted original esp+4 to esp+8 (control).
    auto found = panels.find(panel);
    if (found == panels.end() || !control || !label) return;
    const char* name = Field<const char*>(label, 0);
    unsigned size = Field<unsigned>(label, 4);
    // CExoString's allocation length includes the terminator (5E5ABE/5E5AC0).
    // GFF TAG stores only the characters, so never include that terminator in keys.
    if (name && size && size <= 256 && name[size - 1] == '\0') {
        const auto length = strnlen_s(name, size);
        if (length) found->second.controls[std::string(name, length)] = {control, Field<std::uintptr_t>(control, 0)};
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
        unsigned offset, count;
        if (!gff.field(0, "CONTROLS", 15, offset) || !gff.integer(gff.lists + offset, count) || count > 512 || !gff.range(gff.lists + offset + 4, count, 4)) return false;
        for (unsigned i = 0; i < count; ++i) {
            unsigned object; std::string tag; Extent extent;
            if (!gff.integer(gff.lists + offset + 4 + i * 4, object) || !gff.tag(object, tag) || !gff.extent(object, extent)) return false;
            auto found = item.second.controls.find(tag);
            if (found == item.second.controls.end()) continue;
            void* control = found->second.pointer;
            if (Field<void*>(control, 0x34) != panel || Field<std::uintptr_t>(control, 0) != found->second.table) return false;
            changes.push_back({control, extent});
        }
    }
    for (const auto& change : changes) {
        auto table = Field<std::uintptr_t*>(change.pointer, 0);
        reinterpret_cast<void(__thiscall*)(void*, const Extent*)>(table[1])(change.pointer, &change.extent);
    }
    previousWidth = width; previousHeight = height;
    return true;
}
