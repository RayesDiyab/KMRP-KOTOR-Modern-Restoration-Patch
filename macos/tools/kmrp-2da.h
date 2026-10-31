/* kmrp-2da.h: KOTOR 2DA tables, read, written and merged three ways, for any table.
 *
 * Header only (every function static), so each tool that needs it is still one file:
 * kmrp-gameart.c builds KMRP's tables with it, kmrp-merge.c merges a mod's with them.
 * Nothing here knows any table's name; what KMRP changes in a table is the caller's,
 * given as KMRP's whole table ("ours"), made from vanilla's.
 *
 * The two formats the game reads (both tags are in swkotor.exe, 2026-10-31):
 *
 *   binary "2DA V2.b\n"  column names, each ended by a tab, then a NUL; a u32 row count;
 *                        the row labels, each ended by a tab; rows x columns u16 offsets
 *                        into the cell data, row by row; a u16 data size; the data,
 *                        NUL-ended strings, each value once
 *   text   "2DA V2.0"    a line, then a line that may be "DEFAULT: value", then the
 *                        column names, then one line a row: its label and its cells,
 *                        separated by blanks; "****" is an empty cell, and a cell with
 *                        blanks in it is in double quotes
 *
 * The three-way merge (kmrp_2da_merge), every rule decided from the tables, never from a
 * table's name:
 *
 *   columns  by name, without regard to case, wherever they stand; one a table names
 *            twice is ambiguous, and not merged
 *   rows     by an identity chosen from vanilla's table: the first column whose every
 *            row has a value and no two the same ("label" first where it is such a
 *            column), else the row labels when they are names (not 0, 1, 2 ...) and
 *            unique, else the row number. A key the mod's table repeats or leaves empty
 *            is ambiguous: those rows are left as the mod has them. Matched by number,
 *            a row is the same row only where at least half of its shared cells are
 *            still vanilla's, so a row the mod put in between is never taken for the
 *            one it pushed down
 *   cells    vanilla b, KMRP o, the mod t:  o == b: the mod's;  t == b: KMRP's;
 *            t == o: that;  else the mod's, and a conflict noted
 *   order    the mod's table is the output: its rows, their order and numbers (the game
 *            and its scripts find a row by its number), its labels, its columns, its
 *            format and DEFAULT. KMRP only changes cells inside rows. A row or column
 *            KMRP adds (none today) goes after the mod's last, never in between
 *
 * A note is written for every conflict, every KMRP change that could not be made (the
 * mod removed the row or column, or its row is ambiguous) and every vanilla row the
 * mod's table has at another number. */
#ifndef KMRP_2DA_H
#define KMRP_2DA_H

#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
/* Every function static, and quiet where a tool uses only some of them. */
#if defined(__GNUC__) || defined(__clang__)
#define KMRP_2DA_STATIC static __attribute__((unused))
#else
#define KMRP_2DA_STATIC static
#endif
#ifdef _WIN32
#define kmrp_2da_casecmp _stricmp
#else
#include <strings.h>
#define kmrp_2da_casecmp strcasecmp
#endif

typedef struct {
    int text;              /* 1: "2DA V2.0", 0: "2DA V2.b" */
    char *default_value;   /* text only: its "DEFAULT:" value, or NULL */
    int columns, rows;
    char **headers, **labels, **cells;   /* cells: rows x columns, row by row */
} Kmrp2da;

typedef struct { uint8_t *data; size_t size; } Kmrp2daBytes;

/* What a merge noted, one line each, and how many of each kind. */
typedef struct { char *text; size_t length, capacity; int conflicts, lost, moved, applied; } Kmrp2daNotes;

enum { KMRP_2DA_MAX_ROWS = 1 << 20, KMRP_2DA_MAX_COLUMNS = 4096 };

