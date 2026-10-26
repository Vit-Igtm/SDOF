"""
Project Strikers - RPG theme/pixel art.

"""
import math
import random
import pygame

PIXEL = 3                  # one "art pixel" = 3 screen pixels
SCREEN = 900

# ----------------------------------------------------------------------------
# RPG palette
# ----------------------------------------------------------------------------
INK = (30, 20, 28)
SHADOW = (14, 8, 18)
CREAM = (248, 236, 204)
PARCHMENT = (222, 200, 150)
PARCHMENT_DK = (170, 140, 92)
GOLD = (250, 200, 70)
GOLD_DK = (176, 120, 36)
WOOD = (92, 58, 36)
WOOD_LT = (134, 90, 54)
WOOD_DK = (58, 36, 26)
STONE = (74, 76, 94)
STONE_LT = (116, 120, 142)
CRIMSON = (178, 40, 52)
CRIMSON_LT = (232, 84, 84)
EMERALD = (70, 200, 110)
MANA = (80, 140, 240)
VIOLET = (150, 90, 220)
PANEL_FILL = (38, 26, 40)
PANEL_FILL_LT = (54, 38, 54)
GREY = (150, 146, 158)

RARITY_COLORS = {
    "common": (196, 196, 204),
    "uncommon": (96, 206, 108),
    "rare": (86, 156, 255),
    "epic": (194, 106, 244),
    "legendary": (255, 172, 44),
}

# ----------------------------------------------------------------------------
# Fonts 
# ----------------------------------------------------------------------------
BODY_FONTS = "segoeui,arial,helveticaneue,helvetica,liberationsans,dejavusans,sans"
TITLE_FONTS = "georgia,cambria,palatinolinotype,liberationserif,dejavuserif,serif"
_fonts = {}


def font(size, title=False, bold=True):
    key = (size, title, bold)
    if key not in _fonts:
        _fonts[key] = pygame.font.SysFont(TITLE_FONTS if title else BODY_FONTS, size, bold=bold)
    return _fonts[key]


def draw_text(surf, text, pos, size=24, color=CREAM, anchor="center", title=False, shadow=True, bold=True):
    f = font(size, title, bold)
    img = f.render(str(text), True, color)
    rect = img.get_rect()
    setattr(rect, anchor, pos)
    if shadow:
        sh = f.render(str(text), True, SHADOW)
        surf.blit(sh, rect.move(2, 2))
    surf.blit(img, rect)
    return rect


def wrap_text(text, size, max_w, title=False):
    f = font(size, title)
    words, lines, cur = text.split(" "), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if f.size(t)[0] > max_w and cur:
            lines.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


def draw_wrapped(surf, text, center_x, top, max_w, size=20, color=CREAM, gap=4, shadow=True):
    y = top
    for line in wrap_text(text, size, max_w):
        r = draw_text(surf, line, (center_x, y), size, color, "midtop", shadow=shadow)
        y = r.bottom + gap
    return y


# ----------------------------------------------------------------------------
# UI pieces
# ----------------------------------------------------------------------------
def _notch(r, n):
    return [(r.left + n, r.top), (r.right - n, r.top), (r.right - n, r.top + n), (r.right, r.top + n),
            (r.right, r.bottom - n), (r.right - n, r.bottom - n), (r.right - n, r.bottom), (r.left + n, r.bottom),
            (r.left + n, r.bottom - n), (r.left, r.bottom - n), (r.left, r.top + n), (r.left + n, r.top + n)]


def draw_panel(surf, rect, fill=PANEL_FILL, border=GOLD_DK, hi=None, notch=6):
    r = pygame.Rect(rect)
    pygame.draw.polygon(surf, SHADOW, _notch(r, notch))
    pygame.draw.polygon(surf, border, _notch(r.inflate(-4, -4), notch))
    inner = r.inflate(-10, -10)
    pygame.draw.polygon(surf, fill, _notch(inner, max(2, notch - 3)))
    if hi:
        pygame.draw.line(surf, hi, (inner.left + notch, inner.top + 1), (inner.right - notch, inner.top + 1), 2)
    return inner


def draw_button(surf, rect, text, hover=False, disabled=False, size=28, selected=False):
    r = pygame.Rect(rect)
    if disabled:
        fill, border, tc = (48, 40, 48), (88, 80, 92), (130, 124, 134)
    elif selected:
        fill, border, tc = (150, 98, 40), GOLD, CREAM
    elif hover:
        fill, border, tc = WOOD_LT, GOLD, CREAM
    else:
        fill, border, tc = WOOD, GOLD_DK, CREAM
    inner = draw_panel(surf, r, fill, border, hi=(255, 220, 150) if not disabled else None)
    pygame.draw.line(surf, WOOD_DK if not disabled else (30, 26, 30), (inner.left + 4, inner.bottom - 2),
                     (inner.right - 4, inner.bottom - 2), 3)
    draw_text(surf, text, r.center, size, tc, shadow=not disabled)


