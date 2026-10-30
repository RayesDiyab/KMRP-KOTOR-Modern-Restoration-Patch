using System;
using System.Diagnostics;

namespace Kmrp
{
    /// <summary>A lit volumetric plume. A light source sits behind the crest, luminous
    /// smoke billows down and outward from it, and dust motes fall through the beam.
    ///
    /// The billowing structure is procedural fBm noise, not sprites: soft blobs cannot
    /// produce the fractal, curdled edge that reads as real smoke. The turbulence comes
    /// from domain warping -- the noise field is sampled at coordinates that are themselves
    /// offset by another noise field, which is what folds the plume into itself instead of
    /// leaving it looking like drifting fog.
    ///
    /// Everything is accumulated into one scalar emission buffer at reduced resolution: the
    /// smoke, the source glow, the downward cone, and the motes all add into the same
    /// field, so a single bloom pass and a single colour ramp light all of them
    /// consistently, and the motes glow because they are genuinely part of the lit volume
    /// rather than dots pasted on top. The buffer is then upscaled, which supplies the
    /// final softening for free.
    ///
    /// The cost is per-pixel CPU work, so resolution and octave count are the two dials
    /// that matter for frame time; both are measured rather than guessed.
    ///
    /// Split on 2026-10-30, unchanged, so the Linux installer's window draws the same
    /// header: this file is the arithmetic, the emission buffer as BGRA bytes and where
    /// each mote is; putting them on screen is each window's own (Render, in
    /// KmrpPatcher.cs for Windows' GDI+; MainWindow.cs for the Linux installer).</summary>
    internal sealed partial class LightField
    {
        private sealed class Mote
        {
            internal float X, Y, Fall, Drift, Phase, Size, Age, Life, Seed;
        }

        // The lamp is off-screen, above the top edge, and spans the whole bar: the source
        // is never visible, only what it lights. A localised source was tried first and
        // read as a glowing ball behind the crest.
        private const float TopFalloff = 0.7F;      // how fast the light dies with depth
        private const float TopStrength = 1.10F;
        private const float ShaftScale = 3.2F;      // lateral width of the descending shafts
        private const float ShaftStrength = 0.55F;  // how much of the light is shaped into shafts
        private const float ShaftDrift = 0.035F;    // how fast the shafts slide sideways

        // Rendering budget. Downscale is the single biggest lever on frame time -- the
        // noise is evaluated nine times per buffer pixel, so halving it quadruples the
        // cost -- but it is NOT the lever on how fine the smoke looks. Detail is limited
        // by NoiseScale, not by buffer resolution: measured, going from Downscale 8 to 3
        // tripled the cost and moved the detail figure by 6%.
        private const int Downscale = 12;
        private const int Octaves = 3;

        // Smoke shape.
        // Feature size. This is the dial that decides whether the plume reads as drifting
        // slabs or as see-through wisps; it was 2.4, where the finest octave had features
        // about 100px across and the smoke looked like a moving mass.
        private const float NoiseScale = 8.0F;
        private const float FbmGain = 0.5F;     // octave falloff; higher keeps finer wisps
        private const float WarpStrength = 1.6F;
        private const float FlowSpeed = 0.055F;   // how fast the plume travels downward
        private const float EvolveSpeed = 0.09F;  // how fast it boils in place
        private const float Threshold = 0.26F;    // noise level where smoke begins
        private const float DensityGain = 3.3F;

        // Tendrils hang downward, so the noise is sampled anisotropically: features are
        // stretched along v. At 1.0 the plume is isotropic and reads as clouds; pushed
        // as far as 0.45 it stops looking like smoke and starts looking like a comb of
        // vertical streaks.
        private const float NoiseAspectY = 0.80F;

        // The plume is dense at the top edge and breaks into wisps below a ragged front.
        // The front height is itself noise, which is what makes it billow instead of
        // sitting at a fixed line -- a smooth vertical falloff has no boundary at all.
        private const float FrontBase = 0.34F;    // mean height of the boundary
        private const float FrontWobble = 0.24F;  // how far the boundary billows
        private const float FrontScale = 5.0F;    // lateral size of the billows
        private const float FrontDrift = 0.05F;   // how fast the boundary slides sideways
        private const float TrailFalloff = 4.2F;  // how fast the wisps die below the front

