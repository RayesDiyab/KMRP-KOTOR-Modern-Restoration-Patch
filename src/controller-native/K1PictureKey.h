#pragma once
#include <string>

// The key a picture's or a drawing's name is found by: a resref's 16 characters at most,
// folded as the engine's names are compared, so `fill` need not end within them. Two names
// match exactly when their keys are equal (Test-PictureKey checks this against the
// comparison it replaced: _strnicmp over 16 characters).
inline std::string K1PictureKey(const char* name)
{
    std::string key;
    for (int i = 0; i < 16 && name[i]; ++i) {
        key.push_back(name[i] >= 'A' && name[i] <= 'Z' ? static_cast<char>(name[i] + ('a' - 'A')) : name[i]);
    }
    return key;
}
