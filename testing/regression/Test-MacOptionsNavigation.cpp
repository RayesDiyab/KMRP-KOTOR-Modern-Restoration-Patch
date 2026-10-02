// clang++ -std=c++17 macos/patches/kmrp-layout/navigation.cpp \
//   testing/regression/Test-MacOptionsNavigation.cpp -o /tmp/kmrp-options-test
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <initializer_list>
extern "C" void KmrpNoteArrowNavigation(void*, int, int);
extern "C" int KmrpNavigateListBoundary(void*, int, int);
extern "C" int KmrpKeepKeyboardFocus(void*, int, int);
struct alignas(8) Object { unsigned char data[0x400] = {}; };
template<class T> T& at(void* p, int offset) {
    return *reinterpret_cast<T*>(static_cast<unsigned char*>(p) + offset);
}
void* nav(void* p) { return p; }
void focus(void* panel, void* target, int) { at<void*>(panel, 0x28) = target; }
int main() {
    Object panel, manager, controls[7];
    void* array[7] = {};
    std::uintptr_t vtable[20] = {};
    vtable[0x98 / 8] = reinterpret_cast<std::uintptr_t>(&nav);
    // Arbitrary panel identity and control IDs: no per-menu route is available.
    at<std::uintptr_t>(&panel, 0) = 0x123456;
    at<void*>(&panel, 0x20) = &manager;
    at<void**>(&panel, 0x30) = array;
    at<int>(&panel, 0x38) = 7;
    for (int i = 0; i < 7; ++i) {
        array[i] = &controls[i];
        at<void*>(&controls[i], 0) = vtable;
        at<void*>(&controls[i], 0x50) = &panel;
        at<int>(&controls[i], 0x74) = i;
        at<unsigned char>(&controls[i], 0x68) = 0x0e;
        at<int>(&controls[i], 8) = 100;
        at<int>(&controls[i], 12) = i * 100;
        at<int>(&controls[i], 0x10) = 200;
        at<int>(&controls[i], 0x14) = 60;
        at<void*>(&controls[i], 0x58) = &controls[i];
        at<int>(&controls[i], 0x60) = 1;
        at<void*>(&controls[i], 0x90) = &controls[0];
        at<void*>(&controls[i], 0xa0) = &controls[1];
    }
    at<int>(&manager, 0) = 200;
    at<int>(&manager, 4) = 300;
    // Two live buttons form a valid small cycle but leave the footer and a
    // late-bound control unreachable. Raw ID 2 must never be dereferenced.
    for (int i = 0; i < 2; ++i) {
        at<void*>(&controls[i], 0x88) = &controls[1-i];
        at<void*>(&controls[i], 0x98) = &controls[1-i];
    }
    at<std::intptr_t>(&controls[2], 0x98) = 2;
    at<int>(&controls[3], 12) = 200; // footer on same row as 2, to its right
    at<int>(&controls[3], 8) = 500;
    at<unsigned char>(&controls[4], 0x68) |= 0x20; // disabled
    at<unsigned char>(&controls[5], 0x68) &= ~2; // hidden
    at<int>(&controls[6], 0x60) = 0; // passive description, no handlers
    KmrpNoteArrowNavigation(&controls[0], 0x3e, 1);
    assert(at<void*>(&controls[0], 0x98) == &controls[1]);
    assert(at<void*>(&controls[1], 0x98) == &controls[2]);
    assert(at<void*>(&controls[2], 0x98) == &controls[0]);
    assert(at<void*>(&controls[3], 0x98) == &controls[0]);
    assert(at<void*>(&controls[2], 0x88) == &controls[1]);
    assert(at<void*>(&controls[3], 0x88) == &controls[1]);
    for (int i : {2,3}) {
        assert(at<void*>(&controls[i], 0x90) == &controls[5-i]);
        assert(at<void*>(&controls[i], 0xa0) == &controls[5-i]);
    }
    assert(at<void*>(&controls[0], 0x90) == &controls[0]);
    assert(at<void*>(&controls[0], 0xa0) == &controls[1]);
    assert(KmrpKeepKeyboardFocus(&manager, 200, 300) == 1);
    assert(KmrpKeepKeyboardFocus(&manager, 201, 300) == 0);
    assert(KmrpKeepKeyboardFocus(&manager, 200, 300) == 0);
    // Native slider horizontal links survive even alongside another control.
    std::uintptr_t sliderTable[20];
    std::memcpy(sliderTable, vtable, sizeof sliderTable);
    sliderTable[0x80 / 8] = 0x1004a694cUL;
    at<void*>(&controls[3], 0) = sliderTable;
    at<void*>(&controls[3], 0x90) = &controls[0];
    at<void*>(&controls[3], 0xa0) = &controls[1];
    KmrpNoteArrowNavigation(&controls[2], 0x40, 1);
    assert(at<void*>(&controls[3], 0x90) == &controls[0]);
    assert(at<void*>(&controls[3], 0xa0) == &controls[1]);
    at<void*>(&controls[3], 0) = vtable;
    // A complete custom route survives despite a different geometric order.
    at<int>(&controls[3], 12) = 300;
    const int route[] = {0,2,1,3};
    for (int i = 0; i < 4; ++i) {
        at<void*>(&controls[route[i]], 0x98) = &controls[route[(i+1)%4]];
        at<void*>(&controls[route[i]], 0x88) = &controls[route[(i+3)%4]];
    }
    KmrpNoteArrowNavigation(&controls[0], 0x3e, 1);
    assert(at<void*>(&controls[0], 0x98) == &controls[2]);
    // Removing a runtime control reconnects the remaining graph safely.
    array[2] = nullptr;
    KmrpNoteArrowNavigation(&controls[0], 0x3e, 1);
    assert(at<void*>(&controls[1], 0x98) == &controls[3]);
    at<void*>(&manager, 0x18) = &controls[0];
    assert(KmrpKeepKeyboardFocus(&manager, 200, 300) == 0);
    // A native list consumes arrows itself; its edge must hand off to the
    // shared panel graph, and the footer must be able to return to the list.
    Object lp, lm, list, footer[2], entry;
    void* listControls[] = {&list, &footer[0], &footer[1]};
    void* entries[] = {&entry};
    std::uintptr_t panelTable[20] = {}, listTable[20];
    std::memcpy(listTable, vtable, sizeof listTable);
    listTable[0x80 / 8] = 0x1004a8a38UL;
    panelTable[0x18 / 8] = reinterpret_cast<std::uintptr_t>(&focus);
    at<void*>(&lp, 0) = panelTable;
    at<void*>(&lp, 0x20) = &lm;
    at<void*>(&lp, 0x28) = &list;
    at<void**>(&lp, 0x30) = listControls;
    at<int>(&lp, 0x38) = 3;
    for (int i = 0; i < 3; ++i) {
        void* c = listControls[i];
        at<void*>(c, 0) = i == 0 ? listTable : vtable;
        at<void*>(c, 0x50) = &lp;
        at<int>(c, 0x74) = i;
        at<unsigned char>(c, 0x68) = 0x0e;
        at<int>(c, 8) = i == 2 ? 400 : 100;
        at<int>(c, 12) = i == 0 ? 100 : 700;
        at<int>(c, 0x10) = 200;
        at<int>(c, 0x14) = 60;
        if (i) { at<void*>(c, 0x58) = c; at<int>(c, 0x60) = 1; }
    }
    at<void*>(&entry, 0) = vtable;
    at<unsigned char>(&entry, 0x68) = 0x0e;
    at<void**>(&list, 0x348) = entries;
    at<int>(&list, 0x350) = 1;
    at<short>(&list, 0x37a) = 0;
    assert(KmrpNavigateListBoundary(&list, 0x3e, 1) == 1);
    assert(at<void*>(&lp, 0x28) == &footer[0]);
    assert(at<void*>(&footer[0], 0x88) == &list);
    at<void*>(&lp, 0x28) = &list;
    void* twoEntries[] = {&entry, &entry};
    at<void**>(&list, 0x348) = twoEntries;
    at<int>(&list, 0x350) = 2;
    assert(KmrpNavigateListBoundary(&list, 0x3e, 1) == 0);
    assert(at<void*>(&lp, 0x28) == &list);
    assert(KmrpNavigateListBoundary(&list, 0x3d, 0) == 0);
    at<short>(&list, 0x37a) = 1;
    assert(KmrpNavigateListBoundary(&list, 0x3e, 1) == 1);
    // Side-by-side lists/buttons must also be reachable horizontally; their
    // interior vertical selection must still be left to the native list.
    at<int>(&footer[0], 12) = 100;
    at<int>(&footer[0], 8) = 400;
    at<void*>(&lp, 0x28) = &list;
    assert(KmrpNavigateListBoundary(&list, 0x40, 1) == 1);
    assert(at<void*>(&lp, 0x28) == &footer[0]);
    assert(at<void*>(&footer[0], 0x90) == &list);
    at<void*>(&lp, 0x28) = &list;
    assert(KmrpNavigateListBoundary(&list, 0x3d, 1) == 0);
    assert(at<void*>(&lp, 0x28) == &list);
    std::puts("PASS: disconnected and late-bound controls reachable; hidden/disabled/passive controls skipped; complete custom cycles preserved; footer uses Left/Right and rows use Up/Down; mouse handoff and native list boundary transfer work.");
}
