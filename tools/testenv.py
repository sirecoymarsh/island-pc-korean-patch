"""Test session helpers: wrapper mode switch, preflight checks, log reading."""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gamectl  # noqa: E402

WRAPPER_CFG = os.path.join(HERE, "steam_wrapper.json")
TEST_GAME = gamectl.TEST_GAME
USER_GAME = r"Y:\SteamLibrary\steamapps\common\ISLAND"


def wrapper_mode(test, game=TEST_GAME, extra_env=None):
    cfg = {"mode": "original"}
    if test:
        env = {"ISLANDKO_TEST": "1", "ISLANDKO_TEST_X": "4160", "ISLANDKO_TEST_Y": "200"}
        env.update(extra_env or {})
        cfg = {"mode": "test", "game": game, "env": env}
    json.dump(cfg, open(WRAPPER_CFG, "w", encoding="utf-8"))


def preflight():
    """Refuse to start while any ISLAND.exe is running (the player's game or a stale test)."""
    procs = gamectl.processes()
    if procs:
        raise SystemExit("ISLAND.exe already running: %s" % procs)
    out = subprocess.run(["python", "-I", os.path.join(HERE, "steam_launchopt.py"), "show"], capture_output=True, text=True, encoding="utf-8").stdout
    cur = json.loads(out)["current"]
    if "island-steam-ko" not in cur:
        raise SystemExit("Steam launch option is not the test wrapper; run steam_launchopt.py set-test with Steam closed")


def read_log(game=TEST_GAME):
    p = os.path.join(game, "island-ko.log")
    if not os.path.exists(p):
        return []
    return open(p, encoding="utf-8-sig", errors="replace").read().splitlines()


def start(extra_env=None):
    preflight()
    wrapper_mode(True, extra_env=extra_env)
    gamectl.start_steam_if_needed()
    g = gamectl.launch()
    return g


def finish(g, timeout=30):
    """Normal exit through the game's own close path (message box auto-answered Yes)."""
    if g and g.hwnd:
        g.close()
        t0 = time.time()
        while time.time() - t0 < timeout and g.alive():
            time.sleep(0.5)
    wrapper_mode(False)
    left = [p for p, path in gamectl.processes() if path and TEST_GAME.lower() in path.lower()]
    return left
