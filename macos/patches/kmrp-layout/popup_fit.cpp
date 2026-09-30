/*
  The message popup, fitted to its contents
  ----------------------------------------------------------------------------------------------
  confirm.gui's panel is sized for the tallest case (reverse-engineering/message-popup.md: 525
  units at 3440x1440 so a Yes/No box's Cancel is inside it), and the popup never shrinks it:
  CSWGuiMessageBox::FixMessageLabel (0x100306552; Windows 0x006253A0) starts from the file's
  panel and message sizes, adds the icon, takes one button's height off when there is one,
  grows the message until its text fits, then hangs OK 4 px under the message and Cancel 2 px
  under OK. The message box keeps the file's height, sized for a four-line tutorial text, so a
  one-line question leaves a gap above the buttons, and the panel keeps its height, so there
  is more space below them. Measured at 3024x1964 (2026-09-30): the Exit Game box is 711 px
  tall for about 430 px of contents, 165 px empty above OK and 250 below Cancel.

  The width is the file's too, widened 40 at a time while the text does not fit: a one-line
  question sat in a box sized for a tutorial paragraph (the Exit Game box, 1,224 px wide for
  "Do you really want to quit?").

  This runs at the end of FixMessageLabel, in place of its last call (0x100306a88,
  `call 0x10049dc36`, which it then makes), when the text fits without a scrollbar:
    1. the message box narrows to the least width at which its text still wraps to the same
       height, found by halving and tested with the engine's own wrapping, but never narrower
       than the widest shown button or the icon: a one-line question shrinks to its sentence,
       a paragraph keeps its line count;
    2. it shrinks to its text: its inner height (+0x344 of the list) less the list's own fit
       test, padding (+0x373) plus the tallest item (+0x368);
    3. OK and Cancel move up under it, 4 and 2 px apart, and the icon and the buttons are
       centred across the panel, as FixMessageLabel places them;
    4. the panel keeps the message's margins -- as wide as the message plus its left inset
       on both sides, and ending as far below the last shown button as the message starts
       below the panel's top in the file (the message's saved top, +0xC04) -- and keeps its
       centre, as FixMessageLabel does when it changes a size (the corner moves by half).
  The message list and its text are rebuilt the way FixMessageLabel does after each resize:
  the list's SetExtent (0x1004A81AE), then 0x100306B86, which sizes the text label to the
  list and puts it back in. Controls are placed relative to the panel, so they move with it.

  CSWGuiMessageBox, read from FixMessageLabel: the panel's extent at +0x8 (left, top, width,
  height), set through the vtable's +0x10; the message list (CSWGuiListBox) at +0x850, its
  extent at +0x858; OK at +0x3D0 and Cancel at +0x610, each a button with its extent at +0x8,
  set by 0x1004A5ADC, shown while bit 0x2 of its +0x68 is set (FixMessageLabel's own test);
  the icon, a label at +0x238 with its extent at +0x240, set by 0x1004A56F0, shown when bit
  0x10 of +0x79 is set.
*/
#include "sites.h"

#include <cstdint>
#include <cstring>

namespace {

const uintptr_t kFixMessageLabelLastCall = 0x100306a88;  // call 0x10049dc36
const uintptr_t kPanelFinish = 0x10049dc36;
const auto ListSetExtent = reinterpret_cast<void (*)(void*, const int32_t*)>(0x1004a81aeUL);
const auto RebuildMessage = reinterpret_cast<void (*)(void*)>(0x100306b86UL);
const auto ButtonSetExtent = reinterpret_cast<void (*)(void*, const int32_t*)>(0x1004a5adcUL);
const auto LabelSetExtent = reinterpret_cast<void (*)(void*, const int32_t*)>(0x1004a56f0UL);

const size_t kExtent = 0x8, kList = 0x850, kOk = 0x3d0, kCancel = 0x610, kIcon = 0x238;
const size_t kSavedMessageTop = 0xc04, kIconFlags = 0x79;
const size_t kListInner = 0x344, kListItem = 0x368, kListPad = 0x373, kButtonFlags = 0x68;

template <typename T> T& At(void* base, size_t offset) {
    return *reinterpret_cast<T*>(static_cast<char*>(base) + offset);
}

bool Shown(void* box, size_t button) { return (At<uint8_t>(box, button + kButtonFlags) & 0x2) != 0; }

// The message at `extent`, rebuilt as FixMessageLabel rebuilds it after a resize.
void Relayout(void* box, void* list, const int32_t* extent) {
    ListSetExtent(list, extent);
    RebuildMessage(box);
}

bool Fits(void* list) {   // the list's own test, as FixMessageLabel makes it
    return At<uint8_t>(list, kListPad) + At<int32_t>(list, kListItem) <= At<int32_t>(list, kListInner);
}

// x of a control of width `width` centred across `across`, in FixMessageLabel's arithmetic.
int32_t Centred(int32_t across, int32_t width) { return across / 2 - width / 2; }

}  // namespace