KMRP_2DA_STATIC void kmrp_2da_note(Kmrp2daNotes *n, const char *format, ...) {
    if (!n) return;
    char line[600];
    va_list args;
    va_start(args, format);
    int length = vsnprintf(line, sizeof line, format, args);
    va_end(args);
    if (length < 0) return;
    if (length >= (int)sizeof line) length = (int)sizeof line - 1;
    if (n->length + (size_t)length + 2 > n->capacity) {
        size_t capacity = (n->capacity + (size_t)length + 2) * 2;
        char *grown = (char *)realloc(n->text, capacity);
        if (!grown) return;
        n->text = grown; n->capacity = capacity;
    }
    memcpy(n->text + n->length, line, (size_t)length);
    n->length += (size_t)length;
    n->text[n->length++] = '\n';
    n->text[n->length] = 0;
}

KMRP_2DA_STATIC char *kmrp_2da_dup(const char *s, size_t n) {
    char *d = (char *)malloc(n + 1);
    if (!d) return NULL;
    memcpy(d, s, n); d[n] = 0;
    return d;
}

KMRP_2DA_STATIC void kmrp_2da_free(Kmrp2da *t) {
    if (!t) return;
    for (int c = 0; c < t->columns; c++) free(t->headers ? t->headers[c] : NULL);
    for (int r = 0; r < t->rows; r++) free(t->labels ? t->labels[r] : NULL);
    if (t->cells) for (long i = 0; i < (long)t->rows * t->columns; i++) free(t->cells[i]);
    free(t->headers); free(t->labels); free(t->cells); free(t->default_value);
    memset(t, 0, sizeof *t);
}

KMRP_2DA_STATIC uint32_t kmrp_2da_u32(const uint8_t *p) { return p[0] | p[1] << 8 | p[2] << 16 | (uint32_t)p[3] << 24; }
KMRP_2DA_STATIC unsigned kmrp_2da_u16(const uint8_t *p) { return (unsigned)(p[0] | p[1] << 8); }

KMRP_2DA_STATIC int kmrp_2da_parse_binary(const uint8_t *d, size_t size, Kmrp2da *t) {
    size_t at = 9, start = 9;
    while (at < size && d[at] != 0) {
        if (d[at] == '\t') {
            if (t->columns >= KMRP_2DA_MAX_COLUMNS) return 0;
            char **grown = (char **)realloc(t->headers, sizeof(char *) * (t->columns + 1));
            if (!grown) return 0;
            t->headers = grown;
            if (!(t->headers[t->columns] = kmrp_2da_dup((const char *)d + start, at - start))) return 0;
            t->columns++;
            start = at + 1;
        }
        at++;
    }
    if (at >= size || start != at || !t->columns) return 0;   /* every name ends in a tab */
    at++;
    if (at + 4 > size) return 0;
    uint32_t rows = kmrp_2da_u32(d + at);
    at += 4;
    if (rows > KMRP_2DA_MAX_ROWS || (uint64_t)rows * t->columns * 2 > size) return 0;
    t->labels = (char **)calloc(rows ? rows : 1, sizeof(char *));
    t->cells = (char **)calloc((size_t)rows * t->columns + 1, sizeof(char *));
    if (!t->labels || !t->cells) return 0;
    for (uint32_t r = 0; r < rows; r++) {
        start = at;
        while (at < size && d[at] != '\t') at++;
        if (at >= size) { t->rows = (int)r; return 0; }
        t->labels[r] = kmrp_2da_dup((const char *)d + start, at - start);
        at++;
    }
    t->rows = (int)rows;
    size_t offsets = at, data = offsets + (size_t)rows * t->columns * 2;
    if (data + 2 > size) return 0;
    size_t data_size = kmrp_2da_u16(d + data);
    data += 2;
    if (data + data_size > size) return 0;
    for (size_t i = 0; i < (size_t)rows * t->columns; i++) {
        size_t cell = kmrp_2da_u16(d + offsets + i * 2), end = data + cell;
        if (cell >= data_size && data_size) return 0;
        while (end < data + data_size && d[end] != 0) end++;
        if (data_size && end >= data + data_size) return 0;
        if (!(t->cells[i] = kmrp_2da_dup((const char *)d + data + cell, data_size ? end - data - cell : 0))) return 0;
    }
    return 1;
}

