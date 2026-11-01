using System;
using System.ComponentModel;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Net;
using Microsoft.Win32;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;

// The size rules as the standalone installer applied them, kept to hold the module's against
// (Test-EngineFields). No install runs this: it left src/patcher on 2026-11-01 (approved
// decision 3), with WindowsEnginePatch.cs. Built by build_kmrp.ps1 as kmrp-reference.exe.
namespace Kmrp
{
    internal static class ResolutionPatch
    {
        private static readonly long[] WidthOffsets = { 0x0000AA65, 0x001F0C65 };
        private static readonly long[] HeightOffsets = { 0x0000AA85, 0x001F0C6F };

        // Full-screen Bink playback has its own 640x480 display-mode pair, separate
        // from the normal render-resolution constants above.  The first pair is the
        // width/height comparison in the movie entry path (VA 0x00403D66); the
        // second initializes the temporary movie mode (VA 0x005F5B37).  Leaving
        // either pair at 640x480 makes the engine change display mode around a
        // movie, which is the source of the minimize/focus transition seen with
        // resolution-matched upscaled BIKs.  Both pairs are imm32 operands.
        //
        // A community helper searches for only `00 00 C7 44 24 10` for the second
        // pair.  That sequence occurs hundreds of times and its first match in this
        // executable is not a resolution at all.  These addresses instead come
        // from aligned disassembly of the verified source and are guarded by exact
        // gold-reference values on every application. See reverse-engineering/movies.md.
        // Internal: the KPM edition tags these as KMRP Movies' (KpmEdition.cs).
        // Since 2026-10-20 also the third pair, RestoreResolutionFromMovie's comparison
        // (VA 0x00403EA7 and 0x00403EB3): at 640x480 the game rebuilt its renderer and set
        // the display mode again after every full-screen movie (tools/build_windows_engine.py).
        internal static readonly long[] MovieWidthOffsets = { 0x00003D6C, 0x001F5B3B, 0x00003EAD };
        internal static readonly long[] MovieHeightOffsets = { 0x00003D78, 0x001F5B43, 0x00003EB9 };

        // 0x0028C4E3 (VA 0x0068C4E3) is a THIRD width comparison, deliberately NOT included
        // above. It's the last live branch of the HUD minimap-variant (mipc*.gui) selector:
        // vanilla compares the live screen width against a handful of hardcoded pixel widths
        // to choose which mipc*.gui HUD layout to load (the other two branches are already
        // zeroed/disabled in gold, matching the community "Resolution Unlocker" fix, so they
        // never match). Previously this field was included in WidthOffsets, which made
        // ResolutionPatch overwrite it with resolution.Width every build -- making the
        // comparison "liveWidth == liveWidth", tautologically true, so EVERY resolution ever
        // shipped force-loaded mipc210x7.gui (the one file hand-corrected for 3440x1440)
        // regardless of actual aspect ratio, corrupting minimap/HUD icon layout at every other
        // resolution (confirmed: 1920x1080's journal/cash/item icons and the combat message
        // box both end up overlapping the oversized minimap frame). Leaving this field
        // untouched keeps gold's own baked-in value (3440) permanently, so the comparison is
        // now "liveWidth == 3440": mipc210x7.gui still loads correctly at 3440x1440 (the only
        // resolution it was ever hand-tuned for), while every other resolution now correctly
        // falls through to vanilla's own generic default branch (mipc28x6.gui) instead of the
        // wrong ultra-wide-specific file.

        // Negated screen-width/height reference constants used by two shared widget-geometry
        // recentering helpers (vanilla 0x0040B690 / 0x0040BA20) called from essentially every
        // non-main-menu/non-HUD GUI screen. They compute
        //   newX = originalX - (liveScreenWidth  - DESIGN_WIDTH)  / 2
        //   newY = originalY - (liveScreenHeight - DESIGN_HEIGHT) / 2
        // The gold reference build baked in its own resolution (-3440/-1440) as DESIGN_WIDTH/
        // DESIGN_HEIGHT instead of leaving these resolution-agnostic, so the recentering was a
        // no-op only at exactly 3440x1440 and drifted proportionally to distance from it at any
        // other resolution -- the general PC-screen click-offset bug. Found via
        // generate_gold_delta.py's changed_ranges() surfacing these as previously-undocumented
        // gold-delta chunks, then confirmed by disassembly (tools/build_click_fix_wrapper.py).
        private static readonly long[] NegativeWidthOffsets = { 0x0000B6C7, 0x0000BA6C };
        private static readonly long[] NegativeHeightOffsets = { 0x0000B6DA, 0x0000BA83 };

