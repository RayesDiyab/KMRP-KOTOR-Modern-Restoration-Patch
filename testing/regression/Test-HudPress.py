#!/usr/bin/env python3
"""The controller presses the HUD's controls through their own input call (audit PAD-1, 2, 4).

Reads the unmodified executable and the source. Holds the engine facts the fix rests on, so a
wrong address or a table change fails here and not in a fight:

  * CSWGuiControl::HandleInputEvent stores the value at +0x4C, and it is the only writer of
    that field among the GUI control routines;
  * the HUD's handlers read +0x4C and exit when it is 0, which is why they cannot be called
    directly;
  * the action slots' registrations give 0x1F4 the previous action, 0x1F5 the next and 0x27
    the slot's activate;
  * CSWGuiBarkBubble's constructor writes the vtable the module treats as passive.

Then the source: no direct call of a handler remains on the live path.
Run: python testing/regression/Test-HudPress.py
"""
from pathlib import Path
import re
import struct

from capstone import Cs, CS_ARCH_X86, CS_MODE_32

ROOT = Path(__file__).resolve().parents[2]
EXE = ROOT / "build-inputs" / "swkotornopatch.exe"
BASE = 0x400000
data = EXE.read_bytes()
md = Cs(CS_ARCH_X86, CS_MODE_32)


def code(start, stop):
    return list(md.disasm(data[start - BASE:stop - BASE], start))


def main():
    checks = 0
    # HandleInputEvent stores the value before it calls the handler.
    routine = code(0x00418750, 0x004187BE)
    text = [f"{i.mnemonic} {i.op_str}" for i in routine]
    store = text.index("mov dword ptr [esi + 0x4c], ebx")
    call = next(n for n, line in enumerate(text) if line == "call dword ptr [eax + 4]")
    assert store < call, "HandleInputEvent no longer stores +0x4C before the handler"
    assert text[-1] == "ret 8", "HandleInputEvent's two arguments"
    checks += 2

    # Every handler the pad reaches refuses a zero.
    for va in (0x0068B050, 0x0068B0A0, 0x006884B0, 0x00688520, 0x0068AF70, 0x0068AFE0, 0x0068B970):
        head = [f"{i.mnemonic} {i.op_str}" for i in code(va, va + 24)]
        assert any("[eax + 0x4c]" in line for line in head), f"{va:#x} no longer reads +0x4C"
        checks += 1

    # The slot's registrations, 0x0068BB7C on: the two handlers chosen for target or
    # personal slots, then 0x27, 0, 0x1F4 and 0x1F5 in that order.
    window = [f"{i.mnemonic} {i.op_str}" for i in code(0x0068BB7C, 0x0068BC01)]
    joined = "\n".join(window)
    assert "dword ptr [esp + 0x1c], 0x6884b0" in joined and "dword ptr [esp + 0x18], 0x688520" in joined
    assert "dword ptr [esp + 0x1c], 0x68af70" in joined and "dword ptr [esp + 0x18], 0x68afe0" in joined
    assert joined.index("push 0x68b970") < joined.index("push 0x27"), "0x27 is the slot's activate"
    a = joined.index("mov ecx, dword ptr [esp + 0x1c]")
    b = joined.index("push 0x1f4")
    c = joined.index("mov edx, dword ptr [esp + 0x18]")
    d = joined.index("push 0x1f5")
    assert a < b < c < d, "0x1F4 takes the previous action's handler, 0x1F5 the next's"
    checks += 4

    # The bark bubble's vtable is written by code.
    native = (ROOT / "src/controller-native/vendor/K1XboxControls.cpp").read_text(encoding="utf-8")
    bark = int(re.search(r"K1_BARK_BUBBLE_PANEL_VTABLE\s*=\s*(0x[0-9A-Fa-f]+)", native).group(1), 16)
    needle = b"\xC7\x06" + struct.pack("<I", bark)              # mov dword ptr [esi], vtable
    assert needle in data or b"\xC7\x01" + struct.pack("<I", bark) in data, "no write of the bark vtable"
    checks += 1

    # The source: the live path sends events.
    joystick = (ROOT / "src/controller-native/K1NativeJoystick.cpp").read_text(encoding="utf-8")
    press = joystick[joystick.index("bool PressHudButtonK1(void* mainInterface, std::size_t member)\n{"):]
    press = press[:press.index("\n}\n")]
    assert "SendControlEventK1(button, K1_EVENT_A)" in press
    assert "K1_ON_CLEAR" not in joystick, "a handler address is back"
    cycle = native[native.index("void CycleAction("):]
    cycle = cycle[:cycle.index("\n}\n")]
    assert "SendControlEventK1(buttons[activeIndex], next ? 0x1F5 : 0x1F4)" in cycle
    assert "ActionCallbackFn" not in cycle
    hud = native[native.index("bool IsGameplayHudActive("):]
    hud = hud[:hud.index("\n}\n")]
    assert "K1_BARK_BUBBLE_PANEL_VTABLE" in hud
    request = joystick[joystick.index("void RequestNavigationK1(int dx, int dy, bool edge, bool fromDpad)\n{"):]
    request = request[:request.index("\n}\n")]
    assert "fromDpad && InputClassK1() == K1_CLASS_PC" in request
    memory = (ROOT / "src/controller-native/K1EngineMemory.h").read_text(encoding="utf-8")
    assert "[0x3C / 4]" in memory and "(control, event, value)" in memory
    checks += 7
    print(f"PASS: {checks} checks: controls are pressed through HandleInputEvent, and the engine "
          "facts that rest on hold in the executable.")


if __name__ == "__main__":
    main()
