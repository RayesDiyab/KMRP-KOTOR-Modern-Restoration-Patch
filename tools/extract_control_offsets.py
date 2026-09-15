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

How the control is identified, and why the obvious rule is not enough
--------------------------------------------------------------------

The binder is `__thiscall(control, tag, addToArray)`, so **the control is the
last thing pushed before the call**. That is the rule used here, and it is a
property of the calling convention rather than of any particular compilation.

An earlier version instead looked for the last `lea <reg>, [esi+imm]` whose very
next instruction pushed that same register, inside a 112-byte window. That is
true of most bind sites and false of some, and when it was false the window
still contained an unrelated `lea` from the PREVIOUS control -- so the site was
not reported as unresolved, it was reported with the wrong offset. Inventory's
`BTN_CHANGE1` came out as `panel+0x14EC`, which is `BTN_QUESTITEMS`: its control
is in `edi`, loaded at `0x006B35D4`, nearly a thousand bytes before its bind.

**43 of 673 sites were wrong that way** -- a little over 6%, silently.

So the register is tracked instead of pattern-matched. `lea <reg>, [esi+imm]`
records a value for that register; any other write to it clears the record,
using capstone's own register-access information rather than a list of mnemonics
this file would have to keep correct. A push of a register with no record is
unresolved and is reported as such.

Decoding, and why the answer is taken by agreement
--------------------------------------------------

x86 has no way to find an instruction boundary by looking backwards, and
decoding from the wrong byte invents operands -- `0x006B35C4`, a real
`lea ecx, [esi+0x14EC]`, decodes as `dec dword ptr [ebp+0x14EC8E]` if entered one
byte early, which hides a constructor completely.

Each site is therefore decoded from several different starting offsets. A start
is kept only if its stream lands exactly on the bind call, and the answer is the
one the most starts agree on, with at least MIN_AGREE of them and no rival
answer. A site whose starts disagree is left unresolved rather than settled by
picking one.

What it does not resolve, and why that is correct
-------------------------------------------------

56 of the 771 sites are reported unresolved, in 16 clusters. They are not
failures: those controls have no constant offset to report. The tag is built at
runtime and so is the address --

    00681128  push 0x73D720            "%d"
    0068112E  call 0x006FADB0          sprintf the tag
    00681144  mov  eax, [esp+0x10]
    0068114E  add  eax, 0xFFFFD750     the control, COMPUTED
    00681155  mov  ecx, esi
    0068115F  call 0x0040B930

-- which is a loop binding N controls of one kind. `panel+<constant>` cannot
describe them, so declining is the honest answer. Every control that does have a
fixed offset is resolved: 715 of them.

Self-check
----------