        // The .kfs section (tools/build_font_scale_wrapper.py, baked into the gold
        // reference) holds two 32-bit float scale constants at its very start.
        //
        // Text size itself is NOT scaled here any more: doing it at runtime mutated the
        // shared CAurFontInfo metrics on first draw, one frame after the engine had
        // already measured and centred the text with the unscaled values, which visibly
        // shifted the first screen drawn each session. Font sizing now happens in the
        // font atlases' own TXI metrics instead (tools/build_scaled_fonts.py, shipped per
        // resolution in the GUI archives), so the values are correct before anything
        // measures them. Gold therefore ships the font constant at 1.0 and it stays there.
        //
        // Generic list-row heights keep scaling at runtime: that hook rewrites a row's
        // height as the row is constructed, with nothing having measured it beforehand,
        // so it has no such ordering problem. Rows must grow with the text or entries
        // overlap (originally seen on the save/load list), so this constant is rescaled
        // per resolution using the same height-proportional rule as the font TXIs and the
        // HUD geometry. Clamped at 1.0 so short screens keep vanilla row heights.
        // Text (and therefore row) size grows linearly with screen height: 1.25x at
        // 1080p, 1.75x at 1440p, 2.75x at 2160p. The -0.25 offset holds the scaling a
        // little under a pure height ratio, which read as too large in play-testing.
        // Clamped at 1.0, which takes effect below 900px, so short screens keep vanilla
        // sizing rather than shrinking below it.
        // Inventory item rows size themselves from THREE hardcoded 56s, all
        // independent of resolution and of the font -- which is why enlarged text
        // left the rows and their icons stranded at vanilla size, and why nothing
        // in inventory.gui could move them (PROTOITEM's own 100px EXTENT.HEIGHT is
        // read into the control and then never used for the row).
        //
        //   0x002B527F  mov edi,56              icon box 56x56, text left offset,
        //                                       and text width = row width - 56
        //   0x002B4FA9  mov [esp+0x1C],56       row height -> CSWGuiInGameItemEntry::SetRect
        //   0x002B55E3  mov [esp+0x18],56       row height, second layout path
        //
        // The height ones feed row+0x10, which the listbox harvests as
        // `[listbox+0x2B4] = max(item->height)` and then uses as every row's rect
        // height; row pitch is that plus the GUI's PADDING byte. Patching only the
        // icon constant therefore grows the icons INTO the row below -- all three
        // must move together. Traced and confirmed live under x32dbg.
        //
        // Scaled by the same height rule as the fonts so rows grow with the text.
        // Unlike RowScaleOffset these are reached only by the inventory item row,
        // so they cannot disturb the save/load, journal or resolution lists.
        // Three screens build their list rows from the same class shape, each with
        // its own hardcoded size: the first constant is the row's square icon box
        // (and therefore the text's left offset and width), the rest are the row
        // HEIGHT handed to SetRect. Found by scanning for the shape rather than the
        // value -- `mov <reg>,imm ; cmp <reg2>,<reg> ; jle` locates the icon site in
        // each row class, and `mov [esp+X],imm` right before `call [<reg>+4]`
        // locates the height sites.
        //
        //   inventory  56  0x002B527F icon   0x002B4FA9 + 0x002B55E3 height
        //   abilities  42  0x002AB8EF icon   0x002ACB20 height
        //   store      56  0x002C265F icon   0x002C2A23 height
        //
        // All are imm32, so they take any scale. Each group's icon and height MUST
        // move together: patching the icon alone grows it into the row below, which
        // is exactly what the first inventory attempt did (confirmed in game).
        // Details and the full call chain in
        // reverse-engineering/inventory-item-rows.md.
        // The item STACK-COUNT label, built inside the inventory row's SetRect
        // (0x006B5270) and present in no .gui file. It is bottom-right-aligned
        // INSIDE the icon box: height 19, width 21 for one or two digits and 42 for
        // three or more (`and ecx,21` / `add ecx,21` after a `strlen <= 2` test),
        // top offset 37 -- and 37 + 19 = 56, the vanilla icon size. Scaling the icon
        // without these left a 21x19 label in the corner of a box twice the size,
        // and an enlarged font needs 22px for the widest two-digit pair, so the
        // digits vanished entirely.
        //
        // The width and top operands were originally imm8 (sign-extended), which
        // capped them at 127 -- at 7680x4320 the icon is 336px while the top offset
        // would have stopped at 127, floating the label partway up the icon instead
        // of sitting in its corner. tools/build_stack_count_fix.py relocates that
        // arithmetic into a `.ksc` stub with imm32 operands (gold v10), so all four
        // scale without limit and no clamp is needed.
        // {file offset, operand size in bytes, vanilla value}
        private static readonly int[][] StackCountSites =
        {
            new[] { 0x002B5332, 4, 19 },   // mov [esp+2C], 19  label height (in place)
            new[] { 0x003DF003, 4, 21 },   // and ecx, 21       width, 1-2 digits (.ksc)
            new[] { 0x003DF009, 4, 21 },   // add ecx, 21       width, 3+ digits (.ksc)
            new[] { 0x003DF020, 4, 37 },   // add eax, 37       top offset       (.ksc)
        };