        // Smoke is not uniform, so none of the above is applied evenly across the width.
        // Each column gets its own reach, its own sideways lean, and its own density, all
        // driven by slow noise in u. Without this the plume descends to a single depth
        // everywhere and falls straight down, which reads as an effect rather than as smoke.
        private const float ReachVariation = 0.75F; // +/- share of TrailFalloff per column
        private const float ReachScale = 3.0F;
        private const float ReachDrift = 0.03F;
        private const float LateralDrift = 3.0F;    // how far a tendril leans as it falls
        private const float DriftScale = 2.5F;
        private const float DriftSpeed = 0.02F;
        private const float PatchDepth = 0.09F;     // how much the smoke threshold varies
        private const float PatchScale = 1.8F;

        private const float BloomWeight = 0.55F;
        private const int BloomRadius = 2;
        private const float Exposure = 1.15F;
        private const float MaxAlpha = 0.85F;
        private const int MoteCount = 90;
        // Mote radius as a fraction of the header height. These are drawn at full
        // resolution rather than into the smoke buffer: at Downscale 8 a mote was
        // clamped to a single buffer pixel, so it could not be made any smaller and
        // upscaled to a soft 16px disc.
        private const float MoteSizeMin = 0.0045F;
        private const float MoteSizeSpan = 0.0115F;
        private const float MoteAlpha = 1.0F;
        // Motes are blue rather than taking the smoke's white, so they read as embers of
        // light in the plume instead of brighter specks of the same smoke.
        private const byte MoteR = 110;
        private const byte MoteG = 180;
        private const byte MoteB = 255;
        // The sprite carries a tight core inside a wide halo, so the drawn rectangle is
        // larger than the core. One draw per mote still, rather than a separate halo
        // pass. Keep this in step with the lobe widths in MotePixels: the two together
        // decide the glow's size, and the cost is the square of this number, so an
        // oversized sprite with narrow lobes pays for transparent pixels. At 4.5 with
        // the original lobes, 70% of every sprite was empty and the pass cost 13 ms.
        private const float MoteGlowScale = 2.4F;
        private const int MoteLevels = 24;   // pre-tinted brightness steps

        // The emission ramp, darkest to brightest: white smoke, with only a slight cool
        // lift so it sits with the rest of the palette. A saturated-blue ramp made the
        // plume look like coloured gas rather than lit smoke.
        private static readonly float[] RampStop = { 0.00F, 0.30F, 0.62F, 1.00F };
        private static readonly int[] RampR = { 10, 72, 168, 240 };
        private static readonly int[] RampG = { 12, 76, 173, 245 };
        private static readonly int[] RampB = { 16, 84, 182, 250 };

        private readonly int[] perm = new int[512];
        private readonly Random random = new Random(20260901);
        private readonly Mote[] motes = new Mote[MoteCount];

        private int width, height;
        private float[] field;
        private float[] scratch;
        private float[] colFront, colReach, colShear, colPatch;
        private byte[] pixels;
        private float time;
        private double lastRenderMs;
        // Per-stage timings, so the cost can be attributed rather than guessed at.
        private double msSmoke, msBloom, msMap, msBlit, msMotes;
        private int filledRows;   // deepest buffer row holding any smoke

        internal LightField()
        {
            int[] source = new int[256];
            for (int i = 0; i < 256; i++)
                source[i] = i;
            for (int i = 255; i > 0; i--)
            {
                int j = random.Next(i + 1);
                int swap = source[i];
                source[i] = source[j];
                source[j] = swap;
            }
            for (int i = 0; i < 512; i++)
                perm[i] = source[i & 255];

            for (int i = 0; i < MoteCount; i++)
            {
                motes[i] = new Mote();
                Respawn(motes[i], true);
            }
        }

        /// <summary>Milliseconds spent in the last Render, for the frame-budget check.</summary>
        internal double LastRenderMs { get { return lastRenderMs; } }
        internal double SmokeMs { get { return msSmoke; } }
        internal double BloomMs { get { return msBloom; } }
        internal double MapMs { get { return msMap; } }
        internal double BlitMs { get { return msBlit; } }
        internal double MotesMs { get { return msMotes; } }

