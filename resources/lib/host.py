# -*- coding: utf-8 -*-
"""Ejecución de comandos en el host (soporta Kodi dentro de Flatpak) y gestión del navegador."""
import os
import shlex
import subprocess

DEVNULL = subprocess.DEVNULL

NATIVE_CANDIDATES = [
    "google-chrome-stable", "google-chrome", "chromium", "chromium-browser",
    "microsoft-edge-stable", "microsoft-edge", "brave-browser",
]
FLATPAK_CANDIDATES = [
    "com.google.Chrome", "org.chromium.Chromium", "com.microsoft.Edge", "com.brave.Browser",
]


def in_flatpak():
    return os.path.exists("/.flatpak-info")


def wrap(cmd):
    """Si Kodi corre dentro de Flatpak, ejecuta en el host (requiere permiso org.freedesktop.Flatpak)."""
    if in_flatpak():
        return ["flatpak-spawn", "--host"] + list(cmd)
    return list(cmd)


def run(cmd, timeout=None):
    return subprocess.run(wrap(cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)


def host_home():
    try:
        r = run(["sh", "-c", "printf %s \"$HOME\""], timeout=10)
        out = r.stdout.decode("utf-8", "replace").strip()
        if out:
            return out
    except Exception:
        pass
    return os.path.expanduser("~")


def _which(name):
    try:
        return run(["sh", "-c", "command -v " + shlex.quote(name)], timeout=10).returncode == 0
    except Exception:
        return False


def _flatpak_apps():
    try:
        r = run(["flatpak", "list", "--app", "--columns=application"], timeout=15)
        return set(r.stdout.decode("utf-8", "replace").split())
    except Exception:
        return set()


def detect_browser(custom_cmd=""):
    """Devuelve (comando:list, tipo:str) con tipo 'native' o 'flatpak'. (None, None) si no hay."""
    custom_cmd = (custom_cmd or "").strip()
    if custom_cmd:
        parts = shlex.split(custom_cmd)
        kind = "flatpak" if parts[:2] == ["flatpak", "run"] else "native"
        return parts, kind
    for c in NATIVE_CANDIDATES:
        if _which(c):
            return [c], "native"
    apps = _flatpak_apps()
    for app in FLATPAK_CANDIDATES:
        if app in apps:
            return ["flatpak", "run", app], "flatpak"
    return None, None


def spawn(cmd):
    return subprocess.Popen(wrap(cmd), stdout=DEVNULL, stderr=DEVNULL)


# ---- minimizar / restaurar la ventana de Kodi (X11) ----
def minimize_kodi():
    import xbmc
    xbmc.executebuiltin("Minimize")


def restore_kodi():
    import xbmc
    # xdotool / wmctrl en el host si existen; si no, nada más que hacer
    for cmd in (
        ["sh", "-c", "xdotool search --class kodi windowmap windowactivate 2>/dev/null"],
        ["sh", "-c", "wmctrl -x -a kodi 2>/dev/null"],
    ):
        try:
            if run(cmd, timeout=10).returncode == 0:
                return
        except Exception:
            pass
    xbmc.executebuiltin("Action(FullScreen)")