/* One blank-separated token of a text line: in quotes it may hold blanks. */
KMRP_2DA_STATIC const char *kmrp_2da_token(const char *p, const char *end, char **out) {
    while (p < end && (*p == ' ' || *p == '\t')) p++;
    if (p >= end) { *out = NULL; return p; }
    const char *start = p;
    if (*p == '"') {
        start = ++p;
        while (p < end && *p != '"') p++;
        *out = kmrp_2da_dup(start, (size_t)(p - start));
        return p < end ? p + 1 : p;
    }
    while (p < end && *p != ' ' && *p != '\t') p++;
    *out = kmrp_2da_dup(start, (size_t)(p - start));
    if (*out && strcmp(*out, "****") == 0) (*out)[0] = 0;
    return p;
}

KMRP_2DA_STATIC int kmrp_2da_parse_text(const uint8_t *d, size_t size, Kmrp2da *t) {
    const char *p = (const char *)d, *end = p + size;
    int line = 0, have_headers = 0;
    t->text = 1;
    while (p < end) {
        const char *eol = (const char *)memchr(p, '\n', (size_t)(end - p));
        const char *stop = eol ? eol : end;
        const char *last = stop;
        while (last > p && (last[-1] == '\r' || last[-1] == ' ' || last[-1] == '\t')) last--;
        const char *first = p;
        while (first < last && (*first == ' ' || *first == '\t')) first++;
        if (line == 0) {
            if (last - p < 8 || memcmp(p, "2DA V2.0", 8) != 0) return 0;
        } else if (line == 1 && last - first >= 8 && strncmp(first, "DEFAULT:", 8) == 0) {
            const char *v = first + 8;
            while (v < last && (*v == ' ' || *v == '\t')) v++;
            t->default_value = kmrp_2da_dup(v, (size_t)(last - v));
        } else if (first < last && !have_headers) {
            have_headers = 1;
            for (const char *q = first; q < last;) {
                char *name;
                q = kmrp_2da_token(q, last, &name);
                if (!name) break;
                if (t->columns >= KMRP_2DA_MAX_COLUMNS) { free(name); return 0; }
                char **grown = (char **)realloc(t->headers, sizeof(char *) * (t->columns + 1));
                if (!grown) { free(name); return 0; }
                t->headers = grown;
                t->headers[t->columns++] = name;
            }
            if (!t->columns) return 0;
        } else if (first < last) {
            if (t->rows >= KMRP_2DA_MAX_ROWS) return 0;
            char **labels = (char **)realloc(t->labels, sizeof(char *) * (t->rows + 1));
            if (!labels) return 0;
            t->labels = labels;
            char **cells = (char **)realloc(t->cells, sizeof(char *) * ((size_t)(t->rows + 1) * t->columns + 1));
            if (!cells) return 0;
            t->cells = cells;
            const char *q = kmrp_2da_token(first, last, &t->labels[t->rows]);
            for (int c = 0; c < t->columns; c++) {
                char *cell = NULL;
                q = kmrp_2da_token(q, last, &cell);
                t->cells[(size_t)t->rows * t->columns + c] = cell ? cell : kmrp_2da_dup("", 0);
            }
            t->rows++;
            char *extra = NULL;
            kmrp_2da_token(q, last, &extra);
            if (extra) { free(extra); return 0; }   /* more cells than columns: not a table */
        }
        line++;
        p = eol ? eol + 1 : end;
    }
    return have_headers;
}

/* 1 when DATA is a 2DA in either format. On failure T is empty. */
KMRP_2DA_STATIC int kmrp_2da_parse(const uint8_t *data, size_t size, Kmrp2da *t) {
    memset(t, 0, sizeof *t);
    int ok = 0;
    if (data && size >= 9 && memcmp(data, "2DA V2.b\n", 9) == 0) ok = kmrp_2da_parse_binary(data, size, t);
    else if (data && size >= 8 && memcmp(data, "2DA V2.0", 8) == 0) ok = kmrp_2da_parse_text(data, size, t);
    if (!ok) kmrp_2da_free(t);
    return ok;
}

