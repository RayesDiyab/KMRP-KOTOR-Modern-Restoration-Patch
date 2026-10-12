/*
  KMRP for macOS, the Mac App Store's game: the app that starts the game with KMRP.

  KMRP's installer makes an app of its own beside the game in /Applications, and this is its
  executable:

      /Applications/KOTOR with KMRP.app/Contents/MacOS/KOTOR with KMRP     this file
                                        Contents/Resources/kmrp/loader.dylib
                                                                KotorPatcher.dylib
                                                                patch_config.toml
                                                                patches/, configs/
                                                                game-path.txt

  The game itself is left as Apple signed it: started from Launchpad or its own icon it is the
  game without KMRP. This starts Aspyr's launcher (AppBundleExe) in the game's own folder with
  loader.dylib inserted (loader.c). The game is sandboxed and reads /Applications, which is why
  KMRP's files are in an app there and not in the player's Library (measured 2026-10-12; the
  player's home outside the game's container is closed to it).

  The game's output goes to ~/Library/Logs/KMRP/appstore-game.log, opened here: the sandboxed
  game could not open it, but writes to what it is handed. KMRP_KEEP_OUTPUT=1 leaves the output
  where it is (a run from a terminal). A DYLD_INSERT_LIBRARIES already set is kept after
  KMRP's.
*/
#include <fcntl.h>
#include <limits.h>
#include <mach-o/dyld.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static const char kDefaultGame[] = "/Applications/Knights of the Old Republic.app";

static void Alert(const char* text) {
    fprintf(stderr, "KMRP: %s\n", text);
    char script[2048];
    snprintf(script, sizeof script, "display alert \"KOTOR with KMRP\" message \"%s\"", text);
    execl("/usr/bin/osascript", "osascript", "-e", script, (char*)NULL);
    _exit(1);
}

int main(void) {
    char self[PATH_MAX], real[PATH_MAX];
    uint32_t size = sizeof self;
    if (_NSGetExecutablePath(self, &size) != 0 || !realpath(self, real)) Alert("could not find its own files.");
    char* slash = strrchr(real, '/');          // .../Contents/MacOS/<name>
    if (slash) *slash = 0;
    slash = strrchr(real, '/');                // .../Contents/MacOS
    if (!slash) Alert("could not find its own files.");
    *slash = 0;
    char kmrp[PATH_MAX];
    snprintf(kmrp, sizeof kmrp, "%s/Resources/kmrp", real);

    char game[PATH_MAX];
    snprintf(game, sizeof game, "%s", kDefaultGame);
    char file[PATH_MAX + 32];
    snprintf(file, sizeof file, "%s/game-path.txt", kmrp);
    FILE* f = fopen(file, "r");
    if (f) {
        char line[PATH_MAX];
        if (fgets(line, sizeof line, f)) {
            line[strcspn(line, "\r\n")] = 0;
            if (line[0] == '/') snprintf(game, sizeof game, "%s", line);
        }
        fclose(f);
    }
    char folder[PATH_MAX + 32], launcher[PATH_MAX + 64];
    snprintf(folder, sizeof folder, "%s/Contents/MacOS", game);
    snprintf(launcher, sizeof launcher, "%s/AppBundleExe", folder);
    if (access(launcher, X_OK) != 0)
        Alert("Knights of the Old Republic from the Mac App Store was not found in Applications. Install the game, then install KMRP again.");

    char loader[PATH_MAX + 32], patcher[PATH_MAX + 32];
    snprintf(loader, sizeof loader, "%s/loader.dylib", kmrp);
    snprintf(patcher, sizeof patcher, "%s/KotorPatcher.dylib", kmrp);
    if (access(loader, R_OK) != 0 || access(patcher, R_OK) != 0) Alert("its files are missing. Install KMRP again.");

    const char* inserted = getenv("DYLD_INSERT_LIBRARIES");
    char insert[4 * PATH_MAX];
    if (inserted && inserted[0]) snprintf(insert, sizeof insert, "%s:%s", loader, inserted);
    else snprintf(insert, sizeof insert, "%s", loader);
    setenv("DYLD_INSERT_LIBRARIES", insert, 1);
    setenv("KMRP_PATCHER", patcher, 1);

    const char* keep = getenv("KMRP_KEEP_OUTPUT");
    const char* home = getenv("HOME");
    if (!(keep && keep[0] == '1') && home) {
        char logs[PATH_MAX];
        snprintf(logs, sizeof logs, "%s/Library/Logs/KMRP", home);
        mkdir(logs, 0755);
        strlcat(logs, "/appstore-game.log", sizeof logs);
        const int fd = open(logs, O_WRONLY | O_CREAT | O_TRUNC, 0644);
        if (fd >= 0) {
            dup2(fd, STDOUT_FILENO);
            dup2(fd, STDERR_FILENO);
            if (fd > STDERR_FILENO) close(fd);
        }
    }
    if (chdir(folder) != 0) Alert("could not open the game's folder.");
    execl(launcher, launcher, (char*)NULL);
    Alert("could not start the game.");
    return 1;
}
