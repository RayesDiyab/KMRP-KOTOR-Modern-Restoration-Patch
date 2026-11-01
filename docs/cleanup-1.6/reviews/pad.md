> **Working notes** of the 1.6 audit, 2026-11-01, kept as the evidence for [the report](../../cleanup-audit-1.6-report.md). Not a reference: leads may be overturned there. Documentation standard: [`documentation-standard.md`](../../documentation-standard.md).

# Second pass PAD (saved from agent's reply; verify high ones). Nothing run in game.

PAD-1 HIGH code path confirmed, link to reports strongly suspected: issues 88, 90. K1NativeJoystick.cpp:3077-3089 PressHudButtonK1 (called :2905,:2909; v1.5.1 :2910,:2740,:2743) calls 0x0068B050, 0x0068B0A0 directly with button; handlers begin mov ecx,[arg+0x4C]; je exit (0x0068B057, 0x0068B0A4). Only CSWGuiControl::HandleInputEvent writes +0x4C (0x004187AE). Ctors do not set it (0x0041AA80, 0x0041B8B0, 0x0041C100); HUD 0xC8CC from operator new no zero (0x00633021). So heap garbage, lifetime of HUD. Mouse click sets 1 (0x0041ABD0). Xbox HUD parks BTN_CLEARALL off screen. Return value true when handler declined. Mac hud.cpp:175-180 goes via vtable (kEventA,1). Fix: vtable +0x3C with (0x27,1), click sound; or 0x00688790 for Y (test bit 2 first). Verify: debug line printing +0x4C; pad only after fresh launch, then one mouse click on Clear predicted fix.
  Issue 90: no Steam Input branch; incidental. Issue 88 benign: first Y only tutorial (0x005EDF40 with 0x20).
PAD-2 HIGH confirmed by reading: D-pad up/down and X dead after A: vendor K1XboxControls.cpp:5698-5700 CycleAction, :5784-5788: handlers 0x006884B0, 0x00688520, 0x0068AF70, 0x0068AFE0, 0x0068B970 test [slot+0x4C]; A's release sets 0. Fix: one helper via vtable +0x3C; wheel events 0x1F4,0x1F5 (0x0068BBE3).
PAD-3 MEDIUM suspected: A on focused slot activates twice: K1NativeJoystick.cpp:1509,:1777-1783,:2868. Native 0x27 + HUD update. Need measuring; does 0x0068AD60/0x00689610 dedup?
PAD-4 HIGH confirmed by reading: bark bubble takes action bar (issue 87): vendor :1383-1416 IsGameplayHudActive; K1_CONFIG :615-621; CSWGuiBarkBubble vtable 0x00755C60, AddPanel(bubble,4,1). A does default attack, B disengages, D-pad dropped during lifetime. a7f4224 fixed drawing only. Fix: pass vtable as passive. Link to BOS:SR suspected.
PAD-5 MEDIUM confirmed by reading: D-pad presses in menus move action bar later: K1NativeJoystick.cpp:7200-7203,:7210-7213, :2856-2859. Fix: fromDpad && class PC.
PAD-6 MEDIUM suspected: input rebuild replays held buttons, swallow release :1013-1021. Seed lastButtons, clear remapSuppressed.
PAD-7 LOW suspected: motors hold through movie; one zero call at first movie frame. 0x004B8393 is server path, not movie.
PAD-8 LOW suspected: stale saber K1Rumble.cpp:872,:949-952; clear g_sabers at no-controlled branch :1256-1261.

Verified safe: backend pad change/focus loss; loading screens edges; request windows 250 ms; B,X,Y class PC; remap corrupt ini defaults (K1ButtonRemap.cpp:29-48), conflicts; kHide; pause banner below HUD; floaty text; 13 GetProcAddress signatures match, null checked, no version handshake; KmrpIsBesideK1 cached; issue 85 fix bounded; mid-combat load.
Docs wrong: :3072-3073 "exactly a mouse click"; :1758-1761; :424-425 0x006E622E is INGAME_GAMEPLAY; K1Rumble.cpp:944-946; controller-parity.md, behaviour matrix.
Not verified: live +0x4C; HUD rebuild; StopRumblePattern scripts; turret sign; Start in minigame; Pazaak/class/galaxy sampled; ReadControllerK1 no lock movie vs main; stale hudInterface; Mac PAD-3..5.
