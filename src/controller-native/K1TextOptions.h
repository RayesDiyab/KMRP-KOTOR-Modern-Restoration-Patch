#pragma once

// Core GUI work. Controls inherit the graphics layout that is actually loaded.
void KmrpTextOptionsFrameK1(void* manager);
void KmrpTextOptionsDestroyedK1(void* panel);

// The "Text Size and Font" button the page added to a Graphics Options screen, or null.
void* KmrpTextOptionsEntryK1(void* owner);
// The page is open (the HUD Size page's entry shows no A over it).
bool KmrpTextOptionsOpenK1();
int KmrpTextSizePercentK1();
int KmrpTextSizeForFontK1(const char* font);
int KmrpTextFontStyleK1();
// Changes are queued by callbacks and applied at the next GUI frame boundary.
bool KmrpSetTextPreferencesK1(int percent, int style);
