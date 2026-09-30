// The message popup, fitted to its contents (Windows).
//
// The Windows side of macos/patches/kmrp-layout/popup_fit.cpp, which the Mac has had
// since 2026-09-30 (docs/windows-changes-from-macos.md, item 1; the maintainer, the same
// evening: "you didnt apply the quit game fixes we did on macos"). The same four steps
// with the same arithmetic, on Windows' offsets, read from CSWGuiMessageBox::
// FixMessageLabel (0x006253A0) on 2026-09-30.
//
// confirm.gui's panel is sized for the tallest case, and FixMessageLabel never shrinks
// it: it starts from the file's panel and message sizes (saved at +0x95C and +0x96C),
// adds the icon, widens the message 40 at a time while the text does not fit, then hangs
// OK 4 px under the message and Cancel 2 px under OK and centres the panel on the screen
// (0x0040A600). The message keeps the file's height, sized for a four-line tutorial, so a
// one-line question sat in a box sized for a paragraph: the Exit Game box was 1,224x711 px
// at 3024x1964 on the Mac, for "Do you really want to quit?".
//
// FitMessageBoxK1 runs at the end of FixMessageLabel (the hook at 0x006258E2, after its
// last call), when the text fits without a scrollbar:
//   1. the message narrows to the least width at which its text wraps to the same height,
//      found by halving and tested with the engine's own wrapping, but never narrower than
//      the widest shown button or the icon;
//   2. it shrinks to its text: its inner height less the list's own fit test, padding plus
//      the tallest item;
//   3. OK and Cancel move up under it, 4 and 2 px apart, and the icon and the buttons are
//      centred across the panel, as FixMessageLabel places them;
//   4. the panel keeps the message's margins -- as wide as the message plus its left inset
//      on both sides, and ending as far below the last shown button as the message starts
//      below the panel's top in the file -- and is centred on the screen again with
//      FixMessageLabel's own last call.
// The message is rebuilt after each resize as FixMessageLabel rebuilds it: the list's
// SetExtent, then 0x006252F0, which sizes the text label to the list and puts it back in.
// Controls are placed relative to the panel, so they move with it.
//
// CSWGuiMessageBox on Windows, from FixMessageLabel: the panel's extent at +0x4 (left,
// top, width, height), set through vtable slot 1 like every control's; the message list
// (CSWGuiListBox) at +0x67C, its extent at +0x680, inner height +0x298, tallest item
// +0x2B4, padding (byte) +0x2C0; OK at +0x2F4 and Cancel at +0x4B8, buttons with their
// extent at +0x4, shown while bit 0x2 of their +0x44 is set (FixMessageLabel's own test);
// the icon, a label at +0x1B4, shown when bit 0x10 of the box's +0x64 is set; the file's
// message top at +0x970.
#include <cstdint>
#include <cstring>

namespace {

constexpr std::uintptr_t kRebuildMessage = 0x006252F0;   // thiscall, the box
constexpr std::uintptr_t kCentreOnScreen = 0x0040A600;   // thiscall, the box

constexpr std::size_t kExtent = 0x4, kList = 0x67C, kOk = 0x2F4, kCancel = 0x4B8, kIcon = 0x1B4;
constexpr std::size_t kSavedMessageTop = 0x970, kIconFlags = 0x64, kButtonFlags = 0x44;
constexpr std::size_t kListInner = 0x298, kListItem = 0x2B4, kListPad = 0x2C0;

template <typename T> T& At(void* base, std::size_t offset) {
    return *reinterpret_cast<T*>(static_cast<char*>(base) + offset);
}

using ThisCall = void(__thiscall*)(void*);
using SetExtentCall = void(__thiscall*)(void*, const std::int32_t*);

// Every control's SetExtent is its vtable's slot 1 (FixMessageLabel calls [vtable+4]).
void SetExtent(void* control, const std::int32_t* extent) {
    SetExtentCall call = (*reinterpret_cast<SetExtentCall**>(control))[1];
    call(control, extent);
}

bool Shown(void* box, std::size_t button) {
    return (At<std::uint8_t>(box, button + kButtonFlags) & 0x2) != 0;
}

// The message at `extent`, rebuilt as FixMessageLabel rebuilds it after a resize.
void Relayout(void* box, void* list, const std::int32_t* extent) {
    SetExtent(list, extent);
    reinterpret_cast<ThisCall>(kRebuildMessage)(box);
}

bool Fits(void* list) {   // the list's own test, as FixMessageLabel makes it
    return At<std::uint8_t>(list, kListPad) + At<std::int32_t>(list, kListItem)
        <= At<std::int32_t>(list, kListInner);
}

// x of a control of width `width` centred across `across`, in FixMessageLabel's arithmetic.
std::int32_t Centred(std::int32_t across, std::int32_t width) { return across / 2 - width / 2; }

}  // namespace