        // {expected vanilla value, value to scale from, offsets...}. The two differ
        // only for the feat/power chain rows, which read too small at the vanilla
        // 40 once everything around them grew -- 50 was chosen by eye in game
        // (100px at 3440x1440) and is a deliberate design choice, not a measurement.
        // The shared message popup (confirm.gui and every tutorial hint) sizes
        // itself in code, not from its .gui, so its geometry has to scale with the
        // font the same way the .gui layout does -- see scale_message_popup.py,
        // whose TUNED table is the matching half of this. Gold bakes the values
        // play-tested at 3440x1440, i.e. font scale 2.0; the second column is the
        // scale-1.0 base, so at 1440p this reproduces gold exactly.
        //
        // Each cap has TWO sites. Patching one leaves the other clamping -- the
        // same "there is always a second copy" pattern as gold v11's three row
        // pitch sites and v12's two rect builders.
        // Area map marker geometry. The overlay markers are drawn on grows with the
        // screen (canvasWidth x 440/512 by canvasHeight), but these rectangles were
        // built from vanilla immediates, so relative to the map they shrank by
        // exactly the factor the overlay grew -- 20 px on a 440-wide overlay is 4.5%
        // of the map, the same 20 px on 1478 is 1.4%.
        //
        // The factor is ScaleForHeight -- max(1, height/720), the same rule the fonts
        // and list rows use -- giving a 2x marker at 1440p. Full proportional scaling
        // against the overlay (screenWidth/1024, 3.36x at 3440x1440) was tried first
        // and play-tested too large. Gold bakes the 3440x1440 values; the second
        // column is vanilla, i.e. factor 1.0.
        //
        // There are TWO map-note paths: 0x0069470B branches on whether the note is
        // the selected one, and each side builds its own rectangle. Scaling only the
        // selected side leaves every other note at vanilla size, which is what the
        // first attempt shipped.
        //
        // Every marker's centring offset is -size/2 and MUST move with its size, or
        // the icon drifts off the point it marks.
        private static readonly int[][] MarkerSizeSites =
        {
            //     gold, vanilla, imm32 offsets...
            new[] {   40,   20, 0x00294720 },   // map note size, selected
            new[] {   28,   14, 0x00294763 },   // map note size, UNSELECTED
            new[] {   32,   16, 0x00294A13 },   // party marker size
            new[] {   64,   32, 0x00294AC4 },   // player arrow size
            new[] {   64,   32, 0x0029405B },   // mm_barrow control extent
            new[] {   32,   16, 0x002940DC },   // lbl_mapcircle control extent
        };

        // Same, for the `add r32, imm8` centring offsets. These are signed bytes,
        // so the factor is clamped at 127/16 -- see MarkerScaleForWidth.
        private static readonly int[][] MarkerOffsetSites =
        {
            new[] {  -20,  -10, 0x0029471A, 0x00294726 },   // note, selected
            new[] {  -14,   -7, 0x00294777, 0x0029477A },   // note, UNSELECTED
            new[] {  -16,   -8, 0x00294A53, 0x00294A56 },   // party
            new[] {  -32,  -16, 0x00294AD0, 0x00294AD4 },   // arrow
        };

