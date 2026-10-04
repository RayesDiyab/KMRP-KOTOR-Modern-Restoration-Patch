# Build inputs

> **Documentation standard.** This document follows
> [`../docs/documentation-standard.md`](../docs/documentation-standard.md). Read it before editing
> this file, and check the result still meets it — measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.

Files the build needs that come from **your own copy of the game**. They live
here so the project folder is self-contained and can be moved anywhere; earlier
the build reached outside the folder with a `..\` path, which broke silently the
first time the project was moved.

**Nothing in here is committed.** These are BioWare's files, not ours, and
`.gitignore` blocks them. A fresh clone starts with an empty folder and the
build will tell you exactly what is missing.

| File | Where to get it |
| --- | --- |
| `swkotornopatch.exe` | Optional for historical executable comparisons and installer regressions: the editable 4,042,752-byte `swkotor.exe`, SHA-256 `761F9466…C49E9886`. The normal build does not read it. |
| `swpc_tex_gui.erf` | `TexturePacks\swpc_tex_gui.erf` from your KOTOR installation. Source art for the font atlases, hex row frames, and popup icons. |
| `swkotor-steam.exe` | Optional, for tests only: Steam's own `swkotor.exe`, 4,395,008 bytes, SHA-256 `34E6D971…A439F34C88`, unmodified. `testing\regression\Test-KpmEdition.ps1` installed the KPM edition over it until that test was removed on 2026-10-04 (no test uses it now); without it that test skipped its Steam case and says so. The build does not read it. |
Copy the texture pack in, then:

```powershell
.\build_kmrp.ps1
```

The engine template, controller module and KPM runtime are built from source by
the script. Optional per-resolution font sets may be generated first; see
*Build from source* in the [main README](../README.md).

*Corrected 2026-10-01:* the clean executable and gold snapshot used to be required.
The source-built Windows engine recipe removes both requirements. A Steam game
installation supplies the texture pack needed for the build.

*Corrected 2026-09-24:* this file named `build_universal_patcher.ps1` as the
build and listed `swkotor_gold_final_D8F0EEBF.exe` for `build_gold_patcher.ps1`.
Both scripts were removed on 2026-09-03, when `build_kmrp.ps1` replaced them.

To keep them somewhere else instead, pass `-TexturePack`, set
`KMRP_TEXTURE_PACK`, or create a `build.local.ps1` from
`build.local.example.ps1`.
