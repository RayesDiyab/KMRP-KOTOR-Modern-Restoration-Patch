/*
  KMRP for macOS: the eighteen fonts at the text sizes in use, finished before anything measures
  them (handoff items 55, 56, 64 and 129). The port of the fonts in Windows'
  src/controller-native/K1RuntimeAssets.cpp, whose rules these are; docs/hd-original-font.md and
  docs/ingame-text-options.md describe them.

  Each style's atlases are one set of files in the bank, under private names, in the group
  make_kmrp_assets.py calls FONTS: kmrfogNN the game's own atlases (Original Font), kmrfhoNN HD Font,
  baked at 6x, and kmrfhdNN.txi, the retired font's metrics, every style's size reference (item
  129). A font is the style's TXI set to the size and, for HD Font, its atlas fitted to it, each
  new texel the area average of the old ones it covers, so it is drawn one texel to one pixel
  (FitAtlas). Made the first time a size is used, in the cache's fonts folder (CachedFont), and
  linked into the view of the set the game is shown, in place of the set's own files of those
  names. The view is searched before the override, so the style chosen shows whatever the override
  holds (handoff item 143, Windows 2026-11-08): Modded Font (FontStyle 3, offered only while the
  override has a font) shows the override's fonts, fitted to their size when larger
  (OverrideFontFitted), and Original Font and HD Font show KMRP's own for every name. Until then a
  font the override had was the game's to read from there whatever the choice, drawn at the size
  KMRP's own would have.

  The sizes are finished at the texture loader's end, before any caller can measure (item 55). The
  TXI load (0x1001f866a, Windows 0x00422AF0) has one common return, and every load passes there:
  the font's creation, ReloadFontMetrics at a change of size and Reload here. The widescreen patch
  has the instruction after it (0x1001f8883, its own font scaling, off in the .gui mode); this hook
  is the two before, whose bytes have no relative operand. Until this hook, ScaleOverrideFonts
  walked the texture list at GUI frames and panel starts, so the first line laid out with a new
  font was measured small (issue 63).

  A text size is a change of metrics alone, at once and without making anything; the atlases are
  fitted to it by Apply at Save, and by a change of style. Without the bank's font group (a bank
  built without it) everything here that makes fonts does nothing, the set's fonts stay and the
  sizes still follow the sliders by their metrics.

  CAurFontInfo: fontheight +0x04, baselineheight +0x08, texturewidth +0x0C, spacingR +0x10,
  spacingB +0x14. The texture: font information +0x48, name +0xBC (Windows +0x38, +0x98).
*/
#include "fonts.h"

#include "assets.h"
#include "../kmrp-layout/text_fit.h"
#include "../kmrp-layout/text_settings.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <dirent.h>
#include <iomanip>
#include <map>
#include <sstream>
#include <string>
#include <strings.h>
#include <sys/stat.h>
#include <unistd.h>
#include <vector>