Two binds inside one constructor cannot name the same offset: a panel does not
bind one control under two tags. The extractor asserts that before printing, so
a regression of the kind described above fails the run instead of producing
plausible-looking output.
"""
import collections
import struct
import sys

import capstone

PATH = r"C:\KMRP - KOTOR Modern Restoration Patch\build-inputs\swkotornopatch.exe"
BINDER = 0x0040B930

# Far enough back to reach a `lea` that happens long before its push -- the
# worst real case measured is Inventory's BTN_CHANGE1 at ~0x3A0 bytes.
WINDOW = 0x600
# How many differently-aligned decodes to try per site, and how many must agree.
STARTS = 24
MIN_AGREE = 3
# Two binds this close together are in the same function, so they must not name
# the same offset.
SAME_FUNCTION = 0x200

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
md.detail = True                       # needed for regs_access()

sites = []
for i in range(len(text) - 5):
    if text[i] != 0xE8:
        continue
    if TEXT[0] + i + 5 + struct.unpack_from("<i", text, i + 1)[0] == BINDER:
        sites.append(i)


def resolve(stream, call_va):
    """(tag, offset) for one decoded stream, or (tag, None) when unresolved.

    `regs` maps a register to the panel offset it currently holds. Only
    `lea <reg>, [esi+imm]` puts a value in; every other write takes it out, so a
    register whose value came from somewhere else is never mistaken for a
    control.
    """
    regs = {}
    tag = None
    last_push = None
    for ins in stream:
        if ins.address >= call_va:
            break
        if ins.mnemonic == "push":
            operand = ins.op_str.strip()
            # Captured HERE, not read back at the call. The thiscall setup
            # `mov ecx, esi` sits between the push and the call, so a control
            # pushed from ecx has had its register overwritten by the time the
            # call is reached -- which silently lost all 97 such sites.
            last_push = regs.get(operand)
            if operand.startswith("0x"):
                candidate = read_string(int(operand, 16))
                if candidate and candidate.replace("_", "").isalnum():
                    tag = candidate
            continue

        written = ins.regs_access()[1]
        names = {ins.reg_name(r) for r in written}
        if (ins.mnemonic == "lea" and "[esi +" in f"{ins.mnemonic} {ins.op_str}"):
            register = ins.op_str.split(",")[0].strip()
            try:
                regs[register] = int(
                    ins.op_str.split("[esi +")[1].strip(" ]"), 16)
            except ValueError:
                regs.pop(register, None)
            names.discard(register)
        # Anything else that writes a register invalidates what it held.
        for name in names:
            regs.pop(name, None)

    return tag, last_push


rows = []
unresolved = []
for site in sites:
    call_va = TEXT[0] + site
    answers = collections.Counter()
    tags = collections.Counter()
    for start in range(max(0, site - WINDOW), max(0, site - WINDOW) + STARTS):
        stream = list(md.disasm(text[start:site + 5], TEXT[0] + start))
        if not any(i.address == call_va for i in stream):
            continue          # this alignment never reached the call: discard
        tag, control = resolve(stream, call_va)
        if tag is not None and control is not None:
            answers[control] += 1
            tags[tag] += 1
    if not answers:
        unresolved.append((call_va, "no aligned decode resolved it"))
        continue
    (control, votes), = answers.most_common(1)
    rivals = [c for c, v in answers.items() if c != control and v >= MIN_AGREE]
    if votes < MIN_AGREE or rivals:
        unresolved.append((call_va, f"decodes disagree: {dict(answers)}"))
        continue
    (tag, _), = tags.most_common(1)
    rows.append((call_va, tag, control))

# --- self-check: one constructor cannot bind two tags to one offset ---------
by_offset = collections.defaultdict(list)
for address, tag, control in rows:
    by_offset[control].append((address, tag))
collisions = []
for control, entries in by_offset.items():
    entries.sort()
    for a, b in zip(entries, entries[1:]):
        if b[0] - a[0] < SAME_FUNCTION:
            collisions.append((control, a, b))
if collisions:
    print(f"{len(collisions)} offset collisions inside one function:",
          file=sys.stderr)
    for control, a, b in collisions[:10]:
        print(f"   panel+0x{control:04X}  {a[1]} at {a[0]:08X}"
              f"   and   {b[1]} at {b[0]:08X}", file=sys.stderr)
    raise SystemExit("extraction is wrong; refusing to print it")

print(f"{len(sites)} calls to the binder, {len(rows)} resolved, "
      f"{len(unresolved)} unresolved")
if unresolved and "-v" in sys.argv:
    for address, why in unresolved:
        print(f"  {address:08X}  -- {why}")
print()

args = [a for a in sys.argv[1:] if not a.startswith("-")]
lo = int(args[0], 16) if len(args) > 1 else 0
hi = int(args[1], 16) if len(args) > 1 else 0xFFFFFFFF
names = [n.upper() for n in args[2:]]
for address, tag, control in rows:
    if not (lo <= address <= hi):
        continue
    if names and not any(n in tag.upper() for n in names):
        continue
    print(f"  {address:08X}  {tag:<24} panel+0x{control:04X}")
