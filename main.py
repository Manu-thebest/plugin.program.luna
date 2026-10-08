# -*- coding: utf-8 -*-
import json
import os
import sys
import time
from urllib.parse import urlencode, parse_qsl

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo("id")
HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 else -1
BASE = "plugin://%s/" % ADDON_ID
PROFILE = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))
CACHE = os.path.join(PROFILE, "games.json")
MANUAL = os.path.join(PROFILE, "manual.json")
DIAG = os.path.join(PROFILE, "last_dom.html")

sys.path.insert(0, os.path.join(xbmcvfs.translatePath(ADDON.getAddonInfo("path")), "resources", "lib"))
import host  # noqa: E402
import scraper  # noqa: E402

L = ADDON.getLocalizedString


def log(msg, level=xbmc.LOGINFO):
    xbmc.log("[%s] %s" % (ADDON_ID, msg), level)


def S(key):
    return ADDON.getSetting(key)


def url_for(**kw):
    return BASE + "?" + urlencode(kw)


# ---------------------------------------------------------------- almacenamiento
def _load(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save(path, data):
    os.makedirs(PROFILE, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- navegador
def browser():
    cmd, kind = host.detect_browser(S("browser_cmd"))
    if not cmd:
        xbmcgui.Dialog().ok("Amazon Luna", L(30112))
    return cmd, kind


def profile_flags(kind):
    p = S("profile_dir").strip()
    if not p:
        if kind == "flatpak":
            return []  # el sandbox no ve rutas arbitrarias: se usa el perfil propio del navegador
        p = host.host_home() + "/.config/kodi-luna-browser"
    return ["--user-data-dir=" + p]


def scan_urls():
    base = S("luna_url").strip().rstrip("/") or "https://luna.amazon.com"
    urls = [base + "/"]
    for u in S("scan_urls").split(";"):
        u = u.strip()
        if u:
            urls.append(u)
    return urls


def dump_dom(cmd, kind, url):
    wait_ms = max(5, int(S("headless_wait") or 20)) * 1000
    args = list(cmd) + profile_flags(kind) + [
        "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--window-size=1920,1080",
        "--user-agent=" + S("user_agent"),
        "--virtual-time-budget=%d" % wait_ms,
        "--dump-dom", url,
    ]
    try:
        r = host.run(args, timeout=wait_ms // 1000 + 60)
        return r.stdout.decode("utf-8", "replace")
    except Exception as e:
        log("dump_dom error: %s" % e, xbmc.LOGERROR)
        return ""


def refresh_library(silent=False):
    cmd, kind = browser()
    if not cmd:
        return None
    prog = xbmcgui.DialogProgressBG()
    prog.create("Amazon Luna", L(30110))
    games, last_html = {}, ""
    urls = scan_urls()
    try:
        for i, u in enumerate(urls):
            prog.update(int(100 * i / len(urls)), message=u)
            html = dump_dom(cmd, kind, u)
            if html:
                last_html = html
                for g in scraper.parse_games(html, u):
                    games.setdefault(g["id"], g)
    finally:
        prog.close()
    try:
        os.makedirs(PROFILE, exist_ok=True)
        with open(DIAG, "w", encoding="utf-8") as f:
            f.write(last_html)
    except Exception:
        pass
    lst = sorted(games.values(), key=lambda g: g["title"].lower())
    if lst:
        _save(CACHE, {"ts": time.time(), "games": lst})
        if not silent:
            xbmcgui.Dialog().notification("Amazon Luna", "%s: %d %s" % (L(30117), len(lst), L(30118)),
                                          xbmcgui.NOTIFICATION_INFO, 3000)
    return lst


def get_games(force=False):
    cache = _load(CACHE, {})
    ttl = int(S("cache_hours") or 24) * 3600
    fresh = cache.get("games") and (time.time() - cache.get("ts", 0) < ttl)
    if force or not fresh:
        new = refresh_library(silent=not force)
        if new:
            return new
    return cache.get("games", [])


# ---------------------------------------------------------------- lanzamiento
def play_game(url, title=""):
    cmd, kind = browser()
    if not cmd:
        return
    mode = S("window_mode") or "app_fullscreen"
    args = list(cmd) + profile_flags(kind) + [
        "--autoplay-policy=no-user-gesture-required", "--no-first-run", "--no-default-browser-check",
    ]
    if mode == "kiosk":
        args += ["--kiosk", url]
    elif mode == "window":
        args += ["--new-window", url]
    else:
        args += ["--app=" + url, "--start-fullscreen"]
    extra = S("extra_flags").strip()
    if extra:
        import shlex
        args += shlex.split(extra)
    run_blocking(args, title)


def run_blocking(args, title=""):
    mon = xbmc.Monitor()
    xbmcgui.Dialog().notification("Amazon Luna", "%s %s" % (L(30119), title), xbmcgui.NOTIFICATION_INFO, 2000)
    minimize = S("minimize_kodi") == "true"
    xbmc.Player().stop()
    try:
        xbmc.audioSuspend()
    except Exception:
        pass
    if minimize:
        host.minimize_kodi()
        mon.waitForAbort(1.0)
    log("Launching: %s" % " ".join(args))
    try:
        p = host.spawn(args)
        while p.poll() is None:
            if mon.waitForAbort(1.0):
                p.terminate()
                break
    except Exception as e:
        log("launch error: %s" % e, xbmc.LOGERROR)
    finally:
        try:
            xbmc.audioResume()
        except Exception:
            pass
        if minimize:
            host.restore_kodi()


# ---------------------------------------------------------------- manuales
def add_manual():
    kb = xbmcgui.Dialog()
    title = kb.input(L(30113))
    if not title:
        return
    url = kb.input(L(30114), defaultt="https://luna.amazon.com/game/")
    if not url:
        return
    data = _load(MANUAL, [])
    data.append({"id": "manual:" + url, "title": title, "url": url, "thumb": "", "manual": True})
    _save(MANUAL, data)
    xbmc.executebuiltin("Container.Refresh")


def remove_manual(gid):
    data = [g for g in _load(MANUAL, []) if g["id"] != gid]
    _save(MANUAL, data)
    xbmc.executebuiltin("Container.Refresh")


def save_diag():
    if not xbmcvfs.exists(DIAG):
        refresh_library()
    xbmcgui.Dialog().ok("Amazon Luna", "%s:\n%s" % (L(30116), DIAG))


# ---------------------------------------------------------------- UI
def add_folder_item(label, **kw):
    li = xbmcgui.ListItem(label=label)
    li.setArt({"icon": "DefaultAddonProgram.png"})
    xbmcplugin.addDirectoryItem(HANDLE, url_for(**kw), li, isFolder=False)


def list_root(force=False):
    xbmcplugin.setContent(HANDLE, "files")
    games = get_games(force=force) + _load(MANUAL, [])
    seen = set()
    for g in sorted(games, key=lambda x: x["title"].lower()):
        if g["id"] in seen:
            continue
        seen.add(g["id"])
        li = xbmcgui.ListItem(label=g["title"])
        art = {"icon": g.get("thumb") or "DefaultGame.png"}
        if g.get("thumb"):
            art.update({"thumb": g["thumb"], "poster": g["thumb"]})
        li.setArt(art)
        li.setInfo("video", {"title": g["title"], "plot": g["url"]})
        li.setProperty("IsPlayable", "false")
        if g.get("manual"):
            li.addContextMenuItems([(L(30115), "RunPlugin(%s)" % url_for(action="remove", id=g["id"]))])
        xbmcplugin.addDirectoryItem(HANDLE, url_for(action="play", url=g["url"], title=g["title"]), li, isFolder=False)
    if not games:
        xbmcgui.Dialog().ok("Amazon Luna", L(30111))
    add_folder_item("[B]%s[/B]" % L(30100), action="refresh")
    add_folder_item(L(30101), action="login")
    add_folder_item(L(30102), action="add")
    add_folder_item(L(30103), action="open")
    add_folder_item(L(30104), action="diag")
    add_folder_item(L(30105), action="settings")
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


def router(params):
    action = params.get("action")
    if action == "play":
        play_game(params["url"], params.get("title", ""))
    elif action == "refresh":
        get_games(force=True)
        xbmc.executebuiltin("Container.Refresh")
    elif action == "login" or action == "open":
        cmd, kind = browser()
        if cmd:
            base = S("luna_url").strip() or "https://luna.amazon.com"
            run_blocking(list(cmd) + profile_flags(kind) + ["--new-window", "--start-maximized", base], "Luna")
            if action == "login":
                get_games(force=True)
                xbmc.executebuiltin("Container.Refresh")
    elif action == "add":
        add_manual()
    elif action == "remove":
        remove_manual(params["id"])
    elif action == "diag":
        save_diag()
    elif action == "settings":
        ADDON.openSettings()
    else:
        list_root()


if __name__ == "__main__":
    router(dict(parse_qsl(sys.argv[2][1:])) if len(sys.argv) > 2 else {})
