/*
  The area map (Windows: ResolutionPatch.Apply's map fields, MarkerSizeSites, MarkerOffsetSites,
  and the .kui coordinate wrappers; reverse-engineering/map-scaling.md, area-map-surface.md,
  map-markers.md)
  ----------------------------------------------------------------------------------------------
  Vanilla draws the map picture on a 512x256 canvas, places markers in a 440x256 space, and
  crops the canvas to that space with LBL_Map. KMRP's map.gui files make LBL_Map half the
  screen, the interior of the map's frame art, and Windows sizes everything behind it to match:

    marker overlay  W // 2 x H // 2          canvas  round(overlayW * 512 / 440) x H // 2
    centring        W x H                     (the widescreen patch writes -W, -H at the map's
                                               Draw and HandleMouseInput with UseGuiFileLayouts)

  and rescales every marker position from the 440x256 space to the overlay, and scales the
  markers by min(s, 127/16) (the centring offsets are signed bytes). On the Mac:

  1. The map screen's constructor (0x1002b3930) sizes the canvas image from {0, 0, 512, 256} at
     0x100571390 and the marker overlay from {0, 0, 440, 256} at 0x1005713a0 (__TEXT,__const),
     each read there only. Their width and height are written. The HUD minimap does not build
     this screen, so unlike Windows (0x0062B39B) it needs no guard against the new sizes.

  2. CSWGuiMapHider::Draw converts world positions to the 440x256 space at three calls:
       0x1002b4fca  WorldToMapCoords (0x1004400d2)      map notes and world objects
       0x1002b541b  GetPlayerMapCoords (0x100440300)    party members
       0x1002b54c2  GetPlayerMapCoords                  the player's arrow
     (the minimap calls GetPlayerMapCoords at 0x10023790c, untouched). Each call now goes to a
     stub below, through a thunk on a page within reach of a 5-byte call. The stub calls the
     original, and if it succeeded rescales the result as Windows' wrappers do:
       x = (x * overlayW + 220) / 440,  y = (y * overlayH + 128) / 256   (integer division)
     Draw places the note controls that clicks test from these positions, so clicks follow.

  3. The markers, all in Draw (Windows' sizes in brackets):
       note, not selected   size 14 at 0x1002b500a, centring -7 at 0x1002b4ff2, 0x1002b5001
       note, selected       size 20 at 0x1002b52ca, centring -10 at 0x1002b52b2, 0x1002b52c1
       party member         size 16 at 0x1002b544e, centring -8 at 0x1002b5436, 0x1002b5445
       player arrow         size 32 at 0x1002b54ed, and the 32x32 viewport it is drawn into
                            (0x1002b550d, 0x1002b5512), centring -16 at 0x1002b54d5, 0x1002b54e4
     and the two controls the overlay object's constructor (0x1002b60c4) builds:
       mm_barrow      {0, 0, 32, 32} at 0x1005713c0, read there only: width and height written
       lbl_mapcircle  {0, 0, 16, 16} at 0x1005708a0, also read by the HUD (0x100233e3c), so the
                      map's read (movaps at 0x1002b626e) is pointed at a private copy instead
     Windows has one site for the arrow's 32; the Mac keeps three copies, written together.

  The fog grid already steps by the overlay's live size (the widescreen patch's hooks at
  0x1002b4ce9, 0x1002b4cfc, Windows gold v19). The map-note corrections are kmrp-map-notes.
*/
#include "sites.h"

#include <cmath>
#include <cstring>

extern "C" {
int32_t kmrp_overlay_width = 440;   // set by AddAreaMap; read by the stubs
int32_t kmrp_overlay_height = 256;
}

