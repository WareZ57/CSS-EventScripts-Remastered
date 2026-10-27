/*
 * es_shim - loader that makes EventScripts 2.1.1.379 (Mattie, 2013) run on today's Counter-Strike: Source.
 *
 * The server loads this plugin instead of mattie_eventscripts.so (see addons/mattie_eventscripts.vdf);
 * it loads EventScripts itself and fixes, from the outside, what breaks on the current engine. The
 * EventScripts core binary has no public source code, so nothing inside it is modified on disk.
 *
 *  1. Stack alignment. libpython2.5 and psyco (shipped with ES, built in 2007) do not keep the stack
 *     aligned on 16 bytes. When Python calls an ES C function that calls back into the current engine
 *     (built assuming an aligned stack, SSE movaps), the server crashed (SIGSEGV). ES exposes its
 *     functions to Python only through Py_InitModule4: this shim sits in the global symbol scope before
 *     ES is loaded, so ES's call to Py_InitModule4 lands here and every ES function of the table is
 *     replaced by a trampoline that realigns the stack before calling it (see make_thunk).
 *  2. Nested return values. Every es.* function returns the global g_pPyReturn but never resets it:
 *     an es.* function called while another one runs made the outer one return an object already
 *     handed to its caller, freed one time too many (Python heap corruption, crash later elsewhere).
 *     The trampolines reset g_pPyReturn after every call.
 *  3. Paths. ES builds paths with formats such as "%s/%s/es_%s_db.txt"; without a sub-folder this gives
 *     "cfg//es_x_db.txt", which the current filesystem refuses. ES's calls to sprintf/snprintf/vsnprintf
 *     are redirected and "//" is collapsed in the result of ES path formats.
 *  4. Command words. The current engine's tokenizer (and the tier1 copy linked into ES) compares a signed
 *     char with ' ': every byte >= 0x80 split words, so UTF-8 accents were mangled ("ajoutés" became
 *     "ajout � �s"). Commands are re-tokenized from their raw text with unsigned bytes.
 *  5. Upper-case folders. The current engine looks folders up in lower case (only the file name is
 *     matched case-insensitively): corelib/interfaces/AuthorizationService was unreachable for it. A
 *     lower-case symbolic link is created next to such folders when the shim loads (see
 *     make_lowercase_links); Python and scripts keep using the original path.
 *  6. Unloading. ES is unloaded (dlclose) together with this shim, as when the engine loaded it directly.
 *
 * Build (32-bit, see src/es_shim/build.sh in the GitHub repository):
 *   gcc -m32 -O2 -Wall -Werror -shared -fPIC -fvisibility=hidden -mstackrealign -o es_shim.so es_shim.c -ldl
 * -mstackrealign is required: these functions can be called with a misaligned stack.
 * -DES_SHIM_EFENCE builds a diagnostic version (see the "electric fence" section below).
 */
#define _GNU_SOURCE
#include <ctype.h>
#include <dlfcn.h>
#include <elf.h>
#include <ftw.h>
#include <link.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

#define EXPORT __attribute__((visibility("default")))

typedef struct {
    const char *ml_name;
    void *ml_meth;
    int ml_flags;
    const char *ml_doc;
} PyMethodDef;

typedef void *(*InitModule4Fn)(const char *, PyMethodDef *, const char *, void *, int);
typedef void *(*CreateInterfaceFn)(const char *, int *);

static void *es_handle;
static void *es_base;               /* load address of mattie_eventscripts.so */
static CreateInterfaceFn es_create;
static InitModule4Fn real_init_module4;

/* Trampolines: one executable block, filled as needed (197 functions in ES 379) */
#define THUNK_SIZE 48
#define THUNK_MAX 2048
static unsigned char *thunks;
static int thunk_count;

