#include <cstdint>
#include <cstdio>
#include <initializer_list>
struct Stick { unsigned lastButtons; unsigned lastTriggers; } g_stick;
std::uint8_t g_miniGameFireHeld;
int calls;
int paused;
char fakePlayer;
void __fastcall Fire(void*, void*) { ++calls; }
int __fastcall Paused(void*, void*) { return paused; }
const std::uintptr_t K1_MINIPLAYER_FIRE = reinterpret_cast<std::uintptr_t>(&Fire);
const std::uintptr_t K1_PAUSED_BY_COMBAT = reinterpret_cast<std::uintptr_t>(&Paused);
constexpr unsigned K1_MINIGAME_PLAYER = 0x24;
template<typename T> T* FieldAt(void* p, unsigned offset) { return reinterpret_cast<T*>(static_cast<char*>(p) + offset); }
bool LooksLikePointerK1(void* p) { return p != nullptr; }
void Tick(int type, void* internal, void* game) {
    // KMRP_PRODUCTION_FIRE_BLOCK
}
int main() {
    alignas(void*) char game[0x90] = {};
    *FieldAt<void*>(game, K1_MINIGAME_PLAYER) = &fakePlayer;
    unsigned cases = 0;
    for (int type : {1, 2})
    for (unsigned before = 0; before < 8; ++before)
    for (unsigned after = 0; after < 8; ++after)
    for (int blocked = 0; blocked < 2; ++blocked)
    for (int connected = 0; connected < 2; ++connected) {
        g_miniGameFireHeld = static_cast<std::uint8_t>(before);
        g_stick.lastButtons = (after & 1) ? 0x1000 : 0;
        g_stick.lastTriggers = after >> 1;
        calls = 0;
        paused = blocked;
        Tick(type, connected ? &fakePlayer : nullptr, game);
        const bool newA = (after & 1) && !(before & 1);
        const bool newLT = (after & 2) && !(before & 2);
        const bool newRT = (after & 4) && !(before & 4);
        const int expected = !blocked && connected && (newA || (type == 2 && (newLT || newRT)));
        if (calls != expected || g_miniGameFireHeld != (type == 2 ? after : after & 1)) {
            std::printf("FAIL type=%d before=%u after=%u paused=%d connected=%d calls=%d expected=%d\n", type, before, after, blocked, connected, calls, expected);
            return 1;
        }
        ++cases;
    }
    std::printf("PASS: %u production fire-block transitions (A/LT/RT overlap, holds, simultaneous presses, swoop, pause and missing client).\n", cases);
}
