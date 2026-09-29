/*
  PADDING as a gutter on the scrollbar's side (Windows: gold v11 and v12,
  tools/build_listbox_padding_fix.py, tools/build_gutter_side_fix.py;
  reverse-engineering/listbox-geometry.md)
  ----------------------------------------------------------------------------------------------
  A list box's PADDING byte (.gui) does six jobs in vanilla: the rows' left edge, a matching
  inset on the right, a gap above the first row, a gap between rows (pitch = row height +
  PADDING), and the "does a row fit?" test. KMRP's .gui files are laid out for what Windows
  gold v11 and v12 make of it: a horizontal gutter only, on the side the scrollbar is on.
    left  = LEFTSCROLLBAR ? PADDING : 0      width = contentWidth - PADDING
    top of the first row = 0                 pitch = row height
  Without this, on the Mac the rows were spaced apart by PADDING (inventory at 3024x1964: 153 px
  rows with a gap between each), and a description pane, whose bar is on the right, had its
  gutter on the left and its text running into the bar (both seen 2026-09-29).

  LEFTSCROLLBAR is bit 0x10 of the flags at [listbox + 0x370]: CSWGuiListBox::SetExtent
  (0x1004a81ae) adds the scrollbar's width to the content's left edge on it, as Windows does on
  bit 0x10 of [listbox + 0x2bc]. PADDING is the byte at [listbox + 0x373].

  1. CSWGuiListBox::OrganizeControls (0x1004a82b4; Windows 0x0041B140) lays the rows out when
     they fit, and reads PADDING six times. Five now read 0:

       0x1004a82fd  mov bl, PADDING       pitch and the fit test (no re-measure)   -> mov bl, 0
       0x1004a83de  movzx r13d, PADDING   pitch, also the visible-row divisor      -> xor r13d, r13d
       0x1004a8697  movzx eax, PADDING    fit test (after re-measuring)            -> xor eax, eax
       0x1004a8752  mov bl, PADDING       fit test (after re-measuring)            -> mov bl, 0
       0x1004a895d  movzx eax, PADDING    each visible row's advance               -> xor eax, eax

     The sixth, at 0x1004a8840, sits in a block (0x1004a8838..0x1004a889e, 102 bytes) that
     computed, with p = PADDING:
         leftover = height - p - rows * pitch;  extra = leftover / rows
         width = contentWidth - 2p;  left = p;  first top = p - scrollTop * pitch
     The block now jumps to kmrp_rows_stub below, which computes
         leftover = height - rows * pitch;      extra = leftover / rows
         width = contentWidth - p;   left = LEFTSCROLLBAR ? p : 0;   first top = -scrollTop * pitch
     and jumps back, leaving every register as before except edx (2p before, the left edge
     now), which both paths after the block overwrite before reading (0x1004a88f7, and the
     calls in the loop). The new left edge needs a test and a conditional move, which do not
     fit in the block, hence the stub (Windows moved the same code into its .kgs section).

  2. 0x1004a936e (Windows 0x0041A2D0) lays out the one row of a list whose content is taller
     than the box: every description long enough to scroll. It has its own copy of the
     arithmetic (0x1004a937a..0x1004a93a5, 43 bytes): left = p, width = contentWidth - 2p, and
     p added to the row's top on both scroll branches (sub ecx, r9d at 0x1004a93f6, add edx,
     r9d at 0x1004a9421). It now jumps to kmrp_scroll_stub, which writes the same left edge and
     width as the stub above, and clears r9d, so both branches start the text at the top, as
     Windows' stub does by clearing edi. ecx (2p before) is reloaded at 0x1004a93a5.

  The other functions that read PADDING (HandleInputEvent, Draw, HandleLMouseDown,
  HandleMouseCapturedMovement, and the 0x100-flag layout 0x1004a94f8) only test whether a row
  fits; Windows v11 leaves their equivalents alone too. Clicks are unaffected: each row is a
  control with its own rect. The K2 fix (widescreen patch, 0x1004a8927, 0x1004a8939) sits
  between these sites and is not touched.
*/
#include "sites.h"