        /// <summary>The emission buffer Compute last filled: BufferWidth x BufferHeight BGRA
        /// pixels, premultiplied by nothing, with smoke only in the first FilledRows rows.</summary>
        internal byte[] Pixels { get { return pixels; } }
        internal int BufferWidth { get { return width; } }
        internal int BufferHeight { get { return height; } }
        internal int FilledRows { get { return filledRows; } }
        internal static int MoteCountTotal { get { return MoteCount; } }
        internal static int MoteLevelCount { get { return MoteLevels; } }

        private void Respawn(Mote m, bool scatter)
        {
            m.X = (float)random.NextDouble();
            m.Y = scatter ? (float)random.NextDouble() : -(float)random.NextDouble() * 0.12F;
            // Scaled by 0.75 alongside the drop from 21.4 fps to 16 fps, so the distance
            // a mote covers between frames is unchanged and the motion stays as smooth as
            // it was. The fastest mote moves about 2.6px per frame either way, against a
            // bright core 1.5 to 5.2px across; much past that and it reads as a dot
            // reappearing rather than travelling. Ageing is tied to Fall, so a slower mote
            // also ages slower and still reaches the same depth before it dies.
            m.Fall = 0.0338F + (float)random.NextDouble() * 0.0825F;
            m.Drift = 0.012F + (float)random.NextDouble() * 0.035F;
            m.Phase = (float)(random.NextDouble() * Math.PI * 2);
            m.Size = MoteSizeMin + (float)random.NextDouble() * MoteSizeSpan;
            m.Life = 1F;
            m.Age = scatter ? (float)random.NextDouble() : 0F;
            m.Seed = 0.45F + (float)random.NextDouble() * 0.55F;
        }

        internal void Step(float seconds)
        {
            time += seconds;
            for (int i = 0; i < MoteCount; i++)
            {
                Mote m = motes[i];
                // Motes age by how far they have fallen, so a slow mote is not killed
                // early and the fall reaches the bottom of the header.
                m.Age += seconds * m.Fall / 1.15F;
                m.Y += seconds * m.Fall;
                m.Phase += seconds * 0.7F;
                if (m.Age >= m.Life || m.Y > 1.25F)
                    Respawn(m, false);
            }
        }

        /// <summary>The smoke for an area of AREAWIDTH x AREAHEIGHT pixels, into Pixels at
        /// 1/Downscale of that size. False when the area is too small to draw.</summary>
        internal bool Compute(int areaWidth, int areaHeight)
        {
            if (areaWidth < 8 || areaHeight < 8)
                return false;
            int w = Math.Max(8, areaWidth / Downscale);
            int h = Math.Max(8, areaHeight / Downscale);
            if (field == null || width != w || height != h)
            {
                width = w;
                height = h;
                field = new float[w * h];
                scratch = new float[w * h];
                colFront = new float[w];
                colReach = new float[w];
                colShear = new float[w];
                colPatch = new float[w];
                pixels = new byte[w * h * 4];
            }

            float aspect = areaWidth / (float)areaHeight;
            double freq = Stopwatch.Frequency / 1000.0;
            long t0 = Stopwatch.GetTimestamp();
            RenderSmoke(w, h, aspect);
            long t1 = Stopwatch.GetTimestamp();
            Bloom(w, h);
            long t2 = Stopwatch.GetTimestamp();
            MapToPixels(w, h);
            long t3 = Stopwatch.GetTimestamp();
            msSmoke = (t1 - t0) / freq;
            msBloom = (t2 - t1) / freq;
            msMap = (t3 - t2) / freq;
            return true;
        }

