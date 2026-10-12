#!/usr/bin/env python3
"""Stage KotorPatcher with patches translated for another build of KOTOR_Exe.

    make_runtime.py <map.json> <from KOTOR_Exe> <to KOTOR_Exe> <patch_config.toml> <KotorPatcher.dylib>
                    <out dir> <folder of .kpatch files>...

Takes the package's patch_config.toml (made by KPM for the first build) and writes one for the
second: every hook's address through the map, its original bytes read from the second build
at that address (and compared with the first build's, instruction by instruction), and its
replacement bytes with what moves put right: the absolute target after a `jmp [rip+0]`, the
displacement of a rip-relative operand, the distance of a relative call or jump that leaves
the hook. Each patch's module is taken from the .kpatch of its id in the folders given: built
from sources whose addresses were translated the same way (rewrite_sources.py).
"""
import struct
import sys
import tomllib
import zipfile
from pathlib import Path

import capstone
from capstone import x86_const as x86

sys.path.insert(0, str(Path(__file__).parent))
from lookup import Map  # noqa: E402

BASE = 0x100000000
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
MD.detail = True


def toml(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(value, list):
        return "[" + ", ".join(toml(v) for v in value) + "]"
    return str(value)


def shape(code: bytes, address: int):
    return [(i.mnemonic, i.size) for i in MD.disasm(code, address)]


def rebase(code: bytes, old: int, new: int, m: Map, notes: list) -> bytes:
    """Replacement bytes written for `old`, made right at `new`."""
    out = bytearray(code)
    at = 0
    while at < len(code):
        # jmp qword [rip+0] and the 8-byte absolute target KPM puts after it
        if code[at:at + 6] == b"\xff\x25\x00\x00\x00\x00" and at + 14 <= len(code):
            target, = struct.unpack_from("<Q", code, at + 6)
            to, how = m.to(target)
            if to is None:
                raise ValueError(f"absolute target {target:#x} at {old + at:#x}: {how}")
            struct.pack_into("<Q", out, at + 6, to)
            notes.append(f"abs {target:#x}->{to:#x} ({how})")
            at += 14
            continue
        ins = next(MD.disasm(code[at:at + 16], old + at), None)
        if ins is None:
            raise ValueError(f"cannot decode the replacement at {old + at:#x}")
        here = new + at
        for op in ins.operands:
            if op.type == x86.X86_OP_MEM and op.mem.base == x86.X86_REG_RIP:
                target = ins.address + ins.size + op.mem.disp
                to, how = m.to(target)
                if to is None:
                    raise ValueError(f"operand {target:#x} at {ins.address:#x}: {how}")
                struct.pack_into("<i", out, at + ins.disp_offset, to - (here + ins.size))
                notes.append(f"rip {target:#x}->{to:#x} ({how})")
            elif op.type == x86.X86_OP_IMM and (x86.X86_GRP_JUMP in ins.groups or x86.X86_GRP_CALL in ins.groups):
                target = op.imm
                if old <= target < old + len(code):
                    continue                      # inside the hook: the distance stays
                to, how = m.to(target)
                if to is None:
                    raise ValueError(f"branch to {target:#x} at {ins.address:#x}: {how}")
                distance = to - (here + ins.size)
                if ins.imm_size == 4:
                    struct.pack_into("<i", out, at + ins.imm_offset, distance)
                elif ins.imm_size == 1:
                    if distance != target - (ins.address + ins.size):
                        raise ValueError(f"short branch at {ins.address:#x} would need another distance")
                notes.append(f"rel {target:#x}->{to:#x} ({how})")
        at += ins.size
    return bytes(out)


def main():
    m = Map(sys.argv[1], sys.argv[2], sys.argv[3])
    old_exe, new_exe = Path(sys.argv[2]).read_bytes(), Path(sys.argv[3]).read_bytes()
    config_path, patcher, out = Path(sys.argv[4]), Path(sys.argv[5]), Path(sys.argv[6])
    kpatches = {}
    for folder in sys.argv[7:]:
        for path in Path(folder).glob("*.kpatch"):
            with zipfile.ZipFile(path) as z:
                kpatches[tomllib.loads(z.read("manifest.toml").decode())["patch"]["id"]] = path
    config = tomllib.loads(config_path.read_text())
    import hashlib
    lines = [f'target_version_sha = "{hashlib.sha256(new_exe).hexdigest().upper()}"']
    (out / "patches").mkdir(parents=True, exist_ok=True)
    problems = 0
    for patch in config["patches"]:
        if patch["id"] not in kpatches:
            print(f"  {patch['id']}: no .kpatch of that id in the folders given")
            problems += 1
            continue
        lines += ["[[patches]]", f'id = "{patch["id"]}"', f'dll = "{patch["dll"]}"']
        hooks = patch.get("hooks", [])
        moved = same = 0
        for hook in hooks:
            old = hook["address"]
            new, how = m.to(old)
            original = bytes(hook["original_bytes"])
            if new is None:
                print(f"  {patch['id']} {old:#x}: NOT TRANSLATED ({how})")
                problems += 1
                continue
            there = new_exe[new - BASE:new - BASE + len(original)]
            if shape(original, old) != shape(there, new):
                print(f"  {patch['id']} {old:#x} -> {new:#x}: the instructions differ: {original.hex()} / {there.hex()}")
                problems += 1
                continue
            same += there == original
            moved += there != original
            lines += ["[[patches.hooks]]", f"address = {new}", f"original_bytes = {list(there)}", f'type = "{hook["type"]}"']
            if "replacement_bytes" in hook and how == "inside" and len(original) <= 8:
                # Part of an instruction, a constant in it: not code, and nothing in it moves.
                lines.append(f"replacement_bytes = {hook['replacement_bytes']}")
            elif "replacement_bytes" in hook:
                notes = []
                try:
                    replacement = rebase(bytes(hook["replacement_bytes"]), old, new, m, notes)
                except ValueError as error:
                    print(f"  {patch['id']} {old:#x}: {error}")
                    problems += 1
                    continue
                lines.append(f"replacement_bytes = {list(replacement)}")
                if notes:
                    print(f"  {patch['id']} {old:#x} -> {new:#x}: " + "; ".join(notes))
            for key, value in hook.items():
                if key in ("address", "original_bytes", "type", "replacement_bytes", "parameters"):
                    continue
                if key.endswith("_address"):
                    to, why = m.to(value)
                    if to is None:
                        print(f"  {patch['id']} {old:#x}: {key} {value:#x}: {why}")
                        problems += 1
                        continue
                    value = to
                lines.append(f"{key} = {toml(value)}")
            for parameter in hook.get("parameters", []):
                lines.append("[[patches.hooks.parameters]]")
                for key, value in parameter.items():
                    lines.append(f"{key} = {toml(value)}")
        print(f"{patch['id']}: {len(hooks)} hooks, {same} with the same original bytes, {moved} with an operand that moved")
        if patch.get("dll"):
            (out / patch["dll"]).write_bytes(zipfile.ZipFile(kpatches[patch["id"]]).read("binaries/macos_x86_64.dylib"))
    (out / "patch_config.toml").write_text("\n".join(lines) + "\n")
    (out / "KotorPatcher.dylib").write_bytes(patcher.read_bytes())
    print(f"{out}: {problems} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
