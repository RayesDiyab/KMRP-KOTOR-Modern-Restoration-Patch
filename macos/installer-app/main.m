/*
  KMRP Installer: the Windows patcher's window, over kmrp-mac.sh
  ----------------------------------------------------------------------------------------------
  The Mac installer is kmrp-mac.sh (macos/kmrp-mac.sh). This app carries it and the rest of the
  package in Contents/Resources/kmrp, runs it, and looks like the Windows patcher
  (src/patcher/KmrpPatcher.cs, MainForm; docs/patcher-ui-build.md): the same palette (UiTheme),
  the same header (the brand lockup, the tagline set to the wordmark's width, and LightField's
  smoke and motes, ported below), and the same four-step card with its badges, state labels,
  pill buttons, action row with the progress fill, Advanced Settings view and footer. Every
  position is the Windows design-space rectangle, scaled as FitInitialSizeToWorkingArea scales
  it. Windows' fonts are Microsoft's and cannot ship: DIN Alternate Bold, narrowed to 92%,
  stands in for Bahnschrift SemiCondensed (both DIN), and the system font for Segoe UI.

  What differs is what the Mac installs:
    1. Select Game       the Steam copy kmrp-mac.sh finds, or one chosen with Browse
    2. Verify Game       the unmodified Steam build (1.4.0), or KMRP already installed
    3. Choose Resolution this display first (native, every pixel, and on a Retina display half,
                         the size macOS lays windows out at), then resolutions.txt grouped by
                         shape, then a custom size, checked with kmrp-guiblend's dry run
    4. Apply Patch       kmrp-mac.sh install or uninstall
  and the two options (Advanced Settings), as on Windows: the area map's marker fixes
  (--no-map-notes when off) and controller support (--no-controller). The script's own stage lines drive the progress fill; its output goes to
  ~/Library/Logs/KMRP/installer.log, which Open Log opens.

  kmrp-mac.sh is passed: install --yes, --resolution native|half for this display's rows or
  --size WxH, --no-map-notes, --no-controller, --game when one was chosen; uninstall --yes; status --brief. What
  it refuses (the game running, another build, KotOR Patch Manager's files already there) it
  refuses here too, with its own message.

  Built by macos/build.sh for x86_64 and arm64, macOS 10.13 and later: the controller's SDL3
  and the installer's helpers need 10.13 (the game itself 10.11.6).

  For checking the app from a script (macos/README.md, "The installer app"), NSUserDefaults
  arguments after `open ... --args`:
    -KMRPSelect native|half|WxH   the resolution to select, or the custom size to use
    -KMRPRun install|uninstall    press the action button once the status is in
    -KMRPNoMapNotes YES           turn the map-marker fixes off
    -KMRPNoController YES         turn controller support off
    -KMRPSettings YES             show Advanced Settings
    -KMRPShowList YES             open the resolution list at its top and at its end
                                  (<prefix>-list.png, <prefix>-list-end.png), then close it
    -KMRPShowCustom YES           open the custom-size dialog (<prefix>-custom.png), then close it
    -KMRPSnapshot <prefix>        write <prefix>-ready.png when the window is ready,
                                  <prefix>-progress.png once a run is a third through, and
                                  <prefix>-done.png and <prefix>-log.txt when it ends
    -KMRPQuit YES                 quit after that
*/
#import <Cocoa/Cocoa.h>
#import <UniformTypeIdentifiers/UniformTypeIdentifiers.h>
#import <Accelerate/Accelerate.h>
#include <math.h>
#include <mach/mach_time.h>
#include <sys/xattr.h>

// ------------------------------------------------------------------------------ theme (UiTheme)

static NSColor *RGB(int r, int g, int b) { return [NSColor colorWithSRGBRed:r / 255.0 green:g / 255.0 blue:b / 255.0 alpha:1]; }
static NSColor *RGBA(int a, int r, int g, int b) {
    return [NSColor colorWithSRGBRed:r / 255.0 green:g / 255.0 blue:b / 255.0 alpha:a / 255.0];
}
#define THEME_WINDOW     RGB(7, 12, 21)
#define THEME_ACCENT     RGB(42, 198, 239)
#define THEME_ACCENT_STRONG RGB(0, 166, 214)
#define THEME_ACCENT_DARK RGB(0, 83, 116)
#define THEME_ACCENT_LIT RGB(96, 178, 255)
#define THEME_BORDER     RGB(34, 103, 132)
#define THEME_TEXT       RGB(236, 243, 248)
#define THEME_TEXT_MUTED RGB(177, 195, 208)
#define THEME_TEXT_FAINT RGB(122, 138, 154)
#define THEME_SUCCESS    RGB(126, 224, 171)
#define THEME_WARNING    RGB(255, 207, 112)
#define THEME_ERROR      RGB(255, 142, 142)
#define THEME_DISABLED   RGB(47, 56, 67)
#define THEME_DISABLED_TEXT RGB(139, 151, 164)
#define THEME_CARD       RGB(13, 21, 34)
#define THEME_CARD_HOVER RGB(19, 30, 47)
#define THEME_CARD_EDGE  RGB(31, 46, 69)
#define THEME_HAIRLINE   RGB(23, 34, 52)
#define THEME_BADGE      RGB(18, 28, 44)
#define THEME_BADGE_EDGE RGB(30, 45, 68)
#define THEME_FIELD      RGB(9, 15, 26)
#define THEME_AUTHOR     RGB(146, 170, 200)
#define THEME_GLYPH      RGB(92, 165, 250)

// The design space is Windows' (MainForm): 1981 x 1083 client pixels at uiScale 1, fonts in
// points at 96 dpi. S converts a design length to points at the window's scale.
static CGFloat gScale = 0.5;
static CGFloat S(CGFloat design) { return design * gScale; }
static CGFloat Pt(CGFloat points) { return points * 96.0 / 72.0 * gScale; }   // a WinForms point size

// Bahnschrift SemiCondensed Bold on Windows (UiTheme.DisplayFont): DIN, narrowed.
static NSFont *DisplayFont(CGFloat size) {
    if ([NSFont fontWithName:@"DINAlternate-Bold" size:size]) {
        const CGFloat matrix[6] = {size * 0.92, 0, 0, size, 0, 0};
        NSFont *font = [NSFont fontWithName:@"DINAlternate-Bold" matrix:matrix];
        if (font) return font;
    }
    return [NSFont systemFontOfSize:size weight:NSFontWeightBold];
}

// Segoe UI on Windows.
static NSFont *BodyFont(CGFloat size, NSFontWeight weight) { return [NSFont systemFontOfSize:size weight:weight]; }

// Text attributes AppKit and Core Text both read: Core Text takes its colour as a CGColor.
static NSDictionary *Ink(NSFont *font, NSColor *color) {
    return @{NSFontAttributeName: font, NSForegroundColorAttributeName: color,
             (__bridge NSString *)kCTForegroundColorAttributeName: (__bridge id)color.CGColor};
}

// All the window's text is one Core Text line drawn at an explicit baseline. AppKit's box
// drawing places the line box, not the letters: DIN's box has room above the capitals, so
// labels centred that way sat low (the action button's by about 5 pt, reported 2026-09-30),
// and a box shorter than the line clipped the descenders.
static void DrawAttributed(NSAttributedString *text, CGFloat x, CGFloat baseline, CGFloat width, NSTextAlignment align) {
    if (text.length == 0) return;
    CTLineRef line = CTLineCreateWithAttributedString((__bridge CFAttributedStringRef)text);
    double lineWidth = CTLineGetTypographicBounds(line, NULL, NULL, NULL);
    if (width > 0 && lineWidth > width) {
        NSAttributedString *dots = [[NSAttributedString alloc] initWithString:@"\u2026"
                                                                   attributes:[text attributesAtIndex:text.length - 1 effectiveRange:NULL]];
        CTLineRef ellipsis = CTLineCreateWithAttributedString((__bridge CFAttributedStringRef)dots);
        CTLineRef cut = CTLineCreateTruncatedLine(line, width, kCTLineTruncationEnd, ellipsis);
        CFRelease(ellipsis);
        if (cut) {
            CFRelease(line);
            line = cut;
            lineWidth = CTLineGetTypographicBounds(line, NULL, NULL, NULL);
        }
    }
    CGFloat left = x;
    if (align == NSTextAlignmentCenter) left = x + (width - lineWidth) / 2;
    else if (align == NSTextAlignmentRight) left = x + width - lineWidth;
    CGContextRef g = [NSGraphicsContext currentContext].CGContext;
    CGContextSaveGState(g);
    CGContextSetTextMatrix(g, CGAffineTransformMakeScale(1, -1));   // the views are flipped
    CGContextSetTextPosition(g, left, baseline);
    CTLineDraw(line, g);
    CGContextRestoreGState(g);
    CFRelease(line);
}

// The baseline that centres a line's capitals in `box`, which is where the eye puts its middle.
static CGFloat CentredBaseline(NSRect box, NSFont *font) { return NSMidY(box) + font.capHeight / 2; }

// A line in `box`: its capitals centred in it (`middle`), or its ascent from the box's top.
static void DrawText(NSString *text, NSRect box, NSFont *font, NSColor *color, NSTextAlignment align, BOOL middle) {
    if (!text.length) return;
    CGFloat baseline = middle ? CentredBaseline(box, font) : box.origin.y + font.ascender;
    DrawAttributed([[NSAttributedString alloc] initWithString:text attributes:Ink(font, color)], box.origin.x, baseline,
                   box.size.width, align);
}

// A line at a given baseline.
static void DrawLine(NSString *text, CGFloat x, CGFloat baseline, CGFloat width, NSFont *font, NSColor *color) {
    if (!text.length) return;
    DrawAttributed([[NSAttributedString alloc] initWithString:text attributes:Ink(font, color)], x, baseline, width,
                   NSTextAlignmentLeft);
}

static NSBezierPath *Rounded(NSRect r, CGFloat radius) {
    return [NSBezierPath bezierPathWithRoundedRect:r xRadius:radius yRadius:radius];
}

static void FillVertical(NSBezierPath *path, NSColor *top, NSColor *bottom) {
    // In the flipped views below, 90 degrees runs top to bottom, as on Windows.
    [[[NSGradient alloc] initWithStartingColor:top endingColor:bottom] drawInBezierPath:path angle:90];
}

// ------------------------------------------------------------------------------------ art

static NSMutableDictionary<NSString *, NSImage *> *gArt;
static NSMutableDictionary<NSString *, NSValue *> *gInk;

static NSImage *Art(NSString *name) {
    if (!gArt) gArt = [NSMutableDictionary dictionary];
    NSImage *image = gArt[name];
    if (!image) {
        image = [[NSImage alloc] initWithContentsOfFile:[[NSBundle mainBundle] pathForResource:name ofType:@"png"]];
        if (image) gArt[name] = image;
    }
    return image;
}

// The opaque bounds of an image, as a fraction of it from its top left (UiTheme.InkBoundsOf):
// the Settings gear carries a wide transparent margin.
static NSRect InkBounds(NSString *name, NSImage *image) {
    if (!gInk) gInk = [NSMutableDictionary dictionary];
    if (gInk[name]) return gInk[name].rectValue;
    NSRect result = NSMakeRect(0, 0, 1, 1);
    CGImageRef cg = [image CGImageForProposedRect:NULL context:nil hints:nil];
    if (cg) {
        size_t w = CGImageGetWidth(cg), h = CGImageGetHeight(cg);
        uint8_t *pixels = calloc(w * h, 4);
        CGColorSpaceRef space = CGColorSpaceCreateDeviceRGB();
        CGContextRef context = CGBitmapContextCreate(pixels, w, h, 8, w * 4, space, (CGBitmapInfo)kCGImageAlphaPremultipliedLast);
        CGContextDrawImage(context, CGRectMake(0, 0, w, h), cg);
        size_t minX = w, minY = h, maxX = 0, maxY = 0;
        for (size_t y = 0; y < h; y++)
            for (size_t x = 0; x < w; x++)
                if (pixels[(y * w + x) * 4 + 3] > 8) {
                    if (x < minX) minX = x;
                    if (x > maxX) maxX = x;
                    if (y < minY) minY = y;
                    if (y > maxY) maxY = y;
                }
        CGContextRelease(context);
        CGColorSpaceRelease(space);
        free(pixels);
        if (maxX >= minX)
            result = NSMakeRect((CGFloat)minX / w, (CGFloat)minY / h, (CGFloat)(maxX - minX + 1) / w,
                                (CGFloat)(maxY - minY + 1) / h);
    }
    gInk[name] = [NSValue valueWithRect:result];
    return result;
}

// Line art drawn as a silhouette in `color` (UiTheme.DrawIconMask): the artwork's alpha, our
// colour. `crop` draws only its ink, fitted and centred.
static void DrawArt(NSString *name, NSRect box, NSColor *color, BOOL crop) {
    NSImage *image = Art(name);
    if (!image || box.size.width < 1 || box.size.height < 1) return;
    NSRect from = NSMakeRect(0, 0, image.size.width, image.size.height);
    NSRect to = box;
    if (crop) {
        NSRect ink = InkBounds(name, image);
        from = NSMakeRect(ink.origin.x * image.size.width, (1 - ink.origin.y - ink.size.height) * image.size.height,
                          ink.size.width * image.size.width, ink.size.height * image.size.height);
        CGFloat fit = MIN(box.size.width / from.size.width, box.size.height / from.size.height);
        to = NSMakeRect(NSMidX(box) - from.size.width * fit / 2, NSMidY(box) - from.size.height * fit / 2,
                        from.size.width * fit, from.size.height * fit);
    }
    NSImage *tinted = [NSImage imageWithSize:to.size flipped:NO drawingHandler:^BOOL(NSRect rect) {
        [image drawInRect:rect fromRect:from operation:NSCompositingOperationSourceOver fraction:1];
        [color set];
        NSRectFillUsingOperation(rect, NSCompositingOperationSourceAtop);
        return YES;
    }];
    [tinted drawInRect:to fromRect:NSZeroRect operation:NSCompositingOperationSourceOver fraction:1
        respectFlipped:YES hints:@{NSImageHintInterpolation: @(NSImageInterpolationHigh)}];
}

