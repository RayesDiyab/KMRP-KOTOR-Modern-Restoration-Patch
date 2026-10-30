# K1DC: the emulated GL_ATI_fragment_shader turns off hardware mipmaps

**For:** Synchro (K1 Modern Driver Compatibility)
**From:** KMRP, 2026-10-30
**Short version:** because K1DC reports `GL_ATI_fragment_shader`, KOTOR's 2003 rule for
ATI drivers switches off `GL_SGIS_generate_mipmap`. From then on, every uncompressed
texture the game mipmaps is mipmapped on the CPU by `gluBuild2DMipmaps`, each time it is
loaded. With large texture mods that is visible: a screen with two 768x768 pictures took
about 0.9 s to open. Vanilla's own textures are mostly unaffected, because they ship as
compressed TPCs with their mip levels already built.

## What we measured

Test machine: Steam KOTOR 1.03 at 3440x1440, NVIDIA driver 616.56 (OpenGL 4.6.0),
Windows 11 build 26300, K1DC installed with default settings, KMRP 1.6 development
build. The slow screen was the workbench (upgrade screen), whose KMRP art includes
`lbl_wupgradeb1.tga` and `lbl_wupgradeb2.tga`: 768x768, 32-bit, uncompressed, no TXI.

1. **The delay.** Two openings of the workbench took 912 ms and 893 ms between two GUI
   frames. The three panel constructors had finished by +23 ms; the rest came after them.
2. **Where the time went.** An in-process sampler (a thread suspending the main thread
   every few milliseconds and reading its instruction pointer and stack) took 57 to 58
   samples per opening. 93 to 96% of them were under `swkotor.exe+0x24CE5`, inside
   `CreateTexture` (0x00424980), in `GLU32.dll` (17 to 29%) and `msvcrt.dll` (66 to 75%):
   the branch that calls `gluBuild2DMipmaps` for an uncompressed texture with mipmaps.
3. **Why that branch.** `CreateTexture` uses `GL_GENERATE_MIPMAP_SGIS` only when
   `AurSGIMipmapAvailable` (0x0045F910) returns true. That function (from the public
   swkotor1-reconstruction, `glcaps.cpp`):

   ```c
   if (g_nGLExtensions & mask_ATI_fragment_shader)   // 0x007BB85C & [0x0078E4D0]
       answer = 0;
   else
       answer = (g_nGLExtensions & mask_SGIS_generate_mipmap) == mask_SGIS_generate_mipmap;  // [0x0078E4CC]
   ```

   The answer is cached at 0x0078E538 (-1 until first asked).
4. **What the game and the driver say.** Read from the running game after start-up:

   | | Value |
   | --- | --- |
   | game extension mask (0x007BB85C) | `3F7EFDFF` |
   | SGIS bit (`00080000`) in it | set |
   | ATI fragment shader bit (`00100000`) in it | set |
   | cached answer (0x0078E538) | 0 |
   | driver's `GL_EXTENSIONS` lists `GL_SGIS_generate_mipmap` | yes |
   | driver's `GL_EXTENSIONS` lists `GL_ATI_fragment_shader` | no |

   K1DC's log for the same run: `capability ati_fragment_shader=accepted` and
   `paths ... extensions=0x3F7EFDFF`. So the ATI bit comes from K1DC's answer to
   `CheckExtension("GL_ATI_fragment_shader")` (its detour at 0x004367D4), not from the
   driver.

## Why it matters

- Every uncompressed texture that asks for mipmaps (a TGA without a TXI saying
  `mipmap 0` is mipmapped by default) is rescaled to a power of two and mipmapped on the
  CPU on every load. In KMRP's case that is 684 TGAs (interface art, portraits, icons); in
  the wider modding scene, most texture mods ship TGAs.
- Without K1DC the same driver gives the game hardware mipmaps, because it does not list
  the ATI extension. So installing K1DC makes texture loading slower than without it.
- As far as we can tell, the reason for the 2003 rule (ATI's drivers of the time and
  automatic mipmap generation) no longer applies once K1DC emulates the ATI path through
  ARB programs on a current driver. We have not tested it on an AMD card.

## Suggested fix in K1DC

Keep the ATI answer for the shader path, but let the mipmap check see the driver's real
answer. For example, either of these:

- detour `AurSGIMipmapAvailable` (0x0045F910) to return whether the driver itself lists
  `GL_SGIS_generate_mipmap` (and, if you want to keep the old rule, does not itself list
  `GL_ATI_fragment_shader`); or
- after the extension mask is built, set the cached answer at 0x0078E538 to that value
  before the first texture upload.

## What KMRP does in the meantime

From its next build, KMRP sets the cached answer at 0x0078E538 to 1, once, from its hook
after the first texture upload (0x004216F1), when all of these hold: the game's mask has
the SGIS bit, the game's mask has the ATI bit, the driver lists `GL_SGIS_generate_mipmap`,
and the driver does not list `GL_ATI_fragment_shader`. Nothing else is changed. If K1DC
fixes this itself, KMRP's condition stops being true (the ATI-only-from-K1DC case) or the
write becomes redundant; either way the two do not conflict.

**Result in the game (same machine, same day).** KMRP's log:
`[KMRP] hardware mipmaps on: the driver has GL_SGIS_generate_mipmap and not
GL_ATI_fragment_shader, which only K1DC's emulation reports (the game's answer was -1)`,
and the cached answer read back as 1. Two openings of the workbench:

| | Before | After |
| --- | --- | --- |
| frame gap while opening | 912 ms and 893 ms | under 100 ms both times (below the log's threshold, so no line was written) |
| felt in play | "almost a full second" | "worked quick", about 0.2 s on the first opening |

K1DC's log showed the same two warnings as on a run of 2026-10-20, before any of this
(`gl error site=soft_shadow` and `site=glow`, `INVALID_OPERATION`), and nothing new. We
have not made a side-by-side visual comparison of K1DC's effects with and without the
change.

## Reproducing

1. Install K1DC on an NVIDIA (or any current) driver.
2. Put a large uncompressed TGA with no TXI on a GUI screen through Override (a 768x768
   32-bit `lbl_wupgradeb1.tga` does it), and open the screen: compare the opening time
   with K1DC and without it.
3. Or read the four values above from the running game: with K1DC the cached answer at
   0x0078E538 is 0 although the driver lists `GL_SGIS_generate_mipmap`.