KMRP_2DA_STATIC int kmrp_2da_put(Kmrp2daBytes *b, const void *p, size_t n) {
    uint8_t *grown = (uint8_t *)realloc(b->data, b->size + n + 1);
    if (!grown) return 0;
    b->data = grown;
    memcpy(b->data + b->size, p, n);
    b->size += n;
    return 1;
}
KMRP_2DA_STATIC void kmrp_2da_put_text(Kmrp2daBytes *b, const char *s) { kmrp_2da_put(b, s, strlen(s)); }
KMRP_2DA_STATIC void kmrp_2da_put_u16(Kmrp2daBytes *b, unsigned v) { uint8_t x[2] = { (uint8_t)(v & 0xff), (uint8_t)((v >> 8) & 0xff) }; kmrp_2da_put(b, x, 2); }
KMRP_2DA_STATIC void kmrp_2da_put_u32(Kmrp2daBytes *b, uint32_t v) {
    uint8_t x[4] = { (uint8_t)(v & 0xff), (uint8_t)((v >> 8) & 0xff), (uint8_t)((v >> 16) & 0xff), (uint8_t)(v >> 24) };
    kmrp_2da_put(b, x, 4);
}

/* Binary 2DA as pykotor's TwoDABinaryWriter writes it (GameArtGenerator.Write2da): each
 * distinct value stored once, in the order first used. Empty when the data would not fit
 * the format's 16-bit offsets. */
KMRP_2DA_STATIC Kmrp2daBytes kmrp_2da_write_binary(const Kmrp2da *t) {
    Kmrp2daBytes b = { NULL, 0 };
    kmrp_2da_put_text(&b, "2DA V2.b\n");
    for (int c = 0; c < t->columns; c++) { kmrp_2da_put_text(&b, t->headers[c]); kmrp_2da_put_text(&b, "\t"); }
    kmrp_2da_put(&b, "", 1);
    kmrp_2da_put_u32(&b, (uint32_t)t->rows);
    for (int r = 0; r < t->rows; r++) { kmrp_2da_put_text(&b, t->labels[r]); kmrp_2da_put_text(&b, "\t"); }
    size_t cells = (size_t)t->rows * t->columns, values = 0;
    const char **value = (const char **)malloc(sizeof(char *) * (cells + 1));
    unsigned long *value_offset = (unsigned long *)malloc(sizeof(unsigned long) * (cells + 1)), data_size = 0;
    for (size_t i = 0; value && value_offset && i < cells; i++) {
        size_t found = values;
        for (size_t v = 0; v < values; v++) if (strcmp(value[v], t->cells[i]) == 0) { found = v; break; }
        if (found == values) {
            value[values] = t->cells[i];
            value_offset[values] = data_size;
            data_size += (unsigned long)strlen(t->cells[i]) + 1;
            values++;
        }
        kmrp_2da_put_u16(&b, (unsigned)value_offset[found]);
    }
    if (!value || !value_offset || data_size > 0xFFFF) { free(b.data); b.data = NULL; b.size = 0; }
    else {
        kmrp_2da_put_u16(&b, (unsigned)data_size);
        for (size_t v = 0; v < values; v++) kmrp_2da_put(&b, value[v], strlen(value[v]) + 1);
    }
    free((void *)value); free(value_offset);
    return b;
}

KMRP_2DA_STATIC void kmrp_2da_put_cell(Kmrp2daBytes *b, const char *s) {
    if (!*s) { kmrp_2da_put_text(b, "****"); return; }
    if (strpbrk(s, " \t")) { kmrp_2da_put_text(b, "\""); kmrp_2da_put_text(b, s); kmrp_2da_put_text(b, "\""); return; }
    kmrp_2da_put_text(b, s);
}