// ---------------------------------------------------------------------- the smoke (LightField)
//
// A port of LightField: fBm Perlin noise, domain-warped, lit from above the top edge in
// descending shafts, with a noisy front the plume billows below; one emission buffer at 1/12
// of the header's pixels, a box bloom, the grey-white ramp, and 90 blue motes falling through
// it. Every constant is Windows', so the two look alike. It runs on a background queue at the
// Windows frame interval (62 ms); only the finished frame reaches the main thread.

enum { kDownscale = 12, kOctaves = 3, kMotes = 90, kMoteLevels = 24, kMoteSprite = 48 };
static const float kTopFalloff = 0.7f, kTopStrength = 1.10f, kShaftScale = 3.2f, kShaftStrength = 0.55f,
                   kShaftDrift = 0.035f, kNoiseScale = 8.0f, kFbmGain = 0.5f, kWarpStrength = 1.6f,
                   kFlowSpeed = 0.055f, kEvolveSpeed = 0.09f, kThreshold = 0.26f, kDensityGain = 3.3f,
                   kNoiseAspectY = 0.80f, kFrontBase = 0.34f, kFrontWobble = 0.24f, kFrontScale = 5.0f,
                   kFrontDrift = 0.05f, kTrailFalloff = 4.2f, kReachVariation = 0.75f, kReachScale = 3.0f,
                   kReachDrift = 0.03f, kLateralDrift = 3.0f, kDriftScale = 2.5f, kDriftSpeed = 0.02f,
                   kPatchDepth = 0.09f, kPatchScale = 1.8f, kBloomWeight = 0.55f, kExposure = 1.15f,
                   kMaxAlpha = 0.85f, kMoteSizeMin = 0.0045f, kMoteSizeSpan = 0.0115f, kMoteGlowScale = 2.4f;
static const int kBloomRadius = 2;
static const float kRampStop[4] = {0.00f, 0.30f, 0.62f, 1.00f};
static const int kRampR[4] = {10, 72, 168, 240}, kRampG[4] = {12, 76, 173, 245}, kRampB[4] = {16, 84, 182, 250};

typedef struct { float x, y, fall, drift, phase, size, age, life, seed; } Mote;

typedef struct {
    int perm[512];
    uint64_t rng;
    Mote motes[kMotes];
    float time;
    int w, h, filledRows;
    float *field, *scratch, *colFront, *colReach, *colShear, *colPatch;
    uint8_t *pixels;   // RGBA, premultiplied
} Smoke;

static double Random01(Smoke *s) {   // xorshift64*, seeded from Windows' System.Random seed
    s->rng ^= s->rng >> 12;
    s->rng ^= s->rng << 25;
    s->rng ^= s->rng >> 27;
    return (double)((s->rng * 2685821657736338717ULL) >> 11) / 9007199254740992.0;
}

static float Fade(float t) { return t * t * t * (t * (t * 6 - 15) + 10); }
static float Lerp(float a, float b, float t) { return a + (b - a) * t; }
static float Grad(int hash, float x, float y, float z) {
    int h = hash & 15;
    float u = h < 8 ? x : y;
    float v = h < 4 ? y : (h == 12 || h == 14 ? x : z);
    return ((h & 1) == 0 ? u : -u) + ((h & 2) == 0 ? v : -v);
}

static float Noise(const Smoke *s, float x, float y, float z) {   // Perlin's improved noise
    int xi = (int)floorf(x) & 255, yi = (int)floorf(y) & 255, zi = (int)floorf(z) & 255;
    x -= floorf(x); y -= floorf(y); z -= floorf(z);
    float u = Fade(x), v = Fade(y), t = Fade(z);
    const int *p = s->perm;
    int a = p[xi] + yi, aa = p[a] + zi, ab = p[a + 1] + zi;
    int b = p[xi + 1] + yi, ba = p[b] + zi, bb = p[b + 1] + zi;
    return Lerp(Lerp(Lerp(Grad(p[aa], x, y, z), Grad(p[ba], x - 1, y, z), u),
                     Lerp(Grad(p[ab], x, y - 1, z), Grad(p[bb], x - 1, y - 1, z), u), v),
                Lerp(Lerp(Grad(p[aa + 1], x, y, z - 1), Grad(p[ba + 1], x - 1, y, z - 1), u),
                     Lerp(Grad(p[ab + 1], x, y - 1, z - 1), Grad(p[bb + 1], x - 1, y - 1, z - 1), u), v), t);
}

static float Fbm(const Smoke *s, float x, float y, float z) {
    float sum = 0, amp = 0.5f, freq = 1, norm = 0;
    for (int i = 0; i < kOctaves; i++) {
        sum += amp * Noise(s, x * freq, y * freq, z * freq);
        norm += amp;
        freq *= 2;
        amp *= kFbmGain;
    }
    return norm <= 0 ? 0 : sum * 0.5f / norm;
}

static float LightAt(const Smoke *s, float u, float v) {
    if (v < 0) v = 0;
    float fall = expf(-v * kTopFalloff);
    float n = Noise(s, u * kShaftScale + s->time * kShaftDrift, 11.7f, 3.9f) * 0.5f + 0.5f;
    return kTopStrength * fall * (1 - kShaftStrength + kShaftStrength * n * n);
}

static void Respawn(Smoke *s, Mote *m, int scatter) {
    m->x = (float)Random01(s);
    m->y = scatter ? (float)Random01(s) : -(float)Random01(s) * 0.12f;
    m->fall = 0.0338f + (float)Random01(s) * 0.0825f;
    m->drift = 0.012f + (float)Random01(s) * 0.035f;
    m->phase = (float)(Random01(s) * M_PI * 2);
    m->size = kMoteSizeMin + (float)Random01(s) * kMoteSizeSpan;
    m->life = 1;
    m->age = scatter ? (float)Random01(s) : 0;
    m->seed = 0.45f + (float)Random01(s) * 0.55f;
}

static void SmokeInit(Smoke *s) {
    memset(s, 0, sizeof *s);
    s->rng = 20260901ULL * 2654435761ULL + 1;
    int source[256];
    for (int i = 0; i < 256; i++) source[i] = i;
    for (int i = 255; i > 0; i--) {
        int j = (int)(Random01(s) * (i + 1));
        int swap = source[i]; source[i] = source[j]; source[j] = swap;
    }
    for (int i = 0; i < 512; i++) s->perm[i] = source[i & 255];
    for (int i = 0; i < kMotes; i++) Respawn(s, &s->motes[i], 1);
}

static void SmokeStep(Smoke *s, float seconds) {
    s->time += seconds;
    for (int i = 0; i < kMotes; i++) {
        Mote *m = &s->motes[i];
        m->age += seconds * m->fall / 1.15f;
        m->y += seconds * m->fall;
        m->phase += seconds * 0.7f;
        if (m->age >= m->life || m->y > 1.25f) Respawn(s, m, 0);
    }
}

// Renders the emission buffer for a header of pixelWidth x pixelHeight into s->pixels.
static void SmokeRender(Smoke *s, int pixelWidth, int pixelHeight) {
    int w = MAX(8, pixelWidth / kDownscale), h = MAX(8, pixelHeight / kDownscale);
    if (w != s->w || h != s->h) {
        free(s->field); free(s->scratch); free(s->colFront); free(s->colReach); free(s->colShear);
        free(s->colPatch); free(s->pixels);
        s->w = w; s->h = h;
        s->field = calloc(w * h, sizeof(float));
        s->scratch = calloc(w * h, sizeof(float));
        s->colFront = calloc(w, sizeof(float));
        s->colReach = calloc(w, sizeof(float));
        s->colShear = calloc(w, sizeof(float));
        s->colPatch = calloc(w, sizeof(float));
        s->pixels = calloc(w * h, 4);
    }
    float aspect = pixelWidth / (float)pixelHeight;
    float evolve = s->time * kEvolveSpeed;
    for (int x = 0; x < w; x++) {
        float cu = (x + 0.5f) / w;
        s->colFront[x] = kFrontBase + kFrontWobble * Noise(s, cu * kFrontScale + s->time * kFrontDrift, 7.3f, evolve);
        float reach = Noise(s, cu * kReachScale + s->time * kReachDrift, 21.5f, evolve * 0.4f);
        s->colReach[x] = fmaxf(0.6f, kTrailFalloff * (1 + kReachVariation * 2 * reach));
        s->colShear[x] = kLateralDrift * Noise(s, cu * kDriftScale + s->time * kDriftSpeed, 33.1f, evolve * 0.4f);
        s->colPatch[x] = kPatchDepth * Noise(s, cu * kPatchScale + s->time * 0.03f, 51.7f, evolve * 0.3f);
    }
    for (int y = 0; y < h; y++) {
        float v = (y + 0.5f) / h;
        for (int x = 0; x < w; x++) {
            float u = (x + 0.5f) / w;
            float lit = LightAt(s, u, v);
            float *out = &s->field[y * w + x];
            if (lit < 0.004f) { *out = 0; continue; }
            float below = v - s->colFront[x];
            float shape = below <= 0 ? 1 : expf(-below * s->colReach[x]);
            float nx = u * kNoiseScale * aspect + s->colShear[x] * (below <= 0 ? 0 : below);
            float ny = (v - s->time * kFlowSpeed) * kNoiseScale * kNoiseAspectY;
            float wx = Fbm(s, nx + 3.1f, ny + 1.7f, evolve);
            float wy = Fbm(s, nx - 2.4f, ny + 5.3f, evolve + 2.0f);
            float n = Fbm(s, nx + kWarpStrength * wx, ny + kWarpStrength * wy, evolve);
            float thickness = (n * 0.5f + 0.5f - (kThreshold - s->colPatch[x])) * shape;
            if (thickness <= 0) { *out = 0; continue; }
            *out = (1 - expf(-thickness * kDensityGain)) * lit * kExposure;
        }
    }
    // Bloom: a separable box blur added back over the original.
    float inv = 1.0f / (2 * kBloomRadius + 1);
    for (int y = 0; y < h; y++)
        for (int x = 0; x < w; x++) {
            float sum = 0;
            for (int k = -kBloomRadius; k <= kBloomRadius; k++) sum += s->field[y * w + MIN(MAX(x + k, 0), w - 1)];
            s->scratch[y * w + x] = sum * inv;
        }
    for (int x = 0; x < w; x++)
        for (int y = 0; y < h; y++) {
            float sum = 0;
            for (int k = -kBloomRadius; k <= kBloomRadius; k++) sum += s->scratch[MIN(MAX(y + k, 0), h - 1) * w + x];
            s->field[y * w + x] += sum * inv * kBloomWeight;
        }
    // The ramp.
    int deepest = 0;
    for (int i = 0; i < w * h; i++) {
        uint8_t *px = &s->pixels[i * 4];
        float e = s->field[i];
        if (e <= 0.002f) { px[0] = px[1] = px[2] = px[3] = 0; continue; }
        if (e > 1) e = 1;
        deepest = i / w;
        int stop = 0;
        while (stop < 2 && e > kRampStop[stop + 1]) stop++;
        float span = kRampStop[stop + 1] - kRampStop[stop];
        float f = span <= 0 ? 0 : fminf(fmaxf((e - kRampStop[stop]) / span, 0), 1);
        float a = fminf(e * 1.35f, 1) * kMaxAlpha;
        px[0] = (uint8_t)((kRampR[stop] + (kRampR[stop + 1] - kRampR[stop]) * f) * a);
        px[1] = (uint8_t)((kRampG[stop] + (kRampG[stop + 1] - kRampG[stop]) * f) * a);
        px[2] = (uint8_t)((kRampB[stop] + (kRampB[stop + 1] - kRampB[stop]) * f) * a);
        px[3] = (uint8_t)(a * 255);
    }
    s->filledRows = MIN(h, deepest + 2);
}

static void FreeFrame(void *info, const void *data, size_t size) { free((void *)data); }

// A tight bright core inside a wide soft halo, at one of kMoteLevels brightnesses.
static CGImageRef MoteSprite(float level) {
    int size = kMoteSprite;
    uint8_t *px = calloc(size * size, 4);
    float centre = (size - 1) / 2.0f;
    for (int y = 0; y < size; y++)
        for (int x = 0; x < size; x++) {
            float dx = (x - centre) / centre, dy = (y - centre) / centre;
            double d = sqrt(dx * dx + dy * dy);
            double core = exp(-(d * d) / (2 * 0.1875 * 0.1875)), halo = exp(-(d * d) / (2 * 0.55 * 0.55));
            double edge = d >= 1.0 ? 0.0 : pow(1.0 - d, 1.5);
            double a = fmin(1.0, 0.85 * core + 0.30 * halo) * edge * level;
            uint8_t *p = &px[(y * size + x) * 4];
            p[0] = (uint8_t)(110 * a); p[1] = (uint8_t)(180 * a); p[2] = (uint8_t)(255 * a); p[3] = (uint8_t)(a * 255);
        }
    CGColorSpaceRef space = CGColorSpaceCreateDeviceRGB();
    CGContextRef context = CGBitmapContextCreate(px, size, size, 8, size * 4, space, (CGBitmapInfo)kCGImageAlphaPremultipliedLast);
    CGImageRef image = CGBitmapContextCreateImage(context);
    CGContextRelease(context);
    CGColorSpaceRelease(space);
    free(px);
    return image;
}

