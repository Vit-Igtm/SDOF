"""
Project Strikers - every enemy, mini-boss and boss.

"""
import math
import random

import strikers_art as art
import strikers_data as data
from strikers_util import clamp, seg_dist, wrap_angle

SCREEN = 900
TAU = math.pi * 2
BOSS_ENRAGE_FRAMES = 150 * 60      # soft enrage: +40% speed, much faster attacks
MINI_ENRAGE_FRAMES = 100 * 60


class Enemy:
    def __init__(self, run, kind, x, y, heading=None):
        d = data.ENEMIES[kind]
        self.d, self.run, self.kind = d, run, kind
        self.x, self.y, self.r = float(x), float(y), d["r"]
        diff = run.diff
        self.mini, self.boss = d.get("mini", False), d.get("boss", False)
        if self.boss:
            hp, dmgm = d["hp"] * diff, 1 + (diff - 1) * 0.6
        elif self.mini:
            hp, dmgm = d["hp"] * diff * (1 + 0.05 * run.time / 60.0), 1 + (diff - 1) * 0.6
        elif d.get("fixed_hp"):
            hp, dmgm = d["hp"], 1 + (diff - 1) * 0.3
        else:
            hp, dmgm = d["hp"] * run.hp_scale(), run.dmg_scale()
        self.max_hp = hp
        self.hp = hp
        self.speed0 = d["speed"]
        self.speed = d["speed"]
        self.dmg = d["dmg"] * dmgm
        self.armor = d.get("armor", 0.0)
        self.threat = d["cost"]
        self.elite = d.get("elite", False)
        self.ai = d["ai"]
        self.t = 0
        self.flash = 0
        self.dying = False
        self.remove = False
        self.intangible = False        # cannot be hit or targeted (underground, ethereal, off-screen)
        self.invuln = False            # takes no damage (shielded) but can be targeted
        self.stone = False
        self.hidden = False
        self.ethereal = False
        self.kbx = self.kby = 0.0
        self.burn = 0
        self.orb_cd = 0
        self.sw_cd = 0
        self.slow_t = 0
        self.buffed = False
        self.eshield = 0.0
        self.shield_cd = 0
        self.facing = 1
        self.state = "walk"
        self.timer = random.randint(40, 140)
        self.vx = self.vy = 0.0
        self.offx, self.offy = random.uniform(-30, 30), random.uniform(-30, 30)
        self.sx, self.sy = 0.0, 1.0
        self.strafe = random.choice((-1, 1))
        self.aim = 0.0
        self.angle = random.uniform(0, TAU)
        self.boss_ref = None
        self.guards = []
        self.adds = []
        self.clones = []
        self.fight_t = 0
        self.enraged = False
        self.phase = 1
        self.pierce = d.get("pierce", 0.0)
        if self.ai == "straight" and heading is None:
            heading = math.atan2(run.py - y, run.px - x) + random.uniform(-0.18, 0.18)
        if self.ai == "straight":
            self.vx, self.vy = math.cos(heading) * self.speed0, math.sin(heading) * self.speed0
        init = getattr(self, "init_" + self.ai, None)
        if init:
            init()

    # ------------------------------------------------------------- helpers
    @property
    def untargetable(self):
        return self.intangible or self.invuln or self.stone or self.dying or self.remove

    def tempo(self):
        t = 1.0
        if self.mini or self.boss:
            f = self.hp / self.max_hp
            if f < 0.5:
                t *= 1.15
            if f < 0.25:
                t *= 1.15
            if self.enraged:
                t *= 1.7
            t *= 1.0 + (self.run.diff - 1.0) * 0.35        # later maps attack a little faster
        return t

    def toward(self, tx, ty, speed):
        dx, dy = tx - self.x, ty - self.y
        dist = math.hypot(dx, dy) or 1.0
        self.x += dx / dist * speed
        self.y += dy / dist * speed
        if abs(dx) > 1:
            self.facing = 1 if dx > 0 else -1
        return dist

    def sp(self):
        return self.speed * (1.3 if self.buffed else 1.0)

    def dist_p(self):
        return math.hypot(self.run.px - self.x, self.run.py - self.y)

    def ang_p(self):
        return math.atan2(self.run.py - self.y, self.run.px - self.x)

    def face_p(self):
        self.facing = 1 if self.run.px > self.x else -1

    def keep_distance(self, dmin, dmax, k=1.0):
        run = self.run
        dx, dy = run.px - self.x, run.py - self.y
        dist = math.hypot(dx, dy) or 1.0
        s = self.sp() * k
        if dist > dmax:
            self.x += dx / dist * s
            self.y += dy / dist * s
        elif dist < dmin:
            self.x -= dx / dist * s
            self.y -= dy / dist * s
        else:
            self.x += -dy / dist * s * 0.5 * self.strafe
            self.y += dx / dist * s * 0.5 * self.strafe
            if random.random() < 0.004:
                self.strafe *= -1
        if dx:
            self.facing = 1 if dx > 0 else -1
        if self.t > 90:
            m = 30 + (run.border_w if run.border else 0)
            self.x = clamp(self.x, m, SCREEN - m)
            self.y = clamp(self.y, m, SCREEN - m)
        return dist

    def stay_in(self, m=40):
        self.x = clamp(self.x, m, SCREEN - m)
        self.y = clamp(self.y, m, SCREEN - m)

    def front_reduction(self, bx, by):
        """Fraction of damage ignored for a projectile at (bx, by): 1 = fully blocked."""
        fa = 1.0 if self.d.get("shield") else self.d.get("front_armor", 0.0)
        if not fa:
            return 0.0
        dx, dy = bx - self.x, by - self.y
        dist = math.hypot(dx, dy) or 1.0
        return fa if (dx * self.sx + dy * self.sy) / dist > 0.3 else 0.0

    def contact_dmg(self):
        if self.d.get("nocontact") or self.intangible or self.hidden:
            return 0
        a = self.ai
        if a == "bull" and self.state == "dash":
            return self.dmg * 1.6
        if a == "boss":
            return 34 if self.state == "dash" else 16
        if a == "dreadnought" and self.state == "rev":
            return self.dmg * 1.8
        if a == "construct":
            return self.dmg
        if a == "executioner" and self.state in ("walk", "recover"):
            return self.dmg * 0.6
        return self.dmg

    # -------------------------------------------------------------- update
    def update(self):
        run = self.run
        self.t += 1
        if self.flash:
            self.flash -= 1
        if self.orb_cd:
            self.orb_cd -= 1
        if self.sw_cd:
            self.sw_cd -= 1
        if self.shield_cd:
            self.shield_cd -= 1
        self.speed = self.speed0
        if self.slow_t > 0:
            self.slow_t -= 1
            self.speed *= 0.55
        if self.kbx or self.kby:
            k = 0.1 if (self.boss or self.mini) else 1.0
            self.x += self.kbx * k
            self.y += self.kby * k
            self.kbx *= 0.8
            self.kby *= 0.8
            if abs(self.kbx) < 0.1 and abs(self.kby) < 0.1:
                self.kbx = self.kby = 0.0
        if self.burn > 0:
            self.burn -= 1
            if self.burn % 30 == 0:
                run.damage_enemy(self, run.burn_dmg(), False, "aoe")
        if (self.mini or self.boss) and self.state != "intro":
            self.fight_t += 1
            lim = BOSS_ENRAGE_FRAMES if self.boss else MINI_ENRAGE_FRAMES
            if not self.enraged and self.fight_t > lim:
                self.enraged = True
                self.speed0 *= 1.4
                run.banner("ENRAGED!", (255, 70, 60), 120)
        sup = self.d.get("suppress")
        if sup and not self.dying and self.dist_p() < sup:
            run.suppress_t = 4
        if self.eshield > 0 and self.ai == "templar":
            self.eshield = 0
        getattr(self, "ai_" + self.ai)()
        if self.d.get("shield") or self.d.get("front_armor"):
            dx, dy = run.px - self.x, run.py - self.y
            dist = math.hypot(dx, dy) or 1.0
            self.sx, self.sy = dx / dist, dy / dist

    def pre_death(self):
        """Return True to cancel death (e.g. Construct Zero's self-destruct)."""
        if self.ai == "construct" and not self.sd_done:
            self.state, self.sd_t, self.invuln = "selfdestruct", 180, True
            self.run.banner("SELF-DESTRUCT PROTOCOL!", (255, 70, 60), 180)
            self.run.ebullets = []
            return True
        return False

    def on_damaged(self):
        if self.ai == "vespera" and self.clones:
            for c in self.clones:
                if not c.remove:
                    c.remove = True
                    self.run.fx.append(dict(kind="ring", x=c.x, y=c.y, r=4, max_r=30, ttl=14, color=(190, 120, 255)))
            self.clones = []

    # ======================================================== FOREST (classic)
    def ai_straight(self):
        self.x += self.vx
        self.y += self.vy
        if self.vx:
            self.facing = 1 if self.vx > 0 else -1
        if self.t > 40 and (self.x < -150 or self.x > 1050 or self.y < -150 or self.y > 1050):
            self.remove = True

    def ai_chase(self):
        run = self.run
        dist = self.dist_p()
        k = min(1.0, dist / 220.0)
        self.toward(run.px + self.offx * k, run.py + self.offy * k, self.sp())

    def ai_crawler(self):
        run = self.run
        if self.state == "walk":
            if self.toward(run.px, run.py, self.sp()) < 88:
                self.state, self.timer = "fuse", 42
        else:
            self.timer -= 1
            self.toward(run.px, run.py, self.speed * 0.3)
            if self.timer <= 0:
                run.explode(self.x, self.y, 78, self.dmg)
                self.remove = True

    def ai_mortar(self):
        self.keep_distance(300, 430)
        self.timer -= 1
        if self.timer <= 0:
            self.run.add_lob(self.x, self.y, self.run.px, self.run.py, 75, 36, self.dmg, 46, 300)
            self.timer = random.randint(190, 250)

    def ai_sniper(self):
        run = self.run
        if self.state == "walk":
            self.keep_distance(340, 460)
            self.timer -= 1
            if self.timer <= 0:
                self.state, self.timer = "lock", 120
        else:
            self.timer -= 1
            if self.timer > 24:
                self.aim = math.atan2(run.py - self.y, run.px - self.x)
            if self.timer <= 0:
                run.fire_beam(self.x, self.y, self.aim, self.dmg)
                self.state, self.timer = "walk", random.randint(220, 300)

    def ai_spinner(self):
        run = self.run
        if self.t > 1500:
            self.remove = True
            return
        if self.t % 7 == 0:
            self.aim += 0.31
            for k in range(2):
                run.fire_ebullet(self.x, self.y, self.aim + k * math.pi, 2.2, self.dmg, "orb_p", 6, strict=True)

    def ai_vortex(self):
        run = self.run
        dist = self.toward(run.px, run.py, self.sp())
        if dist < 300:
            run.pull_player(self.x, self.y, 0.7 + 1.4 * (1 - dist / 300.0))
        self.angle += 0.06
        for k in range(3):
            a = self.angle + k * 2.094
            bx, by = self.x + math.cos(a) * 62, self.y + math.sin(a) * 62
            if math.hypot(run.px - bx, run.py - by) < run.pr + 9:
                run.hurt_player(self.dmg)

    def ai_bull(self):
        run = self.run
        if self.state == "walk":
            self.toward(run.px, run.py, self.sp())
            self.timer -= 1
            if self.timer <= 0:
                self.state, self.timer = "windup", 55
                self.aim = math.atan2(run.py - self.y, run.px - self.x)
        elif self.state == "windup":
            self.timer -= 1
            if self.timer <= 0:
                self.state, self.timer = "dash", 75
        elif self.state == "dash":
            self.x += math.cos(self.aim) * 10.5
            self.y += math.sin(self.aim) * 10.5
            self.facing = 1 if math.cos(self.aim) > 0 else -1
            self.timer -= 1
            if self.timer <= 0 or self.x < -120 or self.x > 1020 or self.y < -120 or self.y > 1020:
                self.state, self.timer = "recover", 40
        else:
            self.timer -= 1
            self.toward(run.px, run.py, self.speed * 0.6)
            if self.timer <= 0:
                self.state, self.timer = "walk", random.randint(150, 240)

    def ai_necro(self):
        run = self.run
        self.keep_distance(380, 480)
        self.timer -= 1
        if self.timer <= 0 and len(run.enemies) < 260:
            for _ in range(4):
                run.spawn_enemy("swarmer", self.x + random.uniform(-30, 30), self.y + random.uniform(-30, 30))
            run.fx.append(dict(kind="ring", x=self.x, y=self.y, r=10, max_r=70, ttl=24, color=(170, 90, 230)))
            self.timer = 210

    def ai_wallsum(self):
        self.keep_distance(330, 430)
        self.timer -= 1
        if self.timer <= 0:
            self.run.spawn_walls(3)
            self.timer = 290

    def ai_commander(self):
        self.ai_chase()

    def ai_pod(self):
        self.timer -= 1
        if self.timer <= 0:
            for _ in range(12):
                self.run.spawn_enemy("swarmer", self.x + random.uniform(-20, 20), self.y + random.uniform(-20, 20))
            self.run.fx.append(dict(kind="ring", x=self.x, y=self.y, r=10, max_r=90, ttl=24, color=(255, 170, 50)))
            self.remove = True

    def init_pod(self):
        self.timer = 600

    def ai_guard(self):
        b = self.boss_ref
        if b is None or b.remove or b.dying:
            self.remove = True
            return
        self.angle += 0.012
        self.x = b.x + math.cos(self.angle) * 135
        self.y = b.y + math.sin(self.angle) * 135
        self.face_p()

    # ======================================================== WASTELAND mobs
    def ai_hornet(self):
        run = self.run
        if self.state == "walk":
            self.keep_distance(240, 330)
            self.timer -= 1
            if self.timer <= 0:
                self.state, self.timer = "shoot", 36
        elif self.state == "shoot":
            self.keep_distance(240, 330, 0.5)
            self.timer -= 1
            if self.timer in (30, 20, 10):
                a = run.lead_angle(self.x, self.y, 3.6)
                run.fire_ebullet(self.x, self.y, a, 3.6, self.dmg, "sting", 5, strict=True, life=240)
            if self.timer <= 0:
                a = random.uniform(0, TAU)
                self.vx, self.vy = math.cos(a) * 7.0, math.sin(a) * 7.0
                self.state, self.timer = "dart", 18
        else:
            self.x += self.vx
            self.y += self.vy
            self.timer -= 1
            if self.vx:
                self.facing = 1 if self.vx > 0 else -1
            if self.t > 90:
                self.stay_in(40)
            if self.timer <= 0:
                self.state, self.timer = "walk", random.randint(80, 140)

    def init_hornet(self):
        self.state, self.timer = "walk", random.randint(40, 100)

    def init_burrow(self):
        self.state, self.timer = "under", 0
        self.intangible = True

    def ai_burrow(self):
        run = self.run
        if self.state == "under":
            d = self.toward(run.px, run.py, 3.2)
            if d < 52:
                self.state, self.timer = "tele", 34
        elif self.state == "tele":                 # shaking ground, then pop up
            self.timer -= 1
            if self.timer <= 0:
                self.intangible = False
                run.explode(self.x, self.y, 46, self.dmg)
                self.state, self.timer = "up", 330
        elif self.state == "up":
            self.ai_chase()
            self.timer -= 1
            if self.timer <= 0 and self.dist_p() > 140:
                self.state, self.intangible = "under", True

    def ai_slag(self):
        run = self.run
        self.keep_distance(300, 420)
        self.timer -= 1
        if self.timer <= 0:
            for k in range(2):
                tx, ty = run.px + run.pvx * 50, run.py + run.pvy * 50
                if k:
                    tx += random.uniform(-90, 90)
                    ty += random.uniform(-90, 90)
                run.add_lob(self.x, self.y, clamp(tx, 30, 870), clamp(ty, 30, 870), 70 + k * 12, 40, self.dmg, 54, 520,
                            pool_kind="fire", pierce=0.5)
            self.timer = random.randint(170, 230)

    def init_harvester(self):
        self.state, self.timer = "walk", random.randint(80, 140)
        self.hx = self.hy = 0.0
        self.hvx = self.hvy = 0.0
        self.ht = 0

    def ai_harvester(self):
        run = self.run
        if self.state == "walk":
            self.keep_distance(250, 380)
            self.timer -= 1
            if self.timer <= 0:
                self.state, self.timer = "aim", 54
                self.aim = self.ang_p()
                for k in range(6):                   # the swarm waiting at the end of the hook
                    a = k * TAU / 6
                    run.spawn_enemy("scrapswarmer", self.x + math.cos(a) * 60, self.y + math.sin(a) * 60)
        elif self.state == "aim":
            self.timer -= 1
            if self.timer > 14:
                self.aim = self.ang_p()
            if self.timer <= 0:
                self.hx, self.hy = self.x, self.y
                self.hvx, self.hvy = math.cos(self.aim) * 15, math.sin(self.aim) * 15
                self.ht = 0
                self.state = "hook"
        elif self.state == "hook":
            self.hx += self.hvx
            self.hy += self.hvy
            self.ht += 1
            if math.hypot(run.px - self.hx, run.py - self.hy) < 24 + run.pr and run.dash_t <= 0:
                self.state = "pull"
                run.banner("HOOKED!", (255, 120, 60), 50)
            elif self.ht > 42:
                self.state, self.timer = "walk", 230
        elif self.state == "pull":
            run.root_player(3)
            d = math.hypot(self.x - run.px, self.y - run.py)
            if d > 70 and run.dash_t <= 0:
                run.px += (self.x - run.px) / d * 10
                run.py += (self.y - run.py) / d * 10
                self.hx, self.hy = run.px, run.py
            else:
                self.state, self.timer = "walk", 260

    def ai_stalker(self):
        run = self.run
        self.ai_chase()
        d = self.dist_p()
        if d < 175:
            run.rad_t = 6
            if self.t % 40 == 0:
                run.hurt_player(3 * run.dmg_scale(), dot=True)

    # ======================================================== CASTLE mobs
    def ai_armor(self):
        self.ai_chase()

    def init_gargoyle(self):
        self.state = "fly"
        self.tx = self.ty = 0.0

    def ai_gargoyle(self):
        run = self.run
        if self.state == "fly":
            if self.toward(run.px, run.py, self.sp()) < 190:
                self.state, self.timer = "hover", 44
                self.tx = clamp(run.px + run.pvx * 26, 30, 870)
                self.ty = clamp(run.py + run.pvy * 26, 30, 870)
                run.add_zone(self.tx, self.ty, 38, 44, self.dmg, kind="blast")
        elif self.state == "hover":
            self.timer -= 1
            self.angle += 0.3
            self.y += math.sin(self.angle) * 0.6
            if self.timer <= 8:
                self.state = "drop"
        elif self.state == "drop":
            d = self.toward(self.tx, self.ty, 15)
            if d < 16:
                run.spark(self.x, self.y, (190, 190, 210), 8)
                self.state = "ground"
        else:
            self.ai_chase()

    def ai_bat(self):
        run = self.run
        if self.state == "march":                    # wall formation: sweep in a line first
            self.x += self.vx
            self.y += self.vy
            self.timer -= 1
            if self.timer <= 0:
                self.state = "walk"
            return
        self.angle += 0.17
        d = self.dist_p()
        a = math.atan2(run.py - self.y, run.px - self.x) + math.sin(self.angle) * 0.9 * min(1.0, d / 200.0)
        self.x += math.cos(a) * self.sp()
        self.y += math.sin(a) * self.sp()
        self.facing = 1 if math.cos(a) > 0 else -1

    def init_executioner(self):
        self.state, self.timer = "walk", random.randint(100, 160)

    def ai_executioner(self):
        run = self.run
        if self.state == "walk":
            self.ai_chase()
            self.timer -= 1
            if self.timer <= 0:
                self.state, self.timer, self.ethereal, self.intangible = "ethereal", 80, True, True
        elif self.state == "ethereal":
            tx, ty = run.px + run.pvx * 8, run.py + run.pvy * 8
            d = self.toward(tx, ty, 7.2)
            self.timer -= 1
            if d < 70 or self.timer <= 0:
                self.state, self.timer = "chop", 26
                self.ethereal = self.intangible = False
                self.aim = self.ang_p()
                run.add_zone(self.x + math.cos(self.aim) * 38, self.y + math.sin(self.aim) * 38, 62, 26, self.dmg * 2.0,
                             kind="blast", pierce=0.6, wound=240)
        elif self.state == "chop":
            self.timer -= 1
            if self.timer <= 0:
                self.state, self.timer = "recover", 80
        else:
            self.timer -= 1
            if self.timer <= 0:
                self.state, self.timer = "walk", random.randint(150, 220)

    def ai_templar(self):
        run = self.run
        self.ai_chase()
        if self.t % 20 == 0:
            for e in run.enemies:
                if e is self or e.elite or e.mini or e.boss or e.dying or e.remove or e.ai in ("pod", "guard"):
                    continue
                if e.eshield <= 0 and e.shield_cd <= 0 and math.hypot(e.x - self.x, e.y - self.y) < 215:
                    e.eshield = 28 * run.hp_scale()
                    e.shield_cd = 220

    def init_lich(self):
        self.timer = 150

    def ai_lich(self):
        run = self.run
        self.keep_distance(380, 480)
        self.timer -= 1
        if self.timer <= 0:
            run.spawn_walls(4, kind="bone", near_player=True)
            for _ in range(4):
                x, y = run.edge_pos()
                run.spawn_enemy("bat", x, y)
            run.fx.append(dict(kind="ring", x=self.x, y=self.y, r=10, max_r=80, ttl=24, color=(190, 255, 200)))
            self.timer = 300

    # ======================================================= MINI-BOSS shared
    def mini_idle_start(self, t=100):
        self.state, self.timer = "idle", t

    # ---- The Hollowed Treant ------------------------------------------------
    def init_treant(self):
        self.state, self.timer, self.seq = "idle", 90, 0

    def ai_treant(self):
        run = self.run
        tp = self.tempo()
        f = self.hp / self.max_hp
        if self.state == "idle":
            if self.dist_p() > 190:
                self.toward(run.px, run.py, self.sp())
            self.face_p()
            self.timer -= tp
            if self.timer <= 0:
                self.seq += 1
                if self.seq % 3 == 0:
                    self.state, self.timer = "spore", 38
                else:
                    self.state, self.timer = "stomp", 34
                    self.aim = run.lead_angle(self.x, self.y, 7.0)
        elif self.state == "stomp":
            self.timer -= tp
            if self.timer <= 0:
                lines = [0.0] if f > 0.5 else [-0.34, 0.0, 0.34]
                for off in lines:
                    for i in range(1, 10):
                        px, py = self.x + math.cos(self.aim + off) * i * 68, self.y + math.sin(self.aim + off) * i * 68
                        if 0 < px < SCREEN and 0 < py < SCREEN:
                            run.add_zone(px, py, 34, 14 + i * 4, 18 * (1 + 0.0), kind="root")
                run.shake = max(run.shake, 8)
                self.state, self.timer = "idle", random.randint(110, 150)
        elif self.state == "spore":
            self.timer -= tp
            if self.timer <= 0:
                for k in range(8):
                    a = k * TAU / 8 + 0.2
                    run.add_pool(clamp(self.x + math.cos(a) * 125, 40, 860), clamp(self.y + math.sin(a) * 125, 40, 860),
                                 48, 460, "spore", 4)
                run.fx.append(dict(kind="ring", x=self.x, y=self.y, r=10, max_r=140, ttl=22, color=(150, 230, 90)))
                self.state, self.timer = "idle", 170

    # ---- Bramble Hydra --------------------------------------------------------
    def init_hydra(self):
        self.state, self.timer, self.seq = "idle", 80, 0

    def ai_hydra(self):
        run = self.run
        tp = self.tempo()
        if self.state == "idle":
            if self.dist_p() > 170:
                self.toward(run.px, run.py, self.sp())
            self.face_p()
            self.timer -= tp
            if self.timer <= 0:
                self.seq += 1
                if self.seq % 3 == 0:
                    self.state, self.timer = "trap", 40
                    self.tx, self.ty = run.px + run.pvx * 14, run.py + run.pvy * 14
                    run.add_hazard_ring(self.tx, self.ty, 14, 105, 70, 480, 11, delay=40)
                else:
                    self.state, self.timer = "whip_t", 40
                    self.aim = run.lead_angle(self.x, self.y, 8.0)
        elif self.state == "whip_t":
            self.timer -= tp
            for k in (-1, 0, 1):
                for off in (-0.55, 0.55):
                    run.beam(self.x, self.y, self.aim + off + k * 0.45, 300, 8, 0, False, (255, 70, 70))
            if self.timer <= 0:
                self.state, self.timer = "whip_s", 0
        elif self.state == "whip_s":
            self.timer += tp
            prog = min(1.0, self.timer / 36.0)
            for k in (-1, 0, 1):
                a = self.aim + k * 0.45 + (-0.55 + 1.1 * prog)
                run.beam(self.x, self.y, a, 300, 24, self.dmg, True, (110, 190, 60), thin=True)
            if prog >= 1.0:
                self.state, self.timer = "idle", random.randint(110, 150)
        elif self.state == "trap":
            self.timer -= tp
            if self.timer <= 0:
                self.state, self.timer = "idle", 170

    # ---- Sylphid, the Pollen Queen ------------------------------------------
    def init_sylphid(self):
        self.state, self.timer, self.seq = "idle", 80, 0
        self.aimr = 0.0

    def ai_sylphid(self):
        run = self.run
        tp = self.tempo()
        if self.state == "idle":
            self.keep_distance(280, 400)
            self.timer -= tp
            if self.timer <= 0:
                self.seq += 1
                if self.seq % 4 == 0:
                    self.state, self.timer = "haze", 40
                elif self.seq % 2 == 1:
                    self.state, self.timer = "burst", 36
                else:
                    self.state, self.timer = "spiral", 220
                    self.aimr = random.uniform(0, TAU)
        elif self.state == "burst":
            self.timer -= tp
            if self.timer <= 0:
                for k in range(28):
                    run.fire_ebullet(self.x, self.y, k * TAU / 28, 3.5, 11, "pollen", 6, strict=False,
                                     life=520, decel=0.955, decel_after=26)
                for k in range(18):
                    run.fire_ebullet(self.x, self.y, k * TAU / 18 + 0.17, 2.3, 11, "pollen", 6, strict=False,
                                     life=520, decel=0.95, decel_after=30)
                self.state, self.timer = "idle", 110
        elif self.state == "spiral":
            self.timer -= tp
            if int(self.timer) % 5 == 0:
                self.aimr += 0.31
                for arm in range(2):
                    sp = 2.0 if (int(self.timer) // 5) % 2 else 3.6
                    run.fire_ebullet(self.x, self.y, self.aimr + arm * math.pi, sp, 12, "leaf", 6, strict=False, life=420)
            if self.timer <= 0:
                self.state, self.timer = "idle", 100
        elif self.state == "haze":
            self.timer -= tp
            if self.timer <= 0:
                for k in range(3):
                    x, y = run.edge_pos(None, 20)
                    run.add_haze(clamp(x, 30, 870), clamp(y, 30, 870), 88)
                run.banner("POLLEN HAZE!", (255, 214, 90), 90)
                self.state, self.timer = "idle", 150

    # ---- Barkspine ------------------------------------------------------------
    def init_barkspine(self):
        self.state, self.timer, self.seq = "idle", 70, 0

    def ai_barkspine(self):
        run = self.run
        tp = self.tempo()
        f = self.hp / self.max_hp
        if self.state == "idle":
            if self.dist_p() > 260:
                self.toward(run.px, run.py, self.sp())
            self.face_p()
            self.timer -= tp
            if self.timer <= 0:
                self.seq += 1
                every = 3 if f < 0.5 else 5
                if self.seq % every == 0:
                    self.state, self.timer = "thorns", 210
                    self.aim = self.ang_p()
                    self.ring_i = 0
                elif self.seq % 2 == 1:
                    self.state, self.timer = "wave_t", 40
                    self.aim = run.lead_angle(self.x, self.y, 4.4)
                else:
                    self.state, self.timer = "shotgun_t", 26
                    self.aim = run.lead_angle(self.x, self.y, 4.0)
        elif self.state == "wave_t":
            self.timer -= tp
            lanes = 3 if f > 0.5 else 5
            for k in range(lanes):
                off = (k - (lanes - 1) / 2.0) * 72
                ox, oy = -math.sin(self.aim) * off, math.cos(self.aim) * off
                run.beam(self.x + ox, self.y + oy, self.aim, 900, 6, 0, False, (255, 170, 80))
            if self.timer <= 0:
                for k in range(lanes):
                    off = (k - (lanes - 1) / 2.0) * 72
                    ox, oy = -math.sin(self.aim) * off, math.cos(self.aim) * off
                    for j in range(7):
                        bx = self.x + ox - math.cos(self.aim) * j * 26
                        by = self.y + oy - math.sin(self.aim) * j * 26
                        run.fire_ebullet(bx, by, self.aim, 4.4, 14, "root", 11, strict=False, life=260)
                run.shake = max(run.shake, 8)
                self.state, self.timer = "idle", 120
        elif self.state == "shotgun_t":
            self.timer -= tp
            if self.timer <= 0:
                for k in range(11):
                    a = self.aim + (k - 5) * 0.085
                    run.fire_ebullet(self.x, self.y, a, random.uniform(3.0, 5.0), 11, "sap", 8, strict=False,
                                     life=random.randint(55, 85), on_end="sap")
                self.state, self.timer = "idle", 110
        elif self.state == "thorns":
            self.timer -= tp
            for rn, at in enumerate((180, 130, 80)):
                if int(self.timer) == at and self.ring_i == rn:
                    self.ring_i += 1
                    n = 30
                    gap = self.aim + rn * 0.9
                    for i in range(n):
                        a = i * TAU / n
                        if abs(wrap_angle(a - gap)) < 0.38 or abs(wrap_angle(a - gap - math.pi)) < 0.38:
                            continue
                        run.fire_ebullet(self.x, self.y, a, 2.5, 12, "thorn", 6, strict=False, life=420)
            if self.timer <= 0:
                self.state, self.timer = "idle", 120

    # ---- Scraptooth Dreadnought -----------------------------------------------
    def init_dreadnought(self):
        self.state, self.timer, self.seq, self.charges = "idle", 100, 0, 0

    def ai_dreadnought(self):
        run = self.run
        tp = self.tempo()
        f = self.hp / self.max_hp
        if self.state == "idle":
            if self.dist_p() > 150:
                self.toward(run.px, run.py, self.sp())
            self.face_p()
            self.timer -= tp
            if self.timer <= 0:
                self.seq += 1
                if self.seq % 2 == 1:
                    self.state, self.timer = "wind", 58
                    self.aim = run.lead_angle(self.x, self.y, 11.5)
                    self.charges = 2 if f < 0.5 else 1
                else:
                    self.state, self.timer = "shrap", 34
        elif self.state == "wind":
            self.timer -= tp
            if self.timer > 16:
                self.aim = run.lead_angle(self.x, self.y, 11.5)
            run.beam(self.x, self.y, self.aim, 1300, 70, 0, False, (255, 120, 60), wide_tele=True)
            if self.t % 4 == 0:
                run.spark(self.x + random.uniform(-20, 20), self.y - 30, (230, 230, 230), 2)
            run.shake = max(run.shake, 2)
            if self.timer <= 0:
                self.state, self.timer = "rev", 70
        elif self.state == "rev":
            self.timer -= 1
            self.x += math.cos(self.aim) * 11.5
            self.y += math.sin(self.aim) * 11.5
            self.facing = 1 if math.cos(self.aim) > 0 else -1
            for e in run.enemies:                   # breaks through swarms
                if e is self or e.dying or e.remove or e.mini or e.boss or e.intangible:
                    continue
                if math.hypot(e.x - self.x, e.y - self.y) < self.r + e.r:
                    run.damage_enemy(e, e.max_hp * (0.12 if e.elite else 5.0), False, "env")
            out = self.x < 40 or self.x > SCREEN - 40 or self.y < 40 or self.y > SCREEN - 40
            if self.timer <= 0 or out:
                self.stay_in(50)
                run.fx.append(dict(kind="ring", x=self.x, y=self.y, r=10, max_r=110, ttl=18, color=(220, 200, 180)))
                self.charges -= 1
                if self.charges > 0:
                    self.state, self.timer = "wind", 40
                    self.aim = run.lead_angle(self.x, self.y, 11.5)
                else:
                    self.state, self.timer = "idle", 120
        elif self.state == "shrap":
            self.timer -= tp
            if int(self.timer) % 6 == 0:
                run.spark(self.x, self.y - 20, (255, 160, 60), 2)
            if self.timer <= 0:
                rings = 3 if f < 0.5 else 2
                for rn in range(rings):
                    n = 22
                    for i in range(n):
                        run.fire_ebullet(self.x, self.y, i * TAU / n + rn * 0.14, 6.4 - rn * 1.2, 12, "shard", 5,
                                         strict=False, life=200)
                run.shake = max(run.shake, 8)
                run.fx.append(dict(kind="ring", x=self.x, y=self.y, r=10, max_r=100, ttl=14, color=(255, 170, 70)))
                self.state, self.timer = "idle", 110

    # ---- Rad-Gorgon --------------------------------------------------------
    def init_gorgon(self):
        self.state, self.timer, self.seq = "idle", 80, 0

    def ai_gorgon(self):
        run = self.run
        tp = self.tempo()
        if self.state == "idle":
            self.keep_distance(200, 330)
            self.timer -= tp
            if self.timer <= 0:
                self.seq += 1
                if self.seq % 2 == 1:
                    self.state, self.timer = "beam_t", 46
                    self.aim = self.ang_p()
                else:
                    self.state, self.timer = "pulse", 40
        elif self.state == "beam_t":
            self.timer -= tp
            self.face_p()
            run.beam(self.x, self.y, self.aim - 0.8, 700, 6, 0, False, (140, 255, 120))
            run.beam(self.x, self.y, self.aim + 0.8, 700, 6, 0, False, (140, 255, 120))
            if self.timer <= 0:
                self.state, self.timer = "beam", 0
        elif self.state == "beam":
            self.timer += tp
            prog = min(1.0, self.timer / 150.0)
            a = self.aim - 0.8 + 1.6 * prog
            run.beam(self.x, self.y, a, 700, 28, self.dmg, True, (120, 255, 110))
            if int(self.timer) % 7 == 0:
                dd = random.uniform(130, 600)
                px, py = self.x + math.cos(a) * dd, self.y + math.sin(a) * dd
                if 30 < px < 870 and 30 < py < 870:
                    run.add_pool(px, py, 40, 900, "sludge", 6)
            if prog >= 1.0:
                self.state, self.timer = "idle", 130
        elif self.state == "pulse":
            self.timer -= tp
            if self.timer <= 0:
                run.add_zone(self.x, self.y, 235, 1, self.dmg * 0.8, kind="pulse", effect="mutagen")
                run.fx.append(dict(kind="ring", x=self.x, y=self.y, r=10, max_r=235, ttl=22, color=(130, 255, 120)))
                self.state, self.timer = "idle", 120
            else:
                run.fx.append(dict(kind="ringline", x=self.x, y=self.y, r=235 * (1 - self.timer / 40.0), ttl=1, color=(130, 255, 120)))

    # ---- The Blood-Bound Gargoyle -----------------------------------------------
    def init_bgargoyle(self):
        self.state, self.timer, self.seq = "idle", 90, 0
        self.tx = self.ty = 0.0

    def ai_bgargoyle(self):
        run = self.run
        tp = self.tempo()
        if self.state == "idle":
            if self.dist_p() > 170:
                self.toward(run.px, run.py, self.sp())
            self.face_p()
            self.timer -= tp
            if self.timer <= 0:
                self.seq += 1
                if self.seq % 3 == 0:
                    self.state, self.timer, self.stone = "stone", 240, True
                    run.banner("STONE FORM!", (180, 180, 200), 70)
                else:
                    self.state, self.timer = "rise", 48
                    self.intangible = self.hidden = True
        elif self.state == "stone":
            self.timer -= 1
            run.pull_player(self.x, self.y, 1.5)
            if self.t % 30 == 0:
                run.fx.append(dict(kind="ring", x=self.x, y=self.y, r=320, max_r=40, ttl=26, color=(210, 60, 70)))
            if self.timer <= 0:
                self.stone = False
                self.state, self.timer = "idle", 110
        elif self.state == "rise":
            self.timer -= tp
            if self.timer > 16:
                self.tx = run.px + run.pvx * 10
                self.ty = run.py + run.pvy * 10
            self.tx, self.ty = clamp(self.tx, 40, 860), clamp(self.ty, 40, 860)
            run.fx.append(dict(kind="ringline", x=self.tx, y=self.ty, r=92 * (1 - self.timer / 48.0), ttl=1, color=(255, 70, 70)))
            run.fx.append(dict(kind="ringline", x=self.tx, y=self.ty, r=92, ttl=1, color=(200, 40, 50)))
            if self.timer <= 0:
                self.x, self.y = self.tx, self.ty
                self.intangible = self.hidden = False
                run.shake = max(run.shake, 12)
                run.fx.append(dict(kind="ring", x=self.x, y=self.y, r=10, max_r=95, ttl=16, color=(255, 90, 90)))
                if math.hypot(run.px - self.x, run.py - self.y) < 92 + run.pr:
                    if run.hurt_player(self.dmg * 1.8):
                        self.hp = min(self.max_hp, self.hp + self.dmg * 1.8 * 8)
                self.state, self.timer = "recover", 60
        elif self.state == "recover":
            self.timer -= tp
            if self.timer <= 0:
                self.state, self.timer = "idle", 100

    # ---- Cursed High Inquisitor ----------------------------------------------
    def init_inquisitor(self):
        self.state, self.timer, self.seq = "idle", 80, 0

    def ai_inquisitor(self):
        run = self.run
        tp = self.tempo()
        f = self.hp / self.max_hp
        if self.state == "idle":
            self.keep_distance(300, 420)
            self.timer -= tp
            if self.timer <= 0:
                self.seq += 1
                if self.seq % 2 == 1:
                    self.state, self.timer = "chains", 30
                else:
                    self.state, self.timer = "wave_t", 44
                    self.wave_side = random.choice((0, 2))
                    self.gaps = sorted(random.sample([130, 330, 530, 730], 2))
        elif self.state == "chains":
            self.timer -= tp
            if self.timer <= 0:
                n = 1 if f > 0.5 else 3
                for k in range(n):
                    tx = run.px + run.pvx * 40 + (0 if k == 0 else random.uniform(-190, 190))
                    ty = run.py + run.pvy * 40 + (0 if k == 0 else random.uniform(-190, 190))
                    run.add_zone(clamp(tx, 40, 860), clamp(ty, 40, 860), 62, 54 + k * 8, 10, kind="chains", effect="root")
                self.state, self.timer = "idle", 120
        elif self.state == "wave_t":
            self.timer -= tp
            edge = 14 if self.wave_side == 0 else SCREEN - 14
            if (int(self.timer) // 4) % 2 == 0:
                run.fx.append(dict(kind="edgewarn", y=edge, gaps=self.gaps, ttl=1))
            if self.timer <= 0:
                self.spawn_knights(self.wave_side, self.gaps)
                if f < 0.5:
                    self.pending = (1 - self.wave_side // 2) * 2, 70
                    self.state, self.timer = "wave2", 70
                else:
                    self.state, self.timer = "idle", 140
        elif self.state == "wave2":
            self.timer -= tp
            if self.timer <= 0:
                side = 2 if self.wave_side == 0 else 0
                self.spawn_knights(side, sorted(random.sample([130, 330, 530, 730], 2)))
                self.state, self.timer = "idle", 140

    def spawn_knights(self, side, gaps):
        run = self.run
        y = -26 if side == 0 else SCREEN + 26
        a = math.pi / 2 if side == 0 else -math.pi / 2
        for x in range(30, SCREEN, 62):
            if any(abs(x - g) < 84 for g in gaps):
                continue
            run.fire_ebullet(x, y, a, 2.3, 18, "knight", 17, strict=False, life=520)

    # ======================================================== FINAL BOSSES
    # ---- The Hive Monarch (reworked) -----------------------------------------
    def init_boss(self):
        self.state = "intro"
        self.intangible = True
        self.c_spiral, self.c_acid, self.c_pods = 100.0, 170.0, 240.0
        self.c_ring, self.c_pull = 150.0, 700.0
        self.spiral_left = self.spiral_i = 0
        self.a0 = 0.0
        self.shield_done = set()
        self.shield_t = 0
        self.hatch_done = False
        self.dashes = 0
        self.seq = 0
        self.spin = 0.0
        self.pull_t = 0
        self.p2_t = 0

    def boss_begin_shield(self, thr):
        run = self.run
        self.shield_done.add(thr)
        self.invuln, self.shield_t = True, 1500
        run.ebullets = [b for b in run.ebullets if b.kind != "needle"]
        kinds = ["bearer", "bearer", "bearer"] + (["commander"] if thr < 0.5 else [])
        for k, kd in enumerate(kinds):
            a = k * TAU / len(kinds) + 0.5
            e = run.spawn_enemy(kd, clamp(self.x + math.cos(a) * 190, 60, 840), clamp(self.y + math.sin(a) * 190 + 60, 60, 840))
            self.adds.append(e)
        run.banner("SHIELDED! DESTROY THE GUARDIANS", (120, 220, 255), 150)
        run.fx.append(dict(kind="ring", x=self.x, y=self.y, r=20, max_r=160, ttl=24, color=(120, 220, 255)))

    def ai_boss(self):
        run = self.run
        if self.state == "intro":
            self.y += 2.2
            if self.y >= 210:
                self.state, self.intangible = "fight", False
                self.state = "fight"
                run.banner("THE HIVE MONARCH", (255, 190, 70))
            return
        f = self.hp / self.max_hp
        tp = self.tempo()
        self.armor = 0.12 + 0.06 * (1 - f)               # adaptive armor
        if self.invuln:
            self.adds = [a for a in self.adds if not a.remove and not a.dying]
            self.shield_t -= 1
            tp *= 0.6
            if not self.adds or self.shield_t <= 0:
                self.invuln = False
                run.banner("THE SHIELD SHATTERS!", (255, 220, 120), 90)
                run.fx.append(dict(kind="ring", x=self.x, y=self.y, r=20, max_r=200, ttl=24, color=(255, 220, 120)))
        else:
            for thr in (0.80, 0.45):
                if f <= thr and thr not in self.shield_done:
                    self.boss_begin_shield(thr)
        if self.phase == 1 and f <= 0.60:
            self.phase = 2
            self.speed0 *= 1.25
            self.state, self.timer, self.seq = "chase", 90, 0
            run.ebullets = [b for b in run.ebullets if b.kind != "needle"]
            run.fx.append(dict(kind="ring", x=self.x, y=self.y, r=20, max_r=220, ttl=30, color=(255, 80, 60)))
            run.banner("THE MONARCH IS ENRAGED", (255, 90, 70))
            run.border = True
            self.p2_t = self.t
        if self.phase == 2 and not self.hatch_done and f <= 0.30:
            self.hatch_done = True
            for k in range(6):
                g = run.spawn_enemy("guard", self.x, self.y)
                g.boss_ref, g.angle = self, k * math.pi / 3
                self.guards.append(g)
            run.banner("EMERGENCY HATCH!", (120, 220, 255))
        self.guards = [g for g in self.guards if not g.remove and not g.dying]
        if self.phase == 1:
            self.boss_phase1(tp, f)
        else:
            self.boss_phase2(tp, f)
        self.x = clamp(self.x, self.r + 10, SCREEN - self.r - 10)
        self.y = clamp(self.y, self.r + 10, SCREEN - self.r - 10)

    def boss_acid(self, f, n):
        run = self.run
        for k in range(n):
            if k == 0:
                tx, ty = run.px + run.pvx * 54, run.py + run.pvy * 54      # predictive
            else:
                tx, ty = run.px + random.uniform(-230, 230), run.py + random.uniform(-230, 230)
            run.add_zone(clamp(tx, 40, 860), clamp(ty, 40, 860), 50, 54, 20, kind="acid", pool=("acid", 480, 5))

    def boss_phase1(self, tp, f):
        run = self.run
        self.toward(450 + math.sin(self.t * 0.01) * 220, 200 + math.sin(self.t * 0.017) * 50, self.speed * 0.9)
        self.c_spiral -= tp
        if self.c_spiral <= 0:
            self.a0 += 0.35
            self.spiral_left, self.spiral_i, self.c_spiral = 24, 0, 190
        if self.spiral_left > 0 and self.t % 3 == 0:
            i = self.spiral_i
            ang = self.a0 + i * (TAU / 24)
            if i % 2 == 0:
                opt = dict(homing=0.014, home_until=75) if i % 6 == 0 else {}
                run.fire_ebullet(self.x, self.y, ang, 3.6, 13, "needle", 6, strict=False, **opt)
            else:
                run.fire_ebullet(self.x, self.y, ang, 1.5, 13, "needle", 6, strict=False, life=560)
            self.spiral_i += 1
            self.spiral_left -= 1
        self.c_acid -= tp
        if self.c_acid <= 0:
            self.boss_acid(f, random.randint(4, 6))
            self.c_acid = 380
        self.c_pods -= tp
        if self.c_pods <= 0:
            if not any(e.kind == "pod" and not e.remove for e in run.enemies):
                for x in (130, 770):
                    run.spawn_enemy("pod", x, 450)
                run.banner("HIVE PODS - DESTROY THEM!", (255, 170, 60), 120)
            self.c_pods = 1500

    def boss_phase2(self, tp, f):
        run = self.run
        st = self.state
        run.border_w = min(150, 48 + (self.t - self.p2_t) / 60.0 * 1.15)         # the arena keeps shrinking
        self.c_ring -= tp
        if self.c_ring <= 0 and st not in ("windup", "dash"):
            self.spin += 0.37
            n = 26
            for i in range(n):
                fast = i % 2 == 0
                run.fire_ebullet(self.x, self.y, self.spin + i * TAU / n, 3.9 if fast else 1.3, 12, "orb_e", 6,
                                 strict=False, life=400 if fast else 560)
            self.c_ring = 220
        self.c_acid -= tp
        if self.c_acid <= 0:
            self.boss_acid(f, random.randint(3, 5))
            self.c_acid = 330
        self.c_pull -= tp
        if self.c_pull <= 0:
            self.pull_t, self.c_pull = 55, 800
            run.banner("GRAVITY PULL!", (200, 120, 255), 60)
        if self.pull_t > 0:
            self.pull_t -= 1
            run.pull_player(self.x, self.y, 2.3)
        self.c_pods -= tp
        if self.c_pods <= 0:
            if not any(e.kind == "pod" and not e.remove for e in run.enemies):
                for x in (130, 770):
                    run.spawn_enemy("pod", x, 450)
            self.c_pods = 1700
        if st == "chase":
            if self.dist_p() > 230:
                self.toward(run.px, run.py, self.speed)
            self.timer -= tp
            if self.timer <= 0:
                nxt = self.seq % 2
                self.seq += 1
                if nxt == 0:
                    self.state, self.timer, self.dashes = "windup", 42, 2
                    self.aim = run.lead_angle(self.x, self.y, 13.5)
                else:
                    self.state, self.timer = "storm", 200
        elif st == "windup":
            self.timer -= tp
            if self.timer > 14:
                self.aim = run.lead_angle(self.x, self.y, 13.5)
            run.beam(self.x, self.y, self.aim, 1300, 30, 0, False, (255, 50, 50))
            if self.timer <= 0:
                self.state, self.timer = "dash", 44
        elif st == "dash":
            self.x += math.cos(self.aim) * 13.5
            self.y += math.sin(self.aim) * 13.5
            self.timer -= 1
            m = self.r + 12
            edge = self.x < m or self.x > SCREEN - m or self.y < m or self.y > SCREEN - m
            if edge or self.timer <= 0:
                run.add_zone(self.x, self.y, 150, 1, 14, kind="blast", knock=15)         # displacement shockwave
                run.fx.append(dict(kind="ring", x=self.x, y=self.y, r=10, max_r=150, ttl=16, color=(255, 120, 80)))
                self.dashes -= 1
                if self.dashes > 0:
                    self.state, self.timer = "windup", 34
                    self.aim = run.lead_angle(self.x, self.y, 13.5)
                else:
                    self.state, self.timer = "chase", 110
        elif st == "storm":
            self.timer -= tp
            self.spin += 0.17
            if self.t % 4 == 0:
                for arm, sp in enumerate((4.2, 2.8, 1.7)):
                    run.fire_ebullet(self.x, self.y, self.spin + arm * 2.094, sp, 9, "orb_e", 6, strict=False, life=480)
            if self.timer <= 0:
                self.state, self.timer = "chase", 110

    # ---- Construct Zero, the Siege Engine ------------------------------------
    def init_construct(self):
        self.state = "intro"
        self.intangible = True
        self.c_main, self.c_thr, self.c_mort = 150.0, 330.0, 200.0
        self.seq = 0
        self.beam_a = 0.0
        self.beam_dir = 1
        self.grav_t = self.grid_t = 0
        self.grid_a = 0.0
        self.sd_t = 0
        self.sd_done = False
        self.core_open = False
        self.timer = 0

    def ai_construct(self):
        run = self.run
        if self.state == "intro":
            self.y += 1.8
            if self.y >= 270:
                self.state, self.intangible = "idle", False
                run.banner("CONSTRUCT ZERO", (255, 150, 70))
            return
        f = self.hp / self.max_hp
        tp = self.tempo()
        self.armor = 0.15 + 0.07 * (1 - f)
        if self.state == "selfdestruct":
            self.sd_t -= 1
            run.shake = max(run.shake, 3)
            if self.sd_t <= 0:
                run.fx.append(dict(kind="ring", x=self.x, y=self.y, r=10, max_r=440, ttl=26, color=(255, 120, 60)))
                run.shake = 22
                if math.hypot(run.px - self.x, run.py - self.y) < 430 + run.pr:
                    run.hurt_player(70, pierce=0.4)
                self.sd_done = True
                self.invuln = False
                self.hp = 0
                self.dying = True
                run.kill_queue.append(self)
            return
        if self.phase == 1 and f <= 0.50:
            self.phase, self.core_open = 2, True
            self.state, self.timer = "idle", 0
            self.c_main = 100.0
            self.seq = 0
            run.ebullets = []
            run.mines = []
            run.banner("CORE OVERLOAD!", (255, 90, 70))
            run.fx.append(dict(kind="ring", x=self.x, y=self.y, r=20, max_r=260, ttl=30, color=(120, 240, 255)))
        # slow drift toward the arena centre
        if self.state in ("idle", "sweep_t", "mines") and self.dist_p() > 0:
            self.toward(450 + math.sin(self.t * 0.006) * 80, 290, self.speed * 0.7)
        # ---- concurrent systems
        self.c_thr -= tp
        if self.c_thr <= 0:
            run.add_zone(self.x, self.y, 180, 36, 22, kind="flame", knock=12)
            self.c_thr = 330 if self.phase == 1 else 270
        if self.phase == 2 and self.state in ("grav", "grid"):
            self.c_mort -= tp
            if self.c_mort <= 0:
                tx, ty = run.px + run.pvx * 46, run.py + run.pvy * 46
                run.add_zone(clamp(tx, 40, 860), clamp(ty, 40, 860), 54, 46, 20, kind="flame", pool=("fire", 320, 7))
                self.c_mort = 42 if self.state == "grav" else 80
        # ---- state machine
        st = self.state
        if st == "idle":
            self.c_main -= tp
            if self.c_main <= 0:
                self.seq += 1
                if self.phase == 1:
                    if self.seq % 2 == 1:
                        self.state, self.timer = "sweep_t", 54
                        pa = self.ang_p()
                        self.beam_dir = random.choice((-1, 1))
                        self.beam_a = pa - self.beam_dir * math.pi / 2
                    else:
                        self.state, self.timer = "mines", 30
                else:
                    self.state, self.timer = ("grav", 360) if self.seq % 2 == 1 else ("grid_t", 52)
                    if self.state == "grid_t":
                        self.grid_a = random.uniform(0, math.pi / 2)
        elif st == "sweep_t":
            self.timer -= tp
            run.beam(self.x, self.y, self.beam_a, 1500, 70, 0, False, (255, 60, 60), wide_tele=True)
            run.beam(self.x, self.y, self.beam_a + self.beam_dir * math.pi, 1500, 8, 0, False, (255, 160, 160))
            if self.timer <= 0:
                self.state, self.timer = "sweep", 0
        elif st == "sweep":
            self.timer += tp
            prog = min(1.0, self.timer / 150.0)
            a = self.beam_a + self.beam_dir * math.pi * prog
            run.beam(self.x, self.y, a, 1500, 36, 26, True, (255, 70, 50))
            if prog >= 1.0:
                self.state, self.c_main = "idle", 150.0
        elif st == "mines":
            self.timer -= tp
            if self.timer <= 0:
                for _ in range(8):
                    for _t in range(10):
                        x, y = random.uniform(70, 830), random.uniform(70, 830)
                        if math.hypot(x - run.px, y - run.py) > 110 and math.hypot(x - self.x, y - self.y) > 100:
                            break
                    run.add_mine(x, y)
                run.banner("MINEFIELD!", (255, 170, 70), 70)
                self.state, self.c_main = "idle", 190.0
        elif st == "grav":
            self.timer -= tp
            run.pull_player(self.x, self.y, 1.45)
            run.fx.append(dict(kind="ringline", x=self.x, y=self.y, r=280 * ((self.t % 40) / 40.0), ttl=1, color=(150, 200, 255)))
            if self.timer <= 0:
                self.state, self.c_main = "idle", 110.0
        elif st == "grid_t":
            self.timer -= tp
            for k in range(4):
                run.beam(self.x, self.y, self.grid_a + k * math.pi / 2, 1300, 8, 0, False, (255, 80, 80))
            if self.timer <= 0:
                self.state, self.timer = "grid", 420
        elif st == "grid":
            self.timer -= tp
            self.grid_a += 0.0115
            for k in range(4):
                run.beam(self.x, self.y, self.grid_a + k * math.pi / 2, 1300, 24, 20, True, (255, 70, 90))
            if self.timer <= 0:
                self.state, self.c_main = "idle", 110.0

    # ---- Vespera, the Phantom Monarch ----------------------------------------
    def init_vespera(self):
        self.state, self.timer = "intro", 70
        self.intangible = True
        self.c_blink, self.c_clone, self.c_curtain, self.c_rush = 190.0, 260.0, 300.0, 380.0
        self.dest = (450.0, 200.0)
        self.nova_t = 0
        self.nova_done = False
        self.nova_gap = 0.0
        self.flash_c = 100.0
        self.seq = 0
        self.pend = []         # delayed spawns: [frames_left, callable]

    def dagger_fan(self, x, y, dmg, spread=0.28, speed=6.8):
        run = self.run
        a = run.lead_angle(x, y, speed)
        for k in (-1, 0, 1):
            run.fire_ebullet(x, y, a + k * spread, speed, dmg, "dagger", 6, strict=False, life=200)

    def behind_player(self, off=0.0):
        run = self.run
        dx, dy = run.last_dir
        if run.pvx or run.pvy:
            n = math.hypot(run.pvx, run.pvy) or 1
            dx, dy = run.pvx / n, run.pvy / n
        a = math.atan2(-dy, -dx) + off
        return clamp(run.px + math.cos(a) * 150, 60, 840), clamp(run.py + math.sin(a) * 150, 60, 840)

    def vespera_wave(self, side, speed, dmg, kind, gaps, spacing, rad):
        """A straight line of bullets crossing the arena; side 0=top 1=right 2=bottom 3=left."""
        run = self.run
        for p in range(30, SCREEN, spacing):
            if any(abs(p - g) < 66 for g in gaps):
                continue
            if side == 0:
                run.fire_ebullet(p, -24, math.pi / 2, speed, dmg, kind, rad, strict=False, life=520)
            elif side == 2:
                run.fire_ebullet(p, SCREEN + 24, -math.pi / 2, speed, dmg, kind, rad, strict=False, life=520)
            elif side == 3:
                run.fire_ebullet(-24, p, 0.0, speed, dmg, kind, rad, strict=False, life=520)
            else:
                run.fire_ebullet(SCREEN + 24, p, math.pi, speed, dmg, kind, rad, strict=False, life=520)

    def queue_wave(self, side, delay, **kw):
        gaps = sorted(random.sample([120, 300, 480, 660, 780], 2))
        self.run.fx.append(dict(kind="edgewarn2", side=side, gaps=gaps, ttl=delay))
        self.pend.append([delay, lambda s=side, g=gaps, k=kw: self.vespera_wave(s, gaps=g, **k)])

    def ai_vespera(self):
        run = self.run
        if self.state == "intro":
            self.timer -= 1
            self.hidden = (self.timer // 4) % 2 == 0
            if self.timer <= 0:
                self.state, self.intangible, self.hidden = "fight", False, False
                run.banner("VESPERA, THE PHANTOM MONARCH", (220, 140, 255))
            return
        f = self.hp / self.max_hp
        tp = self.tempo()
        if self.phase == 1 and f <= 0.40:
            self.phase = 2
            run.dark_target = 1.0
            run.banner("THE ECLIPSE REALM", (170, 110, 255), 160)
            self.c_rush = 160.0
        self.pend = [[n - 1, fn] for n, fn in self.pend]
        for n, fn in [p for p in self.pend if p[0] <= 0]:
            fn()
        self.pend = [p for p in self.pend if p[0] > 0]
        if self.phase == 2:                                     # brief flashes show where she is
            self.flash_c -= 1
            if self.flash_c <= 0:
                run.boss_flash = 26
                self.flash_c = 150
        # ---- Desperation Nova (chrysalis)
        if not self.nova_done and f <= 0.15 and self.state not in ("nova", "nova_in"):
            self.state, self.nova_t = "nova_in", 40
            self.invuln = True
            for c in self.clones:
                c.remove = True
            self.clones = []
            run.ebullets = [b for b in run.ebullets if b.kind not in ("phantom",)]
        if self.state == "nova_in":
            self.toward(450, 300, 7)
            self.nova_t -= 1
            if self.nova_t <= 0 and math.hypot(self.x - 450, self.y - 300) < 12:
                self.state, self.nova_t = "nova", 600
                self.invuln = False
                self.nova_gap = random.uniform(0, TAU)
                run.banner("DESPERATION NOVA - KILL HER FAST!", (255, 90, 200), 150)
            return
        if self.state == "nova":
            self.nova_t -= 1
            run.boss_flash = 5
            self.angle += 0.11
            if self.nova_t % 24 == 0 and self.nova_t > 30:
                n = 30
                for i in range(n):
                    run.fire_ebullet(self.x, self.y, self.angle + i * TAU / n, 2.2 if i % 2 else 3.2, 11, "orb_p", 6,
                                     strict=False, life=420)
            if self.nova_t <= 0:                                # burst
                for rn, sp in enumerate((3.3, 2.4, 1.7)):
                    n = 48
                    for i in range(n):
                        a = i * TAU / n
                        if abs(wrap_angle(a - self.nova_gap)) < 0.32:
                            continue
                        run.fire_ebullet(self.x, self.y, a, sp, 46, "phantom", 12, strict=False, life=460)
                run.shake = 16
                run.fx.append(dict(kind="ring", x=self.x, y=self.y, r=10, max_r=300, ttl=26, color=(255, 120, 230)))
                self.nova_done = True
                self.state, self.c_blink = "fight", 140.0
                self.speed0 *= 1.3
            return
        # ---- flitting movement
        if self.state == "fight":
            self.keep_distance(250, 380, 1.0)
        elif self.state == "blink_t":
            self.timer -= 1
            self.hidden = (self.timer // 3) % 2 == 0
            if self.timer <= 0:
                self.x, self.y = self.dest
                self.hidden = False
                run.fx.append(dict(kind="ring", x=self.x, y=self.y, r=4, max_r=44, ttl=14, color=(200, 130, 255)))
                self.dagger_fan(self.x, self.y, 14 * (1 + 0.0))
                self.state = "fight"
        # ---- scheduled attacks (tempo scales them)
        self.c_blink -= tp
        if self.c_blink <= 0 and self.state == "fight":
            self.start_blink(0.0)
            for k, c in enumerate(self.clones):
                if not c.remove:
                    c.start_blink((k + 1) * 0.9 * (1 if k % 2 == 0 else -1))
            self.c_blink = 240.0 if self.phase == 1 else 200.0
        self.c_clone -= tp
        if self.c_clone <= 0:
            self.clones = [c for c in self.clones if not c.remove]
            if self.phase == 1 and not self.clones:
                for sgn in (-1, 1):
                    c = run.spawn_enemy("vespera_clone", clamp(self.x + sgn * 110, 50, 850), clamp(self.y + 40, 50, 850))
                    c.boss_ref = self
                    self.clones.append(c)
                run.banner("MIRROR CLONES!", (200, 150, 255), 70)
            self.c_clone = 560.0
        self.c_curtain -= tp
        if self.c_curtain <= 0:
            side = random.choice((0, 1, 2, 3))
            self.queue_wave(side, 42, speed=3.3, dmg=16, kind="dagger", spacing=36, rad=6)
            self.c_curtain = 330.0 if self.phase == 1 else 400.0
        if self.phase == 2:
            self.c_rush -= tp
            if self.c_rush <= 0:
                side = random.choice((0, 1, 2, 3))
                self.queue_wave(side, 46, speed=4.4, dmg=20, kind="phantom", spacing=70, rad=15)
                if f < 0.28:
                    self.queue_wave((side + 2) % 4, 100, speed=4.4, dmg=20, kind="phantom", spacing=70, rad=15)
                self.c_rush = 420.0

    def start_blink(self, off):
        self.dest = self.behind_player(off)
        self.state, self.timer = "blink_t", 22
        self.run.fx.append(dict(kind="ringline", x=self.dest[0], y=self.dest[1], r=34, ttl=22, color=(200, 130, 255)))

    # ---- phantom clones (cast the same attacks, tiny HP) ------------------
    def init_vclone(self):
        self.state = "fight"
        self.timer = 0

    def ai_vclone(self):
        run = self.run
        b = self.boss_ref
        if b is None or b.remove or b.dying:
            self.remove = True
            return
        if self.state == "fight":
            self.keep_distance(240, 380)
        elif self.state == "blink_t":
            self.timer -= 1
            self.hidden = (self.timer // 3) % 2 == 0
            if self.timer <= 0:
                self.x, self.y = self.dest
                self.hidden = False
                run.fx.append(dict(kind="ring", x=self.x, y=self.y, r=4, max_r=40, ttl=14, color=(200, 130, 255)))
                a = run.lead_angle(self.x, self.y, 6.8)
                for k in (-1, 0, 1):
                    run.fire_ebullet(self.x, self.y, a + k * 0.28, 6.8, 10, "dagger", 6, strict=False, life=200)
                self.state = "fight"

    def start_blink_c(self, off):
        self.start_blink(off)

    # ============================================================== drawing
    def sprite_mode(self):
        run = self.run
        if self.flash > 0:
            return "flash"
        if run.freeze > 0:
            return "frozen"
        if self.stone:
            return "stone"
        if self.ethereal:
            return "ghost"
        if self.ai == "vclone":
            return "ghost"
        if self.buffed and not (self.boss or self.mini):
            return "buffed"
        if self.ai in ("boss", "construct") and self.phase == 2:
            return "rage"
        return "normal"

    def draw_tele(self, surf):
        """Ground telegraphs drawn beneath sprites."""
        run = self.run
        a = self.ai
        if a == "sniper" and self.state == "lock":
            if self.timer > 24 or (self.timer // 3) % 2 == 0:
                ex, ey = self.x + math.cos(self.aim) * 1400, self.y + math.sin(self.aim) * 1400
                art.pixel_line(surf, self.x, self.y, ex, ey, (255, 60, 60) if self.timer <= 24 else (255, 150, 150))
        elif a == "bull" and self.state == "windup":
            ex, ey = self.x + math.cos(self.aim) * 1000, self.y + math.sin(self.aim) * 1000
            if (self.timer // 4) % 2 == 0:
                art.pixel_line(surf, self.x, self.y, ex, ey, (255, 90, 60))
        elif a == "commander":
            pulse = 190 + int(4 * math.sin(self.t * 0.1))
            art.pixel_ring(surf, self.x, self.y, pulse, (255, 214, 80), density=0.45)
        elif a == "harvester" and self.state == "aim":
            if (self.timer // 3) % 2 == 0:
                ex, ey = self.x + math.cos(self.aim) * 560, self.y + math.sin(self.aim) * 560
                art.pixel_line(surf, self.x, self.y, ex, ey, (255, 90, 60))
        elif a == "treant" and self.state == "stomp" and (int(self.timer) // 3) % 2 == 0:
            f = self.hp / self.max_hp
            for off in ([0.0] if f > 0.5 else [-0.34, 0.0, 0.34]):
                art.pixel_line(surf, self.x, self.y, self.x + math.cos(self.aim + off) * 640,
                               self.y + math.sin(self.aim + off) * 640, (200, 120, 60))
        elif a == "necro":
            art.pixel_ring(surf, self.x, self.y, self.d["suppress"], (170, 90, 230), density=0.3)
        elif a == "boss" and self.state == "selfdestruct":
            pass
        elif a == "construct" and self.state == "selfdestruct":
            prog = 1 - self.sd_t / 180.0
            if (self.sd_t // 5) % 2 == 0:
                art.pixel_ring(surf, self.x, self.y, 430, (255, 60, 50), density=0.9)
            art.pixel_ring(surf, self.x, self.y, 430 * prog, (255, 200, 80), density=0.9)
            art.draw_text(surf, "%.1f" % (self.sd_t / 60.0), (int(self.x), int(self.y) - 120), 60, (255, 90, 70), title=True)
        elif a == "templar":
            art.pixel_ring(surf, self.x, self.y, 215, (120, 200, 255), density=0.3)
        elif a == "stalker":
            art.pixel_ring(surf, self.x, self.y, 175, (110, 230, 90), density=0.3)
        elif a == "vespera" and self.state == "nova":
            frac = self.nova_t / 600.0
            art.draw_bar(surf, (250, 60, 400, 14), frac, (255, 90, 200))
            if self.nova_t < 150:
                g = self.nova_gap
                for k in range(1, 8):
                    art.pixel_line(surf, self.x + math.cos(g) * 80 * k * 0.4, self.y + math.sin(g) * 80 * k * 0.4,
                                   self.x + math.cos(g) * 80 * (k * 0.4 + 0.2), self.y + math.sin(g) * 80 * (k * 0.4 + 0.2),
                                   (120, 255, 150))
        elif a == "boss" and self.invuln:
            art.pixel_ring(surf, self.x, self.y, self.r + 24, (120, 220, 255), density=0.8)

    def draw(self, surf, ox, oy):
        run = self.run
        cx, cy = int(self.x) + ox, int(self.y) + oy
        if self.ai == "burrow" and self.state in ("under", "tele"):
            for k in range(5):
                art.pixel_disc(surf, cx - self.facing * k * 7, cy + 6 + (k % 2) * 3, 5 - k // 2, (150, 112, 70))
            if self.state == "tele":
                art.pixel_ring(surf, cx, cy, 46 * (1 - self.timer / 34.0), (255, 80, 60), density=0.8)
            return
        if not self.hidden:
            if self.ai == "vespera" and run.dark > 0.55 and run.boss_flash <= 0 and self.state != "nova":
                pass
            elif self.ai == "vclone" and run.dark > 0.55 and run.boss_flash <= 0:
                pass
            else:
                spr = art.sprite(self.d["sprite"], self.sprite_mode(), self.facing < 0)
                bob = 0 if self.ai in ("spinner", "boss") else int(math.sin(self.t * 0.2 + self.angle) * 2)
                if self.boss or self.mini:
                    bob = int(math.sin(self.t * 0.08) * 4)
                if self.ai == "vclone":
                    spr = pygame_scaled(spr, 0.85)
                surf.blit(spr, spr.get_rect(center=(cx, cy + bob)))
        if self.d.get("shield"):
            ang = math.atan2(self.sy, self.sx)
            art.pixel_arc(surf, cx, cy, self.r + 8, ang - 1.0, ang + 1.0, (190, 210, 235), thick=2)
            art.pixel_arc(surf, cx, cy, self.r + 14, ang - 0.8, ang + 0.8, (110, 140, 190), thick=1)
        elif self.d.get("front_armor") and not self.hidden:
            ang = math.atan2(self.sy, self.sx)
            art.pixel_arc(surf, cx, cy, self.r + 8, ang - 0.9, ang + 0.9, (170, 176, 210), thick=1)
        if self.eshield > 0:
            art.pixel_ring(surf, cx, cy, self.r + 6, (120, 220, 255), density=0.7)
        if self.invuln and (self.boss or self.mini):
            art.pixel_ring(surf, cx, cy, self.r + 14, (150, 230, 255), density=0.9)
        if self.stone:
            art.pixel_ring(surf, cx, cy, self.r + 10, (160, 160, 180), density=0.7)
        a = self.ai
        if a == "vortex":
            for k in range(3):
                ang = self.angle + k * 2.094
                art.pixel_disc(surf, cx + math.cos(ang) * 62, cy + math.sin(ang) * 62, 9, (255, 110, 220))
            art.pixel_ring(surf, cx, cy, 300, (150, 90, 220), density=0.25)
        elif a == "crawler" and self.state == "fuse" and (self.timer // 4) % 2 == 0:
            art.pixel_ring(surf, cx, cy, 78, (255, 100, 60), density=0.7)
        elif a == "pod":
            art.pixel_arc(surf, cx, cy, 30, -1.57, -1.57 + 6.28 * self.timer / 600.0, (255, 190, 60), thick=1)
        elif a == "harvester" and self.state in ("hook", "pull"):
            art.pixel_line(surf, cx, cy, int(self.hx) + ox, int(self.hy) + oy, (170, 170, 190))
            art.pixel_disc(surf, int(self.hx) + ox, int(self.hy) + oy, 9, (220, 220, 235))
        elif a == "executioner" and self.state == "chop":
            ex, ey = cx + math.cos(self.aim) * 38, cy + math.sin(self.aim) * 38
            art.pixel_ring(surf, ex, ey, 62 * (1 - self.timer / 26.0) + 4, (255, 90, 90), density=0.8)
        elif a == "stalker":
            pass
        if self.burn > 0:
            surf.fill((255, 120, 30), (cx - 3, cy - self.r - 8, 6, 6))
        if self.boss or self.mini or self.hidden:
            return
        if self.hp < self.max_hp or self.elite:
            w = max(24, self.r * 2)
            art.draw_bar(surf, (cx - w // 2, cy - self.r - 14, w, 7), self.hp / self.max_hp,
                         (214, 60, 60) if not self.elite else (190, 100, 240))


def pygame_scaled(img, k):
    import pygame
    w, h = img.get_size()
    return pygame.transform.scale(img, (max(1, int(w * k)), max(1, int(h * k))))