/* Text 2DA: tab-separated, its DEFAULT kept. Its spacing is not the mod's, its content is. */
KMRP_2DA_STATIC Kmrp2daBytes kmrp_2da_write_text(const Kmrp2da *t) {
    Kmrp2daBytes b = { NULL, 0 };
    kmrp_2da_put_text(&b, "2DA V2.0\r\n");
    if (t->default_value) { kmrp_2da_put_text(&b, "DEFAULT: "); kmrp_2da_put_cell(&b, t->default_value); }
    kmrp_2da_put_text(&b, "\r\n");
    for (int c = 0; c < t->columns; c++) { kmrp_2da_put_text(&b, "\t"); kmrp_2da_put_cell(&b, t->headers[c]); }
    kmrp_2da_put_text(&b, "\r\n");
    for (int r = 0; r < t->rows; r++) {
        kmrp_2da_put_cell(&b, t->labels[r]);
        for (int c = 0; c < t->columns; c++) {
            kmrp_2da_put_text(&b, "\t");
            kmrp_2da_put_cell(&b, t->cells[(size_t)r * t->columns + c]);
        }
        kmrp_2da_put_text(&b, "\r\n");
    }
    return b;
}

/* The table in its own format. */
KMRP_2DA_STATIC Kmrp2daBytes kmrp_2da_write(const Kmrp2da *t) { return t->text ? kmrp_2da_write_text(t) : kmrp_2da_write_binary(t); }

KMRP_2DA_STATIC const char *kmrp_2da_cell(const Kmrp2da *t, int row, int column) {
    return row >= 0 && column >= 0 && row < t->rows && column < t->columns ? t->cells[(size_t)row * t->columns + column] : NULL;
}

/* The column of this name, -1 when there is none, -2 when the table has two. */
KMRP_2DA_STATIC int kmrp_2da_column(const Kmrp2da *t, const char *name) {
    int found = -1;
    for (int c = 0; c < t->columns; c++)
        if (kmrp_2da_casecmp(t->headers[c], name) == 0) { if (found >= 0) return -2; found = c; }
    return found;
}

/* ------------------------------------------------------------------ row identity */

enum { KMRP_2DA_BY_COLUMN, KMRP_2DA_BY_LABEL, KMRP_2DA_BY_NUMBER };
typedef struct { int kind; char column[256]; } Kmrp2daIdentity;

/* A row's key, or NULL (BY_NUMBER has none: the row number is its key). */
KMRP_2DA_STATIC const char *kmrp_2da_key(const Kmrp2da *t, const Kmrp2daIdentity *id, int row) {
    if (id->kind == KMRP_2DA_BY_LABEL) return t->labels[row];
    if (id->kind == KMRP_2DA_BY_COLUMN) return kmrp_2da_cell(t, row, kmrp_2da_column(t, id->column));
    return NULL;
}

KMRP_2DA_STATIC int kmrp_2da_unique(const Kmrp2da *t, int column, int labels) {
    for (int r = 0; r < t->rows; r++) {
        const char *a = labels ? t->labels[r] : kmrp_2da_cell(t, r, column);
        if (!a || !*a) return 0;
        for (int q = 0; q < r; q++) {
            const char *b = labels ? t->labels[q] : kmrp_2da_cell(t, q, column);
            if (kmrp_2da_casecmp(a, b) == 0) return 0;
        }
    }
    return 1;
}

KMRP_2DA_STATIC int kmrp_2da_labels_are_numbers(const Kmrp2da *t) {
    for (int r = 0; r < t->rows; r++) {
        char want[16];
        snprintf(want, sizeof want, "%d", r);
        if (strcmp(t->labels[r], want) != 0) return 0;
    }
    return 1;
}