        // The largest offset is the arrow's size/2, and it has to fit in a signed
        // byte, so the scale cannot exceed 127/16. The scale follows the HEIGHT, so
        // that binds only above ~5715 px tall: of the 48 shipped resolutions
        // 15360x8640 alone gets under-scaled markers (a third short), still
        // correctly centred. (This said 8192x4608 too, reasoning from width; read
        // back from its output, 8192x4608 is unclamped.) Lifting it needs
        // the adds widened to imm32 in a stub, as the stack-count label needed in
        // gold v10.
        private const float MarkerMaxScale = 127.0f / 16.0f;

        internal static float MarkerScaleForHeight(int height)
        {
            float scale = ScaleForHeight(height);
            return scale > MarkerMaxScale ? MarkerMaxScale : scale;
        }

        private static readonly int[][] PopupSizeGroups =
        {
            //     gold, base@1.0, offsets...
            new[] {  900,  450, 0x002256E3, 0x00225759 },   // auto-fit height stop
            // The width cap is what fixes clipped message text: the auto-fit loop
            // widens the popup 40 units at a time to fit its message, but only
            // while the panel is narrower than this. Authored 440 for 640x480, so
            // at any HD size the panel already exceeds it and the loop never runs.
            new[] { 1600,  800, 0x002256DC, 0x002256F6 },   // auto-fit width cap
            // The icon rect and the inset the message text is pushed down by. They
            // must move together or the text runs under the icon -- and the rect
            // must match the tut_*.tga size GameArtGenerator makes (64s),
            // because the engine draws GUI textures one texel per pixel: a smaller
            // texture TILES, a larger one is CROPPED.
            new[] {  128,   64, 0x00226F95, 0x0022540D },   // icon rect, message inset
        };

        private static readonly int[][] RowSizeGroups =
        {
            new[] { 56, 56, 0x002B527F, 0x002B4FA9, 0x002B55E3 },   // inventory
            // The Skills tab's rows from 50, as the Feats and Powers tabs' chain rows
            // below: one list shows all three tabs, and rows of two heights left one
            // tab's gaps loose at every height (2026-09-30).
            new[] { 42, 50, 0x002AB8EF, 0x002ACB20 },               // abilities: skills tab (1.19x)
            new[] { 56, 56, 0x002C265F, 0x002C2A23 },               // store / merchant
            // The Abilities screen's Powers and Feats tabs are NOT listbox rows and
            // share nothing with the three above -- each row is a feat/power
            // progression chain, built at 0x006CD8CD / 0x006CDB6D as a hardcoded
            // 242x40 rect and laid out by 0x006CCE30 (the chain row's SetRect,
            // which also draws the lbl_skarr arrows and the lbl_indent backing).
            // Only the HEIGHT is scaled: it drives the icon squares inside the row,
            // and doubling it alone was confirmed in game. The width (242, at
            // 0x002CD8D1/0x002CDB71) and the arrow square (32, at 0x002CCE5F) are
            // deliberately left alone -- untested, and the listbox appears to
            // stretch the row's width itself.
            new[] { 40, 50, 0x002CD8D9, 0x002CDB79 },               // abilities: powers/feats chain rows (1.25x)
        };

        // The Options screens' check boxes (Feedback's list, Auto-pause, Gameplay, Graphics,
        // Advanced Graphics, Mouse, Advanced Sound), CSWGuiOptionsCheckbox::SetExtent at
        // 0x006DE000: the circle's four state images in a fixed 25x25 square at the control's
        // left, 2 px below its middle, and the label 30 px in, at every resolution -- a 25 px
        // circle in toggles over 100 px tall at 1440p and up, where vanilla drew it in 43- and
        // 60-px ones. Scaled like the rows, 25s, 2s and 30s, as the Mac's layout patch does
        // (macos/patches/kmrp-layout/resolution_sizes.cpp, AddCheckboxes; the Mac replaces the
        // whole function). Found on the Mac by reading the code, 2026-09-30
        // (docs/windows-changes-from-macos.md, item 13).
        //
        //   0x006DE011  ba 19000000     mov edx, 25            the square, imm32
        //   0x006DE02E  8d 4c 01 02     lea ecx, [ecx+eax+2]   below the middle, disp8
        //   0x006DE08E  83 e9 1e        sub ecx, 30            the label's width
        //   0x006DE091  83 c0 1e        add eax, 30            the label's left
        //
        // The square takes any scale and the drop fits its signed byte up to s = 63, but the
        // label's two immediates are signed bytes too, and 30s passes 127 above 3048 px tall
        // (180 at 7680x4320). Rather than cap the scale, as the map markers do, the two are
        // replaced by a jump into the 15 bytes of NOP padding after the function's `ret 4`
        // (0x006DE0D1..0x006DE0DF, which nothing reaches), where the same two operations
        // take imm32 operands and jump back to 0x006DE094. Flags are not read before the
        // next write. Written at every resolution, 720 and below too, where 30 is vanilla's.
        private const long CheckboxSquareOffset = 0x002DE012;
        private const long CheckboxDropOffset = 0x002DE031;
        private const long CheckboxLabelOffset = 0x002DE08E;
        private const long CheckboxCaveOffset = 0x002DE0D1;
        private static readonly byte[] CheckboxLabelVanilla = { 0x83, 0xE9, 0x1E, 0x83, 0xC0, 0x1E };
        // jmp 0x006DE0D1 (rel32 0x3E from 0x006DE093), then a NOP never reached.
        private static readonly byte[] CheckboxLabelJump = { 0xE9, 0x3E, 0x00, 0x00, 0x00, 0x90 };
        private const int CheckboxCaveLength = 13;   // sub ecx, imm32 (6); add eax, imm32 (5); jmp short (2)