        /// <summary>Where mote INDEX is drawn and how bright: U and V across the area (0 to
        /// 1), its drawn radius as a share of the area's height, and which of the
        /// MoteLevels pre-tinted sprites. False when it is not drawn this frame.</summary>
        internal bool MoteAt(int index, out float u, out float v, out float radiusOfHeight, out int level)
        {
            Mote m = motes[index];
            u = v = radiusOfHeight = 0F;
            level = 0;
            float t = m.Age / Math.Max(0.001F, m.Life);
            float fade = t < 0.12F ? t / 0.12F : (t > 0.45F ? 1F - (t - 0.45F) / 0.55F : 1F);
            if (fade <= 0F)
                return false;

            float mx = m.X + (float)Math.Sin(m.Phase) * m.Drift;
            float my = m.Y;
            if (my < -0.05F || my > 1.05F)
                return false;

            // A mote is only as bright as the light reaching it.
            float bright = fade * m.Seed * LightAt(mx, my) * MoteAlpha * BottomFade(my);
            if (bright <= 0.004F)
                return false;
            if (bright > 1F)
                bright = 1F;

            // Pick a pre-tinted sprite rather than tinting at draw time. A
            // per-draw ColorMatrix puts GDI+ on a slow blit path, and the colour
            // never varies -- only the brightness, which quantises to these levels
            // without any visible banding on something this small and this soft.
            level = (int)(bright * (MoteLevels - 1) + 0.5F);
            if (level < 0) level = 0; else if (level >= MoteLevels) level = MoteLevels - 1;
            u = mx;
            v = my;
            radiusOfHeight = m.Size * MoteGlowScale;
            return true;
        }

        /// <summary>A tight bright core inside a wide soft halo -- two gaussian lobes
        /// rather than one falloff. The narrow lobe keeps the mote a definite point of
        /// light at a few pixels across; the broad lobe is the glow around it. Drawing
        /// one sprite that contains both is cheaper than a separate halo pass, and the
        /// core stays small because the narrow lobe is a small fraction of the sprite.
        /// SIZE x SIZE BGRA pixels, rows SIZE * 4 bytes apart.</summary>
        internal static byte[] MotePixels(int size, float level)
        {
            int stride = size * 4;
            byte[] px = new byte[stride * size];
            float centre = (size - 1) / 2F;
            for (int y = 0; y < size; y++)
            {
                for (int x = 0; x < size; x++)
                {
                    float dx = (x - centre) / centre;
                    float dy = (y - centre) / centre;
                    double d = Math.Sqrt(dx * dx + dy * dy);
                    double core = Math.Exp(-(d * d) / (2 * 0.1875 * 0.1875));
                    double halo = Math.Exp(-(d * d) / (2 * 0.55 * 0.55));
                    // Taper to exactly zero at the rim, or the square sprite shows its
                    // edges once the alpha is scaled up.
                    double edge = d >= 1.0 ? 0.0 : Math.Pow(1.0 - d, 1.5);
                    double a = Math.Min(1.0, 0.85 * core + 0.30 * halo) * edge * level;
                    int at = y * stride + x * 4;
                    px[at] = MoteB;
                    px[at + 1] = MoteG;
                    px[at + 2] = MoteR;
                    px[at + 3] = (byte)Math.Max(0, Math.Min(255, (int)(a * 255)));
                }
            }
            return px;
        }