// ------------------------------------------------------------------------------ the views

@interface KMRPFlippedView : NSView
@end
@implementation KMRPFlippedView
- (BOOL)isFlipped { return YES; }
@end

static NSString *const kTagline = @"M O D E R N .   R E S T O R E D .   S I M P L E .";
static const double kWordmarkInkLeft = 0.0216, kWordmarkInkRight = 0.9774;

// The window's surface: the header (smoke, then the brand and tagline) over Window blue.
@interface KMRPRootView : KMRPFlippedView
@property (nonatomic) CGFloat headerHeight, brandWidth, brandHeight;
@property (nonatomic) CGImageRef smokeFrame;         // retained: the smoke, upscaled to the header's pixels
@property (nonatomic) CGFloat smokeHeight;           // how far down it reaches, in points
@property (nonatomic, strong) NSArray<NSValue *> *moteRects;
@property (nonatomic, strong) NSArray<NSNumber *> *moteLevels;
@end

@implementation KMRPRootView {
    CGImageRef _sprites[kMoteLevels];
    NSFont *_taglineFont;
}

- (void)setSmokeFrame:(CGImageRef)frame {
    if (_smokeFrame) CGImageRelease(_smokeFrame);
    _smokeFrame = frame ? CGImageRetain(frame) : NULL;
}

- (void)drawRect:(NSRect)dirty {
    [THEME_WINDOW setFill];
    NSRectFill(dirty);
    NSRect header = NSMakeRect(0, 0, self.bounds.size.width, self.headerHeight);
    if (!NSIntersectsRect(dirty, header)) return;
    CGContextRef g = [NSGraphicsContext currentContext].CGContext;

    if (self.smokeFrame && self.smokeHeight > 0) {
        CGContextSaveGState(g);
        CGContextTranslateCTM(g, 0, self.smokeHeight);   // the view is flipped; images draw bottom up
        CGContextScaleCTM(g, 1, -1);
        CGContextDrawImage(g, CGRectMake(0, 0, header.size.width, self.smokeHeight), self.smokeFrame);
        CGContextRestoreGState(g);
    }
    if (!_sprites[0])
        for (int i = 0; i < kMoteLevels; i++) _sprites[i] = MoteSprite((i + 1) / (float)kMoteLevels);
    for (NSUInteger i = 0; i < self.moteRects.count; i++)
        CGContextDrawImage(g, NSRectToCGRect(self.moteRects[i].rectValue), _sprites[self.moteLevels[i].intValue]);

    // The lockup and the tagline (MainForm.PaintBrandLayer).
    NSImage *brand = Art(@"brand");
    CGFloat top = S(14), taglineTop = S(30);
    if (brand) {
        NSRect box = NSMakeRect(round((self.bounds.size.width - self.brandWidth) / 2), top, self.brandWidth, self.brandHeight);
        [brand drawInRect:box fromRect:NSZeroRect operation:NSCompositingOperationSourceOver fraction:1
           respectFlipped:YES hints:@{NSImageHintInterpolation: @(NSImageInterpolationHigh)}];
        taglineTop = top + self.brandHeight + S(2);
    }
    if (!_taglineFont) {
        // Set to the width of the wordmark's ink, not of the image, which carries glow past it.
        CGFloat target = (kWordmarkInkRight - kWordmarkInkLeft) * self.brandWidth;
        NSFont *probe = BodyFont(Pt(20), NSFontWeightBold);
        CGFloat measured = [kTagline sizeWithAttributes:Ink(probe, THEME_ACCENT)].width;
        _taglineFont = BodyFont(measured > 1 ? probe.pointSize * target / measured : Pt(10.5), NSFontWeightBold);
    }
    DrawText(kTagline, NSMakeRect(0, taglineTop, self.bounds.size.width, S(60)), _taglineFont, THEME_ACCENT,
             NSTextAlignmentCenter, NO);
}

@end

// CardPanel: a rounded, faintly lit card.
@interface KMRPCard : KMRPFlippedView
@end
@implementation KMRPCard
- (void)drawRect:(NSRect)dirty {
    NSBezierPath *path = Rounded(NSInsetRect(self.bounds, 0.5, 0.5), S(14));
    [THEME_CARD setFill];
    [path fill];
    [THEME_CARD_EDGE setStroke];
    path.lineWidth = 1;
    [path stroke];
}
@end

// StepRow: a lit glyph badge, a title, a subtitle, and room on the right.
@interface KMRPStep : KMRPFlippedView
@property (nonatomic, copy) NSString *title, *subtitle, *icon;
@property (nonatomic) BOOL dimmed, separator;
@property (nonatomic) CGFloat textRight;   // design pixels kept clear on the right for the step's control
@end
@implementation KMRPStep
- (void)setTitle:(NSString *)title { _title = [title copy]; self.needsDisplay = YES; }
- (void)setSubtitle:(NSString *)subtitle { _subtitle = [subtitle copy]; self.needsDisplay = YES; }
- (void)setDimmed:(BOOL)dimmed { _dimmed = dimmed; self.needsDisplay = YES; }
- (void)drawRect:(NSRect)dirty {
    CGFloat width = self.bounds.size.width, header = S(96);
    if (self.separator) {
        NSBezierPath *line = [NSBezierPath bezierPath];
        [line moveToPoint:NSMakePoint(S(26), self.bounds.size.height - 0.5)];
        [line lineToPoint:NSMakePoint(width - S(26), self.bounds.size.height - 0.5)];
        line.lineWidth = MAX(1, gScale);
        [THEME_HAIRLINE setStroke];
        [line stroke];
    }
    NSRect circle = NSMakeRect(S(28), (header - S(64)) / 2, S(64), S(64));
    NSBezierPath *disc = [NSBezierPath bezierPathWithOvalInRect:circle];
    [THEME_BADGE setFill];
    [disc fill];
    [THEME_BADGE_EDGE setStroke];
    [disc stroke];
    CGFloat side = circle.size.width * 0.563;   // UiTheme.DrawIconArt
    DrawArt(self.icon, NSMakeRect(NSMidX(circle) - side / 2, NSMidY(circle) - side / 2, side, side),
            self.dimmed ? THEME_TEXT_FAINT : THEME_GLYPH, NO);
    CGFloat left = S(120), textWidth = width - left - S(self.textRight > 0 ? self.textRight : 40);
    // Windows draws each from a point (title at header/2 - 30, subtitle at header/2 + 4),
    // which puts the baselines about 30 apart.
    // The two lines' baselines 30 apart, as on Windows, and the block from the title's
    // capitals to the subtitle's baseline centred on the badge.
    NSFont *titleFont = DisplayFont(Pt(22)), *subtitleFont = BodyFont(Pt(16.5), NSFontWeightRegular);
    CGFloat apart = S(30), titleBaseline = header / 2 + (titleFont.capHeight - apart) / 2;
    DrawLine(self.title, left, titleBaseline, textWidth, titleFont, self.dimmed ? THEME_TEXT_FAINT : THEME_TEXT);
    DrawLine(self.subtitle, left, titleBaseline + apart, textWidth, subtitleFont,
             self.dimmed ? THEME_TEXT_FAINT : THEME_TEXT_MUTED);
}
@end

// StateLabel: a right-aligned status, optionally with the verified or missing badge.
@interface KMRPState : KMRPFlippedView
@property (nonatomic, copy) NSString *text, *badge;   // badge: nil, "verified" or "missing"
@property (nonatomic, strong) NSColor *color;
- (void)set:(NSString *)text color:(NSColor *)color badge:(NSString *)badge;
@end
@implementation KMRPState
- (void)set:(NSString *)text color:(NSColor *)color badge:(NSString *)badge {
    self.text = text;
    self.color = color;
    self.badge = badge;
    self.needsDisplay = YES;
}
- (void)drawRect:(NSRect)dirty {
    NSFont *font = DisplayFont(Pt(18));
    NSColor *color = self.color ?: THEME_TEXT_MUTED;
    CGFloat textWidth = MIN(self.bounds.size.width, ceil([self.text ?: @"" sizeWithAttributes:Ink(font, color)].width));
    if (self.badge) {
        BOOL iconOnly = self.text.length == 0;
        CGFloat icon = S(iconOnly ? 48 : 32), gap = iconOnly ? 0 : S(8);
        CGFloat group = MIN(self.bounds.size.width, icon + gap + (iconOnly ? 0 : textWidth));
        NSRect box = NSMakeRect(self.bounds.size.width - group, (self.bounds.size.height - icon) / 2, icon, icon);
        DrawArt(self.badge, box, color, NO);
        if (!iconOnly)
            DrawText(self.text, NSMakeRect(NSMaxX(box) + gap, 0, textWidth + 2, self.bounds.size.height), font, color,
                     NSTextAlignmentLeft, YES);
        return;
    }
    DrawText(self.text ?: @"", self.bounds, font, color, NSTextAlignmentRight, YES);
}
@end

// PillButton: the primary gets the lit gradient and, while working, the progress fill.
@interface KMRPPill : KMRPFlippedView
@property (nonatomic, copy) NSString *text, *iconName;
@property (nonatomic) BOOL primary, subtle, enabled;
@property (nonatomic) CGFloat textPoints;
@property (nonatomic) int progress;                  // -1 when not working
@property (nonatomic, weak) id target;
@property (nonatomic) SEL action;
@end
@implementation KMRPPill {
    BOOL _hover, _down;
}
- (instancetype)initWithFrame:(NSRect)frame {
    if ((self = [super initWithFrame:frame])) { _enabled = YES; _progress = -1; }
    return self;
}
- (void)setText:(NSString *)text { _text = [text copy]; self.needsDisplay = YES; }
- (void)setEnabled:(BOOL)enabled { _enabled = enabled; self.needsDisplay = YES; [self.window invalidateCursorRectsForView:self]; }
- (void)setProgress:(int)progress { _progress = progress; self.needsDisplay = YES; }
- (void)updateTrackingAreas {
    for (NSTrackingArea *area in self.trackingAreas) [self removeTrackingArea:area];
    [self addTrackingArea:[[NSTrackingArea alloc] initWithRect:self.bounds
                                                       options:NSTrackingMouseEnteredAndExited | NSTrackingActiveInKeyWindow
                                                         owner:self userInfo:nil]];
    [super updateTrackingAreas];
}
- (void)mouseEntered:(NSEvent *)event { _hover = YES; self.needsDisplay = YES; }
- (void)mouseExited:(NSEvent *)event { _hover = NO; _down = NO; self.needsDisplay = YES; }
- (void)resetCursorRects { if (self.enabled) [self addCursorRect:self.bounds cursor:[NSCursor pointingHandCursor]]; }
- (void)mouseDown:(NSEvent *)event {
    if (!self.enabled || self.progress >= 0) return;
    _down = YES;
    self.needsDisplay = YES;
}
- (void)mouseUp:(NSEvent *)event {
    BOOL inside = NSPointInRect([self convertPoint:event.locationInWindow fromView:nil], self.bounds);
    BOOL fire = _down && inside && self.enabled;
    _down = NO;
    self.needsDisplay = YES;
    if (fire && self.target) [NSApp sendAction:self.action to:self.target from:self];
}
- (void)drawRect:(NSRect)dirty {
    NSRect r = NSInsetRect(self.bounds, 0.5, 0.5);
    NSBezierPath *path = Rounded(r, S(8));
    BOOL working = self.progress >= 0;
    if (working) {
        FillVertical(path, THEME_ACCENT_DARK, RGB(0, 112, 151));
        CGFloat filled = round(self.bounds.size.width * self.progress / 100.0);
        if (filled > 0) {
            [NSGraphicsContext saveGraphicsState];
            [path addClip];
            NSRect fill = NSMakeRect(0, 0, filled, self.bounds.size.height);
            FillVertical([NSBezierPath bezierPathWithRect:fill], RGB(116, 171, 193), RGB(59, 132, 162));
            NSRect shine = NSMakeRect(0, 0, filled, round(self.bounds.size.height * 0.48));
            FillVertical([NSBezierPath bezierPathWithRect:shine], RGBA(34, 255, 255, 255), RGBA(0, 255, 255, 255));
            if (filled < self.bounds.size.width) {
                NSBezierPath *edge = [NSBezierPath bezierPath];
                [edge moveToPoint:NSMakePoint(filled, MAX(3, S(6)))];
                [edge lineToPoint:NSMakePoint(filled, self.bounds.size.height - MAX(3, S(6)))];
                edge.lineWidth = MAX(1, 1.4 * gScale);
                [RGBA(145, 170, 205, 220) setStroke];
                [edge stroke];
            }
            [NSGraphicsContext restoreGraphicsState];
        }
        [RGBA(105, 119, 177, 202) setStroke];
        [path stroke];
    } else if (!self.enabled) {
        [THEME_DISABLED setFill];
        [path fill];
    } else if (self.primary) {
        NSColor *top = _down ? THEME_ACCENT_DARK : (_hover ? THEME_ACCENT_LIT : THEME_ACCENT);
        NSColor *bottom = _down ? THEME_ACCENT_DARK : THEME_ACCENT_STRONG;
        FillVertical(path, top, bottom);
    } else {
        [(_hover ? THEME_CARD_HOVER : THEME_CARD) setFill];
        [path fill];
        [(_hover ? THEME_ACCENT : (self.subtle ? THEME_BORDER : THEME_CARD_EDGE)) setStroke];
        [path stroke];
    }
    NSColor *ink = working ? NSColor.whiteColor
        : (!self.enabled ? THEME_DISABLED_TEXT
            : (self.primary ? NSColor.whiteColor : (self.subtle && !_hover ? THEME_TEXT_MUTED : THEME_TEXT)));
    if (self.iconName) {
        CGFloat side = round(MIN(self.bounds.size.width, self.bounds.size.height) * 0.74);
        DrawArt(self.iconName, NSMakeRect((self.bounds.size.width - side) / 2, (self.bounds.size.height - side) / 2, side, side),
                ink, YES);
        return;
    }
    NSFont *font = DisplayFont(Pt(self.textPoints > 0 ? self.textPoints : (self.primary ? 18 : 15.5)));
    if (working)
        DrawText(self.text, NSOffsetRect(self.bounds, 0, MAX(1, gScale)), font, RGBA(115, 0, 39, 58), NSTextAlignmentCenter, YES);
    DrawText(self.text, self.bounds, font, ink, NSTextAlignmentCenter, YES);
}
@end

