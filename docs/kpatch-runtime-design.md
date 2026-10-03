# Self-contained KMRP and independent controller patches

**Design proposal, reviewed 2026-10-03; not an implemented runtime or release.**
This document follows the [documentation standard](documentation-standard.md).
It records the architecture selected after reviewing upstream discussions and
available source. Statements about future behavior are requirements, not test
results. The two requested packages have not been produced.

## Scope

The requested distribution is two independently usable Windows K1 patches:

| Package | Owns | Does not require |
| --- | --- | --- |
| KMRP | Widescreen menus/HUD/maps, fonts, keyboard/mouse fixes, memory fixes, movies and map-note corrections | Controller patch, a prior KMRP installation, resolution-specific Override files |
| KMRP Controller | Controller input, navigation, prompts, layout/settings screen and rumble | KMRP widescreen/layout/engine fixes |

Both must work together. Controller alone must work with the game's original
layout and must not silently activate KMRP's widescreen engine. Core alone must
contain no controller entry, prompts, polling or controller input interception.
Existing installer outputs remain supported until the new path is verified.

## Evidence and corrections

Reviewed upstream master `de1b3922d203f93b1a7418bb90130301354e7171`, the
repository's pinned KPM checkout `2a784bf92a21dbc179ef17cbd89a07d694bc768d`,
and author prototype branch `ethansm/local-mods` at
`e3bc575d7f185540aeed6638b2c1a1965898f4b8`. These are source inspections,
not our own gameplay verification. GitHub Discussions is disabled on the
upstream repository; the relevant discussions are issue comments and PRs.

