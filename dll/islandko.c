/* ISLAND (CatSystem2) Korean patch loader - version.dll proxy.
 * The build decides the data branch, not the store:
 *   Japanese build : engine 2.6.1.68, no language.txt (Steam's Japanese depot 857454)
 *   English build  : engine 2.6.1.80, exe strings from language.txt (GOG, and Steam's English
 *                    depot 857451 = the same exe wrapped in SteamStub)
 *   SteamStub (.bind section) only says the copy came from Steam; it is logged, nothing more.
 *
 * Loaded by ISLAND.exe from the game folder (it imports VERSION.dll). Never touches the exe file
 * or the Steam DRM: everything happens through the exe's import table after Windows resolved it.
 *
 *  language=ko  (island-ko.ini)
 *    - CreateFile/LoadLibrary of scene.int fes.int config.int image.int movie.int cs2conf.dll
 *      config\startup.xml language.txt are served from <game>\ko\ when present there
 *      (originals stay untouched)
 *    - ko\ISLAND-KO.ttf registered privately for this process (nothing installed)
 *    - MessageBoxA / SetWindowTextA shown as Unicode, Japanese system messages in Korean (Japanese
 *      build); the English build takes its exe strings from ko\language.txt, whose "#949" line
 *      sets their code page
 *    - list view text the exe (English build: also its cs2conf.dll plugin) sends as ANSI
 *      (SendMessageA / SendDlgItemMessageA LVM_*A) goes out as the W message in that code page
 *      (the GOG system information list showed Latin-1)
 *    - startup.xml strings (donor-kanji bytes: key names, voice names) put into list/combo boxes
 *      and labels go out as W text with the donor table applied, also inside cs2conf.dll (Japanese
 *      build: ko\cs2conf.dll, English build: the game's own); reading them back as ANSI returns
 *      the original bytes
 *    - exe dialog resources replaced in memory with the Korean set (ko\exe_rsrc.bin, Japanese
 *      build only)
 *  language=ja / en (original game)
 *    - MessageBoxA / SetWindowTextA shown as Unicode (fixes CP932 mojibake on Korean Windows)
 *
 *  Test runs only - ISLANDKO_TEST=1 (environment) or <game>\island-ko-test.ini [TEST] on=1:
 *  the game believes it is the foreground window, never activates itself, stays outside every
 *  monitor, reads the cursor from shared memory, answers message boxes itself (cs2conf.dll's
 *  too) and uses its own single-instance mutex (never meets the player's game).
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <commctrl.h>
#include <stdlib.h>
#include <string.h>
#include <intrin.h>
#pragma intrinsic(_ReturnAddress)

#pragma comment(lib, "kernel32.lib")
#pragma comment(lib, "user32.lib")
#pragma comment(lib, "gdi32.lib")

/* ------------------------------------------------------------------ proxy */
static HMODULE g_real;
#define VERFN(X) X(GetFileVersionInfoA) X(GetFileVersionInfoByHandle) X(GetFileVersionInfoExA) \
    X(GetFileVersionInfoExW) X(GetFileVersionInfoSizeA) X(GetFileVersionInfoSizeExA) \
    X(GetFileVersionInfoSizeExW) X(GetFileVersionInfoSizeW) X(GetFileVersionInfoW) X(VerFindFileA) \
    X(VerFindFileW) X(VerInstallFileA) X(VerInstallFileW) X(VerLanguageNameA) X(VerLanguageNameW) \
    X(VerQueryValueA) X(VerQueryValueW)
#define DECL(n) static FARPROC p_##n;
VERFN(DECL)
#define STUB(n) __declspec(naked) void proxy_##n(void) { __asm { jmp dword ptr [p_##n] } }
VERFN(STUB)

static void load_real(void)
{
    WCHAR path[MAX_PATH];
    UINT n = GetSystemDirectoryW(path, MAX_PATH);
    lstrcpyW(path + n, L"\\version.dll");
    g_real = LoadLibraryW(path);
#define RESOLVE(n) p_##n = g_real ? GetProcAddress(g_real, #n) : NULL;
    VERFN(RESOLVE)
}

/* ------------------------------------------------------------------ state */
static WCHAR g_gamedir[MAX_PATH];   /* with trailing backslash */
static WCHAR g_kodir[MAX_PATH];     /* <game>\ko\ */
static WCHAR g_font[MAX_PATH];
static int g_ko, g_test, g_font_ok, g_rsrc_state;  /* rsrc: 0 todo, 1 done, -1 skipped */
static int g_edition;          /* 1 Japanese build, 2 English build (language.txt / engine 2.6.1.80) */
static int g_steam;            /* exe carries SteamStub (.bind) - logged only */
static DWORD g_exever_ms, g_exever_ls;   /* exe file version from its version resource (0 = none) */
static UINT g_native_cp = 932; /* code page of the exe's own ANSI strings (MessageBoxA etc.) */
static int g_tx = 4160, g_ty = 200;   /* test window position: outside every monitor */
static HANDLE g_log = INVALID_HANDLE_VALUE;
static CRITICAL_SECTION g_cs;
static HWND g_mainwnd;
#define MAP_LO 0x4E00
#define MAP_HI 0xA000
static WCHAR g_map[MAP_HI - MAP_LO];  /* donor kanji -> real char (Hangul etc.) */
static int g_nmap;
static volatile LONG g_redirects, g_mbox, g_fonts_logged;

typedef struct { WCHAR *jp, *ko; } MSG_T;
static MSG_T *g_msgs;
static int g_nmsgs;

typedef struct { volatile LONG x, y, valid; volatile LONG answer; volatile LONG seq; } TEST_SHM;
static TEST_SHM *g_shm;

static void logw(const WCHAR *fmt, ...)
{
    WCHAR buf[2048];
    char out[6144];
    va_list ap;
    int n;
    DWORD w;
    if (g_log == INVALID_HANDLE_VALUE) return;
    va_start(ap, fmt);
    n = wvsprintfW(buf, fmt, ap);
    va_end(ap);
    if (n < 0) return;
    buf[n++] = L'\r'; buf[n++] = L'\n'; buf[n] = 0;
    n = WideCharToMultiByte(CP_UTF8, 0, buf, n, out, sizeof(out), NULL, NULL);
    EnterCriticalSection(&g_cs);
    WriteFile(g_log, out, n, &w, NULL);
    LeaveCriticalSection(&g_cs);
}

/* ------------------------------------------------------------------ files */
static WCHAR *read_file_w(const WCHAR *path, DWORD *len)
{
    HANDLE h = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    DWORD sz, got;
    BYTE *buf;
    if (h == INVALID_HANDLE_VALUE) return NULL;
    sz = GetFileSize(h, NULL);
    buf = (BYTE *)HeapAlloc(GetProcessHeap(), 0, sz + 4);
    if (!buf || !ReadFile(h, buf, sz, &got, NULL) || got != sz) { CloseHandle(h); return NULL; }
    CloseHandle(h);
    buf[sz] = buf[sz + 1] = buf[sz + 2] = buf[sz + 3] = 0;
    *len = sz;
    return (WCHAR *)buf;
}

static int file_exists(const WCHAR *p)
{
    DWORD a = GetFileAttributesW(p);
    return a != INVALID_FILE_ATTRIBUTES && !(a & FILE_ATTRIBUTE_DIRECTORY);
}

/* ini: language=ko | ja / en / original (UTF-8/ASCII) */
static void read_ini(void)
{
    WCHAR path[MAX_PATH], val[16];
    lstrcpyW(path, g_gamedir);
    lstrcatW(path, L"island-ko.ini");
    GetPrivateProfileStringW(L"ISLAND-KO", L"language", L"ko", val, 16, path);
    g_ko = !(lstrcmpiW(val, L"ja") == 0 || lstrcmpiW(val, L"en") == 0 || lstrcmpiW(val, L"original") == 0);
    if (g_ko) {
        WCHAR probe[MAX_PATH];
        lstrcpyW(probe, g_kodir); lstrcatW(probe, L"scene.int");
        if (!file_exists(probe)) g_ko = 0;   /* Korean files missing: behave as the original game */
    }
}

/* exe file version from the main module's own version resource (SteamStub leaves .rsrc alone) */
static void read_exe_version(void)
{
    HRSRC r = FindResourceW(NULL, MAKEINTRESOURCEW(1), MAKEINTRESOURCEW(16) /* RT_VERSION */);
    HGLOBAL g = r ? LoadResource(NULL, r) : NULL;
    BYTE *p = g ? (BYTE *)LockResource(g) : NULL;
    DWORD n = r ? SizeofResource(NULL, r) : 0, i;
    for (i = 0; p && i + sizeof(VS_FIXEDFILEINFO) <= n; i += 4)
        if (*(DWORD *)(p + i) == 0xFEEF04BD) {
            VS_FIXEDFILEINFO *v = (VS_FIXEDFILEINFO *)(p + i);
            g_exever_ms = v->dwFileVersionMS; g_exever_ls = v->dwFileVersionLS;
            return;
        }
}

/* The English build (GOG, Steam English) reads its exe strings from language.txt and is engine
 * 2.6.1.80; the Japanese build has neither. Anything else is treated as the Japanese build.
 * The SteamStub section (.bind) is in both Steam depots, so it says nothing about the data. */
static int detect_edition(void)
{
    BYTE *base = (BYTE *)GetModuleHandleW(NULL);
    IMAGE_NT_HEADERS32 *nt = (IMAGE_NT_HEADERS32 *)(base + ((IMAGE_DOS_HEADER *)base)->e_lfanew);
    IMAGE_SECTION_HEADER *sec = IMAGE_FIRST_SECTION(nt);
    WCHAR p[MAX_PATH];
    int i;
    for (i = 0; i < nt->FileHeader.NumberOfSections; i++)
        if (!memcmp(sec[i].Name, ".bind", 6)) g_steam = 1;
    read_exe_version();
    lstrcpyW(p, g_gamedir); lstrcatW(p, L"language.txt");
    if (file_exists(p)) return 2;
    if (g_exever_ms == MAKELONG(6, 2) && g_exever_ls == MAKELONG(80, 1)) return 2;   /* 2.6.1.80 */
    return 1;
}

/* ko\ is built by the installer for one build (ko\install.txt line "edition steam|gog", internal
 * names: steam = Japanese build, gog = English build). When Steam switches the game language it
 * swaps the game files for the other build, whose archives the Korean files do not fit (another
 * archive key) - then run as the original game until the patch is installed again. */