// DarkCombo: the dark resolution field with its chevron; the list opens as a menu.
@interface KMRPCombo : KMRPFlippedView
@property (nonatomic, copy) NSString *text, *detail;
@property (nonatomic) BOOL enabled;
@property (nonatomic, weak) id target;
@property (nonatomic) SEL action;
@end
@implementation KMRPCombo
- (void)setText:(NSString *)text { _text = [text copy]; self.needsDisplay = YES; }
- (void)setEnabled:(BOOL)enabled { _enabled = enabled; self.needsDisplay = YES; }
- (void)resetCursorRects { if (self.enabled) [self addCursorRect:self.bounds cursor:[NSCursor pointingHandCursor]]; }
- (void)mouseDown:(NSEvent *)event {
    if (self.enabled && self.target) [NSApp sendAction:self.action to:self.target from:self];
}
- (void)drawRect:(NSRect)dirty {
    [THEME_FIELD setFill];
    NSRectFill(self.bounds);
    NSBezierPath *edge = [NSBezierPath bezierPathWithRect:NSInsetRect(self.bounds, 0.5, 0.5)];
    edge.lineWidth = MAX(1, gScale);
    [THEME_CARD_EDGE setStroke];
    [edge stroke];
    CGFloat button = MAX(18, S(30));
    NSMutableAttributedString *line = [[NSMutableAttributedString alloc]
        initWithString:self.text ?: @"" attributes:Ink(BodyFont(Pt(17), NSFontWeightSemibold), self.enabled ? THEME_TEXT : THEME_TEXT_FAINT)];
    if (self.detail.length)
        [line appendAttributedString:[[NSAttributedString alloc] initWithString:[@"   ·   " stringByAppendingString:self.detail]
                                                                     attributes:Ink(BodyFont(Pt(13), NSFontWeightRegular), THEME_TEXT_MUTED)]];
    DrawAttributed(line, S(10), CentredBaseline(self.bounds, BodyFont(Pt(17), NSFontWeightSemibold)),
                   self.bounds.size.width - S(10) - button - S(4), NSTextAlignmentLeft);
    // The chevron (DarkCombo.WndProc), in the button's column on the right.
    CGFloat s = MAX(gScale * 1.6, 1), cx = self.bounds.size.width - button / 2 - 1, cy = self.bounds.size.height / 2 + 0.5;
    NSBezierPath *chevron = [NSBezierPath bezierPath];
    [chevron moveToPoint:NSMakePoint(cx - 4.5 * s, cy - 2 * s)];
    [chevron lineToPoint:NSMakePoint(cx, cy + 2.5 * s)];
    [chevron lineToPoint:NSMakePoint(cx + 4.5 * s, cy - 2 * s)];
    chevron.lineWidth = MAX(1, 1.6 * s * 0.8);
    chevron.lineCapStyle = NSLineCapStyleRound;
    chevron.lineJoinStyle = NSLineJoinStyleRound;
    [THEME_TEXT_MUTED setStroke];
    [chevron stroke];
}
@end

// OptionToggle: a component with its author, a description, and a switch.
@interface KMRPToggle : KMRPFlippedView
@property (nonatomic, copy) NSString *title, *author, *detail;
@property (nonatomic) BOOL on;
@property (nonatomic, copy) void (^changed)(BOOL on);
@end
@implementation KMRPToggle {
    BOOL _hover;
}
- (void)setOn:(BOOL)on { _on = on; self.needsDisplay = YES; }
- (void)updateTrackingAreas {
    for (NSTrackingArea *area in self.trackingAreas) [self removeTrackingArea:area];
    [self addTrackingArea:[[NSTrackingArea alloc] initWithRect:self.bounds
                                                       options:NSTrackingMouseEnteredAndExited | NSTrackingActiveInKeyWindow
                                                         owner:self userInfo:nil]];
    [super updateTrackingAreas];
}
- (void)mouseEntered:(NSEvent *)event { _hover = YES; self.needsDisplay = YES; }
- (void)mouseExited:(NSEvent *)event { _hover = NO; self.needsDisplay = YES; }
- (void)resetCursorRects { [self addCursorRect:self.bounds cursor:[NSCursor pointingHandCursor]]; }
- (void)mouseDown:(NSEvent *)event {}
- (void)mouseUp:(NSEvent *)event {
    if (!NSPointInRect([self convertPoint:event.locationInWindow fromView:nil], self.bounds)) return;
    self.on = !self.on;
    if (self.changed) self.changed(self.on);
}
- (void)drawRect:(NSRect)dirty {
    NSBezierPath *body = Rounded(NSInsetRect(self.bounds, 0.5, 0.5), S(10));
    [(_hover ? THEME_CARD_HOVER : THEME_BADGE) setFill];
    [body fill];
    [(_hover ? THEME_BORDER : THEME_CARD_EDGE) setStroke];
    [body stroke];
    CGFloat pad = S(20), switchWidth = S(64), switchHeight = S(32), gutter = S(18);
    CGFloat switchLeft = self.bounds.size.width - pad - switchWidth, textWidth = switchLeft - gutter - pad;
    NSFont *titleFont = BodyFont(Pt(17), NSFontWeightSemibold), *small = BodyFont(Pt(13.5), NSFontWeightRegular);
    CGFloat titleTop = pad * 0.72, titleHeight = ceil(titleFont.ascender - titleFont.descender);
    DrawText(self.title, NSMakeRect(pad, titleTop, textWidth, titleHeight + 2), titleFont, THEME_TEXT, NSTextAlignmentLeft, NO);
    if (self.author.length)
        DrawAttributed([[NSAttributedString alloc] initWithString:[@"by " stringByAppendingString:self.author]
                                                       attributes:Ink(small, THEME_AUTHOR)],
                       pad, titleTop + titleFont.ascender, textWidth, NSTextAlignmentRight);
    DrawText(self.detail, NSMakeRect(pad, titleTop + titleHeight + S(2), textWidth, self.bounds.size.height - titleTop - titleHeight),
             small, THEME_TEXT_MUTED, NSTextAlignmentLeft, NO);
    NSRect track = NSMakeRect(switchLeft, (self.bounds.size.height - switchHeight) / 2, switchWidth, switchHeight);
    NSBezierPath *pill = Rounded(track, switchHeight / 2);
    [(self.on ? THEME_ACCENT_STRONG : THEME_DISABLED) setFill];
    [pill fill];
    [(self.on ? THEME_ACCENT : THEME_CARD_EDGE) setStroke];
    [pill stroke];
    CGFloat knob = switchHeight - MAX(2, S(8));
    CGFloat knobX = self.on ? NSMaxX(track) - knob - (switchHeight - knob) / 2 : track.origin.x + (switchHeight - knob) / 2;
    [(self.on ? NSColor.whiteColor : THEME_TEXT_MUTED) setFill];
    [[NSBezierPath bezierPathWithOvalInRect:NSMakeRect(knobX, track.origin.y + (switchHeight - knob) / 2, knob, knob)] fill];
}
@end

// A footer line with a link part (MainForm's logLink and credit).
@interface KMRPLink : KMRPFlippedView
@property (nonatomic, copy) NSString *plain, *link;
@property (nonatomic) NSTextAlignment alignment;
@property (nonatomic, strong) NSColor *linkColor, *hoverColor;
@property (nonatomic, copy) void (^clicked)(void);
@end
@implementation KMRPLink {
    BOOL _hover;
}
- (void)updateTrackingAreas {
    for (NSTrackingArea *area in self.trackingAreas) [self removeTrackingArea:area];
    [self addTrackingArea:[[NSTrackingArea alloc] initWithRect:self.bounds
                                                       options:NSTrackingMouseEnteredAndExited | NSTrackingActiveAlways
                                                         owner:self userInfo:nil]];
    [super updateTrackingAreas];
}
- (void)mouseEntered:(NSEvent *)event { _hover = YES; self.needsDisplay = YES; }
- (void)mouseExited:(NSEvent *)event { _hover = NO; self.needsDisplay = YES; }
- (void)resetCursorRects { [self addCursorRect:self.bounds cursor:[NSCursor pointingHandCursor]]; }
- (void)mouseDown:(NSEvent *)event {}
- (void)mouseUp:(NSEvent *)event { if (self.clicked) self.clicked(); }
- (void)drawRect:(NSRect)dirty {
    NSFont *font = BodyFont(Pt(15.5), NSFontWeightSemibold);
    NSMutableAttributedString *line = [[NSMutableAttributedString alloc] initWithString:self.plain ?: @""
                                                                             attributes:Ink(font, THEME_TEXT_FAINT)];
    NSMutableDictionary *linkInk = [Ink(font, _hover ? self.hoverColor : self.linkColor) mutableCopy];
    if (_hover) linkInk[NSUnderlineStyleAttributeName] = @(NSUnderlineStyleSingle);
    [line appendAttributedString:[[NSAttributedString alloc] initWithString:self.link attributes:linkInk]];
    DrawAttributed(line, 0, CentredBaseline(self.bounds, font), self.bounds.size.width, self.alignment);
}
@end

// ------------------------------------------------------------------------------ the installer

@interface KMRPRow : NSObject
@property (nonatomic, copy) NSString *size;    // "3024x1964"; nil for a group's title
@property (nonatomic, copy) NSString *text;    // the group's title, or what the size is
@property (nonatomic, copy) NSString *choice;  // "native" or "half" on this display's rows
@end
@implementation KMRPRow
@end

static NSString *Pretty(NSString *size) { return [size stringByReplacingOccurrencesOfString:@"x" withString:@" × "]; }

static BOOL ParseSize(NSString *size, NSInteger *width, NSInteger *height) {
    NSArray<NSString *> *parts = [size componentsSeparatedByString:@"x"];
    if (parts.count != 2) return NO;
    NSCharacterSet *other = [NSCharacterSet decimalDigitCharacterSet].invertedSet;
    for (NSString *part in parts)
        if (part.length == 0 || part.length > 5 || [part rangeOfCharacterFromSet:other].location != NSNotFound) return NO;
    *width = parts[0].integerValue;
    *height = parts[1].integerValue;
    return YES;
}

static NSString *Value(NSString *output, NSString *prefix) {
    for (NSString *line in [output componentsSeparatedByString:@"\n"])
        if ([line hasPrefix:prefix]) return [line substringFromIndex:prefix.length];
    return nil;
}

static NSString *LastError(NSString *output) {
    NSString *found = nil;
    for (NSString *line in [output componentsSeparatedByString:@"\n"])
        if ([line hasPrefix:@"error: "]) found = [line substringFromIndex:7];
    return found;
}

// kmrp-mac.sh's stage lines, and how far through its run each one is: roughly the share of
// an install's time spent before it at 3024x1964, where the Override files are most of it.
static const struct { const char *prefix, *stage; int percent; } kStages[] = {
    {"Checking the package", "Checking the package…", 4},
    {"Preparing the menu set", "Preparing the menus…", 10},
    {"Backing up KOTOR_Exe", "Backing up KOTOR_Exe…", 16},
    {"Installing the engine patches", "Installing the engine…", 22},
    {"Setting the resolution", "Setting the resolution…", 28},
    {"Installing artwork and the menu set", "Installing artwork…", 34},
    {"Making the row frames", "Making row frames…", 82},
    {"Enlarging the feat", "Enlarging icons…", 90},
    {"Installed:", "Finishing…", 99},
    {"Removing KMRP from", "Restoring original files…", 20},
    {"KMRP removed", "Finishing…", 99},
};

@interface KMRPInstaller : NSObject <NSApplicationDelegate, NSWindowDelegate>
@property (nonatomic, strong) NSWindow *window;
@property (nonatomic, strong) KMRPRootView *root;
@property (nonatomic, strong) KMRPCard *card;
@property (nonatomic, strong) KMRPStep *stepGame, *stepVerify, *stepResolution, *stepApply;
@property (nonatomic, strong) KMRPState *verifyState, *resolutionState, *applyState;
@property (nonatomic, strong) KMRPPill *browseButton, *actionButton, *settingsButton;
@property (nonatomic, strong) KMRPCombo *resolutionBox;
@property (nonatomic, strong) KMRPCard *settingsView;
@property (nonatomic, strong) KMRPToggle *markerToggle, *controllerToggle;
@property (nonatomic, strong) NSMutableArray<NSView *> *mainViews;
@property (nonatomic, strong) NSMutableArray<KMRPRow *> *rows;
@property (nonatomic, strong) NSSet<NSString *> *setSizes;
@property (nonatomic, strong) NSMutableString *output;
@property (nonatomic, copy) NSString *payload, *script, *chosenGame, *version, *installedSize, *blendTool, *gamePath;
@property (nonatomic, copy) NSString *selectedSize, *selectedChoice, *selectedDetail, *stage;
@property (nonatomic) BOOL running, checking, installed, incomplete, statusLoaded, gameFound, gameReady;
@property (nonatomic) int percent;
@property (nonatomic, strong) NSMenu *openMenu;   // the resolution list while it is open
@property (nonatomic) BOOL listAtEnd;               // a scripted check's second look at the list
@property (nonatomic, copy) NSString *listShot;     // the snapshot name the open list is taken as
@end

