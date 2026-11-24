/* Stand-alone check of version.dll (island-ko) without the game: imports the same APIs as
 * ISLAND.exe, so the proxy hooks this exe's IAT. Run from the test copy folder. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#pragma comment(lib, "version.lib")
#pragma comment(lib, "user32.lib")
#pragma comment(lib, "gdi32.lib")

int main(void)
{
    char buf[512];
    DWORD dummy, sz;
    HANDLE h;
    HMODULE m;
    HDC dc;
    HFONT f;
    LOGFONTA lf;
    GLYPHMETRICS gm;
    MAT2 mat = { {0, 1}, {0, 0}, {0, 0}, {0, 1} };
    int r;
    /* force version.dll import (the proxy) */
    sz = GetFileVersionInfoSizeA("kernel32.dll", &dummy);
    printf("GetFileVersionInfoSizeA(kernel32)=%lu\n", sz);
    h = CreateFileA("scene.int", GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    printf("CreateFileA(scene.int) size=%lu\n", h == INVALID_HANDLE_VALUE ? 0 : GetFileSize(h, NULL));
    if (h != INVALID_HANDLE_VALUE) CloseHandle(h);
    h = CreateFileA("bgm.int", GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    printf("CreateFileA(bgm.int) size=%lu\n", h == INVALID_HANDLE_VALUE ? 0 : GetFileSize(h, NULL));
    if (h != INVALID_HANDLE_VALUE) CloseHandle(h);
    h = CreateFileA("config\\startup.xml", GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    printf("CreateFileA(config\\startup.xml) size=%lu\n", h == INVALID_HANDLE_VALUE ? 0 : GetFileSize(h, NULL));
    if (h != INVALID_HANDLE_VALUE) CloseHandle(h);
    m = LoadLibraryA("cs2conf.dll");
    GetModuleFileNameA(m, buf, sizeof(buf));
    printf("LoadLibraryA(cs2conf.dll) -> %s\n", m ? buf : "(null)");
    dc = CreateCompatibleDC(NULL);
    ZeroMemory(&lf, sizeof(lf));
    lf.lfHeight = -26; lf.lfWeight = 400; lf.lfCharSet = SHIFTJIS_CHARSET; lf.lfQuality = ANTIALIASED_QUALITY;
    lstrcpyA(lf.lfFaceName, "\x82\x6c\x82\x72 \x83\x53\x83\x56\x83\x62\x83\x4e"); /* MS Gothic in CP932 */
    f = CreateFontIndirectA(&lf);
    SelectObject(dc, f);
    GetTextFaceA(dc, sizeof(buf), buf);
    printf("font face selected: %s\n", buf);
    r = (int)GetGlyphOutlineA(dc, 0xF041, GGO_GRAY8_BITMAP, &gm, 0, NULL, &mat);
    printf("GetGlyphOutlineA(F041) bytes=%d box=%ux%u inc=%d\n", r, gm.gmBlackBoxX, gm.gmBlackBoxY, gm.gmCellIncX);
    r = MessageBoxA(NULL, "ISLAND \x82\xf0\x8f\x49\x97\xb9\x82\xb5\x82\xc4\x82\xe6\x82\xeb\x82\xb5\x82\xa2\x82\xc5\x82\xb7\x82\xa9\x81\x48", "\x8f\x49\x97\xb9", MB_YESNO);
    printf("MessageBoxA returned %d\n", r);
    return 0;
}
