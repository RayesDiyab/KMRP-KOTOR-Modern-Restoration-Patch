/*
  KMRP for macOS, controller support: swoop racing and the gun turret (issue #47; handoff item 53).

  The Mac port of NativeMiniGameAxisK1 and UpdateSwoopPromptK1 in
  src/controller-native/K1NativeJoystick.cpp, which say why each thing is done;
  docs/controller-native-path.md, "Swoop racing and the turret". Neither game is a GUI screen.
  CSWMiniGame (the area's, at CSWCArea +0x310; Windows +0x264) is driven from
  CClientExoAppInternal::ProcessInput (0x1002F8226; Windows 0x006227E0) while there is no player
  creature, by polling keymap actions, not by events of the pad's:

      swoop  (type 1, [game+0xB0]; Windows +0x80)   x = action 0x11B + 0x11E, held to -1..1
      turret (type 2)                               x the same, z = action 0x11A and 0x11D

  then CSWMiniGame::UpdateAxis(seconds in xmm0, game, vector) (0x1002E31F2) and Control
  (0x1002E33C4). Right is the positive direction of x, as played on Windows.

  The Mac has three calls of UpdateAxis, Windows two: Aspyr added one for the turret (through
  0x1002E32B6, called at 0x1002F977E) with its own stick layer's values, which KMRP's pad does not feed, ahead
  of the keys' call. So the hooks are not at UpdateAxis's entry as on Windows, where a stick would
  count twice, but on the two calls the keys' vectors go to, each after its vector is made:

      0x1002F98DD  the turret's: rdi the game, r12 the vector
      0x1002F9ADE  the swoop's:  r14 the game, rsi the vector

  The stick is added to what the keys gave, so both work together. A fires once for each press,
  as a key does: held, it would change gear every frame, which the race punishes. In the turret
  either trigger fires too; in a race the triggers do nothing, and each fire input keeps its own
  held bit, so a new pull fires while another stays held. Nothing fires while the game is paused,
  as the router's own MGshoot (event 0xD9) has it: [game+0x38] is the player (Windows +0x24), and
  CSWMiniPlayer::Fire (0x1002F471C; Windows 0x0066DC50) takes it in rdi and returns plainly, which
  is what the router does at 0x1002FA1C0. Start pauses and continues: the game's own action for
  it, PauseMinigame (0xFD), asked of the router as Windows does.

  The shift prompt (the "Also" of item 53). The race's HUD model, m17mg_camera, shows the Space
  picture on its part Plane14 in a texture named abutton. While the pad is in use and a race runs,
  the part's material wears the pad's A in that texture's place (kmrp?_swoop, which
  tools/build_controller_assets.py makes and the controller bank carries), and the game's own
  while it does not. Resolved afresh every frame, from the race itself, so an unloaded or rebuilt
  model leaves no stale pointer here: the only objects kept are texture references, held through
  the engine's own tracked assignment.

    - the player's attached models: CExoArrayList at +0x90 of 16-byte entries, the Gob first
      (CSWTrackFollower::AddModel, 0x1002F1CB0; Windows +0x68, 8 bytes);
    - a Gob's model at +0x68, whose name is at +0x10 (Gob::GetModelName, 0x1001DC72E);
    - Gob::GetPart (0x1001D87CA) with the part's name;
    - a part's mesh from its vtable's +0x68, and the mesh's material at +0x58, as
      Global::PartInitMaterial (0x1001DB70C) reads them;
    - a material's first word is its texture reference (Material::BindTexture0, 0x10019450E), an
      object of vtable 0x1005A3DD0 with the texture at +0x18 (0x1001F9C99 makes it, and
      CAurTexture::GetReferencedTexture, 0x1001F6866, reads it), whose name is at +0x9C
      (0x1001F73FE).
    - 0x1001F9FF4 is the reference to a texture by name and 0x100194F60 the tracked assignment,
      which Material's own loading uses (0x1001942DE). 0x1001F6CE4 says a reference is the engine's
      null texture, the Mac's test for what Windows' K1_TEXTURE_REF_ID tests.

  Windows draws the glyph at run time; the Mac carries the texture (handoff item 101).

  All of it was read from the Mac executable on 2026-11-03. Compiled, not played: no save at hand
  reaches a race or the turret. Which way the turret's vertical axis runs was not measured on
  Windows either: down is taken for positive, as right is.
*/
#include "../kmrp-layout/text.h"
#include "engine.h"
#include "pad.h"
#include "prompts.h"
#include "state.h"

