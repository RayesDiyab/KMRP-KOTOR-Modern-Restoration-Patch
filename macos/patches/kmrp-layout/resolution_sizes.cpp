// The sizes KMRP's Windows installer writes into swkotor.exe per resolution (ResolutionPatch.Apply
// in src/patcher/KmrpPatcher.cs), for the Mac build. All scale by one rule, s = max(1, H / 720),
// the rule the font atlases are baked at, and are computed exactly as the installer computes
// them: the product in single precision, rounded half to even (C#'s Math.Round, nearbyint here).
// Part of the kmrp-layout patch (kmrp_layout.cpp).
#include "sites.h"

#include <mach-o/dyld.h>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <iterator>
#include <string>

/*
  Text-list rows (Windows: the row float in .kfs, set by ResolutionPatch.Apply at RowScaleOffset;
  the hook at 0x00417992, tools/build_font_scale_wrapper.py; reverse-engineering/font.md)
  ----------------------------------------------------------------------------------------------
  List rows built from a list's template row (the save/load list, the journal's quest list, the
  resolution popup) are sized in code or copied from the template, and drawn with KMRP's
  enlarged fonts they overlap. Windows scales the row's height by s where the composite row
  setup copies it into the row: fild, fmul by the row float, fistp (round half to even).

  On the Mac that setup is CSWGuiButton::Initialize (0x1004a59e6; rect, text, border,
  highlight), which the template-row path (vtable + 0x140, 0x1004a5ab2) reaches for 12 row
  classes, the save-game entry among them, and which the journal's quest list calls. It copies
  the rect in two 8-byte moves at 0x1004a5a05 (15 bytes); those now jump to kmrp_button_stub,
  which makes the same copy, scales the height (the int at +0x14) by s exactly as the x87 code
  does (int to double, times the float s, rounded to nearest even: the product is exact in a
  double), and jumps back. rax and rdx, which the copy left holding the rect, are overwritten
  before they are read again. The inventory, store, skills and chain rows have initialisers of
  their own and are sized by the groups below instead. One direct caller outside the lists,
  0x1002b60c4 in the area-map code, is scaled too, as its Windows counterpart would be if it
  calls the same setup; not yet seen in play.
*/
extern "C" {
float kmrp_row_scale = 1.0f;  // s, set by AddResolutionSizes; read by the stub
}

__asm__(
    ".text\n"
    ".p2align 4\n"
    ".globl _kmrp_button_stub\n"
    "_kmrp_button_stub:\n"
    "    movq      (%rsi), %rax\n"             // the copy it replaces
    "    movq      8(%rsi), %rdx\n"
    "    movq      %rdx, 0x10(%rbx)\n"
    "    movq      %rax, 8(%rbx)\n"
    "    cvtsi2sdl 0x14(%rbx), %xmm0\n"        // height
    "    cvtss2sd  _kmrp_row_scale(%rip), %xmm1\n"
    "    mulsd     %xmm1, %xmm0\n"
    "    cvtsd2si  %xmm0, %eax\n"              // rounded to nearest even (MXCSR default)
    "    movl      %eax, 0x14(%rbx)\n"
    "    jmpq      *_kmrp_button_resume(%rip)\n"
    "_kmrp_button_resume:\n"
    "    .quad     0x1004a5a14\n"
    ".globl _kmrp_button_stub_end\n"
    "_kmrp_button_stub_end:\n");

extern "C" const uint8_t kmrp_button_stub[], kmrp_button_stub_end[];

