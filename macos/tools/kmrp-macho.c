/*
 * kmrp-macho: adds, removes or reports one LC_LOAD_DYLIB in the game executable.
 *
 *   kmrp-macho has-dylib    <exe> <name>   exit 0 if linked (matched by file name), 1 if not
 *   kmrp-macho add-dylib    <exe> <path>   add LC_LOAD_DYLIB <path>, e.g. @executable_path/KotorPatcher.dylib
 *   kmrp-macho remove-dylib <exe> <name>   remove it again
 *   kmrp-macho info         <exe>          load command count and free load command space
 *
 * The same edit KotOR Patch Manager makes on macOS (KPatchCore MachODependencies): the
 * command goes into the space the linker already left after the load commands, so nothing
 * in the image moves and no address changes. Only thin x86_64 images are accepted -- the
 * Aspyr KOTOR_Exe is one, and KotorPatcher only exists for x86_64. The file is rewritten
 * through a temporary copy and renamed over the original, so a failed write never leaves a
 * half-edited game. The caller re-signs afterwards (codesign --force --sign -): the edit
 * invalidates the existing signature, as it does for KPM.
 */
#include <errno.h>
#include <fcntl.h>
#include <mach-o/loader.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static void die(const char *msg) {
    fprintf(stderr, "kmrp-macho: %s\n", msg);
    exit(2);
}

static uint8_t *read_file(const char *path, size_t *size) {
    FILE *f = fopen(path, "rb");
    if (!f) { perror(path); exit(2); }
    if (fseek(f, 0, SEEK_END) != 0) die("cannot seek");
    long n = ftell(f);
    if (n <= 0) die("empty or unreadable file");
    rewind(f);
    uint8_t *buf = malloc((size_t)n);
    if (!buf || fread(buf, 1, (size_t)n, f) != (size_t)n) die("cannot read file");
    fclose(f);
    *size = (size_t)n;
    return buf;
}

static void write_file(const char *path, const uint8_t *buf, size_t size) {
    struct stat st;
    if (stat(path, &st) != 0) { perror(path); exit(2); }
    char tmp[4096];
    if (snprintf(tmp, sizeof tmp, "%s.kmrp-tmp", path) >= (int)sizeof tmp) die("path too long");
    int fd = open(tmp, O_WRONLY | O_CREAT | O_TRUNC, st.st_mode & 07777);
    if (fd < 0) { perror(tmp); exit(2); }
    size_t done = 0;
    while (done < size) {
        ssize_t w = write(fd, buf + done, size - done);
        if (w < 0) { if (errno == EINTR) continue; perror(tmp); unlink(tmp); exit(2); }
        done += (size_t)w;
    }
    if (fsync(fd) != 0 || close(fd) != 0) { perror(tmp); unlink(tmp); exit(2); }
    if (rename(tmp, path) != 0) { perror(path); unlink(tmp); exit(2); }
}

/* The image header, checked: thin, 64-bit, x86_64, load commands inside the file. */
static struct mach_header_64 *header_of(uint8_t *buf, size_t size) {
    if (size < sizeof(struct mach_header_64)) die("not a Mach-O file");
    struct mach_header_64 *h = (struct mach_header_64 *)buf;
    if (h->magic != MH_MAGIC_64) die("not a thin 64-bit Mach-O (universal files are not supported)");
    if (h->cputype != CPU_TYPE_X86_64) die("not an x86_64 image");
    if (sizeof(*h) + (size_t)h->sizeofcmds > size) die("load commands run past the end of the file");
    return h;
}

/* Bytes free between the end of the load commands and the first section's contents. */
static size_t free_space(struct mach_header_64 *h, size_t size) {
    uint8_t *p = (uint8_t *)(h + 1);
    uint64_t first = size;
    for (uint32_t i = 0; i < h->ncmds; i++) {
        struct load_command *lc = (struct load_command *)p;
        if (lc->cmd == LC_SEGMENT_64) {
            struct segment_command_64 *seg = (struct segment_command_64 *)p;
            struct section_64 *sect = (struct section_64 *)(seg + 1);
            for (uint32_t s = 0; s < seg->nsects; s++) {
                uint32_t type = sect[s].flags & SECTION_TYPE;
                if (sect[s].offset != 0 && type != S_ZEROFILL && type != S_GB_ZEROFILL &&
                    type != S_THREAD_LOCAL_ZEROFILL && sect[s].offset < first) {
                    first = sect[s].offset;
                }
            }
        }
        p += lc->cmdsize;
    }
    uint64_t used = sizeof(*h) + h->sizeofcmds;
    return first > used ? (size_t)(first - used) : 0;
}