// The stubs are reached by a call from the game, so they return with ret. Caller-saved
// registers are free; the out-pointers are kept across the original call on the stack
// (rsp is 16-byte aligned at the inner call: entry 8, two pushes, sub 8).
__asm__(
    ".text\n"
    ".p2align 4\n"
    ".globl _kmrp_notes_stub\n"
    "_kmrp_notes_stub:\n"                          // WorldToMapCoords(map, xy, z, &x, &y)
    "    pushq   %rsi\n"                           // &x
    "    pushq   %rdx\n"                           // &y
    "    subq    $8, %rsp\n"
    "    callq   *_kmrp_world_to_map(%rip)\n"
    "    addq    $8, %rsp\n"
    "    popq    %r9\n"                            // &y
    "    popq    %r10\n"                           // &x
    "    jmp     _kmrp_rescale\n"
    ".p2align 4\n"
    ".globl _kmrp_party_stub\n"
    "_kmrp_party_stub:\n"                          // GetPlayerMapCoords(map, index, &x, &y)
    "    pushq   %rdx\n"                           // &x
    "    pushq   %rcx\n"                           // &y
    "    subq    $8, %rsp\n"
    "    callq   *_kmrp_player_to_map(%rip)\n"
    "    addq    $8, %rsp\n"
    "    popq    %r9\n"                            // &y
    "    popq    %r10\n"                           // &x
    "_kmrp_rescale:\n"
    "    testl   %eax, %eax\n"
    "    je      1f\n"                             // off the map: untouched, as on Windows
    "    movl    %eax, %r8d\n"
    "    movl    (%r10), %eax\n"
    "    imull   _kmrp_overlay_width(%rip), %eax\n"
    "    addl    $220, %eax\n"
    "    cltd\n"
    "    movl    $440, %ecx\n"
    "    idivl   %ecx\n"
    "    movl    %eax, (%r10)\n"
    "    movl    (%r9), %eax\n"
    "    imull   _kmrp_overlay_height(%rip), %eax\n"
    "    addl    $128, %eax\n"
    "    cltd\n"
    "    movl    $256, %ecx\n"
    "    idivl   %ecx\n"
    "    movl    %eax, (%r9)\n"
    "    movl    %r8d, %eax\n"
    "1:  retq\n"
    "_kmrp_world_to_map:\n"
    "    .quad   0x1004400d2\n"
    "_kmrp_player_to_map:\n"
    "    .quad   0x100440300\n"
    ".globl _kmrp_map_stubs_end\n"
    "_kmrp_map_stubs_end:\n");

extern "C" const uint8_t kmrp_notes_stub[], kmrp_party_stub[], kmrp_popup_stub[];

