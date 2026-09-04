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
| `swkotornopatch.exe` | The editable 4,042,752-byte `swkotor.exe`, SHA-256 `761F9466…C49E9886`. The build verifies this hash and refuses anything else. |
| `swpc_tex_gui.erf` | `TexturePacks\swpc_tex_gui.erf` from your KOTOR installation. Source art for the font atlases, hex row frames, and popup icons. |
| `swkotor_gold_final_D8F0EEBF.exe` | Only for `build_gold_patcher.ps1`, which builds the frozen 3440×1440-only patcher. Not needed for the shipping build. |

Copy them in, then:

```powershell
.\build_universal_patcher.ps1
```

To keep them somewhere else instead, pass `-SourceExe` / `-TexturePack`, set
`KMRP_SOURCE_EXE` / `KMRP_TEXTURE_PACK`, or create a `build.local.ps1` from
`build.local.example.ps1`.
