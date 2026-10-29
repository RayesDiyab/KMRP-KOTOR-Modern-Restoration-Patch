#pragma once
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif
typedef struct { int panel[4], cancel[4]; char fill[17]; } K1PreloadClassInfo;
typedef struct { char fill[17]; int width, height; } K1PreloadPicture;
int KmrpReadPreloadGui(const char* key, const char* source, const char* name,
                       K1PreloadClassInfo* info, K1PreloadPicture* pictures, int capacity);
unsigned char* KmrpReadPreloadTexture(const char* game, const char* assets, const char* name, int* width, int* height);
#ifdef __cplusplus
}
#endif
