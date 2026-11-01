# The 1.6 cleanup audit: every place KMRP changes the game

> **Documentation standard.** This document follows [`documentation-standard.md`](documentation-standard.md).

**Kind: reference, generated.** Made by `tools/list_kmrp_changes.py` from the build (issue 82); run it again rather than editing the tables. The audit column is filled by hand.

In all: 139 KPM hooks across five patches, 146 engine recipe runs and resolution operands, and 10 kinds of run-time write.

## 1. KOTOR Patch Manager hooks

From the `patch_config.toml` sections the build makes. A bundled patch of another author is listed for overlap and timing only: its code is not KMRP's to change.

### 1.1 `kmrp`, 36 hooks (KMRP)

| # | address | type | function | defined in | when | params | what it is for | audit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `0x00404BB0` | detour | `NativeMovieWindowCloseK1` | `src/controller-native/K1MovieWindow.cpp:113` | always | 1 | And once more on the way out, for the same reason. 0x00404BB0 is CExoMoviePlayerInternal::ShutDown, whose entry runs before BinkBufferClo... | keep: `ShutDown`'s entry; the class brush and fill, `movies.md` table at line 778 |
| 2 | `0x00404D06` | detour | `KmrpCoreMovieWorkK1` | `src/controller-native/K1CoreFrames.cpp:116` | always | 1 | (no comment) | keep: KMRP's movie frame; one patch per address, so the controller's is `0x00404D96` (`kpm-edition.md`) |
| 3 | `0x0040554B` | detour | `NativeMovieWindowOpenK1` | `src/controller-native/K1MovieWindow.cpp:104` | always | 1 | Black the movie window the moment it exists. The grey flash before and after every movie is the window class. CExoMoviePlayerInternal::In... | keep: just after `CreateWindowExA`, `movies.md`; with `0x00404BB0` the two ends of one job |
| 4 | `0x00407230` | detour | `KmrpPrepareResourcesK1` | `src/controller-native/K1RuntimeAssets.cpp:1724` | always | 1 | Prepare the embedded bank before the first native resource lookup, so font images and TXI coordinates cannot mix cached stock and replace... | keep: KMRP's resource preparation, one patch per address (`kpm-edition.md`); F2 |
| 5 | `0x0040A680` | detour | `KmrpPanelLayoutStartK1` | `src/controller-native/K1RuntimeLayout.cpp:644` | always | 2 | (no comment) | keep: `StartLoadFromLayout`, what `resolution-switch.md` 5a needs of every panel |
| 6 | `0x0040B930` | detour | `KmrpPanelControlK1` | `src/controller-native/K1RuntimeLayout.cpp:668` | always | 4 | (no comment) | keep: `InitControl`, each control by tag, the same 5a |
| 7 | `0x0040BE70` | detour | `KmrpResolutionRequestedK1` | `src/controller-native/K1RuntimeResolution.cpp:313` | always | 3 | SetSize entry: request only; native SetSize and panel/texture handling still run. | keep: sees all four `SetSize` callers, including a startup path `0x005F18F6` can miss (F10) |
| 8 | `0x0040C24E` | detour | `KeyboardKeepFocusK1` | `src/controller-native/K1KeyboardNavigation.cpp:203` | always | 3 | GUI mouse hit testing, after coordinate storage and 3D cursor processing. mov ecx,[esi+0x10] / test ecx,ecx; the consumed exit unwinds th... | keep: `windows-keyboard-navigation.md`, stationary mouse sample. **That document and CHANGELOG record the Windows repair as not verified on a physical keyboard: F13** |
| 9 | `0x0040CE76` | detour | `KmrpCoreGuiWorkK1` | `src/controller-native/K1CoreFrames.cpp:104` | always | 1 | (no comment) | keep: KMRP's GUI frame, 8 calls; one patch per address (`kpm-edition.md`) |
| 10 | `0x0040CF70` | detour | `KmrpPanelDestroyedK1` | `src/controller-native/K1RuntimeLayout.cpp:714` | always | 1 | (no comment) | keep: `~CSWGuiPanel` (`custom-gui-controls.md`); one entry for five modules' forget calls, already shared |
| 11 | `0x00419A20` | detour | `KmrpControlDestroyedK1` | `src/controller-native/K1RuntimeLayout.cpp:796` | always | 1 | (no comment) | keep from the source: one entry for layout and text state. **Function not named in any document, 44 direct callers: F13** |
| 12 | `0x0041A3E0` | detour | `KmrpTextListDrawK1` | `src/controller-native/K1TextLayout.cpp:849` | always | 1 | Native lists may populate after the common GUI frame; adapt their rows before this first draw as well. SUB ESP,8 / PUSH EBP / MOV EBP,[ES... | keep: one-line forward to `KmrpTextRowsK1` (`release-1.6-progress.md`) |
| 13 | `0x0041A9D0` | detour | `KeyboardNavigateK1` | `src/controller-native/K1KeyboardNavigation.cpp:149` | always | 3 | Keyboard navigation is core behavior, independent of the controller option. CSWGuiNavigable::HandleInputEvent: mov eax,[esp+8] / test eax... | keep: `CSWGuiNavigable`'s input; lists have their own, `0x0041CE20` (`retained-xbox-gui-events.md`). Same 5-line prefix as it. F13 |
| 14 | `0x0041B4BF` | detour | `KmrpListRowK1` | `src/controller-native/K1RuntimeLayout.cpp:471` | always | 3 | CSWGuiListBox::OrganizeControls (0x41b140), the three places it hands a row its rectangle, which is on the stack at [esp+0x20]: the rows... | keep: the three row sites of `OrganizeControls`, one handler, `listbox-geometry.md` |
| 15 | `0x0041B540` | detour | `KmrpListRowK1` | `src/controller-native/K1RuntimeLayout.cpp:471` | always | 3 | (no comment) | keep: as above |
| 16 | `0x0041B59F` | detour | `KmrpListRowK1` | `src/controller-native/K1RuntimeLayout.cpp:471` | always | 3 | (no comment) | keep: as above |
| 17 | `0x0041C1D0` | detour | `KmrpListAddRowsK1` | `src/controller-native/K1RuntimeLayout.cpp:510` | always | 2 | CSWGuiListBox::AddControls, entry (K1RuntimeLayout.cpp, KmrpListAddRowsK1): the rows that outlive a change of resolution get the row heig... | keep: rows made once and kept, `resolution-switch.md` section 6 |
| 18 | `0x0041CE20` | detour | `KeyboardListBoundaryK1` | `src/controller-native/K1KeyboardNavigation.cpp:172` | always | 3 | Lists retain native interior selection; keyboard arrows leave at a boundary. Same six-byte entry, with handled events made inert before n... | keep: `CSWGuiListBox`'s input, `retained-xbox-gui-events.md`. F13 |
| 19 | `0x0041FEB5` | replace | `` |  | always | 0 | Saturate AurTextureGetMaxTexID's return at 4999. Saturating rather than masking: an AND would wrap a legitimate 4500 down to 404 and leav... | keep: real overrun, proved on the gold image, adopted from KPM's TextureBucketSafety (`texture-bucket-overrun.md`); bytes only |
| 20 | `0x004216F1` | detour | `KmrpTextureUploadedK1` | `src/controller-native/K1TextLayout.cpp:783` | always | 1 | CAurTextureBasic::BuildAndStoreTexture, just after its CALL glImage (0x004216EC) uploaded the picture. EBX is the texture; its OpenGL nam... | keep: three jobs at one site: the mipmap correction, once (`third-party-driver-compat.md`), a font's ink, a caption's picture. `const_cast`s not needed since F4 |
| 21 | `0x00422CC1` | detour | `KmrpFontMetricsLoadedK1` | `src/controller-native/K1RuntimeAssets.cpp:1701` | always | 1 | CAurTexture::LoadTXI common epilogue. EDI still owns this texture; both loose and embedded metadata have parsed, and every normal return... | keep: LoadTXI's one common exit, `override-font-metrics.md` |
| 22 | `0x0045A2F0` | detour | `KmrpTextStringWrapK1` | `src/controller-native/K1TextLayout.cpp:558` | always | 2 | (no comment) | keep: the line breaker, vtable `+0x4C` (`native-text-coverage.md`); five text sites, each a different moment |
| 23 | `0x0045A857` | detour | `KmrpTextStringDrawK1` | `src/controller-native/K1TextLayout.cpp:840` | always | 1 | The old font recipe owns Draw's entry (0x45A850..0x45A856), then restores ECX and returns here. Hook its original body, never that trampo... | keep: past the old font recipe's entry; reinstalls the widths after an outer wrap |
| 24 | `0x0045B7A0` | detour | `KmrpTextIdealHeightK1` | `src/controller-native/K1TextLayout.cpp:551` | always | 1 | CAurGUIStringInternal::GetIdealPixelHeight entry: PUSH -1 / MOV EAX,FS:[0], 8 bytes, no relative operand. With -1 it answers from the lin... | keep: vtable `+0x50`; asked with -1 it answers without wrapping, so the wrap hook does not see it (source, `custom-gui-controls.md`) |
| 25 | `0x0045BAC0` | detour | `KmrpTextStringCreatedK1` | `src/controller-native/K1TextLayout.cpp:501` | always | 1 | Per-instance text scale is captured after the native constructor stores +0x40. Each prefix below consists of complete instructions with n... | keep: pairs with `0x0045BC70`; only a table row in `release-1.6-progress.md` |
| 26 | `0x0045BC70` | detour | `KmrpTextStringDestroyedK1` | `src/controller-native/K1TextLayout.cpp:510` | always | 1 | (no comment) | keep: `strings.erase`, without it the map keeps dead entries; same table |
| 27 | `0x0046BE64` | replace | `` |  | always | 0 | Range-check the texture id in AddPartToMeshBuckets. An out-of-range part skips the bucket insert and rejoins at 0x0046BEB1, which preserv... | keep: the same adoption as `0x0041FEB5`; bytes only |
| 28 | `0x004A8380` | replace | `` |  | always | 0 | ~CAurTriangleBin (0x004A8350), the same sequence with eax for edx. | keep: guards a double free; **no double free reproduced in play** (`macos-memory-safety-audit.md`); bytes only |
| 29 | `0x004A847C` | replace | `` |  | always | 0 | DestroyGrassPolys (0x004A8460). | keep: as above |
| 30 | `0x005DDE32` | detour | `NativeFreeSaveBufferK1` | `src/controller-native/K1CoreFrames.cpp:35` | always | 1 | --- Save game memory leak ------------------------------------------------ CERFFile::WriteResource (hook site is +0x272) passes a resourc... | keep: adopted from KPM's SaveGameMemoryLeak, ownership reviewed there, not re-derived here (source). Do not port: the Mac frees it (`macos-memory-safety-audit.md`) |
| 31 | `0x005F0C64` | detour | `KmrpAllowRuntimeResolutionK1` | `src/controller-native/K1RuntimeResolution.cpp:302` | always | 2 | IsValidResolution: CMP EAX,800. Callback supplies the result in EAX. Valid dimensions leave through the original RET 8. For rejection EAX... | keep: the validity rule of `runtime-resolution-preview.md` |
| 32 | `0x005F18F6` | detour | `KmrpModeSwitchK1` | `src/controller-native/K1RuntimeResolution.cpp:290` | always | 0 | The native mode switch, after it stores the new size (0x0078D1D4/0x0078D1D8) and before it re-creates the window at 0x005F19B2, which rel... | keep: before the window is made again, then the fonts' TXI (`runtime-resolution-preview.md`); F10 |
| 33 | `0x006258E2` | detour | `FitMessageBoxK1` | `src/controller-native/K1PopupFit.cpp:85` | always | 1 | --- The message popup, fitted to its contents ------------------------------ CSWGuiMessageBox::FixMessageLabel (0x006253A0) keeps confirm... | keep: `message-popup.md`. 65 lines, one job; its shape is for section 4 |
| 34 | `0x0062785F` | simple | `` |  | always | 0 | ToolTipPanel constructor: width 1280 with height other than 960/1024 skipped StartLoadFromLayout entirely. Route its existing JNE to the... | keep: a 1280-wide size other than 960 or 1024 failed in the tooltip constructor (`runtime-resolution-preview.md`, measured); 2 bytes |
| 35 | `0x006AB9D5` | detour | `GrantedRowTextK1` | `src/controller-native/K1GrantedPopup.cpp:170` | always | 2 | In CSWGuiInGameSkillEntry::SetExtent (0x006AB8E0), before its last call gives the text its rect: `push eax; mov ecx, esi; call [ebp+4]`,... | keep: `windows-changes-from-macos.md`, the row's last call; pairs with `0x006CE0B0` |
| 36 | `0x006CE0B0` | detour | `GrantedPopupFilledK1` | `src/controller-native/K1GrantedPopup.cpp:159` | always | 1 | --- The "granted" popup's rows ---------------------------------------------- The popup listing a level's feats or powers (skillinfo.gui)... | keep: the same; rows and popup are fitted at different moments |

### 1.2 `kmrp-controller`, 38 hooks (KMRP)

| # | address | type | function | defined in | when | params | what it is for | audit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `0x00404D96` | detour | `NativeMovieFrameK1` | `src/controller-native/K1NativeJoystick.cpp:2469` | always | 1 | Poll XInput once per Bink frame; the normal ProcessInput hook does not run while a movie owns the game loop. This must sit INSIDE the loo... | [ ] |
| 2 | `0x00407235` | detour | `ControllerPrepareResourcesK1` | `src/controller-native/K1ControllerStandalone.cpp:372` | always | 1 | (no comment) | keep: the controller's resource preparation, its own site so it works without KMRP (F2) |
| 3 | `0x00409B80` | detour | `NativePanelLoadedK1` | `src/controller-native/K1NativeJoystick.cpp:2828` | always | 3 | (no comment) | [ ] |
| 4 | `0x00409E60` | detour | `GuardPanelEchoK1` | `src/controller-native/K1NativeJoystick.cpp:3688` | always | 3 | The echo guard, on every panel. CSWGuiPanel::HandleInputEvent, 0x00409E60, hands an event to the focused control, [panel+0x1C]; when that... | [ ] |
| 5 | `0x0040C1F6` | detour | `NativeNoteMouseK1` | `src/controller-native/K1NativeJoystick.cpp:2539` | always | 3 | Clear keyboard focus when the mouse moves over an action button. | [ ] |
| 6 | `0x0040C8E0` | detour | `GuardReleaseTargetK1` | `src/controller-native/K1NativeJoystick.cpp:3780` | always | 3 | A release goes where its press went, as the mouse's does: CSWGuiManager:: HandleInputEvent 0x0040C8E0, where every pad and key event reac... | [ ] |
| 7 | `0x0040CE70` | detour | `NativeGuiFrameK1` | `src/controller-native/K1NativeJoystick.cpp:7364` | always | 1 | The GUI's own per-frame update, where KMRP's focus navigation performs its moves. It has to be here rather than in the input hook: CSWGui... | [ ] |
| 8 | `0x0040CFAB` | detour | `NativePanelDestroyedK1` | `src/controller-native/K1NativeJoystick.cpp:2843` | always | 1 | (no comment) | [ ] |
| 9 | `0x005E24E0` | detour | `NativeJoystickInitK1` | `src/controller-native/K1NativeJoystick.cpp:1997` | always | 1 | Register the joystick descriptions and raise the device count, once the input singleton exists. Idempotent; runs every frame and returns... | [ ] |
| 10 | `0x005E271E` | detour | `NativeNoteKeyboardK1` | `src/controller-native/K1NativeJoystick.cpp:2534` | always | 2 | Capture raw keyboard input before KOTOR applies its key bindings. | [ ] |
| 11 | `0x005E30F6` | detour | `NativeJoystickBufferK1` | `src/controller-native/K1NativeJoystick.cpp:2945` | always | 1 | Replace CExoRawInputInternal::GetJoystickBuffer. Hooked past the entry, where esi holds the caller's record buffer -- at the true entry i... | [ ] |
| 12 | `0x005F74B0` | detour | `NativeRumbleStopK1` | `src/controller-native/K1Rumble.cpp:1059` | always | 2 | CClientExoAppInternal::StopRumblePattern, 0x005F74B0, at its entry. ecx is the object; [esp+4] the index. Observes: the engine's search o... | [ ] |
| 13 | `0x005F7617` | detour | `NativeRumbleK1` | `src/controller-native/K1NativeJoystick.cpp:2404` | always | 4 | Route the engine's own rumble to XInput. KOTOR still runs the Xbox build's rumble subsystem. UpdateRumble at 0x005F7500 walks the active... | [ ] |
| 14 | `0x005FB49F` | detour | `NativeRumblePlayK1` | `src/controller-native/K1Rumble.cpp:1028` | always | 2 | CClientExoAppInternal::PlayRumblePattern, 0x005FB490, at its index test: 005FB491  mov ebp,[esp+8]        the pattern index 005FB499  jl... | [ ] |
| 15 | `0x005FB98E` | detour | `NativeRumbleCutoffK1` | `src/controller-native/K1Rumble.cpp:1080` | always | 1 | CClientExoAppInternal::LookUpAndPerformRumbleWithCutOff, 0x005FB960, just after its frame and local string are built: 005FB961  mov ebp,e... | [ ] |
| 16 | `0x006039CF` | detour | `NativeCameraFrameK1` | `src/controller-native/K1NativeJoystick.cpp:2940` | always | 1 | Apply the right-stick camera turn, immediately after UpdateCamera has run. The timing is the whole point, and getting it wrong is why an... | [ ] |
| 17 | `0x0060DE20` | detour | `NativeSaberContactK1` | `src/controller-native/K1Rumble.cpp:1176` | always | 1 | CSWCCreature::ShowLightSaberContactVisual, 0x0060DE20, at its entry; ecx is the wielder. Reached from the attack animation's hit-contact... | [ ] |
| 18 | `0x00617EB0` | detour | `NativeMeleeHitK1` | `src/controller-native/K1Rumble.cpp:1191` | always | 1 | HitEvent, 0x00617EB0, the creature animation event "hit" (registered by CSWCCreature::RegisterCallbacks, 0x0061AB40): the impact moment o... | [ ] |
| 19 | `0x0063C4F0` | detour | `NativeParryK1` | `src/controller-native/K1Rumble.cpp:1211` | always | 1 | CSWCObject::AnimationParry, 0x0063C4F0, at its entry; ecx is the object parrying. The stolen `test ecx,ecx` sets the flags the `je` at 0x... | [ ] |
| 20 | `0x00646BA0` | detour | `NativeSaberPowerK1` | `src/controller-native/K1Rumble.cpp:1150` | always | 2 | CSWCItem::ResolveCreaturePoweredAnimations, 0x00646BA0, at its entry. ecx is the item; [esp+4] the power flag. CSWCItem::PowerItem (0x006... | [ ] |
| 21 | `0x00670FB0` | detour | `NativeMiniGameAxisK1` | `src/controller-native/K1NativeJoystick.cpp:8289` | always | 2 | (no comment) | [ ] |
| 22 | `0x00679940` | detour | `NativeJoystickMovementK1` | `src/controller-native/K1NativeJoystick.cpp:7893` | always | 1 | Override the movement axes at the single point every control scheme passes through. ProcessInput has already clamped the keyboard values... | [ ] |
| 23 | `0x00679B71` | detour | `NativeJoystickSkipNormalizeK1` | `src/controller-native/K1NativeJoystick.cpp:7984` | always | 1 | Bypass Control's own Vector::Normalize, but only while the stick is driving. That call is correct for the keyboard, where each axis is ex... | [ ] |
| 24 | `0x00685ED0` | detour | `KmrpXboxHudBarsK1` | `src/controller-native/K1XboxHud.cpp:1354` | always | 1 | (no comment) | [ ] |
| 25 | `0x00686BA0` | detour | `NativeActionBarK1` | `src/controller-native/K1NativeJoystick.cpp:2854` | always | 1 | Process captured keyboard input during the gameplay HUD update. | [ ] |
| 26 | `0x0068947A` | detour | `KmrpXboxHudListsK1` | `src/controller-native/K1XboxHud.cpp:2616` | always | 1 | (no comment) | [ ] |
| 27 | `0x0068AB10` | detour | `KmrpXboxHudK1` | `src/controller-native/K1XboxHud.cpp:1974` | always | 1 | (no comment) | [ ] |
| 28 | `0x0068B170` | detour | `ClearActionBarControlsK1` | `src/controller-native/vendor/K1XboxControls.cpp:7246` | always | 1 | Clear cached HUD state when KOTOR destroys the gameplay interface. | [ ] |
| 29 | `0x006C00C0` | detour | `KmrpXboxHudPauseReasonK1` | `src/controller-native/K1XboxHud.cpp:2663` | always | 1 | (no comment) | [ ] |
| 30 | `0x006C02A4` | detour | `KmrpXboxHudPauseReasonDoneK1` | `src/controller-native/K1XboxHud.cpp:2672` | always | 1 | (no comment) | [ ] |
| 31 | `0x006C2400` | detour | `ResolveSoloModeConfirmK1` | `src/controller-native/K1NativeJoystick.cpp:2230` | always | 3 | CSWGuiInGameSoloModeQuery::HandleInputEvent, 0x006C2400. 006C2400  mov edx,[esp+8]     value 006C2404  test edx,edx        a release (0)... | keep: solo-mode popup, A on Cancel becomes B |
| 32 | `0x006D4440` | detour | `NativeMuzzleFlashK1` | `src/controller-native/K1Rumble.cpp:1226` | always | 1 | CSWCProjectile::CreateMuzzleFlash, 0x006D4440, at its entry; ecx is the projectile. The stolen `mov ebx,[esp+8]` is ESP-relative, and KPM... | [ ] |
| 33 | `0x006E0CF0` | detour | `ResolveResolutionConfirmK1` | `src/controller-native/K1NativeJoystick.cpp:2246` | always | 3 | CSWGuiOptionsResolution::HandleInputEvent, 0x006E0CF0. Its frame is built on EBP, so the event is read later as [ebp+8]; at the entry it... | keep: resolution popup, confirm once (2026-10-28 double pop) |
| 34 | `0x006F28C0` | detour | `GuardPowersConfirmK1` | `src/controller-native/K1NativeJoystick.cpp:2394` | always | 3 | (no comment) | keep: thin export over GuardChargenConfirmK1 (one per dispatcher, already shared) |
| 35 | `0x006F4680` | detour | `GuardFeatsConfirmK1` | `src/controller-native/K1NativeJoystick.cpp:2389` | always | 3 | (no comment) | keep: as above |
| 36 | `0x006F6A10` | detour | `GuardSkillsConfirmK1` | `src/controller-native/K1NativeJoystick.cpp:2384` | always | 3 | (no comment) | keep: as above |
| 37 | `0x006F8880` | detour | `GuardAbilitiesConfirmK1` | `src/controller-native/K1NativeJoystick.cpp:2379` | always | 3 | (no comment) | keep: as above |
| 38 | `0x006F8FF0` | detour | `GuardPortraitConfirmK1` | `src/controller-native/K1NativeJoystick.cpp:2399` | always | 3 | (no comment) | keep: as above |

### 1.3 `high-fps-fixes`, 36 hooks (D3M0 (bundled, unchanged))

| # | address | type | function | params | audit |
| --- | --- | --- | --- | --- | --- |
| 1 | `0x00460981` | detour | `K1UpdateCycleTexture` | 0 | n/a: theirs |
| 2 | `0x00461823` | detour | `K1GateWaterControllerFrame` | 0 | n/a: theirs |
| 3 | `0x004618BF` | detour | `K1FixWaterVirtualFrameDelta` | 0 | n/a: theirs |
| 4 | `0x00481AF8` | simple | `` | 0 | n/a: theirs |
| 5 | `0x004836C7` | detour | `K1GateJitterBranch1` | 0 | n/a: theirs |
| 6 | `0x004836E6` | replace | `` | 0 | n/a: theirs |
| 7 | `0x00483703` | replace | `` | 0 | n/a: theirs |
| 8 | `0x00483916` | detour | `K1GateJitterBranch2` | 0 | n/a: theirs |
| 9 | `0x00483936` | replace | `` | 0 | n/a: theirs |
| 10 | `0x00483950` | replace | `` | 0 | n/a: theirs |
| 11 | `0x00483B72` | detour | `K1GateJitterBranch3` | 0 | n/a: theirs |
| 12 | `0x00483BA4` | replace | `` | 0 | n/a: theirs |
| 13 | `0x00483BB3` | replace | `` | 0 | n/a: theirs |
| 14 | `0x004842EA` | simple | `` | 0 | n/a: theirs |
| 15 | `0x004973F7` | detour | `K1AccumulateParticleTime` | 0 | n/a: theirs |
| 16 | `0x004974AB` | detour | `K1CalculateParticleBudget` | 0 | n/a: theirs |
| 17 | `0x004975F1` | replace | `` | 0 | n/a: theirs |
| 18 | `0x00497610` | simple | `` | 0 | n/a: theirs |
| 19 | `0x0049CC96` | detour | `K1ResetParticleInit` | 0 | n/a: theirs |
| 20 | `0x0049CFC0` | detour | `K1ResetParticleDestroy` | 0 | n/a: theirs |
| 21 | `0x0060335D` | detour | `K1UpdateJitterTick` | 0 | n/a: theirs |
| 22 | `0x0060F92E` | detour | `K1AccumulatePreviewMilliseconds` | 0 | n/a: theirs |
| 23 | `0x0060FABD` | detour | `K1ResetPreviewIdle` | 0 | n/a: theirs |
| 24 | `0x006138E0` | detour | `K1ResetPreviewObject` | 0 | n/a: theirs |
| 25 | `0x00616E98` | detour | `K1ResetPreviewObject` | 0 | n/a: theirs |
| 26 | `0x00623B54` | replace | `` | 0 | n/a: theirs |
| 27 | `0x00623C16` | simple | `` | 0 | n/a: theirs |
| 28 | `0x00639E01` | replace | `` | 0 | n/a: theirs |
| 29 | `0x0063FF0E` | replace | `` | 0 | n/a: theirs |
| 30 | `0x00641700` | detour | `K1ResetShakeNewEffect` | 0 | n/a: theirs |
| 31 | `0x00641827` | detour | `K1AccumulateShakeMilliseconds` | 0 | n/a: theirs |
| 32 | `0x006440EA` | detour | `K1ResetShakeConstructor` | 0 | n/a: theirs |
| 33 | `0x006A7529` | replace | `` | 0 | n/a: theirs |
| 34 | `0x006A75C8` | replace | `` | 0 | n/a: theirs |
| 35 | `0x006A77A9` | replace | `` | 0 | n/a: theirs |
| 36 | `0x006A7842` | replace | `` | 0 | n/a: theirs |

### 1.4 `k1-marked-empty-containers`, 1 hooks (ShaeMyName (bundled, unchanged))

| # | address | type | function | params | audit |
| --- | --- | --- | --- | --- | --- |
| 1 | `0x00685E69` | replace | `` | 0 | n/a: theirs |

### 1.5 `k1-modern-driver-compatibility`, 28 hooks (Synchro (bundled, unchanged))

| # | address | type | function | params | audit |
| --- | --- | --- | --- | --- | --- |
| 1 | `0x004260D9` | detour | `ARB_ReorderNormalMap` | 2 | n/a: theirs |
| 2 | `0x004264A2` | simple | `` | 0 | n/a: theirs |
| 3 | `0x00426529` | simple | `` | 0 | n/a: theirs |
| 4 | `0x00428859` | detour | `ARB_InstallFrameBufferShaders` | 0 | n/a: theirs |
| 5 | `0x0042BC21` | simple | `` | 0 | n/a: theirs |
| 6 | `0x0042BCB5` | simple | `` | 0 | n/a: theirs |
| 7 | `0x0042BD3F` | simple | `` | 0 | n/a: theirs |
| 8 | `0x0042BDD0` | simple | `` | 0 | n/a: theirs |
| 9 | `0x0042BE3A` | simple | `` | 0 | n/a: theirs |
| 10 | `0x004367D4` | detour | `ARB_FragmentPathAvailable` | 0 | n/a: theirs |
| 11 | `0x004373BD` | detour | `ARB_InstallFragmentPath` | 0 | n/a: theirs |
| 12 | `0x0043D0F2` | detour | `ARB_MaterialHasNormalMap` | 1 | n/a: theirs |
| 13 | `0x0044DF8E` | detour | `ARB_InstallSoftShadowShader` | 0 | n/a: theirs |
| 14 | `0x0045F7E7` | simple | `` | 0 | n/a: theirs |
| 15 | `0x0045FA6C` | simple | `` | 0 | n/a: theirs |
| 16 | `0x00470D51` | detour | `ARB_MaterialHasNormalMap` | 1 | n/a: theirs |
| 17 | `0x00470EB6` | simple | `` | 0 | n/a: theirs |
| 18 | `0x00474FCA` | detour | `ARB_AdoptVertexProgram` | 2 | n/a: theirs |
| 19 | `0x004755A8` | detour | `ARB_AdoptVertexProgram` | 2 | n/a: theirs |
| 20 | `0x0048741B` | detour | `ARB_AdoptVertexProgram` | 2 | n/a: theirs |
| 21 | `0x0048AB8F` | detour | `ARB_SkinBranch` | 1 | n/a: theirs |
| 22 | `0x0048AD63` | detour | `ARB_SkinBranch` | 1 | n/a: theirs |
| 23 | `0x0048AE0E` | detour | `ARB_AdoptVertexProgram` | 2 | n/a: theirs |
| 24 | `0x0048B537` | detour | `ARB_MaterialHasNormalMap` | 1 | n/a: theirs |
| 25 | `0x0048B544` | detour | `ARB_SkinBranch` | 1 | n/a: theirs |
| 26 | `0x0048B5D4` | detour | `ARB_AdoptVertexProgram` | 2 | n/a: theirs |
| 27 | `0x0048C59A` | detour | `ARB_SkinBranch` | 1 | n/a: theirs |
| 28 | `0x00740968` | simple | `` | 0 | n/a: theirs |

## 2. The engine recipe (applied in memory by `kmrp.dll`)

87 byte runs in the game's own code and data, the 0xb000-byte block at `0x0086d000` (KMRP's added code, copied wherever it can be allocated) and 46 relocated fields. Section 4 of `reverse-engineering/binary-inventory.md` names the documents for each run.

| # | VA | len | feature | first named in | audit |
| --- | --- | --- | --- | --- | --- |
| 1 | `0x00403D6C` | 4 | movie display mode | `tools/build_windows_engine.py:114` | [ ] |
| 2 | `0x00403D78` | 4 | movie display mode | `tools/build_windows_engine.py:114` | [ ] |
| 3 | `0x00403EAD` | 4 | movie display mode | `tools/build_windows_engine.py:129` | [ ] |
| 4 | `0x00403EB9` | 4 | movie display mode | `tools/build_windows_engine.py:129` | [ ] |
| 5 | `0x00405734` | 1 | movies | `tools/build_windows_engine.py:108` | [ ] |
| 6 | `0x004057AC` | 7 | movies | `tools/build_windows_engine.py:113` | [ ] |
| 7 | `0x0040AA65` | 4 | core | `tools/build_windows_engine.py:130` | [ ] |
| 8 | `0x0040AA85` | 4 | core | `tools/build_windows_engine.py:130` | [ ] |
| 9 | `0x0040B6C7` | 4 | core | `tools/build_windows_engine.py:132` | [ ] |
| 10 | `0x0040B6DA` | 4 | core | `tools/build_windows_engine.py:133` | [ ] |
| 11 | `0x0040BA6C` | 4 | core | `tools/build_windows_engine.py:132` | [ ] |
| 12 | `0x0040BA83` | 4 | core | `tools/build_windows_engine.py:133` | [ ] |
| 13 | `0x00415E0D` | 5 | core | `tools/build_leading_newline_fix.py:37` | [ ] |
| 14 | `0x00417992` | 10 | core | `tools/build_font_scale_wrapper.py:81` | [ ] |
| 15 | `0x0041A2F2` | 15 | core | `tools/build_gutter_side_fix.py:68` | [ ] |
| 16 | `0x0041B1C4` | 1 | core | `tools/build_listbox_padding_fix.py:57` | [ ] |
| 17 | `0x0041B26B` | 1 | core | `tools/build_listbox_padding_fix.py:59` | [ ] |
| 18 | `0x0041B339` | 1 | core | `tools/build_listbox_padding_fix.py:74` | [ ] |
| 19 | `0x0041B3AE` | 1 | core | `tools/build_listbox_padding_fix.py:76` | [ ] |
| 20 | `0x0041B46D` | 12 | core | `tools/build_gutter_side_fix.py:62` | [ ] |
| 21 | `0x0041B48C` | 5 | core | `tools/build_gutter_side_fix.py:39` | [ ] |
| 22 | `0x0041B507` | 2 | core | `tools/build_listbox_growth_fix.py:54` | [ ] |
| 23 | `0x0041B52E` | 1 | core | `` | [ ] |
| 24 | `0x0041B553` | 1 | core | `tools/build_listbox_padding_fix.py:61` | [ ] |
| 25 | `0x0045992A` | 26 | core | `tools/build_minimap_zoom_fix.py:77` | [ ] |
| 26 | `0x0045A3B7` | 6 | core | `tools/build_wrap_progress_fix.py:39` | [ ] |
| 27 | `0x0045A3DC` | 6 | core | `tools/build_wrap_progress_fix.py:40` | [ ] |
| 28 | `0x0045A5E0` | 16 | core | `tools/build_wrap_progress_fix.py:69` | [ ] |
| 29 | `0x0045A850` | 7 | core | `tools/audit_native_text_paths.py:26` | [ ] |
| 30 | `0x004A1770` | 13 | core | `tools/audit_native_text_paths.py:27` | [ ] |
| 31 | `0x005F0C65` | 4 | core | `tools/build_windows_engine.py:131` | [ ] |
| 32 | `0x005F0C6F` | 4 | core | `tools/build_windows_engine.py:131` | [ ] |
| 33 | `0x005F5B3B` | 12 | movie display mode | `tools/build_windows_engine.py:114` | [ ] |
| 34 | `0x005F92A8` | 2 | movie display mode | `tools/build_windows_engine.py:109` | [ ] |
| 35 | `0x0062540D` | 4 | core | `tools/build_windows_engine.py:136` | [ ] |
| 36 | `0x006256DC` | 11 | core | `tools/build_windows_engine.py:134` | [ ] |
| 37 | `0x006256F6` | 4 | core | `tools/build_windows_engine.py:134` | [ ] |
| 38 | `0x006256FC` | 27 | core | `tools/build_windows_engine.py:160` | [ ] |
| 39 | `0x00625759` | 4 | core | `tools/build_windows_engine.py:135` | [ ] |
| 40 | `0x00626F95` | 4 | core | `tools/build_windows_engine.py:136` | [ ] |
| 41 | `0x0062B39B` | 5 | core | `tools/build_windows_engine.py:181` | [ ] |
| 42 | `0x0068AC9F` | 5 | core | `tools/build_minimap_fog_fix.py:10` | [ ] |
| 43 | `0x0068C4E3` | 4 | core | `tools/build_windows_engine.py:143` | [ ] |
| 44 | `0x0068C4F4` | 8 | core | `` | [ ] |
| 45 | `0x006928B3` | 4 | core | `tools/build_windows_engine.py:137` | [ ] |
| 46 | `0x006928C3` | 4 | core | `tools/build_windows_engine.py:137` | [ ] |
| 47 | `0x0069405B` | 4 | core | `tools/build_windows_engine.py:142` | [ ] |
| 48 | `0x006940DC` | 4 | core | `tools/build_windows_engine.py:142` | [ ] |
| 49 | `0x006944A8` | 6 | core | `tools/build_area_fog_fix.py:42` | [ ] |
| 50 | `0x006944C4` | 6 | core | `tools/build_area_fog_fix.py:75` | [ ] |
| 51 | `0x006946F4` | 5 | core | `tools/build_windows_engine.py:182` | [ ] |
| 52 | `0x0069471A` | 13 | core | `tools/build_native_engine.py:62` | [ ] |
| 53 | `0x00694763` | 4 | core | `tools/build_windows_engine.py:140` | [ ] |
| 54 | `0x00694777` | 4 | core | `tools/build_native_engine.py:62` | [ ] |
| 55 | `0x00694A13` | 4 | core | `tools/build_windows_engine.py:141` | [ ] |
| 56 | `0x00694A39` | 5 | core | `tools/build_windows_engine.py:183` | [ ] |
| 57 | `0x00694A53` | 4 | core | `tools/build_native_engine.py:63` | [ ] |
| 58 | `0x00694AAC` | 5 | core | `tools/build_windows_engine.py:184` | [ ] |
| 59 | `0x00694AC4` | 4 | core | `tools/build_windows_engine.py:141` | [ ] |
| 60 | `0x00694AD0` | 5 | core | `tools/build_native_engine.py:63` | [ ] |
| 61 | `0x0069505C` | 12 | core | `tools/build_windows_engine.py:138` | [ ] |
| 62 | `0x00695082` | 12 | core | `tools/build_windows_engine.py:139` | [ ] |
| 63 | `0x006A74D2` | 48 | core | `tools/build_letterbox_scale_wrapper.py:56` | [ ] |
| 64 | `0x006A7560` | 50 | core | `tools/build_letterbox_scale_wrapper.py:62` | [ ] |
| 65 | `0x006A7943` | 41 | core | `tools/build_letterbox_scale_wrapper.py:68` | [ ] |
| 66 | `0x006A7B59` | 48 | core | `tools/build_letterbox_scale_wrapper.py:74` | [ ] |
| 67 | `0x006A7CD0` | 28 | core | `tools/build_letterbox_scale_wrapper.py:92` | [ ] |
| 68 | `0x006A7F3D` | 55 | core | `tools/build_letterbox_scale_wrapper.py:80` | [ ] |
| 69 | `0x006A8C4C` | 44 | core | `tools/build_letterbox_scale_wrapper.py:86` | [ ] |
| 70 | `0x006A8E1D` | 9 | core | `tools/build_letterbox_scale_wrapper.py:98` | [ ] |
| 71 | `0x006AB8EF` | 4 | core | `tools/build_windows_engine.py:147` | [ ] |
| 72 | `0x006ACB20` | 4 | core | `tools/build_windows_engine.py:147` | [ ] |
| 73 | `0x006B4FA9` | 4 | core | `tools/build_windows_engine.py:146` | [ ] |
| 74 | `0x006B527F` | 4 | core | `tools/build_windows_engine.py:146` | [ ] |
| 75 | `0x006B5332` | 36 | core | `tools/build_windows_engine.py:148` | [ ] |
| 76 | `0x006B55E3` | 4 | core | `tools/build_windows_engine.py:146` | [ ] |
| 77 | `0x006C265F` | 4 | core | `tools/build_windows_engine.py:146` | [ ] |
| 78 | `0x006C2704` | 49 | core | `tools/build_windows_engine.py:162` | [ ] |
| 79 | `0x006C2A23` | 4 | core | `tools/build_windows_engine.py:146` | [ ] |
| 80 | `0x006CD8D9` | 4 | core | `tools/build_windows_engine.py:147` | [ ] |
| 81 | `0x006CDB79` | 4 | core | `tools/build_windows_engine.py:147` | [ ] |
| 82 | `0x006DE012` | 4 | core | `tools/build_windows_engine.py:148` | [ ] |
| 83 | `0x006DE031` | 1 | core | `tools/build_windows_engine.py:151` | [ ] |
| 84 | `0x006DE08E` | 6 | core | `tools/build_windows_engine.py:153` | [ ] |
| 85 | `0x006DE0D1` | 13 | core | `tools/build_windows_engine.py:154` | [ ] |
| 86 | `0x0075477C` | 4 | core | `tools/build_windows_engine.py:186` | [ ] |
| 87 | `0x00755788` | 3 | core | `tools/build_technical_reconstruction_doc.py:522` | [ ] |

### 2.2 Resolution operands, written again at every mode change

| # | VA | size | kind | base |
| --- | --- | --- | --- | --- |
| 1 | `0x00403D6C` | 4 | 1 | 0 |
| 2 | `0x00403D78` | 4 | 2 | 0 |
| 3 | `0x00403EAD` | 4 | 1 | 0 |
| 4 | `0x00403EB9` | 4 | 2 | 0 |
| 5 | `0x0040AA65` | 4 | 1 | 0 |
| 6 | `0x0040AA85` | 4 | 2 | 0 |
| 7 | `0x0040B6C7` | 4 | 4 | 0 |
| 8 | `0x0040B6DA` | 4 | 5 | 0 |
| 9 | `0x0040BA6C` | 4 | 4 | 0 |
| 10 | `0x0040BA83` | 4 | 5 | 0 |
| 11 | `0x005F5B3B` | 4 | 1 | 0 |
| 12 | `0x005F5B43` | 4 | 2 | 0 |
| 13 | `0x0062540D` | 4 | 3 | 64 |
| 14 | `0x006256DC` | 4 | 3 | 800 |
| 15 | `0x006256E3` | 4 | 3 | 450 |
| 16 | `0x006256F6` | 4 | 3 | 800 |
| 17 | `0x006256FD` | 4 | 3 | 40 |
| 18 | `0x00625759` | 4 | 3 | 450 |
| 19 | `0x00626F95` | 4 | 3 | 64 |
| 20 | `0x006928B3` | 4 | 1 | 0 |
| 21 | `0x006928C3` | 4 | 2 | 0 |
| 22 | `0x0069405B` | 4 | 10 | 32 |
| 23 | `0x006940DC` | 4 | 10 | 16 |
| 24 | `0x0069471A` | 1 | 11 | -10 |
| 25 | `0x00694720` | 4 | 10 | 20 |
| 26 | `0x00694726` | 1 | 11 | -10 |
| 27 | `0x00694763` | 4 | 10 | 14 |
| 28 | `0x00694777` | 1 | 11 | -7 |
| 29 | `0x0069477A` | 1 | 11 | -7 |
| 30 | `0x00694A13` | 4 | 10 | 16 |
| 31 | `0x00694A53` | 1 | 11 | -8 |
| 32 | `0x00694A56` | 1 | 11 | -8 |
| 33 | `0x00694AC4` | 4 | 10 | 32 |
| 34 | `0x00694AD0` | 1 | 11 | -16 |
| 35 | `0x00694AD4` | 1 | 11 | -16 |
| 36 | `0x0069505C` | 4 | 6 | 0 |
| 37 | `0x00695064` | 4 | 8 | 0 |
| 38 | `0x00695082` | 4 | 7 | 0 |
| 39 | `0x0069508A` | 4 | 8 | 0 |
| 40 | `0x006AB8EF` | 4 | 3 | 50 |
| 41 | `0x006ACB20` | 4 | 3 | 50 |
| 42 | `0x006B4FA9` | 4 | 3 | 56 |
| 43 | `0x006B527F` | 4 | 3 | 56 |
| 44 | `0x006B5332` | 4 | 3 | 19 |
| 45 | `0x006B55E3` | 4 | 3 | 56 |
| 46 | `0x006C265F` | 4 | 3 | 56 |
| 47 | `0x006C2708` | 4 | 3 | 21 |
| 48 | `0x006C271D` | 4 | 3 | 19 |
| 49 | `0x006C2A23` | 4 | 3 | 56 |
| 50 | `0x006CD8D9` | 4 | 3 | 50 |
| 51 | `0x006CDB79` | 4 | 3 | 50 |
| 52 | `0x006DE012` | 4 | 3 | 25 |
| 53 | `0x006DE031` | 1 | 3 | 2 |
| 54 | `0x006DE0D3` | 4 | 3 | 30 |
| 55 | `0x006DE0D8` | 4 | 3 | 30 |
| 56 | `0x0086F004` | 4 | 9 | 0 |
| 57 | `0x00871003` | 4 | 3 | 21 |
| 58 | `0x00871009` | 4 | 3 | 21 |
| 59 | `0x00871020` | 4 | 3 | 37 |

## 3. Writes KMRP's modules make themselves at run time

| # | what | where in the game | done by | audit |
| --- | --- | --- | --- | --- |
| 1 | engine recipe: every byte run below, the block and its relocations | see section 2 | `src/controller-native/K1RuntimeEngine.cpp:114` | [ ] |
| 2 | resolution operands at each mode change (section 2.2) | see section 2.2 | `src/controller-native/K1RuntimeEngine.cpp:159` | [ ] |
| 3 | start size in the game's own resolution checks | 0x005F0FB2, 0x005F5B84 | `src/controller-native/K1RuntimeResolution.cpp:278` | [ ] |
| 4 | EnumDisplaySettingsA import slot, the display's modes filtered | 0x0073D3E4 | `src/controller-native/K1RuntimeResolution.cpp:112` | [ ] |
| 5 | CSWGuiInGameSkillEntry::SetExtent vtable slot (issue 80 icons) | 0x00755ED4 | `src/controller-native/K1RuntimeLayout.cpp:266` | [ ] |
| 6 | CSWGuiAbilityChain::SetExtent vtable slot (issue 80 icons) | 0x007578AC | `src/controller-native/K1RuntimeLayout.cpp:267` | [ ] |
| 7 | SwapBuffers import slot, the offscreen frame (issue 14) | the game's gdi32 SwapBuffers slot | `src/controller-native/K1OffscreenFrame.cpp:420` | [ ] |
| 8 | opengl32 hot patches: glCopyTexImage2D, glCopyTexSubImage2D, glReadPixels, wglGetProcAddress, wglMakeCurrent | opengl32.dll | `src/controller-native/K1OffscreenFrame.cpp:130` | [ ] |
| 9 | joystick deadzone float set to 0 (KMRP's radial deadzone instead) | K1_JOY_MIN_USEABLE | `src/controller-native/K1NativeJoystick.cpp:77` | [ ] |
| 10 | the game's cached hardware-mipmap answer set to 1 under K1DC | 0x0078E538 | `src/controller-native/K1CoreFrames.cpp:69` | [ ] |

## 4. The native modules' sources, largest first

Which module each file is built into is in `build_native_runtime.cmd` and `build_controller_standalone.cmd`.

| lines | file | in kmrp.dll | in kmrp-controller.dll | audit |
| --- | --- | --- | --- | --- |
| 8455 | `K1NativeJoystick.cpp` |  | yes | [ ] |
| 7455 | `vendor/K1XboxControls.cpp` |  | yes | [ ] |
| 2680 | `K1XboxHud.cpp` |  | yes | [ ] |
| 2007 | `K1RuntimeAssets.cpp` | yes |  | [ ] |
| 1780 | `K1ControllerLayout.cpp` |  | yes | [ ] |
| 1305 | `K1Rumble.cpp` |  | yes | [ ] |
| 973 | `K1TextLayout.cpp` | yes |  | [ ] |
| 962 | `K1HudOptions.cpp` | yes |  | [ ] |
| 944 | `K1RuntimeLayout.cpp` | yes |  | [ ] |
| 745 | `vendor/K1XboxControlsXInput.cpp` |  | yes | [ ] |
| 674 | `K1KpmApplier.cpp` |  |  | [ ] |
| 645 | `K1TextOptions.cpp` | yes |  | [ ] |
| 595 | `K1ControllerBackend.cpp` |  | yes | [ ] |
| 460 | `K1TextRows.cpp` | yes |  | [ ] |
| 422 | `K1OffscreenFrame.cpp` | yes |  | [ ] |
| 412 | `K1PartyRosterGui.cpp` | yes |  | [ ] |
| 403 | `K1ControllerStandalone.cpp` |  | yes | [ ] |
| 347 | `K1RuntimeResolution.cpp` | yes |  | [ ] |
| 290 | `K1CaptionInk.h` |  |  | [ ] |
| 262 | `K1OptionsPad.h` |  |  | [ ] |
| 255 | `K1RuntimeEngine.cpp` | yes |  | [ ] |
| 241 | `K1PcHud.cpp` | yes |  | [ ] |
| 217 | `K1KeyboardNavigation.cpp` | yes |  | [ ] |
| 190 | `K1MovieWindow.cpp` | yes | yes | [ ] |
| 187 | `K1ButtonRemapPolicy.h` |  |  | [ ] |
| 186 | `K1ClassModelTrace.h` |  |  | [ ] |
| 185 | `K1GrantedPopup.cpp` | yes |  | [ ] |
| 183 | `K1HudOptionsPolicy.h` |  |  | [ ] |
| 182 | `K1ControllerPreload.cpp` |  | yes | [ ] |
| 182 | `K1AssetPack.cpp` | yes |  | [ ] |
| 180 | `K1PcHudLayout.h` |  |  | [ ] |
| 168 | `K1PopupFit.cpp` | yes |  | [ ] |
| 154 | `K1ControllerBadgeShapes.inc` |  |  | [ ] |
| 148 | `K1Xpress.cpp` |  | yes | [ ] |
| 143 | `K1PartyRosterState.h` |  |  | [ ] |
| 130 | `KmrpOptions.h` |  |  | [ ] |
| 127 | `K1PcHudLayout.inc` |  |  | [ ] |
| 126 | `K1XboxHudLayout.inc` |  |  | [ ] |
| 122 | `K1CoreFrames.cpp` | yes |  | [ ] |
| 118 | `K1StatusSummary.cpp` | yes | yes | [ ] |
| 115 | `K1ClassSelectArt.h` |  |  | [ ] |
| 112 | `K1GuiModelPreload.h` |  |  | [ ] |
| 110 | `K1SliderGrip.h` |  |  | [ ] |
| 93 | `K1GuiControls.h` | yes |  | [ ] |
| 92 | `K1ListRows.inc` |  |  | [ ] |
| 88 | `K1TextFitPolicy.h` |  |  | [ ] |
| 86 | `K1ButtonRemap.cpp` |  | yes | [ ] |
| 83 | `K1CursorConfinement.cpp` | yes | yes | [ ] |
| 66 | `K1PartyPortraits.cpp` | yes | yes | [ ] |
| 65 | `K1EngineMemory.h` | yes |  | [ ] |
| 58 | `K1TextOptionsPolicy.h` |  |  | [ ] |
| 51 | `K1StatusSummary.h` |  |  | [ ] |
| 47 | `K1AssetPack.h` |  |  | [ ] |
| 38 | `K1MovieWindow.h` |  |  | [ ] |
| 35 | `K1NativeJoystick.h` |  |  | [ ] |
| 32 | `K1RuntimeAssets.h` |  |  | [ ] |
| 32 | `K1Rumble.h` |  |  | [ ] |
| 24 | `K1RuntimeResolution.h` |  |  | [ ] |
| 21 | `K1TextLayout.h` |  |  | [ ] |
| 17 | `K1HudOptions.h` |  |  | [ ] |
| 17 | `K1ControllerBackend.h` |  |  | [ ] |
| 17 | `K1ButtonRemap.h` |  |  | [ ] |
| 15 | `K1TextOptions.h` |  |  | [ ] |
| 15 | `K1CursorConfinement.h` |  |  | [ ] |
| 14 | `K1RuntimeLayout.h` |  |  | [ ] |
| 13 | `K1Xpress.h` |  |  | [ ] |
| 13 | `K1PartyRosterGui.h` |  |  | [ ] |
| 13 | `K1GuiPreloadData.h` |  |  | [ ] |
| 11 | `K1ControllerPreload.h` |  |  | [ ] |
| 10 | `K1TextRows.h` |  |  | [ ] |
| 6 | `K1RuntimeEngine.h` |  |  | [ ] |
| 3 | `K1ControllerLayout.h` |  |  | [ ] |

