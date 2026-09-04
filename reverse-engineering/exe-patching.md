# Patching the executable: the rules, and the ways it goes wrong silently

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](../docs/documentation-standard.md). Read it before editing
> this file, and check the result still meets it — measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.


Twenty tools in `tools/` edit `swkotor.exe`, most by adding a `.k??` section and
trampolining into it. They share a small set of invariants. Breaking one does
not produce an error — it produces a game that crashes somewhere unrelated, or
worse, one that runs and is subtly wrong. This is the checklist.

The gold chain is cumulative: `.kui` → `.klb` → `.kfs` → `.kwl` → `.ksc` →
`.kgs` → `.ktn` → `.kmz` → `.kfg` → `.kmn`, each built from the previous
output. So a tool late in the chain is editing a file that already contains nine
other tools' sections, and anything it disturbs breaks *them*, not itself.

## Rule 1: a patch that edits an existing section must not change the file length

Section headers carry **absolute raw offsets**. `.ktn` says "my bytes start at
file 0x3E1000". Insert one byte anywhere before that and every later section is
one byte off from where its header claims, while the headers still say the old
numbers. The loader maps the wrong bytes and the code in them is garbage.

Only two shapes of edit are legitimate:

* **In-place** — same number of bytes out as in. Growing a stub into its own
  section's zero padding is fine, because the padding is inside the section's
  existing `raw_size`; overwrite the padding, do not insert.
* **Appending a new section** — the file grows by exactly one aligned
  `raw_size` at the very end, after every existing section. That is what
  `build_minimap_zoom_fix.py` and friends do.

Nothing else. If a tool needs more room in the middle, it gets a new section.

### The Python trap that caused this

```python
data[o : o + 9] = tail        # tail is 10 bytes  -- INSERTS, does not overwrite
```

`bytearray` slice assignment resizes to fit. A ten-byte value into a nine-byte
slice inserts one byte and slides the rest of the file. Write instead:

```python
before = len(data)
data[o : o + len(tail)] = tail
assert len(data) == before
```

**Every tool that edits an existing section should assert the length.**
`tools/build_listbox_top_inset.py` carries this as the reference implementation:
it checks the byte it is about to consume is padding, then asserts the length is
unchanged.

## Rule 2: verification must read every section, not the one you touched

The bug above shipped through a verification pass that re-read the exact bytes
it had just written and found them correct. They *were* correct. Everything
after them was not.

A patch tool's self-check should:

1. assert the output length (rule 1);
2. re-read its own patch site and stub;
3. **re-read one known byte from every pre-existing `.k??` section** — cheap,
   and it catches a slide immediately;
4. confirm the `.text` sites it depends on but does not modify are still what it
   expected (e.g. `build_listbox_top_inset.py` verifies gold v11's `33 ff 90` is
   intact before touching anything).

## Rule 3: read the failure signature before theorising

**A fault inside a hook you did not edit means shifted raw offsets, not a bug in
the code you wrote.** The crash that produced this document faulted at
`0x00415E16` — mid-instruction inside gold v13's `.ktn` text-setter hook — while
the edit was in `.kgs`, in listbox layout. Two rounds of reasoning went into why
a listbox change might corrupt a string, when the real answer was that `.ktn`
was no longer where its header said.

Signatures worth recognising:

| what you see | what it usually means |
| --- | --- |
| `cip` mid-instruction, in a hook you did not touch | section raw offsets slid |
| `cip` mid-instruction, in the hook you *did* touch | your resume address is off |
| fault in `.text` far from the patch, registers holding ASCII | a stub returned to a bad address |
| runs, but one screen is wrong | the patch is fine; the `.gui` field is not |

## Rule 4: bisect in the debugger, not in playtests

`x64dbg_command execute` with `init "<path to exe>", "", "<game dir>"` starts the
game under the debugger without anyone touching it. Two `run`s clear the system
breakpoint and the entry point; after that `state` reports `running` if it
launched and `paused` with a `cip` if it faulted. A launch test is about four
tool calls and costs nobody a playtest.

When a build with two independent edits fails, build each edit alone and run
both. The crash in this document was isolated in three runs: the GUI changes
plus the previous exe ran (clearing the `.gui` edits), builder A alone ran,
builder B alone reproduced it. That took less time than the first wrong theory.

## Rule 5: disassemble stubs from raw bytes, not from the section base

x64dbg's disassembly window decodes linearly from wherever you point it. Point
it at a stub's section base when the first instruction is not there and every
instruction after is misaligned — it will render plausible-looking nonsense.
While chasing this crash, x64dbg showed the `.ktn` stub's tail as
`jmp 0x00415E13`, an address one byte into a seven-byte instruction, which
looked exactly like a real bug and was an artefact.

Read the bytes with `x64dbg_memory read` or `PEImage.read_va`, then disassemble
them offline with capstone from the address you actually know is an instruction
boundary.

## Rule 6: the constants move together

`EXPECTED_GOLD_SHA256` (`generate_gold_delta.py`), `GoldPatch.TargetHash` and
`GoldPatch.TargetLength` (`src/patcher/KmrpPatcher.cs`) and `-GoldExe`
(`build_kmrp.ps1`) all describe the same file. Getting one out of
step is caught by the patcher's own startup check — "Embedded patch metadata
does not match this patcher" — which has fired twice in this work. Reproduce it
against the built `gold.kup` before shipping, not after.

## Encoding notes

* `83 /r ib` and `6A ib` sign-extend an imm8: the usable range is 0..127. A
  constant that scales with resolution will exceed that and needs the imm32
  form, which means more bytes, which means a trampoline (see gold v10 in
  [listbox-geometry.md](listbox-geometry.md)).
* Enter stubs with `jmp`, not `call`, when the original code reaches its
  arguments through `[esp+NN]` — `jmp` leaves `esp` alone so those references
  stay valid. Use `call` only when the stub must run code *after* the original
  returns, and then match the callee's stack cleanup (`ret 4` in, `ret 4` out).
* `push`/`pop` inside a stub is balanced and safe for `[esp+NN]`, but it does
  write below `esp`. Prefer a spare register or a stack slot the stub already
  owns.
* Preserve whatever the resume point reads. Check the flags too: if the
  instruction after your resume address is a `jcc`, the last flag-setting
  instruction in the stub must be the one whose flags it expects.

## See also

* [listbox-geometry.md](listbox-geometry.md) — the trampoline pattern, and the
  method for finding which field drives which margin
* [map.md](map.md) — `.kmz` / `.kfg`, and the gates that keep a shared function's
  other callers untouched
* [font.md](font.md) — `.kfs` / `.klb`