/* How rows are told apart, chosen from vanilla's table alone. */
KMRP_2DA_STATIC Kmrp2daIdentity kmrp_2da_identity(const Kmrp2da *base) {
    Kmrp2daIdentity id = { KMRP_2DA_BY_NUMBER, "" };
    int preferred = kmrp_2da_column(base, "label");
    if (base->rows > 0 && preferred >= 0 && kmrp_2da_unique(base, preferred, 0)) {
        id.kind = KMRP_2DA_BY_COLUMN;
        snprintf(id.column, sizeof id.column, "%s", base->headers[preferred]);
        return id;
    }
    for (int c = 0; base->rows > 1 && c < base->columns; c++) {
        if (kmrp_2da_column(base, base->headers[c]) != c || !kmrp_2da_unique(base, c, 0)) continue;
        id.kind = KMRP_2DA_BY_COLUMN;
        snprintf(id.column, sizeof id.column, "%s", base->headers[c]);
        return id;
    }
    if (base->rows > 0 && !kmrp_2da_labels_are_numbers(base) && kmrp_2da_unique(base, 0, 1)) id.kind = KMRP_2DA_BY_LABEL;
    return id;
}

/* The row of T with this identity, -1 when there is none, -2 when it is ambiguous. */
KMRP_2DA_STATIC int kmrp_2da_find(const Kmrp2da *t, const Kmrp2daIdentity *id, const char *key, int number) {
    if (id->kind == KMRP_2DA_BY_NUMBER) return number < t->rows ? number : -1;
    if (!key || !*key) return -1;
    if (id->kind == KMRP_2DA_BY_COLUMN && kmrp_2da_column(t, id->column) < 0) return -2;
    int found = -1;
    for (int r = 0; r < t->rows; r++) {
        const char *k = kmrp_2da_key(t, id, r);
        if (k && kmrp_2da_casecmp(k, key) == 0) { if (found >= 0) return -2; found = r; }
    }
    return found;
}

/* Matched by number only: is the mod's row still vanilla's, in at least half its cells? */
KMRP_2DA_STATIC int kmrp_2da_same_row(const Kmrp2da *base, int b, const Kmrp2da *theirs, int t) {
    int shared = 0, same = 0;
    for (int c = 0; c < base->columns; c++) {
        int tc = kmrp_2da_column(theirs, base->headers[c]);
        if (tc < 0) continue;
        shared++;
        if (strcmp(kmrp_2da_cell(base, b, c), kmrp_2da_cell(theirs, t, tc)) == 0) same++;
    }
    return shared > 0 && same * 2 >= shared;
}

KMRP_2DA_STATIC int kmrp_2da_set(Kmrp2da *t, int row, int column, const char *value) {
    char *copy = kmrp_2da_dup(value, strlen(value));
    if (!copy) return 0;
    free(t->cells[(size_t)row * t->columns + column]);
    t->cells[(size_t)row * t->columns + column] = copy;
    return 1;
}

KMRP_2DA_STATIC int kmrp_2da_copy(const Kmrp2da *from, Kmrp2da *to) {
    memset(to, 0, sizeof *to);
    to->text = from->text;
    to->columns = from->columns;
    to->rows = from->rows;
    to->default_value = from->default_value ? kmrp_2da_dup(from->default_value, strlen(from->default_value)) : NULL;
    to->headers = (char **)calloc(from->columns ? from->columns : 1, sizeof(char *));
    to->labels = (char **)calloc(from->rows ? from->rows : 1, sizeof(char *));
    to->cells = (char **)calloc((size_t)from->rows * from->columns + 1, sizeof(char *));
    if (!to->headers || !to->labels || !to->cells) return 0;
    for (int c = 0; c < from->columns; c++) if (!(to->headers[c] = kmrp_2da_dup(from->headers[c], strlen(from->headers[c])))) return 0;
    for (int r = 0; r < from->rows; r++) if (!(to->labels[r] = kmrp_2da_dup(from->labels[r], strlen(from->labels[r])))) return 0;
    for (size_t i = 0; i < (size_t)from->rows * from->columns; i++)
        if (!(to->cells[i] = kmrp_2da_dup(from->cells[i], strlen(from->cells[i])))) return 0;
    return 1;
}