static int g_ko_mismatch;
static void check_install_build(void)
{
    WCHAR p[MAX_PATH];
    HANDLE h;
    char buf[512];
    DWORD got = 0;
    char *e;
    if (!g_ko) return;
    lstrcpyW(p, g_kodir); lstrcatW(p, L"install.txt");
    h = CreateFileW(p, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    if (h == INVALID_HANDLE_VALUE) return;
    ReadFile(h, buf, sizeof(buf) - 1, &got, NULL);
    CloseHandle(h);
    buf[got] = 0;
    e = strstr(buf, "\nedition ");
    if (!e) return;
    e += 9;
    if ((g_edition == 2) != (strncmp(e, "gog", 3) == 0)) { g_ko = 0; g_ko_mismatch = 1; }
}

/* English build, Korean mode: ko\language.txt may start with "#949" - the engine converts every exe string
 * to that code page before MessageBoxA etc. */
static void read_native_cp(void)
{
    WCHAR p[MAX_PATH];
    HANDLE h;
    char buf[16];
    DWORD got = 0;
    if (g_edition != 2 || !g_ko) return;
    lstrcpyW(p, g_kodir); lstrcatW(p, L"language.txt");
    h = CreateFileW(p, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    if (h == INVALID_HANDLE_VALUE) return;
    ReadFile(h, buf, sizeof(buf) - 1, &got, NULL);
    CloseHandle(h);
    buf[got] = 0;
    if (buf[0] == '#' && buf[1] >= '0' && buf[1] <= '9') {
        UINT cp = (UINT)atoi(buf + 1);
        if (cp && IsValidCodePage(cp)) g_native_cp = cp;
    }
}

/* test runs: environment ISLANDKO_TEST=1, or <game>\island-ko-test.ini [TEST] on=1 x= y= */
static void read_test_flag(void)
{
    WCHAR env[8], v[16], ini[MAX_PATH];
    g_test = GetEnvironmentVariableW(L"ISLANDKO_TEST", env, 8) && env[0] == L'1';
    if (g_test) {
        if (GetEnvironmentVariableW(L"ISLANDKO_TEST_X", v, 16)) g_tx = _wtoi(v);
        if (GetEnvironmentVariableW(L"ISLANDKO_TEST_Y", v, 16)) g_ty = _wtoi(v);
        return;
    }
    lstrcpyW(ini, g_gamedir); lstrcatW(ini, L"island-ko-test.ini");
    if (!file_exists(ini) || GetPrivateProfileIntW(L"TEST", L"on", 0, ini) != 1) return;
    g_test = 1;
    g_tx = GetPrivateProfileIntW(L"TEST", L"x", g_tx, ini);
    g_ty = GetPrivateProfileIntW(L"TEST", L"y", g_ty, ini);
}

/* donor table: ko\pua_table.txt, UTF-16LE lines "8A9E<TAB>X" (donor kanji code point -> char) */
static void load_pua(void)
{
    WCHAR path[MAX_PATH], *t, *p;
    DWORD len;
    lstrcpyW(path, g_kodir); lstrcatW(path, L"pua_table.txt");
    t = read_file_w(path, &len);
    if (!t) return;
    p = t;
    if (*p == 0xFEFF) p++;
    while (*p) {
        unsigned cp = 0;
        while ((*p >= L'0' && *p <= L'9') || (*p >= L'A' && *p <= L'F')) { cp = cp * 16 + (*p <= L'9' ? *p - L'0' : *p - L'A' + 10); p++; }
        if (*p == L'\t' && p[1] && cp >= MAP_LO && cp < MAP_HI) { g_map[cp - MAP_LO] = p[1]; g_nmap++; }
        while (*p && *p != L'\n') p++;
        if (*p) p++;
    }
}

/* message table: ko\msg_ko.txt, UTF-16LE lines "JP<TAB>KO" with \n \r \t escapes */
static void unescape(WCHAR *s)
{
    WCHAR *d = s;
    for (; *s; s++) {
        if (*s == L'\\' && s[1]) {
            s++;
            *d++ = *s == L'n' ? L'\n' : *s == L'r' ? L'\r' : *s == L't' ? L'\t' : *s;
        } else *d++ = *s;
    }
    *d = 0;
}

static void load_msgs(void)
{
    WCHAR path[MAX_PATH], *t, *p;
    DWORD len;
    int cap = 0;
    lstrcpyW(path, g_kodir); lstrcatW(path, L"msg_ko.txt");
    t = read_file_w(path, &len);
    if (!t) return;
    p = t;
    if (*p == 0xFEFF) p++;
    for (WCHAR *q = p; *q; q++) if (*q == L'\n') cap++;
    g_msgs = (MSG_T *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, (cap + 2) * sizeof(MSG_T));
    if (!g_msgs) return;
    while (*p) {
        WCHAR *line = p, *tab;
        while (*p && *p != L'\n') p++;
        if (*p) { *p = 0; p++; }
        if (p - line > 1 && p[-2] == L'\r') p[-2] = 0;
        tab = line;
        while (*tab && *tab != L'\t') tab++;
        if (!*tab || tab == line) continue;
        *tab = 0;
        unescape(line); unescape(tab + 1);
        g_msgs[g_nmsgs].jp = line; g_msgs[g_nmsgs].ko = tab + 1; g_nmsgs++;
    }
}

/* printf-style pattern match: %s %d %02d %x %u %c %ld ... match any run */
static int is_spec(const WCHAR *p, int *len)
{
    const WCHAR *q = p + 1;
    if (*p != L'%') return 0;
    if (*q == L'%') { *len = 2; return 0; }
    while (*q == L'-' || *q == L'0' || *q == L'+' || *q == L' ' || *q == L'#') q++;
    while (*q >= L'0' && *q <= L'9') q++;
    if (*q == L'.') { q++; while (*q >= L'0' && *q <= L'9') q++; }
    while (*q == L'l' || *q == L'h' || *q == L'I') q++;
    if (*q && wcschr(L"sdiuxXcfS", *q)) { *len = (int)(q - p) + 1; return 1; }
    return 0;
}

static int match(const WCHAR *pat, const WCHAR *s, const WCHAR **caps, int *caplen, int ncap)
{
    int sl;
    while (*pat) {
        if (is_spec(pat, &sl)) {
            const WCHAR *rest = pat + sl, *t;
            for (t = s; ; t++) {
                if (ncap < 8) { caps[ncap] = s; caplen[ncap] = (int)(t - s); }
                if (match(rest, t, caps, caplen, ncap + 1)) return 1;
                if (!*t) return 0;
            }
        }
        if (*pat == L'%' && pat[1] == L'%') { if (*s != L'%') return 0; pat += 2; s++; continue; }
        if (*pat != *s) return 0;
        pat++; s++;
    }
    return *s == 0;
}

static int translate(const WCHAR *in, WCHAR *out, int outcap)
{
    const WCHAR *caps[8];
    int caplen[8], i;
    for (i = 0; i < g_nmsgs; i++) {
        if (match(g_msgs[i].jp, in, caps, caplen, 0)) {
            const WCHAR *k = g_msgs[i].ko;
            int o = 0, c = 0, sl;
            while (*k && o < outcap - 1) {
                if (is_spec(k, &sl)) {
                    int j;
                    for (j = 0; j < caplen[c] && o < outcap - 1 && c < 8; j++) out[o++] = caps[c][j];
                    c++; k += sl; continue;
                }
                if (k[0] == L'%' && k[1] == L'%') { out[o++] = L'%'; k += 2; continue; }
                out[o++] = *k++;
            }
            out[o] = 0;
            return 1;
        }
    }
    return 0;
}

/* game ANSI text -> UTF-16: CP932 + our donor-kanji codes, or the code page GOG's
 * ko\language.txt selected for its exe strings (#949) */
static void a2w(const char *s, WCHAR *out, int cap)
{
    int n, i;
    out[0] = 0;
    if (!s) return;
    n = MultiByteToWideChar(g_native_cp, 0, s, -1, out, cap);
    if (n <= 0) { out[0] = 0; return; }
    if (g_native_cp != 932) return;
    for (i = 0; out[i]; i++)
        if (out[i] >= MAP_LO && out[i] < MAP_HI && g_map[out[i] - MAP_LO]) out[i] = g_map[out[i] - MAP_LO];
}

/* ------------------------------------------------------------------ redirect */
static const WCHAR *k_files[] = { L"scene.int", L"fes.int", L"config.int", L"image.int", L"movie.int", L"cs2conf.dll", L"config\\startup.xml", L"language.txt", NULL };

static int redirect(const WCHAR *in, WCHAR *out)
{
    WCHAR full[MAX_PATH * 2];
    int gl, i;
    if (!g_ko || !in) return 0;
    if (!GetFullPathNameW(in, MAX_PATH * 2, full, NULL)) return 0;
    for (i = 0; full[i]; i++) if (full[i] == L'/') full[i] = L'\\';
    gl = lstrlenW(g_gamedir);
    if (CompareStringOrdinal(full, gl, g_gamedir, gl, TRUE) != CSTR_EQUAL) return 0;
    for (i = 0; k_files[i]; i++) {
        if (CompareStringOrdinal(full + gl, -1, k_files[i], -1, TRUE) == CSTR_EQUAL) {
            lstrcpyW(out, g_kodir);
            lstrcatW(out, k_files[i]);
            if (file_exists(out)) return 1;
        }
    }
    return 0;
}

static void ensure_rsrc(void);

typedef HANDLE(WINAPI *CreateFileA_t)(LPCSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);
typedef HANDLE(WINAPI *CreateFileW_t)(LPCWSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);
typedef HMODULE(WINAPI *LoadLibraryA_t)(LPCSTR);
typedef HMODULE(WINAPI *LoadLibraryW_t)(LPCWSTR);
typedef HMODULE(WINAPI *LoadLibraryExA_t)(LPCSTR, HANDLE, DWORD);
typedef HMODULE(WINAPI *LoadLibraryExW_t)(LPCWSTR, HANDLE, DWORD);
typedef int(WINAPI *MessageBoxA_t)(HWND, LPCSTR, LPCSTR, UINT);
typedef BOOL(WINAPI *SetWindowTextA_t)(HWND, LPCSTR);
typedef HWND(WINAPI *CreateWindowExA_t)(DWORD, LPCSTR, LPCSTR, DWORD, int, int, int, int, HWND, HMENU, HINSTANCE, LPVOID);
typedef HFONT(WINAPI *CreateFontIndirectA_t)(const LOGFONTA *);
typedef HWND(WINAPI *GetForegroundWindow_t)(void);
typedef BOOL(WINAPI *SetForegroundWindow_t)(HWND);
typedef HWND(WINAPI *SetActiveWindow_t)(HWND);
typedef HWND(WINAPI *SetFocus_t)(HWND);
typedef BOOL(WINAPI *ShowWindow_t)(HWND, int);
typedef BOOL(WINAPI *GetCursorPos_t)(LPPOINT);
typedef BOOL(WINAPI *SetWindowPos_t)(HWND, HWND, int, int, int, int, UINT);
typedef BOOL(WINAPI *MoveWindow_t)(HWND, int, int, int, int, BOOL);
static SetWindowPos_t o_SetWindowPos;
typedef HWND(WINAPI *WindowFromPoint_t)(POINT);
static WindowFromPoint_t o_WindowFromPoint;
typedef BOOL(WINAPI *SetCursorPos_t)(int, int);
static SetCursorPos_t o_SetCursorPos;
static MoveWindow_t o_MoveWindow;
typedef BOOL(WINAPI *AttachThreadInput_t)(DWORD, DWORD, BOOL);
typedef INT_PTR(WINAPI *DialogBoxParamA_t)(HINSTANCE, LPCSTR, HWND, DLGPROC, LPARAM);
typedef HWND(WINAPI *CreateDialogParamA_t)(HINSTANCE, LPCSTR, HWND, DLGPROC, LPARAM);
typedef HMENU(WINAPI *LoadMenuA_t)(HINSTANCE, LPCSTR);

static CreateFileA_t o_CreateFileA;
static CreateFileW_t o_CreateFileW;
static LoadLibraryA_t o_LoadLibraryA;
static LoadLibraryW_t o_LoadLibraryW;
static LoadLibraryExA_t o_LoadLibraryExA;
static LoadLibraryExW_t o_LoadLibraryExW;
static MessageBoxA_t o_MessageBoxA;
static SetWindowTextA_t o_SetWindowTextA;
static CreateWindowExA_t o_CreateWindowExA;
static CreateFontIndirectA_t o_CreateFontIndirectA;
static GetForegroundWindow_t o_GetForegroundWindow;
static SetForegroundWindow_t o_SetForegroundWindow;
static SetActiveWindow_t o_SetActiveWindow;
static SetFocus_t o_SetFocus;
static ShowWindow_t o_ShowWindow;
static GetCursorPos_t o_GetCursorPos;
static AttachThreadInput_t o_AttachThreadInput;
static DialogBoxParamA_t o_DialogBoxParamA;
static CreateDialogParamA_t o_CreateDialogParamA;
static LoadMenuA_t o_LoadMenuA;

static void a2w_path(LPCSTR s, WCHAR *out)
{
    out[0] = 0;
    if (s) MultiByteToWideChar(CP_ACP, 0, s, -1, out, MAX_PATH * 2);
}

/* ------------------------------------------------------------------ 「처음 상태로 되돌리기」 (11-09)
 * The user: the 확인 창 row puts the game back to its just-installed state (not a view). CatSystem2 keeps what the
 * player has seen in <save>\savegen.dat - "CSS\0", u32 zlib size, u32 size, u32 version, then zlib( blocks of u32
 * tag, u32 length, data ): 0x400 = the persistent globals $512..$1023, 0x10 = read flags per scene (and seen
 * movies), 0x50 = CG registry, 0x4000 = system strings - and holds it in memory while it runs (written at exit).
 * So the change is made at the next start, before the engine reads the file: the screen script asks with
 * `opensite http islandko-reset|restore` (caught here in ShellExecute - nothing is opened) and ends the game, and
 * the first open of savegen.dat in the next run finds ko\reset-request.txt:
 *   reset:   savegen.dat is copied to <save>\ko-backup\savegen-<time>.dat (read back and compared), then rewritten
 *            with blocks 0x10 and 0x50 dropped and the progress globals at their first-start values; settings
 *            globals stay (text, touch, per-character voice, system voice, save pages, message window, caption
 *            band, "don't ask again"); $1003 = 1 - the screen shows it as the row's check.
 *   restore: the current savegen.dat goes to ko-backup\savegen-before-restore-<time>.dat and the backup named in
 *            ko\reset-state.txt is copied back ($1003 there is 0).
 * Save slots, info.txt and setup.xml are never touched. Written back as zlib with stored deflate blocks. */
#define KR_MARK 1003
static const short KR_PROGRESS[][2] = {{512, 513}, {515, 515}, {522, 522}, {525, 525}, {530, 530}, {540, 541},
                                       {545, 546}, {572, 572}, {612, 612}, {710, 724}, {740, 748}, {750, 753},
                                       {849, 849}, {900, 923}, {999, 999}, {1002, 1002}, {1004, 1010}};
static volatile LONG g_kr_checked;

typedef struct { const BYTE *in; DWORD inlen, inpos; unsigned bitbuf, bitcnt; BYTE *out; DWORD outlen, outpos; int err; } PUFF;
typedef struct { short *count, *symbol; } PUFFH;
#define PF_MAXBITS 15

static int pf_bits(PUFF *s, int need)
{
    unsigned val = s->bitbuf;
    while (s->bitcnt < (unsigned)need) {
        if (s->inpos >= s->inlen) { s->err = 1; return 0; }
        val |= (unsigned)s->in[s->inpos++] << s->bitcnt;
        s->bitcnt += 8;
    }
    s->bitbuf = need < 32 ? val >> need : 0;
    s->bitcnt -= need;
    return (int)(val & ((1u << need) - 1));
}

static int pf_stored(PUFF *s)
{
    unsigned len;
    s->bitbuf = 0; s->bitcnt = 0;
    if (s->inpos + 4 > s->inlen) return -2;
    len = s->in[s->inpos] | ((unsigned)s->in[s->inpos + 1] << 8);
    if (s->in[s->inpos + 2] != (BYTE)~len || s->in[s->inpos + 3] != (BYTE)(~len >> 8)) return -2;
    s->inpos += 4;
    if (s->inpos + len > s->inlen || s->outpos + len > s->outlen) return -2;
    memcpy(s->out + s->outpos, s->in + s->inpos, len);
    s->inpos += len; s->outpos += len;
    return 0;
}

static int pf_decode(PUFF *s, const PUFFH *h)
{
    int len, code = 0, first = 0, count, index = 0;
    for (len = 1; len <= PF_MAXBITS; len++) {
        code |= pf_bits(s, 1);
        if (s->err) return -1;
        count = h->count[len];
        if (code - count < first) return h->symbol[index + (code - first)];
        index += count; first += count; first <<= 1; code <<= 1;
    }
    return -1;
}

static int pf_construct(PUFFH *h, const short *length, int n)
{
    int symbol, len, left;
    short offs[PF_MAXBITS + 1];
    for (len = 0; len <= PF_MAXBITS; len++) h->count[len] = 0;
    for (symbol = 0; symbol < n; symbol++) h->count[length[symbol]]++;
    if (h->count[0] == n) return 0;
    left = 1;
    for (len = 1; len <= PF_MAXBITS; len++) { left <<= 1; left -= h->count[len]; if (left < 0) return left; }
    offs[1] = 0;
    for (len = 1; len < PF_MAXBITS; len++) offs[len + 1] = (short)(offs[len] + h->count[len]);
    for (symbol = 0; symbol < n; symbol++) if (length[symbol]) h->symbol[offs[length[symbol]]++] = (short)symbol;
    return left;
}

static const short pf_lbase[29] = {3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258};
static const short pf_lext[29] = {0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0};
static const short pf_dbase[30] = {1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025, 1537, 2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577};
static const short pf_dext[30] = {0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13};

static int pf_codes(PUFF *s, const PUFFH *lencode, const PUFFH *distcode)
{
    int symbol, len;
    DWORD dist;
    do {
        symbol = pf_decode(s, lencode);
        if (symbol < 0) return -10;
        if (symbol < 256) {
            if (s->outpos >= s->outlen) return -2;
            s->out[s->outpos++] = (BYTE)symbol;
        } else if (symbol > 256) {
            symbol -= 257;
            if (symbol >= 29) return -10;
            len = pf_lbase[symbol] + pf_bits(s, pf_lext[symbol]);
            symbol = pf_decode(s, distcode);
            if (symbol < 0 || symbol >= 30) return -10;
            dist = (DWORD)(pf_dbase[symbol] + pf_bits(s, pf_dext[symbol]));
            if (s->err) return -2;
            if (dist > s->outpos || s->outpos + (DWORD)len > s->outlen) return -11;
            while (len--) { s->out[s->outpos] = s->out[s->outpos - dist]; s->outpos++; }
        }
    } while (symbol != 256);
    return 0;
}

static int pf_fixed(PUFF *s)
{
    short lencnt[PF_MAXBITS + 1], lensym[288], distcnt[PF_MAXBITS + 1], distsym[30], lengths[288];
    PUFFH lencode, distcode;
    int symbol;
    lencode.count = lencnt; lencode.symbol = lensym; distcode.count = distcnt; distcode.symbol = distsym;
    for (symbol = 0; symbol < 144; symbol++) lengths[symbol] = 8;
    for (; symbol < 256; symbol++) lengths[symbol] = 9;
    for (; symbol < 280; symbol++) lengths[symbol] = 7;
    for (; symbol < 288; symbol++) lengths[symbol] = 8;
    pf_construct(&lencode, lengths, 288);
    for (symbol = 0; symbol < 30; symbol++) lengths[symbol] = 5;
    pf_construct(&distcode, lengths, 30);
    return pf_codes(s, &lencode, &distcode);
}

static int pf_dynamic(PUFF *s)
{
    static const short order[19] = {16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15};
    short lengths[320], lencnt[PF_MAXBITS + 1], lensym[288], distcnt[PF_MAXBITS + 1], distsym[30];
    PUFFH lencode, distcode;
    int nlen, ndist, ncode, index, err;
    lencode.count = lencnt; lencode.symbol = lensym; distcode.count = distcnt; distcode.symbol = distsym;
    nlen = pf_bits(s, 5) + 257; ndist = pf_bits(s, 5) + 1; ncode = pf_bits(s, 4) + 4;
    if (s->err || nlen > 286 || ndist > 30) return -3;
    for (index = 0; index < ncode; index++) lengths[order[index]] = (short)pf_bits(s, 3);
    for (; index < 19; index++) lengths[order[index]] = 0;
    if (s->err || pf_construct(&lencode, lengths, 19) != 0) return -4;
    index = 0;
    while (index < nlen + ndist) {
        int symbol = pf_decode(s, &lencode), len = 0;
        if (symbol < 0) return -5;
        if (symbol < 16) { lengths[index++] = (short)symbol; continue; }
        if (symbol == 16) { if (!index) return -5; len = lengths[index - 1]; symbol = 3 + pf_bits(s, 2); }
        else if (symbol == 17) symbol = 3 + pf_bits(s, 3);
        else symbol = 11 + pf_bits(s, 7);
        if (s->err || index + symbol > nlen + ndist) return -6;
        while (symbol--) lengths[index++] = (short)len;
    }
    if (!lengths[256]) return -9;
    err = pf_construct(&lencode, lengths, nlen);
    if (err && (err < 0 || nlen != lencode.count[0] + lencode.count[1])) return -7;
    err = pf_construct(&distcode, lengths + nlen, ndist);
    if (err && (err < 0 || ndist != distcode.count[0] + distcode.count[1])) return -8;
    return pf_codes(s, &lencode, &distcode);
}

static DWORD kr_adler(const BYTE *p, DWORD n)
{
    DWORD a = 1, b = 0;
    while (n--) { a = (a + *p++) % 65521; b = (b + a) % 65521; }
    return (b << 16) | a;
}

/* zlib stream -> out (exactly outlen bytes); 0 when the stream and its Adler-32 check out */
static int kr_inflate(const BYTE *in, DWORD inlen, BYTE *out, DWORD outlen)
{
    PUFF s;
    int last, type, err;
    DWORD ad;
    if (inlen < 7 || (in[0] & 0x0f) != 8 || ((in[0] << 8) | in[1]) % 31 || (in[1] & 0x20)) return -1;
    memset(&s, 0, sizeof(s));
    s.in = in + 2; s.inlen = inlen - 6; s.out = out; s.outlen = outlen;
    do {
        last = pf_bits(&s, 1);
        type = pf_bits(&s, 2);
        if (s.err) return -2;
        err = type == 0 ? pf_stored(&s) : type == 1 ? pf_fixed(&s) : type == 2 ? pf_dynamic(&s) : -1;
        if (err) return err;
        if (s.err) return -2;
    } while (!last);
    if (s.outpos != outlen) return -12;
    ad = ((DWORD)in[inlen - 4] << 24) | ((DWORD)in[inlen - 3] << 16) | ((DWORD)in[inlen - 2] << 8) | in[inlen - 1];
    return ad == kr_adler(out, outlen) ? 0 : -13;
}

/* zlib stream with stored blocks (no compression) */
static BYTE *kr_store(const BYTE *p, DWORD n, DWORD *outn)
{
    DWORD cap = 2 + n + (n / 65535 + 1) * 5 + 4, o = 0, ad = kr_adler(p, n);
    BYTE *z = (BYTE *)HeapAlloc(GetProcessHeap(), 0, cap);
    if (!z) return NULL;
    z[o++] = 0x78; z[o++] = 0x01;
    do {
        DWORD k = n > 65535 ? 65535 : n;
        z[o++] = (BYTE)(n <= 65535);
        z[o++] = (BYTE)k; z[o++] = (BYTE)(k >> 8); z[o++] = (BYTE)~k; z[o++] = (BYTE)(~k >> 8);
        memcpy(z + o, p, k); o += k; p += k; n -= k;
    } while (n);
    z[o++] = (BYTE)(ad >> 24); z[o++] = (BYTE)(ad >> 16); z[o++] = (BYTE)(ad >> 8); z[o++] = (BYTE)ad;
    *outn = o;
    return z;
}

static BYTE *kr_read(const WCHAR *path, DWORD *len)
{
    HANDLE h = o_CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    DWORD n, got = 0;
    BYTE *b;
    if (h == INVALID_HANDLE_VALUE) return NULL;
    n = GetFileSize(h, NULL);
    b = (BYTE *)HeapAlloc(GetProcessHeap(), 0, n + 1);
    if (b && (!ReadFile(h, b, n, &got, NULL) || got != n)) { HeapFree(GetProcessHeap(), 0, b); b = NULL; }
    CloseHandle(h);
    *len = n;
    return b;
}

/* write via a temporary file, read it back, then move it over the target */
static int kr_write(const WCHAR *path, const BYTE *p, DWORD n)
{
    WCHAR tmp[MAX_PATH * 2];
    HANDLE h;
    DWORD w = 0, rn = 0;
    BYTE *r;
    int ok;
    lstrcpyW(tmp, path); lstrcatW(tmp, L".ko-tmp");
    h = o_CreateFileW(tmp, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) return 0;
    ok = WriteFile(h, p, n, &w, NULL) && w == n && FlushFileBuffers(h);
    CloseHandle(h);
    r = ok ? kr_read(tmp, &rn) : NULL;
    ok = r && rn == n && !memcmp(r, p, n);
    if (r) HeapFree(GetProcessHeap(), 0, r);
    if (ok) ok = MoveFileExW(tmp, path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH);
    if (!ok) DeleteFileW(tmp);
    return ok;
}

static int kr_is_progress(int v)
{
    int i;
    for (i = 0; i < (int)(sizeof(KR_PROGRESS) / sizeof(KR_PROGRESS[0])); i++)
        if (v >= KR_PROGRESS[i][0] && v <= KR_PROGRESS[i][1]) return 1;
    return 0;
}

/* the reset savegen.dat bytes from the current ones (NULL when the file is not in the expected form) */
static BYTE *kr_reset_bytes(const BYTE *f, DWORD fn, DWORD *outn, int *globals_reset)
{
    DWORD zn, size, o = 0, w = 0, zo = 0;
    BYTE *in, *out, *z, *res;
    int have_globals = 0;
    if (fn < 16 || memcmp(f, "CSS\0", 4)) return NULL;
    zn = *(const DWORD *)(f + 4); size = *(const DWORD *)(f + 8);
    if (zn != fn - 16 || size == 0 || size > (16u << 20)) return NULL;
    in = (BYTE *)HeapAlloc(GetProcessHeap(), 0, size);
    out = (BYTE *)HeapAlloc(GetProcessHeap(), 0, size);
    if (!in || !out || kr_inflate(f + 16, zn, in, size) != 0) { logw(L"reset: savegen.dat did not inflate"); goto fail; }
    *globals_reset = 0;
    while (o + 8 <= size) {
        DWORD tag = *(DWORD *)(in + o), len = *(DWORD *)(in + o + 4);
        if (len > size - o - 8) { logw(L"reset: block %x at %u runs past the end", tag, o); goto fail; }
        if (tag == 0x10 || tag == 0x50) { o += 8 + len; continue; }        /* read flags, CG registry: dropped */
        memcpy(out + w, in + o, 8 + len);
        if (tag == 0x400) {
            int *g = (int *)(out + w + 8), i;
            if (len != 2048) { logw(L"reset: globals block of %u bytes", len); goto fail; }
            for (i = 0; i < 512; i++) {
                int v = 512 + i, def = (v == 512 || v == 540 || v == 541 || v == 572) ? -1 : 0;
                if (kr_is_progress(v) && g[i] != def) { g[i] = def; (*globals_reset)++; }
            }
            g[KR_MARK - 512] = 1;
            have_globals = 1;
        }
        w += 8 + len; o += 8 + len;
    }
    if (o != size || !have_globals) { logw(L"reset: savegen.dat blocks end at %u of %u, globals %d", o, size, have_globals); goto fail; }
    z = kr_store(out, w, &zo);
    if (!z) goto fail;
    res = (BYTE *)HeapAlloc(GetProcessHeap(), 0, 16 + zo);
    if (res) {
        memcpy(res, f, 16);
        *(DWORD *)(res + 4) = zo; *(DWORD *)(res + 8) = w;
        memcpy(res + 16, z, zo);
        *outn = 16 + zo;
    }
    HeapFree(GetProcessHeap(), 0, z);
    HeapFree(GetProcessHeap(), 0, in); HeapFree(GetProcessHeap(), 0, out);
    return res;
fail:
    if (in) HeapFree(GetProcessHeap(), 0, in);
    if (out) HeapFree(GetProcessHeap(), 0, out);
    return NULL;
}

static void kr_file(const WCHAR *name, WCHAR *out)
{
    lstrcpyW(out, g_kodir); lstrcatW(out, name);
}

static void kr_put_text(const WCHAR *path, const WCHAR *text)
{
    char u[MAX_PATH * 6];
    int n = WideCharToMultiByte(CP_UTF8, 0, text, -1, u, sizeof(u), NULL, NULL);
    if (n > 0) kr_write(path, (const BYTE *)u, (DWORD)(n - 1));
}

static int kr_get_text(const WCHAR *path, WCHAR *out, int cap)
{
    DWORD n;
    BYTE *b = kr_read(path, &n);
    int k;
    out[0] = 0;
    if (!b) return 0;
    b[n] = 0;
    k = MultiByteToWideChar(CP_UTF8, 0, (char *)b, -1, out, cap);
    HeapFree(GetProcessHeap(), 0, b);
    while (k > 1 && (out[k - 2] == L'\r' || out[k - 2] == L'\n' || out[k - 2] == L' ')) out[--k - 1] = 0;
    return out[0] != 0;
}

/* the first open of <save>\savegen.dat in this run: carry out a pending reset / restore request */
static void kr_check(const WCHAR *path)
{
    WCHAR req[MAX_PATH * 2], state[MAX_PATH * 2], what[32], dir[MAX_PATH * 2], bak[MAX_PATH * 2], cur[MAX_PATH * 2];
    SYSTEMTIME t;
    int i;
    if (InterlockedExchange(&g_kr_checked, 1)) return;
    kr_file(L"reset-request.txt", req);
    if (!kr_get_text(req, what, 32)) return;
    logw(L"reset: request '%s' at the first open of %s", what, path);
    lstrcpyW(dir, path);
    for (i = lstrlenW(dir); i > 0 && dir[i - 1] != L'\\' && dir[i - 1] != L'/'; i--) ;
    dir[i] = 0;
    lstrcatW(dir, L"ko-backup");
    CreateDirectoryW(dir, NULL);
    GetLocalTime(&t);
    kr_file(L"reset-state.txt", state);
    if (!lstrcmpiW(what, L"reset")) {
        DWORD fn = 0, nn = 0, bn = 0;
        BYTE *f = kr_read(path, &fn), *nb, *back;
        int greset = 0;
        if (!f) { logw(L"reset: cannot read %s", path); DeleteFileW(req); return; }
        wsprintfW(bak, L"%s\\savegen-%04d%02d%02d-%02d%02d%02d.dat", dir, t.wYear, t.wMonth, t.wDay, t.wHour, t.wMinute, t.wSecond);
        nb = kr_reset_bytes(f, fn, &nn, &greset);
        back = NULL;
        if (nb && kr_write(bak, f, fn) && (back = kr_read(bak, &bn)) != NULL && bn == fn && !memcmp(back, f, fn)
            && kr_write(path, nb, nn)) {
            kr_put_text(state, bak);
            logw(L"reset: done - backup %s (%u bytes), new savegen.dat %u bytes, progress globals reset %d", bak, fn, nn, greset);
        } else {
            logw(L"reset: NOT done (backup or write failed) - savegen.dat left as it was");
        }
        if (back) HeapFree(GetProcessHeap(), 0, back);
        if (nb) HeapFree(GetProcessHeap(), 0, nb);
        HeapFree(GetProcessHeap(), 0, f);
        DeleteFileW(req);
        return;
    }
    if (!lstrcmpiW(what, L"restore")) {
        DWORD bn = 0, cn = 0;
        BYTE *b, *c;
        if (!kr_get_text(state, bak, MAX_PATH * 2) || !(b = kr_read(bak, &bn))) {
            logw(L"restore: no backup recorded / readable (%s)", bak);
            DeleteFileW(req);
            return;
        }
        wsprintfW(cur, L"%s\\savegen-before-restore-%04d%02d%02d-%02d%02d%02d.dat", dir, t.wYear, t.wMonth, t.wDay, t.wHour, t.wMinute, t.wSecond);
        c = kr_read(path, &cn);
        if ((!c || kr_write(cur, c, cn)) && kr_write(path, b, bn)) {
            DeleteFileW(state);
            logw(L"restore: done - %s back (%u bytes); the reset-time state kept as %s", bak, bn, c ? cur : L"(none)");
        } else {
            logw(L"restore: NOT done - savegen.dat left as it was");
        }
        if (c) HeapFree(GetProcessHeap(), 0, c);
        HeapFree(GetProcessHeap(), 0, b);
        DeleteFileW(req);
        return;
    }
    logw(L"reset: unknown request '%s'", what);
    DeleteFileW(req);
}

static void kr_on_open(const WCHAR *n)
{
    int L;
    if (!n || g_kr_checked) return;
    L = lstrlenW(n);
    if (L >= 12 && CompareStringOrdinal(n + L - 11, -1, L"savegen.dat", -1, TRUE) == CSTR_EQUAL &&
        (n[L - 12] == L'\\' || n[L - 12] == L'/'))
        kr_check(n);
}

/* `opensite http islandko-reset|restore` from the 확인 창 tab: a request for the next start, nothing is opened */
static int kr_request(const char *s)
{
    const char *p;
    WCHAR req[MAX_PATH * 2];
    if (!s) return 0;
    for (p = s; *p; p++) {
        if (!_strnicmp(p, "islandko-reset", 14) || !_strnicmp(p, "islandko-restore", 16)) {
            kr_file(L"reset-request.txt", req);
            kr_put_text(req, !_strnicmp(p, "islandko-reset", 14) ? L"reset" : L"restore");
            logw(L"reset: request '%S' for the next start", p);
            return 1;
        }
    }
    return 0;
}

typedef HINSTANCE(WINAPI *ShellExecuteA_t)(HWND, LPCSTR, LPCSTR, LPCSTR, LPCSTR, INT);
typedef BOOL(WINAPI *ShellExecuteExA_t)(void *);
static ShellExecuteA_t o_ShellExecuteA;
static ShellExecuteExA_t o_ShellExecuteExA;

static HINSTANCE WINAPI h_ShellExecuteA(HWND w, LPCSTR op, LPCSTR file, LPCSTR par, LPCSTR dir, INT show)
{
    if (kr_request(file) || kr_request(par)) return (HINSTANCE)(ULONG_PTR)42;
    return o_ShellExecuteA(w, op, file, par, dir, show);
}

/* SHELLEXECUTEINFOA: cbSize, fMask, hwnd, lpVerb, lpFile, lpParameters, lpDirectory, nShow, hInstApp, ... */
static BOOL WINAPI h_ShellExecuteExA(void *info)
{
    BYTE *i = (BYTE *)info;
    if (i && (kr_request(*(const char **)(i + 16)) || kr_request(*(const char **)(i + 20)))) {
        *(HINSTANCE *)(i + 32) = (HINSTANCE)(ULONG_PTR)42;
        return TRUE;
    }
    return o_ShellExecuteExA(info);
}

static HANDLE WINAPI h_CreateFileA(LPCSTR n, DWORD a, DWORD s, LPSECURITY_ATTRIBUTES sa, DWORD c, DWORD f, HANDLE t)
{
    WCHAR w[MAX_PATH * 2], r[MAX_PATH * 2];
    ensure_rsrc();
    if (n && !g_kr_checked) {
        a2w_path(n, w);
        kr_on_open(w);
    }
    if (g_ko && n) {
        a2w_path(n, w);
        if (redirect(w, r)) {
            InterlockedIncrement(&g_redirects);
            logw(L"redirect %s -> %s", w, r);
            return o_CreateFileW(r, a, s, sa, c, f, t);
        }
    }
    return o_CreateFileA(n, a, s, sa, c, f, t);
}

static HANDLE WINAPI h_CreateFileW(LPCWSTR n, DWORD a, DWORD s, LPSECURITY_ATTRIBUTES sa, DWORD c, DWORD f, HANDLE t)
{
    WCHAR r[MAX_PATH * 2];
    ensure_rsrc();
    kr_on_open(n);
    if (g_ko && n && redirect(n, r)) {
        InterlockedIncrement(&g_redirects);
        logw(L"redirect %s -> %s", n, r);
        return o_CreateFileW(r, a, s, sa, c, f, t);
    }
    return o_CreateFileW(n, a, s, sa, c, f, t);
}

static int libname_is_cs2conf(const WCHAR *w, WCHAR *r)
{
    const WCHAR *b = w, *p;
    if (!g_ko || !w) return 0;
    for (p = w; *p; p++) if (*p == L'\\' || *p == L'/') b = p + 1;
    if (CompareStringOrdinal(b, -1, L"cs2conf.dll", -1, TRUE) != CSTR_EQUAL) return 0;
    if (b != w) return redirect(w, r);
    lstrcpyW(r, g_kodir); lstrcatW(r, L"cs2conf.dll");
    return file_exists(r);
}

static void hook_conf(HMODULE m);

static HMODULE conf_loaded(HMODULE m) { hook_conf(m); return m; }

/* the settings plugin loaded from the game folder (GOG: <game>\cs2conf.dll, loaded and freed
 * each time the settings open) gets the dialog text hooks too */
static HMODULE conf_plain(HMODULE m, const WCHAR *name)
{
    const WCHAR *b = name, *p;
    if (!m || !g_ko || !name) return m;
    for (p = name; *p; p++) if (*p == L'\\' || *p == L'/') b = p + 1;
    if (CompareStringOrdinal(b, -1, L"cs2conf.dll", -1, TRUE) == CSTR_EQUAL) hook_conf(m);
    return m;
}

static HMODULE WINAPI h_LoadLibraryA(LPCSTR n)
{
    WCHAR w[MAX_PATH * 2], r[MAX_PATH * 2];
    ensure_rsrc();
    a2w_path(n, w);
    if (libname_is_cs2conf(w, r)) { logw(L"loadlib %s -> %s", w, r); return conf_loaded(o_LoadLibraryExW(r, NULL, LOAD_WITH_ALTERED_SEARCH_PATH)); }
    return conf_plain(o_LoadLibraryA(n), w);
}
static HMODULE WINAPI h_LoadLibraryW(LPCWSTR n)
{
    WCHAR r[MAX_PATH * 2];
    ensure_rsrc();
    if (libname_is_cs2conf(n, r)) { logw(L"loadlib %s -> %s", n, r); return conf_loaded(o_LoadLibraryExW(r, NULL, LOAD_WITH_ALTERED_SEARCH_PATH)); }
    return conf_plain(o_LoadLibraryW(n), n);
}
static HMODULE WINAPI h_LoadLibraryExA(LPCSTR n, HANDLE f, DWORD fl)
{
    WCHAR w[MAX_PATH * 2], r[MAX_PATH * 2];
    ensure_rsrc();
    a2w_path(n, w);
    if (!(fl & (LOAD_LIBRARY_AS_DATAFILE | LOAD_LIBRARY_AS_IMAGE_RESOURCE)) && libname_is_cs2conf(w, r)) {
        logw(L"loadlib %s -> %s", w, r);
        return conf_loaded(o_LoadLibraryExW(r, f, fl | LOAD_WITH_ALTERED_SEARCH_PATH));
    }
    if (fl & (LOAD_LIBRARY_AS_DATAFILE | LOAD_LIBRARY_AS_IMAGE_RESOURCE)) return o_LoadLibraryExA(n, f, fl);
    return conf_plain(o_LoadLibraryExA(n, f, fl), w);
}
static HMODULE WINAPI h_LoadLibraryExW(LPCWSTR n, HANDLE f, DWORD fl)
{
    WCHAR r[MAX_PATH * 2];
    ensure_rsrc();
    if (!(fl & (LOAD_LIBRARY_AS_DATAFILE | LOAD_LIBRARY_AS_IMAGE_RESOURCE)) && libname_is_cs2conf(n, r)) {
        logw(L"loadlib %s -> %s", n, r);
        return conf_loaded(o_LoadLibraryExW(r, f, fl | LOAD_WITH_ALTERED_SEARCH_PATH));
    }
    if (fl & (LOAD_LIBRARY_AS_DATAFILE | LOAD_LIBRARY_AS_IMAGE_RESOURCE)) return o_LoadLibraryExW(n, f, fl);
    return conf_plain(o_LoadLibraryExW(n, f, fl), n);
}

/* ------------------------------------------------------------------ text UI */
static int donor_text(const char *s, WCHAR *out, int cap);

/* exe text -> W: the Korean message table first, then startup.xml donor strings, then the
 * patch code page */
static void tr_text(const char *in, WCHAR *out, int cap)
{
    WCHAR *tmp = (WCHAR *)HeapAlloc(GetProcessHeap(), 0, cap * sizeof(WCHAR));
    if (!tmp) { if (!donor_text(in, out, cap)) a2w(in, out, cap); return; }
    a2w(in, tmp, cap);
    if (!(g_ko && translate(tmp, out, cap)) && !donor_text(in, out, cap)) lstrcpynW(out, tmp, cap);
    HeapFree(GetProcessHeap(), 0, tmp);
}

static int WINAPI h_MessageBoxA(HWND h, LPCSTR text, LPCSTR cap, UINT type)
{
    WCHAR wt[4096], wc[512];
    ensure_rsrc();
    tr_text(text, wt, 4096);
    tr_text(cap, wc, 512);
    InterlockedIncrement(&g_mbox);
    logw(L"messagebox type=%x caption=[%s] text=[%s] caller=%p", type, wc, wt, _ReturnAddress());
    if (g_test) {
        UINT t = type & 0xF;
        int ans = (t == MB_YESNO || t == MB_YESNOCANCEL) ? IDYES : (t == MB_OKCANCEL || t == MB_RETRYCANCEL) ? IDOK : IDOK;
        if (g_shm && g_shm->answer) ans = g_shm->answer;
        logw(L"messagebox auto-answer %d", ans);
        return ans;
    }
    return MessageBoxW(h, wt, wc, type);
}

static BOOL WINAPI h_SetWindowTextA(HWND h, LPCSTR s)
{
    WCHAR w[1024];
    tr_text(s, w, 1024);
    return SetWindowTextW(h, w);
}

/* ------------------------------------------------------------------ list view text
 * The exe fills its list views (GOG: settings > system information) with ANSI messages, and the
 * common controls showed the CP949 language.txt strings as Latin-1 (11-08 user screenshot). In
 * Korean mode such text goes out as the W message, converted with the patch code page. Items
 * using fields outside the classic LVITEM/LVCOLUMN are left alone. */
typedef LRESULT (WINAPI *SendMessageA_t)(HWND, UINT, WPARAM, LPARAM);
typedef LRESULT (WINAPI *SendDlgItemMessageA_t)(HWND, int, UINT, WPARAM, LPARAM);
static SendMessageA_t o_SendMessageA;
static SendDlgItemMessageA_t o_SendDlgItemMessageA;

typedef BOOL (WINAPI *SetDlgItemTextA_t)(HWND, int, LPCSTR);
typedef int (WINAPI *GetWindowTextA_t)(HWND, LPSTR, int);
typedef UINT (WINAPI *GetDlgItemTextA_t)(HWND, int, LPSTR, int);
static SetDlgItemTextA_t o_SetDlgItemTextA;
static GetWindowTextA_t o_GetWindowTextA;
static GetDlgItemTextA_t o_GetDlgItemTextA;
static BYTE *g_exe_lo, *g_exe_hi;   /* main exe image: list view conversion is for its calls only */

static int has_high(const char *s)
{
    if (!s || s == LPSTR_TEXTCALLBACKA) return 0;
    for (; *s; s++) if ((BYTE)*s >= 0x80) return 1;
    return 0;
}

/* ------------------------------------------------------------------ donor strings in dialogs
 * startup.xml strings (key names, voice names, sound group comments) are our donor-kanji CP932
 * bytes, which the engine draws with ISLAND-KO.ttf. Windows list/combo boxes and labels read them
 * in the system code page and showed wrong Hangul (11-08 user screenshot: GOG settings > input >
 * button list). In Korean mode a string that reads as CP932 with donor kanji and without
 * half-width katakana (every CP949 Hangul string has those when read as CP932) goes out as the
 * W call with the donor table applied; any other string is passed on untouched. Reading such an
 * item back as ANSI gives the original bytes, so the exe still finds its own strings. */
#define DN_MAX 512
static struct { WCHAR *w; char *a; } g_dn[DN_MAX];
static volatile LONG g_ndn;

static int same_w(const WCHAR *a, const WCHAR *b)
{
    while (*a && *a == *b) { a++; b++; }
    return *a == *b;
}

static void dn_remember(const WCHAR *w, const char *a)
{
    int i;
    EnterCriticalSection(&g_cs);
    for (i = 0; i < g_ndn; i++) if (same_w(g_dn[i].w, w)) break;
    if (i == g_ndn && g_ndn < DN_MAX) {
        int lw = lstrlenW(w) + 1, la = lstrlenA(a) + 1;
        WCHAR *cw = (WCHAR *)HeapAlloc(GetProcessHeap(), 0, lw * sizeof(WCHAR));
        char *ca = (char *)HeapAlloc(GetProcessHeap(), 0, la);
        if (cw && ca) {
            CopyMemory(cw, w, lw * sizeof(WCHAR)); CopyMemory(ca, a, la);
            g_dn[i].w = cw; g_dn[i].a = ca;
            InterlockedIncrement(&g_ndn);
            if (g_ndn <= 3 || g_ndn == DN_MAX) logw(L"donor text #%d len=%d", g_ndn, lw - 1);
        }
    }
    LeaveCriticalSection(&g_cs);
}

static const char *dn_recall(const WCHAR *w)
{
    const char *r = NULL;
    int i;
    if (!g_ndn || !w || !*w) return NULL;
    EnterCriticalSection(&g_cs);
    for (i = 0; i < g_ndn; i++) if (same_w(g_dn[i].w, w)) { r = g_dn[i].a; break; }
    LeaveCriticalSection(&g_cs);
    return r;
}

static int donor_text(const char *s, WCHAR *out, int cap)
{
    int i, donors = 0;
    if (!g_ko || !g_nmap || !has_high(s)) return 0;
    if (MultiByteToWideChar(932, MB_ERR_INVALID_CHARS, s, -1, out, cap) <= 0) { out[0] = 0; return 0; }
    for (i = 0; out[i]; i++) {
        WCHAR c = out[i];
        if (c >= 0xFF61 && c <= 0xFF9F) { out[0] = 0; return 0; }
        if (c >= MAP_LO && c < MAP_HI && g_map[c - MAP_LO]) { out[i] = g_map[c - MAP_LO]; donors++; }
    }
    if (!donors) { out[0] = 0; return 0; }
    dn_remember(out, s);
    return 1;
}

/* 1 list box, 2 combo box; 0 other classes and owner-drawn boxes without strings */
static int str_ctl(HWND h)
{
    WCHAR cls[16];
    LONG st;
    if (!h || !GetClassNameW(h, cls, 16)) return 0;
    st = GetWindowLongW(h, GWL_STYLE);
    if (!lstrcmpiW(cls, L"ListBox") || !lstrcmpiW(cls, L"ComboLBox"))
        return (st & (LBS_OWNERDRAWFIXED | LBS_OWNERDRAWVARIABLE)) && !(st & LBS_HASSTRINGS) ? 0 : 1;
    if (!lstrcmpiW(cls, L"ComboBox"))
        return (st & (CBS_OWNERDRAWFIXED | CBS_OWNERDRAWVARIABLE)) && !(st & CBS_HASSTRINGS) ? 0 : 2;
    return 0;
}

static int own_window(HWND h)
{
    DWORD pid = 0;
    return h && GetWindowThreadProcessId(h, &pid) && pid == GetCurrentProcessId();
}

/* ANSI read-back of text we stored as W from a donor string: the original bytes, never longer
 * than what the system code page would have returned (the caller sized its buffer for that) */
static int dn_read(HWND h, UINT m, WPARAM w, LPARAM l, LRESULT *res)
{
    WCHAR buf[1024];
    const char *a;
    LRESULT n;
    if (!g_ndn || !l || !own_window(h)) return 0;
    if (m == WM_GETTEXT) {
        if ((int)w <= 0) return 0;
        n = SendMessageW(h, WM_GETTEXTLENGTH, 0, 0);
        if (n <= 0 || n >= 1024) return 0;
        buf[0] = 0;
        SendMessageW(h, WM_GETTEXT, 1024, (LPARAM)buf);
        a = dn_recall(buf);
        if (!a || lstrlenA(a) >= (int)w) return 0;
    } else {
        UINT lenmsg = m == LB_GETTEXT ? LB_GETTEXTLEN : CB_GETLBTEXTLEN;
        if (str_ctl(h) != (m == LB_GETTEXT ? 1 : 2)) return 0;
        n = SendMessageW(h, lenmsg, w, 0);
        if (n <= 0 || n >= 1024) return 0;
        buf[0] = 0;
        if (SendMessageW(h, m, w, (LPARAM)buf) <= 0) return 0;
        a = dn_recall(buf);
        if (!a || lstrlenA(a) > o_SendMessageA(h, lenmsg, w, 0)) return 0;
    }
    lstrcpyA((char *)l, a);
    *res = lstrlenA(a);
    return 1;
}

static int dlg_text(HWND h, UINT m, WPARAM w, LPARAM l, LRESULT *res)
{
    WCHAR buf[1024];
    int kind;
    switch (m) {
    case LB_ADDSTRING: case LB_INSERTSTRING: case LB_FINDSTRING: case LB_FINDSTRINGEXACT: case LB_SELECTSTRING:
        kind = 1; break;
    case CB_ADDSTRING: case CB_INSERTSTRING: case CB_FINDSTRING: case CB_FINDSTRINGEXACT: case CB_SELECTSTRING:
        kind = 2; break;
    case WM_SETTEXT:
        if (!donor_text((const char *)l, buf, 1024)) return 0;
        *res = SendMessageW(h, WM_SETTEXT, w, (LPARAM)buf);
        return 1;
    case LB_GETTEXT: case CB_GETLBTEXT: case WM_GETTEXT:
        return dn_read(h, m, w, l, res);
    default:
        return 0;
    }
    if (str_ctl(h) != kind || !donor_text((const char *)l, buf, 1024)) return 0;
    *res = SendMessageW(h, m, w, (LPARAM)buf);
    return 1;
}

static int lv_text(HWND h, UINT m, WPARAM w, LPARAM l, LRESULT *res)
{
    WCHAR buf[1024];
    if (!g_ko || !h || !l) return 0;
    if (m == LVM_INSERTITEMA || m == LVM_SETITEMA || m == LVM_SETITEMTEXTA) {
        const LVITEMA *a = (const LVITEMA *)l;
        LVITEMW u;
        UINT known = LVIF_TEXT | LVIF_IMAGE | LVIF_PARAM | LVIF_STATE | LVIF_INDENT | LVIF_NORECOMPUTE | LVIF_DI_SETITEM;
        if (m != LVM_SETITEMTEXTA && (!(a->mask & LVIF_TEXT) || (a->mask & ~known))) return 0;
        if (!has_high(a->pszText)) return 0;
        ZeroMemory(&u, sizeof(u));
        u.mask = a->mask; u.iItem = a->iItem; u.iSubItem = a->iSubItem; u.state = a->state; u.stateMask = a->stateMask;
        u.cchTextMax = a->cchTextMax; u.iImage = a->iImage; u.lParam = a->lParam;
        if (m != LVM_SETITEMTEXTA && (a->mask & LVIF_INDENT)) u.iIndent = a->iIndent;
        if (!donor_text(a->pszText, buf, 1024)) a2w(a->pszText, buf, 1024);
        u.pszText = buf;
        *res = SendMessageW(h, m == LVM_INSERTITEMA ? LVM_INSERTITEMW : m == LVM_SETITEMA ? LVM_SETITEMW : LVM_SETITEMTEXTW, w, (LPARAM)&u);
        return 1;
    }
    if (m == LVM_INSERTCOLUMNA || m == LVM_SETCOLUMNA) {
        const LVCOLUMNA *a = (const LVCOLUMNA *)l;
        LVCOLUMNW u;
        UINT known = LVCF_FMT | LVCF_WIDTH | LVCF_TEXT | LVCF_SUBITEM | LVCF_IMAGE | LVCF_ORDER;
        if (!(a->mask & LVCF_TEXT) || (a->mask & ~known) || !has_high(a->pszText)) return 0;
        ZeroMemory(&u, sizeof(u));
        u.mask = a->mask; u.fmt = a->fmt; u.cx = a->cx; u.cchTextMax = a->cchTextMax; u.iSubItem = a->iSubItem;
        if (a->mask & LVCF_IMAGE) u.iImage = a->iImage;
        if (a->mask & LVCF_ORDER) u.iOrder = a->iOrder;
        if (!donor_text(a->pszText, buf, 1024)) a2w(a->pszText, buf, 1024);
        u.pszText = buf;
        *res = SendMessageW(h, m == LVM_INSERTCOLUMNA ? LVM_INSERTCOLUMNW : LVM_SETCOLUMNW, w, (LPARAM)&u);
        return 1;
    }
    return 0;
}

static int from_exe(void *ra) { return (BYTE *)ra >= g_exe_lo && (BYTE *)ra < g_exe_hi; }

/* list views (patch code page): the exe's own calls, and on the English build also its cs2conf.dll plugin, whose
 * system information page showed CP949 as Latin-1; list/combo boxes and WM_SETTEXT/GETTEXT:
 * donor strings only, from the exe or from cs2conf.dll */
static LRESULT WINAPI h_SendMessageA(HWND h, UINT m, WPARAM w, LPARAM l)
{
    LRESULT r;
    if (m >= LVM_FIRST && m < LVM_FIRST + 0x100) {
        if ((g_edition == 2 || from_exe(_ReturnAddress())) && lv_text(h, m, w, l, &r)) return r;
    } else if (g_ko && dlg_text(h, m, w, l, &r)) return r;
    return o_SendMessageA(h, m, w, l);
}

static LRESULT WINAPI h_SendDlgItemMessageA(HWND d, int id, UINT m, WPARAM w, LPARAM l)
{
    LRESULT r;
    if (m >= LVM_FIRST && m < LVM_FIRST + 0x100) {
        if ((g_edition == 2 || from_exe(_ReturnAddress())) && lv_text(GetDlgItem(d, id), m, w, l, &r)) return r;
    } else if (g_ko && dlg_text(GetDlgItem(d, id), m, w, l, &r)) return r;
    return o_SendDlgItemMessageA(d, id, m, w, l);
}

static BOOL WINAPI h_SetDlgItemTextA(HWND d, int id, LPCSTR s)
{
    WCHAR buf[1024];
    if (donor_text(s, buf, 1024)) return SetDlgItemTextW(d, id, buf);
    return o_SetDlgItemTextA(d, id, s);
}

static int WINAPI h_GetWindowTextA(HWND h, LPSTR s, int n)
{
    LRESULT r;
    if (g_ndn && s && n > 0 && dn_read(h, WM_GETTEXT, (WPARAM)n, (LPARAM)s, &r)) return (int)r;
    return o_GetWindowTextA(h, s, n);
}

static UINT WINAPI h_GetDlgItemTextA(HWND d, int id, LPSTR s, int n)
{
    LRESULT r;
    if (g_ndn && s && n > 0 && dn_read(GetDlgItem(d, id), WM_GETTEXT, (WPARAM)n, (LPARAM)s, &r)) return (UINT)r;
    return o_GetDlgItemTextA(d, id, s, n);
}

static HWND WINAPI h_CreateWindowExA(DWORD ex, LPCSTR cls, LPCSTR name, DWORD st, int x, int y, int cx, int cy, HWND parent, HMENU menu, HINSTANCE inst, LPVOID param)
{
    HWND h;
    int top = !parent || (st & WS_CHILD) == 0;
    if (g_test && top && !(st & WS_CHILD)) { ex |= WS_EX_NOACTIVATE; x = g_tx; y = g_ty; }
    h = o_CreateWindowExA(ex, cls, name, st, x, y, cx, cy, parent, menu, inst, param);
    if (h && top && !(st & WS_CHILD) && !g_mainwnd && (st & WS_CAPTION || st & WS_POPUP)) {
        WCHAR w[512];
        g_mainwnd = h;
        if (name && *name) { tr_text(name, w, 512); SetWindowTextW(h, w); }
        logw(L"main window %p style=%x ex=%x %dx%d", h, st, ex, cx, cy);
    }
    return h;
}

/* Korean mode: every font the game creates uses our face. The player's saved settings
 * (setup.xml FONT/face, e.g. MS Gothic from an earlier Japanese run) would otherwise win and
 * the Korean PUA codes would have no glyphs. */
static char g_face[LF_FACESIZE] = "ISLAND KO";

static HFONT WINAPI h_CreateFontIndirectA(const LOGFONTA *lf)
{
    LOGFONTA l2;
    if (lf && InterlockedIncrement(&g_fonts_logged) <= 16) {
        WCHAR face[64];
        MultiByteToWideChar(932, 0, lf->lfFaceName, -1, face, 64);
        logw(L"font face=[%s] h=%d w=%d weight=%d charset=%d quality=%d%s", face, lf->lfHeight, lf->lfWidth, lf->lfWeight, lf->lfCharSet, lf->lfQuality, (g_ko && g_font_ok) ? L" -> ISLAND KO" : L"");
    }
    if (lf && g_ko && g_font_ok) {
        l2 = *lf;
        lstrcpynA(l2.lfFaceName, g_face, LF_FACESIZE);
        /* our donor-kanji glyphs are keyed to CP932 codes (GetGlyphOutlineA converts through the
         * font's charset) - the English build may ask for another charset */
        l2.lfCharSet = SHIFTJIS_CHARSET;
        return o_CreateFontIndirectA(&l2);
    }
    return o_CreateFontIndirectA(lf);
}

/* test runs: a mutex of our own, so a test copy and the player's game never see each other
 * (both editions use FWISLANDMUTEXOBJ) */
typedef HANDLE(WINAPI *CreateMutexA_t)(LPSECURITY_ATTRIBUTES, BOOL, LPCSTR);
static CreateMutexA_t o_CreateMutexA;
static HANDLE WINAPI h_CreateMutexA(LPSECURITY_ATTRIBUTES sa, BOOL own, LPCSTR name)
{
    char n2[MAX_PATH];
    if (g_test && name && lstrlenA(name) < MAX_PATH - 16) {
        lstrcpyA(n2, name); lstrcatA(n2, "_ISLANDKO_TEST");
        logw(L"test mutex renamed");
        return o_CreateMutexA(sa, own, n2);
    }
    return o_CreateMutexA(sa, own, name);
}

/* ------------------------------------------------------------------ test mode */
static HWND WINAPI h_GetForegroundWindow(void)
{
    if (g_test && g_mainwnd && IsWindow(g_mainwnd)) return g_mainwnd;
    return o_GetForegroundWindow();
}
static BOOL WINAPI h_SetForegroundWindow(HWND h) { if (g_test) return TRUE; return o_SetForegroundWindow(h); }
static HWND WINAPI h_SetActiveWindow(HWND h) { if (g_test) return g_mainwnd; return o_SetActiveWindow(h); }
static HWND WINAPI h_SetFocus(HWND h) { if (g_test) return g_mainwnd; return o_SetFocus(h); }
static BOOL WINAPI h_AttachThreadInput(DWORD a, DWORD b, BOOL c) { if (g_test) return TRUE; return o_AttachThreadInput(a, b, c); }
static BOOL WINAPI h_ShowWindow(HWND h, int cmd)
{
    if (g_test && (cmd == SW_SHOW || cmd == SW_SHOWNORMAL || cmd == SW_RESTORE || cmd == SW_SHOWDEFAULT)) cmd = SW_SHOWNOACTIVATE;
    if (g_test && cmd == SW_SHOWMAXIMIZED) cmd = SW_SHOWNOACTIVATE;
    return o_ShowWindow(h, cmd);
}
static BOOL WINAPI h_SetWindowPos(HWND h, HWND after, int x, int y, int cx, int cy, UINT fl)
{
    if (g_test && h == g_mainwnd) {
        if (!(fl & SWP_NOMOVE)) { x = g_tx; y = g_ty; }
        fl |= SWP_NOACTIVATE;
        if (after == HWND_TOP || after == HWND_TOPMOST) fl |= SWP_NOZORDER;
    }
    return o_SetWindowPos(h, after, x, y, cx, cy, fl);
}
static BOOL WINAPI h_MoveWindow(HWND h, int x, int y, int cx, int cy, BOOL rp)
{
    if (g_test && h == g_mainwnd) { x = g_tx; y = g_ty; }
    return o_MoveWindow(h, x, y, cx, cy, rp);
}
/* test mode: the virtual cursor lies over the (off-screen) game window */
static HWND WINAPI h_WindowFromPoint(POINT pt)
{
    if (g_test && g_mainwnd) {
        RECT r;
        if (GetWindowRect(g_mainwnd, &r) && PtInRect(&r, pt)) return g_mainwnd;
    }
    return o_WindowFromPoint(pt);
}
/* test mode: the game's own cursor moves (choice auto-move etc.) go to the virtual cursor,
 * never to the player's real mouse */
static BOOL WINAPI h_SetCursorPos(int x, int y)
{
    if (g_test) {
        if (g_shm && g_mainwnd) {
            POINT q;
            q.x = x; q.y = y;
            ScreenToClient(g_mainwnd, &q);
            g_shm->x = q.x; g_shm->y = q.y; g_shm->valid = 1;
            InterlockedIncrement(&g_shm->seq);
        }
        return TRUE;
    }
    return o_SetCursorPos(x, y);
}
static BOOL WINAPI h_GetCursorPos(LPPOINT p)
{
    if (g_test && g_shm && g_shm->valid && g_mainwnd && p) {
        POINT q;
        q.x = g_shm->x; q.y = g_shm->y;
        ClientToScreen(g_mainwnd, &q);
        *p = q;
        return TRUE;
    }
    return o_GetCursorPos(p);
}

/* ------------------------------------------------------------------ exe resources */
#pragma pack(push, 1)
typedef struct { DWORD magic, version, rva, vsize, before_len; unsigned __int64 before_fnv; DWORD after_len, new_dir_size, new_vsize; } RSRC_HDR;
#pragma pack(pop)

static unsigned __int64 fnv64(const BYTE *p, DWORD n)
{
    unsigned __int64 h = 1469598103934665603ULL;
    DWORD i;
    for (i = 0; i < n; i++) { h ^= p[i]; h *= 1099511628211ULL; }
    return h;
}

static void apply_rsrc(void)
{
    WCHAR path[MAX_PATH];
    HANDLE f;
    DWORD sz, got, old;
    BYTE *buf, *base = (BYTE *)GetModuleHandleW(NULL);
    RSRC_HDR *hd;
    IMAGE_NT_HEADERS32 *nt;
    IMAGE_SECTION_HEADER *sec;
    IMAGE_DATA_DIRECTORY *dd;
    int i;
    lstrcpyW(path, g_kodir); lstrcatW(path, L"exe_rsrc.bin");
    f = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    if (f == INVALID_HANDLE_VALUE) { logw(L"rsrc: no file"); return; }
    sz = GetFileSize(f, NULL);
    buf = (BYTE *)HeapAlloc(GetProcessHeap(), 0, sz);
    if (!buf || !ReadFile(f, buf, sz, &got, NULL) || got != sz) { CloseHandle(f); return; }
    CloseHandle(f);
    hd = (RSRC_HDR *)buf;
    if (hd->magic != 0x53524B49 || sizeof(RSRC_HDR) + hd->after_len != sz) { logw(L"rsrc: bad file"); return; }
    nt = (IMAGE_NT_HEADERS32 *)(base + ((IMAGE_DOS_HEADER *)base)->e_lfanew);
    dd = &nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_RESOURCE];
    sec = IMAGE_FIRST_SECTION(nt);
    for (i = 0; i < nt->FileHeader.NumberOfSections; i++, sec++)
        if (sec->VirtualAddress == hd->rva) break;
    if (i == nt->FileHeader.NumberOfSections || dd->VirtualAddress != hd->rva || sec->Misc.VirtualSize != hd->vsize) { logw(L"rsrc: layout differs, skipped"); return; }
    if (fnv64(base + hd->rva, hd->before_len) != hd->before_fnv) { logw(L"rsrc: original differs, skipped"); return; }
    if (hd->after_len > ((hd->vsize + 0xFFF) & ~0xFFF)) { logw(L"rsrc: too big"); return; }
    if (!VirtualProtect(base + hd->rva, hd->after_len, PAGE_READWRITE, &old)) return;
    CopyMemory(base + hd->rva, buf + sizeof(RSRC_HDR), hd->after_len);
    VirtualProtect(base + hd->rva, hd->after_len, PAGE_READONLY, &old);
    if (VirtualProtect(nt, 0x1000, PAGE_READWRITE, &old)) {
        dd->Size = hd->new_dir_size;
        sec->Misc.VirtualSize = hd->new_vsize;
        VirtualProtect(nt, 0x1000, old, &old);
    }
    g_rsrc_state = 1;
    logw(L"rsrc: Korean resources applied (%u bytes)", hd->after_len);
}

static void ensure_rsrc(void)
{
    if (g_rsrc_state || !g_ko) return;
    EnterCriticalSection(&g_cs);
    if (!g_rsrc_state) { g_rsrc_state = -1; apply_rsrc(); }
    LeaveCriticalSection(&g_cs);
}

static INT_PTR WINAPI h_DialogBoxParamA(HINSTANCE i, LPCSTR t, HWND p, DLGPROC f, LPARAM l) { ensure_rsrc(); return o_DialogBoxParamA(i, t, p, f, l); }
static HWND WINAPI h_CreateDialogParamA(HINSTANCE i, LPCSTR t, HWND p, DLGPROC f, LPARAM l) { ensure_rsrc(); return o_CreateDialogParamA(i, t, p, f, l); }
static HMENU WINAPI h_LoadMenuA(HINSTANCE i, LPCSTR n) { ensure_rsrc(); return o_LoadMenuA(i, n); }

/* ------------------------------------------------------------------ IAT */
static int hook_in(BYTE *base, const char *dll, const char *fn, void *nf, void **orig)
{
    IMAGE_NT_HEADERS32 *nt = (IMAGE_NT_HEADERS32 *)(base + ((IMAGE_DOS_HEADER *)base)->e_lfanew);
    IMAGE_DATA_DIRECTORY *dd = &nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
    IMAGE_IMPORT_DESCRIPTOR *imp = (IMAGE_IMPORT_DESCRIPTOR *)(base + dd->VirtualAddress);
    HMODULE m = GetModuleHandleA(dll);
    FARPROC target = m ? GetProcAddress(m, fn) : NULL;
    int n = 0;
    if (!dd->VirtualAddress) return 0;
    for (; imp->Name; imp++) {
        IMAGE_THUNK_DATA32 *ft, *ot;
        DWORD k;
        if (lstrcmpiA((char *)(base + imp->Name), dll)) continue;
        ft = (IMAGE_THUNK_DATA32 *)(base + imp->FirstThunk);
        ot = imp->OriginalFirstThunk ? (IMAGE_THUNK_DATA32 *)(base + imp->OriginalFirstThunk) : NULL;
        for (k = 0; ft[k].u1.Function; k++) {
            int hit = 0;
            if (ot && !(ot[k].u1.Ordinal & IMAGE_ORDINAL_FLAG32)) {
                IMAGE_IMPORT_BY_NAME *ib = (IMAGE_IMPORT_BY_NAME *)(base + ot[k].u1.AddressOfData);
                hit = !lstrcmpA((char *)ib->Name, fn);
            }
            if (!hit && target && (FARPROC)(ULONG_PTR)ft[k].u1.Function == target) hit = 1;
            if (hit) {
                DWORD old;
                if (VirtualProtect(&ft[k], 4, PAGE_READWRITE, &old)) {
                    if (!*orig) *orig = (void *)(ULONG_PTR)ft[k].u1.Function;
                    ft[k].u1.Function = (DWORD)(ULONG_PTR)nf;
                    VirtualProtect(&ft[k], 4, old, &old);
                    n++;
                }
            }
        }
    }
    if (!*orig && target) *orig = (void *)target;
    return n;
}

static int hook(const char *dll, const char *fn, void *nf, void **orig)
{
    return hook_in((BYTE *)GetModuleHandleW(NULL), dll, fn, nf, orig);
}

/* ------------------------------------------------------------------ test-only sound probe (11-08)
 * The CG gallery showed a voice caption while the player heard no voice. Test runs log what the engine does
 * with its DirectSound buffers (DSOUND.dll is delay-loaded: DirectSoundCreate8 = ordinal 11) - created, played,
 * stopped, the volume asked for, and how loud the data written into them is - and every buffer is kept at the
 * minimum volume whatever the engine asks, so a test never makes a sound. Log lines start with "snd". */
typedef struct { WORD tag, ch; DWORD rate, avg; WORD align, bits, cb; } SP_WFX;
typedef struct { DWORD size, flags, bytes, res; SP_WFX *fmt; GUID alg; } SP_DESC;
#define SP_PRIMARY 0x00000001u
#define SP_CTRLVOLUME 0x00000080u
#define SP_VOLMIN (-10000)
#define SP_MAX 1024
typedef HRESULT (WINAPI *SP_QI_t)(void *, const GUID *, void **);
typedef ULONG (WINAPI *SP_REL_t)(void *);
typedef HRESULT (WINAPI *SP_DSC8_t)(const GUID *, void **, void *);
typedef HRESULT (WINAPI *SP_CREATE_t)(void *, const SP_DESC *, void **, void *);
typedef HRESULT (WINAPI *SP_DUP_t)(void *, void *, void **);
typedef HRESULT (WINAPI *SP_PLAY_t)(void *, DWORD, DWORD, DWORD);
typedef HRESULT (WINAPI *SP_STOP_t)(void *);
typedef HRESULT (WINAPI *SP_VOL_t)(void *, LONG);
typedef HRESULT (WINAPI *SP_UNLOCK_t)(void *, void *, DWORD, void *, DWORD);
typedef FARPROC (WINAPI *GetProcAddress_t)(HMODULE, LPCSTR);
static GetProcAddress_t o_GetProcAddress;
static SP_DSC8_t o_DirectSoundCreate8;
static SP_CREATE_t o_SP_Create;
static SP_DUP_t o_SP_Dup;
typedef struct { void **vt; SP_PLAY_t play; SP_STOP_t stop; SP_VOL_t vol; SP_UNLOCK_t unlock; } SPVT;
static SPVT g_spvt[8];
static int g_nspvt;
static struct { void *p; DWORD ms, t0, n, peak; WORD ch, bits; LONG vol; unsigned __int64 sum; } g_sp[SP_MAX];
static int g_nsp, g_spnext;
static DWORD g_sp_t0;
static const GUID SP_IID_DSB8 = {0x6825a449, 0x7524, 0x4d82, {0x92, 0x0f, 0x50, 0xe3, 0x6a, 0xb3, 0xab, 0x1e}};

static DWORD sp_now(void) { return GetTickCount(); }   /* the system tick, so a test tool can line its own steps up */

static SPVT *sp_vt(void *b)
{
    void **vt = *(void ***)b;
    int i;
    for (i = 0; i < g_nspvt; i++) if (g_spvt[i].vt == vt) return &g_spvt[i];
    return NULL;
}

static int sp_id(void *b)
{
    int i;
    for (i = 0; i < g_nsp; i++) if (g_sp[i].p == b) return i;
    return -1;
}

static void sp_flush(int i, const WCHAR *why)
{
    if (i < 0 || !g_sp[i].n) return;
    logw(L"snd %u data #%d %s samples=%u avg=%u peak=%u", sp_now(), i, why, g_sp[i].n, (DWORD)(g_sp[i].sum / g_sp[i].n), g_sp[i].peak);
    g_sp[i].n = 0; g_sp[i].sum = 0; g_sp[i].peak = 0; g_sp[i].t0 = GetTickCount();
}

static HRESULT WINAPI h_SP_Play(void *b, DWORD r, DWORD p, DWORD fl)
{
    SPVT *v = sp_vt(b);
    int i;
    EnterCriticalSection(&g_cs);
    i = sp_id(b);
    sp_flush(i, L"before-play");
    logw(L"snd %u play #%d loop=%u ms=%u vol=%d", sp_now(), i, fl & 1, i >= 0 ? g_sp[i].ms : 0, i >= 0 ? g_sp[i].vol : 0);
    LeaveCriticalSection(&g_cs);
    return v ? v->play(b, r, p, fl) : E_FAIL;
}

static HRESULT WINAPI h_SP_Stop(void *b)
{
    SPVT *v = sp_vt(b);
    int i;
    EnterCriticalSection(&g_cs);
    i = sp_id(b);
    sp_flush(i, L"before-stop");
    logw(L"snd %u stop #%d", sp_now(), i);
    LeaveCriticalSection(&g_cs);
    return v ? v->stop(b) : E_FAIL;
}

static HRESULT WINAPI h_SP_Vol(void *b, LONG vol)
{
    SPVT *v = sp_vt(b);
    int i;
    EnterCriticalSection(&g_cs);
    i = sp_id(b);
    if (i >= 0 && g_sp[i].vol != vol) { g_sp[i].vol = vol; logw(L"snd %u vol #%d %d", sp_now(), i, vol); }
    LeaveCriticalSection(&g_cs);
    return v ? v->vol(b, SP_VOLMIN) : E_FAIL;   /* asked for vol, kept silent */
}

static void sp_add(int i, const void *p, DWORD n)
{
    const short *s = (const short *)p;
    DWORD k;
    if (!p || g_sp[i].bits != 16) return;
    for (k = 0; k < n / 2; k++) {
        DWORD a = s[k] < 0 ? (DWORD)(-(int)s[k]) : (DWORD)s[k];
        g_sp[i].sum += a;
        if (a > g_sp[i].peak) g_sp[i].peak = a;
    }
    g_sp[i].n += n / 2;
}

static HRESULT WINAPI h_SP_Unlock(void *b, void *p1, DWORD n1, void *p2, DWORD n2)
{
    SPVT *v = sp_vt(b);
    int i;
    EnterCriticalSection(&g_cs);
    i = sp_id(b);
    if (i >= 0) {
        sp_add(i, p1, n1);
        sp_add(i, p2, n2);
        if (GetTickCount() - g_sp[i].t0 >= 250) sp_flush(i, L"written");
    }
    LeaveCriticalSection(&g_cs);
    return v ? v->unlock(b, p1, n1, p2, n2) : E_FAIL;
}

static void sp_patch_slot(void **slot, void *nf)
{
    DWORD old;
    if (VirtualProtect(slot, sizeof(void *), PAGE_EXECUTE_READWRITE, &old)) {
        *slot = nf;
        VirtualProtect(slot, sizeof(void *), old, &old);
    }
}

/* patch a buffer vtable once (Play 12, SetVolume 15, Stop 18, Unlock 19), keeping its own originals */
static SPVT *sp_patch(void *b)
{
    void **vt = *(void ***)b;
    SPVT *v = sp_vt(b);
    if (v || g_nspvt >= 8) return v;
    v = &g_spvt[g_nspvt++];
    v->vt = vt;
    v->play = (SP_PLAY_t)vt[12]; v->vol = (SP_VOL_t)vt[15]; v->stop = (SP_STOP_t)vt[18]; v->unlock = (SP_UNLOCK_t)vt[19];
    sp_patch_slot(&vt[12], (void *)h_SP_Play);
    sp_patch_slot(&vt[15], (void *)h_SP_Vol);
    sp_patch_slot(&vt[18], (void *)h_SP_Stop);
    sp_patch_slot(&vt[19], (void *)h_SP_Unlock);
    logw(L"snd probe: buffer vtable %p patched", vt);
    return v;
}

/* a new secondary buffer (or duplicate): table entry, patched vtable, minimum volume - also for the
 * IDirectSoundBuffer8 face of it when that is another pointer */
static void sp_new(void *b, WORD ch, WORD bits, DWORD rate, DWORD bytes, DWORD ms, int from)
{
    void *b8 = NULL;
    int k;
    for (k = 0; k < 2; k++) {
        void *x = k ? b8 : b;
        SPVT *v;
        int i;
        if (!x || (k && x == b)) continue;
        EnterCriticalSection(&g_cs);
        v = sp_patch(x);
        i = sp_id(x);
        if (i < 0) {
            if (g_nsp < SP_MAX) i = g_nsp++;
            else i = g_spnext++ % SP_MAX;
        }
        memset(&g_sp[i], 0, sizeof(g_sp[i]));
        g_sp[i].p = x; g_sp[i].t0 = GetTickCount(); g_sp[i].vol = 1;
        g_sp[i].ch = ch; g_sp[i].bits = bits; g_sp[i].ms = ms;
        logw(L"snd %u new #%d%s from=%d bytes=%u fmt=%u/%u/%u ms=%u", sp_now(), i, k ? L" (8)" : L"", from, bytes, ch, rate, bits, ms);
        LeaveCriticalSection(&g_cs);
        if (v) v->vol(x, SP_VOLMIN);
        if (!k) ((SP_QI_t)(*(void ***)b)[0])(b, &SP_IID_DSB8, &b8);
    }
    if (b8) ((SP_REL_t)(*(void ***)b8)[2])(b8);
}

static HRESULT WINAPI h_SP_Create(void *ds, const SP_DESC *d, void **pp, void *u)
{
    SP_DESC c;
    HRESULT hr;
    int primary = d && (d->flags & SP_PRIMARY);
    if (d && !primary) {
        memset(&c, 0, sizeof(c));
        memcpy(&c, d, d->size < sizeof(c) ? d->size : sizeof(c));
        c.flags |= SP_CTRLVOLUME;
        d = &c;
    }
    hr = o_SP_Create(ds, d, pp, u);
    if (SUCCEEDED(hr) && pp && *pp && d && !primary) {
        const SP_WFX *f = d->fmt;
        sp_new(*pp, f ? f->ch : 0, f ? f->bits : 0, f ? f->rate : 0, d->bytes,
               f && f->avg ? (DWORD)((unsigned __int64)d->bytes * 1000 / f->avg) : 0, -1);
    } else if (!SUCCEEDED(hr)) logw(L"snd %u create failed %x", sp_now(), hr);
    return hr;
}

static HRESULT WINAPI h_SP_Dup(void *ds, void *src, void **pp)
{
    HRESULT hr = o_SP_Dup(ds, src, pp);
    if (SUCCEEDED(hr) && pp && *pp) {
        int s;
        WORD ch = 0, bits = 0;
        DWORD ms = 0;
        EnterCriticalSection(&g_cs);
        s = sp_id(src);
        if (s >= 0) { ch = g_sp[s].ch; bits = g_sp[s].bits; ms = g_sp[s].ms; }
        LeaveCriticalSection(&g_cs);
        sp_new(*pp, ch, bits, 0, 0, ms, s);
    }
    return hr;
}

static HRESULT WINAPI h_DirectSoundCreate8(const GUID *g, void **pp, void *u)
{
    HRESULT hr = o_DirectSoundCreate8(g, pp, u);
    if (SUCCEEDED(hr) && pp && *pp) {
        void **vt = *(void ***)*pp;
        if (!o_SP_Create) { o_SP_Create = (SP_CREATE_t)vt[3]; sp_patch_slot(&vt[3], (void *)h_SP_Create); }
        if (!o_SP_Dup) { o_SP_Dup = (SP_DUP_t)vt[5]; sp_patch_slot(&vt[5], (void *)h_SP_Dup); }
        g_sp_t0 = GetTickCount();
        logw(L"snd probe on: device %p", *pp);
    }
    return hr;
}

static FARPROC WINAPI h_GetProcAddress(HMODULE m, LPCSTR name)
{
    FARPROC f = o_GetProcAddress(m, name);
    if (g_test && f && m && m == GetModuleHandleA("dsound.dll") &&
        ((ULONG_PTR)name == 11 || (HIWORD((ULONG_PTR)name) && !lstrcmpA(name, "DirectSoundCreate8")))) {
        o_DirectSoundCreate8 = (SP_DSC8_t)f;
        return (FARPROC)h_DirectSoundCreate8;
    }
    return f;
}

/* cs2conf.dll (Japanese build: ko\cs2conf.dll, the whole settings dialog; English build: the game's own plugin, the
 * general/display/system information pages around the exe's input/voice pages) gets the
 * donor-string handling - only donor strings are changed there - and on the English build the list view text */
static void hook_conf(HMODULE m)
{
    int n = 0;
    if (!m || !g_ko) return;
    n += hook_in((BYTE *)m, "user32.dll", "SendMessageA", (void *)h_SendMessageA, (void **)&o_SendMessageA);
    n += hook_in((BYTE *)m, "user32.dll", "SendDlgItemMessageA", (void *)h_SendDlgItemMessageA, (void **)&o_SendDlgItemMessageA);
    n += hook_in((BYTE *)m, "user32.dll", "SetDlgItemTextA", (void *)h_SetDlgItemTextA, (void **)&o_SetDlgItemTextA);
    if (g_test) n += hook_in((BYTE *)m, "user32.dll", "MessageBoxA", (void *)h_MessageBoxA, (void **)&o_MessageBoxA);   /* answered */
    logw(L"cs2conf %p: dialog text hooks=%d", m, n);
}

#define HOOK(dll, name) hooked += hook(dll, #name, (void *)h_##name, (void **)&o_##name)

static void init(HMODULE self)
{
    WCHAR exe[MAX_PATH], logp[MAX_PATH], env[8];
    int i, hooked = 0;
    InitializeCriticalSection(&g_cs);
    {
        BYTE *b = (BYTE *)GetModuleHandleW(NULL);
        IMAGE_NT_HEADERS32 *nt = (IMAGE_NT_HEADERS32 *)(b + ((IMAGE_DOS_HEADER *)b)->e_lfanew);
        g_exe_lo = b; g_exe_hi = b + nt->OptionalHeader.SizeOfImage;
    }
    GetModuleFileNameW(NULL, exe, MAX_PATH);
    lstrcpyW(g_gamedir, exe);
    for (i = lstrlenW(g_gamedir); i > 0 && g_gamedir[i - 1] != L'\\'; i--) ;
    g_gamedir[i] = 0;
    lstrcpyW(g_kodir, g_gamedir); lstrcatW(g_kodir, L"ko\\");
    (void)env;
    read_test_flag();
    lstrcpyW(logp, g_gamedir); lstrcatW(logp, L"island-ko.log");
    g_log = CreateFileW(logp, GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, CREATE_ALWAYS, 0, NULL);
    if (g_log != INVALID_HANDLE_VALUE) { DWORD w; WriteFile(g_log, "\xEF\xBB\xBF", 3, &w, NULL); }
    g_edition = detect_edition();
    read_ini();
    check_install_build();
    read_native_cp();
    load_pua();
    if (g_ko) {
        load_msgs();
        lstrcpyW(g_font, g_kodir); lstrcatW(g_font, L"ISLAND-KO.ttf");
        g_font_ok = AddFontResourceExW(g_font, FR_PRIVATE, 0);
    }
    if (g_test) {
        HANDLE m = CreateFileMappingW(INVALID_HANDLE_VALUE, NULL, PAGE_READWRITE, 0, sizeof(TEST_SHM), L"Local\\IslandKoTest");
        if (m) g_shm = (TEST_SHM *)MapViewOfFile(m, FILE_MAP_ALL_ACCESS, 0, 0, sizeof(TEST_SHM));
    }
    HOOK("kernel32.dll", CreateFileA);
    HOOK("kernel32.dll", CreateFileW);
    HOOK("kernel32.dll", LoadLibraryA);
    HOOK("kernel32.dll", LoadLibraryW);
    HOOK("kernel32.dll", LoadLibraryExA);
    HOOK("kernel32.dll", LoadLibraryExW);
    HOOK("user32.dll", MessageBoxA);
    HOOK("user32.dll", SetWindowTextA);
    HOOK("user32.dll", CreateWindowExA);
    HOOK("user32.dll", DialogBoxParamA);
    HOOK("user32.dll", CreateDialogParamA);
    HOOK("user32.dll", LoadMenuA);
    HOOK("user32.dll", SendMessageA);
    HOOK("user32.dll", SendDlgItemMessageA);
    HOOK("user32.dll", SetDlgItemTextA);
    HOOK("user32.dll", GetWindowTextA);
    HOOK("user32.dll", GetDlgItemTextA);
    HOOK("gdi32.dll", CreateFontIndirectA);
    HOOK("shell32.dll", ShellExecuteA);       /* 「처음 상태로 되돌리기」 requests (islandko-reset|restore) */
    HOOK("shell32.dll", ShellExecuteExA);
    if (g_test) {
        HOOK("user32.dll", GetForegroundWindow);
        HOOK("user32.dll", SetForegroundWindow);
        HOOK("user32.dll", SetActiveWindow);
        HOOK("user32.dll", SetFocus);
        HOOK("user32.dll", ShowWindow);
        HOOK("user32.dll", GetCursorPos);
        HOOK("user32.dll", SetWindowPos);
        HOOK("user32.dll", MoveWindow);
        HOOK("user32.dll", WindowFromPoint);
        HOOK("user32.dll", SetCursorPos);
        HOOK("user32.dll", AttachThreadInput);
        HOOK("kernel32.dll", CreateMutexA);
        HOOK("kernel32.dll", GetProcAddress);   /* sound probe, keeps the test silent */
    }
    if (!o_LoadLibraryExW) o_LoadLibraryExW = LoadLibraryExW;
    if (!o_CreateFileW) o_CreateFileW = CreateFileW;
    logw(L"island-ko 1.3 build=%s steam=%d exe=%u.%u.%u.%u lang=%s native_cp=%u test=%d hooks=%d font=%d map=%d msgs=%d game=%s",
         g_edition == 2 ? L"en" : L"ja", g_steam, HIWORD(g_exever_ms), LOWORD(g_exever_ms), HIWORD(g_exever_ls), LOWORD(g_exever_ls),
         g_ko ? L"ko" : L"original", g_native_cp, g_test, hooked, g_font_ok, g_nmap, g_nmsgs, g_gamedir);
    if (g_ko_mismatch)
        logw(L"ko\\ was installed for the %s build, the game folder now holds the %s build (Steam game language changed?) - running as the original game until the patch is installed again",
             g_edition == 2 ? L"Japanese" : L"English", g_edition == 2 ? L"English" : L"Japanese");
}

BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID r)
{
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(h);
        load_real();
        init(h);
    } else if (reason == DLL_PROCESS_DETACH && !r) {
        if (g_font_ok) RemoveFontResourceExW(g_font, FR_PRIVATE, 0);
    }
    return TRUE;
}
