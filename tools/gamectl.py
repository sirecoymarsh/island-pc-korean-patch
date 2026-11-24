"""Background control of the ISLAND Steam test copy (with the loader DLL in test mode).

The DLL (ISLANDKO_TEST=1) makes the game think it is the foreground window, keeps it outside
every monitor, never activates it and reads the cursor from shared memory "Local\\IslandKoTest";
so posted messages work without touching the real mouse/keyboard focus.
"""
import ctypes as C
import ctypes.wintypes as W
import os
import subprocess
import time

U = C.WinDLL("user32", use_last_error=True)
G = C.WinDLL("gdi32", use_last_error=True)
K = C.WinDLL("kernel32", use_last_error=True)
U.SetProcessDPIAware()

WM_KEYDOWN, WM_KEYUP, WM_CHAR = 0x100, 0x101, 0x102
WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_LBUTTONUP, WM_RBUTTONDOWN, WM_RBUTTONUP = 0x200, 0x201, 0x202, 0x204, 0x205
WM_MOUSEWHEEL, WM_CLOSE = 0x20A, 0x10
WM_ACTIVATEAPP, WM_ACTIVATE, WM_SETFOCUS, WM_NCACTIVATE = 0x1C, 0x6, 0x7, 0x86

STEAM = r"F:\steam\steam.exe"
TEST_GAME = r"Y:\AI\island-steam-ko\testgame"

U.PostMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
U.SendMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
U.SendMessageW.restype = W.LPARAM
U.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
U.IsWindowVisible.argtypes = [W.HWND]
U.GetClientRect.argtypes = [W.HWND, C.POINTER(W.RECT)]
U.GetWindowRect.argtypes = [W.HWND, C.POINTER(W.RECT)]
U.PrintWindow.argtypes = [W.HWND, W.HDC, W.UINT]
U.GetDC.argtypes = [W.HWND]
U.GetDC.restype = W.HDC
U.ReleaseDC.argtypes = [W.HWND, W.HDC]
U.GetWindowTextW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
U.GetClassNameW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
U.GetForegroundWindow.restype = W.HWND
G.CreateCompatibleDC.argtypes = [W.HDC]
G.CreateCompatibleDC.restype = W.HDC
G.CreateCompatibleBitmap.argtypes = [W.HDC, C.c_int, C.c_int]
G.CreateCompatibleBitmap.restype = W.HBITMAP
G.SelectObject.argtypes = [W.HDC, W.HGDIOBJ]
G.SelectObject.restype = W.HGDIOBJ
G.DeleteObject.argtypes = [W.HGDIOBJ]
G.DeleteDC.argtypes = [W.HDC]
G.GetDIBits.argtypes = [W.HDC, W.HBITMAP, W.UINT, W.UINT, W.LPVOID, W.LPVOID, W.UINT]
K.OpenFileMappingW.argtypes = [W.DWORD, W.BOOL, W.LPCWSTR]
K.OpenFileMappingW.restype = W.HANDLE
K.MapViewOfFile.argtypes = [W.HANDLE, W.DWORD, W.DWORD, W.DWORD, C.c_size_t]
K.MapViewOfFile.restype = W.LPVOID


class TestShm(C.Structure):
    _fields_ = [("x", C.c_long), ("y", C.c_long), ("valid", C.c_long), ("answer", C.c_long), ("seq", C.c_long)]


def lparam(x, y):
    return (y & 0xFFFF) << 16 | (x & 0xFFFF)


def processes(name="ISLAND.exe"):
    """[(pid, exe path)] using tasklist + wmic-free query via PowerShell CIM (native)."""
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "Get-CimInstance Win32_Process -Filter \"Name='%s'\" | ForEach-Object { \"$($_.ProcessId)|$($_.ExecutablePath)\" }" % name],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    res = []
    for line in out.splitlines():
        if "|" in line:
            pid, path = line.split("|", 1)
            res.append((int(pid), path))
    return res


def steam_running():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq steam.exe", "/NH"], capture_output=True, text=True).stdout
    return "steam.exe" in out.lower()


def windows_of(pid):
    found = []
    CB = C.WINFUNCTYPE(C.c_bool, W.HWND, W.LPARAM)

    def cb(h, l):
        p = W.DWORD()
        U.GetWindowThreadProcessId(h, C.byref(p))
        if p.value == pid and U.IsWindowVisible(h):
            cls = C.create_unicode_buffer(128)
            U.GetClassNameW(h, cls, 128)
            found.append((h, cls.value))
        return True
    U.EnumWindows(CB(cb), 0)
    return found


def client_size(hwnd):
    r = W.RECT()
    U.GetClientRect(hwnd, C.byref(r))
    return r.right - r.left, r.bottom - r.top