        // The message popup's widening step, in CSWGuiMessageBox::FixMessageLabel
        // (0x006253A0). A box whose text does not fit grows in a loop: each pass adds 40
        // to the width (and takes 20 off the left) while the width is under its cap, and
        // one line of the font to the height. The caps and the line follow the screen
        // (PopupSizeGroups; the font is baked for the height); the 40 never did, so the
        // same text made a wide box at a low resolution and a tall, narrow one at a high
        // one (seen on the Mac at 3840x2160; docs/windows-changes-from-macos.md, item 24).
        //
        //   0x006256FC  83 44 24 38 28   add [esp+38], 40
        //   0x00625701  8b 44 24 20      mov eax, [esp+20]
        //   0x00625705  83 c1 28         add ecx, 40
        //   0x00625708  89 4c 24 28      mov [esp+28], ecx
        //   0x0062570C  83 e8 14         sub eax, 20
        //   0x0062570F  8d 4c 24 30      lea ecx, [esp+30]
        //   0x00625713  89 44 24 20      mov [esp+20], eax
        //
        // The three numbers are signed bytes and cannot hold 120. The same 27 bytes with
        // one 32-bit step, 40s (eax is loaded anew at 0x00625717 and no flag is read):
        //   mov eax, step ; add [esp+38], eax ; add ecx, eax ; mov [esp+28], ecx ;
        //   sar eax, 1 ; sub [esp+20], eax ; lea ecx, [esp+30] ; nop ; nop
        private const long PopupStepOffset = 0x002256FC;
        private static readonly byte[] PopupStepVanilla =
        {
            0x83, 0x44, 0x24, 0x38, 0x28, 0x8B, 0x44, 0x24, 0x20, 0x83, 0xC1, 0x28, 0x89, 0x4C,
            0x24, 0x28, 0x83, 0xE8, 0x14, 0x8D, 0x4C, 0x24, 0x30, 0x89, 0x44, 0x24, 0x20,
        };
        private static readonly byte[] PopupStepCode =
        {
            0xB8, 0x28, 0x00, 0x00, 0x00, 0x01, 0x44, 0x24, 0x38, 0x01, 0xC1, 0x89, 0x4C, 0x24,
            0x28, 0xD1, 0xF8, 0x29, 0x44, 0x24, 0x20, 0x8D, 0x4C, 0x24, 0x30, 0x90, 0x90,
        };

