/*
  The dialogue reply list fills the reply panel (K7)
  ----------------------------------------------------------------------------------------------
  The widescreen patch sizes the dialogue letterbox from the screen's height (bar = H/6, KMRP's
  Windows formula; kmrp_engine_fixes.cpp, "Dialogue letterbox sized from the screen height") and
  grows the reply panel under the bottom bar to the bar, but the reply list in it (LB_REPLIES)
  keeps the height its .gui gives it: vanilla's 98 px, so with KMRP's enlarged text the replies
  scrolled while most of the bar stayed empty. The widescreen patch's hook K7 stretched the list
  to the panel until FTD's branch dropped it (2026-09-30, commit range 71ac5fa..074972b); it is
  KMRP's now, so KMRP no longer depends on the base patch keeping it.

  CSWGuiDialogCinematic::SetExtent (0x100244d4a) copies the list's rect (+0x20c8) to a local
  rect at r14, sets its width to the panel's ([rbx + 0x10]) and hands it to the list's SetExtent
  (0x1004a81ae). The two instructions that set the width (0x100244d7d, 7 bytes: mov eax,
  [rbx+0x10]; mov [r14+8], eax) now jump, through the near page's thunk at kRepliesThunk, to
  kmrp_replies_stub, which sets the width the same way and also the height: the panel's height
  less the list's top, never less than the list's own. Nothing after the site reads eax or the
  flags (the next instructions load rsi and call SetExtent). The same instructions K7 used.

  If the base patch hooks the site again, its bytes are no longer vanilla's and this group is
  left alone (kmrp_layout.cpp applies a group only where every site holds its expected bytes).
*/
#include "sites.h"

#include <cstring>

__asm__(
    ".text\n"
    ".p2align 4\n"
    ".globl _kmrp_replies_stub\n"
    "_kmrp_replies_stub:\n"
    "    movl    0x10(%rbx), %eax\n"          // the panel's width, as the site did
    "    movl    %eax, 0x8(%r14)\n"
    "    movl    0x14(%rbx), %eax\n"          // the panel's height
    "    subl    0x4(%r14), %eax\n"           // less the list's top
    "    cmpl    0xc(%r14), %eax\n"
    "    jle     1f\n"                        // never shorter than the list already is
    "    movl    %eax, 0xc(%r14)\n"
    "1:\n"
    "    jmpq    *_kmrp_replies_resume(%rip)\n"
    "_kmrp_replies_resume:\n"
    "    .quad   0x100244d84\n"
    ".globl _kmrp_replies_stub_end\n"
    "_kmrp_replies_stub_end:\n");

extern "C" const uint8_t kmrp_replies_stub[], kmrp_replies_stub_end[];

namespace kmrp {

void AddDialogueReplies(std::vector<Group>& groups, uintptr_t nearPage) {
    if (!nearPage) return;   // the constructor could not place the page: the list stays as it is
    const uintptr_t site = 0x100244d7d;
    const int32_t rel = static_cast<int32_t>(static_cast<int64_t>(nearPage + kRepliesThunk) -
                                             static_cast<int64_t>(site + 5));
    groups.push_back({"dialogue reply list", {
        {site, Bytes({0x8b, 0x43, 0x10, 0x41, 0x89, 0x46, 0x08}),
         Join({Bytes({0xe9}), Int32(rel), Bytes({0x90, 0x90})})},
    }});
}

}  // namespace kmrp