#include <cstring>
#include <iterator>

// The stubs. Each ends in an absolute jump back into the game (jmp *resume(%rip)), so it works
// wherever the module is loaded; nothing in them is relative to the game's code.
__asm__(
    ".text\n"
    ".p2align 4\n"
    ".globl _kmrp_rows_stub\n"
    "_kmrp_rows_stub:\n"
    "    movl    0x344(%r12), %r14d\n"      // height
    "    movswl  0x378(%r12), %edi\n"       // visible rows
    "    movl    %edi, %eax\n"
    "    movl    -0x2c(%rbp), %r8d\n"       // pitch
    "    imull   %r8d, %eax\n"
    "    subl    %eax, %r14d\n"             // leftover
    "    movl    %r14d, %eax\n"
    "    cltd\n"
    "    idivl   %edi\n"                    // extra per row
    "    movzbl  0x373(%r12), %r15d\n"      // PADDING
    "    movl    0x340(%r12), %ecx\n"       // content width
    "    movl    0x368(%r12), %ebx\n"       // row height
    "    subl    %r15d, %ecx\n"             // width - PADDING
    "    xorl    %edx, %edx\n"
    "    testb   $0x10, 0x370(%r12)\n"      // LEFTSCROLLBAR
    "    cmovnel %r15d, %edx\n"
    "    movl    %edx, -0x40(%rbp)\n"       // left
    "    movl    %r13d, -0x3c(%rbp)\n"
    "    movl    %ecx, -0x38(%rbp)\n"       // width
    "    movl    %ebx, -0x34(%rbp)\n"       // height
    "    movswl  0x37c(%r12), %esi\n"       // scroll top
    "    movl    %esi, %ecx\n"
    "    imull   %r8d, %ecx\n"
    "    movl    %ecx, %r15d\n"
    "    negl    %r15d\n"                   // first top
    "    jmpq    *_kmrp_rows_resume(%rip)\n"
    "_kmrp_rows_resume:\n"
    "    .quad   0x1004a889e\n"
    ".globl _kmrp_rows_stub_end\n"
    "_kmrp_rows_stub_end:\n"
    ".p2align 4\n"
    ".globl _kmrp_scroll_stub\n"
    "_kmrp_scroll_stub:\n"
    "    movzbl  0x373(%rbx), %r9d\n"       // PADDING
    "    movl    0x340(%rbx), %esi\n"       // content width
    "    movl    0x368(%rbx), %eax\n"       // row height
    "    subl    %r9d, %esi\n"              // width - PADDING
    "    xorl    %ecx, %ecx\n"
    "    testb   $0x10, 0x370(%rbx)\n"      // LEFTSCROLLBAR
    "    cmovnel %r9d, %ecx\n"
    "    movl    %ecx, -0x18(%rbp)\n"       // left
    "    movl    $0, -0x14(%rbp)\n"         // top
    "    movl    %esi, -0x10(%rbp)\n"       // width
    "    movl    %eax, -0xc(%rbp)\n"        // height
    "    xorl    %r9d, %r9d\n"              // no PADDING in the top on either scroll branch
    "    jmpq    *_kmrp_scroll_resume(%rip)\n"
    "_kmrp_scroll_resume:\n"
    "    .quad   0x1004a93a5\n"
    ".globl _kmrp_scroll_stub_end\n"
    "_kmrp_scroll_stub_end:\n");

extern "C" const uint8_t kmrp_rows_stub[], kmrp_rows_stub_end[];
extern "C" const uint8_t kmrp_scroll_stub[], kmrp_scroll_stub_end[];