        // The stack-count label of a STORE row, in CSWGuiStoreItemEntry::SetExtent
        // (0x006C2650). The inventory's is 21s wide (42s for three digits or more) and 19s
        // tall in the icon's lower right corner (StackCountSites). The store's kept the
        // game's own: 21 or 42 wide whatever the screen, as tall as the icon, at the row's
        // top (docs/windows-changes-from-macos.md, item 26; on the Mac the count stood in
        // the icon's upper right corner, half outside the frame).
        //
        //   0x006C2704  33 c9            xor ecx, ecx
        //   0x006C2706  83 f8 02         cmp eax, 2            the count's length
        //   0x006C2709  0f 9e c1         setle cl
        //   0x006C270C  8b d7            mov edx, edi          edi: the icon's size
        //   0x006C270E  89 7c 24 2c      mov [esp+2c], edi     height
        //   0x006C2712  49               dec ecx
        //   0x006C2713  83 e1 15         and ecx, 21
        //   0x006C2716  83 c1 15         add ecx, 21
        //   0x006C2719  8b c1            mov eax, ecx
        //   0x006C271B  2b d0            sub edx, eax
        //   0x006C271D  89 44 24 28      mov [esp+28], eax     width
        //   0x006C2721  8b 44 24 20      mov eax, [esp+20]
        //   0x006C2725  03 c2            add eax, edx
        //   0x006C2727  8d 8e 34030000   lea ecx, [esi+334]
        //   0x006C272D  8d 54 24 20      lea edx, [esp+20]
        //   0x006C2731  89 44 24 20      mov [esp+20], eax     left
        //
        // The same 49 bytes by the inventory's rule, with 32-bit operands (eax is loaded
        // anew at 0x006C2735; ecx and edx leave as the game leaves them):
        //   cmp eax, 2 ; mov ecx, 21s ; jle +2 ; add ecx, ecx ; mov [esp+28], ecx ;
        //   add [esp+20], edi ; sub [esp+20], ecx ; mov eax, 19s ; mov [esp+2c], eax ;
        //   sub eax, edi ; sub [esp+24], eax ; lea ecx, [esi+334] ; lea edx, [esp+20]
        // so the top is the row's top and the icon less the label's height: the game's 37
        // at its own size (56 - 19). Built, not yet seen in the game.
        private const long StoreCountOffset = 0x002C2704;
        private static readonly byte[] StoreCountVanilla =
        {
            0x33, 0xC9, 0x83, 0xF8, 0x02, 0x0F, 0x9E, 0xC1, 0x8B, 0xD7, 0x89, 0x7C, 0x24, 0x2C,
            0x49, 0x83, 0xE1, 0x15, 0x83, 0xC1, 0x15, 0x8B, 0xC1, 0x2B, 0xD0, 0x89, 0x44, 0x24,
            0x28, 0x8B, 0x44, 0x24, 0x20, 0x03, 0xC2, 0x8D, 0x8E, 0x34, 0x03, 0x00, 0x00, 0x8D,
            0x54, 0x24, 0x20, 0x89, 0x44, 0x24, 0x20,
        };
        private static readonly byte[] StoreCountCode =
        {
            0x83, 0xF8, 0x02, 0xB9, 0x15, 0x00, 0x00, 0x00, 0x7E, 0x02, 0x03, 0xC9, 0x89, 0x4C,
            0x24, 0x28, 0x01, 0x7C, 0x24, 0x20, 0x29, 0x4C, 0x24, 0x20, 0xB8, 0x13, 0x00, 0x00,
            0x00, 0x89, 0x44, 0x24, 0x2C, 0x2B, 0xC7, 0x29, 0x44, 0x24, 0x24, 0x8D, 0x8E, 0x34,
            0x03, 0x00, 0x00, 0x8D, 0x54, 0x24, 0x20,
        };

        private const long RowScaleOffset = 0x003DD004;
        private const float GoldRowScale = 1.75f;
        private const float ScaleHeightDivisor = 720.0f;
        // Text sizing is height/720 with no offset: 1.00x at 720p, 1.50x at
        // 1080p, 2.00x at 1440p, 3.00x at 2160p. An earlier -0.25 offset made
        // 1440p and 2160p read as 1.75x/2.75x, which play-tested too small.
        // MUST stay in step with font_scale_for() in
        // tools/prepare_universal_resources.py, which sizes the atlas metrics.
        private const float ScaleOffset = 0.0f;

        internal static float ScaleForHeight(int height)
        {
            float scale = height / ScaleHeightDivisor - ScaleOffset;
            return scale < 1.0f ? 1.0f : scale;
        }

