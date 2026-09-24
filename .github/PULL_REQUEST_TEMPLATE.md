## What this changes

<!-- One subject per pull request. What behaviour is different afterwards? -->

## Why

<!-- The cause, not just the symptom. Addresses, measurements, or the vanilla
     behaviour it disagrees with. -->

## How it was verified

<!-- What you MEASURED, and how. Values read back out of the built files, a
     pixel comparison, a breakpoint. Include the numbers. -->

## Not verified

<!-- Say plainly what you could not check: resolutions not tested, screens not
     seen. An honest gap is far more useful than implied coverage. -->

## Checklist

- [ ] No game executables or game resources are committed
- [ ] Anything sized in pixels scales by `max(1.0, height / 720)`, on **both**
      the `.gui` side and the executable side
- [ ] In-place executable edits keep the file length unchanged (a new `.k??`
      section adds exactly its 4,096 raw bytes), and every `.k??` section still
      reads back
- [ ] Affected documentation in `docs/` or `reverse-engineering/` updated,
      including any earlier statement this proves wrong
- [ ] `CHANGELOG.md` entry added under `## [Unreleased]`
