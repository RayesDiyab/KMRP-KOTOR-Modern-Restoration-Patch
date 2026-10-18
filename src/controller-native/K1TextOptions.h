#pragma once

// Core GUI work. Controls inherit the graphics layout that is actually loaded.
void KmrpTextOptionsFrameK1(void* manager);
void KmrpTextOptionsDestroyedK1(void* panel);

int KmrpTextSizePercentK1();
int KmrpTextSizeForFontK1(const char* font);
int KmrpTextFontStyleK1();
// Changes are queued by callbacks and applied at the next GUI frame boundary.
bool KmrpSetTextPreferencesK1(int percent, int style);
