"""
Project Strikers - UI layer: paints a Run.

`RunRenderer` only READS the state  (positions, timers, lists of bullets / pools / effects) and draws it.
"""
import math
import random

import pygame

from core import game_data as data
from core.run import SCREEN, TIME_FREEZE_CD
from core.util import abbr
from core.world import POOL_COL, POOL_EDGE, ZONE_COL
from ui import art
from ui.enemy_view import draw_enemy, draw_enemy_tele

_circ = {}
_SCALED = {}


def disc(surf, x, y, r, color, alpha):
    """Cached translucent filled circle."""
    r = max(2, int(r) // 2 * 2)
    key = (r, color, alpha // 12)
    s = _circ.get(key)
    if s is None:
        s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, color + (alpha,), (r, r), r)
        _circ[key] = s
    surf.blit(s, (int(x) - r, int(y) - r))


def scaled(img, m):
    """Cached copy of a sprite scaled by m (Big Hits perk)."""
    if m == 1.0:
        return img
    key = (id(img), round(m, 2))
    hit = _SCALED.get(key)
    if hit is None:
        w, h = img.get_size()
        hit = (img, pygame.transform.scale(img, (max(1, int(w * m)), max(1, int(h * m)))))
        _SCALED[key] = hit
    return hit[1]


class RunRenderer:
    def __init__(self, run):
        self.run = run
        self._dark_surf = None

    def draw(self, surf, bg):
        R = self.run
        ox = random.randint(-3, 3) if R.shake > 0 else 0
        oy = random.randint(-3, 3) if R.shake > 0 else 0
        surf.blit(bg, (ox, oy))
        if R.border:
            self.draw_border(surf)
        self.draw_world_under(surf, ox, oy)
        for pp in R.ppools:
            fade = min(1.0, pp["life"] / 50.0)
            disc(surf, pp["x"] + ox, pp["y"] + oy, pp["r"], (90, 220, 70), int(110 * fade))
            art.pixel_ring(surf, pp["x"] + ox, pp["y"] + oy, pp["r"], (190, 255, 120), density=0.5)
        for s in R.springs:
            fade = min(1.0, s["life"] / 50.0)
            disc(surf, s["x"] + ox, s["y"] + oy, s["r"], (90, 230, 150), int(80 * fade))
            art.pixel_ring(surf, s["x"] + ox, s["y"] + oy, s["r"], (190, 255, 220), density=0.5)
            for k in range(4):
                a = R.frame * 0.05 + k * 1.57
                surf.fill((220, 255, 240), (int(s["x"] + math.cos(a) * s["r"] * 0.6) + ox, int(s["y"] - ((R.frame + k * 15) % 60)) + oy, 4, 4))
            art.pixel_disc(surf, s["x"] + ox, s["y"] + oy, 12, (80, 170, 255))
        for b in R.blizzards:
            disc(surf, R.px + ox, R.py + oy, b["r"], (170, 220, 255), 55)
            art.pixel_ring(surf, R.px + ox, R.py + oy, b["r"], (210, 240, 255), density=0.5)
            for k in range(14):
                a = R.frame * 0.07 + k * 0.45
                rr = (k * 37 + R.frame * 2) % b["r"]
                surf.fill((255, 255, 255), (int(R.px + math.cos(a * 2 + k) * rr) + ox, int(R.py + math.sin(a * 2 + k) * rr) + oy, 4, 4))
        for tl in R.telegraphs:
            if (tl["t"] // 5) % 2 == 0:
                art.pixel_ring(surf, tl["x"] + ox, tl["y"] + oy, tl["r"], (255, 70, 70), density=0.8)
            art.pixel_disc(surf, tl["x"] + ox, tl["y"] + oy, 6, (255, 90, 90))
        for e in R.enemies:
            draw_enemy_tele(e, surf)
        for m in R.meteors:
            frac = 1 - m["t"] / float(m["total"])
            art.pixel_ring(surf, m["x"] + ox, m["y"] + oy, m["r"], (255, 90, 60), density=0.8)
            art.pixel_ring(surf, m["x"] + ox, m["y"] + oy, m["r"] * frac, (255, 200, 90), density=0.8)
        gem = art.misc("gem")
        for g in R.gems:
            surf.blit(gem, gem.get_rect(center=(int(g.x) + ox, int(g.y) + oy + int(math.sin(R.frame * 0.1 + g.x) * 2))))
        for g in R.coins:
            surf.blit(art.misc("coin"), art.misc("coin").get_rect(center=(int(g.x) + ox, int(g.y) + oy)))
        for g in R.foods:
            surf.blit(art.misc("food"), art.misc("food").get_rect(center=(int(g.x) + ox, int(g.y) + oy)))
        bn = R.S("burn_aura")
        if bn:
            art.pixel_ring(surf, R.px + ox, R.py + oy, R.aura_rad(), (255, 120, 40), density=0.5)
        for e in sorted(R.enemies, key=lambda q: q.y):
            draw_enemy(e, surf, ox, oy)
        for f in R.fx:
            if f["kind"] == "ghost":
                g = art.sprite("player", "ghost", R.facing < 0)
                surf.blit(g, g.get_rect(center=(int(f["x"]) + ox, int(f["y"]) + oy)))
        if R.sentry:
            art.pixel_disc(surf, R.sentry["x"] + ox, R.sentry["y"] + oy, 9, (120, 220, 255))
            art.pixel_ring(surf, R.sentry["x"] + ox, R.sentry["y"] + oy, 12, (255, 255, 255), density=0.6)
        if R.S("orbital_barrage"):
            n_orb = 3 + R.S("extra_barrel")
            for k in range(n_orb):
                a = R.orb_ang + k * 2 * math.pi / n_orb
                art.pixel_disc(surf, R.px + ox + math.cos(a) * 95, R.py + oy + math.sin(a) * 95, 9 * R.size_mult, (255, 190, 60))
        blink = R.invuln > 0 and (R.frame // 3) % 2 == 0
        if not blink:
            mode = "flash" if R.flash_p > 0 else "normal"
            spr = art.sprite("player", mode, R.facing < 0)
            bob = int(math.sin(R.frame * 0.2) * 2)
            surf.blit(spr, spr.get_rect(center=(int(R.px) + ox, int(R.py) + oy + bob)))
        if R.shield_ready:
            art.pixel_ring(surf, R.px + ox, R.py + oy, 32, (130, 210, 255), density=0.8)
        if R.bm_t > 0:
            art.pixel_ring(surf, R.px + ox, R.py + oy, 30 + (R.frame // 4) % 3 * 2, (220, 40, 80), density=0.7)
        if R.root_t > 0:
            art.pixel_ring(surf, R.px + ox, R.py + oy, 24, (190, 130, 255), density=0.9)
            art.pixel_ring(surf, R.px + ox, R.py + oy, 18, (130, 90, 200), density=0.9)
        if "spinning_swords" in R.weapons:
            sw = art.misc("sword")
            n_sw = 4 + R.S("extra_barrel")
            for k in range(n_sw):
                a = R.sword_ang + k * 2 * math.pi / n_sw
                img = scaled(art.rot(sw, a), R.size_mult)
                surf.blit(img, img.get_rect(center=(int(R.px + math.cos(a) * 80) + ox, int(R.py + math.sin(a) * 80) + oy)))
        for b in R.bullets:
            if b.img in ("arrow", "gunshot"):
                img = art.rot(art.misc(b.img), math.atan2(b.vy, b.vx))
            else:
                img = art.misc(b.img)
            img = scaled(img, R.size_mult)
            surf.blit(img, img.get_rect(center=(int(b.x) + ox, int(b.y) + oy)))
        axe = art.misc("axe")
        for a in R.axes:
            img = scaled(art.rot(axe, a["spin"]), R.size_mult)
            surf.blit(img, img.get_rect(center=(int(a["x"]) + ox, int(a["y"]) + oy)))
        pot = art.misc("potion")
        for p in R.potions:
            frac = p["t"] / float(p["total"])
            x = p["sx"] + (p["tx"] - p["sx"]) * frac
            y = p["sy"] + (p["ty"] - p["sy"]) * frac - math.sin(frac * math.pi) * 90
            img = scaled(art.rot(pot, frac * 14), R.size_mult)
            surf.blit(img, img.get_rect(center=(int(x) + ox, int(y) + oy)))
        for m in R.meteors:
            frac = m["t"] / float(m["total"])
            img = art.misc("meteor")
            surf.blit(img, img.get_rect(center=(int(m["x"]) + ox, int(m["y"] - frac * 520) + oy)))
        dark_on = R.dark > 0.03
        if not dark_on:
            self.draw_ebullets(surf, ox, oy)
        self.draw_fx(surf, ox, oy)
        for p in R.parts:
            surf.fill(p["color"], (int(p["x"]) + ox, int(p["y"]) + oy, 4, 4))
        for t in R.texts:
            art.draw_text(surf, t["text"], (int(t["x"]) + ox, int(t["y"]) + oy), 20, t["color"])
        if dark_on:
            self.draw_darkness(surf)
            self.draw_ebullets(surf, ox, oy)
        if R.haze_in > 0.02:
            v = art.vignette((230, 200, 90))
            v.set_alpha(int(255 * min(1.0, R.haze_in)))
            surf.blit(v, (0, 0))
        self.draw_hud(surf)

    def draw_ebullets(self, surf, ox, oy):
        R = self.run
        for b in R.ebullets:
            if abs(b.vx) + abs(b.vy) > 0.2:
                b.ang = math.atan2(b.vy, b.vx)
            img = art.bullet_img(b.kind, getattr(b, "ang", 0.0))
            surf.blit(img, img.get_rect(center=(int(b.x) + ox, int(b.y) + oy)))

    def draw_border(self, surf):
        R = self.run
        w = R.border_w
        pulse = 130 + int(60 * math.sin(R.frame * 0.1))
        col = (pulse, 30, 40)
        step = art.PIXEL * 4
        for i in range(0, SCREEN, step):
            surf.fill(col, (i, 0, 12, 12))
            surf.fill(col, (i, SCREEN - 12, 12, 12))
            surf.fill(col, (0, i, 12, 12))
            surf.fill(col, (SCREEN - 12, i, 12, 12))
        for k in range(1, max(4, int(w // 12))):
            a = max(8, int(70 * (1 - k * 12.0 / max(48.0, w))))
            s = pygame.Surface((SCREEN, 12), pygame.SRCALPHA)
            s.fill((200, 30, 40, a))
            surf.blit(s, (0, k * 12))
            surf.blit(s, (0, SCREEN - 12 - k * 12))
            s2 = pygame.Surface((12, SCREEN), pygame.SRCALPHA)
            s2.fill((200, 30, 40, a))
            surf.blit(s2, (k * 12, 0))
            surf.blit(s2, (SCREEN - 12 - k * 12, 0))

    def draw_darkness(self, surf):
        R = self.run
        """Eclipse Realm: everything black except a glow around the player and brief flashes at Vespera."""
        if self._dark_surf is None:
            self._dark_surf = pygame.Surface((SCREEN // 2, SCREEN // 2), pygame.SRCALPHA)
        ds = self._dark_surf
        ds.fill((4, 2, 12, int(236 * min(1.0, R.dark))))
        hole = art.light_hole(66)
        ds.blit(hole, (int(R.px / 2) - 66, int(R.py / 2) - 66), special_flags=pygame.BLEND_RGBA_MIN)
        if R.boss_flash > 0:
            h2 = art.light_hole(30)
            for e in R.enemies:
                if e.ai in ("vespera", "vclone") and not e.dying:
                    ds.blit(h2, (int(e.x / 2) - 30, int(e.y / 2) - 30), special_flags=pygame.BLEND_RGBA_MIN)
        surf.blit(pygame.transform.scale(ds, (SCREEN, SCREEN)), (0, 0))

    def draw_hud(self, surf):
        R = self.run
        surf.blit(art.misc("heart"), (24, 22))
        art.draw_bar(surf, (60, 22, 270, 26), R.hp / R.max_hp, (206, 52, 62))
        art.draw_text(surf, "%d / %d" % (max(0, R.hp), R.max_hp), (195, 35), 18, art.CREAM)
        art.draw_text(surf, "Lv %d" % R.level, (28, 62), 24, art.GOLD, "topleft")
        surf.blit(art.misc("coin_ui"), (28, 92))
        art.draw_text(surf, str(R.gold), (56, 92), 22, art.GOLD, "topleft")
        y = 124
        if R.P("dash"):
            ready = R.dash_cd <= 0
            art.draw_bar(surf, (28, y, 110, 14), 1.0 - R.dash_cd / float(max(1, R.dash_cooldown())), (100, 200, 255) if ready else (80, 110, 150))
            art.draw_text(surf, "DASH", (142, y + 7), 14, art.CREAM, "midleft")
            y += 22
        tags = []
        if R.wound_t > 0:
            tags.append(("WOUNDED  heal -50%", (255, 110, 110)))
        if R.rad_t > 0:
            tags.append(("IRRADIATED  regen -50%", (130, 255, 120)))
        if R.suppress_t > 0:
            tags.append(("SUPPRESSED  speed/cooldowns -50%", (190, 130, 255)))
        if R.slow_t > 0:
            tags.append(("SLOWED", (150, 200, 255)))
        if R.root_t > 0:
            tags.append(("ROOTED  (dash breaks free)", (210, 160, 255)))
        if R.bm_t > 0:
            tags.append(("BLOOD MAGIC  attack x2  %ds" % (R.bm_t // 60 + 1), (255, 90, 120)))
        if R.S("glass_cannon"):
            tags.append(("GLASS CANNON", (255, 190, 120)))
        for text, col in tags:
            art.draw_text(surf, text, (28, y), 15, col, "topleft")
            y += 18
        # timer plate (no wave names any more; new enemies are announced instead)
        shown = max(0, R.map["duration"] - R.time) if not R.boss_spawned else 0
        mm, ss = divmod(int(shown), 60)
        art.draw_panel(surf, (370, 14, 160, 46), art.PANEL_FILL, art.GOLD_DK)
        art.draw_text(surf, "BOSS" if R.boss_spawned else "%02d:%02d" % (mm, ss), (450, 37), 30, art.CREAM)
        # boss / mini-boss bar
        tgt, col = None, (190, 60, 220)
        if R.boss and not R.boss.remove and R.boss.state != "intro":
            tgt = R.boss
        elif R.mini and not R.mini.remove:
            tgt, col = R.mini, (230, 160, 60)
        if tgt is not None:
            art.draw_text(surf, tgt.d["name"], (450, 76), 17, art.CREAM)
            art.draw_bar(surf, (200, 88, 500, 20), max(0, tgt.hp) / tgt.max_hp, col, segs=10)
            if tgt.invuln or tgt.stone:
                art.draw_text(surf, "INVULNERABLE", (450, 120), 14, (150, 230, 255))
            if tgt.adapt > 0.08:
                art.draw_text(surf, "ADAPTIVE ARMOR -%d%%" % int(tgt.adapt * 100), (200, 120), 14, (255, 200, 120), "midleft")
            if tgt.enraged:
                art.draw_text(surf, "ENRAGED", (700, 120), 14, (255, 90, 70), "midright")
        # weapons panel (separate from the skill chips)
        art.draw_panel(surf, (8, 812, 124, 62), art.PANEL_FILL, art.GOLD_DK)
        art.draw_text(surf, "WEAPONS %d/%d" % (len(R.weapons), data.MAX_WEAPONS), (70, 823), 13, art.PARCHMENT, shadow=False)
        for i in range(data.MAX_WEAPONS):
            bx = 16 + i * 38
            pygame.draw.rect(surf, art.SHADOW, (bx, 834, 32, 32))
            if i < len(R.weapons):
                sk = data.SKILL_BY_ID[R.weapons[i]]
                c = art.RARITY_COLORS[sk["rarity"]]
                ic = art.icon(R.weapons[i])
                if ic:
                    surf.blit(ic, (bx + 4, 838))
                pygame.draw.rect(surf, c, (bx, 834, 32, 32), 2)
            else:
                pygame.draw.rect(surf, (70, 60, 76), (bx, 834, 32, 32), 1)
        # passive skill chips
        x, row = 142, 0
        for sid, n in R.skills.items():
            sk = data.SKILL_BY_ID[sid]
            if sk["slot"]:
                continue
            c = art.RARITY_COLORS[sk["rarity"]]
            if x > 690:
                x, row = 142, row + 1
            cy = 846 - row * 32
            pygame.draw.rect(surf, art.SHADOW, (x, cy, 28, 28))
            pygame.draw.rect(surf, c, (x + 2, cy + 2, 24, 24), 2)
            art.draw_text(surf, abbr(sk["name"]), (x + 14, cy + 14), 12, c, shadow=False)
            if n > 1:
                art.draw_text(surf, str(n), (x + 27, cy + 27), 12, art.CREAM, "bottomright")
            x += 30
        # active skills (keys 1-3)
        art.draw_panel(surf, (704, 798, 190, 76), art.PANEL_FILL, art.GOLD_DK)
        art.draw_text(surf, "ACTIVE SKILLS %d/%d" % (len(R.actives), data.MAX_ACTIVES), (799, 808), 13, art.PARCHMENT, shadow=False)
        key_i = 0
        for i in range(data.MAX_ACTIVES):
            bx = 712 + i * 60
            pygame.draw.rect(surf, art.SHADOW, (bx, 818, 52, 50))
            if i < len(R.actives):
                sid = R.actives[i]
                sk = data.SKILL_BY_ID[sid]
                c = art.RARITY_COLORS[sk["rarity"]]
                ic = art.icon(sid)
                if ic:
                    surf.blit(ic, (bx + 14, 822))
                if sid in data.AUTO_ACTIVES:
                    cdv = R.tf_cd
                    if cdv > 0:
                        h = max(1, int(50 * cdv / float(TIME_FREEZE_CD)))
                        s = pygame.Surface((52, h), pygame.SRCALPHA)
                        s.fill((10, 8, 16, 190))
                        surf.blit(s, (bx, 818))
                        sec = int(cdv / 60.0 + 0.99)
                        art.draw_text(surf, "%d:%02d" % divmod(sec, 60), (bx + 26, 846), 16, art.CREAM)
                    else:
                        art.draw_text(surf, "AUTO", (bx + 26, 859), 13, (170, 225, 255), shadow=False)
                else:
                    key_i += 1
                    cdv = R.cds.get(sid, 0)
                    total = data.ACTIVE_COOLDOWN.get(sid, 20) * 60.0
                    if cdv > 0:
                        h = max(1, int(50 * cdv / total))
                        s = pygame.Surface((52, h), pygame.SRCALPHA)
                        s.fill((10, 8, 16, 190))
                        surf.blit(s, (bx, 818))
                        art.draw_text(surf, "%d" % (cdv / 60.0 + 0.99), (bx + 26, 846), 20, art.CREAM)
                    else:
                        art.draw_text(surf, "READY", (bx + 26, 859), 12, (140, 255, 160), shadow=False)
                    art.draw_text(surf, str(key_i), (bx + 6, 822), 16, art.GOLD, "topleft")
                pygame.draw.rect(surf, c, (bx, 818, 52, 50), 2)
            else:
                pygame.draw.rect(surf, (70, 60, 76), (bx, 818, 52, 50), 1)
        # exp bar
        art.draw_bar(surf, (0, SCREEN - 20, SCREEN, 20), R.exp / float(data.exp_needed(R.level)), (90, 170, 255))
        # toasts, announcements & banners
        ty = 150
        for t in R.toasts:
            art.draw_text(surf, t["text"], (450, ty), 20, t["color"])
            ty += 24
        ay = 215
        for a in R.announces:
            al = min(1.0, a["ttl"] / 30.0)
            col = tuple(int(c * al + 20 * (1 - al)) for c in a["color"])
            art.draw_text(surf, a["text"], (450, ay), 34, col, title=True)
            ay += 40
        for b in R.banners:
            al = min(1.0, b["ttl"] / 30.0)
            col = tuple(int(c * al + 20 * (1 - al)) for c in b["color"])
            art.draw_text(surf, b["text"], (450, 330), 44, col, title=True)

    def draw_world_under(self, surf, ox, oy):
        R = self.run
        for p in R.pools:
            fade = min(1.0, p["life"] / 60.0)
            col = POOL_COL.get(p["kind"], (110, 200, 50))
            disc(surf, p["x"] + ox, p["y"] + oy, p["r"], col, int(120 * fade))
            pygame.draw.circle(surf, POOL_EDGE.get(p["kind"], (190, 255, 90)), (int(p["x"]) + ox, int(p["y"]) + oy), int(p["r"]), 2)
        for h in R.hazes:
            fade = min(1.0, h["life"] / 80.0)
            disc(surf, h["x"] + ox, h["y"] + oy, h["r"], (255, 190, 90), int(70 * fade))
            disc(surf, h["x"] + ox, h["y"] + oy, h["r"] * 0.6, (255, 150, 200), int(60 * fade))
            art.pixel_ring(surf, h["x"] + ox, h["y"] + oy, h["r"], (255, 220, 120), density=0.35)
        for z in R.zones:
            if z["total"] <= 2:
                continue
            col = ZONE_COL.get(z["kind"], (255, 90, 90))
            frac = 1 - z["t"] / float(z["total"])
            disc(surf, z["x"] + ox, z["y"] + oy, z["r"] * max(0.1, frac), col, 90)
            if (z["t"] // 4) % 2 == 0 or z["total"] < 24:
                art.pixel_ring(surf, z["x"] + ox, z["y"] + oy, z["r"], col, density=0.8)
        for q in R.ringq:
            if (q["t"] // 4) % 2 == 0:
                art.pixel_ring(surf, q["x"] + ox, q["y"] + oy, q["radius"], (255, 80, 80), density=0.9)
        for l in R.lobs:
            frac = l["t"] / float(l["total"])
            art.pixel_ring(surf, l["tx"] + ox, l["ty"] + oy, l["r"] * (0.35 + 0.65 * frac), (255, 80, 80), density=0.8)
            col = {"fire": (255, 140, 40)}.get(l["pool_kind"], (150, 230, 70))
            if l["arc"]:
                x = l["sx"] + (l["tx"] - l["sx"]) * frac
                y = l["sy"] + (l["ty"] - l["sy"]) * frac - math.sin(frac * math.pi) * 120
                art.pixel_disc(surf, x + ox, y + oy, 9, col)
            else:
                art.pixel_disc(surf, l["tx"] + ox, l["ty"] + oy - (1 - frac) * 260, 9, col)
        for m in R.mines:
            on = (m["t"] // max(4, m["t"] // 30)) % 2 == 0 if m["t"] < 240 else (m["t"] // 30) % 2 == 0
            art.pixel_disc(surf, m["x"] + ox, m["y"] + oy, 12, (60, 56, 70))
            art.pixel_disc(surf, m["x"] + ox, m["y"] + oy, 6, (255, 70, 50) if on else (120, 30, 30))
            if m["t"] < 150 and on:
                art.pixel_ring(surf, m["x"] + ox, m["y"] + oy, 92, (255, 110, 60), density=0.4)
        # beams: telegraphs first, live beams on top
        for x1, y1, x2, y2, w, dmg, active, col, thin, wide in R.beam_list:
            if active:
                continue
            if wide:
                self._band(surf, x1 + ox, y1 + oy, x2 + ox, y2 + oy, w, (84, 20, 26))
                art.pixel_line(surf, x1 + ox, y1 + oy, x2 + ox, y2 + oy, col)
            elif (R.frame // 3) % 2 == 0 or w > 10:
                art.pixel_line(surf, x1 + ox, y1 + oy, x2 + ox, y2 + oy, col)
        for x1, y1, x2, y2, w, dmg, active, col, thin, wide in R.beam_list:
            if not active:
                continue
            self._band(surf, x1 + ox, y1 + oy, x2 + ox, y2 + oy, w, col)
            self._band(surf, x1 + ox, y1 + oy, x2 + ox, y2 + oy, max(4, w * 0.4), (255, 252, 230))
        for w in R.walls:
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
        for b in R.bushes:
            fade = b["life"] < 60 and (b["life"] // 4) % 2 == 0
            if not fade:
                art.pixel_disc(surf, b["x"] + ox, b["y"] + oy, b["r"], (50, 110, 44))
                art.pixel_disc(surf, b["x"] + ox, b["y"] + oy, b["r"] - 6, (110, 180, 70))
                for k in range(6):
                    a = k * 1.047 + b["x"]
                    surf.fill((220, 240, 160), (int(b["x"] + math.cos(a) * (b["r"] + 2)) + ox, int(b["y"] + math.sin(a) * (b["r"] + 2)) + oy, 3, 3))

    def _band(self, surf, x1, y1, x2, y2, w, color):
        R = self.run
        dx, dy = x2 - x1, y2 - y1
        d = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / d * w / 2.0, dx / d * w / 2.0
        pygame.draw.polygon(surf, color, [(x1 + nx, y1 + ny), (x2 + nx, y2 + ny), (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)])

    def draw_fx(self, surf, ox, oy):
        R = self.run
        for f in R.fx:
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
