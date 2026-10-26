"""
Project Strikers - hostile world objects (zones, pools, beams, mines, haze, walls, status effects).

"""
import math
import random

import pygame

import strikers_art as art
from strikers_util import seg_dist

SCREEN = 900
MAX_EBULLETS = 520
SOFT_EBULLETS = 150

ZONE_COL = {"blast": (255, 80, 80), "root": (210, 140, 70), "acid": (150, 230, 70), "flame": (255, 140, 50),
            "pulse": (130, 255, 120), "chains": (180, 120, 255)}
POOL_COL = {"acid": (110, 200, 50), "fire": (240, 110, 30), "sludge": (80, 200, 90), "spore": (150, 220, 90),
            "sap": (150, 80, 210), "curse": (150, 90, 210)}
POOL_EDGE = {"acid": (190, 255, 90), "fire": (255, 210, 90), "sludge": (170, 255, 150), "spore": (220, 255, 150),
             "sap": (220, 170, 255), "curse": (220, 170, 255)}

_circ = {}


def disc(surf, x, y, r, color, alpha):
    r = max(2, int(r) // 2 * 2)
    key = (r, color, alpha // 12)
    s = _circ.get(key)
    if s is None:
        s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, color + (alpha,), (r, r), r)
        _circ[key] = s
    surf.blit(s, (int(x) - r, int(y) - r))


class WorldMixin:
    def init_world(self):
        self.ebullets = []
        self.lobs, self.pools, self.walls, self.zones = [], [], [], []
        self.mines, self.hazes, self.bushes, self.ringq = [], [], [], []
        self.beam_list = []
        self.root_t = self.slow_t = self.wound_t = self.rad_t = self.suppress_t = 0
        self.slow_mult = 1.0
        self.push = None
        self.haze_now = False
        self.haze_in = 0.0
        self.dot_cd = 0
        self.border = False
        self.border_w = 48
        self.border_tick = 0

    # ------------------------------------------------------- player status
    def root_player(self, frames):
        self.root_t = max(self.root_t, int(frames))

    def slow_player(self, frames, mult=0.6):
        self.slow_mult = mult if self.slow_t <= 0 else min(self.slow_mult, mult)
        self.slow_t = max(self.slow_t, int(frames))

    def wound_player(self, frames):
        self.wound_t = max(self.wound_t, int(frames))

    def push_player(self, vx, vy, frames=8):
        self.push = [vx, vy, int(frames)]

    def pull_player(self, cx, cy, strength):
        if self.dash_t > 0:
            return
        dx, dy = cx - self.px, cy - self.py
        d = math.hypot(dx, dy) or 1.0
        if d < 30:
            return
        self.px += dx / d * strength
        self.py += dy / d * strength

    def lead_angle(self, x, y, speed):
        """Aim at where the player will be, not where they are."""
        dx, dy = self.px - x, self.py - y
        t = min(55.0, math.hypot(dx, dy) / max(0.5, speed))
        tx, ty = self.px + self.pvx * t * 0.85, self.py + self.pvy * t * 0.85
        tx = max(20, min(SCREEN - 20, tx))
        ty = max(20, min(SCREEN - 20, ty))
        return math.atan2(ty - y, tx - x)

    # ------------------------------------------------------------ projectiles
    def fire_ebullet(self, x, y, ang, speed, dmg, kind="orb_e", r=6, strict=True, life=420,
                     decel=None, decel_after=0, homing=0.0, home_until=0, on_end=None):
        n = len(self.ebullets)
        if n >= MAX_EBULLETS or (strict and n >= SOFT_EBULLETS):
            return None
        if not strict:
            dmg *= self.hz                           # boss / mini-boss bullets scale with map difficulty
        b = type("EB", (), {})()
        b.x, b.y = x, y
        b.vx, b.vy = math.cos(ang) * speed, math.sin(ang) * speed
        b.dmg, b.r, b.life, b.kind = dmg, r, life, kind
        b.age, b.decel, b.decel_after = 0, decel, decel_after
        b.homing, b.home_until, b.on_end = homing, home_until, on_end
        self.ebullets.append(b)
        return b

    def add_lob(self, sx, sy, tx, ty, total, r, dmg, pool_r, pool_life, arc=True, pool_kind="acid", pierce=0.0):
        self.lobs.append(dict(sx=sx, sy=sy, tx=tx, ty=ty, t=0, total=total, r=r, dmg=dmg, pool_r=pool_r,
                              pool_life=pool_life, arc=arc, pool_kind=pool_kind, pierce=pierce))

    def fire_beam(self, x, y, ang, dmg):
        x2, y2 = x + math.cos(ang) * 1500, y + math.sin(ang) * 1500
        self.fx.append(dict(kind="beamflash", x=x, y=y, x2=x2, y2=y2, ttl=10))
        if seg_dist(self.px, self.py, x, y, x2, y2) < 16 + self.pr:
            self.hurt_player(dmg, pierce=0.25)

    def beam(self, x, y, ang, length, width, dmg, active, color, thin=False, wide_tele=False):
        """Called every frame the beam exists: a telegraph (active=False) or a damaging beam."""
        self.beam_list.append((x, y, x + math.cos(ang) * length, y + math.sin(ang) * length, width, dmg, active, color, thin, wide_tele))

    def process_beams(self):
        for x1, y1, x2, y2, w, dmg, active, col, thin, wide in self.beam_list:
            if active and dmg > 0 and self.dash_t <= 0:
                if seg_dist(self.px, self.py, x1, y1, x2, y2) < w / 2.0 + self.pr - 4:
                    self.hurt_player(dmg * self.hz, pierce=0.2)

    # --------------------------------------------------------------- zones
    def add_zone(self, x, y, r, delay, dmg, kind="blast", knock=0, effect=None, pool=None, pierce=0.0, wound=0):
        self.zones.append(dict(x=x, y=y, r=r, t=max(1, int(delay)), total=max(1, int(delay)), dmg=dmg, kind=kind,
                               knock=knock, effect=effect, pool=pool, pierce=pierce, wound=wound))

    def add_pool(self, x, y, r, life, kind="acid", dmg=5):
        if len(self.pools) > 70:
            self.pools.pop(0)
        self.pools.append(dict(x=x, y=y, r=r, life=life, max=life, tick=random.randint(0, 29), kind=kind, dmg=dmg))

    def resolve_zone(self, z):
        kind = z["kind"]
        col = ZONE_COL.get(kind, (255, 90, 90))
        if kind != "pulse" or z["r"] < 100:
            self.fx.append(dict(kind="ring", x=z["x"], y=z["y"], r=6, max_r=z["r"], ttl=12, color=col))
        if math.hypot(self.px - z["x"], self.py - z["y"]) < z["r"] + self.pr:
            hit = self.hurt_player(z["dmg"], pierce=z["pierce"], wound=z["wound"])
            if hit:
                if z["effect"] == "root":
                    self.root_player(48)
                elif z["effect"] == "mutagen":
                    self.slow_player(300, 0.7)
                    self.rad_t = max(self.rad_t, 300)
                    self.toast("MUTAGEN: slowed and healing reduced!", (130, 255, 120), 120)
                if z["knock"]:
                    dx, dy = self.px - z["x"], self.py - z["y"]
                    d = math.hypot(dx, dy) or 1.0
                    self.push_player(dx / d * z["knock"], dy / d * z["knock"], 9)
        if z["pool"]:
            pk, plife, pdmg = z["pool"]
            self.add_pool(z["x"], z["y"], z["r"] * 0.8, plife, pk, pdmg)
        if kind == "blast" and z["r"] > 100:
            self.shake = max(self.shake, 8)

    def add_hazard_ring(self, x, y, n, radius, hp, life, dmg, delay=40):
        self.ringq.append(dict(x=x, y=y, n=n, radius=radius, hp=hp, life=life, dmg=dmg, t=int(delay), total=int(delay)))

    def add_mine(self, x, y):
        self.mines.append(dict(x=x, y=y, t=720))

    def add_haze(self, x, y, r):
        if len(self.hazes) < 7:
            self.hazes.append(dict(x=x, y=y, r=r, life=1300))

    def spawn_walls(self, n, kind="wall", near_player=False):
        for i in range(n):
            for _try in range(10):
                if near_player:
                    a = i * math.pi * 2 / n + random.uniform(-0.35, 0.35)
                    d = random.uniform(105, 150)
                    cx = max(70, min(830, self.px + math.cos(a) * d))
                    cy = max(70, min(830, self.py + math.sin(a) * d))
                    horiz = abs(math.sin(a)) > abs(math.cos(a))
                    w, h = (110, 26) if horiz else (26, 110)
                else:
                    a = random.uniform(0, 6.28)
                    d = random.uniform(130, 230)
                    cx = max(70, min(830, self.px + math.cos(a) * d))
                    cy = max(70, min(830, self.py + math.sin(a) * d))
                    w, h = (120, 26) if random.random() < 0.5 else (26, 120)
                rect = pygame.Rect(int(cx - w / 2), int(cy - h / 2), w, h)
                if rect.inflate(self.pr * 2 + 8, self.pr * 2 + 8).collidepoint(self.px, self.py):
                    continue
                self.walls.append(dict(rect=rect, t=70, life=420 if near_player else 360, kind=kind))
                break

    # ----------------------------------------------------------------- step
    def step_status(self):
        for k in ("root_t", "slow_t", "wound_t", "rad_t", "suppress_t", "dot_cd"):
            v = getattr(self, k)
            if v > 0:
                setattr(self, k, v - 1)
        if self.slow_t <= 0:
            self.slow_mult = 1.0

    def step_ebullets(self):
        keep = []
        walls = [w["rect"] for w in self.walls if w["t"] <= 0]
        pr = self.pr
        for b in self.ebullets:
            b.age += 1
            if b.decel and b.age > b.decel_after:
                b.vx *= b.decel
                b.vy *= b.decel
                if abs(b.vx) + abs(b.vy) < 0.18:
                    b.vx = b.vy = 0.0                      # hovering
            if b.homing and b.age < b.home_until:
                sp = math.hypot(b.vx, b.vy) or 1.0
                cur = math.atan2(b.vy, b.vx)
                want = math.atan2(self.py - b.y, self.px - b.x)
                da = (want - cur + math.pi) % (2 * math.pi) - math.pi
                cur += max(-b.homing, min(b.homing, da))
                b.vx, b.vy = math.cos(cur) * sp, math.sin(cur) * sp
            b.x += b.vx
            b.y += b.vy
            b.life -= 1
            dead = b.life <= 0 or b.x < -40 or b.x > SCREEN + 40 or b.y < -40 or b.y > SCREEN + 40
            if dead:
                if b.on_end == "sap" and 0 < b.x < SCREEN and 0 < b.y < SCREEN:
                    self.add_pool(b.x, b.y, 30, 220, "sap", 0)
                continue
            if walls and any(r.collidepoint(b.x, b.y) for r in walls):
                continue
            rr = pr + b.r - 2
            dx, dy = b.x - self.px, b.y - self.py
            if abs(dx) < rr and abs(dy) < rr and dx * dx + dy * dy < rr * rr:
                if self.dash_t > 0 or self.rev_invuln > 0 or self.invuln > 0:
                    keep.append(b)                      # i-frames: it passes through
                    continue
                self.hurt_player(b.dmg)
                if b.on_end == "sap":
                    self.add_pool(b.x, b.y, 30, 220, "sap", 0)
                    self.slow_player(90, 0.55)
                continue
            keep.append(b)
        self.ebullets = keep

    def step_lobs(self):
        keep = []
        for l in self.lobs:
            l["t"] += 1
            if l["t"] >= l["total"]:
                col = POOL_COL.get(l["pool_kind"], (150, 230, 70))
                self.fx.append(dict(kind="ring", x=l["tx"], y=l["ty"], r=6, max_r=l["r"], ttl=12, color=col))
                if math.hypot(self.px - l["tx"], self.py - l["ty"]) < l["r"] + self.pr:
                    self.hurt_player(l["dmg"], pierce=l["pierce"])
                pd = max(5, l["dmg"] * 0.35) if l["pool_kind"] == "fire" else 5
                self.add_pool(l["tx"], l["ty"], l["pool_r"], l["pool_life"], l["pool_kind"], pd)
            else:
                keep.append(l)
        self.lobs = keep

    def step_zones(self):
        keep = []
        for z in self.zones:
            z["t"] -= 1
            if z["t"] <= 0:
                self.resolve_zone(z)
            else:
                keep.append(z)
        self.zones = keep
        keep = []
        for q in self.ringq:
            q["t"] -= 1
            if q["t"] <= 0:
                for i in range(q["n"]):
                    a = i * 2 * math.pi / q["n"]
                    self.bushes.append(dict(x=q["x"] + math.cos(a) * q["radius"], y=q["y"] + math.sin(a) * q["radius"],
                                            r=17, hp=q["hp"], life=q["life"], dmg=q["dmg"], tick=0))
                self.fx.append(dict(kind="ring", x=q["x"], y=q["y"], r=10, max_r=q["radius"] + 20, ttl=14, color=(110, 190, 60)))
            else:
                keep.append(q)
        self.ringq = keep

    def step_pools(self):
        inside_any = False
        for p in self.pools:
            p["life"] -= 1
            p["tick"] += 1
            if math.hypot(self.px - p["x"], self.py - p["y"]) < p["r"] + self.pr - 4:
                k = p["kind"]
                if k == "sap":
                    self.slow_player(30, 0.55)
                elif k == "sludge":
                    self.slow_player(30, 0.8)
                    self.rad_t = max(self.rad_t, 60)
                elif k == "spore":
                    self.slow_player(20, 0.88)
                inside_any = True
                if p["tick"] % 30 == 0 and p["dmg"] > 0 and self.dot_cd <= 0:
                    self.hurt_player(p["dmg"] * (1.0 + (self.hz - 1) * 0.5), dot=True, pierce=0.3 if k == "fire" else 0.0)
                    self.dot_cd = 12
        self.pools = [p for p in self.pools if p["life"] > 0]
        # thorn bushes: solid, prickly, breakable
        for b in self.bushes:
            b["life"] -= 1
            if self.dash_t > 0:
                continue
            dx, dy = self.px - b["x"], self.py - b["y"]
            d = math.hypot(dx, dy)
            if d < b["r"] + self.pr:
                if d < 1:
                    dx, dy, d = 1.0, 0.0, 1.0
                push = b["r"] + self.pr - d
                self.px += dx / d * push
                self.py += dy / d * push
                b["tick"] += 1
                if b["tick"] % 30 == 1:
                    self.hurt_player(b["dmg"], dot=True)
        self.bushes = [b for b in self.bushes if b["life"] > 0 and b["hp"] > 0]

    def step_mines(self):
        keep = []
        for m in self.mines:
            m["t"] -= 1
            if m["t"] <= 0 or math.hypot(self.px - m["x"], self.py - m["y"]) < 24 + self.pr * 0.5:
                self.fx.append(dict(kind="ring", x=m["x"], y=m["y"], r=8, max_r=92, ttl=14, color=(255, 150, 60)))
                self.spark(m["x"], m["y"], (255, 170, 70), 10)
                self.shake = max(self.shake, 6)
                if math.hypot(self.px - m["x"], self.py - m["y"]) < 92 + self.pr:
                    self.hurt_player(32 * self.hz, pierce=0.2)
                continue
            keep.append(m)
        self.mines = keep

    def step_hazes(self):
        self.haze_now = False
        for h in self.hazes:
            h["life"] -= 1
            dx, dy = self.px - h["x"], self.py - h["y"]
            d = math.hypot(dx, dy) or 1.0
            h["x"] += dx / d * 0.55
            h["y"] += dy / d * 0.55
            if d < h["r"]:
                self.haze_now = True
        self.hazes = [h for h in self.hazes if h["life"] > 0]
        self.haze_in += ((1.0 if self.haze_now else 0.0) - self.haze_in) * 0.12

    def step_walls(self):
        for w in self.walls:
            if w["t"] > 0:
                w["t"] -= 1
            else:
                w["life"] -= 1
        self.walls = [w for w in self.walls if w["life"] > 0]

    def collide_walls(self):
        for w in self.walls:
            if w["t"] > 0:
                continue
            r = w["rect"]
            cx = max(r.left, min(self.px, r.right))
            cy = max(r.top, min(self.py, r.bottom))
            dx, dy = self.px - cx, self.py - cy
            d = math.hypot(dx, dy)
            if d < self.pr:
                if d == 0:
                    self.py -= self.pr
                else:
                    self.px += dx / d * (self.pr - d)
                    self.py += dy / d * (self.pr - d)

    # ----------------------------------------------------------------- draw
    def draw_world_under(self, surf, ox, oy):
        for p in self.pools:
            fade = min(1.0, p["life"] / 60.0)
            col = POOL_COL.get(p["kind"], (110, 200, 50))
            disc(surf, p["x"] + ox, p["y"] + oy, p["r"], col, int(120 * fade))
            pygame.draw.circle(surf, POOL_EDGE.get(p["kind"], (190, 255, 90)), (int(p["x"]) + ox, int(p["y"]) + oy), int(p["r"]), 2)
        for h in self.hazes:
            fade = min(1.0, h["life"] / 80.0)
            disc(surf, h["x"] + ox, h["y"] + oy, h["r"], (255, 190, 90), int(70 * fade))
            disc(surf, h["x"] + ox, h["y"] + oy, h["r"] * 0.6, (255, 150, 200), int(60 * fade))
            art.pixel_ring(surf, h["x"] + ox, h["y"] + oy, h["r"], (255, 220, 120), density=0.35)
        for z in self.zones:
            if z["total"] <= 2:
                continue
            col = ZONE_COL.get(z["kind"], (255, 90, 90))
            frac = 1 - z["t"] / float(z["total"])
            disc(surf, z["x"] + ox, z["y"] + oy, z["r"] * max(0.1, frac), col, 90)
            if (z["t"] // 4) % 2 == 0 or z["total"] < 24:
                art.pixel_ring(surf, z["x"] + ox, z["y"] + oy, z["r"], col, density=0.8)
        for q in self.ringq:
            if (q["t"] // 4) % 2 == 0:
                art.pixel_ring(surf, q["x"] + ox, q["y"] + oy, q["radius"], (255, 80, 80), density=0.9)
        for l in self.lobs:
            frac = l["t"] / float(l["total"])
            art.pixel_ring(surf, l["tx"] + ox, l["ty"] + oy, l["r"] * (0.35 + 0.65 * frac), (255, 80, 80), density=0.8)
            col = {"fire": (255, 140, 40)}.get(l["pool_kind"], (150, 230, 70))
            if l["arc"]:
                x = l["sx"] + (l["tx"] - l["sx"]) * frac
                y = l["sy"] + (l["ty"] - l["sy"]) * frac - math.sin(frac * math.pi) * 120
                art.pixel_disc(surf, x + ox, y + oy, 9, col)
            else:
                art.pixel_disc(surf, l["tx"] + ox, l["ty"] + oy - (1 - frac) * 260, 9, col)
        for m in self.mines:
            on = (m["t"] // max(4, m["t"] // 30)) % 2 == 0 if m["t"] < 240 else (m["t"] // 30) % 2 == 0
            art.pixel_disc(surf, m["x"] + ox, m["y"] + oy, 12, (60, 56, 70))
            art.pixel_disc(surf, m["x"] + ox, m["y"] + oy, 6, (255, 70, 50) if on else (120, 30, 30))
            if m["t"] < 150 and on:
                art.pixel_ring(surf, m["x"] + ox, m["y"] + oy, 92, (255, 110, 60), density=0.4)
        # beams: telegraphs first, live beams on top
        for x1, y1, x2, y2, w, dmg, active, col, thin, wide in self.beam_list:
            if active:
                continue
            if wide:
                self._band(surf, x1 + ox, y1 + oy, x2 + ox, y2 + oy, w, (84, 20, 26))
                art.pixel_line(surf, x1 + ox, y1 + oy, x2 + ox, y2 + oy, col)
            elif (self.frame // 3) % 2 == 0 or w > 10:
                art.pixel_line(surf, x1 + ox, y1 + oy, x2 + ox, y2 + oy, col)
        for x1, y1, x2, y2, w, dmg, active, col, thin, wide in self.beam_list:
            if not active:
                continue
            self._band(surf, x1 + ox, y1 + oy, x2 + ox, y2 + oy, w, col)
            self._band(surf, x1 + ox, y1 + oy, x2 + ox, y2 + oy, max(4, w * 0.4), (255, 252, 230))
        for w in self.walls:
            r = w["rect"].move(ox, oy)
            if w["t"] > 0:
                if (w["t"] // 5) % 2 == 0:
                    pygame.draw.rect(surf, (255, 90, 90), r, 3)
            elif w.get("kind") == "bone":
                pygame.draw.rect(surf, (200, 190, 168), r)
                pygame.draw.rect(surf, (250, 244, 228), r, 3)
                pygame.draw.rect(surf, (120, 110, 96), r.inflate(-12, -12), 2)
            else:
                pygame.draw.rect(surf, (96, 100, 130), r)
                pygame.draw.rect(surf, (150, 156, 190), r, 3)
                pygame.draw.rect(surf, (90, 230, 255), r.inflate(-14, -14), 2)
        for b in self.bushes:
            fade = b["life"] < 60 and (b["life"] // 4) % 2 == 0
            if not fade:
                art.pixel_disc(surf, b["x"] + ox, b["y"] + oy, b["r"], (50, 110, 44))
                art.pixel_disc(surf, b["x"] + ox, b["y"] + oy, b["r"] - 6, (110, 180, 70))
                for k in range(6):
                    a = k * 1.047 + b["x"]
                    surf.fill((220, 240, 160), (int(b["x"] + math.cos(a) * (b["r"] + 2)) + ox, int(b["y"] + math.sin(a) * (b["r"] + 2)) + oy, 3, 3))

    def _band(self, surf, x1, y1, x2, y2, w, color):
        dx, dy = x2 - x1, y2 - y1
        d = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / d * w / 2.0, dx / d * w / 2.0
        pygame.draw.polygon(surf, color, [(x1 + nx, y1 + ny), (x2 + nx, y2 + ny), (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)])

    def draw_fx(self, surf, ox, oy):
        for f in self.fx:
            k = f["kind"]
            if k == "ring":
                t0 = f.setdefault("t0", f["ttl"])
                rr = f["r"] + (f["max_r"] - f["r"]) * (1 - f["ttl"] / float(t0))
                art.pixel_ring(surf, f["x"] + ox, f["y"] + oy, rr, f["color"], density=0.9)
            elif k == "ringline":
                art.pixel_ring(surf, f["x"] + ox, f["y"] + oy, max(2, f["r"]), f["color"], density=0.8)
            elif k == "line":
                art.pixel_line(surf, f["x"] + ox, f["y"] + oy, f["x2"] + ox, f["y2"] + oy, f["color"])
            elif k == "beamflash":
                self._band(surf, f["x"] + ox, f["y"] + oy, f["x2"] + ox, f["y2"] + oy, 9, (255, 250, 200))
            elif k == "edgewarn":
                y = f["y"]
                for x in range(0, SCREEN, 24):
                    if any(abs(x + 12 - g) < 66 for g in f["gaps"]):
                        continue
                    surf.fill((255, 70, 70), (x, int(y) - 6, 18, 12))
            elif k == "edgewarn2":
                side, gaps = f["side"], f["gaps"]
                for p in range(0, SCREEN, 24):
                    if any(abs(p + 12 - g) < 66 for g in gaps):
                        continue
                    if (f["ttl"] // 4) % 2:
                        continue
                    if side == 0:
                        surf.fill((255, 70, 70), (p, 0, 18, 12))
                    elif side == 2:
                        surf.fill((255, 70, 70), (p, SCREEN - 12, 18, 12))
                    elif side == 3:
                        surf.fill((255, 70, 70), (0, p, 12, 18))
                    else:
                        surf.fill((255, 70, 70), (SCREEN - 12, p, 12, 18))