        internal static void Apply(byte[] executable, ResolutionChoice resolution)
        {
            if (executable == null || executable.LongLength != GoldPatch.TargetLength)
                throw new InvalidDataException("The executable image has an unexpected size.");

            foreach (long offset in WidthOffsets)
                ReplaceInt32(executable, offset, 3440, resolution.Width, "screen width");
            foreach (long offset in HeightOffsets)
                ReplaceInt32(executable, offset, 1440, resolution.Height, "screen height");
            foreach (long offset in MovieWidthOffsets)
                ReplaceInt32(executable, offset, 3440, resolution.Width, "movie display-mode width");
            foreach (long offset in MovieHeightOffsets)
                ReplaceInt32(executable, offset, 1440, resolution.Height, "movie display-mode height");
            ReplaceSingle(executable, RowScaleOffset, GoldRowScale, ScaleForHeight(resolution.Height),
                "list-row scale");
            float rowSizeScale = ScaleForHeight(resolution.Height);
            foreach (int[] site in StackCountSites)
                ReplaceInt32(executable, site[0], site[2],
                             (int)Math.Round(site[2] * rowSizeScale), "stack-count label");

            foreach (int[] group in RowSizeGroups)
            {
                int expected = group[0];
                int scaled = (int)Math.Round(group[1] * rowSizeScale);
                for (int i = 2; i < group.Length; i++)
                    ReplaceInt32(executable, group[i], expected, scaled, "list row/icon size");
            }

            foreach (int[] group in PopupSizeGroups)
            {
                int expected = group[0];
                int scaled = (int)Math.Round(group[1] * rowSizeScale);
                for (int i = 2; i < group.Length; i++)
                    ReplaceInt32(executable, group[i], expected, scaled, "message popup size");
            }

            // The Options check boxes (CheckboxSquareOffset and the rest, above).
            int checkboxLabel = (int)Math.Round(30 * rowSizeScale);
            ReplaceInt32(executable, CheckboxSquareOffset, 25, (int)Math.Round(25 * rowSizeScale),
                "check box size");
            ReplaceSByte(executable, CheckboxDropOffset, 2, (int)Math.Round(2 * rowSizeScale),
                "check box offset");
            ReplaceBytes(executable, CheckboxLabelOffset, CheckboxLabelVanilla, CheckboxLabelJump,
                "check box label");
            byte[] cave = new byte[CheckboxCaveLength];
            cave[0] = 0x81;                                  // sub ecx, imm32
            cave[1] = 0xE9;
            Buffer.BlockCopy(BitConverter.GetBytes(checkboxLabel), 0, cave, 2, 4);
            cave[6] = 0x05;                                  // add eax, imm32
            Buffer.BlockCopy(BitConverter.GetBytes(checkboxLabel), 0, cave, 7, 4);
            cave[11] = 0xEB;                                 // jmp short 0x006DE094
            cave[12] = 0xB6;
            byte[] padding = new byte[CheckboxCaveLength];
            for (int i = 0; i < padding.Length; i++)
                padding[i] = 0x90;
            ReplaceBytes(executable, CheckboxCaveOffset, padding, cave, "check box label");

            // The message popup's widening step (PopupStepOffset, above).
            byte[] popupStep = (byte[])PopupStepCode.Clone();
            Buffer.BlockCopy(BitConverter.GetBytes((int)Math.Round(40 * rowSizeScale)), 0, popupStep, 1, 4);
            ReplaceBytes(executable, PopupStepOffset, PopupStepVanilla, popupStep, "message popup step");

            // The store row's stack-count label (StoreCountOffset, above).
            byte[] storeCount = (byte[])StoreCountCode.Clone();
            Buffer.BlockCopy(BitConverter.GetBytes((int)Math.Round(21 * rowSizeScale)), 0, storeCount, 4, 4);
            Buffer.BlockCopy(BitConverter.GetBytes((int)Math.Round(19 * rowSizeScale)), 0, storeCount, 25, 4);
            ReplaceBytes(executable, StoreCountOffset, StoreCountVanilla, storeCount, "store stack-count label");

            float markerScale = MarkerScaleForHeight(resolution.Height);
            foreach (int[] group in MarkerSizeSites)
            {
                int scaled = (int)Math.Round(group[1] * markerScale);
                if (scaled < 1) scaled = 1;
                for (int i = 2; i < group.Length; i++)
                    ReplaceInt32(executable, group[i], group[0], scaled, "map marker size");
            }
            foreach (int[] group in MarkerOffsetSites)
            {
                int scaled = -(int)Math.Round(-group[1] * markerScale);
                if (scaled > -1) scaled = -1;
                for (int i = 2; i < group.Length; i++)
                    ReplaceSByte(executable, group[i], group[0], scaled, "map marker centring");
            }
            foreach (long offset in NegativeWidthOffsets)
                ReplaceInt32(executable, offset, -3440, -resolution.Width, "click-fix width reference");
            foreach (long offset in NegativeHeightOffsets)
                ReplaceInt32(executable, offset, -1440, -resolution.Height, "click-fix height reference");
            ReplaceInt32(executable, 0x002928B3, 2750, resolution.CenteringWidth, "map horizontal centering");
            ReplaceInt32(executable, 0x002928C3, 1400, resolution.CenteringHeight, "map vertical centering");
            ReplaceInt32(executable, 0x0029505C, 1720, resolution.CanvasWidth, "map canvas width");
            ReplaceInt32(executable, 0x00295064, 720, resolution.CanvasHeight, "map canvas height");
            ReplaceInt32(executable, 0x00295082, 1478, resolution.OverlayWidth, "marker overlay width");
            ReplaceInt32(executable, 0x0029508A, 720, resolution.CanvasHeight, "marker overlay height");
        }

