// The rumble mixer's own functions, from the shipped source, without a game: the file is
// included whole, so the harness reaches what its anonymous namespace holds, and only the
// three calls it makes into the controller module are supplied here. Test-RumbleMixer.py
// builds and runs this. Nothing here reads engine memory: the mixer's part never does.
#include "../../src/controller-native/K1Rumble.cpp"

void* ClientExoAppK1() { return nullptr; }
int InputClassK1() { return 0; }
std::uint32_t CurrentTargetK1() { return 0x7F000000u; }

static int failures = 0;
static void Check(bool condition, const char* text)
{
    std::printf("%s  %s\n", condition ? "ok  " : "FAIL", text);
    if (!condition) ++failures;
}

static bool Near(float a, float b) { return std::fabs(a - b) < 1e-5f; }

static void Reset(int mode = MODE_ENHANCED)
{
    StopAll("test");
    g_clock = 0.0f;
    g_settings.mode = mode;
    g_settings.strength = 1.0f;
    g_settings.hum = 0.06f;
    g_settings.humPulse = 0.1f;
    g_settings.humPeriodMin = 0.5f;
    g_settings.humPeriodMax = 0.5f;
    g_settings.loaded = true;
    g_settings.nextCheck = GetTickCount() + 60000;
    g_humPulse = { -1.0f, 0, 0, 1u };
}

static const float kUp[] = { 0.0f, 1.0f };
static const float kUpTimes[] = { 0.0f, 1.0f };
static const float kFlat[] = { 0.5f, 0.5f };
static const float kFlatTimes[] = { 0.0f, 2.0f };

static RumbleRowK1 Row(const float* heavy, const float* heavyTimes, int heavyCount, const float* light,
                       const float* lightTimes, int lightCount, int loop)
{
    RumbleRowK1 row{};
    row.heavyMagnitudes = heavy;
    row.heavyTimes = heavyTimes;
    row.heavyCount = heavyCount;
    row.lightMagnitudes = light;
    row.lightTimes = lightTimes;
    row.lightCount = lightCount;
    row.loop = loop;
    return row;
}