        private void RenderSmoke(int w, int h, float aspect)
        {
            float evolve = time * EvolveSpeed;

            // Per-column variation, hoisted out of the pixel loop: it depends on u and
            // time but not on v, so evaluating it per column instead of per pixel costs
            // w noise samples a frame rather than w*h.
            for (int x = 0; x < w; x++)
            {
                float cu = (x + 0.5F) / w;
                colFront[x] = FrontBase + FrontWobble
                    * Noise(cu * FrontScale + time * FrontDrift, 7.3F, evolve);
                float reach = Noise(cu * ReachScale + time * ReachDrift, 21.5F, evolve * 0.4F);
                colReach[x] = Math.Max(0.6F, TrailFalloff * (1F + ReachVariation * 2F * reach));
                colShear[x] = LateralDrift
                    * Noise(cu * DriftScale + time * DriftSpeed, 33.1F, evolve * 0.4F);
                colPatch[x] = PatchDepth
                    * Noise(cu * PatchScale + time * 0.03F, 51.7F, evolve * 0.3F);
            }

            for (int y = 0; y < h; y++)
            {
                float v = (y + 0.5F) / h;

                for (int x = 0; x < w; x++)
                {
                    float u = (x + 0.5F) / w;

                    float lit = LightAt(u, v);
                    if (lit < 0.004F)
                    {
                        field[y * w + x] = 0F;
                        continue;
                    }

                    // Solid above the front, decaying into wisps below it, at a rate
                    // that differs column by column. The front is continuous at the
                    // boundary (exp(0) == 1), so there is no seam.
                    float below = v - colFront[x];
                    float shape = below <= 0F ? 1F
                        : (float)Math.Exp(-below * colReach[x]);

                    // Sample the plume in a frame that travels downward with it. The
                    // lateral offset grows with depth, so a tendril leans further the
                    // further it falls, and neighbouring columns lean different ways.
                    float nx = u * NoiseScale * aspect
                        + colShear[x] * (below <= 0F ? 0F : below);
                    float ny = (v - time * FlowSpeed) * NoiseScale * NoiseAspectY;

                    // Domain warp: offset the lookup by another noise field. This is what
                    // curdles the plume instead of leaving it as smooth drifting fog.
                    float wx = Fbm(nx + 3.1F, ny + 1.7F, evolve);
                    float wy = Fbm(nx - 2.4F, ny + 5.3F, evolve + 2.0F);
                    float n = Fbm(nx + WarpStrength * wx, ny + WarpStrength * wy, evolve);

                    // Beer-Lambert extinction rather than a linear ramp with a clamp.
                    // The clamp was what made the plume read as moving slabs: everything
                    // past the saturation point rendered as one flat opaque value, so
                    // large regions had no internal variation at all. An exponential
                    // approaches full opacity without ever reaching it, which is both how
                    // light actually attenuates through a medium and what keeps the smoke
                    // see-through.
                    float thickness = (n * 0.5F + 0.5F - (Threshold - colPatch[x])) * shape;
                    if (thickness <= 0F)
                    {
                        field[y * w + x] = 0F;
                        continue;
                    }
                    float dens = 1F - (float)Math.Exp(-thickness * DensityGain);

                    field[y * w + x] = dens * lit * Exposure * BottomFade(v);
                }
            }
        }

        /// <summary>The header's bottom. The smoke and the motes are drawn only inside the
        /// header, and in the columns where the plume reaches furthest they were still thick
        /// at its edge, so beside the card, which does not cover the window's margins, they
        /// stopped on a straight line (seen on the Mac's port of this code, 2026-09-30,
        /// docs/windows-changes-from-macos.md item 11). Over the lowest 30% of the header
        /// they fade to nothing, smoothly, as macos/installer-app/main.m's BottomFade.</summary>
        private static float BottomFade(float v)
        {
            const float start = 0.70F;
            if (v <= start)
                return 1F;
            if (v >= 1F)
                return 0F;
            float t = (1F - v) / (1F - start);
            return t * t * (3F - 2F * t);
        }

        /// <summary>Light entering from above the top edge, across the full width, dying
        /// with depth. Broken into irregular descending shafts so it reads as light coming
        /// through something rather than as a flat gradient -- the shafts are what make the
        /// effect visible while the source itself stays off-screen.</summary>
        private float LightAt(float u, float v)
        {
            if (v < 0F)
                v = 0F;
            float fall = (float)Math.Exp(-v * TopFalloff);
            float s = Noise(u * ShaftScale + time * ShaftDrift, 11.7F, 3.9F) * 0.5F + 0.5F;
            float shaft = 1F - ShaftStrength + ShaftStrength * s * s;
            return TopStrength * fall * shaft;
        }

        /// <summary>Separable box blur added back over the original. Two narrow passes are
        /// cheaper than one wide one and land close enough to a gaussian for a glow.</summary>
        private void Bloom(int w, int h)
        {
            int r = BloomRadius;
            float inv = 1F / (2 * r + 1);

            for (int y = 0; y < h; y++)
            {
                int row = y * w;
                for (int x = 0; x < w; x++)
                {
                    float sum = 0F;
                    for (int k = -r; k <= r; k++)
                    {
                        int sx = x + k;
                        if (sx < 0) sx = 0; else if (sx >= w) sx = w - 1;
                        sum += field[row + sx];
                    }
                    scratch[row + x] = sum * inv;
                }
            }
            for (int x = 0; x < w; x++)
            {
                for (int y = 0; y < h; y++)
                {
                    float sum = 0F;
                    for (int k = -r; k <= r; k++)
                    {
                        int sy = y + k;
                        if (sy < 0) sy = 0; else if (sy >= h) sy = h - 1;
                        sum += scratch[sy * w + x];
                    }
                    field[y * w + x] += sum * inv * BloomWeight;
                }
            }
        }