#include <cstdint>
#include <cstring>
#include <strings.h>

namespace kmrp {

float g_leftTrigger = 0.0f, g_rightTrigger = 0.0f;
std::uint32_t g_padSeen = 0;

namespace minigame {
namespace {

using engine::At;
using text::LooksLikePointer;
using text::Readable;

const std::size_t kGameType = 0xb0, kGamePlayer = 0x38;
const int kSwoop = 1, kTurret = 2;
const int kEventPauseMiniGame = 0xfd;

const auto Fire = reinterpret_cast<void (*)(void* player)>(0x1002f471cUL);
const auto PausedByCombat = reinterpret_cast<int (*)(void* internal)>(0x10026b4f4UL);

const std::size_t kPlayerModels = 0x90, kPlayerModelCount = 0x98, kModelEntry = 0x10;
const std::size_t kGobModel = 0x68, kModelName = 0x10;
const std::size_t kVtPartMesh = 0x68, kMeshMaterial = 0x58;
const std::uintptr_t kTextureRefVtable = 0x1005a3dd0UL;
const std::size_t kRefTexture = 0x18, kTextureName = 0x9c, kTextureSize = 0x110;
const auto GetPart = reinterpret_cast<void* (*)(void* gob, const char* name)>(0x1001d87caUL);
const auto TextureByName = reinterpret_cast<void* (*)(const char* name, void*)>(0x1001f9ff4UL);
const auto AssignTexture = reinterpret_cast<void* (*)(void** slot, void* reference)>(0x100194f60UL);
const auto IsNullTexture = reinterpret_cast<bool (*)(void* reference)>(0x1001f6ce4UL);

std::uint8_t g_fireHeld = 0;
bool g_startHeld = false;

float HeldToUnit(float value) { return value < -1.0f ? -1.0f : value > 1.0f ? 1.0f : value; }

const char* TextureName(void* reference) {
    if (!Readable(reference, 0x28) || At<std::uintptr_t>(reference, 0) != kTextureRefVtable) return nullptr;
    void* const texture = At<void*>(reference, kRefTexture);
    return Readable(texture, kTextureSize) ? &At<char>(texture, kTextureName) : nullptr;
}

void** PromptMaterial(void* game) {
    void* const player = At<void*>(game, kGamePlayer);
    if (!Readable(player, kPlayerModelCount + sizeof(int))) return nullptr;
    const int count = At<int>(player, kPlayerModelCount);
    char* const models = At<char*>(player, kPlayerModels);
    // The game's tracks have four or five attachments. Modded race lists are allowed; a count
    // that cannot be real is refused before its extent is worked out.
    if (count <= 0 || count > 64 || !Readable(models, count * kModelEntry)) return nullptr;
    for (int i = 0; i < count; ++i) {
        void* const gob = At<void*>(models, i * kModelEntry);
        if (!Readable(gob, kGobModel + sizeof(void*))) continue;
        char* const model = At<char*>(gob, kGobModel);
        if (!Readable(model, kModelName + 16) || strncasecmp(model + kModelName, "m17mg_camera", 16) != 0) continue;
        void* const part = GetPart(gob, "Plane14");
        const std::uintptr_t vtable = Readable(part, sizeof(void*)) ? At<std::uintptr_t>(part, 0) : 0;
        if (!LooksLikePointer(reinterpret_cast<void*>(vtable))) return nullptr;
        void* const mesh = reinterpret_cast<void* (*)(void*)>(*reinterpret_cast<std::uintptr_t*>(vtable + kVtPartMesh))(part);
        if (!Readable(mesh, kMeshMaterial + sizeof(void*))) return nullptr;
        void** const material = At<void**>(mesh, kMeshMaterial);
        return Readable(material, sizeof(void*)) ? material : nullptr;
    }
    return nullptr;
}

void UpdateSwoopPrompt(void* game) {
    static void* original = nullptr;
    static void* glyphs[4] = {};
    void** const material = PromptMaterial(game);
    if (!material) return;
    void* const current = *material;
    bool known = current != nullptr && current == original;
    for (void* glyph : glyphs) known |= glyph != nullptr && current == glyph;
    if (!known) {
        const char* const name = TextureName(current);
        if (!name || strncasecmp(name, "abutton", 8) != 0) return;
        AssignTexture(&original, current);
    }
    const bool usePad = engine::CurrentInputClass() == engine::kClassMiniGame && device::PadInUse();
    const char letter = prompts::FamilyLetter();
    const char* const letters = "psnd";
    const char* const found = std::strchr(letters, letter);
    const int family = found ? static_cast<int>(found - letters) : 0;
    void* wanted = usePad ? glyphs[family] : original;
    // No texture demand or reference assignment while the selected cue is set.
    if (wanted && current == wanted) return;
    if (usePad) {
        if (!glyphs[family]) {
            char name[17] = "kmrpp_swoop";
            name[3] = letters[family];
            if (void* const loaded = TextureByName(name, nullptr)) AssignTexture(&glyphs[family], loaded);
        }
        wanted = glyphs[family] && !IsNullTexture(glyphs[family]) ? glyphs[family] : original;
    }
    if (wanted && wanted != current) AssignTexture(material, wanted);
}

}  // namespace

}  // namespace minigame
}  // namespace kmrp