namespace kmrp {
namespace {

// ResolutionPatch.MarkerScaleForHeight: the height rule, capped so the largest centring
// offset (the arrow's -16) still fits a signed byte.
float MarkerScale(int height) {
    float scale = static_cast<float>(height) / 720.0f;
    if (scale < 1.0f) scale = 1.0f;
    const float cap = 127.0f / 16.0f;
    return scale > cap ? cap : scale;
}

int32_t Size(int vanilla, float scale) {  // (int)Math.Round(vanilla * scale), at least 1
    const int32_t v = static_cast<int32_t>(std::nearbyint(static_cast<double>(static_cast<float>(vanilla) * scale)));
    return v < 1 ? 1 : v;
}

std::vector<uint8_t> Offset(int vanilla, float scale) {  // -(int)Math.Round(-vanilla * scale), at most -1
    int32_t v = -static_cast<int32_t>(std::nearbyint(static_cast<double>(static_cast<float>(-vanilla) * scale)));
    if (v > -1) v = -1;
    return {static_cast<uint8_t>(static_cast<int8_t>(v))};
}

std::vector<uint8_t> Byte(int8_t v) { return {static_cast<uint8_t>(v)}; }

std::vector<uint8_t> CallTo(uintptr_t site, uintptr_t target) {
    const int32_t rel = static_cast<int32_t>(static_cast<int64_t>(target) - static_cast<int64_t>(site + 5));
    return Join({Bytes({0xe8}), Int32(rel)});
}

std::vector<uint8_t> Thunk(const uint8_t* target) {  // jmp *0(%rip); .quad target; 2 bytes padding
    std::vector<uint8_t> out = {0xff, 0x25, 0x00, 0x00, 0x00, 0x00};
    const uint64_t address = reinterpret_cast<uintptr_t>(target);
    out.resize(14);
    memcpy(out.data() + 6, &address, 8);
    out.resize(16, 0xcc);
    return out;
}

// The near page's layout: two thunks, then the map's copy of lbl_mapcircle's rect, then the
// message popup's thunk (popup_fit.cpp).
const size_t kNotesThunk = 0, kPartyThunk = 16, kCircleRect = 32;
static_assert(kCircleRect + 16 == kPopupThunk, "the popup's thunk follows the rect");

}  // namespace

std::vector<uint8_t> AreaMapPage(int height) {
    const int32_t circle = Size(16, MarkerScale(height));
    return Join({Thunk(kmrp_notes_stub), Thunk(kmrp_party_stub),
                 Int32(0), Int32(0), Int32(circle), Int32(circle), Thunk(kmrp_popup_stub)});
}

void AddAreaMap(std::vector<Group>& groups, int width, int height, uintptr_t nearPage) {
    const int32_t overlayWidth = width / 2, overlayHeight = height / 2;
    const int32_t canvasWidth = static_cast<int32_t>(std::nearbyint(static_cast<double>(overlayWidth * 512) / 440.0));
    kmrp_overlay_width = overlayWidth;
    kmrp_overlay_height = overlayHeight;
    groups.push_back({"area map canvas and overlay", {
        {0x100571398, Join({Int32(512), Int32(256)}), Join({Int32(canvasWidth), Int32(overlayHeight)})},
        {0x1005713a8, Join({Int32(440), Int32(256)}), Join({Int32(overlayWidth), Int32(overlayHeight)})},
    }});

    const float m = MarkerScale(height);
    const int32_t arrow = Size(32, m);
    groups.push_back({"area map markers", {
        {0x1002b500b, Int32(14), Int32(Size(14, m))},
        {0x1002b4ff4, Byte(-7), Offset(-7, m)},
        {0x1002b5003, Byte(-7), Offset(-7, m)},
        {0x1002b52cb, Int32(20), Int32(Size(20, m))},
        {0x1002b52b4, Byte(-10), Offset(-10, m)},
        {0x1002b52c3, Byte(-10), Offset(-10, m)},
        {0x1002b544f, Int32(16), Int32(Size(16, m))},
        {0x1002b5438, Byte(-8), Offset(-8, m)},
        {0x1002b5447, Byte(-8), Offset(-8, m)},
        {0x1002b54ee, Int32(32), Int32(arrow)},
        {0x1002b550e, Int32(32), Int32(arrow)},
        {0x1002b5513, Int32(32), Int32(arrow)},
        {0x1002b54d7, Byte(-16), Offset(-16, m)},
        {0x1002b54e6, Byte(-16), Offset(-16, m)},
        {0x1005713c8, Join({Int32(32), Int32(32)}), Join({Int32(arrow), Int32(arrow)})},
    }});

    if (!nearPage) return;  // the constructor could not place the page: positions stay vanilla
    const uintptr_t circleSite = 0x1002b626e;  // movaps xmm0, [rip + disp32]
    const int32_t circleDisp = static_cast<int32_t>(
        static_cast<int64_t>(nearPage + kCircleRect) - static_cast<int64_t>(circleSite + 7));
    groups.push_back({"area map positions", {
        {0x1002b4fca, CallTo(0x1002b4fca, 0x1004400d2), CallTo(0x1002b4fca, nearPage + kNotesThunk)},
        {0x1002b541b, CallTo(0x1002b541b, 0x100440300), CallTo(0x1002b541b, nearPage + kPartyThunk)},
        {0x1002b54c2, CallTo(0x1002b54c2, 0x100440300), CallTo(0x1002b54c2, nearPage + kPartyThunk)},
        {circleSite + 3, Int32(0x2ba62b), Int32(circleDisp)},
    }});
}

}  // namespace kmrp
