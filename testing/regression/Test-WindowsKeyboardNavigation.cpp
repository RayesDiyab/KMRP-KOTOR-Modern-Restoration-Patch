// Compile x86 with /DKMRP_KEYBOARD_TEST and K1KeyboardNavigation.cpp.
// Synthetic Windows object layouts exercise traversal and input independence.
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <initializer_list>
extern "C" int __cdecl KeyboardNavigateK1(void*, int*, int*);
extern "C" int __cdecl KeyboardListBoundaryK1(void*, int*, int*);
extern "C" int __cdecl KeyboardKeepFocusK1(void*, int, int);
struct Object { unsigned char data[0x400] = {}; };
template<class T> T& at(void* p, unsigned offset) {
    return *reinterpret_cast<T*>(static_cast<char*>(p) + offset);
}
void* __fastcall nav(void* p, void*) { return p; }
void __fastcall focus(void* panel, void*, void* target, int) { at<void*>(panel, 0x1C) = target; }
int move(void* control, int event, bool list = false, int value = 1) {
    return list ? KeyboardListBoundaryK1(control, &event, &value)
                : KeyboardNavigateK1(control, &event, &value);
}
void run(int height) {
    Object panel, manager, controls[7], rows[3];
    void* array[7] = {}, *panels[] = {&panel};
    std::uintptr_t table[24] = {}, panelTable[24] = {}, sliderTable[24] = {}, listTable[24] = {};
    table[0x4C / 4] = reinterpret_cast<std::uintptr_t>(&nav);
    panelTable[0x08 / 4] = reinterpret_cast<std::uintptr_t>(&focus);
    std::memcpy(sliderTable, table, sizeof table);
    std::memcpy(listTable, table, sizeof table);
    sliderTable[0x3C / 4] = 0x0041ADF0;
    listTable[0x3C / 4] = 0x0041CE20;
    at<void*>(&panel, 0) = panelTable;
    at<void*>(&panel, 0x18) = &manager;
    at<void**>(&panel, 0x20) = array;
    at<int>(&panel, 0x24) = 7;
    at<void**>(&manager, 0x88) = panels;
    at<int>(&manager, 0x8C) = 1;
    at<int>(&manager, 0) = 123; at<int>(&manager, 4) = 456;
    for (int i = 0; i < 7; ++i) {
        array[i] = &controls[i];
        at<void*>(&controls[i], 0) = table;
        at<void*>(&controls[i], 0x34) = &panel;
        at<int>(&controls[i], 0x50) = i;
        at<unsigned char>(&controls[i], 0x44) = 0x0E;
        at<int>(&controls[i], 4) = height / 5;
        at<int>(&controls[i], 8) = i * height / 10;
        at<int>(&controls[i], 0x0C) = height / 3;
        at<int>(&controls[i], 0x10) = height / 12;
        at<void*>(&controls[i], 0x38) = &controls[i];
        at<int>(&controls[i], 0x3C) = 1;
        at<void*>(&controls[i], 0x5C) = &controls[1-i%2];
        at<void*>(&controls[i], 0x64) = &controls[1-i%2];
    }
    at<std::uintptr_t>(&controls[2], 0x64) = 2; // unresolved ID, never followed
    at<int>(&controls[3], 8) = at<int>(&controls[2], 8);
    at<int>(&controls[3], 4) = height * 3 / 5;
    at<unsigned char>(&controls[4], 0x44) |= 0x20;
    at<unsigned char>(&controls[5], 0x44) &= ~2;
    at<int>(&controls[6], 0x3C) = 0; // passive description
    unsigned char links[7][16];
    for (int i = 0; i < 7; ++i) std::memcpy(links[i], controls[i].data + 0x5C, 16);
    at<void*>(&panel, 0x1C) = &controls[0];
    int event = 0x3E, value = 1;
    assert(KeyboardNavigateK1(&controls[0], &event, &value) == 1 && event == 0x41);
    assert(at<void*>(&panel, 0x1C) == &controls[1]);
    assert(move(&controls[1], 0x3E) == 1);
    assert(at<void*>(&panel, 0x1C) == &controls[2]);
    assert(move(&controls[2], 0x40) == 1);
    assert(at<void*>(&panel, 0x1C) == &controls[3]);
    assert(move(&controls[3], 0x3D) == 1);
    assert(at<void*>(&panel, 0x1C) == &controls[1]);
    assert(KeyboardKeepFocusK1(&manager, 123, 456) == 1);
    assert(KeyboardKeepFocusK1(&manager, 124, 456) == 0);
    assert(KeyboardKeepFocusK1(&manager, 123, 456) == 0);
    for (int i = 0; i < 7; ++i) assert(std::memcmp(links[i], controls[i].data + 0x5C, 16) == 0);
    // Controller directions and releases cannot enter the keyboard repair.
    for (int e : {0x2F, 0x30, 0x31, 0x32, 0x3B, 0x3C}) assert(move(&controls[1], e) == 0);
    assert(move(&controls[1], 0x3E, false, 0) == 0);
    assert(at<void*>(&panel, 0x1C) == &controls[1]);
    // Slider horizontal input stays native, but vertical input reaches the footer.
    at<void*>(&controls[1], 0) = sliderTable;
    assert(move(&controls[1], 0x40) == 0);
    assert(move(&controls[1], 0x3E) == 1);
    assert(at<void*>(&panel, 0x1C) == &controls[2]);
    at<void*>(&controls[1], 0) = table;
    // Native lists keep interior selection; boundary movement skips disabled rows.
    void* rowArray[] = {&rows[0], &rows[1], &rows[2]};
    for (int i = 0; i < 3; ++i) { at<void*>(&rows[i], 0) = table; at<unsigned char>(&rows[i], 0x44) = 8; }
    at<void*>(&controls[1], 0) = listTable;
    at<int>(&controls[1], 0x3C) = 0;
    at<void**>(&controls[1], 0x29C) = rowArray;
    at<int>(&controls[1], 0x2A0) = 3;
    at<short>(&controls[1], 0x2C6) = 1;
    at<void*>(&panel, 0x1C) = &controls[1];
    assert(move(&controls[1], 0x3E, true) == 0);
    at<unsigned char>(&rows[2], 0x44) = 0;
    assert(move(&controls[1], 0x3E, true) == 1);
    assert(at<void*>(&panel, 0x1C) == &controls[2]);
    assert(KeyboardKeepFocusK1(&manager, 123, 456) == 1);
    at<void*>(&manager, 0x10) = &controls[2]; // native capture must resume mouse work
    assert(KeyboardKeepFocusK1(&manager, 123, 456) == 0);
    at<void*>(&manager, 0x10) = nullptr;
    // Empty actionable lists can yield focus; nonempty uninitialized ones do
    // not lose their first native selection. Controller list events stay native.
    at<void*>(&panel, 0x1C) = &controls[1];
    at<int>(&controls[1], 0x3C) = 1;
    at<int>(&controls[1], 0x2A0) = 0;
    at<short>(&controls[1], 0x2C6) = -1;
    assert(move(&controls[1], 0x32, true) == 0);
    assert(move(&controls[1], 0x3E, true) == 1);
    at<void*>(&panel, 0x1C) = &controls[1];
    at<int>(&controls[1], 0x2A0) = 3;
    assert(move(&controls[1], 0x3E, true) == 0);
    at<void*>(&controls[1], 0) = table;
    at<int>(&controls[1], 0x3C) = 1;
    // A complete custom order is retained; simulate its native focus assignment.
    at<int>(&controls[3], 8) = height * 3 / 10;
    const int order[] = {0,2,1,3};
    for (int i = 0; i < 4; ++i) {
        at<void*>(&controls[order[i]], 0x5C) = &controls[order[(i+3)%4]];
        at<void*>(&controls[order[i]], 0x64) = &controls[order[(i+1)%4]];
    }
    at<void*>(&panel, 0x1C) = &controls[0];
    assert(move(&controls[0], 0x3E) == 0);
    at<void*>(&panel, 0x1C) = &controls[2];
    assert(KeyboardKeepFocusK1(&manager, 123, 456) == 1);
    at<int>(&manager, 0x98) = 1; // a new modal invalidates the stationary latch
    assert(KeyboardKeepFocusK1(&manager, 123, 456) == 0);
    std::printf("Windows keyboard traversal: height %d passed\n", height);
}
int main() {
    static_assert(sizeof(void*) == 4, "Use the x86 compiler for Windows object layouts");
    for (int height : {600,720,1200,1440,2160}) run(height);
}
