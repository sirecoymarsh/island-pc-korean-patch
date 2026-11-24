/* island-ko build-detection probe (no game): imports version.dll like ISLAND.exe, so the proxy
 * from this exe's folder loads, runs its init (writes island-ko.log here) and the probe exits.
 * Variants (build_edtest.cmd):
 *   /DBIND            a section named .bind (stands in for SteamStub)
 *   edtest_ver68.res  version resource 2.6.1.68 (Japanese build)
 *   edtest_ver80.res  version resource 2.6.1.80 (English build) */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#pragma comment(lib, "version.lib")

#ifdef BIND
#pragma section(".bind", read)
__declspec(allocate(".bind")) const char g_bind[] = "edtest stand-in for SteamStub";
static const char *volatile g_keep = g_bind;   /* keeps the section through /OPT:REF */
#endif

int main(void)
{
    DWORD dummy;
    DWORD sz = GetFileVersionInfoSizeA("kernel32.dll", &dummy);
#ifdef BIND
    if (g_keep[0] == 0) return 3;
#endif
    return sz != 0 ? 0 : 2;
}
