"""Extract every (control tag -> offset in its panel) pair the engine binds.

A panel's controls are embedded objects, not pointers, and the module addresses
them as a fixed offset from the panel. Those offsets used to come from a symbol
database. They do not have to: the engine states every one of them itself, in
the call that attaches a control to its tag.

    0067AE38  push 0x752F0C            "BTN_LOADGAME"
    0067AE3D  lea  ecx, [esp+0xC]
    0067AE41  call 0x005E5A90          CExoString from the literal
    0067AE46  push 1
    0067AE48  lea  edx, [esp+0xC]
    0067AE4C  push edx                 the string
    0067AE4D  lea  eax, [esi+0x5B4]    the embedded control
    0067AE53  push eax
    0067AE54  mov  ecx, esi
    0067AE5E  call 0x0040B930          bind

Two things this got wrong before, both worth stating because both produced
plausible-looking output:

  * the register holding the control varies -- ecx for one button, eax for the
    next, edx for the one after -- so matching only `lea ecx` silently paired
    each tag with the PREVIOUS button's offset. The control is the last
    `lea <reg>, [esi+imm]` whose very next instruction pushes that same register.
  * decoding from an arbitrary byte lands mid-instruction and invents operands,
    so each window is tried at successive starts until one decodes cleanly onto
    the call itself.

The call address is reported alongside, because a tag alone does not identify a
panel -- BTN_EXIT and BTN_BACK are bound by many of them.
"""
import struct
import sys

import capstone

PATH = r"C:\KMRP - KOTOR Modern Restoration Patch\build-inputs\swkotornopatch.exe"
BINDER = 0x0040B930

data = open(PATH, "rb").read()
pe = struct.unpack_from("<I", data, 0x3C)[0]
nsec = struct.unpack_from("<H", data, pe + 6)[0]
optsz = struct.unpack_from("<H", data, pe + 20)[0]
base = struct.unpack_from("<I", data, pe + 24 + 28)[0]
secs = []
off = pe + 24 + optsz
for i in range(nsec):
    name, vsz, va, rsz, ro = struct.unpack_from("<8sIIII", data, off + i * 40)
    secs.append((va + base, vsz, ro, rsz))
TEXT = secs[0]


def read_string(va, limit=64):
    for sva, vsz, ro, rsz in secs:
        if sva <= va < sva + vsz:
            o = ro + (va - sva)
            end = data.find(bytes([0]), o, o + limit)
            if end < 0:
                return None
            raw = data[o:end]
            if not raw or not all(32 <= c < 127 for c in raw):
                return None
            return raw.decode("ascii")
    return None


text = data[TEXT[2]:TEXT[2] + TEXT[1]]
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)

sites = []
for i in range(len(text) - 5):
    if text[i] != 0xE8:
        continue
    if TEXT[0] + i + 5 + struct.unpack_from("<i", text, i + 1)[0] == BINDER:
        sites.append(i)

rows = []
for site in sites:
    window_start = None
    for start in range(max(0, site - 112), site):
        stream = list(md.disasm(text[start:site + 5], TEXT[0] + start))
        if any(i.address - TEXT[0] == site for i in stream):
            window_start = start
            decoded = stream
            break
    if window_start is None:
        continue

    control = None
    tag = None
    pending = None          # (register, offset) awaiting its push
    for ins in decoded:
        line = f"{ins.mnemonic} {ins.op_str}"
        if ins.mnemonic == "lea" and "[esi +" in line:
            register = ins.op_str.split(",")[0].strip()
            try:
                pending = (register, int(line.split("[esi +")[1].strip(" ]"), 16))
            except ValueError:
                pending = None
        elif ins.mnemonic == "push":
            if pending and ins.op_str.strip() == pending[0]:
                control = pending[1]
                pending = None
            elif ins.op_str.startswith("0x"):
                candidate = read_string(int(ins.op_str, 16))
                if candidate and candidate.replace("_", "").isalnum():
                    tag = candidate
        else:
            if ins.mnemonic not in ("mov", "nop"):
                pending = pending if ins.mnemonic == "lea" else pending
    if control is not None and tag is not None:
        rows.append((TEXT[0] + site, tag, control))

print(f"{len(sites)} calls to the binder, {len(rows)} resolved")
print()

lo = int(sys.argv[1], 16) if len(sys.argv) > 2 else 0
hi = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0xFFFFFFFF
names = [n.upper() for n in sys.argv[3:]]
for address, tag, control in rows:
    if not (lo <= address <= hi):
        continue
    if names and not any(n in tag.upper() for n in names):
        continue
    print(f"  {address:08X}  {tag:<24} panel+0x{control:04X}")