namespace kmrp {

namespace assets {
// The bank's copy of a font source, by its private name (assets.cpp). Weak, so a build without it
// links, and a font style then cannot be made; assets.cpp's own takes its place.
__attribute__((weak)) bool FontSource(const std::string&, std::vector<unsigned char>&) { return false; }
}

namespace fonts {
namespace {

using namespace KmrpTextOptions;

const char* const kNames[18] = {
    "dialogfont10x10", "dialogfont10x10a", "dialogfont10x10b", "dialogfont12x16", "dialogfont16x16", "dialogfont16x16a",
    "dialogfont16x16b", "dialogfont32x32", "fnt_console", "fnt_credits", "fnt_creditsa", "fnt_creditsb", "fnt_d10x10b",
    "fnt_d16x16", "fnt_d16x16a", "fnt_d16x16b", "fnt_dialog16x16", "fnt_galahad14"};

// The size the HD atlas is baked at, and the one the text sizes are reckoned from.
const float kHdBakeScale = 6.0f, kSizeReferenceScale = 3.0f;

struct State {
    std::map<std::string, float> heights;   // by lower-case name: its height at the default text size
    std::map<std::string, float> first;     // as first parsed, for a font with no noted height
    std::map<std::string, bool> theirs;     // the override's font names, lower case
    bool listed = false;
    // The names the newest view holds. The game lists a folder once, when it is given one, so a
    // view's names are fixed then: a name taken out would be a file the game still lists and
    // cannot open, one put in would not be seen. Set as a view is prepared, before that.
    bool inView[18] = {};
    std::string root;   // the cache's folder for this build
    int height = 720;
};
State& TheState() {
    static State* state = new State;
    return *state;
}

std::string Lower(std::string text) {
    for (char& c : text) c = static_cast<char>(tolower(static_cast<unsigned char>(c)));
    return text;
}
int IndexOf(const std::string& lower) {
    for (int i = 0; i < 18; ++i)
        if (lower == kNames[i]) return i;
    return -1;
}

void ListOverride() {
    State& state = TheState();
    if (state.listed) return;
    state.listed = true;
    const std::string folder = assets::OverrideDirectory();
    DIR* dir = folder.empty() ? nullptr : opendir(folder.c_str());
    if (!dir) return;
    while (dirent* entry = readdir(dir)) {
        const std::string name = Lower(entry->d_name);
        const std::size_t dot = name.rfind('.');
        if (dot == std::string::npos) continue;
        const std::string kind = name.substr(dot);
        if (kind == ".tga" || kind == ".tpc" || kind == ".txi") state.theirs[name.substr(0, dot)] = true;
    }
    closedir(dir);
}
bool OverrideFont(const char* name) {
    ListOverride();
    return TheState().theirs.count(name) != 0;
}

bool Exists(const std::string& path) {
    struct stat info;
    return lstat(path.c_str(), &info) == 0;
}

// The path a font name has in the game's override, without extension, or empty.
std::string OverrideFontBase(const char* name) {
    const std::string folder = assets::OverrideDirectory();
    return folder.empty() ? folder : folder + "/" + name;
}
// The override's font of a name as a .tga with its .txi and no .tpc: one KMRP can show itself, as
// it is or fitted (the game prefers a .tpc wherever it is, so one with a .tpc is left to the
// override).
bool OverridePair(unsigned i) {
    const std::string base = OverrideFontBase(kNames[i]);
    return !base.empty() && Exists(base + ".tga") && Exists(base + ".txi") && !Exists(base + ".tpc");
}

// FNV-1a over 32-bit parts, a byte at a time, as Windows' over its DWORDs.
void Mix(std::uint64_t& id, std::uint32_t part) {
    for (int shift = 0; shift < 32; shift += 8) { id ^= (part >> shift) & 0xFF; id *= 1099511628211ull; }
}
void MixFile(std::uint64_t& id, const struct stat& info) {
    const auto size = static_cast<std::uint64_t>(info.st_size);
    const auto seconds = static_cast<std::uint64_t>(info.st_mtimespec.tv_sec);
    Mix(id, static_cast<std::uint32_t>(size >> 32));
    Mix(id, static_cast<std::uint32_t>(size));
    Mix(id, static_cast<std::uint32_t>(seconds >> 32));
    Mix(id, static_cast<std::uint32_t>(seconds));
    Mix(id, static_cast<std::uint32_t>(info.st_mtimespec.tv_nsec));
}
bool ReadFile(const std::string& path, std::vector<unsigned char>& data) {
    FILE* f = fopen(path.c_str(), "rb");
    if (!f) return false;
    data.clear();
    unsigned char buffer[65536];
    std::size_t n;
    while ((n = fread(buffer, 1, sizeof buffer, f)) > 0) data.insert(data.end(), buffer, buffer + n);
    const bool ok = !ferror(f);
    fclose(f);
    return ok;
}
bool WriteNew(const std::string& path, const std::vector<unsigned char>& data) {
    FILE* f = fopen(path.c_str(), "wb");
    if (!f) return false;
    const bool ok = fwrite(data.data(), 1, data.size(), f) == data.size();
    return fclose(f) == 0 && ok;
}
bool Link(const std::string& from, const std::string& to) {
    unlink(to.c_str());
    if (link(from.c_str(), to.c_str()) == 0) return true;
    return symlink(from.c_str(), to.c_str()) == 0;
}

// `fontheight` out of a .txi's text, or 0.
float FontHeightOf(const std::vector<unsigned char>& txi) {
    static const char key[] = "fontheight";
    const std::string text(txi.begin(), txi.end());
    for (std::size_t at = text.find(key); at != std::string::npos; at = text.find(key, at + 1)) {
        if (at != 0 && text[at - 1] != '\n' && text[at - 1] != '\r') continue;
        const double value = std::atof(text.c_str() + at + sizeof(key) - 1);
        if (value > 0.0 && value < 100.0) return static_cast<float>(value);
    }
    return 0.0f;
}

// The sources were baked at 3x, as the old per-size baker rounded them: half-even, in integers.
float FontTargetHeight(float sharedHeight, int screenHeight) {
    const std::uint64_t pixels = static_cast<unsigned>(std::lround(sharedHeight * 100.0f));
    // The old builder rounded its scale to six decimals before baking. Keep that detail too
    // (12-point text at 1050 lines otherwise changes by one pixel).
    const std::uint64_t scaledHeight = screenHeight > 720 ? screenHeight : 720;
    const std::uint64_t scaleMicros = (scaledHeight * 1000000 + 360) / 720;
    const std::uint64_t numerator = pixels * scaleMicros;
    const std::uint64_t denominator = 3000000;
    std::uint64_t rounded = numerator / denominator;
    const auto remainder = numerator % denominator;
    if (remainder * 2 > denominator || (remainder * 2 == denominator && (rounded & 1))) ++rounded;
    return static_cast<float>(rounded) / 100.0f;
}

bool FontTxiAtHeight(std::vector<unsigned char>& data, float height) {
    const float own = FontHeightOf(data);
    if (!(own > 0.001f) || !(height > 0.001f)) return false;
    const double factor = static_cast<double>(height) / own;
    std::istringstream input(std::string(data.begin(), data.end()));
    std::ostringstream output;
    std::string line;
    while (std::getline(input, line)) {
        std::istringstream field(line);
        std::string key;
        double value;
        field >> key;
        const bool dimension = key == "fontheight" || key == "baselineheight" || key == "texturewidth" || key == "spacingR" || key == "spacingB";
        if (dimension && field >> value)
            output << key << ' ' << std::fixed << std::setprecision(6) << (key == "fontheight" ? height : value * factor) << '\n';
        else
            output << line << '\n';
    }
    const std::string text = output.str();
    data.assign(text.begin(), text.end());
    return true;
}
// A TXI field set to a value, every other line as it was.
bool SetTxiField(std::vector<unsigned char>& data, const char* key, double value) {
    std::istringstream input(std::string(data.begin(), data.end()));
    std::ostringstream output;
    std::string line;
    bool found = false;
    while (std::getline(input, line)) {
        std::istringstream field(line);
        std::string name;
        field >> name;
        if (name == key) {
            output << key << ' ' << std::fixed << std::setprecision(6) << value << '\n';
            found = true;
        } else {
            output << line << '\n';
        }
    }
    const std::string text = output.str();
    data.assign(text.begin(), text.end());
    return found;
}

// One axis of an image resampled: each new texel the average of the old ones it covers, weighted by
// how much of each it covers (shrinking), or the two nearest blended by distance (growing).
// `stride` is how far apart one line's texels are.
void ResampleAxis(const std::vector<float>& in, int inLength, int lines, int stride, int lineStride, std::vector<float>& out,
                  int outLength, int outStride, int outLineStride) {
    const double scale = static_cast<double>(inLength) / outLength;
    for (int o = 0; o < outLength; ++o) {
        const double start = o * scale, end = (o + 1) * scale;
        int first, last;
        double weights[64];
        if (scale >= 1.0) {
            first = static_cast<int>(start);
            last = (std::min)(inLength - 1, static_cast<int>(std::ceil(end)) - 1);
            if (last - first >= 64) last = first + 63;
            for (int i = first; i <= last; ++i)
                weights[i - first] = ((std::min)(end, i + 1.0) - (std::max)(start, static_cast<double>(i))) / scale;
        } else {
            const double centre = (o + 0.5) * scale - 0.5;
            first = (std::max)(0, static_cast<int>(std::floor(centre)));
            last = (std::min)(inLength - 1, first + 1);
            const double t = (std::min)(1.0, (std::max)(0.0, centre - first));
            weights[0] = last == first ? 1.0 : 1.0 - t;
            if (last != first) weights[1] = t;
        }
        for (int line = 0; line < lines; ++line) {
            double sum = 0.0;
            for (int i = first; i <= last; ++i)
                sum += weights[i - first] * in[static_cast<std::size_t>(line) * lineStride + static_cast<std::size_t>(i) * stride];
            out[static_cast<std::size_t>(line) * outLineStride + static_cast<std::size_t>(o) * outStride] = static_cast<float>(sum);
        }
    }
}

// An atlas (an uncompressed 32-bit TGA, white letters in alpha, as tools/build_scaled_fonts.write_tga
// writes them) made `factor` times its size. Its coordinates are fractions of the atlas, so they
// stay right; the TXI is given the new width. False if the file is not such a TGA.
bool FitAtlas(std::vector<unsigned char>& tga, float factor, int& newWidth) {
    if (tga.size() < 18 || tga[1] != 0 || tga[2] != 2 || tga[16] != 32) return false;
    const std::size_t offset = 18 + tga[0];
    const int width = tga[12] | (tga[13] << 8), height = tga[14] | (tga[15] << 8);
    if (width <= 0 || height <= 0 || tga.size() < offset + static_cast<std::size_t>(width) * height * 4) return false;
    newWidth = (std::max)(1, static_cast<int>(std::lround(width * factor)));
    const int newHeight = (std::max)(1, static_cast<int>(std::lround(height * static_cast<double>(newWidth) / width)));
    if (newWidth == width && newHeight == height) return true;
    const std::size_t pixels = static_cast<std::size_t>(width) * height;
    // White letters need only their alpha resampled; an atlas with colour in it (fnt_galahad14, the
    // original's own letters with their dark edge) has every channel resampled.
    bool white = true;
    for (std::size_t i = 0; i < pixels && white; ++i)
        white = tga[offset + i * 4] == 255 && tga[offset + i * 4 + 1] == 255 && tga[offset + i * 4 + 2] == 255;
    std::vector<unsigned char> out(tga.begin(), tga.begin() + offset);
    out[12] = static_cast<unsigned char>(newWidth & 0xFF);
    out[13] = static_cast<unsigned char>(newWidth >> 8);
    out[14] = static_cast<unsigned char>(newHeight & 0xFF);
    out[15] = static_cast<unsigned char>(newHeight >> 8);
    const std::size_t newPixels = static_cast<std::size_t>(newWidth) * newHeight;
    out.resize(offset + newPixels * 4, 255);
    std::vector<float> plane(pixels), across(static_cast<std::size_t>(newWidth) * height), down(newPixels);
    for (int channel = white ? 3 : 0; channel < 4; ++channel) {
        for (std::size_t i = 0; i < pixels; ++i) plane[i] = tga[offset + i * 4 + channel];
        // Across, then down: each pass reads one plane and writes the next.
        ResampleAxis(plane, width, height, 1, width, across, newWidth, 1, newWidth);
        ResampleAxis(across, height, newWidth, newWidth, 1, down, newHeight, newWidth, 1);
        for (std::size_t i = 0; i < newPixels; ++i) {
            const long v = std::lround(down[i]);
            out[offset + i * 4 + channel] = static_cast<unsigned char>(v < 0 ? 0 : v > 255 ? 255 : v);
        }
    }
    tga.swap(out);
    return true;
}

bool Source(const char* prefix, unsigned i, const char* extension, std::vector<unsigned char>& data) {
    char name[32];
    std::snprintf(name, sizeof name, "%s%02u%s", prefix, i, extension);
    return assets::FontSource(name, data);
}

// The size a font is drawn at on a screen `height` lines high: `target` at the default text size
// (also what an override font of that name is drawn at), `sized` at the text size in use.
bool FontSizes(unsigned i, int height, float& target, float& sized) {
    std::vector<unsigned char> data;
    if (!Source("kmrfhd", i, ".txi", data)) return false;
    target = FontTargetHeight(FontHeightOf(data) * kSizeReferenceScale / kHdBakeScale, height);
    sized = target * (static_cast<float>(textfit::TextSizeForFont(kNames[i])) / Default);
    return target > 0.0f;
}

// One font of a style at one size, in the cache's fonts folder, made the first time: the style's
// TXI set to the size and, for HD Font, its atlas fitted to it. Windows measured 1.0 to 1.3 s for
// all eighteen, on every start and every change of size, before it kept them.
bool CachedFont(const char* prefix, unsigned i, float sized, bool fitted, std::string& txiPath, std::string& tgaPath) {
    unsigned bits;
    std::memcpy(&bits, &sized, sizeof bits);
    char number[32];
    std::snprintf(number, sizeof number, "%02u-%08X", i, bits);
    const std::string folder = TheState().root + "/fonts";
    mkdir(folder.c_str(), 0755);
    const std::string base = folder + "/" + prefix + number;
    txiPath = base + ".txi";
    tgaPath = base + ".tga";
    if (Exists(txiPath) && Exists(tgaPath)) return true;
    std::vector<unsigned char> txi, tga;
    if (!Source(prefix, i, ".txi", txi) || !Source(prefix, i, ".tga", tga)) return false;
    const float own = FontHeightOf(txi);
    if (!(own > 0.001f) || !FontTxiAtHeight(txi, sized)) return false;
    if (fitted) {
        int newWidth = 0;
        if (!FitAtlas(tga, sized / own, newWidth) || !SetTxiField(txi, "texturewidth", newWidth / 100.0)) return false;
    }
    // Each under a working name, the atlas first: a TXI is never there without it.
    const std::string work = ".tmp" + std::to_string(getpid());
    const bool ok = WriteNew(tgaPath + work, tga) && rename((tgaPath + work).c_str(), tgaPath.c_str()) == 0 &&
        WriteNew(txiPath + work, txi) && rename((txiPath + work).c_str(), txiPath.c_str()) == 0;
    unlink((tgaPath + work).c_str());
    unlink((txiPath + work).c_str());
    return ok;
}

// A font the override has as a .tga with its .txi, fitted to the size it is drawn at as KMRP's own
// HD fonts are (FitAtlas), in the cache's fonts folder (handoff item 143). Until then such a font
// only had its metrics scaled, and the game shrank its whole atlas each time it drew: the KMRP
// Font Converter writes six times the original size, 2 to 3 times larger than drawn at 1080 and
// 1440 lines, with no mipmaps. The mod's files are read, never changed: the copy is made from
// them, under a name of their sizes and times. False, and the font shown as it is, for a .tpc,
// no .txi, an atlas that is not uncompressed 32-bit, or one at or below the size.
bool OverrideFontFitted(unsigned i, float sized, std::string& txiPath, std::string& tgaPath) {
    const std::string base = OverrideFontBase(kNames[i]);
    struct stat tgaInfo, txiInfo;
    if (base.empty() || Exists(base + ".tpc") || stat((base + ".tga").c_str(), &tgaInfo) != 0 ||
        stat((base + ".txi").c_str(), &txiInfo) != 0) return false;
    std::uint64_t id = 1469598103934665603ull;   // a changed file is a new name
    MixFile(id, tgaInfo);
    MixFile(id, txiInfo);
    unsigned bits;
    std::memcpy(&bits, &sized, sizeof bits);
    char number[64];
    std::snprintf(number, sizeof number, "-%016llX-%08X", static_cast<unsigned long long>(id), bits);
    const std::string folder = TheState().root + "/fonts";
    mkdir(folder.c_str(), 0755);
    const std::string cached = folder + "/ovr-" + kNames[i] + number;
    txiPath = cached + ".txi";
    tgaPath = cached + ".tga";
    if (Exists(txiPath) && Exists(tgaPath)) return true;
    std::vector<unsigned char> txi, tga;
    if (!ReadFile(base + ".txi", txi)) return false;
    const float own = FontHeightOf(txi);
    if (!(own > 0.001f) || !(sized < own)) return false;   // only ever made smaller
    if (!ReadFile(base + ".tga", tga) || tga.size() < 18 || tga[1] != 0 || tga[2] != 2 || tga[16] != 32) return false;
    const int width = tga[12] | (tga[13] << 8), height = tga[14] | (tga[15] << 8);
    int newWidth = 0;
    if (!FontTxiAtHeight(txi, sized) || !FitAtlas(tga, sized / own, newWidth) ||
        !SetTxiField(txi, "texturewidth", newWidth / 100.0)) return false;
    const std::string work = ".tmp" + std::to_string(getpid());
    const bool ok = WriteNew(tgaPath + work, tga) && rename((tgaPath + work).c_str(), tgaPath.c_str()) == 0 &&
        WriteNew(txiPath + work, txi) && rename((txiPath + work).c_str(), txiPath.c_str()) == 0;
    unlink((tgaPath + work).c_str());
    unlink((txiPath + work).c_str());
    if (ok)
        std::fprintf(stderr, "[KMRP] the override's font %s fitted from %dx%d to %dx%d (%.3f) for the size in use\n",
                     kNames[i], width, height, tga[12] | (tga[13] << 8), tga[14] | (tga[15] << 8), sized / own);
    return ok;
}

// A file of the override copied into `to`, never linked: a hard link is the mod's own file.
bool CopyIn(const std::string& from, const std::string& to) {
    std::vector<unsigned char> data;
    unlink(to.c_str());
    return ReadFile(from, data) && WriteNew(to, data);
}

// The style's fonts at the sizes in use, as links in `view`. Every source of KMRP's is checked to
// be there before anything changes. `fresh`: a view the game has not listed yet, whose names are
// chosen here (State::inView); every other only has its names relinked. Modded Font shows a font
// the override has as a .tga and .txi from there, fitted when larger and else as it is; any other
// font of the override's (one with a .tpc, or part of a pair) is left out of the view so the game
// reads it from the override; KMRP's HD Font stands in for the names the override lacks.
bool LinkFonts(const std::string& view, bool fresh) {
    if (view.empty()) return false;
    State& state = TheState();
    const int style = textfit::FontStyle();
    const bool modded = style == Modded;
    const bool fitted = style != Original;
    const char* const prefix = style == Original ? "kmrfog" : "kmrfho";
    if (fresh)
        for (unsigned i = 0; i < 18; ++i) state.inView[i] = !(modded && OverrideFont(kNames[i]) && !OverridePair(i));
    const auto theirs = [&](unsigned i) { return modded && OverrideFont(kNames[i]) && OverridePair(i); };
    for (unsigned i = 0; i < 18; ++i) {
        if (!state.inView[i] || theirs(i)) continue;
        std::string txi, tga;
        float target, sized;
        if (!FontSizes(i, state.height, target, sized) || !CachedFont(prefix, i, sized, fitted, txi, tga)) return false;
    }
    for (unsigned i = 0; i < 18; ++i) {
        const std::string name = view + "/" + kNames[i];
        if (!state.inView[i]) {
            if (fresh) { unlink((name + ".tga").c_str()); unlink((name + ".txi").c_str()); }
            continue;
        }
        float target, sized;
        std::string txi, tga;
        if (!FontSizes(i, state.height, target, sized)) return false;
        if (theirs(i)) {
            if (OverrideFontFitted(i, sized, txi, tga)) {
                if (!Link(tga, name + ".tga") || !Link(txi, name + ".txi")) return false;
                continue;
            }
            const std::string base = OverrideFontBase(kNames[i]);
            if (!CopyIn(base + ".tga", name + ".tga") || !CopyIn(base + ".txi", name + ".txi")) return false;
            continue;
        }
        if (!CachedFont(prefix, i, sized, fitted, txi, tga)) return false;
        if (!Link(tga, name + ".tga") || !Link(txi, name + ".txi")) return false;
    }
    return true;
}

}  // namespace

bool IsFont(const char* name) { return name && IndexOf(Lower(name)) >= 0; }

void Prepare(const std::string& whole, const std::string& view, int height) {
    State& state = TheState();
    state.height = height;
    const std::size_t slash = view.rfind('/');
    if (slash != std::string::npos) state.root = view.substr(0, slash);
    state.heights.clear();
    for (unsigned i = 0; i < 18; ++i) {
        float target, sized;
        if (FontSizes(i, height, target, sized)) {
            state.heights[kNames[i]] = target;
        } else {
            // A bank with no font group: the set's own font is the size at 50%.
            std::vector<unsigned char> txi;
            const float own = ReadFile(whole + "/" + kNames[i] + ".txi", txi) ? FontHeightOf(txi) : 0.0f;
            if (own > 0.0f) state.heights[kNames[i]] = own;
        }
    }
    if (!LinkFonts(view, true)) fprintf(stderr, "[KMRP] the fonts of the style in use could not be made: the set's stay\n");
}

bool Apply() {
    const bool linked = LinkFonts(assets::NewestSetDirectory(), false);
    assets::ReleaseUnpacked();   // the blocks read for the sources, up to 48 MB, not kept for the run
    return linked;
}

// The fonts the override has, as listed at the start: 0 when none, else a number of their names,
// sizes and times, so a new set can be told from one already seen (text_settings.cpp: Modded Font
// is chosen by itself only for a new set).
std::uint64_t OverrideFontSet() {
    std::uint64_t id = 1469598103934665603ull;
    bool any = false;
    for (unsigned i = 0; i < 18; ++i) {
        if (!OverrideFont(kNames[i])) continue;
        any = true;
        Mix(id, i);
        const std::string base = OverrideFontBase(kNames[i]);
        for (const char* extension : {".tga", ".tpc", ".txi"}) {
            struct stat info;
            if (base.empty() || stat((base + extension).c_str(), &info) != 0) { Mix(id, 0xFFFFFFFFu); continue; }
            MixFile(id, info);
        }
    }
    return any ? (id ? id : 1) : 0;
}

// Reload as Windows' page does it: all styles keep the same native texture and font objects, the
// reset frees image and OpenGL state, not the font information strings hold. The queue is the
// engine's build queue, which also uploads and rebuilds its registry of texture names.
//   0x100635b58, 0x100635b60  the textures, how many (Windows 0x7A4798, 0x7A479C)
//   0x1001f7d58  CAurTextureBasic's reset (0x420670)
//   0x1001f866a  the TXI load (texture, name) (0x422AF0)
//   0x1001f7d16  append to the build queue at 0x100635b88 (0x46BD10, 0x7A4770)
//   0x1001fa0cc  the queue built (0x4217F0)
void Reload(bool images) {
    void** const textures = *reinterpret_cast<void***>(0x100635b58);
    const int count = *reinterpret_cast<const int*>(0x100635b60);
    if (!textures || count <= 0 || count > 0x100000) return;
    for (int i = 0; i < count; ++i) {
        char* const texture = static_cast<char*>(textures[i]);
        if (!texture || !*reinterpret_cast<void**>(texture + 0x48)) continue;
        char name[17] = {};
        std::memcpy(name, texture + 0xbc, 16);
        if (!IsFont(name)) continue;
        if (images) reinterpret_cast<void (*)(void*)>(0x1001f7d58)(texture);
        reinterpret_cast<void (*)(void*, const char*)>(0x1001f866a)(texture, texture + 0xbc);
        if (images) reinterpret_cast<void (*)(void*, void*)>(0x1001f7d16)(reinterpret_cast<void*>(0x100635b88), texture);
    }
    if (images) reinterpret_cast<void (*)()>(0x1001fa0cc)();
}

}  // namespace fonts
}  // namespace kmrp