extern "C" __attribute__((visibility("default"))) void KMRP_FitMessageBox(void* box) {
    char* const base = static_cast<char*>(box);
    void* list = base + kList;
    const int32_t item = At<int32_t>(list, kListItem);
    if (item <= 0 || !Fits(list)) return;   // no text, or it needs the scrollbar: as the engine left it
    int32_t message[4], ok[4], cancel[4], icon[4], panel[4];
    memcpy(message, &At<int32_t>(list, kExtent), sizeof message);
    memcpy(ok, &At<int32_t>(box, kOk + kExtent), sizeof ok);
    memcpy(cancel, &At<int32_t>(box, kCancel + kExtent), sizeof cancel);
    memcpy(icon, &At<int32_t>(box, kIcon + kExtent), sizeof icon);
    memcpy(panel, &At<int32_t>(box, kExtent), sizeof panel);
    const bool hasIcon = (At<uint8_t>(box, kIconFlags) & 0x10) != 0;

    // 1. The least width at which the text wraps to the same height, halving between the
    //    widest thing that must fit and the width it has.
    int32_t least = 1;
    if (Shown(box, kOk) && ok[2] > least) least = ok[2];
    if (Shown(box, kCancel) && cancel[2] > least) least = cancel[2];
    if (hasIcon && icon[2] > least) least = icon[2];
    int32_t low = least, high = message[2];
    while (low < high) {
        message[2] = low + (high - low) / 2;
        Relayout(box, list, message);
        if (At<int32_t>(list, kListItem) == item && Fits(list)) high = message[2];
        else low = message[2] + 1;
    }
    message[2] = high;
    Relayout(box, list, message);

    // 2. Down to its text.
    const int32_t slack = At<int32_t>(list, kListInner) - (At<uint8_t>(list, kListPad) + At<int32_t>(list, kListItem));
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
    int32_t width = message[2] + 2 * message[0];
    if (width > panel[2]) width = panel[2];
    ok[0] = Centred(width, ok[2]);
    ok[1] = message[1] + message[3] + 4;
    cancel[0] = Centred(width, cancel[2]);
    cancel[1] = ok[1] + ok[3] + 2;
    ButtonSetExtent(base + kOk, ok);
    ButtonSetExtent(base + kCancel, cancel);
    icon[0] = Centred(width, icon[2]);
    LabelSetExtent(base + kIcon, icon);
    int32_t bottom = message[1] + message[3];
    if (Shown(box, kOk)) bottom = ok[1] + ok[3];
    if (Shown(box, kCancel)) bottom = cancel[1] + cancel[3];

    // 4. The panel, with the message's margins all round, about its old centre.
    const int32_t height = bottom + At<int32_t>(box, kSavedMessageTop);
    panel[0] += (panel[2] - width) / 2;
    panel[2] = width;
    if (height < panel[3]) {
        panel[1] += (panel[3] - height) / 2;
        panel[3] = height;
    }
    using SetExtent = void (*)(void*, const int32_t*);
    (*reinterpret_cast<SetExtent*>(*reinterpret_cast<char**>(box) + 0x10))(box, panel);
}

// Reached by a 5-byte call from FixMessageLabel through the near page (area_map.cpp's thunks):
// rdi is the message box, as for the call it replaces. The fit, then that call, whose return
// goes back to FixMessageLabel's epilogue. The stack is 16-aligned at the inner call.
__asm__(
    ".text\n"
    ".globl _kmrp_popup_stub\n"
    "_kmrp_popup_stub:\n"
    "    pushq   %rdi\n"
    "    call    _KMRP_FitMessageBox\n"
    "    popq    %rdi\n"
    "    jmp     *_kmrp_panel_finish(%rip)\n"
    "_kmrp_panel_finish:\n"
    "    .quad   0x10049dc36\n"
    ".globl _kmrp_popup_stub_end\n"
    "_kmrp_popup_stub_end:\n");

namespace kmrp {

void AddPopupFit(std::vector<Group>& groups, uintptr_t nearPage) {
    if (!nearPage) return;   // the constructor could not place the page: the popup stays as it is
    const auto call = [](uintptr_t site, uintptr_t target) {
        const int32_t rel = static_cast<int32_t>(static_cast<int64_t>(target) - static_cast<int64_t>(site + 5));
        return Join({Bytes({0xe8}), Int32(rel)});
    };
    groups.push_back({"message popup fit", {
        {kFixMessageLabelLastCall, call(kFixMessageLabelLastCall, kPanelFinish),
         call(kFixMessageLabelLastCall, nearPage + kPopupThunk)},
    }});
}

}  // namespace kmrp