def capture(hwnd, path=None):
    """PrintWindow(PW_CLIENTONLY|PW_RENDERFULLCONTENT) -> PIL image (and optional PNG)."""
    from PIL import Image
    w, h = client_size(hwnd)
    if w <= 0 or h <= 0:
        return None
    hdc = U.GetDC(hwnd)
    mdc = G.CreateCompatibleDC(hdc)
    bmp = G.CreateCompatibleBitmap(hdc, w, h)
    old = G.SelectObject(mdc, bmp)
    U.PrintWindow(hwnd, mdc, 1 | 2)

    class BIH(C.Structure):
        _fields_ = [("biSize", W.DWORD), ("biWidth", W.LONG), ("biHeight", W.LONG), ("biPlanes", W.WORD), ("biBitCount", W.WORD),
                    ("biCompression", W.DWORD), ("biSizeImage", W.DWORD), ("biXPelsPerMeter", W.LONG), ("biYPelsPerMeter", W.LONG),
                    ("biClrUsed", W.DWORD), ("biClrImportant", W.DWORD)]
    bih = BIH()
    bih.biSize = C.sizeof(BIH); bih.biWidth = w; bih.biHeight = -h; bih.biPlanes = 1; bih.biBitCount = 32
    buf = C.create_string_buffer(w * h * 4)
    G.GetDIBits(mdc, bmp, 0, h, buf, C.byref(bih), 0)
    G.SelectObject(mdc, old); G.DeleteObject(bmp); G.DeleteDC(mdc); U.ReleaseDC(hwnd, hdc)
    img = Image.frombuffer("RGBA", (w, h), buf.raw, "raw", "BGRA", 0, 1).convert("RGB")
    if path:
        img.save(path)
    return img


class Game:
    def __init__(self, pid, hwnd):
        self.pid, self.hwnd = pid, hwnd
        self.shm = None
        m = K.OpenFileMappingW(0xF001F, False, "Local\\IslandKoTest")
        if m:
            p = K.MapViewOfFile(m, 0xF001F, 0, 0, C.sizeof(TestShm))
            if p:
                self.shm = TestShm.from_address(p)

    def alive(self):
        return any(p == self.pid for p, _ in processes())

    def cursor(self, x, y):
        if self.shm:
            self.shm.x, self.shm.y, self.shm.valid = x, y, 1

    def move(self, x, y):
        self.cursor(x, y)
        U.PostMessageW(self.hwnd, WM_MOUSEMOVE, 0, lparam(x, y))

    def click(self, x, y, hold=0.08, settle=0.25):
        self.move(x, y)
        time.sleep(settle)
        U.PostMessageW(self.hwnd, WM_LBUTTONDOWN, 1, lparam(x, y))
        time.sleep(hold)
        U.PostMessageW(self.hwnd, WM_LBUTTONUP, 0, lparam(x, y))

    def rclick(self, x=640, y=360, hold=0.08):
        self.move(x, y)
        time.sleep(0.15)
        U.PostMessageW(self.hwnd, WM_RBUTTONDOWN, 2, lparam(x, y))
        time.sleep(hold)
        U.PostMessageW(self.hwnd, WM_RBUTTONUP, 0, lparam(x, y))

    def key(self, vk, hold=0.06):
        sc = U.MapVirtualKeyW(vk, 0)
        U.PostMessageW(self.hwnd, WM_KEYDOWN, vk, 1 | (sc << 16))
        time.sleep(hold)
        U.PostMessageW(self.hwnd, WM_KEYUP, vk, 1 | (sc << 16) | (3 << 30))

    def key_down(self, vk, repeat=False):
        sc = U.MapVirtualKeyW(vk, 0)
        U.PostMessageW(self.hwnd, WM_KEYDOWN, vk, 1 | (sc << 16) | ((1 << 30) if repeat else 0))

    def key_up(self, vk):
        sc = U.MapVirtualKeyW(vk, 0)
        U.PostMessageW(self.hwnd, WM_KEYUP, vk, 1 | (sc << 16) | (3 << 30))

    def wheel(self, delta, x=640, y=360):
        U.PostMessageW(self.hwnd, WM_MOUSEWHEEL, (delta & 0xFFFF) << 16, lparam(x, y))

    def shot(self, path=None):
        return capture(self.hwnd, path)

    def close(self, answer=6):
        if self.shm:
            self.shm.answer = answer
        U.PostMessageW(self.hwnd, WM_CLOSE, 0, 0)


def gpu_fault_count():
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "(Get-WinEvent -FilterHashtable @{LogName='System';ProviderName='nvlddmkm'} -ErrorAction SilentlyContinue | Measure-Object).Count"],
                         capture_output=True, text=True).stdout.strip()
    return int(out or 0)


def start_steam_if_needed(timeout=90):
    if steam_running():
        return False
    subprocess.Popen([STEAM, "-silent"], close_fds=True)
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(2)
        if steam_running():
            break
    time.sleep(20)  # let it sign in
    return True


def launch(timeout=90):
    """Ask Steam to run app 857450 (the launch option points to our wrapper)."""
    before = {p for p, _ in processes()}
    subprocess.Popen([STEAM, "-applaunch", "857450"], close_fds=True)
    t0 = time.time()
    pid = None
    while time.time() - t0 < timeout:
        for p, path in processes():
            if p not in before and path and os.path.normcase(path).startswith(os.path.normcase(TEST_GAME)):
                pid = p
        if pid:
            break
        time.sleep(1)
    if not pid:
        return None
    t0 = time.time()
    while time.time() - t0 < timeout:
        ws = [w for w in windows_of(pid)]
        big = [w for w in ws if client_size(w[0])[0] >= 640]
        if big:
            return Game(pid, big[0][0])
        time.sleep(0.5)
    return Game(pid, None)
