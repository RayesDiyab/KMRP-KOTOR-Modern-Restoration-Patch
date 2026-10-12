/*
  KMRP for macOS, the Mac App Store's game: the library the game is started with.

  The App Store's game cannot be changed (docs/macos-app-store.md, section 3: one file added to
  its bundle and its launcher no longer starts), so nothing is written into it. KMRP's launcher
  (launcher.c) starts Aspyr's own launcher with this library in DYLD_INSERT_LIBRARIES, which the
  game accepts (no hardened runtime) and hands on to KOTOR_Exe.

  The same environment reaches Aspyr's launcher first, so KotorPatcher is loaded only when the
  process is KOTOR_Exe, and only when that file is the build the hooks were translated for
  (KMRP_APPSTORE_EXE_SHA, given by the build): after an update of the game from the App Store
  the game runs without KMRP instead of with hooks at the wrong addresses.

  KMRP_PATCHER is KotorPatcher.dylib's path; it finds patch_config.toml and patches/ beside
  itself.

  Fullscreen: for Steam's game the installer sets DisplayFullScreen in Aspyr's preferences
  (kmrp-mac.sh, set_fullscreen). The App Store game's preferences are in its container, closed
  to the installer, so this library sets the same key from inside the game, before Aspyr's
  launcher reads it. Once only (KMRPFullScreenSet beside it): windowed mode chosen afterwards in
  Aspyr's launcher stays.
*/
#include <CommonCrypto/CommonDigest.h>
#include <CoreFoundation/CoreFoundation.h>
#include <dlfcn.h>
#include <fcntl.h>
#include <mach-o/dyld.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#ifndef KMRP_APPSTORE_EXE_SHA
#error "KMRP_APPSTORE_EXE_SHA: the SHA-256 of the App Store's KOTOR_Exe, lower case"
#endif

static int Sha256Of(const char* path, char hex[65]) {
    const int fd = open(path, O_RDONLY);
    if (fd < 0) return 0;
    CC_SHA256_CTX context;
    CC_SHA256_Init(&context);
    static unsigned char buffer[1 << 16];
    ssize_t got;
    while ((got = read(fd, buffer, sizeof buffer)) > 0) CC_SHA256_Update(&context, buffer, (CC_LONG)got);
    close(fd);
    unsigned char digest[CC_SHA256_DIGEST_LENGTH];
    CC_SHA256_Final(digest, &context);
    for (int i = 0; i < CC_SHA256_DIGEST_LENGTH; i++) snprintf(hex + 2 * i, 3, "%02x", digest[i]);
    return got == 0;
}

static void FullscreenOnce(void) {
    const CFStringRef app = kCFPreferencesCurrentApplication;
    CFPropertyListRef done = CFPreferencesCopyAppValue(CFSTR("KMRPFullScreenSet"), app);
    if (done) { CFRelease(done); return; }
    CFPreferencesSetAppValue(CFSTR("DisplayFullScreen"), kCFBooleanTrue, app);
    CFPreferencesSetAppValue(CFSTR("KMRPFullScreenSet"), kCFBooleanTrue, app);
    const Boolean saved = CFPreferencesAppSynchronize(app);
    fprintf(stderr, "[kmrp-loader] fullscreen made the default in Aspyr's launcher: %s\n", saved ? "saved" : "not saved");
}

__attribute__((constructor)) static void KmrpAppStoreLoader(void) {
    char path[4096];
    uint32_t size = sizeof path;
    if (_NSGetExecutablePath(path, &size) != 0) return;
    const char* name = strrchr(path, '/');
    name = name ? name + 1 : path;
    if (strcmp(name, "AppBundleExe") == 0) { FullscreenOnce(); return; }
    if (strcmp(name, "KOTOR_Exe") != 0) return;
    const char* patcher = getenv("KMRP_PATCHER");
    if (!patcher) return;
    char hex[65] = "";
    if (!Sha256Of(path, hex) || strcmp(hex, KMRP_APPSTORE_EXE_SHA) != 0) {
        fprintf(stderr, "[kmrp-loader] KOTOR_Exe is %s, not the build KMRP was made for (%s): the game runs without KMRP\n",
                hex[0] ? hex : "unreadable", KMRP_APPSTORE_EXE_SHA);
        return;
    }
    void* handle = dlopen(patcher, RTLD_NOW | RTLD_GLOBAL);
    fprintf(stderr, "[kmrp-loader] KOTOR_Exe pid %d: %s %s\n", getpid(), patcher, handle ? "loaded" : dlerror());
}
