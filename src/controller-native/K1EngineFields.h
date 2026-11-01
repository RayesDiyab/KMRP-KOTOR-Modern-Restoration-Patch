// The value each size field of the engine recipe takes at a screen size: the one rule the
// module applies (K1RuntimeEngine.cpp) and Test-EngineFields compiles on its own, as it
// needs nothing of the game. The fields and their kinds are tools/build_native_engine.py's
// (resolution_fields). The rules for these fields are documented with the Windows
// installer's reference copy (ResolutionPatch, src/patcher/InstallCore.cs).
#pragma once

#include "../../macos/tools/kmrp-iconsize.h"
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>

inline int KmrpRoundEven(double value)
{
    const double lower = std::floor(value), fraction = value - lower;
    return static_cast<int>(lower + (fraction > .5 ||
        (fraction == .5 && std::fmod(lower, 2.) != 0.) ? 1 : 0));
}

inline std::array<std::uint8_t, 4> KmrpEngineFieldValue(std::uint32_t va, std::uint32_t size, std::uint32_t kind,
    int base, int width, int height, int iconPercent)
{
    const float scale = height > 720 ? static_cast<float>(height) / 720.f : 1.f;
    const float marker = scale > 127.f / 16.f ? 127.f / 16.f : scale;
    int value = 0;
    std::array<std::uint8_t, 4> result{};
    switch (kind) {
    case 1: value = width; break;
    case 2: value = height; break;
    case 3:
        value = KmrpRoundEven(static_cast<float>(base) * scale);
        // The Icon Size slider (issue 80, kmrp-iconsize.h): the feat and power chart rows
        // (CSWGuiSkillFlowChart::AddPowerSet, AddFeatSet) and the Skills tab's rows
        // (CSWGuiInGameSkillEntry) grow with their icons where the icons outgrow them. At
        // the default (50%) every value is as before.
        if (va == 0x006CD8D9 || va == 0x006CDB79)
            value = kmrp_icon_chain_row(value, scale, iconPercent);
        else if (va == 0x006AB8EF || va == 0x006ACB20)
            value = kmrp_icon_skill_row(value, scale, iconPercent);
        break;
    case 4: value = -width; break;
    case 5: value = -height; break;
    case 6: value = KmrpRoundEven((width / 2) * 512 / 440.0); break;
    case 7: value = width / 2; break;
    case 8: value = height / 2; break;
    case 9: std::memcpy(result.data(), &scale, 4); return result;
    case 10: value = KmrpRoundEven(static_cast<float>(base) * marker); if (value < 1) value = 1; break;
    case 11: value = -KmrpRoundEven(static_cast<float>(-base) * marker); if (value > -1) value = -1; break;
    }
    std::memcpy(result.data(), &value, size);
    return result;
}