| Source | Established by inspection | Consequence for KMRP |
| --- | --- | --- |
| [GUI framework #104](https://github.com/LaneDibello/Kotor-Patch-Manager/issues/104), including all five comments | Native construction, layout loading, control binding, event registration and final state are separate stages. List contents/prototypes and screen-specific state remain hardcoded. | Hook measured lifecycle stages; geometry alone is insufficient. |
| [GUI proof of concept #114](https://github.com/LaneDibello/Kotor-Patch-Manager/pull/114) | Merged GameAPI/list-box support exists; bespoke GUI creation does not depend on the new hotbar RFC. | Reuse existing native wrappers rather than build a second general GUI engine. |
| [Hotbar RFC #295](https://github.com/LaneDibello/Kotor-Patch-Manager/issues/295) | Reports DLL-embedded art and native runtime controls for K2, and proposed shared `GuiKit.h`. No issue comments or linked implementation PR at review time. | A useful pattern, not a ready K1 implementation. |
| [Published hotbar source](https://github.com/ethansm/Kotor-Patch-Manager/blob/e3bc575d7f185540aeed6638b2c1a1965898f4b8/Patches/ForcePowerHotbar/ForcePowerHotbar.cpp) and [hook table](https://github.com/ethansm/Kotor-Patch-Manager/blob/e3bc575d7f185540aeed6638b2c1a1965898f4b8/Patches/ForcePowerHotbar/kotor2-steam-aspyr.hooks.toml) | This snapshot creates 57 labels from native templates before `StopLoadFromLayout`, appends them to the panel list, embeds TGA art, and refills textures after engine reset. Old HUD labels are deliberately retained; it intercepts DirectInput records and subclasses WndProc for the picker wheel. | Correction: the RFC's 67-control count, shared helper and WndProc description cannot be treated as the exact available implementation. Do not copy its ownership leaks or assume WndProc handles all native input. |
| [Patch communication #180](https://github.com/LaneDibello/Kotor-Patch-Manager/issues/180), including the prototype comment | Proposes an optional `KPatchInit`, versioned plain-C services, caller-owned memory and lazy lookup. Neither inspected upstream master nor the pinned runtime contains this API. | Design for it, but do not silently require an unmerged service. Avoid permanent negative caching and load-order dependencies. |
| [Widescreen #19](https://github.com/LaneDibello/Kotor-Patch-Manager/issues/19), all twelve comments | Resolution validation, GUI extents, mouse transforms, movie mode switches, refresh rates and dark-side ending credits are distinct concerns. Fullscreen mode selection comes from OS-supported modes. | Populate Graphics from valid hardware modes; remove fixed GUI-layout restrictions, not hardware validation. Cover the ending credits as well as ordinary movies. |
| [Resource research #47](https://github.com/LaneDibello/Kotor-Patch-Manager/issues/47), all nine returned comments | Resource priority/ownership spans directories, ERFs, RIMs and fixed tables; texture resolution crosses these paths. Some observations are explicitly tentative. | Do not replace global resource lookup just to avoid loose files. Preserve other mods' resource precedence. |
| [Inline detours #270](https://github.com/LaneDibello/Kotor-Patch-Manager/issues/270) | Existing KPM detours do not provide arbitrary function wrapping with a callable original. Relative displaced instructions and cleanup need explicit treatment. | Prefer declared, measured KPM hook sites; do not hide undeclared hooks or assume trampoline relocation works. |
| [Runtime 3D UI #298](https://github.com/LaneDibello/Kotor-Patch-Manager/issues/298), [effects UI #300](https://github.com/LaneDibello/Kotor-Patch-Manager/issues/300), [portrait UI #299](https://github.com/LaneDibello/Kotor-Patch-Manager/issues/299) | Report control ID coordination, graphics-state preservation, texture/model lifetime and limited directly tested aspect ratios. | Runtime creation alone proves neither broad resolution support nor compatibility. |
| [Widescreen PR #296](https://github.com/LaneDibello/Kotor-Patch-Manager/pull/296) | Open, unmerged at review time; changes the Mac widescreen implementation's two modes. Current upstream widescreen manifest supports K1 macOS only. | Do not treat its architecture or offsets as shipping Windows support. |

Earlier implementation direction considered replacing complete GUI resources
from an embedded resolution bank. Rejected as the primary architecture: it
removes filesystem conflicts but still replaces another mod's effective GUI,
retains cache/lifetime complexity, and does not update existing live controls.
An initial in-memory blend experiment was moved out of shipping source into
ignored research output. It did not link successfully on Windows and is not a
tested runtime component.

## Recommended architecture

Use a hybrid native approach. Let the game load its normal resources, then
modify existing controls through measured K1 lifecycle hooks. Create only KMRP's
additional controls at runtime. Embed KMRP-owned art, font assets and compact
layout rules inside each package's module. This follows the useful native-control
pattern without importing an entire K2 hotbar or replacing every GUI resource.

Retain the existing authoritative geometry rules and font-fit calculations.
Compile those rules/data for native use; do not infer a new layout from a single
1920x1200 sample. Reuse the current blend arithmetic where it is useful as layout
data, rather than exposing its generated GFF as a replacement for the original
resource. Preserve `max(1.0, height / 720)` and use the game's actual font
metadata, wrapping and drawing bounds. Apply metadata before text centering.
Both the ideal-height calculation and companion font-height getter must agree
on upward rounding; the earlier Mac one-sided fix caused a dialog loop.

Read an immutable baseline for each panel/control generation. Compute a fresh
layout from that baseline whenever effective resolution changes; never scale an
already scaled extent. Call native layout methods where they update child
geometry, list prototypes or hitboxes. Observe later native layout writes so
they cannot overwrite the result, as happened with the first Mac clipping fix.
Explicitly preserve foreign controls and avoid scaling controls injected by
the controller patch twice. Track ownership by actual instance/generation,
not a fixed reserved ID assumed free in every mod combination.

New controls need explicit construction, panel registration, event/focus setup,
visibility/hit-testing and destruction. Register embedded artwork through the
native texture path with engine-compatible allocation and reference ownership.
Recreate image data after resolution/graphics resets and unregister or retain
only deliberately bounded process-lifetime caches. Never leave stale panel,
font or texture pointers after a GUI reconstruction. Shared image ownership
must be resolved before invoking native destructors.

## In-game resolution changes

The player's entry point remains **Options -> Graphics -> Resolution**.
Enumerate the monitor/driver's supported width, height and refresh-rate tuples;
deduplicate deliberately and keep mode validation. Fullscreen must not offer
unsupported modes simply because KMRP can calculate their geometry. Arbitrary
window sizes are a separate path bounded by native field sizes and minimum
usable layout, not by the build's list of 66 resource sets.

Preserve native confirm/revert behavior. After a successful mode change, obtain
the actual active dimensions, invalidate affected font/texture generations and
re-layout/rebuild panels at a safe game-thread boundary. Reversion goes through
the same path. Preserve the selected mode in the game's normal settings only
when appropriate. Test both acceptance and timeout/cancellation, rather than
only startup at a new INI size. Alt-Tab, window resize and movie transitions
must follow the same dimension-change contract.

This is the full migration requirement. A subsequent experimental first slice
preserves the native constructor and callback and broadens the GUI validator;
its limited live results and rejected first attempt are recorded in the
[runtime resolution experiment](../reverse-engineering/runtime-resolution-preview.md).
It does not yet implement the layout/font change transaction.

## Independent packages and upstream boundaries

Compile separate modules with explicit ownership. Do not reuse the current
all-features module with only a different manifest: its core supplies GUI/movie
frame dispatch and its controller still depends on installed prompt resources
and an adjacent SDL DLL. Merely deleting `requires = ["kmrp"]` is incorrect.

Controller must supply its own startup/frame lifecycle and native prompt/control
creation against the original GUI. Prefer a statically linked, pinned SDL build
with its license in the controller package to remove the adjacent-DLL dependency;
prove that build before selecting it. KPM's inspected `ExtractPatchDll` extracts
only the selected platform module, so an extra SDL archive member is insufficient.

Build common helpers into both modules where harmless, using source under an
upstream-appropriate `Patches/Common`/GameAPI boundary. Runtime hook ownership
must remain unique when both are installed. Optional cooperation uses a versioned
plain-C interface with documented lifetimes/threading and lookup after module
loading; there is no mandatory third patch. Prefer KPM's service API when it
actually exists. Until then, any compatibility bridge must be explicit and
verified, not a private global hook chain which KPM cannot inspect.

Keep native keyboard/mouse routing and controller routing distinct. A controller
overlay consumes only events it handles while active, and hiding it also removes
its hit targets. Do not apply the hotbar's WndProc approach wholesale to K1's
DirectInput/menu paths. Existing keyboard focus/tab repairs remain core behavior.

Shared native APIs, lifecycle helpers, resolution support and hook improvements
should be suitable for upstream KPM; KMRP-specific layout/art/engine choices
remain in the KMRP package. No PR, remote comment, commit or push was made during
this research. Publication needs its separately scoped authorization.

## Verification gates before claiming completion

1. Core alone, controller alone, both together, neither; both package load orders.
   Start from a clean game fixture with no installed KMRP Override or data files.
2. Differential geometry checks against the current generated layouts and
   `GuiBlend` at representative sizes, including sizes absent from the catalog.
   Record explicit native limits and unsupported cases.
3. Live Windows reproduction of both clipping cases at 1920x1200 using native
   font metrics, wrapped lines and final draw bounds; verify both height getters.
   The archived 38px/82px action-label measurements are not a live result.
4. Physical keyboard arrows/Tab/Enter/Esc, mouse targeting and controller
   navigation independently, including input-device switches and hidden overlays.
5. 1280x720, 1920x1200, 2560x1440, 3440x1440 and a 32:9 size where hardware permits;
   include custom windowed dimensions. Test mode accept/revert repeatedly,
   scene/menu changes, repeated HUD reconstruction, Alt-Tab and graphics resets.
6. Movies, input restoration, ending credits, map centering/markers, list row
   population, status summary and translated/long text; check texture and control
   allocations remain bounded across repetitions.
7. Exact byte guards, declared hook overlaps, source-built binary inventories,
   artifact round-trip checks, appropriate existing regressions and documentation
   links. Keep proprietary build inputs and generated resources out of Git.

The architecture review itself established no new live Windows behavior.
**Status update, 2026-10-03:** an independent no-controller preview package now
builds and has limited native resolution-switch measurements in an isolated CD
1.03 fixture. It is not complete standalone KMRP. Native panel/font/texture
migration, controller independence, general mode-change compatibility and the
verification gates above remain unfinished. See the linked experiment before
using any preview result as evidence.