/*
 * Every es.* function does: g_pPyReturn = NULL; run the ES command; return g_pPyReturn (without
 * Py_INCREF, the command created the object) or None. It never resets g_pPyReturn afterwards: if an
 * es.* function calls another one (es.load of an addon whose load() calls es.entitygetvalue), the outer
 * function returns the inner result, already given to its caller, and Python frees it one time too many.
 * The trampoline therefore resets g_pPyReturn after every call.
 */
static void **g_return_slot;
static void *dummy_return_slot;

static void shim_log(const char *msg)
{
    fprintf(stderr, "[es_shim] %s\n", msg);
}

/*
 * push ebp ; mov ebp, esp ; and esp, -16
 * push [ebp+20] ; push [ebp+16] ; push [ebp+12] ; push [ebp+8]   (4 arguments copied: 16 bytes,
 * mov eax, target ; call eax                                       the stack stays aligned at the call)
 * mov dword [g_pPyReturn], 0
 * leave ; ret
 * Python C functions (PyCFunction) are cdecl and take at most 3 arguments; reading a fourth stack
 * word is harmless. The return value (eax) is preserved.
 */
static void *make_thunk(void *target)
{
    static const unsigned char tpl[] = {
        0x55, 0x89, 0xE5, 0x83, 0xE4, 0xF0,
        0xFF, 0x75, 0x14, 0xFF, 0x75, 0x10, 0xFF, 0x75, 0x0C, 0xFF, 0x75, 0x08,
        0xB8, 0, 0, 0, 0, 0xFF, 0xD0,
        0xC7, 0x05, 0, 0, 0, 0, 0, 0, 0, 0,
        0xC9, 0xC3,
    };
    if (!g_return_slot) {
        g_return_slot = (void **)dlsym(es_handle, "g_pPyReturn");
        if (!g_return_slot) {
            shim_log("g_pPyReturn not found: nested return values are not fixed");
            g_return_slot = &dummy_return_slot;
        }
    }
    if (!thunks) {
        thunks = mmap(NULL, THUNK_SIZE * THUNK_MAX, PROT_READ | PROT_WRITE | PROT_EXEC,
                      MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        if (thunks == MAP_FAILED) {
            thunks = NULL;
            shim_log("cannot map the trampolines: functions left unwrapped");
            return target;
        }
    }
    if (thunk_count >= THUNK_MAX)
        return target;
    unsigned char *t = thunks + THUNK_SIZE * thunk_count++;
    memcpy(t, tpl, sizeof(tpl));
    memcpy(t + 19, &target, 4);
    memcpy(t + 27, &g_return_slot, 4);
    return t;
}

static int in_es(void *fn)
{
    Dl_info info;
    return fn && dladdr(fn, &info) && info.dli_fbase == es_base;
}

EXPORT void *Py_InitModule4(const char *name, PyMethodDef *methods, const char *doc, void *self, int apiver)
{
    if (!real_init_module4) {
        void *py = dlopen("libpython2.5.so.1.0", RTLD_NOW | RTLD_NOLOAD);
        if (py)
            real_init_module4 = (InitModule4Fn)dlsym(py, "Py_InitModule4");
        if (!real_init_module4)
            real_init_module4 = (InitModule4Fn)dlsym(RTLD_NEXT, "Py_InitModule4");
        if (!real_init_module4) {
            shim_log("Py_InitModule4 not found in libpython2.5");
            return NULL;
        }
    }
    int wrapped = 0;
    for (PyMethodDef *m = methods; m && m->ml_name; m++) {
        if (in_es(m->ml_meth)) {
            m->ml_meth = make_thunk(m->ml_meth);
            wrapped++;
        }
    }
    if (wrapped) {
        char msg[160];
        snprintf(msg, sizeof(msg), "module %s: %d functions wrapped", name ? name : "?", wrapped);
        shim_log(msg);
    }
    return real_init_module4(name, methods, doc, self, apiver);
}

/* ── "//" in paths ────────────────────────────────────────────────── */

static int is_es_path_format(const char *fmt)
{
    return es_base && fmt && (strstr(fmt, "%s/") || strstr(fmt, "/%s")) && in_es((void *)fmt);
}

/* "a//b" -> "a/b" (except after ':' so URLs are left alone); returns the new length */
static int collapse_slashes(char *s)
{
    char *r = s, *w = s;
    for (; *r; r++) {
        if (*r == '/' && w > s && w[-1] == '/' && !(w - 1 > s && w[-2] == ':'))
            continue;
        *w++ = *r;
    }
    *w = '\0';
    return (int)(w - s);
}

static int es_vsnprintf(char *buf, size_t size, const char *fmt, va_list ap)
{
    int n = vsnprintf(buf, size, fmt, ap);
    if (n >= 0 && (size_t)n < size && is_es_path_format(fmt))
        n = collapse_slashes(buf);
    return n;
}

static int es_snprintf(char *buf, size_t size, const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    int n = es_vsnprintf(buf, size, fmt, ap);
    va_end(ap);
    return n;
}

static int es_sprintf(char *buf, const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    int n = vsprintf(buf, fmt, ap);
    va_end(ap);
    if (n >= 0 && is_es_path_format(fmt))
        n = collapse_slashes(buf);
    return n;
}

#ifdef ES_SHIM_EFENCE
/* ── Diagnostic: "electric fence" on Python objects ───────────────────
 * Only built with -DES_SHIM_EFENCE. The shim is in the global scope before libpython, so libpython
 * calls our PyObject_Malloc/Free/Realloc. After SIGUSR2 is sent to srcds, objects of EF_MIN to EF_MAX
 * bytes each get their own page, made inaccessible and never reused when freed: any access to a freed
 * object (an extra Py_DECREF...) crashes immediately, in the call stack of the culprit. Run srcds under
 * gdb to read that stack. Adjust EF_MIN/EF_MAX to the size class of the corrupted pool. */
#include <signal.h>

#define EF_MIN 57
#define EF_MAX 64
#define EF_REGION (768u << 20)

typedef void *(*MallocFn)(size_t);
typedef void (*FreeFn)(void *);
typedef void *(*ReallocFn)(void *, size_t);
static MallocFn real_pymalloc;
static FreeFn real_pyfree;
static ReallocFn real_pyrealloc;
static char *ef_base, *ef_next;
static volatile sig_atomic_t ef_active;

static void ef_on(int sig)
{
    (void)sig;
    ef_active = 1;
}

static void ef_init(void)
{
    if (real_pymalloc)
        return;
    void *py = dlopen("libpython2.5.so.1.0", RTLD_NOW | RTLD_NOLOAD);
    real_pymalloc = (MallocFn)dlsym(py, "PyObject_Malloc");
    real_pyfree = (FreeFn)dlsym(py, "PyObject_Free");
    real_pyrealloc = (ReallocFn)dlsym(py, "PyObject_Realloc");
    ef_base = mmap(NULL, EF_REGION, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE, -1, 0);
    ef_next = ef_base == MAP_FAILED ? NULL : ef_base;
    signal(SIGUSR2, ef_on);
}

static int ef_owns(void *p)
{
    return ef_next && (char *)p >= ef_base && (char *)p < ef_base + EF_REGION;
}

/* One readable page per object, followed by a guard page; the object sits at the end of its page */
static void *ef_alloc(size_t n)
{
    if (ef_next + 8192 > ef_base + EF_REGION || mprotect(ef_next, 4096, PROT_READ | PROT_WRITE) != 0)
        return real_pymalloc(n);
    *(size_t *)ef_next = n;
    char *p = ef_next + 4096 - ((n + 7) & ~(size_t)7);
    ef_next += 8192;
    return p;
}

EXPORT void *PyObject_Malloc(size_t n)
{
    ef_init();
    if (ef_active && n >= EF_MIN && n <= EF_MAX)
        return ef_alloc(n);
    return real_pymalloc(n);
}

EXPORT void PyObject_Free(void *p)
{
    ef_init();
    if (ef_owns(p)) {
        char *page = (char *)((uintptr_t)p & ~(uintptr_t)4095);
        mprotect(page, 4096, PROT_NONE);
        return;
    }
    real_pyfree(p);
}

EXPORT void *PyObject_Realloc(void *p, size_t n)
{
    ef_init();
    if (ef_owns(p)) {
        size_t old = *(size_t *)((uintptr_t)p & ~(uintptr_t)4095);
        void *q = PyObject_Malloc(n);
        if (q)
            memcpy(q, p, old < n ? old : n);
        PyObject_Free(p);
        return q;
    }
    return real_pyrealloc(p, n);
}
#endif

/* ── Command tokenizer ────────────────────────────────────────────── */

/*
 * CCommand::Tokenize of the current engine (and the copy linked into ES) compares a signed char with
 * ' ': every byte >= 0x80 ends a word, so "ajoutés" (UTF-8) became "ajout" "\xC3" "\xA9s" and es_tell
 * printed "ajout � �s". The raw text (ArgS) is intact: commands are re-tokenized here with the same
 * algorithm (quotes, break characters {}()':, // comments) on unsigned bytes.
 */
#define COMMAND_MAX_ARGC 64
#define COMMAND_MAX_LENGTH 512

typedef struct {
    int argc;
    int argv0_size;
    char args_buffer[COMMAND_MAX_LENGTH];
    char argv_buffer[COMMAND_MAX_LENGTH];
    const char *argv[COMMAND_MAX_ARGC];
} CCommand; /* tier1 layout (checked: argv at +0x408 both in the engine and in ES) */

typedef struct {
    char set[256];
} CharacterSet;

static int in_set(const CharacterSet *set, unsigned char c)
{
    return set->set[c] != 0;
}

static int is_space(unsigned char c)
{
    return c == ' ' || (c >= '\t' && c <= '\r');
}

/* Same as CUtlBuffer::ParseToken (with // comments); -1 at the end of the text */
static int parse_token(const char *buf, int len, int *pos, const CharacterSet *brk, char *out, int max)
{
    out[0] = 0;
    for (;;) {
        while (*pos < len && is_space((unsigned char)buf[*pos]))
            (*pos)++;
        if (*pos + 1 < len && buf[*pos] == '/' && buf[*pos + 1] == '/') {
            while (*pos < len && buf[*pos] != '\n')
                (*pos)++;
            continue;
        }
        break;
    }
    if (*pos >= len) {
        (*pos)++;
        return -1;
    }
    unsigned char c = (unsigned char)buf[(*pos)++];
    if (c == 0)
        return -1;
    int n = 0;
    if (c == '"') {
        while (*pos < len) {
            c = (unsigned char)buf[(*pos)++];
            if (c == '"' || c == 0)
                break;
            out[n] = (char)c;
            if (++n == max) {
                out[n - 1] = 0;
                return max;
            }
        }
        out[n] = 0;
        return n;
    }
    if (in_set(brk, c)) {
        out[0] = (char)c;
        out[1] = 0;
        return 1;
    }
    for (;;) {
        out[n] = (char)c;
        if (++n == max) {
            out[n - 1] = 0;
            return max;
        }
        if (*pos >= len)
            break;
        c = (unsigned char)buf[(*pos)++];
        if (in_set(brk, c) || c == '"' || c <= ' ') {
            (*pos)--;
            break;
        }
    }
    out[n] = 0;
    return n;
}

/* Replaces CCommand::Tokenize(const char*, characterset_t*) (thiscall = cdecl with this first) */
static int fixed_tokenize(CCommand *cmd, const char *text, const CharacterSet *brk)
{
    static CharacterSet default_breaks;
    if (!default_breaks.set['{'])
        for (const char *b = "{}()':"; *b; b++)
            default_breaks.set[(unsigned char)*b] = 1;

    cmd->argc = 0;
    cmd->argv0_size = 0;
    cmd->args_buffer[0] = 0;
    cmd->argv_buffer[0] = 0;
    if (!text)
        return 0;
    if (!brk)
        brk = &default_breaks;
    int len = (int)strlen(text);
    if (len >= COMMAND_MAX_LENGTH - 1)
        return 0;
    memcpy(cmd->args_buffer, text, len + 1);

    int pos = 0, used = 0;
    while (pos <= len && cmd->argc < COMMAND_MAX_ARGC) {
        char *out = &cmd->argv_buffer[used];
        int max = COMMAND_MAX_LENGTH - used;
        int start = pos;
        int size = parse_token(cmd->args_buffer, len, &pos, brk, out, max);
        if (size < 0)
            break;
        if (size == max) {
            cmd->argc = 0;
            cmd->argv0_size = 0;
            cmd->args_buffer[0] = 0;
            cmd->argv_buffer[0] = 0;
            return 0;
        }
        if (cmd->argc == 1) {
            /* Start of ArgS, as in tier1 (handles a quoted first word) */
            cmd->argv0_size = pos;
            int end_quote = cmd->args_buffer[cmd->argv0_size - 1] == '"';
            if (end_quote)
                cmd->argv0_size--;
            cmd->argv0_size -= size;
            if (cmd->argv0_size > start && cmd->args_buffer[cmd->argv0_size - 1] == '"')
                cmd->argv0_size--;
        }
        cmd->argv[cmd->argc++] = out;
        used += size + 1;
    }
    return 1;
}

/* Command received from the engine: re-tokenized from its raw text before it reaches ES */
static const CCommand *retokenize(const CCommand *in, CCommand *fixed)
{
    return fixed_tokenize(fixed, in->args_buffer, NULL) ? fixed : in;
}

typedef void (*DispatchFn)(void *, const CCommand *);
typedef int (*ClientCommandFn)(void *, void *, const CCommand *);
static DispatchFn orig_dispatch;
static ClientCommandFn orig_client_command;

static void hook_dispatch(void *self, const CCommand *cmd)
{
    CCommand fixed;
    orig_dispatch(self, retokenize(cmd, &fixed));
}

static int hook_client_command(void *self, void *edict, const CCommand *cmd)
{
    CCommand fixed;
    return orig_client_command(self, edict, retokenize(cmd, &fixed));
}

/* ── Redirecting ES relocations ───────────────────────────────────── */

/* Current protection of a page (read from /proc/self/maps), restored after writing */
static int page_prot(uintptr_t addr)
{
    FILE *f = fopen("/proc/self/maps", "r");
    int prot = PROT_READ | PROT_EXEC;
    if (!f)
        return prot;
    unsigned long lo, hi;
    char perms[8];
    while (fscanf(f, "%lx-%lx %7s %*[^\n]", &lo, &hi, perms) == 3) {
        if (addr >= lo && addr < hi) {
            prot = (perms[0] == 'r' ? PROT_READ : 0) | (perms[1] == 'w' ? PROT_WRITE : 0)
                 | (perms[2] == 'x' ? PROT_EXEC : 0);
            break;
        }
    }
    fclose(f);
    return prot;
}

static int write_word(int32_t *loc, int32_t delta)
{
    long page = sysconf(_SC_PAGESIZE);
    uintptr_t pg = (uintptr_t)loc & ~(uintptr_t)(page - 1);
    size_t span = ((uintptr_t)loc + 4 > pg + page) ? page * 2 : page;
    int prot = page_prot(pg);
    if (mprotect((void *)pg, span, PROT_READ | PROT_WRITE | PROT_EXEC) != 0)
        return 0;
    *loc += delta;
    mprotect((void *)pg, span, prot);
    return 1;
}

/*
 * ES is built without PIC: every call (R_386_PC32) and every vtable pointer (R_386_32) to a symbol is
 * written into its image at load time. They are rewritten to our functions (the target changes, the
 * implicit addend follows); the rest of the process is untouched.
 */
static void patch_es_relocs(void)
{
    struct {
        const char *name;
        void *fn;
        void **orig;
        int count;
    } hooks[] = {
        { "sprintf", (void *)es_sprintf, NULL, 0 },
        { "snprintf", (void *)es_snprintf, NULL, 0 },
        { "vsnprintf", (void *)es_vsnprintf, NULL, 0 },
        { "_ZN8CCommand8TokenizeEPKcP14characterset_t", (void *)fixed_tokenize, NULL, 0 },
        { "_ZN10ConCommand8DispatchERK8CCommand", (void *)hook_dispatch, (void **)&orig_dispatch, 0 },
        { "_ZN19CEventScriptsPlugin13ClientCommandEP7edict_tRK8CCommand",
          (void *)hook_client_command, (void **)&orig_client_command, 0 },
    };
    const size_t nhooks = sizeof(hooks) / sizeof(hooks[0]);

    struct link_map *lm;
    if (dlinfo(es_handle, RTLD_DI_LINKMAP, &lm) != 0) {
        shim_log("dlinfo failed: relocations not redirected");
        return;
    }
    Elf32_Rel *rel = NULL;
    Elf32_Sym *symtab = NULL;
    const char *strtab = NULL;
    size_t relsz = 0;
    for (Elf32_Dyn *d = (Elf32_Dyn *)lm->l_ld; d->d_tag != DT_NULL; d++) {
        if (d->d_tag == DT_REL) rel = (Elf32_Rel *)d->d_un.d_ptr;
        else if (d->d_tag == DT_RELSZ) relsz = d->d_un.d_val;
        else if (d->d_tag == DT_SYMTAB) symtab = (Elf32_Sym *)d->d_un.d_ptr;
        else if (d->d_tag == DT_STRTAB) strtab = (const char *)d->d_un.d_ptr;
    }
    if (!rel || !symtab || !strtab)
        return;

    /* Address each symbol was resolved to by the dynamic linker (global scope, then ES) */
    void *resolved[sizeof(hooks) / sizeof(hooks[0])];
    for (size_t h = 0; h < nhooks; h++) {
        resolved[h] = dlsym(RTLD_DEFAULT, hooks[h].name);
        if (!resolved[h])
            resolved[h] = dlsym(es_handle, hooks[h].name);
        if (hooks[h].orig)
            *hooks[h].orig = resolved[h];
    }

    for (size_t i = 0; i < relsz / sizeof(Elf32_Rel); i++) {
        int type = ELF32_R_TYPE(rel[i].r_info);
        if (type != R_386_PC32 && type != R_386_32)
            continue;
        const char *name = strtab + symtab[ELF32_R_SYM(rel[i].r_info)].st_name;
        for (size_t h = 0; h < nhooks; h++) {
            if (!resolved[h] || strcmp(name, hooks[h].name) != 0)
                continue;
            int32_t *loc = (int32_t *)(lm->l_addr + rel[i].r_offset);
            if (write_word(loc, (int32_t)((intptr_t)hooks[h].fn - (intptr_t)resolved[h])))
                hooks[h].count++;
            break;
        }
    }

    char msg[200];
    snprintf(msg, sizeof(msg), "relocations redirected: printf %d, Tokenize %d, Dispatch %d, ClientCommand %d",
             hooks[0].count + hooks[1].count + hooks[2].count, hooks[3].count, hooks[4].count, hooks[5].count);
    shim_log(msg);
}

/* ── Lower-case folder links ──────────────────────────────────────── */

static int lowercase_links_made;

static int lowercase_entry(const char *path, const struct stat *st, int type, struct FTW *ftw)
{
    (void)st;
    if (type != FTW_D || ftw->level == 0)
        return 0;
    const char *base = path + ftw->base;
    int upper = 0;
    for (const char *c = base; *c; c++)
        if (isupper((unsigned char)*c))
            upper = 1;
    if (!upper)
        return 0;
    char lower[4096];
    size_t len = (size_t)snprintf(lower, sizeof(lower), "%.*s", ftw->base, path);
    for (const char *c = base; *c && len < sizeof(lower) - 1; c++)
        lower[len++] = (char)tolower((unsigned char)*c);
    lower[len] = '\0';
    struct stat existing;
    if (lstat(lower, &existing) != 0 && symlink(base, lower) == 0)
        lowercase_links_made++;
    return 0;
}

/* game: the mod folder (cstrike). Links are created under addons/eventscripts and cfg. */
static void make_lowercase_links(const char *game)
{
    static const char *roots[] = { "addons/eventscripts", "cfg" };
    char root[4096 + 64];
    for (size_t i = 0; i < sizeof(roots) / sizeof(roots[0]); i++) {
        snprintf(root, sizeof(root), "%s/%s", game, roots[i]);
        nftw(root, lowercase_entry, 32, FTW_PHYS);
    }
    if (lowercase_links_made) {
        char msg[96];
        snprintf(msg, sizeof(msg), "%d lower-case folder links created", lowercase_links_made);
        shim_log(msg);
    }
}

/* ── Loading ──────────────────────────────────────────────────────── */

static int load_es(void)
{
    if (es_create)
        return 1;

    /* This shim must be in the global scope before ES to intercept Py_InitModule4. The reference taken
     * here is released at once (the promotion stays): the engine must be able to unload the shim, which
     * then unloads ES (see shim_fini). */
    Dl_info self;
    void *self_handle;
    if (!dladdr((void *)load_es, &self)
        || !(self_handle = dlopen(self.dli_fname, RTLD_NOW | RTLD_GLOBAL | RTLD_NOLOAD))) {
        shim_log("cannot promote the shim to the global scope");
        return 0;
    }
    dlclose(self_handle);

    /* <game>/addons/es_shim.so */
    char addons[2048], game[2048], path[4096];
    snprintf(addons, sizeof(addons), "%s", self.dli_fname);
    char *slash = strrchr(addons, '/');
    if (slash)
        *slash = '\0';
    else
        snprintf(addons, sizeof(addons), "addons");
    snprintf(game, sizeof(game), "%s", addons);
    slash = strrchr(game, '/');
    if (slash)
        *slash = '\0';
    else
        snprintf(game, sizeof(game), ".");
    make_lowercase_links(game);

    snprintf(path, sizeof(path), "%s/mattie_eventscripts.so", addons);
    es_handle = dlopen(path, RTLD_NOW);
    if (!es_handle) {
        fprintf(stderr, "[es_shim] cannot load %s: %s\n", path, dlerror());
        return 0;
    }
    es_create = (CreateInterfaceFn)dlsym(es_handle, "CreateInterface");
    Dl_info es_info;
    if (!es_create || !dladdr((void *)es_create, &es_info)) {
        shim_log("CreateInterface not found in mattie_eventscripts.so");
        es_create = NULL;
        return 0;
    }
    es_base = es_info.dli_fbase;
    patch_es_relocs();
    return 1;
}

/*
 * The engine unloads the shim (plugin_unload, quit): ES is unloaded with it, as when the engine loaded
 * it directly, so its static destructors (ConVar/ConCommand) run while the engine is still alive.
 */
__attribute__((destructor)) static void shim_fini(void)
{
    if (es_handle) {
        dlclose(es_handle);
        es_handle = NULL;
        es_create = NULL;
        es_base = NULL;
    }
}

EXPORT void *CreateInterface(const char *name, int *rc)
{
    if (!load_es()) {
        if (rc)
            *rc = 1; /* IFACE_FAILED */
        return NULL;
    }
    return es_create(name, rc);
}