/* A column after the table's last, empty in every row. */
KMRP_2DA_STATIC int kmrp_2da_add_column(Kmrp2da *t, const char *name) {
    char **headers = (char **)realloc(t->headers, sizeof(char *) * (t->columns + 1));
    if (!headers) return -1;
    t->headers = headers;
    char **cells = (char **)calloc((size_t)t->rows * (t->columns + 1) + 1, sizeof(char *));
    if (!cells) return -1;
    for (int r = 0; r < t->rows; r++) {
        for (int c = 0; c < t->columns; c++) cells[(size_t)r * (t->columns + 1) + c] = t->cells[(size_t)r * t->columns + c];
        cells[(size_t)r * (t->columns + 1) + t->columns] = kmrp_2da_dup("", 0);
    }
    free(t->cells);
    t->cells = cells;
    t->headers[t->columns] = kmrp_2da_dup(name, strlen(name));
    return t->columns++;
}

/* A row after the table's last, numbered as the next. */
KMRP_2DA_STATIC int kmrp_2da_add_row(Kmrp2da *t) {
    char **labels = (char **)realloc(t->labels, sizeof(char *) * (t->rows + 1));
    if (!labels) return -1;
    t->labels = labels;
    char **cells = (char **)realloc(t->cells, sizeof(char *) * ((size_t)(t->rows + 1) * t->columns + 1));
    if (!cells) return -1;
    t->cells = cells;
    char number[16];
    snprintf(number, sizeof number, "%d", t->rows);
    t->labels[t->rows] = kmrp_2da_dup(number, strlen(number));
    for (int c = 0; c < t->columns; c++) t->cells[(size_t)t->rows * t->columns + c] = kmrp_2da_dup("", 0);
    return t->rows++;
}

enum { KMRP_2DA_MERGED = 0, KMRP_2DA_UNREADABLE = 1, KMRP_2DA_UNSAFE = 2 };

/* OUT: the mod's table with KMRP's changes merged in, three ways against vanilla. NAME only
 * labels the notes. KMRP_2DA_MERGED, else nothing is written to OUT and the mod's table
 * should be used as it is (KMRP_2DA_UNSAFE: the notes say why). */
