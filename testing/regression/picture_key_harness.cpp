// K1PictureKey against the comparison it replaced, on awkward names. Test-PictureKey.py runs it.
#include "K1PictureKey.h"
#include <cstdio>
#include <cstring>
#include <random>
#include <string.h>
#include <string>
#include <vector>

// FindK1Scene's test, as it was until 2026-11-01: `name` is a scene's, `fill` a border's.
static bool OldSceneMatch(const std::string& name, const char* fill)
{
    return _strnicmp(name.c_str(), fill, 16) == 0 && name.size() <= 16 &&
           (name.size() == 16 || fill[name.size()] == '\0');
}

int main()
{
    std::mt19937 random(82);
    const char letters[] = "aAbBzZ_0-kKmMrR";
    const auto word = [&](int length) {
        std::string text;
        for (int i = 0; i < length; ++i) text.push_back(letters[random() % (sizeof letters - 1)]);
        return text;
    };
    int checked = 0, matched = 0, failures = 0;
    const auto check = [&](const std::string& name, const char* fill) {
        const bool old = OldSceneMatch(name, fill);
        const bool now = name.size() <= 16 && K1PictureKey(name.c_str()) == K1PictureKey(fill);
        ++checked;
        matched += old;
        if (old != now && ++failures <= 5) std::printf("FAIL %s against %.20s: old %d, new %d\n", name.c_str(), fill, old, now);
    };
    for (int round = 0; round < 400000; ++round) {
        const int length = 1 + random() % 18;
        const std::string name = word(length);
        std::string fill = name;
        switch (random() % 6) {
        case 0: for (char& c : fill) if (c >= 'a' && c <= 'z') c = static_cast<char>(c - 32); break;
        case 1: for (char& c : fill) if (c >= 'A' && c <= 'Z') c = static_cast<char>(c + 32); break;
        case 2: fill += word(1 + random() % 4); break;       // longer than the name
        case 3: if (fill.size() > 1) fill.pop_back(); break; // shorter
        case 4: fill = word(length); break;
        default: break;
        }
        check(name, fill.c_str());
    }
    // A border's fill is a 16-byte field read as it stands: nothing need end it inside them.
    char field[17];
    std::memcpy(field, "kmzs1234560800a0", 16);
    field[16] = 'X';
    check("kmzs1234560800a0", field);
    check("KMZS1234560800A0", field);
    check("kmzs1234560800a", field);
    check("", "");
    check("", "a");
    std::printf("%d pairs, %d matching, %d differ from the old comparison\n", checked, matched, failures);
    if (matched < 1000) {
        std::puts("FAIL too few matches to mean anything");
        return 1;
    }
    return failures ? 1 : 0;
}
