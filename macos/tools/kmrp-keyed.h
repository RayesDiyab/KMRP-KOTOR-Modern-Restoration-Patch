/* One resource through chitin.key, for the tools that read the game's files directly. Only
 * its own bytes are read from the BIF: models.bif is 950 MB. The three tools had a copy each
 * until 2026-11-01, one with fewer checks (audit S-8, GUI-7).
 *
 * Each includes this after its own Buffer, u16 and u32, with KMRP_KEYED_LIMIT defined as the
 * largest resource it will take; it also uses kmrp_fopen and strcasecmp, and fseeko, which
 * MSVC calls _fseeki64. The sums of file values are 64-bit: the module is 32-bit. */
static Buffer keyed_resource(const Buffer *key, const char *key_path, const char *resref, int type) {
    Buffer none = { NULL, 0 };
    if (!key->data || key->size < 24 || memcmp(key->data, "KEY V1  ", 8) != 0) return none;
    uint32_t bif_count = u32(key->data + 8), key_count = u32(key->data + 12);
    uint32_t file_table = u32(key->data + 16), key_table = u32(key->data + 20);
    for (uint32_t i = 0; i < key_count; i++) {
        uint64_t at = (uint64_t)key_table + (uint64_t)i * 22;
        if (at + 22 > key->size) break;
        char name[17] = { 0 };
        memcpy(name, key->data + at, 16);
        if (strcasecmp(name, resref) != 0 || u16(key->data + at + 16) != type) continue;
        uint32_t id = u32(key->data + at + 18), bif_index = id >> 20, index = id & 0xFFFFF;
        uint64_t entry = (uint64_t)file_table + (uint64_t)bif_index * 12;
        if (bif_index >= bif_count || entry + 12 > key->size) return none;
        uint32_t name_offset = u32(key->data + entry + 4);
        uint16_t name_length = u16(key->data + entry + 8);
        char bif_path[4096], relative[512] = { 0 };
        if (name_length >= sizeof relative || (uint64_t)name_offset + name_length > key->size) return none;
        memcpy(relative, key->data + name_offset, name_length);
        for (char *p = relative; *p; p++) if (*p == '\\') *p = '/';
        /* Either separator: on Windows the module passes C:\...\chitin.key, and with '/' alone
           the BIF was looked for in the current folder, which is the game's only when the game
           itself runs this. The installer's prebuild of every size runs elsewhere, so
           tutorial.2da was never read and nothing was made (2026-10-23). */
        const char *slash = strrchr(key_path, '/');
        const char *other = strrchr(key_path, '\\');
        if (other && (!slash || other > slash)) slash = other;
        int dir_length = slash ? (int)(slash - key_path) : 1;
        snprintf(bif_path, sizeof bif_path, "%.*s/%s", dir_length, slash ? key_path : ".", relative);
        FILE *f = kmrp_fopen(bif_path, "rb");
        if (!f) return none;
        uint8_t head[20], record[16];
        Buffer out = none;
        if (fread(head, 1, 20, f) == 20 && memcmp(head, "BIFFV1  ", 8) == 0 && index < u32(head + 8) &&
            fseeko(f, (long long)u32(head + 16) + (long long)index * 16, SEEK_SET) == 0 &&
            fread(record, 1, 16, f) == 16 && (u32(record) & 0xFFFFF) == index) {
            uint32_t offset = u32(record + 4), size = u32(record + 8);
            if (size > 0 && size < KMRP_KEYED_LIMIT && fseeko(f, offset, SEEK_SET) == 0 && (out.data = malloc(size))) {
                if (fread(out.data, 1, size, f) == size) out.size = size;
                else { free(out.data); out.data = NULL; }
            }
        }
        fclose(f);
        return out;
    }
    return none;
}