namespace kmrp {
namespace {

// ResolutionPatch.ScaleForHeight: height / 720f, never below 1.
float ScaleForHeight(int height) {
    const float scale = static_cast<float>(height) / 720.0f;
    return scale < 1.0f ? 1.0f : scale;
}

// (int)Math.Round(base * scale).
int32_t Scaled(int base, float scale) {
    return static_cast<int32_t>(std::nearbyint(static_cast<double>(static_cast<float>(base) * scale)));
}

/*
  List rows (Windows: RowSizeGroups; reverse-engineering/inventory-item-rows.md)
  ----------------------------------------------------------------------------------------------
  Three screens build their list rows in code, each with a square icon box and a row height of
  the same size: inventory 56, store 56, skills 42 (vanilla's). The skills rows are scaled from
  50, as the Feats and Powers tabs' chain rows below, since 2026-09-30: the Abilities screen
  shows all three tabs in one list, and rows of two heights left one tab's gaps loose. Windows scales icon and height together
  (the icon alone grows into the row below). On the Mac each row's SetExtent keeps the icon
  size in a register (r13d, edx) but offsets the text by separate 8-bit copies of it, so those
  two instructions are pointed at the register: the text then starts after the icon whatever
  its size, as on Windows, where one register carries all three.

    inventory  CSWGuiInGameItemEntry::SetExtent 0x1002be3fe: icon mov r13d, 56 at 0x1002be441,
               text add r15d, 56 at 0x1002be4da, add eax, -56 at 0x1002be4e1;
               height: the row's initialiser 0x1002be608 builds {0, 0, width, 56} at 0x1002be870
               and hands it to SetExtent. The listbox takes every row's height from it
               (max(item height)), and no other 56 feeds it: every imm 56 in 0x1002bd000..
               0x1002c6000 was checked, and no packed {width, 56} constant exists in the binary.
    store      the container/store row (SetExtent 0x1002bfb06; the same shape): its icon is the
               row's height already (the widescreen patch's hook at 0x1002bfb49 reads it from
               the rect), so only the height, {0, 0, width, 56} at 0x1002bff6d, is written.
    skills     CSWGuiInGameSkillEntry::SetExtent: icon mov edx, 42 at 0x10022f256, text
               add eax, 42 at 0x10022f297, add esi, -42 at 0x10022f29d; height 42 at 0x10022f60b.
*/
void AddListRows(std::vector<Group>& groups, float s) {
    const int32_t row56 = Scaled(56, s), rowSkill = Scaled(50, s);
    groups.push_back({"inventory rows", {
        {0x1002be443, Int32(56), Int32(row56)},
        {0x1002be874, Int32(56), Int32(row56)},
        {0x1002be4da, Bytes({0x41, 0x83, 0xc7, 0x38}), Bytes({0x45, 0x01, 0xef, 0x90})},  // add r15d, r13d
        {0x1002be4e1, Bytes({0x83, 0xc0, 0xc8}), Bytes({0x44, 0x29, 0xe8})},              // sub eax, r13d
    }});
    groups.push_back({"store rows", {
        {0x1002bfb49, Bytes({0x44, 0x8b, 0x6b, 0x14, 0x90, 0x90}),  // the widescreen patch's icon hook
         Bytes({0x44, 0x8b, 0x6b, 0x14, 0x90, 0x90})},
        {0x1002bff71, Int32(56), Int32(row56)},
    }});
    groups.push_back({"skills rows", {
        {0x10022f257, Int32(42), Int32(rowSkill)},
        {0x10022f60f, Int32(42), Int32(rowSkill)},
        {0x10022f297, Bytes({0x83, 0xc0, 0x2a}), Bytes({0x01, 0xd0, 0x90})},  // add eax, edx
        {0x10022f29d, Bytes({0x83, 0xc6, 0xd6}), Bytes({0x29, 0xd6, 0x90})},  // sub esi, edx
    }});
}

/*
  Stack-count label (Windows: StackCountSites, .ksc)
  ----------------------------------------------------------------------------------------------
  The inventory row's quantity label, built in SetExtent and present in no .gui file: 19 high,
  21 wide for one or two digits and 42 for more, 37 below the row's top, right-aligned in the
  56 icon. Windows scales all four; there the 3+ digit width is 21 + 21, each scaled. On the
  Mac the top offset is an 8-bit operand (lea eax, [r12 + 37]), which stops at 127 (s = 3.4),
  as Windows' did until its .ksc stub, so the block 0x1002be4a0..0x1002be4d2 is rewritten with
  32-bit operands, in the same 50 bytes:

      vanilla                          rewritten
      cmp eax, 2                       cmp eax, 2
      mov eax, 42                      mov ecx, W          W = 21s
      mov ecx, 21                      jle +2
      cmovg ecx, eax                   add ecx, ecx        3+ digits: 2W
      lea rsi, [rbp - 0x68]            lea rsi, [rbp - 0x68]
      mov [rsi + 8], ecx               mov [rsi + 8], ecx
      mov eax, 56                      lea eax, [r15 + I]  I = 56s, the icon
      sub eax, ecx                     sub eax, ecx
      add eax, r15d                    mov [rsi], eax
      mov [rsi], eax                   lea eax, [r12 + T]  T = 37s
      lea eax, [r12 + 37]              mov [rsi + 4], eax
      mov [rsi + 4], eax               mov dword [rsi + 0xc], H   H = 19s
      mov dword [rsi + 0xc], 19        nop; nop

  No branch lands inside the block, nothing in it is RIP-relative, and eax and the flags are
  dead after it (the next instructions load rdi and call). At s = 1 it computes what vanilla
  does. Written with the inventory rows (the icon it aligns to is theirs).
*/
std::vector<uint8_t> StackLabelBlock(float s) {
    return Join({
        Bytes({0x83, 0xf8, 0x02}),                             // cmp eax, 2
        Bytes({0xb9}), Int32(Scaled(21, s)),                   // mov ecx, W
        Bytes({0x7e, 0x02}),                                   // jle +2
        Bytes({0x01, 0xc9}),                                   // add ecx, ecx
        Bytes({0x48, 0x8d, 0x75, 0x98}),                       // lea rsi, [rbp - 0x68]
        Bytes({0x89, 0x4e, 0x08}),                             // mov [rsi + 8], ecx
        Bytes({0x41, 0x8d, 0x87}), Int32(Scaled(56, s)),       // lea eax, [r15 + I]
        Bytes({0x29, 0xc8}),                                   // sub eax, ecx
        Bytes({0x89, 0x06}),                                   // mov [rsi], eax
        Bytes({0x41, 0x8d, 0x84, 0x24}), Int32(Scaled(37, s)), // lea eax, [r12 + T]
        Bytes({0x89, 0x46, 0x04}),                             // mov [rsi + 4], eax
        Bytes({0xc7, 0x46, 0x0c}), Int32(Scaled(19, s)),       // mov dword [rsi + 0xc], H
        Bytes({0x90, 0x90}),
    });
}

// A plain array, not a std::vector: see kmrp_layout.cpp on C++ globals.
const uint8_t kVanillaStackLabelBlock[] = {
    0x83, 0xf8, 0x02, 0xb8, 0x2a, 0x00, 0x00, 0x00, 0xb9, 0x15, 0x00, 0x00, 0x00, 0x0f, 0x4f, 0xc8,
    0x48, 0x8d, 0x75, 0x98, 0x89, 0x4e, 0x08, 0xb8, 0x38, 0x00, 0x00, 0x00, 0x29, 0xc8, 0x44, 0x01,
    0xf8, 0x89, 0x06, 0x41, 0x8d, 0x44, 0x24, 0x25, 0x89, 0x46, 0x04, 0xc7, 0x46, 0x0c, 0x13, 0x00,
    0x00, 0x00,
};

void AddStackLabel(std::vector<Group>& groups, float s) {
    const std::vector<uint8_t> vanilla(std::begin(kVanillaStackLabelBlock), std::end(kVanillaStackLabelBlock));
    groups.push_back({"stack-count label", {{0x1002be4a0, vanilla, StackLabelBlock(s)}}});
    // The store row draws the same label; its x follows the store icon, as the inventory's does.
    // (Windows scales only the inventory's label; the store's kept 21x19 at 37 here too until
    // 2026-10-09: the group after this one.)
    // The widescreen patch restores the vanilla mov eax, 56 here with UseGuiFileLayouts.
    groups.push_back({"store stack-count label", {{0x1002bfbc0, Int32(56), Int32(Scaled(56, s))}}});
    // And its width, height and place below the row's top, since 2026-10-09. The store's row
    // (CSWGuiStoreItemEntry::SetExtent, 0x1002bfb06) has the inventory's block byte for byte at
    // 0x1002bfba8, and only the icon in it was scaled: at 3840x2160 the count stood 37 px
    // under the top of a 168 px icon, 21 px wide, beside the icon's upper corner (the
    // maintainer saw it in a shop: "wrong only in the shop"). The icon's number, the five
    // bytes at 0x1002bfbbf, stays where it is and whoever writes the layout's sizes writes it
    // (above, or the widescreen patch); the 23 bytes before it and the 22 after are KMRP's:
    //
    //   cmp eax, 2 ; mov ecx, W ; jle +2 ; add ecx, ecx ; lea rsi, [rbp-0x68] ;
    //   mov [rsi+8], ecx ; mov edx, r12d ; nop                      W = 21s, twice for 3+ digits
    //   (mov eax, I)                                               I = 56s, the icon
    //   add edx, eax ; sub eax, ecx ; add eax, r15d ; mov [rsi], eax ;
    //   mov dword [rsi+0xc], H ; sub edx, [rsi+0xc] ; mov [rsi+4], edx      H = 19s
    //
    // The top is the row's top and the icon less the label's height, which is the game's 37
    // at its own size (56 - 19). edx is free here: the call that follows takes two arguments.
    const std::vector<uint8_t> before(std::begin(kVanillaStackLabelBlock), std::begin(kVanillaStackLabelBlock) + 23);
    const std::vector<uint8_t> after(std::begin(kVanillaStackLabelBlock) + 28, std::end(kVanillaStackLabelBlock));
    Group store{"store stack-count label's size and place", {
        {0x1002bfba8, before,
         Join({Bytes({0x83, 0xf8, 0x02, 0xb9}), Int32(Scaled(21, s)),
               Bytes({0x7e, 0x02, 0x01, 0xc9, 0x48, 0x8d, 0x75, 0x98, 0x89, 0x4e, 0x08, 0x44, 0x89, 0xe2, 0x90})})},
        {0x1002bfbc4, after,
         Join({Bytes({0x01, 0xc2, 0x29, 0xc8, 0x44, 0x01, 0xf8, 0x89, 0x06, 0xc7, 0x46, 0x0c}), Int32(Scaled(19, s)),
               Bytes({0x2b, 0x56, 0x0c, 0x89, 0x56, 0x04})})},
    }};
    store.own = true;
    groups.push_back(store);
}

/*
  Feat and power chain rows (Windows: RowSizeGroups, last entry)
  ----------------------------------------------------------------------------------------------
  The Powers and Feats tabs are not listbox rows: each row is a progression chain, built as a
  hard-coded 242x40 rect. Windows scales only the height, from 50 rather than the vanilla 40
  (chosen by eye in game: 40 read too small once everything around it grew). On the Mac both
  chain-row creators (0x10028d7bc, 0x10028dc90) load one 16-byte rect, {0, 0, 242, 40} at
  0x100570ef0 in __TEXT,__const, read by those two only, and pass it to CSWGuiSkillFlow::SetExtent
  (0x10028cb6a, Windows 0x006CCE30). The height is the int at 0x100570efc.
*/
void AddChainRows(std::vector<Group>& groups, float s) {
    groups.push_back({"feat and power chain rows", {{0x100570efc, Int32(40), Int32(Scaled(50, s))}}});
}

const uint8_t kVanillaButtonCopy[] = {
    0x48, 0x8b, 0x06, 0x48, 0x8b, 0x56, 0x08, 0x48, 0x89, 0x53, 0x10, 0x48, 0x89, 0x43, 0x08,
};

void AddTextListRows(std::vector<Group>& groups, float s) {
    kmrp_row_scale = s;
    std::vector<uint8_t> jump = {0xff, 0x25, 0x00, 0x00, 0x00, 0x00};  // jmp *0(%rip)
    const uint64_t target = reinterpret_cast<uintptr_t>(kmrp_button_stub);
    jump.resize(14);
    memcpy(jump.data() + 6, &target, 8);
    jump.resize(sizeof kVanillaButtonCopy, 0xcc);
    groups.push_back({"text-list rows", {
        {0x1004a5a05, std::vector<uint8_t>(std::begin(kVanillaButtonCopy), std::end(kVanillaButtonCopy)), jump},
    }});
}

/*
  The message popup (Windows: PopupSizeGroups; reverse-engineering/message-popup.md)
  ----------------------------------------------------------------------------------------------
  confirm.gui backs the shared message popup (Yes/No confirmations and every tutorial hint),
  which sizes itself in code: CSWGuiMessageBox::FixMessageLabel (0x100306552; Windows
  0x006253A0) widens it 40 at a time while it is narrower than 440 and grows it a line at a
  time while it is shorter than 280, and adds the icon's 32 to the panel's height and to the
  message's top. Windows scales them from a base at scale 1 (KMRP's own sizes, not vanilla):
  the auto-fit caps 800s and 450s, the icon 64s, which matches the tut_*.tga icons KMRP ships
  per resolution (the engine draws GUI art one texel per pixel, so the rect must equal the
  texture). Each cap has two sites; the Mac compiled two of the four tests as >= (cmp 439, 279):

    0x100306877  cmp edi, 440   width < 440: widen          -> 800s
    0x10030688b  cmp edi, 439   width > 439                  -> 800s - 1
    0x10030687f  cmp esi, 279   height > 279: stop           -> 450s - 1
    0x1003068fd  cmp esi, 279   height > 279: stop growing   -> 450s - 1
    0x1003065a1  mov ecx, 32    panel height and message top += icon   (Windows 0x0062540C) -> 64s
    0x100571bb0  {0, 10, 32, 32} the icon's rect, __TEXT,__const, read by the popup's
                 constructor (0x100305e50) only; width and height (Windows 0x00626F94) -> 64s

  The other numbers in the loop (widen by 40, grow only past 160) are not scaled on Windows
  either.

  The icon's size is taken from the tutorial icons installed in Override when they are there:
  every KMRP set ships them at exactly 64s (checked for all 66, 2026-09-29), so it is the same
  number, but a display the build has no set for gets the icons of the nearest set, a few
  pixels off 64s, and the rect must equal the texture or the engine tiles or crops it.
*/
// The width of Override/tut_attack.tga (square, as all KMRP's tut_* are), or 0 when it is not
// there: the game's executable is .../Contents/MacOS/KOTOR_Exe, Override is
// .../Contents/Assets/override.
int32_t InstalledTutorialIconSize() {
    char executable[4096];
    uint32_t length = sizeof executable;
    if (_NSGetExecutablePath(executable, &length) != 0) return 0;
    std::string path(executable);
    const size_t macos = path.rfind("/MacOS/");
    if (macos == std::string::npos) return 0;
    path = path.substr(0, macos) + "/Assets/override/tut_attack.tga";
    FILE* f = fopen(path.c_str(), "rb");
    if (!f) return 0;
    uint8_t header[18];
    const size_t got = fread(header, 1, sizeof header, f);
    fclose(f);
    if (got != sizeof header) return 0;
    const int32_t width = header[12] | header[13] << 8, height = header[14] | header[15] << 8;
    return (width > 0 && width == height) ? width : 0;
}

void AddMessagePopup(std::vector<Group>& groups, float s) {
    const int32_t installed = InstalledTutorialIconSize();
    const int32_t width = Scaled(800, s), height = Scaled(450, s), icon = installed ? installed : Scaled(64, s);
    groups.push_back({"message popup", {
        {0x100306879, Int32(440), Int32(width)},
        {0x10030688d, Int32(439), Int32(width - 1)},
        {0x100306881, Int32(279), Int32(height - 1)},
        {0x1003068ff, Int32(279), Int32(height - 1)},
        {0x1003065a2, Int32(32), Int32(icon)},
        {0x100571bb8, Join({Int32(32), Int32(32)}), Join({Int32(icon), Int32(icon)})},
    }});
}

/*
  Options check boxes (Windows: not yet; docs/windows-changes-from-macos.md, item 13)
  ----------------------------------------------------------------------------------------------
  The Options screens' toggles (Feedback's list, Auto-pause, Gameplay, Graphics, Advanced
  Graphics, Mouse, Advanced Sound) are CSWGuiOptionsCheckbox, one vtable (0x1005AC6A8), built by
  the Options screens' code only. Its SetExtent (0x1002CECEE; Windows 0x006DE000) puts the
  circle's four state images (+0xB0, +0x138, +0x250, +0x2D8) in a fixed 25x25 square at the
  control's left, 2 below its middle, and the label (the text control at +0x1B8) 30 in, at
  every size: at 3024x1964 a 25-px circle in 117- to 164-px toggles, where vanilla drew it in
  43- and 60-px ones at 640x480 and 1280x720 (found by reading the code, 2026-09-30). The
  function is replaced: a 14-byte absolute jump over its 17-byte prologue goes to
  CheckboxExtent, which does the same with 25s, 30s and 2s (68, 82 and 5 at 3024x1964),
  the text through the same call (0x1004A3D4C), and returns to the caller as the original did.
*/
int32_t g_checkbox_box = 25, g_checkbox_label = 30, g_checkbox_drop = 2;

void CheckboxExtent(void* self, const int32_t* rect) {
    char* box = static_cast<char*>(self);
    const int32_t left = rect[0], top = rect[1], width = rect[2], height = rect[3];
    const int32_t y = top + g_checkbox_drop + (height - g_checkbox_box) / 2;  // truncated, as sar
    for (const size_t image : {0xb0, 0x138, 0x2d8, 0x250}) {
        const int32_t square[4] = {left, y, g_checkbox_box, g_checkbox_box};
        memcpy(box + image, square, sizeof square);
    }
    const int32_t text[4] = {left + g_checkbox_label, top, width - g_checkbox_label, height};
    reinterpret_cast<void (*)(void*, const int32_t*)>(0x1004a3d4cUL)(box + 0x1b8, text);
    memcpy(box + 0x8, rect, 16);   // the control's own extent
}

void AddCheckboxes(std::vector<Group>& groups, float s) {
    g_checkbox_box = Scaled(25, s);
    g_checkbox_label = Scaled(30, s);
    g_checkbox_drop = Scaled(2, s);
    std::vector<uint8_t> jump = {0xff, 0x25, 0x00, 0x00, 0x00, 0x00};  // jmp *0(%rip)
    const uint64_t target = reinterpret_cast<uintptr_t>(&CheckboxExtent);
    jump.resize(14);
    memcpy(jump.data() + 6, &target, 8);
    jump.resize(17, 0xcc);
    groups.push_back({"options check boxes", {
        {0x1002cecee, Bytes({0x55, 0x48, 0x89, 0xe5, 0x41, 0x56, 0x53, 0x48, 0x83, 0xec, 0x10,
                             0x49, 0x89, 0xf6, 0x48, 0x89, 0xfb}), jump},
    }});
}

}  // namespace

// AddResolutionSizes also sets kmrp_row_scale, which the text-list row stub reads.
void AddResolutionSizes(std::vector<Group>& groups, int height) {
    const float s = ScaleForHeight(height);
    AddTextListRows(groups, s);
    AddListRows(groups, s);
    AddStackLabel(groups, s);
    AddChainRows(groups, s);
    AddMessagePopup(groups, s);
    AddCheckboxes(groups, s);
}

}  // namespace kmrp