KMRP_2DA_STATIC int kmrp_2da_merge(const char *name, const Kmrp2da *base, const Kmrp2da *ours, const Kmrp2da *theirs,
                          Kmrp2da *out, Kmrp2daNotes *notes) {
    Kmrp2daNotes unseen = { NULL, 0, 0, 0, 0, 0, 0 };
    if (!notes) notes = &unseen;
    memset(out, 0, sizeof *out);
    for (int c = 0; c < theirs->columns; c++)
        if (kmrp_2da_column(theirs, theirs->headers[c]) != c)
            kmrp_2da_note(notes, "%s: the column %s is there twice; KMRP leaves it as the mod has it", name, theirs->headers[c]);
    const Kmrp2daIdentity id = kmrp_2da_identity(base);
    if (id.kind == KMRP_2DA_BY_COLUMN && kmrp_2da_column(theirs, id.column) < 0) {
        kmrp_2da_note(notes, "%s: the mod's table has no %s column, which names its rows; not merged", name, id.column);
        return KMRP_2DA_UNSAFE;
    }
    if (!kmrp_2da_copy(theirs, out)) { kmrp_2da_free(out); return KMRP_2DA_UNREADABLE; }
    for (int o = 0; o < ours->rows; o++) {
        const char *key = kmrp_2da_key(ours, &id, o);
        const int b = kmrp_2da_find(base, &id, key, o);
        int t = b == -1 ? -1 : kmrp_2da_find(theirs, &id, key, o);
        const char *what = key ? key : ours->labels[o];
        if (b == -2) { kmrp_2da_note(notes, "%s: KMRP's row %s is not one vanilla row; not applied", name, what); notes->lost++; continue; }
        /* Does KMRP change this row at all? */
        int changed = b < 0;
        for (int c = 0; !changed && c < ours->columns; c++) {
            const int bc = kmrp_2da_column(base, ours->headers[c]);
            changed = bc < 0 ? *kmrp_2da_cell(ours, o, c) != 0 : strcmp(kmrp_2da_cell(ours, o, c), kmrp_2da_cell(base, b, bc)) != 0;
        }
        if (!changed) continue;
        if (b < 0) {
            /* A row KMRP adds: after the mod's last, unless the mod has one of that key. */
            if (id.kind == KMRP_2DA_BY_NUMBER || kmrp_2da_find(out, &id, key, o) != -1) {
                kmrp_2da_note(notes, "%s: KMRP's new row %s is in the mod's table already, or cannot be told apart; not added", name, what);
                notes->lost++;
                continue;
            }
            t = kmrp_2da_add_row(out);
            if (t < 0) { kmrp_2da_free(out); return KMRP_2DA_UNREADABLE; }
            kmrp_2da_note(notes, "%s: KMRP's row %s added as row %d", name, what, t);
        } else if (t == -2) {
            kmrp_2da_note(notes, "%s: the mod's table has more than one row %s; KMRP's change to it is not applied", name, what);
            notes->lost++;
            continue;
        } else if (t < 0) {
            kmrp_2da_note(notes, "%s: the mod's table has no row %s; KMRP's change to it is lost", name, what);
            notes->lost++;
            continue;
        } else if (id.kind == KMRP_2DA_BY_NUMBER && !kmrp_2da_same_row(base, b, theirs, t)) {
            kmrp_2da_note(notes, "%s: the mod's row %d is not vanilla's row %d any more; KMRP's change to it is not applied", name, t, b);
            notes->lost++;
            continue;
        } else if (t != b) {
            kmrp_2da_note(notes, "%s: vanilla's row %s (row %d) is row %d in the mod's table; scripts asking for row %d get the mod's row there",
                          name, what, b, t, b);
            notes->moved++;
        }
        for (int c = 0; c < ours->columns; c++) {
            const char *o_value = kmrp_2da_cell(ours, o, c);
            const int bc = b < 0 ? -1 : kmrp_2da_column(base, ours->headers[c]);
            const char *b_value = bc >= 0 ? kmrp_2da_cell(base, b, bc) : "";
            if (strcmp(o_value, b_value) == 0) continue;            /* not KMRP's change */
            int tc = kmrp_2da_column(out, ours->headers[c]);
            if (tc == -2) {
                kmrp_2da_note(notes, "%s: row %s, column %s: the mod's table has the column twice; KMRP's %s not applied", name, what, ours->headers[c], o_value);
                notes->lost++;
                continue;
            }
            if (tc < 0) {
                if (bc >= 0) {
                    kmrp_2da_note(notes, "%s: the mod's table has no column %s; KMRP's change to row %s is lost", name, ours->headers[c], what);
                    notes->lost++;
                    continue;
                }
                if ((tc = kmrp_2da_add_column(out, ours->headers[c])) < 0) { kmrp_2da_free(out); return KMRP_2DA_UNREADABLE; }
                kmrp_2da_note(notes, "%s: KMRP's column %s added after the mod's last", name, ours->headers[c]);
            }
            const char *t_value = kmrp_2da_cell(out, t, tc);
            if (strcmp(t_value, b_value) == 0 || (b < 0 && !*t_value)) {
                if (!kmrp_2da_set(out, t, tc, o_value)) { kmrp_2da_free(out); return KMRP_2DA_UNREADABLE; }
                notes->applied++;
            } else if (strcmp(t_value, o_value) != 0) {
                kmrp_2da_note(notes, "%s: row %s, column %s: the mod's \"%s\" kept (vanilla \"%s\", KMRP \"%s\")",
                              name, what, ours->headers[c], t_value, b_value, o_value);
                notes->conflicts++;
            }
        }
    }
    /* Never a row moved or renumbered: the mod's rows are where they were, KMRP's after. */
    for (int r = 0; r < theirs->rows; r++)
        if (strcmp(out->labels[r], theirs->labels[r]) != 0) { kmrp_2da_free(out); return KMRP_2DA_UNSAFE; }
    return KMRP_2DA_MERGED;
}

#endif