// The TXI load's common return (0x1001f887a, Windows 0x00422CC1), before the texture reaches any
// caller: r14 the texture. Both loose TXI and embedded metadata have finished parsing. A missing
// TXI and a texture that is no font have no font information. The five dimensional fields are
// scaled to the height this font is to have, glyph coordinates and the source files staying, and
// fontheight is set exactly, so repeat notifications cannot compound.
extern "C" __attribute__((visibility("default"))) void KmrpFontMetricsLoaded(void* object) {
    using namespace kmrp::fonts;
    if (!object) return;
    char* const texture = static_cast<char*>(object);
    float* const info = *reinterpret_cast<float**>(texture + 0x48);
    if (!info) return;
    char name[17] = {};
    std::memcpy(name, texture + 0xbc, 16);
    const std::string lower = Lower(name);
    if (IndexOf(lower) < 0) return;
    const float own = info[1];
    if (!(own > 0.001f) || !(own < 100.0f)) return;
    State& state = TheState();
    auto found = state.heights.find(lower);
    if (found == state.heights.end()) {
        // Parsed before the view was prepared, or a font with no height noted: what it holds is
        // the size at 50%.
        found = state.first.find(lower);
        if (found == state.first.end()) found = state.first.emplace(lower, own).first;
    }
    const float target = found->second * (static_cast<float>(kmrp::textfit::TextSizeForFont(name)) / KmrpTextOptions::Default);
    const float factor = target / own;
    if (!(factor > 0.01f) || !(factor < 128.0f) || own == target) return;
    for (int field = 1; field <= 5; ++field) info[field] *= factor;
    info[1] = target;
}