        /// <summary>When set, every field Apply reads or writes, as {FILE offset, size}:
        /// WindowsEnginePatch checks them against its source-authored guard coverage,
        /// including fields the old gold snapshot left at their vanilla value.</summary>
        internal static List<long[]> Touched;

        private static void Touch(long offset, int size)
        {
            if (Touched != null)
                Touched.Add(new[] { offset, size });
        }

        private static void ReplaceSingle(byte[] data, long offset, float expected, float replacement, string label)
        {
            Touch(offset, 4);
            if (offset < 0 || offset + 4 > data.LongLength)
                throw new InvalidDataException("The " + label + " patch address is outside the executable.");
            int index = checked((int)offset);
            float actual = BitConverter.ToSingle(data, index);
            if (actual != expected)
                throw new InvalidDataException("The " + label + " patch did not match the verified gold build.");
            byte[] value = BitConverter.GetBytes(replacement);
            Buffer.BlockCopy(value, 0, data, index, value.Length);
        }

        /// <summary>Code, not a value: `expected` must be there whole, and is replaced by
        /// `replacement` of the same length.</summary>
        private static void ReplaceBytes(byte[] data, long offset, byte[] expected, byte[] replacement, string label)
        {
            Touch(offset, expected.Length);
            if (replacement.Length != expected.Length || offset < 0 || offset + expected.Length > data.LongLength)
                throw new InvalidDataException("The " + label + " patch address is outside the executable.");
            for (int i = 0; i < expected.Length; i++)
                if (data[offset + i] != expected[i])
                    throw new InvalidDataException("The " + label + " patch did not match the verified gold build.");
            Buffer.BlockCopy(replacement, 0, data, checked((int)offset), replacement.Length);
        }

        private static void ReplaceSByte(byte[] data, long offset, int expected, int replacement, string label)
        {
            Touch(offset, 1);
            if (replacement < -128 || replacement > 127)
                throw new InvalidDataException("The " + label + " value " + replacement +
                    " does not fit in a signed byte.");
            sbyte found = unchecked((sbyte)data[offset]);
            if (found != expected)
                throw new InvalidDataException("The " + label + " field held " + found +
                    " where " + expected + " was expected.");
            data[offset] = unchecked((byte)(sbyte)replacement);
        }

        /// <summary>FILE offset of the .kmn enable flag. Non-zero applies Derslok's 250
        /// map-note position corrections; zero makes the lookup return immediately, so the
        /// table is inert rather than absent. See tools/build_map_note_table.py.</summary>
        internal const long MapNoteFlagOffset = 0x003E4000;

        internal static void WriteInt32(byte[] data, long offset, int value)
        {
            Touch(offset, 4);
            byte[] encoded = BitConverter.GetBytes(value);
            Buffer.BlockCopy(encoded, 0, data, checked((int)offset), encoded.Length);
        }

        private static void ReplaceInt32(byte[] data, long offset, int expected, int replacement, string label)
        {
            Touch(offset, 4);
            if (offset < 0 || offset + 4 > data.LongLength)
                throw new InvalidDataException("The " + label + " patch address is outside the executable.");
            int index = checked((int)offset);
            int actual = BitConverter.ToInt32(data, index);
            if (actual != expected)
                throw new InvalidDataException("The " + label + " patch did not match the verified gold build.");
            byte[] value = BitConverter.GetBytes(replacement);
            Buffer.BlockCopy(value, 0, data, index, value.Length);
        }
    }
}
