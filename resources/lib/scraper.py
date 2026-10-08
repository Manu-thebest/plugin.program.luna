# -*- coding: utf-8 -*-
"""Extracción de la lista de juegos del DOM renderizado de Luna.

Luna no tiene API pública documentada, así que se lee el HTML ya renderizado
(chrome --headless --dump-dom) y se buscan enlaces a páginas de juego (/game/<slug>/<ASIN>).
Si Amazon cambia el marcado, el parser es tolerante: sólo exige el patrón de la URL.
"""
import re
from html.parser import HTMLParser
from urllib.parse import urljoin

GAME_RE = re.compile(r"/game/([^/?#\"'<>\s]+)(?:/([A-Z0-9]{10}))?")
GENERIC = {"play", "jugar", "play now", "learn more", "más información", "mas informacion", ""}


def _clean(t):
    return re.sub(r"\s+", " ", (t or "")).strip()


def _slug_to_title(slug):
    return " ".join(w.capitalize() for w in re.split(r"[-_]+", slug) if w)


class _Parser(HTMLParser):
    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base = base
        self.games = {}
        self._stack = []  # anchors abiertos (dicts)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a":
            href = a.get("href") or ""
            m = GAME_RE.search(href)
            cur = None
            if m:
                cur = {
                    "href": urljoin(self.base, href.split("?")[0].split("#")[0]),
                    "slug": m.group(1), "id": m.group(2) or m.group(1),
                    "aria": _clean(a.get("aria-label")), "title": _clean(a.get("title")),
                    "alt": "", "thumb": "", "text": [],
                }
            self._stack.append(cur)
        elif tag in ("img", "source") and self._stack:
            cur = next((c for c in reversed(self._stack) if c), None)
            if cur is not None:
                if tag == "img" and not cur["alt"]:
                    cur["alt"] = _clean(a.get("alt"))
                src = a.get("src") or a.get("data-src") or ""
                if not src and a.get("srcset"):
                    src = a["srcset"].split(",")[0].strip().split(" ")[0]
                if src and not cur["thumb"] and not src.startswith("data:"):
                    cur["thumb"] = urljoin(self.base, src)

    def handle_data(self, data):
        cur = next((c for c in reversed(self._stack) if c), None)
        if cur is not None and data.strip():
            cur["text"].append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._stack:
            cur = self._stack.pop()
            if cur:
                self._commit(cur)

    def _commit(self, c):
        title = ""
        for cand in (c["aria"], c["alt"], c["title"], _clean(" ".join(c["text"]))):
            if cand and cand.lower() not in GENERIC and len(cand) < 120:
                title = cand
                break
        key = c["id"]
        prev = self.games.get(key)
        if prev:  # mejora título/miniatura si el enlace repetido trae más datos
            if not prev["title"] and title:
                prev["title"] = title
            if not prev["thumb"] and c["thumb"]:
                prev["thumb"] = c["thumb"]
            return
        self.games[key] = {"id": key, "title": title, "url": c["href"], "thumb": c["thumb"], "slug": c["slug"]}


def parse_games(html, base_url):
    p = _Parser(base_url)
    try:
        p.feed(html)
    except Exception:
        pass
    games = p.games
    # Respaldo: URLs de juego sueltas en el HTML (scripts JSON, etc.)
    for m in re.finditer(r"/game/([a-z0-9][a-z0-9\-_]*)/([A-Z0-9]{10})", html):
        slug, gid = m.group(1), m.group(2)
        if gid not in games:
            games[gid] = {"id": gid, "title": "", "url": urljoin(base_url, "/game/%s/%s" % (slug, gid)),
                          "thumb": "", "slug": slug}
    out = []
    for g in games.values():
        if not g["title"]:
            g["title"] = _slug_to_title(g["slug"])
        out.append(g)
    out.sort(key=lambda g: g["title"].lower())
    return out


def looks_logged_out(html):
    h = html.lower()
    return ("ap/signin" in h or "ap_email" in h or "sign in" in h and "luna" in h and "/game/" not in h)