def draw_bar(surf, rect, frac, fill, back=(32, 22, 34), segs=0):
    r = pygame.Rect(rect)
    frac = max(0.0, min(1.0, frac))
    pygame.draw.rect(surf, SHADOW, r)
    inner = r.inflate(-4, -4)
    pygame.draw.rect(surf, back, inner)
    w = int(inner.w * frac)
    if w > 0:
        pygame.draw.rect(surf, fill, (inner.x, inner.y, w, inner.h))
        light = tuple(min(255, c + 60) for c in fill)
        pygame.draw.rect(surf, light, (inner.x, inner.y, w, max(1, inner.h // 3)))
    if segs:
        for i in range(1, segs):
            x = inner.x + inner.w * i // segs
            pygame.draw.line(surf, SHADOW, (x, inner.y), (x, inner.bottom), 1)
    pygame.draw.rect(surf, GOLD_DK, r, 2)


# ----------------------------------------------------------------------------
# Pixel-snapped drawing helpers
# ----------------------------------------------------------------------------
def snap(v, s=PIXEL):
    return int(v // s) * s


def pixel_ring(surf, cx, cy, r, color, size=PIXEL, density=1.0):
    n = max(8, int(2 * math.pi * r / (size * 1.3) * density))
    for i in range(n):
        a = i / n * 2 * math.pi
        surf.fill(color, (snap(cx + math.cos(a) * r), snap(cy + math.sin(a) * r), size, size))


def pixel_arc(surf, cx, cy, r, a0, a1, color, size=PIXEL, thick=2):
    n = max(6, int(abs(a1 - a0) * r / (size * 0.9)))
    for t in range(thick):
        rr = r + t * size
        for i in range(n + 1):
            a = a0 + (a1 - a0) * i / n
            surf.fill(color, (snap(cx + math.cos(a) * rr), snap(cy + math.sin(a) * rr), size, size))


def pixel_line(surf, x1, y1, x2, y2, color, size=PIXEL):
    d = math.hypot(x2 - x1, y2 - y1)
    n = max(1, int(d / size))
    for i in range(n + 1):
        t = i / n
        surf.fill(color, (snap(x1 + (x2 - x1) * t), snap(y1 + (y2 - y1) * t), size, size))


def pixel_disc(surf, cx, cy, r, color, size=PIXEL):
    rr = int(r // size)
    for gy in range(-rr, rr + 1):
        for gx in range(-rr, rr + 1):
            if gx * gx + gy * gy <= rr * rr:
                surf.fill(color, (snap(cx) + gx * size, snap(cy) + gy * size, size, size))


# ----------------------------------------------------------------------------
# Sprites: left-half character grids, mirrored. '.' = transparent.
# ----------------------------------------------------------------------------
_O = (24, 14, 30)

SPRITE_DEFS = {}


def _def(name, rows, pal, scale=PIXEL):
    p = {"o": _O}
    p.update(pal)
    SPRITE_DEFS[name] = (rows, p, scale)


_def("player", [
    "...ooooo",
    "..ooBBBB",
    ".oBBBBBB",
    ".oBbbbbb",
    ".oBbssss",
    ".oBbsoss",
    ".oBbssss",
    "..oBbbss",
    "..oobbbb",
    ".obbBbbb",
    ".obbbggg",
    "obbbbbgg",
    "obbBbbbb",
    "obbbbbbb",
    ".oobbbbb",
    "..okk..."],
    dict(B=(110, 156, 255), b=(54, 90, 200), s=(252, 212, 172), g=(255, 214, 80), k=(120, 76, 44)))

_def("swarmer", [
    "..o...", "...o..", "..oooo", ".orrrr", ".orrry", "orrrrr", "orRrrr", "orrrrr", ".orrrr", "..o.oo"],
    dict(r=(150, 74, 40), R=(200, 118, 62), y=(255, 226, 80)))

_def("slime", [
    "......", "...ooo", ".ooGGG", "oGhGGG", "oGGwoG", "oGGGGG", "oGGgGG", "oGGGGG", ".ooooo"],
    dict(G=(96, 200, 110), h=(170, 240, 170), g=(60, 150, 82), w=(255, 255, 255)))

_def("crawler", [
    "..o...", ".o.ooo", "o.orrr", "..orRy", ".oorrr", "o.orkk", "..orkk", ".o.orr", "o..ooo"],
    dict(r=(232, 110, 40), R=(255, 162, 62), k=(52, 40, 44), y=(255, 240, 90)))

_def("mortar", [
    "...oooo", ".ooGGGG", "oGGGGGG", "oGyoGGG", "oGGGGGG", "oGGGooo", "oGGoLLL", "oGGoLLL", ".oGGoLL", ".ooGGoo", "..oo.oo"],
    dict(G=(104, 176, 74), L=(196, 255, 84), y=(255, 232, 90)))

_def("sniper", [
    ".ww...", "wwww..", ".www.o", "..wwoo", "....oY", "....oY", ".....o", ".....o", "....oL", "....oL", ".....L"],
    dict(w=(188, 222, 255), Y=(255, 232, 100), L=(190, 255, 90)))

_def("spinner", [
    "...oooo", ".ooSSSS", "oSSSSSS", "oSSoooo", "oSoPPPP", "oSoPPEE", "oSoPPEE", "oSoPPPP", "oSSoooo", "oSSSSSS", ".ooSSSS", "...oooo"],
    dict(S=(122, 126, 152), P=(150, 64, 204), E=(255, 130, 255)))

_def("bearer", [
    "....orr", "..ooSSS", ".oSSSSS", ".oSsooo", ".oSsyyy", ".oSsooo", "oSSSSSS", "oSsSSSS", "oSSSSSS", "oSsSSSS", ".oSSSSS", ".ooSSSS", "..oo.oo"],
    dict(S=(158, 168, 190), s=(104, 112, 136), r=(214, 56, 56), y=(255, 224, 80)))

_def("vortex", [
    "....ooo", "..ooVVV", ".oVVVVV", ".oVVvvv", "oVVvwww", "oVvvwpp", "oVvwppp", "oVvwppp", "oVvvwpp", "oVVvvww", ".oVVvvv", ".oVVVVV", "..ooVVV", "....ooo"],
    dict(V=(140, 80, 210), v=(96, 44, 156), w=(232, 208, 255), p=(255, 130, 226)))

_def("bull", [
    "h.......", "hh......", ".hoBBBBB", ".oBBBBBB", "oBBwoBBB", "oBBBBBBB", "oBBBBBPP", ".oBBBPoP", ".oBBBPPP", "..ooBBBB", "...o.oBB", "....o.oo"],
    dict(B=(158, 100, 62), h=(244, 236, 208), w=(255, 255, 255), P=(222, 140, 130)))

_def("necromancer", [
    "...ooooo", "..oDDDDD", ".oDDDDDD", ".oDDDDDD", ".oDooooo", ".oDosess", ".oDosssS", ".oDooooo",
    "oDDDDDDD", "oDdDDDDD", "oDDDDdDD", "oDDDDDDD", "oDdDDDDD", "oDDDDDDD", "oDDDDDDD", "oDDDDDDD", ".oDDDDDD", "..oooooo"],
    dict(D=(84, 48, 130), d=(124, 80, 178), s=(238, 232, 218), S=(190, 184, 170), e=(120, 255, 150)))

_def("wall_summoner", [
    "...oooooo", "..oSSSSSS", "..oSSSSSS", "..oSoRRRR", "..oSSSSSS", "..oosSSSS", ".oooSSSSS", "ooSSSSSSS",
    "oSSSsSSSS", "oSSSsRRRR", "oSSSSSsSS", "oSsSSSSSS", "ooSSSSSSS", ".oSSooooo", ".oSSo....", ".oSSo....", ".oSSSoooo", ".ooooo..."],
    dict(S=(128, 128, 146), s=(88, 88, 106), R=(90, 236, 255)))

_def("commander", [
    "...o....GG", "....o..GGG", "..ooooooGG", ".oAAAAAAAA", ".oAAyAAAAA", "oAAAAAAAAA", "oAaAAAAaAA", "oAAAAGGAAA",
    "oAAAAAAAAA", "oAaAAAAAAA", "oAAAAAAAAA", ".oAAAAAAAA", ".oAAAAAAAA", "..ooAAAooo", ".o.oo.o.oo", "o..o..o..o"],
    dict(A=(66, 118, 78), a=(106, 176, 108), G=(255, 214, 80), y=(255, 90, 80)))

_def("pod", [
    "..ooo", ".oPPP", "oPPpp", "oPpOO", "oPpOO", "oPPpp", "oPPPP", ".oPPP", "..ooo"],
    dict(P=(120, 150, 70), p=(86, 112, 50), O=(255, 170, 50)), scale=4)

_def("boss", [
    ".........g..g.", ".........ggggg", "........oooooo", ".......oCCCCCC", "......oCCccCCC", "..ww..oCeeeCCC",
    ".wwww.oCeEeCCC", "wwwwwwoCCCCCCC", "wwWwwwooCCooCC", "wwwWwwwoCCCCCC", ".wwwwwwooCCCCC", "..wwwwwoCCccCC",
    "...wwwwoCCOOCC", "....wwooCOOOCC", ".....woCCOOOOC", "......oCCOAAOC", "......oCCOAAOC", "......oCCCOOCC",
    ".......oCCCCCC", "........oCCCCC", ".........ooCCC", "...........ooo"],
    dict(g=(255, 204, 64), C=(92, 72, 126), c=(136, 112, 176), e=(255, 80, 80), E=(255, 226, 226),
         w=(176, 206, 244), W=(232, 246, 255), O=(255, 156, 44), A=(176, 255, 76)), scale=5)

BOSS_RAGE_PAL = dict(C=(160, 44, 54), c=(214, 78, 78), w=(255, 170, 140), W=(255, 230, 210), e=(255, 240, 120))


# ----------------------------------------------------------------------------
# Procedural helper for building the bigger sprites.
# ----------------------------------------------------------------------------
class _Cv:
    def __init__(self, w, h, sym=True):
        self.sym, self.hw, self.H = sym, w, h
        self.W = w * 2 if sym else w
        self.cx = w - 0.5
        self.g = [["."] * self.W for _ in range(h)]

    def px(self, x, y, c):
        x, y = int(x), int(y)
        if 0 <= y < self.H:
            if 0 <= x < self.W:
                self.g[y][x] = c
            if self.sym and 0 <= self.W - 1 - x < self.W:
                self.g[y][self.W - 1 - x] = c

    def get(self, x, y):
        return self.g[y][x] if 0 <= x < self.W and 0 <= y < self.H else "."

    def rect(self, x0, y0, x1, y1, c):
        for y in range(int(y0), int(y1) + 1):
            for x in range(int(x0), int(x1) + 1):
                self.px(x, y, c)

    def ell(self, cx, cy, rx, ry, c):
        for y in range(int(cy - ry) - 1, int(cy + ry) + 2):
            for x in range(int(cx - rx) - 1, int(cx + rx) + 2):
                if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0:
                    self.px(x, y, c)

    def line(self, x0, y0, x1, y1, c, t=1):
        n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for i in range(n + 1):
            x = x0 + (x1 - x0) * i / n
            y = y0 + (y1 - y0) * i / n
            for dx in range(t):
                for dy in range(t):
                    self.px(round(x) + dx, round(y) + dy, c)

    def poly(self, pts, c):
        if self.sym:      # edges on the centre column must reach the mirror line
            pts = [(self.hw if p[0] == self.hw - 1 else p[0], p[1]) for p in pts]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        for y in range(int(min(ys)), int(max(ys)) + 1):
            for x in range(int(min(xs)), int(max(xs)) + 1):
                px_, py_, ins, j = x + 0.5, y + 0.5, False, len(pts) - 1
                for i in range(len(pts)):
                    xi, yi, xj, yj = pts[i][0], pts[i][1], pts[j][0], pts[j][1]
                    if (yi > py_) != (yj > py_) and px_ < (xj - xi) * (py_ - yi) / (yj - yi) + xi:
                        ins = not ins
                    j = i
                if ins:
                    self.px(x, y, c)

    def speckle(self, base, alt, p, rnd):
        for y in range(self.H):
            for x in range(self.hw if self.sym else self.W):
                if self.g[y][x] == base and rnd.random() < p:
                    self.px(x, y, alt)

    def shade(self, base, hi, lo):
        old = [r[:] for r in self.g]
        for y in range(self.H):
            for x in range(self.W):
                if old[y][x] == base:
                    up = old[y - 1][x] if y > 0 else "."
                    dn = old[y + 1][x] if y < self.H - 1 else "."
                    if up != base:
                        self.g[y][x] = hi
                    elif dn != base:
                        self.g[y][x] = lo

    def outline(self):
        old = [r[:] for r in self.g]
        for y in range(self.H):
            for x in range(self.W):
                if old[y][x] == ".":
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        xx, yy = x + dx, y + dy
                        if 0 <= xx < self.W and 0 <= yy < self.H and old[yy][xx] not in (".", "o"):
                            self.g[y][x] = "o"
                            break

    def halo(self, ch, dist=1):
        old = [r[:] for r in self.g]
        for y in range(self.H):
            for x in range(self.W):
                if old[y][x] == "." and (x + y) % 2 == 0:
                    for dy in range(-dist, dist + 1):
                        for dx in range(-dist, dist + 1):
                            xx, yy = x + dx, y + dy
                            if 0 <= xx < self.W and 0 <= yy < self.H and old[yy][xx] not in (".", ch):
                                self.g[y][x] = ch
                                break
                        else:
                            continue
                        break

    def rows(self):
        return ["".join(r[:self.hw]) if self.sym else "".join(r) for r in self.g]


def _mk(hw, h, fn, seed=1, halo=None, sym=True):
    c = _Cv(hw, h, sym)
    fn(c, random.Random(seed))
    c.outline()
    if halo:
        c.halo(halo)
    return c.rows()


# ---------------------------------------------------------------- wasteland mobs
def _f_scrapswarmer(c, r):
    hw, cx = c.hw, c.cx
    c.line(1, 8, 0, 11, "k")
    c.line(3, 9, 2, 11, "k")
    c.line(5, 9, 5, 11, "k")
    c.ell(cx, 7.5, 6.3, 3.4, "r")
    c.ell(2.2, 5.8, 2.4, 1.8, "g")
    c.rect(hw - 1, 6, hw - 1, 10, "g")
    c.ell(cx, 3.6, 3.6, 2.6, "r")
    c.rect(hw - 2, 1, hw - 1, 2, "g")
    c.line(2, 2, 0, 0, "G")
    c.px(hw - 3, 4, "y")
    c.px(hw - 2, 4, "y")
    c.px(hw - 1, 6, "w")
    c.speckle("r", "k", 0.10, r)
    c.shade("r", "R", "d")
    c.shade("g", "G", "k")


_def("scrapswarmer", _mk(7, 12, _f_scrapswarmer), dict(
    r=(158, 78, 40), R=(214, 124, 62), d=(100, 46, 30), g=(128, 130, 142), G=(184, 186, 198),
    k=(52, 40, 44), y=(255, 232, 80), w=(240, 236, 220)))


def _f_rad_hornet(c, r):
    hw, cx = c.hw, c.cx
    c.ell(2.6, 4.0, 2.8, 3.4, "w")
    c.ell(3.2, 8.0, 2.0, 1.6, "w")
    c.line(2, 2, 3, 6, "W")
    c.line(1, 4, 3, 5, "W")
    c.ell(cx, 4.2, 2.8, 2.0, "k")
    c.ell(cx, 2.2, 2.2, 1.6, "k")
    c.px(hw - 2, 2, "R")
    c.px(hw - 3, 1, "k")
    c.line(hw - 3, 0, hw - 4, -1 if False else 0, "k")
    c.ell(cx, 8.4, 3.0, 3.0, "G")
    c.ell(cx, 8.4, 1.8, 2.0, "L")
    c.rect(hw - 3, 7, hw - 1, 7, "k")
    c.rect(hw - 3, 10, hw - 1, 10, "k")
    c.rect(hw - 1, 12, hw - 1, 13, "T")
    c.px(hw - 3, 5, "y")
    c.px(hw - 2, 5, "y")


_def("rad_hornet", _mk(8, 14, _f_rad_hornet), dict(
    w=(176, 226, 232), W=(236, 252, 255), k=(44, 44, 36), R=(255, 70, 60), y=(250, 220, 60),
    G=(70, 190, 60), L=(190, 255, 90), T=(220, 255, 140)))


def _f_dust_crawler(c, r):
    hw, cx = c.hw, c.cx
    c.ell(cx, 1.8, 2.6, 1.6, "S")
    c.ell(cx, 4.2, 4.2, 2.4, "s")
    c.ell(cx, 7.2, 5.6, 3.6, "S")
    c.ell(cx, 7.4, 4.4, 2.4, "L")
    c.ell(cx, 8.0, 2.6, 1.8, "m")
    c.px(hw - 2, 7, "w")
    c.px(hw - 1, 7, "w")
    c.px(hw - 3, 9, "w")
    c.px(hw - 1, 9, "w")
    c.px(hw - 4, 5, "k")
    c.px(hw - 4, 4, "k")
    c.rect(0, 6, 1, 9, "k")
    c.px(0, 10, "k")
    c.px(1, 10, "k")
    c.line(0, 4, 2, 3, "d")
    c.speckle("S", "L", 0.10, r)
    c.speckle("s", "d", 0.12, r)


_def("dust_crawler", _mk(7, 11, _f_dust_crawler), dict(
    S=(222, 196, 140), s=(188, 160, 104), L=(240, 222, 170), d=(150, 122, 80), k=(58, 40, 36),
    m=(80, 30, 36), w=(252, 248, 236)))


def _f_slag_thrower(c, r):
    hw, cx = c.hw, c.cx
    c.rect(hw - 4, 16, hw - 2, 19, "b")
    c.rect(hw - 5, 19, hw - 2, 19, "k")
    c.ell(cx, 12, 5.6, 4.6, "b")
    c.rect(0, 10, 1, 16, "b")
    c.rect(0, 16, 1, 17, "f")
    c.ell(cx, 5, 3.0, 2.8, "b")
    c.px(hw - 3, 5, "F")
    c.px(hw - 2, 5, "F")
    c.px(hw - 3, 7, "w")
    c.px(hw - 1, 7, "w")
    c.ell(2.2, 8.4, 2.8, 2.2, "r")
    c.rect(0, 2, 2, 8, "m")
    c.rect(0, 1, 2, 1, "M")
    c.px(1, 0, "F")
    c.rect(hw - 3, 9, hw - 1, 14, "r")
    c.ell(cx, 12, 1.8, 2.2, "f")
    c.ell(cx, 12, 0.9, 1.2, "F")
    c.line(hw - 6, 11, hw - 4, 15, "f")
    c.speckle("b", "d", 0.12, r)
    c.shade("r", "R", "d")
    c.shade("m", "M", "k")


_def("slag_thrower", _mk(9, 20, _f_slag_thrower), dict(
    b=(104, 62, 54), d=(70, 40, 40), r=(150, 78, 40), R=(204, 120, 58), k=(40, 28, 30), m=(88, 90, 100),
    M=(150, 154, 168), f=(255, 120, 30), F=(255, 220, 90), w=(236, 230, 210), h=(120, 50, 24)))


def _f_harvester(c, r):
    hw, cx = c.hw, c.cx
    c.rect(0, 16, hw - 1, 19, "k")
    for x in (1, 4, 7):
        c.ell(x + 0.5, 17.6, 1.8, 1.8, "t")
        c.px(x, 17, "g")
    c.rect(hw - 7, 8, hw - 1, 16, "g")
    c.rect(hw - 6, 9, hw - 5, 11, "d")
    c.rect(hw - 6, 13, hw - 4, 14, "d")
    c.px(hw - 3, 15, "R")
    c.px(hw - 3, 9, "R")
    c.rect(hw - 4, 3, hw - 1, 7, "G")
    c.rect(hw - 3, 5, hw - 1, 5, "R")
    c.px(hw - 1, 2, "R")
    c.px(hw - 1, 1, "R")
    c.rect(1, 7, 2, 13, "a")
    c.line(2, 6, 2, 3, "a")
    c.line(2, 3, 4, 1, "H", 1)
    c.px(5, 1, "H")
    c.px(5, 2, "H")
    c.rect(hw - 9, 9, hw - 8, 11, "d")
    c.shade("g", "G", "d")
    c.shade("a", "H", "k")


_def("harvester", _mk(10, 20, _f_harvester, seed=2), dict(
    g=(120, 124, 134), G=(176, 180, 192), d=(70, 72, 84), k=(38, 38, 46), t=(66, 66, 76), a=(90, 92, 104),
    H=(206, 208, 220), R=(255, 50, 50)))


def _f_toxic_stalker(c, r):
    hw, cx = c.hw, c.cx
    c.rect(hw - 5, 15, hw - 3, 17, "g")
    c.rect(hw - 6, 17, hw - 3, 18, "d")
    c.ell(cx, 13, 4.6, 3.8, "g")
    c.ell(cx, 9.6, 7.6, 3.6, "g")
    c.rect(0, 9, 1, 15, "g")
    c.px(0, 16, "c")
    c.px(1, 16, "c")
    c.px(0, 17, "c")
    for (x, y) in [(hw - 8, 6), (hw - 6, 5), (hw - 4, 5)]:
        c.px(x, y, "S")
        c.px(x, y - 1, "S")
    c.ell(cx, 4.2, 3.2, 2.6, "g")
    c.rect(hw - 3, 3, hw - 2, 4, "y")
    c.px(hw - 3, 3, "Y")
    c.rect(hw - 3, 6, hw - 1, 6, "d")
    c.px(hw - 2, 6, "c")
    c.line(hw - 5, 9, hw - 3, 14, "L")
    c.line(hw - 8, 10, hw - 6, 13, "L")
    c.px(hw - 2, 11, "L")
    c.speckle("g", "d", 0.10, r)
    c.shade("g", "G", "d")


_def("toxic_stalker", _mk(9, 19, _f_toxic_stalker, seed=3, halo="a"), dict(
    g=(98, 160, 70), G=(150, 214, 96), d=(56, 100, 52), S=(210, 236, 120), L=(200, 255, 100),
    y=(255, 232, 40), Y=(255, 255, 190), c=(230, 240, 170), a=(110, 200, 60)))


# ---------------------------------------------------------------- dark-castle mobs
def _f_cursed_armor(c, r):
    hw, cx = c.hw, c.cx
    c.rect(hw - 5, 15, hw - 1, 19, "S")
    c.px(hw - 1, 17, "d")
    c.px(hw - 1, 18, "d")
    c.rect(hw - 6, 19, hw - 1, 19, "d")
    c.rect(0, 9, 1, 15, "S")
    c.rect(0, 15, 1, 16, "d")
    c.rect(hw - 5, 8, hw - 1, 14, "S")
    c.rect(hw - 1, 9, hw - 1, 13, "v")
    c.rect(hw - 3, 11, hw - 1, 11, "v")
    c.ell(2.6, 8.0, 3.2, 2.4, "S")
    c.ell(cx, 4.2, 3.4, 3.4, "S")
    c.rect(hw - 3, 4, hw - 1, 4, "v")
    c.rect(hw - 2, 5, hw - 1, 6, "d")
    c.rect(hw - 1, 0, hw - 1, 1, "d")
    c.rect(hw - 3, 6, hw - 3, 6, "d")
    c.shade("S", "s", "d")


_def("cursed_armor", _mk(9, 20, _f_cursed_armor), dict(
    S=(84, 90, 112), s=(132, 140, 166), d=(48, 52, 70), v=(214, 110, 255), p=(110, 50, 170)))


def _f_gargoyle(c, r):
    hw, cx = c.hw, c.cx
    c.poly([(hw - 3, 4), (1, 0), (0, 4), (2, 6), (1, 9), (4, 8), (hw - 3, 9)], "W")
    c.line(hw - 3, 5, 1, 1, "S")
    c.line(hw - 3, 6, 2, 6, "S")
    c.ell(cx, 7.4, 3.0, 3.0, "S")
    c.ell(cx, 4.4, 2.6, 2.2, "S")
    c.px(hw - 3, 2, "d")
    c.px(hw - 3, 3, "d")
    c.px(hw - 2, 4, "e")
    c.px(hw - 1, 6, "w")
    c.px(hw - 3, 10, "d")
    c.px(hw - 2, 10, "d")
    c.speckle("S", "s", 0.12, r)
    c.shade("S", "s", "d")


_def("gargoyle", _mk(8, 11, _f_gargoyle), dict(
    S=(128, 130, 142), s=(168, 170, 182), d=(78, 80, 92), W=(98, 100, 114), e=(255, 60, 60), w=(240, 240, 240)))


def _f_blood_bat(c, r):
    hw, cx = c.hw, c.cx
    c.poly([(hw - 2, 3), (0, 1), (0, 6), (2, 5), (3, 8), (5, 6), (hw - 2, 7)], "C")
    c.line(hw - 2, 3, 0, 1, "c")
    c.line(hw - 2, 5, 1, 5, "c")
    c.ell(cx, 5.0, 1.8, 2.6, "c")
    c.px(hw - 2, 1, "c")
    c.px(hw - 2, 2, "c")
    c.px(hw - 2, 4, "y")
    c.px(hw - 2, 7, "w")


_def("blood_bat", _mk(7, 9, _f_blood_bat), dict(
    C=(130, 22, 44), c=(206, 50, 66), y=(255, 230, 90), w=(255, 250, 240)))


def _f_executioner(c, r):
    hw, cx = c.hw, c.cx
    # cloak
    c.poly([(hw - 1, 8), (hw - 4, 9), (2, 13), (1, 20), (hw - 1, 20)], "k")
    for x in range(1, hw - 1, 2):
        c.px(x, 20, ".")
    c.line(2, 14, 2, 19, "b")
    c.line(hw - 5, 12, hw - 5, 19, "b")
    # hood
    c.ell(cx, 5, 4.2, 4.6, "k")
    c.ell(cx, 6, 2.8, 2.8, "K")
    c.px(hw - 3, 6, "e")
    c.px(hw - 2, 6, "e")
    # huge double-bladed axe held in front
    c.rect(hw - 1, 8, hw - 1, 21, "h")
    c.px(hw - 1, 7, "a")
    c.poly([(hw - 2, 11), (hw - 4, 10), (3, 8), (0, 9), (1, 13), (0, 18), (3, 18), (hw - 4, 16), (hw - 2, 15)], "A")
    c.line(0, 9, 1, 13, "a")
    c.line(1, 13, 0, 18, "a")
    c.line(3, 8, 0, 9, "a")
    c.line(0, 18, 3, 18, "a")
    c.rect(hw - 2, 12, hw - 1, 14, "h")
    c.px(hw - 2, 13, "g")
    c.shade("A", "a", "k")


_def("executioner", _mk(9, 21, _f_executioner), dict(
    A=(150, 160, 190), a=(230, 240, 255), k=(26, 28, 46), K=(10, 10, 22), b=(110, 150, 220),
    e=(200, 250, 255), h=(120, 100, 90), g=(190, 205, 230), n=(90, 130, 210)))


def _f_templar(c, r):
    hw, cx = c.hw, c.cx
    c.poly([(2, 9), (hw - 1, 8), (hw - 1, 19), (1, 19)], "D")
    c.rect(hw - 5, 15, hw - 2, 19, "C")
    c.px(hw - 1, 17, "k")
    c.px(hw - 1, 18, "k")
    c.rect(hw - 5, 8, hw - 1, 14, "C")
    c.rect(hw - 5, 14, hw - 1, 14, "G")
    c.rect(0, 9, 1, 15, "C")
    c.rect(0, 15, 1, 16, "G")
    c.ell(2.6, 8.0, 3.0, 2.2, "G")
    c.ell(cx, 4.2, 3.3, 3.3, "C")
    c.rect(hw - 3, 4, hw - 1, 4, "k")
    c.rect(hw - 3, 5, hw - 3, 5, "p")
    c.rect(hw - 1, 0, hw - 1, 2, "G")
    c.line(hw - 3, 0, hw - 4, 2, "p")
    c.ell(cx, 11, 1.8, 1.8, "q")
    c.px(hw - 1, 11, "W")
    c.px(hw - 2, 10, "p")
    c.px(hw - 2, 12, "p")
    c.shade("C", "c", "D")


_def("templar", _mk(9, 20, _f_templar, halo="a"), dict(
    C=(170, 34, 52), c=(224, 70, 80), D=(100, 20, 38), G=(250, 200, 70), k=(30, 16, 24), p=(255, 120, 220),
    q=(100, 240, 255), W=(255, 255, 255), a=(190, 90, 220)))


def _f_lich(c, r):
    hw, cx = c.hw, c.cx
    c.poly([(hw - 1, 9), (hw - 5, 10), (2, 15), (0, 20), (hw - 1, 20)], "R")
    for x in range(0, hw - 1, 2):
        c.px(x, 20, ".")
        c.px(x + 1, 19, "r")
    c.line(hw - 4, 11, hw - 3, 19, "r")
    c.line(3, 13, 2, 19, "r")
    c.ell(cx, 11.5, 1.6, 1.6, "e")
    c.px(hw - 1, 11, "E")
    c.rect(1, 11, 1, 14, "B")
    c.px(0, 15, "B")
    c.px(1, 15, "B")
    c.ell(cx, 5.2, 3.4, 3.6, "R")
    c.ell(cx, 5.6, 2.7, 3.0, "B")
    c.rect(hw - 3, 4, hw - 2, 5, "k")
    c.px(hw - 3, 5, "e")
    c.px(hw - 2, 4, "e")
    c.px(hw - 1, 6, "k")
    c.rect(hw - 3, 8, hw - 1, 8, "k")
    c.px(hw - 2, 8, "B")
    c.px(hw - 4, 8, "B")
    c.line(hw - 4, 2, hw - 5, 0, "G")
    c.line(hw - 2, 2, hw - 3, -1 if False else 0, "G")
    c.rect(hw - 1, 0, hw - 1, 1, "G")
    c.rect(hw - 4, 2, hw - 1, 2, "G")
    c.shade("R", "m", "r")


_def("lich", _mk(9, 21, _f_lich, halo="a"), dict(
    R=(60, 40, 84), r=(36, 24, 54), m=(92, 66, 124), B=(232, 228, 206), k=(14, 10, 20), e=(110, 255, 140),
    E=(220, 255, 230), G=(206, 200, 170), a=(60, 170, 90)))


def _f_thorn(c, r):
    hw, cx = c.hw, c.cx
    c.ell(cx, 6.2, 6.0, 3.8, "G")
    c.ell(cx, 4.5, 4.0, 2.6, "G")
    c.speckle("G", "g", 0.22, r)
    c.speckle("G", "d", 0.12, r)
    for (x, y, x2, y2) in [(1, 3, 0, 1), (3, 1, 3, 0), (0, 6, -1, 5), (1, 9, 0, 10), (hw - 3, 9, hw - 3, 10), (2, 8, 1, 9)]:
        c.px(x, y, "R")
        c.px(x2, y2, "T")
    c.px(hw - 3, 5, "y")
    c.px(hw - 2, 5, "y")
    c.px(hw - 2, 7, "d")
    c.shade("G", "g", "d")


_def("thorn", _mk(7, 11, _f_thorn), dict(
    G=(50, 120, 60), g=(84, 166, 80), d=(28, 74, 44), R=(214, 40, 56), T=(255, 120, 120), y=(255, 236, 90)))


# ---------------------------------------------------------------- forest mini-bosses (scale 4)
def _f_treant(c, r):
    hw, cx = c.hw, c.cx
    # roots
    c.line(hw - 5, 23, hw - 11, 26, "B", 2)
    c.line(hw - 7, 22, hw - 12, 22, "B", 2)
    c.line(hw - 3, 24, hw - 5, 27, "B", 2)
    # arms
    c.line(hw - 8, 14, 3, 10, "B", 2)
    c.line(hw - 8, 18, 2, 18, "B", 2)
    c.ell(2.5, 9, 2.8, 2.6, "L")
    c.ell(2.0, 18, 2.2, 2.2, "L")
    # trunk
    c.ell(cx, 17.5, 8.4, 9.4, "B")
    c.rect(hw - 8, 20, hw - 1, 25, "B")
    for x in (hw - 7, hw - 4):
        c.line(x, 12, x, 24, "b")
    c.line(hw - 6, 13, hw - 6, 22, "T")
    c.speckle("B", "b", 0.10, r)
    # hollow face
    c.ell(cx, 16, 4.4, 5.2, "k")
    c.rect(hw - 4, 14, hw - 3, 15, "e")
    c.px(hw - 4, 13, "E")
    c.line(hw - 3, 19, hw - 1, 19, "m")
    c.px(hw - 3, 20, "m")
    c.px(hw - 1, 20, "m")
    # crown
    c.ell(cx, 7, 10.5, 5.5, "L")
    c.ell(4.5, 9, 4.2, 3, "L")
    c.ell(hw - 5, 4.5, 5, 3.6, "L")
    c.speckle("L", "l", 0.16, r)
    c.speckle("L", "d", 0.10, r)
    c.shade("L", "l", "d")
    for (x, y) in [(5, 7), (hw - 3, 2), (3, 11), (hw - 8, 4)]:
        c.px(x, y, "e")


_def("treant", _mk(13, 28, _f_treant, seed=4), dict(
    L=(62, 130, 56), l=(104, 176, 78), d=(34, 82, 44), B=(112, 78, 52), b=(78, 52, 38), T=(150, 108, 70),
    k=(24, 14, 30), e=(210, 110, 255), E=(250, 210, 255), m=(170, 60, 190)), scale=4)


def _f_hydra(c, r):
    hw, cx = c.hw, c.cx
    # mound
    c.ell(cx, 22, 11.2, 4.4, "D")
    c.speckle("D", "d", 0.2, r)
    c.line(hw - 11, 21, hw - 4, 18, "G", 2)
    # centre neck + head
    c.rect(hw - 2, 9, hw - 1, 20, "G")
    c.ell(cx, 6.5, 3.6, 3.0, "G")
    c.rect(hw - 3, 8, hw - 1, 9, "m")
    c.px(hw - 3, 10, "w")
    c.px(hw - 3, 5, "y")
    c.px(hw - 2, 5, "y")
    c.px(hw - 4, 3, "R")
    c.px(hw - 1, 2, "R")
    # side necks
    c.line(hw - 6, 20, 4, 15, "G", 2)
    c.line(4, 15, 3, 10, "G", 2)
    c.ell(3.0, 8, 3.0, 2.4, "G")
    c.rect(2, 9, 4, 10, "m")
    c.px(1, 11, "w")
    c.px(4, 11, "w")
    c.px(3, 7, "y")
    c.px(2, 7, "y")
    c.px(1, 5, "R")
    c.px(4, 5, "R")
    c.shade("G", "g", "d")
    # thorns
    for (x, y) in [(hw - 4, 12), (hw - 4, 16), (hw - 2, 19), (2, 13), (6, 17), (1, 20), (hw - 8, 21), (4, 22), (hw - 5, 23), (0, 22)]:
        c.px(x, y, "R")
    for (x, y) in [(hw - 5, 12), (hw - 5, 16), (3, 14), (5, 16)]:
        c.px(x, y, "R")


_def("hydra", _mk(12, 26, _f_hydra, seed=5), dict(
    G=(70, 150, 66), g=(122, 200, 90), d=(36, 88, 46), D=(46, 100, 50), R=(230, 52, 64), m=(70, 16, 34),
    w=(250, 246, 230), y=(255, 236, 80)), scale=4)


def _f_sylphid(c, r):
    hw, cx = c.hw, c.cx
    # wings
    c.poly([(hw - 4, 10), (hw - 6, 5), (2, 0), (0, 3), (1, 9), (hw - 5, 14)], "w")
    c.poly([(hw - 4, 13), (hw - 5, 16), (2, 19), (1, 15), (hw - 6, 12)], "w")
    c.line(hw - 4, 10, 2, 1, "W")
    c.line(hw - 4, 11, 1, 8, "W")
    c.line(hw - 5, 14, 3, 17, "W")
    c.line(hw - 4, 3, 4, 3, "w")
    # skirt of petals
    c.ell(hw - 5.5, 19, 2.6, 4.0, "P")
    c.ell(hw - 2.5, 20, 2.4, 4.2, "p")
    c.ell(cx, 20.5, 2.0, 3.8, "P")
    c.px(hw - 6, 23, "y")
    c.px(hw - 3, 24, "y")
    c.px(hw - 1, 24, "y")
    # bodice
    c.rect(hw - 3, 11, hw - 1, 16, "p")
    c.rect(hw - 3, 14, hw - 1, 14, "y")
    c.rect(hw - 5, 12, hw - 4, 14, "s")
    c.px(hw - 6, 14, "y")
    c.px(hw - 7, 13, "Y")
    # head + hair
    c.rect(hw - 5, 7, hw - 4, 14, "h")
    c.ell(cx, 7.4, 3.0, 3.2, "s")
    c.ell(cx, 5.2, 3.6, 2.2, "h")
    c.px(hw - 3, 8, "e")
    c.px(hw - 2, 8, "e")
    c.px(hw - 1, 10, "m")
    c.line(hw - 3, 4, hw - 4, 1, "P")
    c.line(hw - 6, 5, hw - 7, 3, "P")
    c.rect(hw - 1, 0, hw - 1, 3, "y")
    c.px(hw - 2, 1, "Y")


_def("sylphid", _mk(11, 25, _f_sylphid, seed=6), dict(
    w=(226, 204, 255), W=(255, 240, 255), P=(255, 168, 212), p=(236, 110, 170), y=(255, 226, 90),
    Y=(255, 250, 200), s=(255, 226, 208), h=(255, 214, 110), e=(220, 40, 130), m=(200, 70, 90),
    a=(255, 190, 230)), scale=4)


def _f_barkspine(c, r):
    hw, cx = c.hw, c.cx
    # jagged root spikes on the back
    c.poly([(hw - 11, 10), (hw - 12, 3), (hw - 8, 9)], "S")
    c.poly([(hw - 8, 8), (hw - 8, 0), (hw - 4, 7)], "S")
    c.poly([(hw - 4, 7), (hw - 3, 1), (hw - 1, 1), (hw - 1, 7)], "S")
    # root feet
    c.poly([(hw - 9, 19), (hw - 13, 25), (hw - 10, 26), (hw - 6, 22)], "B")
    c.poly([(hw - 5, 22), (hw - 7, 26), (hw - 4, 26), (hw - 1, 23)], "B")
    # stump
    c.poly([(hw - 10, 9), (hw - 12, 16), (hw - 11, 22), (hw - 7, 24), (hw - 1, 25), (hw - 1, 7), (hw - 5, 8), (hw - 7, 6)], "B")
    c.speckle("B", "b", 0.14, r)
    for (x, y0, y1) in [(hw - 10, 12, 20), (hw - 3, 18, 23)]:
        c.line(x, y0, x, y1, "b")
    c.line(hw - 8, 18, hw - 8, 23, "T")
    # face
    c.rect(hw - 7, 12, hw - 4, 13, "e")
    c.rect(hw - 6, 12, hw - 5, 12, "E")
    c.line(hw - 8, 10, hw - 4, 11, "k")
    c.rect(hw - 5, 17, hw - 1, 19, "k")
    c.px(hw - 4, 17, "e")
    c.px(hw - 2, 18, "e")
    c.px(hw - 1, 17, "e")
    # sap
    for (x, y0, y1) in [(hw - 7, 14, 19), (hw - 11, 11, 16), (hw - 2, 9, 14), (hw - 5, 21, 24)]:
        c.line(x, y0, x, y1, "e")
        c.px(x, y1 + 1, "E")
    c.shade("B", "T", "b")


_def("barkspine", _mk(13, 27, _f_barkspine, seed=7), dict(
    B=(112, 78, 50), b=(74, 50, 36), T=(156, 112, 72), S=(190, 160, 110), k=(30, 18, 34),
    e=(190, 100, 255), E=(244, 210, 255)), scale=4)


# ---------------------------------------------------------------- wasteland mini-bosses (scale 4)
def _f_dreadnought(c, r):
    hw, cx = c.hw, c.cx
    # stacks and steam
    for x in (hw - 10, hw - 3):
        c.rect(x, 1, x + 1, 7, "g")
        c.rect(x, 0, x + 1, 0, "d")
    c.ell(hw - 9.5, -0.5, 2.2, 1.4, "W")
    c.ell(hw - 2.5, 0.0, 2.0, 1.2, "w")
    # tracks
    c.rect(1, 19, hw - 1, 23, "k")
    for x in (3, 7, 11):
        c.ell(x + 0.5, 21, 2.0, 2.0, "t")
        c.px(x, 21, "g")
    # hull
    c.rect(1, 9, hw - 1, 19, "r")
    c.rect(2, 10, 6, 15, "g")
    c.rect(7, 10, hw - 1, 13, "R")
    c.rect(2, 16, 5, 18, "R")
    c.rect(2, 10, 6, 10, "G")
    for (x, y) in [(2, 11), (6, 11), (2, 14), (6, 14), (hw - 2, 11), (8, 11)]:
        c.px(x, y, "k")
    # cab head
    c.rect(hw - 7, 3, hw - 1, 9, "r")
    c.rect(hw - 6, 4, hw - 5, 6, "y")
    c.rect(hw - 6, 3, hw - 3, 3, "k")
    c.px(hw - 4, 4, "k")
    # grille mouth + teeth
    c.rect(hw - 7, 13, hw - 1, 16, "k")
    for x in range(hw - 7, hw, 2):
        c.px(x, 13, "T")
        c.px(x + 1, 16, "T")
    # tusks
    c.poly([(hw - 9, 13), (hw - 11, 6), (hw - 12, 3), (hw - 7, 10)], "T")
    c.poly([(hw - 8, 16), (hw - 10, 21), (hw - 6, 17)], "T")
    c.speckle("r", "d", 0.12, r)
    c.speckle("R", "d", 0.12, r)
    c.shade("g", "G", "d")


_def("dreadnought", _mk(13, 25, _f_dreadnought, seed=8), dict(
    r=(150, 72, 40), R=(196, 108, 56), d=(98, 44, 30), g=(116, 120, 132), G=(170, 174, 188), k=(34, 30, 34),
    t=(72, 72, 82), y=(255, 226, 80), T=(238, 226, 190), w=(210, 214, 220), W=(240, 244, 250)), scale=4)


def _f_gorgon(c, r):
    hw, cx = c.hw, c.cx
    # legs / feet
    c.ell(hw - 6, 21.5, 3.4, 1.8, "G")
    c.px(hw - 9, 22, "w")
    c.px(hw - 8, 22, "w")
    # body
    c.ell(cx, 16.5, 10.4, 6.0, "G")
    c.ell(cx, 17.5, 6, 4.2, "g")
    # arms
    c.ell(2.2, 16, 2.8, 4.2, "G")
    c.px(0, 20, "w")
    c.px(2, 20, "w")
    # head
    c.ell(cx, 8, 8.4, 5.4, "G")
    c.ell(cx, 10.5, 6.4, 2.6, "m")
    for x in range(hw - 7, hw, 2):
        c.px(x, 9, "w")
        c.px(x + 1, 12, "w")
    # eyes
    c.rect(hw - 7, 5, hw - 5, 6, "y")
    c.px(hw - 6, 5, "k")
    c.px(hw - 6, 6, "k")
    c.line(hw - 8, 4, hw - 4, 3, "d")
    # crest
    for x in range(hw - 9, hw, 2):
        c.poly([(x, 4), (x + 1, 0 if x % 4 else 1), (x + 2, 4)], "S")
    # glowing veins
    c.line(hw - 8, 13, hw - 5, 18, "V")
    c.line(hw - 5, 14, hw - 3, 19, "V")
    c.line(hw - 11, 15, hw - 9, 19, "V")
    c.line(hw - 3, 6, hw - 1, 7, "V")
    c.px(hw - 8, 8, "V")
    for (x, y) in [(hw - 9, 7), (hw - 4, 15), (hw - 11, 13)]:
        c.ell(x, y, 1.1, 1.1, "v")
    c.speckle("G", "d", 0.10, r)
    c.shade("G", "g", "d")


_def("gorgon", _mk(13, 23, _f_gorgon, seed=9), dict(
    G=(72, 120, 56), g=(116, 164, 80), d=(42, 74, 40), m=(70, 20, 40), w=(248, 244, 224), y=(255, 230, 70),
    k=(20, 14, 20), S=(190, 214, 100), V=(150, 255, 90), v=(110, 220, 70), a=(70, 190, 60)), scale=4)


# ---------------------------------------------------------------- dark castle mini-bosses (scale 4)
def _f_bgargoyle(c, r):
    hw, cx = c.hw, c.cx
    # wings
    c.poly([(hw - 5, 8), (hw - 8, 3), (3, 0), (0, 2), (1, 8), (0, 14), (4, 12), (3, 17), (hw - 6, 16)], "W")
    for (x1, y1) in [(3, 0), (0, 8), (3, 16)]:
        c.line(hw - 6, 9, x1, y1, "S")
    c.line(hw - 7, 10, 2, 11, "S")
    for (x, y) in [(hw - 8, 8), (hw - 11, 4), (4, 10), (hw - 9, 13)]:
        c.px(x, y, "e")
    # legs
    c.ell(hw - 5.5, 20.5, 3.0, 2.6, "S")
    c.px(hw - 8, 22, "w")
    c.px(hw - 6, 22, "w")
    # torso
    c.ell(cx, 14, 5.6, 6.4, "S")
    c.ell(cx, 14, 3.4, 4.4, "s")
    c.rect(hw - 1, 10, hw - 1, 17, "e")
    c.rect(hw - 3, 12, hw - 1, 12, "e")
    c.px(hw - 3, 15, "e")
    c.px(hw - 2, 16, "e")
    # arms
    c.ell(hw - 8, 14, 2.0, 4.6, "S")
    # head
    c.ell(cx, 7, 4.6, 4.0, "S")
    c.poly([(hw - 4, 4), (hw - 7, 0), (hw - 6, 5)], "h")
    c.rect(hw - 4, 6, hw - 3, 7, "e")
    c.rect(hw - 4, 6, hw - 4, 6, "E")
    c.rect(hw - 3, 10, hw - 3, 10, "w")
    c.rect(hw - 1, 10, hw - 1, 10, "w")
    c.px(hw - 1, 8, "d")
    c.speckle("S", "d", 0.12, r)
    c.speckle("S", "s", 0.12, r)
    c.shade("S", "s", "d")


_def("bgargoyle", _mk(14, 24, _f_bgargoyle, seed=10), dict(
    S=(128, 130, 148), s=(170, 172, 190), d=(78, 80, 98), W=(92, 70, 96), h=(60, 60, 76),
    e=(255, 60, 70), E=(255, 190, 190), w=(240, 238, 240), a=(120, 30, 60)), scale=4)


def _f_inquisitor(c, r):
    hw, cx = c.hw, c.cx
    # robe with tail
    c.poly([(hw - 6, 10), (hw - 9, 15), (hw - 7, 19), (hw - 4, 22), (hw - 1, 24), (hw - 1, 10)], "R")
    for x in range(hw - 9, hw - 1, 3):
        c.line(x, 17, x, 20, "r")
    c.line(hw - 6, 11, hw - 8, 15, "G")
    c.line(hw - 8, 15, hw - 6, 19, "G")
    c.line(hw - 6, 19, hw - 3, 22, "G")
    c.rect(hw - 1, 11, hw - 1, 22, "G")
    # sleeves + staves
    c.poly([(hw - 6, 11), (3, 12), (2, 16), (hw - 7, 15)], "R")
    c.line(2, 6, 2, 19, "t")
    c.ell(2, 5, 1.8, 1.8, "e")
    c.px(2, 4, "E")
    c.px(3, 13, "b")
    c.px(2, 13, "b")
    # hood
    c.ell(cx, 6, 4.8, 5.2, "R")
    c.ell(cx, 7, 3.0, 3.6, "k")
    c.ell(cx, 7, 2.2, 2.8, "b")
    c.rect(hw - 3, 6, hw - 2, 7, "k")
    c.px(hw - 3, 6, "e")
    c.px(hw - 2, 7, "e")
    c.px(hw - 1, 9, "k")
    c.rect(hw - 3, 9, hw - 3, 9, "k")
    # crown
    c.rect(hw - 5, 2, hw - 1, 2, "G")
    for x in (hw - 5, hw - 3, hw - 1):
        c.px(x, 1, "G")
    c.px(hw - 1, 0, "e")
    c.shade("R", "P", "r")


_def("inquisitor", _mk(10, 25, _f_inquisitor, seed=11), dict(
    R=(104, 54, 150), P=(150, 96, 200), r=(62, 28, 96), G=(250, 200, 70), k=(16, 8, 20), b=(232, 226, 204),
    e=(255, 70, 140), E=(255, 200, 230), t=(110, 80, 60), a=(150, 50, 160)), scale=4)


# ---------------------------------------------------------------- final bosses
def _f_construct(c, r):
    hw, cx = c.hw, c.cx
    # treads
    c.rect(0, 21, 5, 27, "k")
    for y in (23, 26):
        c.ell(2.5, y, 2.2, 1.8, "t")
    c.rect(7, 22, hw - 1, 27, "d")
    c.rect(hw - 3, 22, hw - 1, 27, "k")
    # shoulder cannons
    c.rect(0, 9, 5, 14, "S")
    c.rect(1, 1, 3, 9, "c")
    c.rect(0, 0, 4, 1, "m")
    c.px(2, 0, "M")
    c.rect(5, 6, 5, 9, "d")
    # main hull
    c.rect(3, 10, hw - 1, 22, "S")
    c.rect(3, 10, hw - 1, 11, "s")
    c.rect(3, 20, 6, 21, "d")
    for y in (12, 14, 16, 18):
        c.px(4, y, "k")
        c.px(hw - 1, y, "k") if False else None
    for (x, y) in [(4, 12), (4, 19), (hw - 4, 12), (hw - 2, 21), (8, 21)]:
        c.px(x, y, "k")
    c.rect(hw - 7, 18, hw - 1, 19, "d")
    # core + hatch
    c.ell(cx, 15.5, 5.2, 4.6, "h")
    c.ell(cx, 15.5, 4.0, 3.6, "C")
    c.ell(cx, 15.5, 2.2, 2.0, "W")
    c.poly([(hw - 9, 10), (hw - 8, 10), (hw - 5, 13), (hw - 5, 18), (hw - 8, 21), (hw - 9, 21)], "S")
    c.line(hw - 8, 12, hw - 6, 14, "k")
    c.rect(hw - 6, 11, hw - 1, 11, "h")
    # head
    c.rect(hw - 6, 3, hw - 1, 9, "S")
    c.rect(hw - 6, 3, hw - 1, 3, "s")
    c.rect(hw - 5, 4, hw - 1, 4, "d")
    c.ell(cx, 6.5, 2.4, 2.4, "R")
    c.px(hw - 2, 5, "r")
    c.px(hw - 1, 5, "r")
    c.rect(hw - 9, 6, hw - 7, 8, "d")
    c.px(hw - 8, 4, "R")
    c.shade("S", "s", "d")
    c.shade("c", "s", "k")


_def("construct", _mk(15, 28, _f_construct, seed=12), dict(
    S=(98, 110, 132), s=(154, 168, 192), d=(58, 66, 86), k=(30, 34, 46), t=(72, 78, 96), c=(76, 84, 102),
    m=(255, 170, 60), M=(255, 240, 160), h=(36, 44, 58), C=(70, 220, 255), W=(230, 255, 255),
    R=(255, 50, 50), r=(255, 190, 190)), scale=6)

CONSTRUCT_RAGE_PAL = dict(
    S=(150, 54, 48), s=(206, 98, 78), d=(88, 28, 30), c=(122, 48, 44), t=(96, 44, 44), h=(58, 22, 26),
    C=(255, 110, 36), W=(255, 232, 150), R=(255, 236, 80), r=(255, 255, 200), m=(255, 90, 40))


def _f_vespera(c, r):
    hw, cx = c.hw, c.cx
    # cape-wings
    c.poly([(hw - 3, 9), (hw - 5, 5), (5, 2), (0, 0), (0, 8), (1, 14), (3, 20), (6, 17), (hw - 5, 19)], "V")
    c.line(5, 2, 0, 0, "v")
    c.line(0, 0, 0, 8, "v")
    c.line(0, 8, 1, 14, "v")
    c.line(1, 14, 3, 20, "v")
    c.line(hw - 3, 10, 1, 2, "m")
    c.line(hw - 3, 11, 1, 10, "m")
    c.line(hw - 4, 13, 3, 19, "m")
    # gown
    c.poly([(hw - 3, 15), (hw - 6, 22), (hw - 3, 25), (hw - 1, 26), (hw - 1, 15)], "G")
    c.rect(hw - 3, 10, hw - 1, 16, "G")
    c.line(hw - 3, 16, hw - 5, 22, "v")
    c.rect(hw - 1, 11, hw - 1, 24, "m")
    c.line(hw - 4, 11, hw - 6, 15, "p")
    c.px(hw - 6, 16, "p")
    # hair + head
    c.rect(hw - 4, 5, hw - 4, 13, "D")
    c.ell(cx, 6.8, 3.0, 3.6, "p")
    c.ell(cx, 4.0, 3.4, 1.8, "D")
    c.rect(hw - 4, 6, hw - 2, 7, "p")
    c.rect(hw - 3, 6, hw - 2, 7, "e")
    c.px(hw - 1, 9, "m")
    c.rect(hw - 3, 9, hw - 1, 9, "p")
    # crown shards
    c.line(hw - 4, 3, hw - 6, 0, "c")
    c.line(hw - 2, 3, hw - 3, 0, "c")
    c.rect(hw - 1, 0, hw - 1, 3, "c")
    c.px(hw - 1, 0, "e")


_def("vespera", _mk(12, 27, _f_vespera, seed=13), dict(
    V=(54, 30, 96), v=(130, 90, 200), G=(40, 22, 72), D=(26, 14, 44), m=(236, 60, 200),
    p=(240, 230, 246), e=(255, 60, 220), c=(190, 160, 255)), scale=5)

_sprite_cache = {}
_rot_cache = {}


def rot(img, ang):
    """Rotated copy of an UP-pointing sprite so that it points along the screen
    angle `ang` (radians, from math.atan2(vy, vx)). Cached in 15 degree steps."""
    deg = (-math.degrees(ang) - 90) % 360
    b = int(round(deg / 15.0)) % 24
    key = (id(img), b)
    hit = _rot_cache.get(key)
    if hit is None:
        hit = (img, pygame.transform.rotate(img, b * 15))   # keep img alive so id stays unique
        _rot_cache[key] = hit
    return hit[1]


def _mirror(rows):
    return [r + r[::-1] for r in rows]


def _build(name, pal_override=None):
    rows, pal, scale = SPRITE_DEFS[name]
    pal = dict(pal)
    if pal_override:
        pal.update(pal_override)
    rows = _mirror(rows)
    w, h = len(rows[0]), len(rows)
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != ".":
                surf.set_at((x, y), pal[ch])
    return pygame.transform.scale(surf, (w * scale, h * scale))


def _stone_col(c):
    """Grey, slightly cool 'petrified' version of a colour."""
    g = 0.30 * c[0] + 0.59 * c[1] + 0.11 * c[2]
    g = g * 0.8 + 36
    return (int(g * 0.96), int(g), int(min(255, g * 1.08)))


def _dim_col(c):
    return (int(c[0] * 0.45), int(c[1] * 0.45), int(c[2] * 0.45))


def sprite(name, mode="normal", flip=False):
    key = (name, mode, flip)
    s = _sprite_cache.get(key)
    if s is not None:
        return s
    if mode == "rage":
        s = _build(name, CONSTRUCT_RAGE_PAL if name == "construct" else BOSS_RAGE_PAL)
    elif mode == "normal":
        s = _build(name)
    elif mode in ("stone", "dim"):
        pal = SPRITE_DEFS[name][1]
        s = _build(name, {k: (_stone_col(v) if mode == "stone" else _dim_col(v)) for k, v in pal.items()})
    else:
        base = sprite(name, "normal")
        if mode == "flash":
            s = pygame.mask.from_surface(base).to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0))
        else:
            s = base.copy()
            tint = {"frozen": (40, 90, 170, 0), "buffed": (90, 20, 20, 0), "ghost": (60, 60, 120, 0)}[mode]
            s.fill(tint, special_flags=pygame.BLEND_RGB_ADD)
    if flip:
        s = pygame.transform.flip(s, True, False)
    _sprite_cache[key] = s
    return s


def check_sprites():
    """Dev helper: report rows with inconsistent widths."""
    bad = []
    for n, (rows, _, _) in SPRITE_DEFS.items():
        w = len(rows[0])
        for i, r in enumerate(rows):
            if len(r) != w:
                bad.append((n, i, len(r), w))
    return bad


# --- small procedural sprites -------------------------------------------------
def _grid_surface(rows, pal, scale=PIXEL):
    h, w = len(rows), len(rows[0])
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != ".":
                s.set_at((x, y), pal[ch])
    return pygame.transform.scale(s, (w * scale, h * scale))


_misc = {}


def misc(name):
    if name in _misc:
        return _misc[name]
    if name == "gem":
        s = _grid_surface(["..c..", ".cCc.", "cCWCc", ".cCc.", "..c.."],
                          dict(c=(40, 120, 220), C=(100, 200, 255), W=(230, 250, 255)))
    elif name == "coin":
        s = _grid_surface([".ooo.", "oyYyo", "oYyyo", "oyyyo", ".ooo."],
                          dict(o=(120, 76, 20), y=(255, 206, 60), Y=(255, 244, 150)))
    elif name == "food":
        s = _grid_surface(["..gg..", ".oRRo.", "oRhRRo", "oRRRRo", ".oRRo.", "..oo.."],
                          dict(o=(80, 20, 24), R=(220, 56, 56), h=(255, 160, 150), g=(80, 180, 80)))
    elif name == "shard":
        s = _grid_surface([".y.", "yYy", ".y."], dict(y=(255, 200, 80), Y=(255, 250, 200)))
    elif name == "needle":
        s = _grid_surface([".g.", "gGg", "gGg", ".g."], dict(g=(120, 220, 70), G=(220, 255, 150)))
    elif name == "orb_e":
        s = _grid_surface([".rr.", "rRRr", "rRRr", ".rr."], dict(r=(210, 40, 60), R=(255, 150, 150)))
    elif name == "orb_p":
        s = _grid_surface([".pp.", "pPPp", "pPPp", ".pp."], dict(p=(160, 70, 220), P=(240, 190, 255)))
    elif name == "orb_a":
        s = _grid_surface([".aa.", "aAAa", "aAAa", ".aa."], dict(a=(110, 200, 50), A=(220, 255, 140)))
    elif name == "bolt":
        s = _grid_surface([".yy.", "yYYy", "yYYy", ".yy."], dict(y=(255, 220, 90), Y=(255, 255, 220)))
    elif name == "bolt_crit":
        s = _grid_surface([".mm.", "mWWm", "mWWm", ".mm."], dict(m=(236, 70, 220), W=(255, 230, 255)))
    elif name == "heart":
        s = _grid_surface([".rr.rr.", "rRRrRRr", "rRRRRRr", ".rRRRr.", "..rRr..", "...r..."],
                          dict(r=(200, 36, 52), R=(255, 110, 110)), 3)
    elif name == "coin_ui":
        s = _grid_surface([".ooo.", "oyYyo", "oYyyo", "oyyyo", ".ooo."],
                          dict(o=(120, 76, 20), y=(255, 206, 60), Y=(255, 244, 150)), 4)
    elif name in _GRIDS:
        rows, pal, scale = _GRIDS[name]
        s = _grid_surface(rows, pal, scale)
    else:
        raise KeyError(name)
    _misc[name] = s
    return s


# Extra small sprites: projectiles, weapons. "up" ones point UP and are turned with rot().
_GRIDS = {
    "pollen": ([".y.", "yYy", ".y."], dict(y=(255, 214, 70), Y=(255, 250, 190)), 3),
    "spore": (["..gg..", ".gGGg.", "gGGGGg", "gGGGGg", ".gGGg.", "..gg.."], dict(g=(80, 170, 60), G=(170, 240, 110)), 3),
    "leaf": ([".p.", "pPp", "pPp", ".p."], dict(p=(236, 90, 170), P=(255, 190, 225)), 3),
    "root": (["..b..", ".bBb.", "bBBBb", "bBdBb", "bBBBb", ".bBb."], dict(b=(110, 72, 40), B=(176, 120, 66), d=(70, 44, 28)), 3),
    "sap": ([".pp.", "pPPp", "pPPp", ".pp."], dict(p=(130, 70, 190), P=(214, 164, 255)), 3),
    "thorn_b": ([".t.", "tTt", "tTt", ".t.", ".t."], dict(t=(60, 120, 50), T=(184, 232, 124)), 3),
    "shard": ([".s.", "sSs", "sSs", ".s."], dict(s=(120, 126, 150), S=(224, 230, 244)), 3),
    "sting": ([".y.", "yYy", ".y.", ".y."], dict(y=(190, 230, 60), Y=(244, 255, 160)), 3),
    "dagger": ([".w.", "wWw", "wWw", "wWw", "wWw", ".k.", "kgk"],
               dict(w=(170, 182, 220), W=(250, 252, 255), k=(90, 70, 110), g=(180, 110, 230)), 3),
    "phantom": (["..ppp..", ".pPPPp.", "pPwPwPp", "pPPPPPp", "pPPPPPp", "pPpPpPp", ".p.p.p."],
                dict(p=(110, 64, 176), P=(196, 156, 244), w=(20, 8, 40)), 3),
    "knight": (["..pppp..", ".pSSSSp.", ".pSkkSp.", ".pSSSSp.", "pSSSSSSp", "pSSPPSSp", "pSSPPSSp", ".pSSSSp.", ".pp..pp."],
               dict(p=(28, 32, 72), S=(120, 136, 192), k=(10, 10, 30), P=(196, 206, 244)), 3),
    "bone": ([".w.", "wWw", ".w.", ".w."], dict(w=(190, 180, 160), W=(250, 244, 230)), 3),
    "flame": ([".oo.", "oOOo", "oOYo", ".oo."], dict(o=(220, 80, 20), O=(255, 150, 40), Y=(255, 240, 150)), 3),
    "gunshot": (["yy", "YY", "yy"], dict(y=(255, 210, 90), Y=(255, 255, 230)), 3),
    "arrow": (["..a..", ".aAa.", "..s..", "..s..", "..s..", "..s..", ".fsf.", "f.s.f"],
              dict(a=(220, 226, 240), A=(255, 255, 255), s=(160, 108, 64), f=(220, 60, 60)), 3),
    "axe": (["..hh...", ".hAAA..", "hAAAAh.", ".hAAh..", "..hH...", "..H....", "..H....", "..H...."],
            dict(A=(208, 214, 232), h=(110, 116, 144), H=(140, 92, 54)), 3),
    "sword": (["..w..", "..W..", "..W..", "..W..", "..W..", "..W..", ".gkg.", "..k.."],
              dict(w=(255, 255, 255), W=(214, 226, 248), g=(255, 208, 80), k=(90, 60, 50)), 3),
    "potion": ([".kk.", ".gg.", "gGGg", "gGGg", "gGGg", ".gg."],
               dict(k=(140, 92, 54), g=(50, 150, 64), G=(150, 250, 110)), 3),
    "meteor": (["...ooo...", "..oOOOo..", ".oOYYYOo.", "oOYYWYYOo", "oOYWWWYOo", "oOYYWYYOo", ".oOYYYOo.", "..oOOOo..", "...ooo..."],
               dict(o=(150, 40, 20), O=(240, 100, 30), Y=(255, 200, 70), W=(255, 250, 200)), 4),
}
BULLET_ROT = {"leaf", "thorn_b", "shard", "sting", "dagger", "bone", "gunshot", "arrow"}
BULLET_SPRITE = {"needle": "needle", "orb_e": "orb_e", "orb_p": "orb_p", "orb_a": "orb_a", "pollen": "pollen", "spore": "spore",
                 "leaf": "leaf", "root": "root", "sap": "sap", "thorn": "thorn_b", "shard": "shard", "sting": "sting",
                 "dagger": "dagger", "phantom": "phantom", "knight": "knight", "bone": "bone", "flame": "flame"}


def bullet_img(kind, ang=0.0):
    name = BULLET_SPRITE.get(kind, "orb_e")
    img = misc(name)
    return rot(img, ang) if name in BULLET_ROT else img


# 8x8 icons (x3 = 24px) for weapons and active skills
_ICONS = {
    "gunner": (["........", ".gggggg.", "gGGGGGGg", "gGgggggg", ".gg.gG..", "...gGg..", "...ggg..", "........"],
               dict(g=(90, 96, 124), G=(176, 184, 214))),
    "acid_potion": (["...kk...", "...gg...", "..gggg..", ".gGGGGg.", "gGGHGGGg", "gGGGGGGg", ".gGGGGg.", "..gggg.."],
                    dict(k=(140, 92, 54), g=(50, 150, 64), G=(110, 230, 80), H=(214, 255, 190))),
    "bow": ([".....bb.", "....bB.s", "...bB..s", "...bB..s", "...bB..s", "...bB..s", "....bB.s", ".....bb."],
            dict(b=(120, 76, 40), B=(190, 130, 70), s=(236, 236, 240))),
    "axe": (["..mmm...", ".mMMMm..", "mMMMMm..", ".mMMmh..", "..mmhh..", "....h...", "...h....", "..h....."],
            dict(m=(120, 126, 150), M=(214, 220, 240), h=(150, 98, 56))),
    "spinning_swords": (["w......w", ".w....w.", "..w..w..", "...ww...", "...gg...", "..g..g..", ".k....k.", "k......k"],
                        dict(w=(226, 236, 255), g=(255, 208, 80), k=(120, 80, 56))),
    "meteor_shower": (["o.......", ".oo.....", "..oo....", "...oOo..", "....oOOo", "....oOYo", ".....oOo", "......oo"],
                      dict(o=(220, 70, 24), O=(255, 140, 40), Y=(255, 240, 160))),
    "healing_spring": (["..gggg..", "..gWWg..", "gggWWggg", "gWWWWWWg", "gggWWggg", "..gWWg..", "..gggg..", ".bbbbbb."],
                       dict(g=(60, 190, 100), W=(220, 255, 230), b=(70, 140, 230))),
    "blizzard": (["...w....", ".w.w.w..", "..www...", "wwwWwww.", "..www...", ".w.w.w..", "...w....", "........"],
                 dict(w=(150, 210, 255), W=(255, 255, 255))),
    "time_freeze": ([".wwwwww.", ".w....w.", "..w..w..", "...ww...", "...ww...", "..w..w..", ".w.bb.w.", ".wwwwww."],
                    dict(w=(170, 220, 255), b=(90, 150, 255))),
}
_icons = {}


def icon(name):
    """24x24 pixel icon for weapons / active skills, or None."""
    if name not in _ICONS:
        return None
    if name not in _icons:
        rows, pal = _ICONS[name]
        _icons[name] = _grid_surface(rows, pal, 3)
    return _icons[name]


# ----------------------------------------------------------------------------
# Backgrounds (all drawn at 300x300 art pixels, then scaled x3 -> 900x900)
# ----------------------------------------------------------------------------
LOW = SCREEN // PIXEL


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _finish(low):
    return pygame.transform.scale(low, (SCREEN, SCREEN))


def make_glade_bg():
    rnd = random.Random(11)
    low = pygame.Surface((LOW, LOW))
    greens = [(74, 144, 76), (66, 132, 70), (80, 152, 82), (60, 124, 66)]
    for cy in range(0, LOW, 5):
        for cx in range(0, LOW, 5):
            i = int((math.sin(cx * 0.09) + math.cos(cy * 0.08) + rnd.random() * 1.4 + 2.2)) % 4
            pygame.draw.rect(low, greens[i], (cx, cy, 5, 5))
    for _ in range(5200):
        low.set_at((rnd.randrange(LOW), rnd.randrange(LOW)), rnd.choice(greens + [(92, 164, 90), (52, 110, 58)]))
    # dirt path
    dirt = [(158, 118, 74), (146, 106, 64), (168, 128, 82)]
    for y in range(LOW):
        cx = LOW / 2 + 46 * math.sin(y * 0.021) + 14 * math.sin(y * 0.07)
        hw = 11 + 2.5 * math.sin(y * 0.09)
        for x in range(int(cx - hw - 2), int(cx + hw + 3)):
            d = abs(x - cx)
            if d < hw or (d < hw + 2 and rnd.random() < 0.5):
                if 0 <= x < LOW:
                    low.set_at((x, y), rnd.choice(dirt))
    # stone summoning circle
    c = LOW // 2
    pygame.draw.circle(low, (104, 108, 124), (c, c), 42)
    pygame.draw.circle(low, (140, 146, 168), (c, c), 42, 3)
    pygame.draw.circle(low, (86, 90, 108), (c, c), 36)
    pygame.draw.circle(low, (126, 132, 152), (c, c), 28, 2)
    for k in range(8):
        a = k * math.pi / 4
        x1, y1 = c + math.cos(a) * 30, c + math.sin(a) * 30
        x2, y2 = c + math.cos(a) * 40, c + math.sin(a) * 40
        pygame.draw.line(low, (180, 200, 230) if k % 2 == 0 else (150, 160, 190), (x1, y1), (x2, y2), 2)
    for _ in range(260):
        a, r = rnd.uniform(0, 6.28), rnd.uniform(0, 36)
        low.set_at((int(c + math.cos(a) * r), int(c + math.sin(a) * r)), rnd.choice([(94, 98, 116), (112, 118, 136), (78, 82, 98)]))
    # grass tufts, flowers, rocks
    for _ in range(170):
        x, y = rnd.randrange(8, LOW - 8), rnd.randrange(8, LOW - 8)
        col = (46, 104, 56)
        low.set_at((x, y), col)
        low.set_at((x - 1, y - 1), col)
        low.set_at((x + 1, y - 1), col)
    for _ in range(90):
        x, y = rnd.randrange(10, LOW - 10), rnd.randrange(10, LOW - 10)
        if abs(x - c) ** 2 + abs(y - c) ** 2 < 46 ** 2:
            continue
        petal = rnd.choice([(255, 255, 255), (255, 226, 90), (255, 140, 190), (150, 200, 255)])
        low.set_at((x, y), petal)
        low.set_at((x, y + 1), (50, 120, 60))
    for _ in range(26):
        x, y = rnd.randrange(14, LOW - 14), rnd.randrange(14, LOW - 14)
        if abs(x - c) ** 2 + abs(y - c) ** 2 < 48 ** 2:
            continue
        pygame.draw.ellipse(low, (112, 112, 124), (x, y, 7, 4))
        pygame.draw.ellipse(low, (150, 150, 164), (x + 1, y, 4, 2))
    # forest border
    border = 13
    pygame.draw.rect(low, (28, 66, 44), (0, 0, LOW, border))
    pygame.draw.rect(low, (28, 66, 44), (0, LOW - border, LOW, border))
    pygame.draw.rect(low, (28, 66, 44), (0, 0, border, LOW))
    pygame.draw.rect(low, (28, 66, 44), (LOW - border, 0, border, LOW))
    spots = []
    for t in range(-6, LOW + 6, 11):
        spots += [(t, 4), (t + 5, LOW - 5), (4, t + 3), (LOW - 5, t + 7)]
    for (x, y) in spots:
        r = rnd.randint(7, 10)
        pygame.draw.circle(low, (24, 58, 40), (x, y), r + 1)
        pygame.draw.circle(low, (34, 82, 52), (x, y), r)
        pygame.draw.circle(low, (50, 112, 66), (x - 2, y - 2), r // 2)
        low.set_at((x - 3, y - 3), (110, 170, 100))
    # subtle edge shading
    shade = pygame.Surface((LOW, LOW), pygame.SRCALPHA)
    for i in range(18):
        a = int(90 * (1 - i / 18) ** 2)
        pygame.draw.rect(shade, (10, 10, 30, a), (i, i, LOW - 2 * i, LOW - 2 * i), 1)
    low.blit(shade, (0, 0))
    return _finish(low)


def make_title_bg():
    rnd = random.Random(5)
    low = pygame.Surface((LOW, LOW))
    top, mid, hor = (12, 8, 36), (92, 40, 104), (244, 150, 94)
    for y in range(200):
        t = y / 200
        col = _lerp(top, mid, t * 1.6) if t < 0.625 else _lerp(mid, hor, (t - 0.625) / 0.375)
        pygame.draw.line(low, col, (0, y), (LOW, y))
    pygame.draw.rect(low, hor, (0, 200, LOW, 100))
    for _ in range(170):
        x, y = rnd.randrange(LOW), rnd.randrange(130)
        low.set_at((x, y), rnd.choice([(255, 255, 255), (220, 220, 255), (255, 240, 180)]))
    pygame.draw.circle(low, (255, 240, 200), (225, 52), 17)
    pygame.draw.circle(low, (236, 216, 176), (219, 48), 5)
    pygame.draw.circle(low, (236, 216, 176), (230, 58), 3)

    def ridge(base, amp, col, seed, step=14):
        r2 = random.Random(seed)
        pts, h = [(0, LOW)], base
        for x in range(0, LOW + step, step):
            h = max(base - amp, min(base + amp // 2, h + r2.randint(-amp // 2, amp // 2)))
            pts.append((x, h))
        pts.append((LOW, LOW))
        pygame.draw.polygon(low, col, pts)
    ridge(190, 36, (84, 44, 100), 1)
    ridge(205, 26, (52, 28, 76), 2)
    # castle on a hill
    pygame.draw.ellipse(low, (36, 22, 58), (60, 196, 180, 60))
    cs = (28, 18, 46)
    pygame.draw.rect(low, cs, (112, 158, 76, 46))
    for tx in (104, 148, 188):
        pygame.draw.rect(low, cs, (tx, 130 if tx == 148 else 142, 14, 64 if tx == 148 else 56))
        pygame.draw.polygon(low, (50, 26, 66), [(tx - 3, 142 if tx != 148 else 130), (tx + 7, 120 if tx != 148 else 108), (tx + 17, 142 if tx != 148 else 130)])
    for x in range(114, 188, 8):
        pygame.draw.rect(low, cs, (x, 153, 5, 6))
    for (wx, wy) in [(152, 140), (152, 152), (126, 170), (166, 170), (108, 156), (192, 156)]:
        pygame.draw.rect(low, (255, 214, 96), (wx, wy, 3, 4))
    pygame.draw.rect(low, (255, 190, 80), (141, 184, 18, 20))
    pygame.draw.rect(low, (28, 18, 46), (141, 184, 18, 3))
    # foreground
    pygame.draw.rect(low, (14, 10, 26), (0, 252, LOW, 48))
    r3 = random.Random(9)
    for x in range(-4, LOW + 8, 11):
        h = r3.randint(26, 52)
        pygame.draw.polygon(low, (16, 12, 30), [(x, 262), (x + 8, 262 - h), (x + 16, 262)])
        pygame.draw.polygon(low, (16, 12, 30), [(x + 1, 262 - h * 0.45), (x + 8, 262 - h - 6), (x + 15, 262 - h * 0.45)])
    return _finish(low)


def make_lobby_bg():
    rnd = random.Random(21)
    low = pygame.Surface((LOW, LOW))
    for y in range(132):
        pygame.draw.line(low, _lerp((16, 20, 56), (116, 70, 118), y / 132), (0, y), (LOW, y))
    for _ in range(70):
        low.set_at((rnd.randrange(LOW), rnd.randrange(90)), rnd.choice([(255, 255, 255), (220, 230, 255)]))
    r2 = random.Random(3)
    for x in range(-6, LOW + 10, 9):
        h = r2.randint(24, 46)
        pygame.draw.polygon(low, (24, 40, 52), [(x, 136), (x + 6, 136 - h), (x + 12, 136)])
    pygame.draw.rect(low, (24, 40, 52), (0, 130, LOW, 10))
    greens = [(52, 108, 62), (46, 98, 58), (58, 118, 68)]
    for y in range(132, LOW, 4):
        for x in range(0, LOW, 4):
            low.fill(rnd.choice(greens), (x, y, 4, 4))
    for _ in range(2200):
        low.set_at((rnd.randrange(LOW), rnd.randrange(132, LOW)), rnd.choice([(70, 132, 80), (38, 84, 50)]))
    pygame.draw.ellipse(low, (122, 92, 60), (40, 150, 220, 110))
    pygame.draw.ellipse(low, (140, 106, 68), (56, 158, 188, 90))
    for _ in range(500):
        a, r = rnd.uniform(0, 6.28), rnd.uniform(0, 1)
        low.set_at((int(150 + math.cos(a) * 104 * r), int(205 + math.sin(a) * 48 * r)), rnd.choice([(110, 80, 52), (154, 118, 76)]))
    # tent (left)
    pygame.draw.polygon(low, (170, 52, 56), [(30, 176), (68, 122), (106, 176)])
    pygame.draw.polygon(low, (214, 92, 84), [(68, 122), (106, 176), (80, 176)])
    pygame.draw.polygon(low, (232, 214, 170), [(52, 176), (68, 146), (84, 176)])
    pygame.draw.polygon(low, (40, 24, 28), [(60, 176), (68, 156), (76, 176)])
    pygame.draw.line(low, (92, 58, 36), (68, 122), (68, 112), 2)
    pygame.draw.polygon(low, GOLD, [(68, 111), (80, 115), (68, 119)])
    # quest board (right)
    pygame.draw.rect(low, (92, 58, 36), (222, 140, 4, 46))
    pygame.draw.rect(low, (92, 58, 36), (264, 140, 4, 46))
    pygame.draw.rect(low, (134, 90, 54), (216, 128, 58, 38))
    pygame.draw.rect(low, (58, 36, 26), (216, 128, 58, 38), 2)
    for (px, py, pc) in [(222, 134, (236, 224, 186)), (240, 134, (236, 224, 186)), (256, 138, (236, 224, 186)), (230, 150, (236, 224, 186))]:
        pygame.draw.rect(low, pc, (px, py, 11, 13))
        low.set_at((px + 5, py + 1), (178, 40, 52))
    # torches
    for tx in (22, 278):
        pygame.draw.rect(low, (92, 58, 36), (tx, 168, 3, 26))
        pygame.draw.rect(low, (58, 36, 26), (tx - 1, 166, 5, 4))
    # barrels
    for (bx, by) in [(104, 186), (114, 192)]:
        pygame.draw.rect(low, (118, 76, 44), (bx, by, 10, 12))
        pygame.draw.rect(low, (60, 40, 30), (bx, by + 2, 10, 1))
        pygame.draw.rect(low, (60, 40, 30), (bx, by + 8, 10, 1))
    # fire pit stones
    for k in range(10):
        a = k / 10 * 6.28
        pygame.draw.rect(low, (116, 120, 140), (int(190 + math.cos(a) * 13), int(212 + math.sin(a) * 6), 4, 3))
    return _finish(low)


def draw_fire(surf, x, y, t, scale=PIXEL):
    """Animated campfire + torches' glow. (x, y) in screen px = base of the fire."""
    rnd = random.Random(t // 5)
    glow = pygame.Surface((220, 220), pygame.SRCALPHA)
    for r, a in ((100, 20), (70, 30), (44, 44)):
        pygame.draw.circle(glow, (255, 150, 60, a), (110, 110), r)
    surf.blit(glow, (x - 110, y - 100))
    flame = [(0, 0, (255, 120, 30), 5, 3), (0, -2, (255, 170, 40), 3, 4), (0, -4, (255, 230, 120), 2, 3)]
    for i in range(-2, 3):
        h = rnd.randint(4, 8) - abs(i)
        for j in range(h):
            col = [(220, 60, 24), (255, 120, 30), (255, 190, 60), (255, 240, 150)][min(3, j * 4 // max(1, h))]
            surf.fill(col, (x + i * scale, y - j * scale, scale, scale))
    for _ in range(3):
        ex = x + rnd.randint(-3, 3) * scale
        ey = y - rnd.randint(9, 16) * scale
        surf.fill((255, 200, 90), (ex, ey, scale, scale))


def _crack(low, rnd, x, y, ang, n, col):
    for i in range(n):
        ang += rnd.uniform(-0.5, 0.5)
        x += math.cos(ang)
        y += math.sin(ang)
        if 0 <= int(x) < LOW and 0 <= int(y) < LOW:
            low.set_at((int(x), int(y)), col)
        if rnd.random() < 0.06 and n - i > 6:
            _crack(low, rnd, x, y, ang + rnd.choice((-1, 1)) * rnd.uniform(0.6, 1.1), (n - i) // 2, col)


def make_wasteland_bg():
    rnd = random.Random(31)
    low = pygame.Surface((LOW, LOW))
    sands = [(176, 132, 86), (168, 124, 80), (184, 140, 92), (160, 118, 74)]
    for cy in range(0, LOW, 5):
        for cx in range(0, LOW, 5):
            i = int((math.sin(cx * 0.07) + math.cos(cy * 0.09) + rnd.random() * 1.5 + 2.3)) % 4
            pygame.draw.rect(low, sands[i], (cx, cy, 5, 5))
    for _ in range(5200):
        low.set_at((rnd.randrange(LOW), rnd.randrange(LOW)), rnd.choice(sands + [(194, 150, 100), (150, 110, 68)]))
    for k in range(34):                       # wind ripples
        y0, x0, ln = rnd.randrange(20, LOW - 20), rnd.randrange(0, LOW - 70), rnd.randint(30, 80)
        for x in range(ln):
            low.set_at((x0 + x, y0 + int(2 * math.sin(x * 0.15 + k))), (192, 150, 100))
    for _ in range(26):                       # cracks
        _crack(low, rnd, rnd.randrange(20, LOW - 20), rnd.randrange(20, LOW - 20), rnd.uniform(0, 6.28),
               rnd.randint(14, 40), (118, 82, 52))
    c = LOW // 2
    for _ in range(9):                        # craters
        x, y = rnd.randrange(24, LOW - 40), rnd.randrange(24, LOW - 30)
        if (x - c) ** 2 + (y - c) ** 2 < 62 ** 2:
            continue
        w = rnd.randint(14, 26)
        pygame.draw.ellipse(low, (150, 108, 68), (x, y, w, w * 2 // 3))
        pygame.draw.ellipse(low, (128, 90, 56), (x + 2, y + 2, w - 4, w * 2 // 3 - 3))
        pygame.draw.ellipse(low, (196, 152, 104), (x, y, w, w * 2 // 3), 1)
    for _ in range(8):                        # toxic puddles
        x, y = rnd.randrange(30, LOW - 50), rnd.randrange(30, LOW - 40)
        if (x - c) ** 2 + (y - c) ** 2 < 66 ** 2:
            continue
        w = rnd.randint(16, 30)
        pygame.draw.ellipse(low, (70, 120, 52), (x - 1, y - 1, w + 2, w // 2 + 3))
        pygame.draw.ellipse(low, (96, 200, 80), (x, y, w, w // 2 + 1))
        pygame.draw.ellipse(low, (170, 255, 120), (x + w // 4, y + 1, w // 3, w // 6 + 1))
    # central rusted arena plate with hazard ring
    pygame.draw.circle(low, (96, 78, 66), (c, c), 50)
    pygame.draw.circle(low, (124, 100, 82), (c, c), 50, 3)
    pygame.draw.circle(low, (80, 64, 56), (c, c), 42)
    for k in range(24):
        a = k / 24 * 2 * math.pi
        col = (232, 190, 50) if k % 2 == 0 else (40, 34, 36)
        pygame.draw.line(low, col, (c + math.cos(a) * 44, c + math.sin(a) * 44), (c + math.cos(a + 0.12) * 49, c + math.sin(a + 0.12) * 49), 3)
    pygame.draw.circle(low, (110, 90, 76), (c, c), 30, 2)
    for k in range(6):
        a = k / 6 * 2 * math.pi
        pygame.draw.line(low, (60, 48, 44), (c, c), (c + math.cos(a) * 30, c + math.sin(a) * 30), 2)
    for k in range(12):
        a = k / 12 * 2 * math.pi
        low.set_at((int(c + math.cos(a) * 36), int(c + math.sin(a) * 36)), (170, 150, 130))
    for _ in range(180):
        a, r = rnd.uniform(0, 6.28), rnd.uniform(0, 40)
        low.set_at((int(c + math.cos(a) * r), int(c + math.sin(a) * r)), rnd.choice([(70, 56, 50), (104, 84, 70), (140, 70, 40)]))
    for _ in range(14):                       # scrap plates, tires, bones, dead brush
        x, y = rnd.randrange(22, LOW - 30), rnd.randrange(22, LOW - 24)
        if (x - c) ** 2 + (y - c) ** 2 < 58 ** 2:
            continue
        kind = rnd.randrange(4)
        if kind == 0:
            pygame.draw.rect(low, (118, 96, 82), (x, y, rnd.randint(8, 14), rnd.randint(4, 7)))
            pygame.draw.rect(low, (170, 80, 40), (x + 1, y + 1, 4, 2))
        elif kind == 1:
            pygame.draw.circle(low, (40, 34, 36), (x, y), 5)
            pygame.draw.circle(low, (96, 90, 96), (x, y), 2)
        elif kind == 2:
            pygame.draw.line(low, (236, 226, 200), (x, y), (x + 6, y + 2), 1)
            pygame.draw.line(low, (236, 226, 200), (x + 2, y - 2), (x + 4, y + 4), 1)
        else:
            for _b in range(4):
                pygame.draw.line(low, (110, 78, 48), (x, y), (x + rnd.randint(-5, 5), y - rnd.randint(3, 7)), 1)
    for (x, y) in [(46, 232), (236, 56), (250, 220)]:   # rusted wrecks
        pygame.draw.rect(low, (96, 56, 40), (x, y, 30, 12))
        pygame.draw.rect(low, (150, 80, 46), (x + 3, y - 4, 16, 6))
        pygame.draw.rect(low, (70, 100, 120), (x + 5, y - 3, 5, 3))
        pygame.draw.rect(low, (40, 34, 36), (x + 2, y + 10, 7, 4))
        pygame.draw.rect(low, (40, 34, 36), (x + 20, y + 10, 7, 4))
        pygame.draw.rect(low, (60, 36, 30), (x, y, 30, 12), 1)
    border = 13                               # canyon walls
    rock = (92, 52, 40)
    for rr in ((0, 0, LOW, border), (0, LOW - border, LOW, border), (0, 0, border, LOW), (LOW - border, 0, border, LOW)):
        pygame.draw.rect(low, rock, rr)
    for t in range(-6, LOW + 6, 9):
        for (x, y) in ((t, 4), (t + 4, LOW - 5), (4, t + 3), (LOW - 5, t + 6)):
            r = rnd.randint(5, 9)
            pygame.draw.circle(low, (66, 38, 32), (x, y), r + 1)
            pygame.draw.circle(low, (110, 64, 48), (x, y), r)
            pygame.draw.circle(low, (150, 92, 62), (x - 2, y - 2), r // 2)
            low.set_at((x - 3, y - 3), (200, 140, 96))
    shade = pygame.Surface((LOW, LOW), pygame.SRCALPHA)
    for i in range(18):
        a = int(80 * (1 - i / 18) ** 2)
        pygame.draw.rect(shade, (40, 20, 10, a), (i, i, LOW - 2 * i, LOW - 2 * i), 1)
    low.blit(shade, (0, 0))
    return _finish(low)


def make_castle_bg():
    rnd = random.Random(41)
    low = pygame.Surface((LOW, LOW))
    tones = [(54, 58, 84), (60, 64, 92), (48, 52, 78), (66, 70, 100)]
    for ty in range(0, LOW, 15):
        off = 0 if (ty // 15) % 2 == 0 else 10
        for tx in range(-20, LOW, 20):
            col = tones[rnd.randrange(4)]
            pygame.draw.rect(low, col, (tx + off, ty, 20, 15))
            pygame.draw.rect(low, (30, 32, 52), (tx + off, ty, 20, 15), 1)
            pygame.draw.line(low, tuple(min(255, v + 16) for v in col), (tx + off + 1, ty + 1), (tx + off + 18, ty + 1))
    for _ in range(3600):
        low.set_at((rnd.randrange(LOW), rnd.randrange(LOW)), rnd.choice(tones + [(40, 42, 66), (74, 78, 108)]))
    for _ in range(18):
        _crack(low, rnd, rnd.randrange(20, LOW - 20), rnd.randrange(20, LOW - 20), rnd.uniform(0, 6.28),
               rnd.randint(10, 28), (26, 26, 44))
    for _ in range(40):                       # moss / damp
        x, y = rnd.randrange(16, LOW - 16), rnd.randrange(16, LOW - 16)
        for _m in range(5):
            low.set_at((x + rnd.randint(-2, 2), y + rnd.randint(-1, 1)), (44, 80, 70))
    # royal carpet runner
    pygame.draw.rect(low, (104, 22, 40), (128, 0, 44, LOW))
    pygame.draw.rect(low, (140, 34, 54), (132, 0, 36, LOW))
    for x in (128, 171):
        pygame.draw.line(low, (214, 168, 60), (x, 0), (x, LOW))
    for y in range(8, LOW, 14):
        pygame.draw.polygon(low, (214, 168, 60), [(150, y - 4), (154, y), (150, y + 4), (146, y)])
        pygame.draw.rect(low, (170, 120, 50), (134, y - 1, 6, 2))
        pygame.draw.rect(low, (170, 120, 50), (160, y - 1, 6, 2))
    # arcane rune circle
    c = LOW // 2
    pygame.draw.circle(low, (36, 30, 64), (c, c), 52)
    pygame.draw.circle(low, (150, 90, 230), (c, c), 52, 2)
    pygame.draw.circle(low, (110, 66, 190), (c, c), 44, 1)
    pts = [(c + math.cos(k * 2 * math.pi / 5 - math.pi / 2) * 42, c + math.sin(k * 2 * math.pi / 5 - math.pi / 2) * 42) for k in range(5)]
    for i in range(5):
        pygame.draw.line(low, (176, 120, 250), pts[i], pts[(i + 2) % 5], 1)
    pygame.draw.circle(low, (200, 150, 255), (c, c), 6, 1)
    for k in range(12):
        a = k / 12 * 2 * math.pi
        low.set_at((int(c + math.cos(a) * 48), int(c + math.sin(a) * 48)), (230, 200, 255))
    # moonlight from tall windows
    light = pygame.Surface((LOW, LOW), pygame.SRCALPHA)
    for x0 in (36, 90, 196, 250):
        pygame.draw.polygon(light, (150, 180, 255, 26), [(x0, 20), (x0 + 16, 20), (x0 + 58, 280), (x0 + 30, 280)])
    low.blit(light, (0, 0))
    # bones / rubble / cobwebs
    for _ in range(12):
        x, y = rnd.randrange(24, LOW - 24), rnd.randrange(24, LOW - 24)
        if (x - c) ** 2 + (y - c) ** 2 < 60 ** 2 or 120 < x < 180:
            continue
        if rnd.random() < 0.5:
            pygame.draw.line(low, (210, 204, 190), (x, y), (x + 5, y + 2))
            pygame.draw.circle(low, (210, 204, 190), (x + 6, y + 2), 1)
        else:
            pygame.draw.ellipse(low, (70, 74, 100), (x, y, 6, 4))
    # castle wall border: battlements, pillars and torches
    border = 13
    wall = (30, 32, 52)
    for rr in ((0, 0, LOW, border), (0, LOW - border, LOW, border), (0, 0, border, LOW), (LOW - border, 0, border, LOW)):
        pygame.draw.rect(low, wall, rr)
    for t in range(0, LOW, 10):
        for (x, y, w, h) in ((t, 0, 7, 9), (t, LOW - 9, 7, 9), (0, t, 9, 7), (LOW - 9, t, 9, 7)):
            pygame.draw.rect(low, (52, 56, 84), (x, y, w, h))
            pygame.draw.rect(low, (82, 88, 124), (x, y, w, 1))
    for t in range(20, LOW, 40):
        for (x, y) in ((t, 6), (t, LOW - 7), (6, t), (LOW - 7, t)):
            pygame.draw.circle(low, (24, 26, 42), (x, y), 6)
            pygame.draw.circle(low, (70, 76, 112), (x, y), 5)
            pygame.draw.circle(low, (110, 118, 156), (x - 1, y - 1), 2)
    glow = pygame.Surface((LOW, LOW), pygame.SRCALPHA)
    for t in range(40, LOW, 80):
        for (x, y) in ((t, 14), (t, LOW - 15), (14, t), (LOW - 15, t)):
            for r, a in ((22, 14), (14, 22), (7, 40)):
                pygame.draw.circle(glow, (255, 170, 70, a), (x, y), r)
            pygame.draw.rect(low, (255, 214, 110), (x - 1, y - 2, 3, 4))
    low.blit(glow, (0, 0))
    shade = pygame.Surface((LOW, LOW), pygame.SRCALPHA)
    for i in range(20):
        a = int(110 * (1 - i / 20) ** 2)
        pygame.draw.rect(shade, (6, 4, 20, a), (i, i, LOW - 2 * i, LOW - 2 * i), 1)
    low.blit(shade, (0, 0))
    return _finish(low)


def make_map_bg(theme):
    return {"glade": make_glade_bg, "wasteland": make_wasteland_bg, "castle": make_castle_bg}.get(theme, make_glade_bg)()


# ----------------------------------------------------------------------------
# Darkness (Vespera's Eclipse Realm) and pollen-haze vignette
# ----------------------------------------------------------------------------
_hole_cache = {}


def light_hole(r):
    """Square surface whose alpha rises from 0 (centre) to 255 (edge); blit with BLEND_RGBA_MIN to punch light."""
    r = int(r)
    if r not in _hole_cache:
        s = pygame.Surface((2 * r + 1, 2 * r + 1), pygame.SRCALPHA)
        for y in range(2 * r + 1):
            for x in range(2 * r + 1):
                d = math.hypot(x - r, y - r) / r
                a = 0 if d < 0.55 else (255 if d >= 1 else int(255 * ((d - 0.55) / 0.45) ** 1.4))
                s.set_at((x, y), (255, 255, 255, a))
        _hole_cache[r] = s
    return _hole_cache[r]


_vig = {}


def vignette(color=(230, 200, 90)):
    if color not in _vig:
        s = pygame.Surface((SCREEN, SCREEN), pygame.SRCALPHA)
        for i in range(36):
            a = int(120 * (1 - i / 36.0) ** 2)
            pygame.draw.rect(s, color + (a,), (i * 4, i * 4, SCREEN - i * 8, SCREEN - i * 8), 4)
        _vig[color] = s
    return _vig[color]


def cover_overlay(alpha=150):
    s = pygame.Surface((SCREEN, SCREEN), pygame.SRCALPHA)
    s.fill((8, 4, 16, alpha))
    return s
