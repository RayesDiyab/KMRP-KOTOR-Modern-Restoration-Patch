// KMRP for macOS: the text sizes, font and icon size the Text Size and Font page chooses, as the
// module holds them (text_settings.cpp). The rules are Windows' own header, K1TextOptionsPolicy.h,
// and the arithmetic of the icons macos/tools/kmrp-iconsize.h. Saved in swkotor.ini, in
// [KMRP Text], with Windows' keys.
#pragma once

#include "../../../src/controller-native/K1TextOptionsPolicy.h"

namespace kmrp {
namespace textfit {

// What is in force now, and what swkotor.ini holds. Reading either reads the file the first time.
KmrpTextOptions::Settings& Live();
KmrpTextOptions::Settings& Saved();
bool WriteSettings(const KmrpTextOptions::Settings& settings);
int FontStyle();

}  // namespace textfit
}  // namespace kmrp
