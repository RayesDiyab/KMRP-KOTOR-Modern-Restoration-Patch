// Controller remapping's rules (src/controller-native/K1ButtonRemapPolicy.h), no game.
#include "../../src/controller-native/K1ButtonRemapPolicy.h"
#include <cassert>
#include <iostream>
using namespace KmrpRemap;

int main() {
    // The default layout: every action on its own button, complete.
    Mapping m;
    assert(m.Complete() && m.IsDefault());
    for (int b = 0; b < ButtonCount; ++b) assert(m.ActionOn(b) == b && m.button[b] == b);

    // No swapping: Undo Action (Y's) given RB takes it from Next Target (RB's), which is
    // left with no button; Y is free. Not complete, so not savable.
    Mapping changed;
    assert(changed.Assign(Y, RB) == RB);
    assert(changed.button[Y] == RB && changed.button[RB] == None && changed.ActionOn(Y) == None);
    assert(changed.ActionOn(RB) == Y && !changed.Complete() && !changed.IsDefault());
    // Next Target given the free Y: complete again.
    assert(changed.Assign(RB, Y) == None && changed.Complete());
    // Giving an action the button it already has displaces nobody.
    assert(changed.Assign(A, A) == None && changed.Complete());
    // Out of range: nothing changes.
    Mapping same = changed;
    assert(changed.Assign(-1, A) == None && changed.Assign(A, ButtonCount) == None && changed == same);
    // Two actions on one button is not complete, whatever else.
    Mapping twice;
    twice.button[B] = A;
    assert(!twice.Complete());

    // The translator: in the world a pad button becomes its action's default button;
    // elsewhere every button is itself.
    Mapping swapped;                 // Undo Action on RB, Next Target on Y
    swapped.Assign(Y, RB);
    swapped.Assign(RB, Y);
    Translator t;
    assert(t.Apply(Mask[RB], true, swapped) == Mask[Y]);          // RB pressed in the world: Undo Action
    assert(t.Apply(0, true, swapped) == 0);
    assert(t.Apply(Mask[RB], false, swapped) == Mask[RB]);        // in a menu: RB
    assert(t.Apply(0, false, swapped) == 0);
    // The D-pad, Start and Back pass through untouched, in the world and out of it.
    constexpr std::uint16_t fixed = 0x0001 | 0x0002 | 0x0004 | 0x0008 | 0x0010 | 0x0020;
    assert(t.Apply(fixed, true, swapped) == fixed);
    assert(t.Apply(0, true, swapped) == 0);
    // A press keeps the meaning it had when it went down: RB pressed in the world (Undo
    // Action, so Y), still held as a menu opens, is still Y until it is let go; then a
    // new press in the menu is RB.
    assert(t.Apply(Mask[RB], true, swapped) == Mask[Y]);
    assert(t.Apply(Mask[RB], false, swapped) == Mask[Y]);
    assert(t.Apply(0, false, swapped) == 0);
    assert(t.Apply(Mask[RB], false, swapped) == Mask[RB]);
    assert(t.Apply(0, false, swapped) == 0);
    // And the other way: pressed in a menu, held into the world.
    assert(t.Apply(Mask[Y], false, swapped) == Mask[Y]);
    assert(t.Apply(Mask[Y], true, swapped) == Mask[Y]);
    assert(t.Apply(0, true, swapped) == 0);
    assert(t.Apply(Mask[Y], true, swapped) == Mask[RB]);
    assert(t.Apply(0, true, swapped) == 0);
    // The triggers, folded into the word, translate like any button: Pause (RT's) on LB.
    Mapping triggers;
    triggers.Assign(RT, LB);
    triggers.Assign(LB, RT);
    Translator u;
    assert(u.Apply(Mask[LB], true, triggers) == Mask[RT] && (Mask[RT] & TriggerBits));
    assert(u.Apply(Mask[LB] | Mask[RT], true, triggers) == (Mask[RT] | Mask[LB]));
    assert(u.Apply(0, true, triggers) == 0);
    // An incomplete layout is never used: buttons stay themselves.
    Translator v;
    assert(v.Apply(Mask[RB], true, changed.Complete() ? Mapping{} : twice) == Mask[RB]);

    // The screen's editor: rows are buttons. Undo Action (Y's row) given RB: it moves to
    // RB's row, and Next Target, which RB had, waits in Y's row, the row Undo Action
    // left. Not complete.
    Editor e;
    e.Assign(Y, RB);
    assert(e.ActionInRow(RB) == Y && e.ActionInRow(Y) == RB && e.Waiting(Y) && !e.Waiting(RB));
    assert(e.mapping.button[RB] == None && !e.Complete());
    // Next Target, waiting in Y's row, given Y: complete, nothing waits.
    e.Assign(Y, Y);
    assert(e.Complete() && !e.Waiting(Y) && e.ActionInRow(Y) == RB && e.mapping.button[RB] == Y);
    // A chain: Interact (A's row) to LB; Previous Target waits in A's row; given B there,
    // Release Bar waits in A's row instead; given A, complete.
    Editor c;
    c.Assign(A, LB);
    assert(c.Waiting(A) && c.ActionInRow(A) == LB && c.ActionInRow(LB) == A);
    c.Assign(A, B);
    assert(c.Waiting(A) && c.ActionInRow(A) == B && c.ActionInRow(B) == LB && c.mapping.button[LB] == B);
    c.Assign(A, A);
    assert(c.Complete() && c.ActionInRow(A) == B && c.mapping.button[B] == A);
    // A waiting action given the button of another waiting row: they trade waiting
    // rows, and the count of waiting rows stays the count of free buttons.
    Editor w;
    w.Assign(X, Y);               // Disengage to Y; Undo Action waits in X's row
    w.Assign(A, B);               // Interact to B; Release Bar waits in A's row
    assert(w.Waiting(X) && w.Waiting(A));
    w.Assign(X, A);               // Undo Action (waiting in X's row) given A, where Release Bar waits
    assert(w.mapping.button[Y] == A && w.Waiting(X) && w.ActionInRow(X) == B && !w.Waiting(A));
    int waitingRows = 0, freeButtons = 0;
    for (int b = 0; b < ButtonCount; ++b) {
        waitingRows += w.Waiting(b);
        freeButtons += w.mapping.ActionOn(b) == None;
    }
    assert(waitingRows == freeButtons && waitingRows == 1);
    // Every press in every order keeps one waiting action per free button.
    for (int first = 0; first < ButtonCount; ++first)
        for (int second = 0; second < ButtonCount; ++second)
            for (int third = 0; third < ButtonCount; ++third) {
                Editor r;
                r.Assign(first, second);
                r.Assign(second, third);
                r.Assign(third, first);
                int wr = 0, fb = 0;
                for (int b = 0; b < ButtonCount; ++b) {
                    wr += r.Waiting(b);
                    fb += r.mapping.ActionOn(b) == None;
                    if (r.mapping.ActionOn(b) != None) assert(r.waiting[b] == None);
                }
                assert(wr == fb && (wr == 0) == r.Complete());
            }
    e.Reset();
    assert(e.mapping.IsDefault() && e.Complete());

    // Names: what the settings file holds.
    for (int b = 0; b < ButtonCount; ++b) assert(ButtonByName(ButtonNames[b]) == b);
    assert(ButtonByName("rb") == RB && ButtonByName("Start") == None && ButtonByName(nullptr) == None);
    std::cout << "PASS: remapping's assignment, completeness, translation (world only, kept per press) and names\n";
}