int main()
{
    bool done = false;

    // The evaluator, against CSWRumblePattern::GetMagnitude's rules.
    Check(Near(Evaluate(kUp, kUpTimes, 2, 0.25f, false, done), 0.25f) && !done, "linear between two keyframes");
    Check(Near(Evaluate(kUp, kUpTimes, 2, 1.5f, false, done), 0.0f) && done, "past the last keyframe it is done");
    Check(Near(Evaluate(kUp, kUpTimes, 2, 1.25f, true, done), 0.25f) && !done, "a loop wraps by the last keyframe's time");
    Check(Near(Evaluate(nullptr, nullptr, 0, 0.5f, false, done), 0.0f) && done, "a motor with no keyframes is done");
    static const float kStep[] = { 0.2f, 0.8f, 0.3f }, kStepTimes[] = { 0.0f, 0.5f, 0.5f };
    Check(Near(Evaluate(kStep, kStepTimes, 3, 0.25f, false, done), 0.5f), "a span up to a step");
    Evaluate(kStep, kStepTimes, 3, 0.5f, false, done);
    Check(!done, "two keyframes at one time are not a division by zero");

    // The mix: the maximum per motor, never the sum.
    const RumbleRowK1 ramp = Row(kUp, kUpTimes, 2, kFlat, kFlatTimes, 2, 0);
    const RumbleRowK1 flat = Row(kFlat, kFlatTimes, 2, kFlat, kFlatTimes, 2, 0);
    float heavy, light;
    Reset();
    Play(&flat, 1.0f, ORIGINAL, "one", 1.0f);
    Play(&flat, 1.0f, ORIGINAL, "two", 1.0f);
    Mix(heavy, light);
    Check(Near(heavy, 0.5f) && Near(light, 0.5f), "two 50% effects stay 50%");
    Reset();
    Play(&ramp, 1.0f, ORIGINAL, "ramp", 1.0f);
    Play(&flat, 0.5f, ORIGINAL, "quiet", 1.0f);
    g_clock = 0.75f;
    Mix(heavy, light);
    Check(Near(heavy, 0.75f) && Near(light, 0.5f), "each motor takes its own strongest layer");
    Reset();
    Play(&flat, 0.5f, ORIGINAL, "scaled", 0.5f);
    Mix(heavy, light);
    Check(Near(heavy, 0.25f), "a layer's scale reaches the output");
    Reset();
    Play(&flat, 1.0f, ORIGINAL, "ending", 1.0f);
    g_clock = 3.0f;
    Mix(heavy, light);
    Check(!g_layers[0].active && Near(heavy, 0.0f), "a finished layer is freed");
    Reset();
    const RumbleRowK1 onlyLight = Row(nullptr, nullptr, 0, kFlat, kFlatTimes, 2, 0);
    Play(&onlyLight, 1.0f, ORIGINAL, "light", 1.0f);
    g_clock = 1.0f;
    Mix(heavy, light);
    Check(g_layers[0].active && Near(light, 0.5f), "a layer lives while either motor plays");

    // Modes.
    Reset(MODE_OFF);
    Play(&flat, 1.0f, ORIGINAL, "off", 1.0f);
    Check(!g_layers[0].active, "Off plays nothing");
    Reset(MODE_ORIGINAL);
    Play(&flat, 1.0f, ENHANCED, "enhanced", 1.0f);
    Play(&flat, 1.0f, RESTORED, "restored", 1.0f);
    Check(!g_layers[0].active && !g_layers[1].active, "Original plays neither Restored nor Enhanced");
    Play(&flat, 1.0f, ORIGINAL, "original", 1.0f);
    Check(g_layers[0].active, "Original plays BioWare's");
    Reset();
    Play(&flat, 0.0f, ORIGINAL, "silent", 1.0f);
    Play(nullptr, 1.0f, ORIGINAL, "no row", 1.0f);
    Check(!g_layers[0].active, "scale 0 and a missing row play nothing");

    // Merging and keys.
    Reset();
    Play(&flat, 0.4f, ORIGINAL, "first", 1.0f, KEY_NONE, 0.1f);
    g_clock = 0.05f;
    Play(&flat, 0.8f, ORIGINAL, "second", 1.0f, KEY_NONE, 0.1f);
    int live = 0;
    for (const Layer& layer : g_layers) live += layer.active;
    Check(live == 1 && Near(g_layers[0].scale, 0.8f), "a repeat inside the merge time joins it, at the larger scale");
    g_clock = 0.2f;
    Play(&flat, 0.3f, ORIGINAL, "third", 1.0f, KEY_NONE, 0.1f);
    live = 0;
    for (const Layer& layer : g_layers) live += layer.active;
    Check(live == 2, "after the merge time it stacks");
    Reset();
    Play(&flat, 1.0f, ORIGINAL, "keyed", 1.0f, 77u);
    g_clock = 0.1f;
    Play(&ramp, 1.0f, ORIGINAL, "keyed again", 1.0f, 77u);
    live = 0;
    for (const Layer& layer : g_layers) live += layer.active;
    Check(live == 1 && g_layers[0].row == &ramp, "a key has one layer, the newest");
    Stop(77u, "test");
    Check(!Find(77u), "Stop ends a key");
    Stop(KEY_NONE, "test");

    // A looping layer held by a condition.
    const RumbleRowK1 loop = Row(kFlat, kFlatTimes, 2, kFlat, kFlatTimes, 2, 1);
    Reset();
    Hold(88u, true, &loop, 0.5f, ORIGINAL, "start", "stop");
    Hold(88u, true, &loop, 0.25f, ORIGINAL, "start", "stop");
    Check(Find(88u) && Near(Find(88u)->scale, 0.25f), "Hold keeps one layer and follows the scale");
    g_clock = 9.0f;
    Mix(heavy, light);
    Check(Find(88u) && Near(heavy, 0.125f), "a loop outlasts its length");
    Hold(88u, false, &loop, 0.5f, ORIGINAL, "start", "stop");
    Check(!Find(88u), "Hold ends it");

    // A full table: the oldest unkeyed layer goes, a keyed one never does.
    Reset();
    for (int i = 0; i < K1_RUMBLE_LAYERS; ++i) {
        g_clock = 0.01f * static_cast<float>(i);
        Play(&loop, 1.0f, ORIGINAL, "fill", 1.0f, i == 0 ? 99u : KEY_NONE);
    }
    const float secondOldest = g_layers[1].start;
    g_clock = 1.0f;
    Play(&ramp, 1.0f, ORIGINAL, "one more", 1.0f);
    Check(Find(99u) != nullptr, "a full table keeps the keyed layer");
    Check(g_layers[1].row == &ramp, "and gives the oldest unkeyed slot to the new one");
    Check(secondOldest >= 0.0f, "the table held its layers");
    Reset();
    for (int i = 0; i < K1_RUMBLE_LAYERS; ++i) Play(&loop, 1.0f, ORIGINAL, "keyed", 1.0f, 200u + i);
    Play(&ramp, 1.0f, ORIGINAL, "no room", 1.0f);
    bool rampIn = false;
    for (const Layer& layer : g_layers) rampIn |= layer.row == &ramp;
    Check(!rampIn, "a table of keyed layers takes nothing");

    // The hum: gated on the light motor only, on a fixed rhythm here.
    Reset();
    Play(&loop, 1.0f, ORIGINAL, "hum", 1.0f, KEY_HUM);
    Mix(heavy, light);
    Check(Near(light, 0.5f) && Near(heavy, 0.5f), "the hum starts with a pulse");
    g_clock = 0.3f;
    Mix(heavy, light);
    Check(Near(light, 0.0f) && Near(heavy, 0.5f), "between pulses the light motor is off and the heavy one is not");
    g_clock = 0.55f;
    Mix(heavy, light);
    Check(Near(light, 0.5f), "the next pulse comes at the period");
    Reset();
    g_settings.humPulse = 0.0f;
    Play(&loop, 1.0f, ORIGINAL, "steady", 1.0f, KEY_HUM);
    g_clock = 0.3f;
    Mix(heavy, light);
    Check(Near(light, 0.5f), "pulse 0 is a steady hum");

    // BioWare's table: every pattern is reachable and its keyframes are in time order.
    int rows = 0;
    bool ordered = true, known = true;
    for (int index = 0; index < K1_RUMBLE_PATTERN_COUNT; ++index) {
        const RumbleRowK1* const row = Pattern(index);
        if (!row) { known = false; continue; }
        ++rows;
        for (int i = 1; i < row->heavyCount; ++i) ordered &= row->heavyTimes[i] >= row->heavyTimes[i - 1];
        for (int i = 1; i < row->lightCount; ++i) ordered &= row->lightTimes[i] >= row->lightTimes[i - 1];
    }
    Check(known && rows == K1_RUMBLE_PATTERN_COUNT, "every BioWare pattern is there");
    Check(ordered, "keyframes run forward in time");

    std::printf("%d failed\n", failures);
    return failures ? 1 : 0;
}