extern "C" void __cdecl FitMessageBoxK1(void* box) {
    if (!box) return;
    char* const base = static_cast<char*>(box);
    void* list = base + kList;
    const std::int32_t item = At<std::int32_t>(list, kListItem);
    if (item <= 0 || !Fits(list)) return;   // no text, or it needs the scrollbar: as the engine left it
    std::int32_t message[4], ok[4], cancel[4], icon[4], panel[4];
    std::memcpy(message, &At<std::int32_t>(list, kExtent), sizeof message);
    std::memcpy(ok, &At<std::int32_t>(box, kOk + kExtent), sizeof ok);
    std::memcpy(cancel, &At<std::int32_t>(box, kCancel + kExtent), sizeof cancel);
    std::memcpy(icon, &At<std::int32_t>(box, kIcon + kExtent), sizeof icon);
    std::memcpy(panel, &At<std::int32_t>(box, kExtent), sizeof panel);
    const bool hasIcon = (At<std::uint8_t>(box, kIconFlags) & 0x10) != 0;

    // 1. The least width at which the text wraps to the same height, halving between the
    //    widest thing that must fit and the width it has.
    std::int32_t least = 1;
    if (Shown(box, kOk) && ok[2] > least) least = ok[2];
    if (Shown(box, kCancel) && cancel[2] > least) least = cancel[2];
    if (hasIcon && icon[2] > least) least = icon[2];
    std::int32_t low = least, high = message[2];
    while (low < high) {
        message[2] = low + (high - low) / 2;
        Relayout(box, list, message);
        if (At<std::int32_t>(list, kListItem) == item && Fits(list)) high = message[2];
        else low = message[2] + 1;
    }
    message[2] = high;
    Relayout(box, list, message);

    // 2. Down to its text.
    const std::int32_t slack = At<std::int32_t>(list, kListInner)
        - (At<std::uint8_t>(list, kListPad) + At<std::int32_t>(list, kListItem));
    if (slack > 0) {
        message[3] -= slack;
        Relayout(box, list, message);
        if (!Fits(list)) {                   // the text no longer fits: put the height back
            message[3] += slack;
            Relayout(box, list, message);
        }
    }

    // 3. The buttons under it and everything centred across the panel's new width: the
    //    message and its left inset on both sides, never wider than the panel was.
    std::int32_t width = message[2] + 2 * message[0];
    if (width > panel[2]) width = panel[2];
    ok[0] = Centred(width, ok[2]);
    ok[1] = message[1] + message[3] + 4;
    cancel[0] = Centred(width, cancel[2]);
    cancel[1] = ok[1] + ok[3] + 2;
    SetExtent(base + kOk, ok);
    SetExtent(base + kCancel, cancel);
    icon[0] = Centred(width, icon[2]);
    SetExtent(base + kIcon, icon);
    std::int32_t bottom = message[1] + message[3];
    if (Shown(box, kOk)) bottom = ok[1] + ok[3];
    if (Shown(box, kCancel)) bottom = cancel[1] + cancel[3];

    // 4. The panel, with the message's margins all round, centred on the screen again as
    //    FixMessageLabel's last call centres it.
    const std::int32_t height = bottom + At<std::int32_t>(box, kSavedMessageTop);
    panel[0] += (panel[2] - width) / 2;
    panel[2] = width;
    if (height < panel[3]) {
        panel[1] += (panel[3] - height) / 2;
        panel[3] = height;
    }
    SetExtent(box, panel);
    reinterpret_cast<ThisCall>(kCentreOnScreen)(box);
}