@implementation KMRPInstaller {
    Smoke _smoke;
    dispatch_queue_t _smokeQueue;
    dispatch_source_t _smokeTimer;
    uint64_t _lastTick;
    BOOL _framePending;
    int _headerPixelWidth, _headerPixelHeight;
    CGFloat _headerWidth, _headerHeight;
}

// ---------------------------------------------------------------------------------- window

- (void)applicationDidFinishLaunching:(NSNotification *)notification {
    self.payload = [[NSBundle mainBundle].resourcePath stringByAppendingPathComponent:@"kmrp"];
    self.script = [self.payload stringByAppendingPathComponent:@"kmrp-mac.sh"];
    NSString *version = [NSString stringWithContentsOfFile:[self.payload stringByAppendingPathComponent:@"VERSION"]
                                                  encoding:NSUTF8StringEncoding error:nil];
    self.version = [version stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]] ?: @"";
    self.output = [NSMutableString string];
    self.percent = -1;
    [self buildMenu];
    [self loadRows];
    [self buildWindow];
    [self selectRow:[self defaultRow]];
    [self updateView];
    [self.window makeKeyAndOrderFront:nil];
    if (@available(macOS 14, *)) [NSApp activate];
    else [NSApp activateIgnoringOtherApps:YES];
    [self startSmoke];
    self.blendTool = [self copyBlendTool];
    [self loadSetSizes];
    [self refreshStatus];
}

- (void)buildMenu {
    NSMenu *bar = [NSMenu new];
    NSMenuItem *appItem = [NSMenuItem new];
    NSMenu *appMenu = [NSMenu new];
    [appMenu addItemWithTitle:@"Hide KMRP" action:@selector(hide:) keyEquivalent:@"h"];
    [appMenu addItem:[NSMenuItem separatorItem]];
    [appMenu addItemWithTitle:@"Quit KMRP" action:@selector(terminate:) keyEquivalent:@"q"];
    appItem.submenu = appMenu;
    [bar addItem:appItem];
    NSMenuItem *editItem = [NSMenuItem new];
    NSMenu *editMenu = [[NSMenu alloc] initWithTitle:@"Edit"];
    [editMenu addItemWithTitle:@"Cut" action:@selector(cut:) keyEquivalent:@"x"];
    [editMenu addItemWithTitle:@"Copy" action:@selector(copy:) keyEquivalent:@"c"];
    [editMenu addItemWithTitle:@"Paste" action:@selector(paste:) keyEquivalent:@"v"];
    [editMenu addItemWithTitle:@"Select All" action:@selector(selectAll:) keyEquivalent:@"a"];
    editItem.submenu = editMenu;
    [bar addItem:editItem];
    NSApp.mainMenu = bar;
}

// MainForm's constructor and FitInitialSizeToWorkingArea, in its design space.
- (void)buildWindow {
    const CGFloat stepHeight = 108, cardAspect = 2.25, brandCardFraction = 0.5;
    const CGFloat cardWidth = round((4 * stepHeight + 30 + 76 + 40) * cardAspect);
    NSImage *brand = Art(@"brand");
    const CGFloat brandWidth = round(cardWidth * brandCardFraction);
    const CGFloat brandHeight = brand ? round(brand.size.height * brandWidth / brand.size.width) : 150;
    const CGFloat headerHeight = 14 + brandHeight + 56;
    const CGFloat gap = round(cardWidth / 2 - (kWordmarkInkRight - 0.5) * brandWidth);
    const CGFloat clientWidth = cardWidth + 2 * gap;
    // The action row: under the four steps, the room Windows keeps for step 2's recovery
    // buttons (67) and a 30 gap; then the card's bottom padding.
    const CGFloat actionTop = 4 * 96 + 30 + 67, actionHeight = 76, actionGap = 12;
    const CGFloat cardHeight = actionTop + actionHeight + 40;
    const CGFloat clientHeight = headerHeight + cardHeight + 14 + 34 + 18;

    // The approved 1080p composition is a 1300x700 window on a 1920x1040 working area,
    // scaled to this screen's, and never more than 94% of it. Windows measures in pixels at
    // about 96 per inch; a Mac's points are denser (about 125 per inch on a 14" MacBook Pro at
    // its default, 109 on a 5K display), so the same formula made the text small (reported
    // 2026-09-30). The Mac's window is 1.3 times the Windows formula, which puts the step
    // subtitles at about 14.6 pt on a 14" MacBook Pro.
    const CGFloat pointDensity = 1.3;
    NSRect work = NSScreen.mainScreen.visibleFrame;
    CGFloat reference = MIN(1300 / clientWidth, 700 / clientHeight);
    CGFloat monitor = MIN(work.size.width / 1920, work.size.height / 1040);
    CGFloat fit = MIN(work.size.width * 0.94 / clientWidth, (work.size.height * 0.94 - 28) / clientHeight);
    gScale = MAX(0.35, MIN(reference * monitor * pointDensity, fit));

    NSRect content = NSMakeRect(0, 0, round(S(clientWidth)), round(S(clientHeight)));
    self.window = [[NSWindow alloc] initWithContentRect:content
                                              styleMask:NSWindowStyleMaskTitled | NSWindowStyleMaskClosable |
                                                        NSWindowStyleMaskMiniaturizable
                                                backing:NSBackingStoreBuffered defer:NO];
    self.window.title = @"KMRP – KOTOR Modern Restoration Patch";
    self.window.delegate = self;
    self.window.releasedWhenClosed = NO;
    self.window.backgroundColor = THEME_WINDOW;
    self.window.titlebarAppearsTransparent = YES;
    if (@available(macOS 10.14, *)) self.window.appearance = [NSAppearance appearanceNamed:NSAppearanceNameDarkAqua];

    self.root = [[KMRPRootView alloc] initWithFrame:content];
    self.root.headerHeight = S(headerHeight);
    self.root.brandWidth = S(brandWidth);
    self.root.brandHeight = S(brandHeight);
    self.window.contentView = self.root;
    [self.window center];

    self.card = [[KMRPCard alloc] initWithFrame:NSMakeRect(S(gap), S(headerHeight), S(cardWidth), S(cardHeight))];
    [self.root addSubview:self.card];
    self.mainViews = [NSMutableArray array];

    self.stepGame = [self step:0 icon:@"folder" title:@"1. Select Game" subtitle:@""];
    self.stepGame.textRight = 190;
    self.browseButton = [self pill:@"Browse" frame:NSMakeRect(cardWidth - 168, 24, 132, 48) action:@selector(chooseGame:)];
    self.browseButton.textPoints = 18;
    [self.stepGame addSubview:self.browseButton];

    self.stepVerify = [self step:1 icon:@"shield" title:@"2. Verify Game" subtitle:@"Checking for the Steam version of KOTOR."];
    self.verifyState = [self stateIn:self.stepVerify width:cardWidth];
    self.stepVerify.textRight = 220;

    self.stepResolution = [self step:2 icon:@"monitor" title:@"3. Choose Resolution" subtitle:@""];
    self.stepResolution.textRight = 470;
    self.resolutionBox = [[KMRPCombo alloc] initWithFrame:NSMakeRect(S(cardWidth - 448), S(26), S(412), S(44))];
    self.resolutionBox.target = self;
    self.resolutionBox.action = @selector(openResolutions:);
    self.resolutionBox.enabled = YES;
    [self.stepResolution addSubview:self.resolutionBox];
    self.resolutionState = [self stateIn:self.stepResolution width:cardWidth];
    self.resolutionState.hidden = YES;

    self.stepApply = [self step:3 icon:@"tools" title:@"4. Apply Patch" subtitle:@""];
    self.stepApply.separator = NO;
    self.applyState = [self stateIn:self.stepApply width:cardWidth];
    self.stepApply.textRight = 300;

    const CGFloat actionWidth = cardWidth - 160 - actionGap - actionHeight;
    self.actionButton = [self pill:@"Start Patching" frame:NSMakeRect(80, actionTop, actionWidth, actionHeight) action:@selector(act:)];
    self.actionButton.primary = YES;
    [self.card addSubview:self.actionButton];
    [self.mainViews addObject:self.actionButton];
    self.settingsButton = [self pill:@"" frame:NSMakeRect(80 + actionWidth + actionGap, actionTop, actionHeight, actionHeight)
                              action:@selector(openSettings:)];
    self.settingsButton.subtle = YES;
    self.settingsButton.iconName = @"Settings";
    self.settingsButton.toolTip = @"Advanced Settings";
    [self.card addSubview:self.settingsButton];
    [self.mainViews addObject:self.settingsButton];

    [self buildSettings:cardWidth height:cardHeight];

    __weak KMRPInstaller *weakSelf = self;
    KMRPLink *log = [[KMRPLink alloc] initWithFrame:NSMakeRect(S(gap + 8), S(headerHeight + cardHeight + 14), S(320), S(34))];
    log.plain = [NSString stringWithFormat:@"v%@   ·   ", self.version];
    log.link = @"Open Log";
    log.linkColor = THEME_ACCENT;
    log.hoverColor = NSColor.whiteColor;
    log.alignment = NSTextAlignmentLeft;
    log.clicked = ^{ [weakSelf openLog]; };
    [self.root addSubview:log];
    KMRPLink *credit = [[KMRPLink alloc] initWithFrame:NSMakeRect(S(gap + cardWidth - 268), S(headerHeight + cardHeight + 14),
                                                                  S(260), S(34))];
    credit.plain = @"";
    credit.link = @"Created by RaymanGT";
    credit.linkColor = THEME_TEXT_FAINT;
    credit.hoverColor = THEME_ACCENT;
    credit.alignment = NSTextAlignmentRight;
    credit.clicked = ^{
        [[NSWorkspace sharedWorkspace] openURL:[NSURL URLWithString:@"https://deadlystream.com/profile/68365-raymangt/"]];
    };
    [self.root addSubview:credit];
}

- (KMRPStep *)step:(int)index icon:(NSString *)icon title:(NSString *)title subtitle:(NSString *)subtitle {
    KMRPStep *step = [[KMRPStep alloc] initWithFrame:NSMakeRect(0, S(index * 96), self.card.bounds.size.width, S(96))];
    step.icon = icon;
    step.title = title;
    step.subtitle = subtitle;
    step.separator = YES;
    [self.card addSubview:step];
    [self.mainViews addObject:step];
    return step;
}

- (KMRPState *)stateIn:(KMRPStep *)step width:(CGFloat)cardWidth {
    KMRPState *state = [[KMRPState alloc] initWithFrame:NSMakeRect(S(cardWidth - 340), S(20), S(300), S(56))];
    state.color = THEME_TEXT_MUTED;
    [step addSubview:state];
    return state;
}

- (KMRPPill *)pill:(NSString *)text frame:(NSRect)design action:(SEL)action {
    KMRPPill *pill = [[KMRPPill alloc] initWithFrame:NSMakeRect(S(design.origin.x), S(design.origin.y),
                                                                S(design.size.width), S(design.size.height))];
    pill.text = text;
    pill.target = self;
    pill.action = action;
    return pill;
}

// The Advanced Settings view: it covers the card, as on Windows.
- (void)buildSettings:(CGFloat)cardWidth height:(CGFloat)cardHeight {
    KMRPCard *view = [[KMRPCard alloc] initWithFrame:self.card.bounds];
    view.hidden = YES;
    [self.card addSubview:view];
    self.settingsView = view;
    NSTextField *title = [NSTextField labelWithString:@"Advanced Settings"];
    title.font = BodyFont(Pt(24), NSFontWeightSemibold);
    title.textColor = THEME_TEXT;
    title.frame = NSMakeRect(S(36), S(24), S(cardWidth - 72), S(48));
    [view addSubview:title];
    NSTextField *subtitle = [NSTextField labelWithString:@"Choose optional components. Both are on by default, and each can be "
                                                         @"turned off on its own."];
    subtitle.font = BodyFont(Pt(14), NSFontWeightRegular);
    subtitle.textColor = THEME_TEXT_MUTED;
    subtitle.frame = NSMakeRect(S(36), S(74), S(cardWidth - 72), S(30));
    [view addSubview:subtitle];
    self.markerToggle = [[KMRPToggle alloc] initWithFrame:NSMakeRect(S(36), S(122), S(cardWidth - 72), S(86))];
    self.markerToggle.title = @"Area Map Marker Fixes";
    self.markerToggle.author = @"Derslok";
    self.markerToggle.detail = @"Corrects misplaced area-map marker positions across the game.";
    NSUserDefaults *defaults = [NSUserDefaults standardUserDefaults];
    self.markerToggle.on = [defaults objectForKey:@"MarkerFixes"] ? [defaults boolForKey:@"MarkerFixes"] : YES;
    if ([defaults boolForKey:@"KMRPNoMapNotes"]) self.markerToggle.on = NO;
    self.markerToggle.changed = ^(BOOL on) { [[NSUserDefaults standardUserDefaults] setBool:on forKey:@"MarkerFixes"]; };
    [view addSubview:self.markerToggle];
    // MainForm's controllerToggle: KMRP's controller support, the module and SDL (kmrp-mac.sh
    // --no-controller leaves both out, and its settings file).
    self.controllerToggle = [[KMRPToggle alloc] initWithFrame:NSMakeRect(S(36), S(122 + 86 + 8), S(cardWidth - 72), S(86))];
    self.controllerToggle.title = @"Controller Support";
    self.controllerToggle.author = @"RaymanGT, based on Saul0097";
    self.controllerToggle.detail = @"Xbox, PlayStation, Switch and Steam Deck: play, menus and matching button prompts.";
    self.controllerToggle.on = [defaults objectForKey:@"ControllerSupport"] ? [defaults boolForKey:@"ControllerSupport"] : YES;
    if ([defaults boolForKey:@"KMRPNoController"]) self.controllerToggle.on = NO;
    self.controllerToggle.changed = ^(BOOL on) { [[NSUserDefaults standardUserDefaults] setBool:on forKey:@"ControllerSupport"]; };
    [view addSubview:self.controllerToggle];
    CGFloat rowTop = cardHeight - 116, rowWidth = floor((cardWidth - 160 - 12) / 2);
    KMRPPill *defaultsButton = [self pill:@"Restore Defaults" frame:NSMakeRect(80, rowTop, rowWidth, 76)
                                   action:@selector(restoreDefaults:)];
    defaultsButton.subtle = YES;
    [view addSubview:defaultsButton];
    [view addSubview:[self pill:@"Back" frame:NSMakeRect(80 + rowWidth + 12, rowTop, rowWidth, 76) action:@selector(closeSettings:)]];
}