namespace kmrp {
namespace {

// Plain arrays, not std::vectors: see kmrp_layout.cpp on C++ globals.
const uint8_t kVanillaRowsBlock[] = {
    0x45, 0x8b, 0xb4, 0x24, 0x44, 0x03, 0x00, 0x00, 0x45, 0x0f, 0xb6, 0xbc, 0x24, 0x73, 0x03, 0x00,
    0x00, 0x45, 0x29, 0xfe, 0x41, 0x0f, 0xbf, 0xbc, 0x24, 0x78, 0x03, 0x00, 0x00, 0x89, 0xf8, 0x44,
    0x8b, 0x45, 0xd4, 0x41, 0x0f, 0xaf, 0xc0, 0x41, 0x29, 0xc6, 0x44, 0x89, 0xf0, 0x99, 0xf7, 0xff,
    0x43, 0x8d, 0x14, 0x3f, 0x41, 0x8b, 0x8c, 0x24, 0x40, 0x03, 0x00, 0x00, 0x41, 0x8b, 0x9c, 0x24,
    0x68, 0x03, 0x00, 0x00, 0x29, 0xd1, 0x44, 0x89, 0x7d, 0xc0, 0x44, 0x89, 0x6d, 0xc4, 0x89, 0x4d,
    0xc8, 0x89, 0x5d, 0xcc, 0x41, 0x0f, 0xbf, 0xb4, 0x24, 0x7c, 0x03, 0x00, 0x00, 0x89, 0xf1, 0x41,
    0x0f, 0xaf, 0xc8, 0x41, 0x29, 0xcf,
};

const uint8_t kVanillaScrollBlock[] = {
    0x44, 0x0f, 0xb6, 0x8b, 0x73, 0x03, 0x00, 0x00, 0x43, 0x8d, 0x0c, 0x09, 0x8b, 0xb3, 0x40, 0x03,
    0x00, 0x00, 0x8b, 0x83, 0x68, 0x03, 0x00, 0x00, 0x29, 0xce, 0x44, 0x89, 0x4d, 0xe8, 0xc7, 0x45,
    0xec, 0x00, 0x00, 0x00, 0x00, 0x89, 0x75, 0xf0, 0x89, 0x45, 0xf4,
};

std::vector<uint8_t> FromArray(const uint8_t* begin, const uint8_t* end) { return {begin, end}; }

// jmp *0(%rip) and the target, then int3 up to the block's length (never reached).
std::vector<uint8_t> JumpTo(const uint8_t* target, size_t length) {
    std::vector<uint8_t> out = {0xff, 0x25, 0x00, 0x00, 0x00, 0x00};
    const uint64_t address = reinterpret_cast<uintptr_t>(target);
    out.resize(14);
    memcpy(out.data() + 6, &address, 8);
    out.resize(length, 0xcc);
    return out;
}

}  // namespace

void AddListboxPadding(std::vector<Group>& groups) {
    const std::vector<uint8_t> readBl = Bytes({0x41, 0x8a, 0x9c, 0x24, 0x73, 0x03, 0x00, 0x00});
    const std::vector<uint8_t> zeroBl = Bytes({0xb3, 0x00, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90});
    const std::vector<uint8_t> readEax = Bytes({0x41, 0x0f, 0xb6, 0x84, 0x24, 0x73, 0x03, 0x00, 0x00});
    const std::vector<uint8_t> zeroEax = Bytes({0x31, 0xc0, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90});
    groups.push_back({"list-box padding", {
        {0x1004a82fd, readBl, zeroBl},
        {0x1004a83de, Bytes({0x45, 0x0f, 0xb6, 0xac, 0x24, 0x73, 0x03, 0x00, 0x00}),
                      Bytes({0x45, 0x31, 0xed, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90})},
        {0x1004a8697, readEax, zeroEax},
        {0x1004a8752, readBl, zeroBl},
        {0x1004a8838, FromArray(std::begin(kVanillaRowsBlock), std::end(kVanillaRowsBlock)),
                      JumpTo(kmrp_rows_stub, sizeof kVanillaRowsBlock)},
        {0x1004a895d, readEax, zeroEax},
        {0x1004a937a, FromArray(std::begin(kVanillaScrollBlock), std::end(kVanillaScrollBlock)),
                      JumpTo(kmrp_scroll_stub, sizeof kVanillaScrollBlock)},
    }});
}

}  // namespace kmrp
