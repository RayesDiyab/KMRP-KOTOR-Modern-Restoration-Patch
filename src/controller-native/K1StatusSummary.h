#pragma once
// Shared by KMRP's module (kmrp.dll) and the controller patch's (kmrp-controller.dll).
// Until 2026-10-31 this lived in K1ControllerLayout.cpp, which kmrp.dll then compiled whole, with
// the rest of the controller code, for it (issue 82, F1:
// docs/cleanup-1.6/F1-kmrp-without-controller-code.md).
#include <cstdint>

// ---------------------------------------------------------------- status summary
//
// The box that lists what just changed, each line beside its icon, with OK under
// them: "Journal Entry Added", "Credits Lost: 100", "Experience Points (XP)
// Received: 50", "Item(s) Received". Reported broken at 3440x1440 on 2026-09-25
// from three screenshots: text past the box's right edge, OK drawn over the last
// line as a bar, and the XP line showing only "Received: 50".
//
// CSWGuiStatusSummary (constructor 0x006272A0, vtable 0x0074FF68) loads
// statussummary.gui, which High Resolution Menus does not ship, so it is the
// game's own 640x480 file (gui.bif): a 322x332 box, 32x32 icons at x 10, lines at
// x 52 that are 32 tall, OK 100x22. Its layout is code, 0x00625C60, in the same
// pixels: rows from y 10 and 37 apart (0x0062622A); each line 150 wide at first
// and widened 20 at a time (0x006261E8) until the line breaker fits it on one line,
// but never past 440 (0x006261AE, 0x006261F4); the box that width plus 62, centred
// on the screen (0x00626274..0x006262B4); OK 7 above where the next row would
// start and the box 32 below that (0x0062627B, 0x00626282).
//
// That was right for a 16 px font. KMRP draws text at the resolution's scale --
// 32 px a line at 3440x1440 -- so the rows collide, OK lands on the last line, the
// XP line hits the 440 cap and wraps with only its second line in view (the box
// measured 507 px on the screenshot, the formula gives 502), and the breaker's
// measure, which truncates each glyph, stops the widening short of the drawn text.
//
// So the box is laid out again every frame after the engine's own pass: the same
// layout scaled by the lines' font height over 16, each line as wide as the glyphs
// the engine draws for it (the dialogue A's measure, lastReplyLine above), capped
// only by the screen. Only the extents change, and only when they differ.
// Seen in game at 3440x1440 on 2026-09-25 with one row, "Journal Entry Added"
// after Trask's first conversation: box 489x144 on the screen's centre, the line
// inside it, OK centred under it. Two or more rows have not been seen yet.
constexpr std::uintptr_t K1_STATUS_SUMMARY_VTABLE = 0x74FF68;
constexpr unsigned K1_SUMMARY_ICONS = 0x300;   // nine CSWGuiLabels, 0x140 apart
constexpr unsigned K1_SUMMARY_LINES = 0xE40;   // their lines, in the same order
constexpr unsigned K1_SUMMARY_OK = 0x1980;     // CSWGuiButton
constexpr unsigned K1_LABEL_SIZE = 0x140;
constexpr int K1_SUMMARY_ROWS = 9;


// The box laid out again for the drawn text, every frame (each module's GUI frame).
void StatusSummaryFrameK1(void* manager);
// The pad's A beside OK, `ok` its rect: the controller patch's (K1ControllerLayout.cpp);
// KMRP's module has none and answers false (K1CoreFrames.cpp). True when shown.
bool StatusSummaryBadgeK1(void* panel, const int* ok);