// ProcessInput, ahead of its two calls of UpdateAxis with the keys' vectors (above). Once a frame
// for either kind of game. A plain return leaves the vector as the keys made it.
extern "C" __attribute__((visibility("default"))) void KmrpMiniGameAxis(void* game, float* vector) {
    using namespace kmrp;
    using namespace kmrp::minigame;
    if (!Readable(game, kGameType + sizeof(int))) return;
    const int type = At<int>(game, kGameType);
    if (type != kSwoop && type != kTurret) return;

    if (type == kSwoop) UpdateSwoopPrompt(game);

    void* const internal = engine::ClientInternal();
    // The buffer's word, not the raw pad: a Start or A that skipped a movie and is still held must
    // not pause or fire as the game starts (audit PAD-9; Windows reads its filtered lastButtons).
    const bool start = (g_padSeen & kPadStart) != 0;
    if (start && !g_startHeld && internal) engine::HandleInputEvent()(internal, kEventPauseMiniGame, 1);
    g_startHeld = start;

    // A, LT and RT tracked apart: a new pull must still fire while another input stays held.
    // Simultaneous presses ask for one fire this frame.
    const std::uint8_t held = static_cast<std::uint8_t>(
        ((g_padSeen & kPadA) ? 1u : 0u) |
        (type == kTurret ? (((g_padSeen & kPadLT) ? 2u : 0u) | ((g_padSeen & kPadRT) ? 4u : 0u)) : 0u));
    const bool pressed = (held & ~g_fireHeld) != 0;
    if (pressed && internal && PausedByCombat(internal) == 0) {
        void* const player = At<void*>(game, kGamePlayer);
        if (LooksLikePointer(player)) Fire(player);
    }
    g_fireHeld = held;

    // The stick as the buffer has it (native.cpp): right and down positive, a radial deadzone, and
    // what is left rescaled over the whole range.
    if (!Readable(vector, 3 * sizeof(float))) return;
    vector[0] = HeldToUnit(vector[0] + g_leftX);       // right is positive: played on Windows
    if (type == kTurret) vector[2] = HeldToUnit(vector[2] + g_leftY);   // not measured
}