- (void)openSettings:(id)sender { [self showSettings:YES]; }
- (void)closeSettings:(id)sender { [self showSettings:NO]; }
- (void)restoreDefaults:(id)sender {   // the documented defaults: both on
    self.markerToggle.on = YES;
    self.controllerToggle.on = YES;
    [[NSUserDefaults standardUserDefaults] setBool:YES forKey:@"MarkerFixes"];
    [[NSUserDefaults standardUserDefaults] setBool:YES forKey:@"ControllerSupport"];
}

// Cross-fades the card's two views, as FadeOverlay does.
- (void)showSettings:(BOOL)open {
    if (self.running) return;
    NSArray<NSView *> *incoming = open ? @[self.settingsView] : self.mainViews;
    NSArray<NSView *> *outgoing = open ? self.mainViews : @[self.settingsView];
    for (NSView *view in incoming) { view.alphaValue = 0; view.hidden = NO; }
    [NSAnimationContext runAnimationGroup:^(NSAnimationContext *context) {
        context.duration = 0.18;
        for (NSView *view in incoming) view.animator.alphaValue = 1;
        for (NSView *view in outgoing) view.animator.alphaValue = 0;
    } completionHandler:^{
        for (NSView *view in outgoing) { view.hidden = YES; view.alphaValue = 1; }
    }];
}

// -------------------------------------------------------------------------------- the smoke

- (void)startSmoke {
    SmokeInit(&_smoke);
    _smokeQueue = dispatch_queue_create("kmrp.smoke", DISPATCH_QUEUE_SERIAL);
    _headerWidth = self.root.bounds.size.width;
    _headerHeight = self.root.headerHeight;
    NSSize pixels = [self.root convertSizeToBacking:NSMakeSize(_headerWidth, _headerHeight)];
    _headerPixelWidth = (int)fabs(pixels.width);
    _headerPixelHeight = (int)fabs(pixels.height);
    _lastTick = mach_absolute_time();
    _smokeTimer = dispatch_source_create(DISPATCH_SOURCE_TYPE_TIMER, 0, 0, _smokeQueue);
    // 62 ms: the rate Windows' 60 ms timer lands on, which the motes' speed is tuned for.
    dispatch_source_set_timer(_smokeTimer, DISPATCH_TIME_NOW, 62 * NSEC_PER_MSEC, 4 * NSEC_PER_MSEC);
    __weak KMRPInstaller *weakSelf = self;
    dispatch_source_set_event_handler(_smokeTimer, ^{ [weakSelf smokeTick]; });
    dispatch_resume(_smokeTimer);
}

- (void)smokeTick {   // on _smokeQueue
    static mach_timebase_info_data_t timebase;
    if (!timebase.denom) mach_timebase_info(&timebase);
    uint64_t now = mach_absolute_time();
    float seconds = (float)((double)(now - _lastTick) * timebase.numer / timebase.denom / 1e9);
    _lastTick = now;
    // The simulation always steps; a frame is only made when the last one has been shown.
    SmokeStep(&_smoke, fminf(seconds, 0.25f));
    @synchronized (self) { if (_framePending) return; }
    if (_headerPixelWidth < 16 || _headerPixelHeight < 16) return;
    SmokeRender(&_smoke, _headerPixelWidth, _headerPixelHeight);
    // Upscaled here, smoothly, to the header's own pixels: only the rows that hold smoke, as
    // Windows does (the plume fills about the top half and the rest is zeroes).
    CGImageRef frame = NULL;
    CGFloat smokeHeight = 0;
    int rows = _smoke.filledRows;
    if (rows > 0) {
        size_t width = (size_t)_headerPixelWidth;
        size_t height = (size_t)MIN(_headerPixelHeight, (int)ceil(rows * (double)_headerPixelHeight / _smoke.h));
        size_t rowBytes = width * 4;
        void *pixels = malloc(height * rowBytes);
        vImage_Buffer source = {_smoke.pixels, (vImagePixelCount)rows, (vImagePixelCount)_smoke.w, (size_t)_smoke.w * 4};
        vImage_Buffer scaled = {pixels, (vImagePixelCount)height, (vImagePixelCount)width, rowBytes};
        vImageScale_ARGB8888(&source, &scaled, NULL, kvImageEdgeExtend);
        CGDataProviderRef provider = CGDataProviderCreateWithData(NULL, pixels, height * rowBytes, FreeFrame);
        CGColorSpaceRef space = CGColorSpaceCreateDeviceRGB();
        frame = CGImageCreate(width, height, 8, 32, rowBytes, space, (CGBitmapInfo)kCGImageAlphaPremultipliedLast,
                              provider, NULL, false, kCGRenderingIntentDefault);
        CGColorSpaceRelease(space);
        CGDataProviderRelease(provider);
        smokeHeight = height * _headerHeight / _headerPixelHeight;
    }
    // The motes, in the header's points (MainForm draws them at full resolution).
    NSMutableArray *rects = [NSMutableArray array], *levels = [NSMutableArray array];
    for (int i = 0; i < kMotes; i++) {
        Mote *m = &_smoke.motes[i];
        float t = m->age / fmaxf(0.001f, m->life);
        float fade = t < 0.12f ? t / 0.12f : (t > 0.45f ? 1 - (t - 0.45f) / 0.55f : 1);
        if (fade <= 0) continue;
        float mx = m->x + sinf(m->phase) * m->drift, my = m->y;
        if (my < -0.05f || my > 1.05f) continue;
        float bright = fminf(fade * m->seed * LightAt(&_smoke, mx, my), 1);
        if (bright <= 0.004f) continue;
        int level = MIN(MAX((int)(bright * (kMoteLevels - 1) + 0.5f), 0), kMoteLevels - 1);
        CGFloat radius = m->size * kMoteGlowScale * _headerHeight;
        [rects addObject:[NSValue valueWithRect:NSMakeRect(mx * _headerWidth - radius, my * _headerHeight - radius,
                                                           MAX(2, radius * 2), MAX(2, radius * 2))]];
        [levels addObject:@(level)];
    }
    @synchronized (self) { _framePending = YES; }
    dispatch_async(dispatch_get_main_queue(), ^{
        self.root.smokeFrame = frame;
        if (frame) CGImageRelease(frame);
        self.root.smokeHeight = smokeHeight;
        self.root.moteRects = rects;
        self.root.moteLevels = levels;
        [self.root setNeedsDisplayInRect:NSMakeRect(0, 0, self.root.bounds.size.width, self.root.headerHeight)];
        @synchronized (self) { self->_framePending = NO; }
    });
}

// ------------------------------------------------------------------------------ resolutions

// This display, then resolutions.txt.
- (void)loadRows {
    self.rows = [NSMutableArray array];
    CGDirectDisplayID display = CGMainDisplayID();
    CGSize points = CGDisplayBounds(display).size;
    size_t pixelWidth = 0, pixelHeight = 0;
    CGDisplayModeRef mode = CGDisplayCopyDisplayMode(display);
    if (mode) {
        pixelWidth = CGDisplayModeGetPixelWidth(mode);
        pixelHeight = CGDisplayModeGetPixelHeight(mode);
        CGDisplayModeRelease(mode);
    }
    NSInteger pointWidth = (NSInteger)points.width, pointHeight = (NSInteger)points.height;
    if (pointWidth >= 640 && pointHeight >= 480 && pixelWidth >= (size_t)pointWidth) {
        NSString *name = @"This display";
        if (@available(macOS 10.15, *)) {
            NSString *screen = NSScreen.screens.firstObject.localizedName;
            if (screen.length) name = [NSString stringWithFormat:@"This display · %@", screen];
        }
        [self.rows addObject:[self row:nil text:name choice:nil]];
        NSString *native = [NSString stringWithFormat:@"%zux%zu", pixelWidth, pixelHeight];
        NSString *half = [NSString stringWithFormat:@"%ldx%ld", (long)pointWidth, (long)pointHeight];
        if (pixelWidth > (size_t)pointWidth) {
            [self.rows addObject:[self row:native text:@"This display, native: every pixel, the sharpest" choice:@"native"]];
            [self.rows addObject:[self row:half text:@"This display, half: scaled up by macOS, lighter on the GPU" choice:@"half"]];
        } else {
            [self.rows addObject:[self row:native text:@"This display" choice:@"native"]];
        }
    }
    NSString *list = [NSString stringWithContentsOfFile:[[NSBundle mainBundle] pathForResource:@"resolutions" ofType:@"txt"]
                                               encoding:NSUTF8StringEncoding error:nil];
    for (NSString *line in [list componentsSeparatedByCharactersInSet:[NSCharacterSet newlineCharacterSet]]) {
        if ([line hasPrefix:@"= "]) {
            [self.rows addObject:[self row:nil text:[line substringFromIndex:2] choice:nil]];
            continue;
        }
        NSArray<NSString *> *fields = [line componentsSeparatedByString:@"\t"];
        NSInteger w, h;
        if (fields.count == 2 && ParseSize(fields[0], &w, &h)) [self.rows addObject:[self row:fields[0] text:fields[1] choice:nil]];
    }
}

- (KMRPRow *)row:(NSString *)size text:(NSString *)text choice:(NSString *)choice {
    KMRPRow *row = [KMRPRow new];
    row.size = size;
    row.text = text;
    row.choice = choice;
    return row;
}

- (KMRPRow *)defaultRow {
    for (KMRPRow *row in self.rows)
        if ([row.choice isEqualToString:@"native"]) return row;
    for (KMRPRow *row in self.rows)
        if (row.size) return row;
    return nil;
}

- (void)selectRow:(KMRPRow *)row {
    if (row) [self selectSize:row.size choice:row.choice detail:row.text];
}

- (void)selectSize:(NSString *)size choice:(NSString *)choice detail:(NSString *)detail {
    self.selectedSize = size;
    self.selectedChoice = choice;
    self.selectedDetail = detail;
    self.resolutionBox.text = Pretty(size);
    self.resolutionBox.detail = choice ? [@"This display, " stringByAppendingString:choice] : detail;
    self.resolutionBox.needsDisplay = YES;
}

// The list, as the dropdown's menu: this display, then each shape, then a custom size.
- (void)openResolutions:(id)sender {
    NSMenu *menu = [NSMenu new];
    menu.autoenablesItems = NO;
    if (@available(macOS 10.14, *)) menu.appearance = [NSAppearance appearanceNamed:NSAppearanceNameDarkAqua];
    NSFont *sizeFont = [NSFont monospacedDigitSystemFontOfSize:MAX(12, Pt(14)) weight:NSFontWeightSemibold];
    NSFont *detailFont = BodyFont(MAX(11, Pt(12.5)), NSFontWeightRegular);
    // Each description starts at one tab stop, past the widest size, so they line up.
    NSMutableParagraphStyle *columns = [NSMutableParagraphStyle new];
    CGFloat sizeWidth = [Pretty(@"0000x0000") sizeWithAttributes:Ink(sizeFont, THEME_TEXT)].width;
    columns.tabStops = @[[[NSTextTab alloc] initWithTextAlignment:NSTextAlignmentLeft location:ceil(sizeWidth) + 22 options:@{}]];
    NSMenuItem *selected = nil;
    for (KMRPRow *row in self.rows) {
        NSMenuItem *item = [[NSMenuItem alloc] initWithTitle:row.text action:nil keyEquivalent:@""];
        if (!row.size) {
            if (menu.numberOfItems) [menu addItem:[NSMenuItem separatorItem]];
            item.enabled = NO;
            item.attributedTitle = [[NSAttributedString alloc] initWithString:row.text
                                                                   attributes:Ink(BodyFont(MAX(11, Pt(12)), NSFontWeightBold), THEME_ACCENT)];
            [menu addItem:item];
            continue;
        }
        NSMutableAttributedString *title = [[NSMutableAttributedString alloc] initWithString:Pretty(row.size)
                                                                                   attributes:Ink(sizeFont, THEME_TEXT)];
        [title appendAttributedString:[[NSAttributedString alloc] initWithString:[@"\t" stringByAppendingString:row.text]
                                                                      attributes:Ink(detailFont, THEME_TEXT_MUTED)]];
        [title addAttribute:NSParagraphStyleAttributeName value:columns range:NSMakeRange(0, title.length)];
        item.attributedTitle = title;
        item.indentationLevel = 1;
        item.target = self;
        item.action = @selector(pickResolution:);
        item.representedObject = row;
        if ([row.size isEqualToString:self.selectedSize] && [row.text isEqualToString:self.selectedDetail]) {
            item.state = NSControlStateValueOn;
            selected = item;
        }
        [menu addItem:item];
    }
    [menu addItem:[NSMenuItem separatorItem]];
    NSMenuItem *custom = [[NSMenuItem alloc] initWithTitle:@"Custom size…" action:@selector(customSize:) keyEquivalent:@""];
    custom.attributedTitle = [[NSAttributedString alloc] initWithString:@"Custom size…" attributes:Ink(sizeFont, THEME_TEXT)];
    custom.indentationLevel = 1;
    custom.target = self;
    if (self.selectedSize && !self.selectedChoice && [self.selectedDetail hasPrefix:@"Custom"]) custom.state = NSControlStateValueOn;
    [menu addItem:custom];
    menu.minimumWidth = self.resolutionBox.bounds.size.width;
    self.openMenu = menu;
    // Opens below the field, as Windows' dropdown does; a scripted check can open it on its last
    // item instead, to see the end of a list taller than the screen.
    [menu popUpMenuPositioningItem:self.listAtEnd ? custom : nil
                        atLocation:NSMakePoint(0, self.resolutionBox.bounds.size.height + 2) inView:self.resolutionBox];
    (void)selected;
}

