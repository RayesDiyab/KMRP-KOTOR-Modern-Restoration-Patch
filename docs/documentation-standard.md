# The documentation standard

Every document in this repository is held to this. It exists because a third-party
patcher for the same executable ships a `TECHNICAL.txt` listing every offset it
writes, so that a collision is diagnosable by someone who is not its author — and
when we measured ours against it, ours was worse. The benchmark is
[`reverse-engineering/map-scaling.md`](../reverse-engineering/map-scaling.md) and
[`reverse-engineering/map-markers.md`](../reverse-engineering/map-markers.md).
Match those or improve on them.

The test a document has to pass: **someone who was not here, working only from
this repository and a clean executable, can verify every claim and redo the work.**

## Two kinds of document, kept apart

| kind | holds | example |
| --- | --- | --- |
| **Lab record** | What was tried, in the order it happened. Failures, dead ends, rejected candidates, disproved theories. Never edited to look tidy. | `map.md`, `experiments/` |
| **Reference** | The finished mechanism. What the code does now, byte for byte. | `map-scaling.md`, `map-markers.md` |

Mixing them is how `map.md` came to describe a design that had been superseded
for weeks. Each says at the top which it is, and links to the other.

## The rules

**1. Every claim is measured, and says how.** "Read out of gold v18", "disassembled
from the clean executable", "computed from values read out of them". If a number
came from a design note or another project's documentation rather than the
binary, that is a different claim and must be labelled as such — it may be wrong.

> This is not hypothetical. A section here once said the conversion routine
> "divides by" two shared float constants. It does not: it divides by a
> per-object field, and those constants are bounds checks. That sentence was
> written from the design note instead of the disassembly.

**2. State the build.** Which executable, its SHA-256, its length. A document
about bytes is meaningless without saying *which* bytes.

**3. State the address convention, every time.** `VA` versus `FILE`, the
`FILE = VA − 0x400000` rule, **and the exception**: appended sections need
`FILE = VA − 0x492000`. Mixing them silently produces offsets that land nowhere.

**4. Tables for data, prose for reasoning.** Every site gets a row: VA, FILE,
size, vanilla value, new value, purpose. Never bury an offset in a sentence.

**5. Quote the disassembly, annotated and trimmed.** Only the instructions that
carry the argument, with addresses, and a comment on each line that matters.

**6. Give the formula, then a table of what it produces.** `canvas = screen // 2`
is the rule; the per-resolution table is the evidence that the rule is what
actually ships.

**7. Corroborate where you can, and name the source.** An independent
reimplementation (reone), another patcher's published offsets, a second
measurement path. Mark it as corroboration, not as primary evidence.

**8. Close the loop numerically.** The strongest section in this repository is the
one where a transform applied to module data reproduces seven marker positions
that had been read off a screenshot months earlier, to sub-pixel accuracy. Find
the check that makes a claim falsifiable, and run it.

**9. Record what was rejected, and why.** The alternative that was tried and
failed is as valuable as the one that shipped — it is what stops the next person
retrying it. Say what was appealing about it and what killed it.

**10. Mark untested explicitly.** "Verified in play at 3440×1440; every other
resolution verified by reading the bytes back, not by looking at the game." Never
imply coverage you do not have. A reader who finds one overstated claim has to
doubt all of them.

**11. Corrections stay visible.** When a document was wrong, say what it said,
what is true, and why the mistake was made. Do not silently edit. The mistakes
are load-bearing: they are the reason the rules exist.

**12. Say what is deliberately *not* changed.** A reader needs to distinguish "we
left this alone on purpose, here is why" from "we never looked at this". Untouched
shared state is often the most important fact in the document.

**13. State the count, and how you established it.** "Fourteen sites, here they
are" — not "the size constant". If you believe there is one site, say why.
See [`CONTRIBUTING.md`](../CONTRIBUTING.md): finding a site means the search is
incomplete, not finished.

**14. End with how to verify by hand.** The commands, the offsets, and the checks
that catch the mistakes that subsystem invites. If a reader cannot re-derive your
claims without your machine, the document has failed.

## Skeleton

```markdown
# <Subsystem>: what KMRP writes, byte for byte

<One paragraph: what this covers, what it does not, and which document has the rest.>
<A sentence on provenance: measured how, and where untested is marked.>

## The build this describes
## 1. What the engine actually does      <- annotated disassembly, corroboration, numeric proof
## 2. The model / the domains            <- formulas, then a per-resolution table
## 3. Every byte KMRP writes             <- tables: per-resolution, fixed, redirected call sites
## 4. The injected code                  <- stubs disassembled from the shipped binary
## 5. How this stays isolated            <- what it shares with other subsystems, and why that is safe
## 6. Limits                             <- encoding ceilings, clamps, rounding, which resolutions are affected
## 7. What is deliberately not changed
## 8. Verifying by hand
```

Not every document needs all of it. Every document needs 1, 3, 7 and 8.

## Anti-patterns, all of them real

| Anti-pattern | What happened here |
| --- | --- |
| Describing a release candidate as if it shipped | `map.md` claimed four immediates were restored to retail and a call was redirected. Gold did neither, for weeks. |
| Restating a design note as measurement | "Divides by the shared floats" — it divides by a per-object field. |
| One site assumed to be the only site | Map markers: three attempts, fourteen sites, each layer found only after a play-test said it had not worked. |
| A number stated without its resolution | "Marker overlay 1478×720" is only true at 3440×1440. It is 344×300 at 800×600. |
| Silent correction | Fixing a wrong sentence without saying it was wrong, which destroys the record of why the rule exists. |
| Implying coverage | "Verified" when four resolutions were checked out of forty-eight. |

## Before you commit a document

- [ ] Every number traced to a binary, a formula, or a labelled external source
- [ ] Build identity and address convention stated
- [ ] Sites in a table, with vanilla and current values
- [ ] Formula plus the table it produces
- [ ] Anything untested labelled untested
- [ ] Rejected alternatives recorded with their reasoning
- [ ] Corrections visible, not silent
- [ ] "Not changed" section present
- [ ] A reader with a clean executable can verify it without asking you
- [ ] `python .github/scripts/check_links.py` passes