static const char *base_name(const char *path) {
    const char *slash = strrchr(path, '/');
    return slash ? slash + 1 : path;
}

/* Offset of the LC_LOAD_DYLIB whose file name matches, or 0. */
static size_t find_dylib(struct mach_header_64 *h, const char *name) {
    uint8_t *start = (uint8_t *)h;
    uint8_t *p = (uint8_t *)(h + 1);
    const char *want = base_name(name);
    for (uint32_t i = 0; i < h->ncmds; i++) {
        struct load_command *lc = (struct load_command *)p;
        if (lc->cmdsize < sizeof(struct load_command)) die("malformed load command");
        if (lc->cmd == LC_LOAD_DYLIB || lc->cmd == LC_LOAD_WEAK_DYLIB) {
            struct dylib_command *dc = (struct dylib_command *)p;
            if (dc->dylib.name.offset < lc->cmdsize) {
                const char *have = (const char *)p + dc->dylib.name.offset;
                size_t room = lc->cmdsize - dc->dylib.name.offset;
                if (strnlen(have, room) < room && strcmp(base_name(have), want) == 0) {
                    return (size_t)(p - start);
                }
            }
        }
        p += lc->cmdsize;
    }
    return 0;
}

int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "usage: kmrp-macho has-dylib|add-dylib|remove-dylib <exe> <name> | info <exe>\n");
        return 2;
    }
    const char *verb = argv[1], *exe = argv[2];
    size_t size;
    uint8_t *buf = read_file(exe, &size);
    struct mach_header_64 *h = header_of(buf, size);

    if (strcmp(verb, "info") == 0) {
        printf("ncmds=%u sizeofcmds=%u free=%zu\n", h->ncmds, h->sizeofcmds, free_space(h, size));
        return 0;
    }
    if (argc < 4) die("missing library name");
    const char *name = argv[3];

    if (strcmp(verb, "has-dylib") == 0) {
        return find_dylib(h, name) ? 0 : 1;
    }

    if (strcmp(verb, "add-dylib") == 0) {
        if (find_dylib(h, name)) {
            printf("already linked: %s\n", name);
            return 0;
        }
        size_t len = strlen(name) + 1;
        size_t cmdsize = (sizeof(struct dylib_command) + len + 7) & ~(size_t)7;
        size_t room = free_space(h, size);
        if (cmdsize > room) {
            fprintf(stderr, "kmrp-macho: %zu bytes of load command space left, %zu needed\n", room, cmdsize);
            return 2;
        }
        uint8_t *at = (uint8_t *)(h + 1) + h->sizeofcmds;
        for (size_t i = 0; i < cmdsize; i++) {
            if (at[i] != 0) die("load command space is not empty");
        }
        struct dylib_command *dc = (struct dylib_command *)at;
        dc->cmd = LC_LOAD_DYLIB;
        dc->cmdsize = (uint32_t)cmdsize;
        dc->dylib.name.offset = sizeof(struct dylib_command);
        dc->dylib.timestamp = 2;
        dc->dylib.current_version = 0x10000;
        dc->dylib.compatibility_version = 0x10000;
        memcpy(at + sizeof(struct dylib_command), name, len);
        h->ncmds += 1;
        h->sizeofcmds += (uint32_t)cmdsize;
        write_file(exe, buf, size);
        printf("added LC_LOAD_DYLIB %s\n", name);
        return 0;
    }

    if (strcmp(verb, "remove-dylib") == 0) {
        size_t off = find_dylib(h, name);
        if (!off) {
            printf("not linked: %s\n", name);
            return 0;
        }
        uint8_t *cmd = buf + off;
        uint32_t cmdsize = ((struct load_command *)cmd)->cmdsize;
        uint8_t *end = (uint8_t *)(h + 1) + h->sizeofcmds;
        memmove(cmd, cmd + cmdsize, (size_t)(end - (cmd + cmdsize)));
        memset(end - cmdsize, 0, cmdsize);
        h->ncmds -= 1;
        h->sizeofcmds -= cmdsize;
        write_file(exe, buf, size);
        printf("removed LC_LOAD_DYLIB %s\n", name);
        return 0;
    }

    die("unknown command");
    return 2;
}