- (void)pickResolution:(NSMenuItem *)item {
    [self selectRow:item.representedObject];
    [self updateView];
}

// A size the list does not have. The installer blends a set for it, so it is checked with
// kmrp-guiblend's dry run: exit 0, the sets cover it; 2, they do not.
- (void)customSize:(id)sender {
    NSAlert *alert = [NSAlert new];
    alert.messageText = @"Custom resolution";
    alert.informativeText = @"KMRP has menu sets for the listed sizes. For any other, the installer blends one from the "
                            @"sets around it, for shapes from 4:3 to 32:9.";
    NSView *fields = [[NSView alloc] initWithFrame:NSMakeRect(0, 0, 220, 26)];
    NSTextField *width = [[NSTextField alloc] initWithFrame:NSMakeRect(0, 0, 90, 24)];
    NSTextField *height = [[NSTextField alloc] initWithFrame:NSMakeRect(126, 0, 90, 24)];
    width.placeholderString = @"width";
    height.placeholderString = @"height";
    NSInteger w = 0, h = 0;
    if (ParseSize(self.selectedSize ?: @"", &w, &h)) {
        width.stringValue = [NSString stringWithFormat:@"%ld", (long)w];
        height.stringValue = [NSString stringWithFormat:@"%ld", (long)h];
    }
    NSTextField *times = [NSTextField labelWithString:@"×"];
    times.alignment = NSTextAlignmentCenter;
    times.frame = NSMakeRect(90, 2, 36, 20);
    [fields addSubview:width];
    [fields addSubview:times];
    [fields addSubview:height];
    alert.accessoryView = fields;
    [alert addButtonWithTitle:@"Use This Size"];
    [alert addButtonWithTitle:@"Cancel"];
    alert.window.initialFirstResponder = width;
    [alert beginSheetModalForWindow:self.window completionHandler:^(NSModalResponse response) {
        if (response != NSAlertFirstButtonReturn) return;
        [self useCustomSize:[NSString stringWithFormat:@"%@x%@", width.stringValue, height.stringValue] tell:YES];
    }];
}

- (BOOL)useCustomSize:(NSString *)size tell:(BOOL)tell {
    NSInteger w, h;
    NSString *problem = nil;
    if (!ParseSize(size, &w, &h) || w < 640 || h < 480) problem = @"Type a size of at least 640 × 480.";
    else if (![self.setSizes containsObject:size]) {
        int status = [self blendCheck:w height:h];
        if (status == 2) problem = @"KMRP's menu sets do not reach this size or shape. Sizes from 4:3 to 32:9 work.";
        else if (status != 0) problem = @"The size could not be checked: the package may be damaged.";
    }
    if (problem) {
        if (tell) {
            NSAlert *alert = [NSAlert new];
            alert.messageText = @"This size cannot be used";
            alert.informativeText = problem;
            dispatch_async(dispatch_get_main_queue(), ^{ [alert beginSheetModalForWindow:self.window completionHandler:nil]; });
        }
        return NO;
    }
    NSString *key = [NSString stringWithFormat:@"%ldx%ld", (long)w, (long)h];
    [self selectSize:key choice:nil detail:[self.setSizes containsObject:key] ? @"Custom" : @"Custom, blended at install"];
    [self updateView];
    return YES;
}

- (int)blendCheck:(NSInteger)width height:(NSInteger)height {
    if (!self.blendTool) return -1;
    NSTask *task = [NSTask new];
    task.executableURL = [NSURL fileURLWithPath:self.blendTool];
    task.arguments = @[[self.payload stringByAppendingPathComponent:@"gui-blend.bin"],
                       [NSString stringWithFormat:@"%ld", (long)width], [NSString stringWithFormat:@"%ld", (long)height]];
    task.standardOutput = [NSFileHandle fileHandleWithNullDevice];
    task.standardError = [NSFileHandle fileHandleWithNullDevice];
    if (![task launchAndReturnError:nil]) return -1;
    [task waitUntilExit];
    return task.terminationStatus;
}

// kmrp-guiblend, copied out of the bundle without the quarantine flag: Gatekeeper kills a
// flagged helper as it starts (exit 137), and a downloaded app's bundle is read-only
// (kmrp-mac.sh does the same for its helpers).
- (NSString *)copyBlendTool {
    NSString *folder = [NSTemporaryDirectory() stringByAppendingPathComponent:
                        [NSString stringWithFormat:@"kmrp-installer-%d", getpid()]];
    NSString *tool = [folder stringByAppendingPathComponent:@"kmrp-guiblend"];
    NSFileManager *files = [NSFileManager defaultManager];
    [files createDirectoryAtPath:folder withIntermediateDirectories:YES attributes:nil error:nil];
    [files removeItemAtPath:tool error:nil];
    if (![files copyItemAtPath:[self.payload stringByAppendingPathComponent:@"bin/kmrp-guiblend"] toPath:tool error:nil])
        return nil;
    removexattr(tool.fileSystemRepresentation, "com.apple.quarantine", 0);
    return tool;
}

- (void)loadSetSizes {
    NSString *layouts = [self.payload stringByAppendingPathComponent:@"layouts.zip"];
    [self run:@"/usr/bin/unzip" arguments:@[@"-Z1", layouts, @"index/*"] log:NO completion:^(int status, NSString *output) {
        NSMutableSet *sizes = [NSMutableSet set];
        for (NSString *line in [output componentsSeparatedByString:@"\n"])
            if ([line hasPrefix:@"index/"] && [line hasSuffix:@".txt"])
                [sizes addObject:[line substringWithRange:NSMakeRange(6, line.length - 10)]];
        self.setSizes = sizes;
    }];
}

// ---------------------------------------------------------------------------------- status

- (NSArray<NSString *> *)gameArguments { return self.chosenGame ? @[@"--game", self.chosenGame] : @[]; }

// kmrp-mac.sh status --brief: install.info, or the game and its build, without hashing every
// installed file. The action waits for it.
- (void)refreshStatus {
    self.checking = YES;
    [self updateView];
    NSArray *arguments = [@[self.script, @"status", @"--brief"] arrayByAddingObjectsFromArray:self.gameArguments];
    [self run:@"/bin/zsh" arguments:arguments log:NO completion:^(int status, NSString *output) {
        self.checking = NO;
        NSString *game = Value(output, @"game=") ?: Value(output, @"game: ");
        self.gamePath = game;
        self.gameFound = game != nil && status == 0;
        self.installed = NO;
        self.incomplete = NO;
        self.gameReady = NO;
        self.installedSize = nil;
        if (status == 0 && [output containsString:@"KMRP is not installed."]) {
            self.gameReady = [output containsString:@"KOTOR_Exe: unmodified Steam build"];
        } else if (status == 0) {
            self.installed = YES;
            self.incomplete = ![output containsString:@"complete=1"];
            self.installedSize = Value(output, @"resolution=");
        }
        BOOL first = !self.statusLoaded;
        self.statusLoaded = YES;
        [self updateView];
        if (first) [self startAutomation];
    }];
}

// MainForm.RefreshStatus: every step's title, subtitle and state from what is installed.
- (void)updateView {
    BOOL done = self.installed && !self.incomplete;
    BOOL verified = self.gameReady || self.installed;
    self.stepGame.title = done ? @"1. Selected Game" : @"1. Select Game";
    self.stepVerify.title = done ? @"2. Verified Game" : @"2. Verify Game";
    self.stepResolution.title = done ? @"3. Chosen Resolution" : @"3. Choose Resolution";
    self.stepGame.subtitle = self.gamePath ? self.gamePath.stringByDeletingLastPathComponent.stringByAbbreviatingWithTildeInPath : (self.statusLoaded
        ? @"KOTOR was not found in your Steam libraries. Choose Knights of the Old Republic.app."
        : @"Looking for KOTOR in your Steam libraries…");

    if (!self.statusLoaded) {
        [self.verifyState set:@"" color:THEME_TEXT_MUTED badge:nil];
        self.stepVerify.subtitle = @"Checking for the Steam version of KOTOR.";
    } else if (verified) {
        [self.verifyState set:@"Verified" color:THEME_SUCCESS badge:@"verified"];
    } else {
        [self.verifyState set:@"" color:THEME_WARNING badge:@"missing"];
    }
    if (self.statusLoaded) {
        if (done) self.stepVerify.subtitle = @"KOTOR Modern Restoration Patch detected.";
        else if (self.incomplete) self.stepVerify.subtitle = @"An install did not finish. Restore Original undoes it.";
        else if (self.gameReady) self.stepVerify.subtitle = @"Unmodified Steam version 1.4.0 detected.";
        else if (self.gameFound)
            self.stepVerify.subtitle = @"This copy cannot be patched. Steam's Verify Integrity restores the original.";
        else self.stepVerify.subtitle = @"Choose the game with Browse, then it is checked again.";
    }

    self.stepResolution.dimmed = self.statusLoaded && !verified;
    self.stepResolution.subtitle = done ? @"Installed resolution." : @"Select the resolution you want to patch for.";
    self.resolutionBox.hidden = done || (self.statusLoaded && !verified);
    self.resolutionState.hidden = !done;
    if (done) [self.resolutionState set:Pretty(self.installedSize ?: @"?") color:THEME_TEXT badge:nil];

    if (self.running) return;
    if (done) {
        [self.applyState set:@"Patched successfully" color:THEME_SUCCESS badge:nil];
        self.stepApply.subtitle = self.installedSize
            ? [NSString stringWithFormat:@"KOTOR is ready to play at %@.", Pretty(self.installedSize)]
            : @"KOTOR is ready to play.";
    } else if (self.incomplete) {
        [self.applyState set:@"Not finished" color:THEME_WARNING badge:nil];
        self.stepApply.subtitle = @"Restore Original undoes what the install did.";
    } else if (self.gameReady) {
        [self.applyState set:@"Ready to patch" color:THEME_ACCENT badge:nil];
        self.stepApply.subtitle = @"Everything is ready. Start patching when ready.";
    } else {
        [self.applyState set:self.statusLoaded ? @"Not patched" : @"" color:THEME_TEXT_MUTED badge:nil];
        self.stepApply.subtitle = @"Patches will be applied to make KOTOR modern-ready.";
    }
    self.actionButton.text = self.installed ? @"Restore Original" : @"Start Patching";
    self.actionButton.enabled = self.statusLoaded && !self.checking && (self.installed || (self.gameReady && self.selectedSize));
    self.browseButton.enabled = YES;
    self.resolutionBox.enabled = YES;
    self.settingsButton.enabled = YES;
}

- (void)chooseGame:(id)sender {
    NSOpenPanel *panel = [NSOpenPanel openPanel];
    panel.message = @"Choose Knights of the Old Republic.app";
    if (@available(macOS 11, *)) panel.allowedContentTypes = @[UTTypeApplicationBundle];
    else panel.allowedFileTypes = @[@"app"];
    panel.canChooseDirectories = NO;
    panel.treatsFilePackagesAsDirectories = NO;
    [panel beginSheetModalForWindow:self.window completionHandler:^(NSModalResponse result) {
        if (result != NSModalResponseOK) return;
        self.chosenGame = panel.URL.path;
        [self refreshStatus];
    }];
}

// ---------------------------------------------------------------------------- patch, restore

- (void)act:(id)sender {
    if (self.installed) [self restore];
    else [self patch];
}

- (void)patch {
    NSMutableArray *arguments = [NSMutableArray arrayWithObjects:self.script, @"install", @"--yes", nil];
    [arguments addObjectsFromArray:self.gameArguments];
    if (self.selectedChoice) [arguments addObjectsFromArray:@[@"--resolution", self.selectedChoice]];
    else [arguments addObjectsFromArray:@[@"--size", self.selectedSize]];
    if (!self.markerToggle.on) [arguments addObject:@"--no-map-notes"];
    if (!self.controllerToggle.on) [arguments addObject:@"--no-controller"];
    [self runOperation:@"Patch" arguments:arguments];
}

- (void)restore {
    [self runOperation:@"Restore"
             arguments:[@[self.script, @"uninstall", @"--yes"] arrayByAddingObjectsFromArray:self.gameArguments]];
}

