#include <cstdint>
#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <cstddef>
#include <initializer_list>
template<class T> T* FieldAt(void* p, std::size_t n) { return reinterpret_cast<T*>(static_cast<char*>(p) + n); }
constexpr auto K1_PAZAAK_GAME_DISPATCHER = 0x0067E8F0u;
constexpr std::size_t K1_PAZAAK_CARD_MODE = 0x86E4, K1_PAZAAK_HAND_CARDS = 0x2DE0, K1_PAZAAK_HAND_STRIDE = 0x31C;
constexpr std::size_t K1_PANEL_ACTIVE = 0x1C, K1_CTL_FLAGS = 0x44;
constexpr unsigned K1_CTL_FLAG_VISIBLE = 2, K1_CTL_FLAG_DISABLED = 0x20;
constexpr int K1_GUI_EVENT_CONFIRM = 0x27;
constexpr std::size_t K1_PAZAAK_FLIPS = 0x62BC, K1_PAZAAK_FLIP_STRIDE = 0x1C4;
constexpr std::size_t K1_PAZAAK_FLIP_ICON = 0x69CC, K1_PAZAAK_FLIP_LEGEND = 0x6B0C;
constexpr int K1_BADGE_LABEL_PARAMS = 0x70;
static unsigned char panel[0x8700], playButton[0x1D4], flipButton[0x1D4];
static int plays, flips, flashes, draws;
static bool controller, consumeCard;
static void* modal;
static float flashColour[3] = {1, 1, 1};
struct { void* panel; void* playButton; void* flipButton; void** mouseVtables[6]; int handSlot; } g_pazaakTable;
struct K1BadgeOverlay { void* label; };
static unsigned char badge[0x140];
static K1BadgeOverlay overlay{badge};
K1BadgeOverlay* FindK1BadgeOverlay(void*) { return &overlay; }
std::uintptr_t DispatcherOfK1(void*) { return K1_PAZAAK_GAME_DISPATCHER; }
bool IsReadableK1(void* p, std::size_t n) { return p == panel && n <= sizeof panel; }
bool IsControllerInputActiveK1() { return controller; }
void* TopPanelK1() { return modal ? modal : panel; }
using SetActiveControlFn = void(__thiscall*)(void*, void*, int);
void LogGuardK1(const char*, void*, int, int) {}
void __fastcall MockPlay(void* p, void*, void* card) {
    ++plays;
    if (consumeCard) { *FieldAt<int>(card, 0x304) = -1; *FieldAt<void*>(p, K1_PANEL_ACTIVE) = nullptr; }
}
void __fastcall MockFocus(void* p, void*, void* card, int) { *FieldAt<void*>(p, K1_PANEL_ACTIVE) = card; }
void __fastcall MockFlash(void* p, void*, const float* colour) {
    if ((p != playButton && p != flipButton) || colour != flashColour) std::abort();
    ++flashes;
}
void __fastcall MockFlip(void*, void*, void* card) { ++flips; *FieldAt<int>(card, 0x308) ^= 1; }
void __fastcall MockDraw(void*, void*, float) { ++draws; }
void __fastcall MockTextColor(void* params, void*, const float* color) {
    std::memcpy(static_cast<char*>(params) + 0x1C, color, 12);
}
void __fastcall MockSetEnabled(void* button, void*, int enabled) {
    auto& flags = *FieldAt<unsigned>(button, 0x44);
    flags = enabled ? flags | 8u : flags & ~8u;
    const float nativeCyan[3] = {0, enabled ? .66f : .33f, enabled ? .98f : .49f};
    std::memcpy(FieldAt<char>(button, 0x188), nativeCyan, 12);
}
void PazaakActionFlashK1(void*, bool);
void RememberPazaakHandSlotK1(void*, void*);
int PazaakHandSlotK1(void*, void*);
// PRODUCTION_HANDLERS
static void require(bool b, const char* msg) { if (!b) { std::puts(msg); std::exit(1); } }
int main() {
    g_pazaakTable.panel = panel; g_pazaakTable.playButton = playButton; g_pazaakTable.flipButton = flipButton;
    int cases = 0;
    for (int index = 0; index < 4; ++index) {
        void* card = panel + K1_PAZAAK_HAND_CARDS + index * K1_PAZAAK_HAND_STRIDE;
        *FieldAt<void*>(panel, K1_PANEL_ACTIVE) = card;
        *FieldAt<unsigned>(card, K1_CTL_FLAGS) = K1_CTL_FLAG_VISIBLE;
        for (int mode = 0; mode < 3; ++mode) for (int state = 0; state <= 10; ++state) for (int value = -2; value <= 28; ++value) {
            *FieldAt<int>(panel, K1_PAZAAK_CARD_MODE) = mode;
            *FieldAt<int>(panel, 0x86D4) = state;
            *FieldAt<int>(card, 0x304) = value;
            plays = flips = flashes = 0;
            PazaakPlayFocusedCardK1(panel);
            const bool canPlay = mode == 0 && state == 3 && value >= 0;
            require(PazaakHandActionEnabledK1(panel, false) == canPlay, "Play caption state mismatch");
            require(plays == int(canPlay) && flashes == int(canPlay), "Play accepted/flash mismatch");
            plays = flips = flashes = 0;
            // All small controls are invisible: the new flip must still work.
            *FieldAt<unsigned>(panel, K1_PAZAAK_FLIPS + index * K1_PAZAAK_FLIP_STRIDE + K1_CTL_FLAGS) = 0;
            PazaakFlipFocusedCardK1(panel);
            const bool canFlip = mode == 0 && value >= 12 && value < 18;
            require(PazaakHandActionEnabledK1(panel, true) == canFlip, "Flip caption state mismatch");
            require(flips == int(canFlip) && flashes == int(canFlip), "Flip accepted/flash mismatch");
            ++cases;
        }
        *FieldAt<int>(panel, K1_PAZAAK_CARD_MODE) = 0;
        *FieldAt<int>(card, 0x304) = 12;
        for (unsigned flags : {0u, K1_CTL_FLAG_VISIBLE | K1_CTL_FLAG_DISABLED}) {
            *FieldAt<unsigned>(card, K1_CTL_FLAGS) = flags;
            flips = flashes = 0; PazaakFlipFocusedCardK1(panel);
            require(flips == 0 && flashes == 0, "Invisible/blocked card flipped");
        }
        void* table[40] = {};
        table[0x38 / 4] = reinterpret_cast<void*>(&MockDraw);
        g_pazaakTable.mouseVtables[index] = table;
        void* small = panel + K1_PAZAAK_FLIPS + index * K1_PAZAAK_FLIP_STRIDE;
        controller = true; draws = 0; PazaakMouseOnlyDrawK1(small, nullptr, .016f);
        require(draws == 0, "Small flip drawn for controller");
        controller = false; PazaakMouseOnlyDrawK1(small, nullptr, .016f);
        require(draws == 1, "Small flip not drawn for mouse");
    }
    controller = true;
    *FieldAt<int>(panel, K1_PAZAAK_CARD_MODE) = 0;
    *FieldAt<int>(panel, 0x86D4) = 3;
    for (int i = 0; i < 4; ++i) {
        void* card = panel + K1_PAZAAK_HAND_CARDS + i * K1_PAZAAK_HAND_STRIDE;
        *FieldAt<unsigned>(card, K1_CTL_FLAGS) = 2;
        *FieldAt<int>(card, 0x304) = i == 0 ? 12 : 3;
    }
    g_pazaakTable.handSlot = 0;
    *FieldAt<void*>(panel, K1_PANEL_ACTIVE) = panel + 0x6C4C;
    EnsurePazaakHandFocusK1(panel);
    require(*FieldAt<void*>(panel, K1_PANEL_ACTIVE) == panel + K1_PAZAAK_HAND_CARDS, "Opening focus not first hand slot");
    require(PazaakHandActionEnabledK1(panel, false) && PazaakHandActionEnabledK1(panel, true), "Flippable card actions disabled");
    NavigatePazaakHandK1(panel, 1, 0);
    void* slot1 = panel + K1_PAZAAK_HAND_CARDS + K1_PAZAAK_HAND_STRIDE;
    require(*FieldAt<void*>(panel, K1_PANEL_ACTIVE) == slot1, "Right did not move one slot");
    require(PazaakHandActionEnabledK1(panel, false) && !PazaakHandActionEnabledK1(panel, true), "Nonflippable card actions wrong");
    consumeCard = true; PazaakPlayFocusedCardK1(panel); consumeCard = false;
    require(*FieldAt<void*>(panel, K1_PANEL_ACTIVE) == slot1, "Played slot focus lost");
    EnsurePazaakHandFocusK1(panel);
    require(!PazaakHandActionEnabledK1(panel, false) && !PazaakHandActionEnabledK1(panel, true), "Empty slot action enabled");
    NavigatePazaakHandK1(panel, -1, 0); NavigatePazaakHandK1(panel, 1, 0);
    require(*FieldAt<void*>(panel, K1_PANEL_ACTIVE) == slot1, "Empty hand slot skipped by navigation");
    NavigatePazaakHandK1(panel, 0, -1);
    require(*FieldAt<void*>(panel, K1_PANEL_ACTIVE) == slot1, "Up left hand row");
    modal = panel + 0x100;
    *FieldAt<void*>(panel, K1_PANEL_ACTIVE) = nullptr;
    EnsurePazaakHandFocusK1(panel);
    require(*FieldAt<void*>(panel, K1_PANEL_ACTIVE) == nullptr, "Focus moved while modal open");
    modal = nullptr; EnsurePazaakHandFocusK1(panel);
    require(*FieldAt<void*>(panel, K1_PANEL_ACTIVE) == slot1, "Modal return forgot slot");
    controller = false; *FieldAt<void*>(panel, K1_PANEL_ACTIVE) = nullptr;
    EnsurePazaakHandFocusK1(panel);
    require(*FieldAt<void*>(panel, K1_PANEL_ACTIVE) == nullptr, "Mouse focus changed");
    void* vtable[40] = {};
    vtable[0x88 / 4] = reinterpret_cast<void*>(&MockSetEnabled);
    vtable[0x38 / 4] = reinterpret_cast<void*>(&MockDraw);
    *FieldAt<void**>(flipButton, 0) = vtable;
    *FieldAt<void**>(playButton, 0) = vtable;
    *FieldAt<float>(playButton, 0x1C4) = .8f;
    SetPazaakActionEnabledK1(playButton, false);
    require(*FieldAt<float>(playButton, 0x1C4) == .8f, "Playing a card canceled its accepted press flash");
    for (float timer : {-1.0f, .8f, .4f, .01f}) {
        *FieldAt<float>(flipButton, 0x1C4) = timer;
        SetPazaakActionEnabledK1(flipButton, false);
        require((*FieldAt<unsigned>(flipButton, 0x44) & 8u) == 0, "Disabled flip remains selectable");
        require(*FieldAt<float>(flipButton, 0x1C4) < 0, "Old pulse can overwrite gray");
        for (int c = 0; c < 3; ++c) require(FieldAt<float>(flipButton, 0x188)[c] == .5f, "Caption not gray");
        KmrpPromptDimK1(flipButton, true);
        for (int c = 0; c < 3; ++c) require(FieldAt<float>(badge, 0x80)[c] == .4f, "Badge not dimmed");
        *FieldAt<float>(flipButton, 0x1C4) = .6f;
        SetPazaakActionEnabledK1(flipButton, true);
        require((*FieldAt<unsigned>(flipButton, 0x44) & 8u) != 0, "Enabled flip not selectable");
        require(*FieldAt<float>(flipButton, 0x1C4) == .6f, "Enabled press pulse canceled");
        KmrpPromptDimK1(flipButton, false);
        for (int c = 0; c < 3; ++c) require(FieldAt<float>(badge, 0x80)[c] == 1, "Badge did not recover");
    }
    for (int i = 4; i < 6; ++i) {
        g_pazaakTable.mouseVtables[i] = vtable;
        void* legend = panel + (i == 4 ? K1_PAZAAK_FLIP_ICON : K1_PAZAAK_FLIP_LEGEND);
        // Simulate RefreshDisplay restoring the visible flag after the frame update.
        *FieldAt<unsigned>(legend, 0x44) = 2;
        controller = true; draws = 0; PazaakMouseOnlyDrawK1(legend, nullptr, .016f);
        require(draws == 0, "PC flip legend painted over controller action");
        controller = false; PazaakMouseOnlyDrawK1(legend, nullptr, .016f);
        require(draws == 1, "Mouse legend drawing lost");
    }
    *FieldAt<void*>(panel, K1_PANEL_ACTIVE) = nullptr;
    flips = flashes = 0; PazaakFlipFocusedCardK1(panel);
    require(!flips && !flashes, "Missing focus flipped");
    std::printf("Pazaak production handlers: %d card/mode/turn cases; gray disabled captions, dim badges, pulse preservation and six mouse-only draws passed.\n", cases);
}
