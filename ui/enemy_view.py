"""
Project Strikers - UI layer: how enemies, mini-bosses and bosses are drawn.

Reads an `core.enemy.Enemy` (position, state, timers) and paints it. No game rules here.
"""
import math

import pygame

from ui import art


def scaled_sprite(img, k):
    w, h = img.get_size()
    return pygame.transform.scale(img, (max(1, int(w * k)), max(1, int(h * k))))


def enemy_sprite_mode(e):
    run = e.run
    if e.flash > 0:
        return "flash"
    if run.freeze > 0:
        return "frozen"
    if e.stone:
        return "stone"
    if e.ethereal:
        return "ghost"
    if e.ai == "vclone":
        return "ghost"
    if e.buffed and not (e.boss or e.mini):
        return "buffed"
    if e.ai in ("boss", "construct") and e.phase == 2:
        return "rage"
    return "normal"


def draw_enemy_tele(e, surf):
    """Ground telegraphs drawn beneath sprites."""
    run = e.run
    a = e.ai
    if a == "sniper" and e.state == "lock":
        if e.timer > 24 or (e.timer // 3) % 2 == 0:
            ex, ey = e.x + math.cos(e.aim) * 1400, e.y + math.sin(e.aim) * 1400
            art.pixel_line(surf, e.x, e.y, ex, ey, (255, 60, 60) if e.timer <= 24 else (255, 150, 150))
    elif a == "bull" and e.state == "windup":
        ex, ey = e.x + math.cos(e.aim) * 1000, e.y + math.sin(e.aim) * 1000
        if (e.timer // 4) % 2 == 0:
            art.pixel_line(surf, e.x, e.y, ex, ey, (255, 90, 60))
    elif a == "commander":
        pulse = 190 + int(4 * math.sin(e.t * 0.1))
        art.pixel_ring(surf, e.x, e.y, pulse, (255, 214, 80), density=0.45)
    elif a == "harvester" and e.state == "aim":
        if (e.timer // 3) % 2 == 0:
            ex, ey = e.x + math.cos(e.aim) * 560, e.y + math.sin(e.aim) * 560
            art.pixel_line(surf, e.x, e.y, ex, ey, (255, 90, 60))
    elif a == "treant" and e.state == "stomp" and (int(e.timer) // 3) % 2 == 0:
        f = e.hp / e.max_hp
        for off in ([0.0] if f > 0.5 else [-0.34, 0.0, 0.34]):
            art.pixel_line(surf, e.x, e.y, e.x + math.cos(e.aim + off) * 640,
                           e.y + math.sin(e.aim + off) * 640, (200, 120, 60))
    elif a == "necro":
        art.pixel_ring(surf, e.x, e.y, e.d["suppress"], (170, 90, 230), density=0.3)
    elif a == "boss" and e.state == "selfdestruct":
        pass
    elif a == "construct" and e.state == "selfdestruct":
        prog = 1 - e.sd_t / 180.0
        if (e.sd_t // 5) % 2 == 0:
            art.pixel_ring(surf, e.x, e.y, 430, (255, 60, 50), density=0.9)
        art.pixel_ring(surf, e.x, e.y, 430 * prog, (255, 200, 80), density=0.9)
        art.draw_text(surf, "%.1f" % (e.sd_t / 60.0), (int(e.x), int(e.y) - 120), 60, (255, 90, 70), title=True)
    elif a == "templar":
        art.pixel_ring(surf, e.x, e.y, 215, (120, 200, 255), density=0.3)
    elif a == "stalker":
        art.pixel_ring(surf, e.x, e.y, 175, (110, 230, 90), density=0.3)
    elif a == "vespera" and e.state == "nova":
        frac = e.nova_t / 600.0
        art.draw_bar(surf, (250, 60, 400, 14), frac, (255, 90, 200))
        if e.nova_t < 150:
            g = e.nova_gap
            for k in range(1, 8):
                art.pixel_line(surf, e.x + math.cos(g) * 80 * k * 0.4, e.y + math.sin(g) * 80 * k * 0.4,
                               e.x + math.cos(g) * 80 * (k * 0.4 + 0.2), e.y + math.sin(g) * 80 * (k * 0.4 + 0.2),
                               (120, 255, 150))
    elif a == "boss" and e.invuln:
        art.pixel_ring(surf, e.x, e.y, e.r + 24, (120, 220, 255), density=0.8)


def draw_enemy(e, surf, ox, oy):
    run = e.run
    cx, cy = int(e.x) + ox, int(e.y) + oy
    if e.ai == "burrow" and e.state in ("under", "tele"):
        for k in range(5):
            art.pixel_disc(surf, cx - e.facing * k * 7, cy + 6 + (k % 2) * 3, 5 - k // 2, (150, 112, 70))
        if e.state == "tele":
            art.pixel_ring(surf, cx, cy, 46 * (1 - e.timer / 34.0), (255, 80, 60), density=0.8)
        return
    if not e.hidden:
        if e.ai == "vespera" and run.dark > 0.55 and run.boss_flash <= 0 and e.state != "nova":
            pass
        elif e.ai == "vclone" and run.dark > 0.55 and run.boss_flash <= 0:
            pass
        else:
            spr = art.sprite(e.d["sprite"], enemy_sprite_mode(e), e.facing < 0)
            bob = 0 if e.ai in ("spinner", "boss") else int(math.sin(e.t * 0.2 + e.angle) * 2)
            if e.boss or e.mini:
                bob = int(math.sin(e.t * 0.08) * 4)
            if e.ai == "vclone":
                spr = scaled_sprite(spr, 0.85)
            surf.blit(spr, spr.get_rect(center=(cx, cy + bob)))
    if e.d.get("shield"):
        ang = math.atan2(e.sy, e.sx)
        art.pixel_arc(surf, cx, cy, e.r + 8, ang - 1.0, ang + 1.0, (190, 210, 235), thick=2)
        art.pixel_arc(surf, cx, cy, e.r + 14, ang - 0.8, ang + 0.8, (110, 140, 190), thick=1)
    elif e.d.get("front_armor") and not e.hidden:
        ang = math.atan2(e.sy, e.sx)
        art.pixel_arc(surf, cx, cy, e.r + 8, ang - 0.9, ang + 0.9, (170, 176, 210), thick=1)
    if e.eshield > 0:
        art.pixel_ring(surf, cx, cy, e.r + 6, (120, 220, 255), density=0.7)
    if e.invuln and (e.boss or e.mini):
        art.pixel_ring(surf, cx, cy, e.r + 14, (150, 230, 255), density=0.9)
    if e.stone:
        art.pixel_ring(surf, cx, cy, e.r + 10, (160, 160, 180), density=0.7)
    a = e.ai
    if a == "vortex":
        for k in range(3):
            ang = e.angle + k * 2.094
            art.pixel_disc(surf, cx + math.cos(ang) * 62, cy + math.sin(ang) * 62, 9, (255, 110, 220))
        art.pixel_ring(surf, cx, cy, 300, (150, 90, 220), density=0.25)
    elif a == "crawler" and e.state == "fuse" and (e.timer // 4) % 2 == 0:
        art.pixel_ring(surf, cx, cy, 78, (255, 100, 60), density=0.7)
    elif a == "pod":
        art.pixel_arc(surf, cx, cy, 30, -1.57, -1.57 + 6.28 * e.timer / 600.0, (255, 190, 60), thick=1)
    elif a == "harvester" and e.state in ("hook", "pull"):
        art.pixel_line(surf, cx, cy, int(e.hx) + ox, int(e.hy) + oy, (170, 170, 190))
        art.pixel_disc(surf, int(e.hx) + ox, int(e.hy) + oy, 9, (220, 220, 235))
    elif a == "executioner" and e.state == "chop":
        ex, ey = cx + math.cos(e.aim) * 38, cy + math.sin(e.aim) * 38
        art.pixel_ring(surf, ex, ey, 62 * (1 - e.timer / 26.0) + 4, (255, 90, 90), density=0.8)
    elif a == "stalker":
        pass
    if e.burn > 0:
        surf.fill((255, 120, 30), (cx - 3, cy - e.r - 8, 6, 6))
    if e.boss or e.mini or e.hidden:
        return
    if e.hp < e.max_hp or e.elite:
        w = max(24, e.r * 2)
        art.draw_bar(surf, (cx - w // 2, cy - e.r - 14, w, 7), e.hp / e.max_hp,
                     (214, 60, 60) if not e.elite else (190, 100, 240))