// MainForm.RunOperation: the action button becomes the progress surface; the step says what
// is happening; a failure is a blocking message with the script's own words.
- (void)runOperation:(NSString *)name arguments:(NSArray<NSString *> *)arguments {
    if (self.running) return;
    BOOL patch = [name isEqualToString:@"Patch"];
    self.running = YES;
    [self.output setString:@""];
    self.percent = 0;
    self.stage = patch ? @"Preparing patch…" : @"Preparing restore…";
    [self showProgress];
    self.browseButton.enabled = NO;
    self.resolutionBox.enabled = NO;
    self.settingsButton.enabled = NO;
    [self.applyState set:patch ? @"Patching…" : @"Restoring…" color:THEME_ACCENT badge:nil];
    self.stepApply.subtitle = patch ? @"KMRP is updating your game. Please wait."
                                    : @"KMRP is restoring your original files. Please wait.";
    NSArray *shown = [arguments subarrayWithRange:NSMakeRange(1, arguments.count - 1)];
    [self appendLogFile:[NSString stringWithFormat:@"\n== %@ %@: kmrp-mac.sh %@\n", [NSDate date], name,
                                                   [shown componentsJoinedByString:@" "]]];
    [self run:@"/bin/zsh" arguments:arguments log:YES completion:^(int status, NSString *output) {
        self.running = NO;
        self.percent = -1;
        self.actionButton.progress = -1;
        [self appendLogFile:[NSString stringWithFormat:@"== exit status %d\n", status]];
        [self refreshStatus];
        if (status == 0) {
            [self.applyState set:patch ? @"Patched successfully" : @"Restored successfully" color:THEME_SUCCESS badge:nil];
        } else {
            [self.applyState set:@"Error" color:THEME_ERROR badge:nil];
            self.stepApply.subtitle = [name stringByAppendingString:@" stopped. What it had done was undone."];
            [self tell:[name stringByAppendingString:@" blocked"] text:[self failure:output]];
        }
        [self finishAutomation];
    }];
}

- (void)showProgress {
    self.actionButton.progress = self.percent;
    self.actionButton.text = [NSString stringWithFormat:@"%@   %d%%", self.stage, self.percent];
    static BOOL snapped;
    if (self.percent >= 34 && !snapped) {   // a scripted check sees the progress fill once
        snapped = YES;
        dispatch_async(dispatch_get_main_queue(), ^{ [self snapshot:@"progress"]; });
    }
}

- (NSString *)failure:(NSString *)output {
    NSString *text = LastError(output) ?: @"The installer stopped. Open Log shows what it did.";
    if ([output containsString:@"Operation not permitted"])
        text = [text stringByAppendingString:@"\n\nmacOS stopped KMRP from changing the game. In System Settings, "
                                             @"Privacy & Security, App Management, allow KMRP Installer, then try again."];
    return text;
}

- (void)tell:(NSString *)title text:(NSString *)text {
    if ([[NSUserDefaults standardUserDefaults] stringForKey:@"KMRPRun"].length) return;
    NSAlert *alert = [NSAlert new];
    alert.alertStyle = NSAlertStyleCritical;
    alert.messageText = title;
    alert.informativeText = text;
    [alert beginSheetModalForWindow:self.window completionHandler:nil];
}

// -------------------------------------------------------------------------------------- log

- (NSString *)logPath { return [NSHomeDirectory() stringByAppendingPathComponent:@"Library/Logs/KMRP/installer.log"]; }

- (void)appendLogFile:(NSString *)text {
    NSString *path = [self logPath];
    NSFileManager *files = [NSFileManager defaultManager];
    [files createDirectoryAtPath:path.stringByDeletingLastPathComponent withIntermediateDirectories:YES attributes:nil error:nil];
    if (![files fileExistsAtPath:path]) [[NSData data] writeToFile:path atomically:YES];
    NSFileHandle *file = [NSFileHandle fileHandleForWritingAtPath:path];
    [file seekToEndOfFile];
    [file writeData:[text dataUsingEncoding:NSUTF8StringEncoding]];
    [file closeFile];
}

- (void)openLog {
    NSString *path = [self logPath];
    if (![[NSFileManager defaultManager] fileExistsAtPath:path]) [self appendLogFile:@"KMRP Installer log\n"];
    [[NSWorkspace sharedWorkspace] openURL:[NSURL fileURLWithPath:path]];
}

// Each line kmrp-mac.sh prints: to the log file, and a known stage moves the progress.
- (void)scriptLines:(NSString *)lines {
    [self.output appendString:lines];
    [self appendLogFile:lines];
    for (NSString *line in [lines componentsSeparatedByString:@"\n"])
        for (size_t i = 0; i < sizeof kStages / sizeof kStages[0]; i++)
            if ([line hasPrefix:@(kStages[i].prefix)] && kStages[i].percent > self.percent) {
                self.percent = kStages[i].percent;
                self.stage = @(kStages[i].stage);
                [self showProgress];
            }
}

// ----------------------------------------------------------------------------- running a command

// Runs a command with stdin closed, stdout and stderr on one pipe; with `log`, each finished
// line goes to scriptLines as it arrives. The completion gets the exit status and the output.
- (void)run:(NSString *)tool arguments:(NSArray<NSString *> *)arguments log:(BOOL)log
 completion:(void (^)(int status, NSString *output))completion {
    NSTask *task = [NSTask new];
    task.executableURL = [NSURL fileURLWithPath:tool];
    task.arguments = arguments;
    task.currentDirectoryURL = [NSURL fileURLWithPath:self.payload];
    task.standardInput = [NSFileHandle fileHandleWithNullDevice];
    NSPipe *pipe = [NSPipe pipe];
    task.standardOutput = pipe;
    task.standardError = pipe;
    NSMutableData *all = [NSMutableData data];
    NSMutableData *pending = [NSMutableData data];
    pipe.fileHandleForReading.readabilityHandler = ^(NSFileHandle *handle) {
        NSData *data = handle.availableData;
        if (data.length == 0) {   // every writer has closed the pipe
            handle.readabilityHandler = nil;
            [task waitUntilExit];
            NSString *text = [[NSString alloc] initWithData:all encoding:NSUTF8StringEncoding] ?: @"";
            NSString *rest = [[NSString alloc] initWithData:pending encoding:NSUTF8StringEncoding] ?: @"";
            int status = task.terminationStatus;
            dispatch_async(dispatch_get_main_queue(), ^{
                if (log && rest.length) [self scriptLines:[rest stringByAppendingString:@"\n"]];
                completion(status, text);
            });
            return;
        }
        [all appendData:data];
        if (!log) return;
        [pending appendData:data];
        const char *bytes = pending.bytes;
        NSUInteger end = pending.length;
        while (end > 0 && bytes[end - 1] != '\n') end--;
        if (end == 0) return;
        NSString *lines = [[NSString alloc] initWithBytes:bytes length:end encoding:NSUTF8StringEncoding] ?: @"";
        [pending replaceBytesInRange:NSMakeRange(0, end) withBytes:NULL length:0];
        dispatch_async(dispatch_get_main_queue(), ^{ [self scriptLines:lines]; });
    };
    NSError *error = nil;
    if (![task launchAndReturnError:&error]) {
        pipe.fileHandleForReading.readabilityHandler = nil;
        NSString *message = [NSString stringWithFormat:@"error: could not start %@: %@\n", tool.lastPathComponent,
                                                       error.localizedDescription];
        dispatch_async(dispatch_get_main_queue(), ^{ completion(-1, message); });
    }
}

// ------------------------------------------------------------------------------------- quitting

- (BOOL)windowShouldClose:(NSWindow *)sender {
    if (self.running) NSBeep();
    return !self.running;
}

- (NSApplicationTerminateReply)applicationShouldTerminate:(NSApplication *)sender {
    if (!self.running) return NSTerminateNow;
    NSBeep();
    return NSTerminateCancel;
}

- (void)applicationWillTerminate:(NSNotification *)notification {
    if (self.blendTool) [[NSFileManager defaultManager] removeItemAtPath:self.blendTool.stringByDeletingLastPathComponent error:nil];
}

- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication *)sender { return YES; }

// ------------------------------------------------------------------------ scripted checks

- (void)startAutomation {
    NSUserDefaults *defaults = [NSUserDefaults standardUserDefaults];
    NSString *select = [defaults stringForKey:@"KMRPSelect"];
    if (select.length) {
        KMRPRow *found = nil;
        for (KMRPRow *row in self.rows)
            if ([row.choice isEqualToString:select] || (!row.choice && [row.size isEqualToString:select])) { found = row; break; }
        if (found) [self selectRow:found];
        else [self useCustomSize:select tell:NO];
        [self updateView];
    }
    if ([defaults boolForKey:@"KMRPSettings"]) [self showSettings:YES];
    // The smoke's first frames and the settings fade, then the snapshot and the run.
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(1.5 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
        [self snapshot:@"ready"];
        if ([defaults boolForKey:@"KMRPShowList"] || [defaults boolForKey:@"KMRPShowCustom"]) {
            [self showForSnapshots];
            return;
        }
        NSString *run = [defaults stringForKey:@"KMRPRun"];
        BOOL can = self.actionButton.enabled;
        if ([run isEqualToString:@"install"] && can && !self.installed) [self patch];
        else if ([run isEqualToString:@"uninstall"] && can && self.installed) [self restore];
        else {
            if (run.length) [self.output appendFormat:@"KMRPRun %@: the action is not available\n", run];
            [self finishAutomation];
        }
    });
}

- (void)finishAutomation {
    NSUserDefaults *defaults = [NSUserDefaults standardUserDefaults];
    if (![defaults stringForKey:@"KMRPSnapshot"].length && ![defaults boolForKey:@"KMRPQuit"]) return;
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.5 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
        if (self.checking) { [self finishAutomation]; return; }
        [self snapshot:@"done"];
        NSString *prefix = [defaults stringForKey:@"KMRPSnapshot"];
        if (prefix.length)
            [self.output writeToFile:[prefix stringByAppendingString:@"-log.txt"] atomically:YES encoding:NSUTF8StringEncoding error:nil];
        if ([defaults boolForKey:@"KMRPQuit"]) [NSApp terminate:nil];
    });
}

// The list and the custom-size dialog are windows of their own, so each is opened and
// photographed in turn. The list tracks the mouse modally: its snapshot is scheduled in the
// run loop modes the tracking runs in, and closes it.
- (void)showForSnapshots {
    NSUserDefaults *defaults = [NSUserDefaults standardUserDefaults];
    if ([defaults boolForKey:@"KMRPShowList"] && !self.resolutionBox.hidden) {
        for (NSString *shot in @[@"list", @"list-end"]) {
            self.listShot = shot;
            self.listAtEnd = [shot isEqualToString:@"list-end"];
            [self performSelector:@selector(snapshotList) withObject:nil afterDelay:1.0 inModes:@[NSRunLoopCommonModes]];
            [self openResolutions:nil];   // returns when snapshotList closes it
        }
        self.listAtEnd = NO;
    }
    if ([defaults boolForKey:@"KMRPShowCustom"]) {
        [self customSize:nil];
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(1.0 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
            NSWindow *sheet = self.window.attachedSheet;
            if (sheet) {
                [self snapshotView:sheet.contentView name:@"custom"];
                [self.window endSheet:sheet];
            }
            [self finishAutomation];
        });
        return;
    }
    [self finishAutomation];
}

- (void)snapshotList {
    for (NSWindow *window in NSApp.windows) {
        if (window != self.window && window.isVisible && [NSStringFromClass(window.class) containsString:@"Menu"]) {
            [self snapshotView:window.contentView.superview ?: window.contentView name:self.listShot];
            break;
        }
    }
    [self.openMenu cancelTracking];
}

- (void)snapshot:(NSString *)name { [self snapshotView:self.window.contentView name:name]; }

// A view as a PNG, over the window's own background (a sheet's or a menu's material does not
// draw into a cached image).
- (void)snapshotView:(NSView *)view name:(NSString *)name {
    NSString *prefix = [[NSUserDefaults standardUserDefaults] stringForKey:@"KMRPSnapshot"];
    if (!prefix.length || !view) return;
    [view displayIfNeeded];
    NSBitmapImageRep *controls = [view bitmapImageRepForCachingDisplayInRect:view.bounds];
    [view cacheDisplayInRect:view.bounds toBitmapImageRep:controls];
    NSBitmapImageRep *image = [view bitmapImageRepForCachingDisplayInRect:view.bounds];
    [NSGraphicsContext saveGraphicsState];
    NSGraphicsContext.currentContext = [NSGraphicsContext graphicsContextWithBitmapImageRep:image];
    NSAppearance *appearance = NSAppearance.currentAppearance;
    if (@available(macOS 10.14, *)) NSAppearance.currentAppearance = view.effectiveAppearance;
    [(view.window == self.window ? THEME_WINDOW : [NSColor windowBackgroundColor]) setFill];
    NSRectFill(view.bounds);
    [controls drawInRect:view.bounds fromRect:NSZeroRect operation:NSCompositingOperationSourceOver fraction:1
          respectFlipped:NO hints:nil];
    NSAppearance.currentAppearance = appearance;
    [NSGraphicsContext restoreGraphicsState];
    [[image representationUsingType:NSBitmapImageFileTypePNG properties:@{}]
        writeToFile:[NSString stringWithFormat:@"%@-%@.png", prefix, name] atomically:YES];
}

@end

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        static KMRPInstaller *installer;   // NSApplication holds its delegate weakly
        NSApplication *app = [NSApplication sharedApplication];
        installer = [KMRPInstaller new];
        app.delegate = installer;
        app.activationPolicy = NSApplicationActivationPolicyRegular;
        [app run];
    }
    return 0;
}