        private void MapToPixels(int w, int h)
        {
            int count = w * h;
            int deepest = 0;
            for (int i = 0; i < count; i++)
            {
                int at = i * 4;
                float e = field[i];
                if (e <= 0.002F)
                {
                    pixels[at] = 0;
                    pixels[at + 1] = 0;
                    pixels[at + 2] = 0;
                    pixels[at + 3] = 0;
                    continue;
                }
                if (e > 1F)
                    e = 1F;
                deepest = i / w;

                int stop = 0;
                while (stop < RampStop.Length - 2 && e > RampStop[stop + 1])
                    stop++;
                float span = RampStop[stop + 1] - RampStop[stop];
                float f = span <= 0F ? 0F : (e - RampStop[stop]) / span;
                if (f < 0F) f = 0F; else if (f > 1F) f = 1F;

                pixels[at] = (byte)(RampB[stop] + (RampB[stop + 1] - RampB[stop]) * f);
                pixels[at + 1] = (byte)(RampG[stop] + (RampG[stop + 1] - RampG[stop]) * f);
                pixels[at + 2] = (byte)(RampR[stop] + (RampR[stop + 1] - RampR[stop]) * f);
                // Alpha rises faster than colour so thin smoke is tinted, not merely dim.
                float a = e * 1.35F;
                if (a > 1F) a = 1F;
                pixels[at + 3] = (byte)(a * MaxAlpha * 255F);
            }
            filledRows = Math.Min(h, deepest + 2);   // one row of margin for the upscale
        }

        private float Fbm(float x, float y, float z)
        {
            float sum = 0F, amp = 0.5F, freq = 1F, norm = 0F;
            for (int i = 0; i < Octaves; i++)
            {
                sum += amp * Noise(x * freq, y * freq, z * freq);
                norm += amp;
                freq *= 2F;
                amp *= FbmGain;
            }
            // Normalised, so changing Octaves or FbmGain changes the character of the
            // noise without also changing its overall level -- otherwise every detail
            // tweak silently rescales the density and has to be re-tuned.
            return norm <= 0F ? 0F : sum * 0.5F / norm;
        }

        private static float Fade(float t) { return t * t * t * (t * (t * 6F - 15F) + 10F); }
        private static float Lerp(float a, float b, float t) { return a + (b - a) * t; }

        private static float Grad(int hash, float x, float y, float z)
        {
            int h = hash & 15;
            float u = h < 8 ? x : y;
            float v = h < 4 ? y : (h == 12 || h == 14 ? x : z);
            return ((h & 1) == 0 ? u : -u) + ((h & 2) == 0 ? v : -v);
        }

        /// <summary>Perlin improved gradient noise. Gradient rather than value noise:
        /// value noise leaves visible axis-aligned blocking once it is warped.</summary>
        private float Noise(float x, float y, float z)
        {
            int xi = (int)Math.Floor(x) & 255;
            int yi = (int)Math.Floor(y) & 255;
            int zi = (int)Math.Floor(z) & 255;
            x -= (float)Math.Floor(x);
            y -= (float)Math.Floor(y);
            z -= (float)Math.Floor(z);
            float u = Fade(x), v = Fade(y), t = Fade(z);

            int a = perm[xi] + yi, aa = perm[a] + zi, ab = perm[a + 1] + zi;
            int b = perm[xi + 1] + yi, ba = perm[b] + zi, bb = perm[b + 1] + zi;

            return Lerp(
                Lerp(Lerp(Grad(perm[aa], x, y, z), Grad(perm[ba], x - 1, y, z), u),
                     Lerp(Grad(perm[ab], x, y - 1, z), Grad(perm[bb], x - 1, y - 1, z), u), v),
                Lerp(Lerp(Grad(perm[aa + 1], x, y, z - 1), Grad(perm[ba + 1], x - 1, y, z - 1), u),
                     Lerp(Grad(perm[ab + 1], x, y - 1, z - 1), Grad(perm[bb + 1], x - 1, y - 1, z - 1), u), v),
                t);
        }
    }
}
