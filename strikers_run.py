"""
Project Strikers - the gameplay engine for a single run.

`Run` owns every entity and rule (player, enemies, director, skills, weapons, active skills,
mini-bosses and the final boss). 
"""
import math
import os
import random
from types import SimpleNamespace

import pygame

import strikers_art as art
import strikers_data as data
from strikers_enemy import Enemy
from strikers_util import abbr, calc_damage_reduction, clamp
from strikers_world import WorldMixin, disc

FPS = 60
TIME_FREEZE_CD = 180 * FPS               # 3 minute cooldown
SENTRY_LASER_CD = 5 * FPS

_SCALED = {}


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
SCREEN = 900
TIME_SCALE = float(os.environ.get("STRIKERS_TIME_SCALE", "1"))   # dev: >1 fast-forwards the wave timeline
RAR = data.RARITIES
TAU = math.pi * 2
SUSTAIN_CAP = 0.05          # lifesteal + regeneration can heal at most 5% max HP per second

REWARD_WEIGHT_MULT = [0.45, 0.9, 1.5, 2.6, 2.3]


class Run(WorldMixin):
    def __init__(self, perks, keybinds, map_def):
        self.perks, self.keys, self.map = perks, keybinds, map_def
        self.diff = map_def.get("diff", 1.0)
        self.hz = 1.0 + (self.diff - 1.0) * 0.5            # extra bite for boss / mini-boss projectiles
        self.god = False                                    # dev switch for tests
        self.frame, self.time = 0, 0.0
        self.status = "playing"            # playing | levelup | won | dead
        self.px, self.py, self.pr = 450.0, 640.0, 14
        self.pvx = self.pvy = 0.0
        self.facing = 1
        self.last_dir = (0.0, -1.0)
        self.skills = {}
        self.weapons, self.actives = [], []
        self.wcd, self.cds = {}, {}
        self.level, self.exp, self.total_exp = 1, 0.0, 0.0
        self.pending, self.reward_pending = 0, 0
        self.choices, self.forced, self.pick_kind = [], False, "level"
        self.pity_high = self.pity_leg = 0
        self.rerolls, self.bans = perks.get("reroll", 0), perks.get("ban", 0)
        self.banned = set()
        self.revives = 1 if perks.get("revive", 0) > 0 else 0
        self.gold_f, self.kills, self.boss_bonus = 0.0, {}, 0
        self.enemies, self.bullets = [], []
        self.gems, self.coins, self.foods = [], [], []
        self.telegraphs = []
        self.fx, self.parts, self.texts, self.toasts, self.banners, self.announces = [], [], [], [], [], []
        self.axes, self.potions, self.ppools = [], [], []
        self.springs, self.blizzards, self.meteors = [], [], []
        self.kill_queue = []
        self.init_world()
        # timers / state
        self.invuln = self.rev_invuln = self.dash_t = self.dash_cd = self.fire_cd = self.flash_p = self.shake = 0
        self.dash_dir = (0.0, -1.0)
        self.freeze = 0
        self.sw_t = self.sw_cd = 0
        self.shield_ready, self.shield_t = False, 0
        self.rep_t, self.mag_t, self.pull_t = 600, 1800, 0
        self.oc_t = 0
        self.bm_t = 0
        self.surge_cd = 0
        self.adr, self.adr_t = 0, 0
        self.tf_cd = 0                      # Time Freeze cooldown (frames); 0 = ready
        self.orb_ang = 0.0
        self.sword_ang = 0.0
        self.aura_t = 0
        self.sentry = None
        self.sustain = 0.0
        self.near_n = 0
        self.dark, self.dark_target, self.boss_flash = 0.0, 0.0, 0
        self._dark_surf = None
        # progression of the run
        self.boss_spawned = False
        self.boss = None
        self.boss_name = data.ENEMIES[map_def["boss"]]["name"]
        self.form_cd = {}
        self.next_elite = 420.0
        self.fusions = set()
        self.seen = set()
        self.corpse_warned = False
        self.corpse_kind = {"glade": "acid", "wasteland": "sludge", "castle": "curse"}.get(map_def.get("theme"), "acid")
        self.mini = None
        self.minis_done = 0
        self.mini_next = float(data.MINI_FIRST_AT)
        pool = list(map_def.get("minis", []))
        self.mini_picks = random.sample(pool, min(2, len(pool)))
        self.max_hp = None
        self.hp = 1.0
        self.recompute()
        self.hp = self.max_hp
        self.sustain = SUSTAIN_CAP * self.max_hp
        for _ in range(perks.get("head_start", 0)):
            pool = [s for s in self.available_skills() if s["rarity"] == "common" and not s["slot"]]
            if pool:
                self.add_skill(random.choice(pool)["id"], toast=False)
        vet = perks.get("veteran", 0)
        if vet:
            self.level += vet
            self.pending += vet

    # ------------------------------------------------------------------ stats
    def S(self, k):
        return self.skills.get(k, 0)

    def P(self, k):
        return self.perks.get(k, 0)

    def recompute(self):
        S, P = self.S, self.P
        old = self.max_hp
        self.max_hp = (100 + 10 * P("max_hp")) * (1 + 0.10 * S("vitality") + 0.15 * S("titan"))
        if old is not None and self.max_hp > old:
            self.hp += self.max_hp - old
        self.atk = 12 * (1 + 0.03 * P("might") + 0.10 * S("strength") + 0.25 * S("titan")) * (2.0 if self.bm_t > 0 else 1.0)
        self.crit_chance = 5 + 2 * P("crit") + 5 * S("crit_rate")
        self.crit_dmg = 100 + 5 * P("crit") + 10 * S("crit_dmg")
        self.atk_speed = 1 + 0.05 * P("atk_speed") + 0.15 * S("fast_hands") + 0.20 * S("gale")
        self.base_speed = data.BASE_PLAYER_SPEED * (1 + 0.03 * P("move_speed")) * (1 - 0.05 * S("fortress")) * (1 + 0.10 * S("gale"))
        self.n_proj = 1 + P("multishot") + S("extra_barrel")
        self.size_mult = 1.0 + 0.20 * P("big_hits")
        self.pickup_r = 70 * (1 + 0.2 * P("magnet"))
        self.xp_mult = 1 + 0.05 * P("yield") + 0.2 * S("scholar")
        self.gold_mult = 1 + 0.05 * P("yield") + 0.3 * S("greed")
        self.reduction = min(0.75, calc_damage_reduction(4 * P("armor")) + 0.10 * S("hardened") + 0.20 * S("fortress"))
        self.dodge = 0.02 * P("dodge")
        self.regen = 0.5 * P("regen")
        self.pen = 0.06 * P("pen")
        self.knock = 1.2 * P("pen")
        self.aoe_lvl = P("aoe")
        old_f = set(self.fusions)
        self.fusions = {f[2] for f in data.FUSIONS if P("synergy") > 0 and S(f[0]) and S(f[1])}
        for name in self.fusions - old_f:
            self.toast("FUSION: " + name + "!", (255, 220, 120))

    def weapon_n(self):
        """Projectiles per shot for weapons: every Extra Barrel counts in full, Projectile Multiplier at half rate."""
        return 1 + self.S("extra_barrel") + self.P("multishot") // 2

    def aura_rad(self):
        return (85 + 15 * (max(1, self.S("burn_aura")) - 1)) * self.size_mult

    def hp_scale(self):
        """Exponential-ish run-time growth: gentle early, brutal after ~12 minutes."""
        m = self.time / 60.0
        s = 1 + 0.12 * m + 0.004 * m * m
        s *= 1 + 0.3 * (self.diff - 1.0)
        return s * (1.1 if self.S("greed") else 1.0)

    def dmg_scale(self):
        m = self.time / 60.0
        return 1 + 0.03 * m + 0.006 * max(0.0, m - 10.0) ** 2 + 0.0008 * max(0.0, m - 14.0) ** 3

    def burn_dmg(self):
        n = max(1, self.S("burn_aura"))
        return 0.35 * self.atk * (1 + 0.5 * (n - 1)) * self.out_mult()

    def out_mult(self):
        return 1.5 if self.S("glass_cannon") else 1.0

    def in_mult(self):
        return 1.25 if self.S("glass_cannon") else 1.0

    def berserk_steps(self):
        if not self.S("berserker"):
            return 0.0
        return max(0.0, (1.0 - self.hp / self.max_hp) * 100.0 / 2.0)

    def cur_speed(self):
        s = self.base_speed * (1 + 0.02 * self.adr) * (1.3 if self.sw_t > 0 else 1.0)
        if self.slow_t > 0:
            s *= self.slow_mult
        if self.haze_now:
            s *= 0.85
        if self.border and self.in_border():
            s *= 0.65
        return s

    def atk_speed_now(self):
        s = self.atk_speed * (2.0 if self.oc_t > 0 else 1.0) * (1 + 0.01 * self.berserk_steps())
        if self.suppress_t > 0:
            s *= 0.5
        return s

    def cd_rate(self):
        r = 1 + 0.05 * self.P("arcane")
        if self.suppress_t > 0:
            r *= 0.5
        return r

    def dash_cooldown(self):
        return int(240 * (0.85 ** max(0, self.P("dash") - 1)))

    def in_border(self):
        w = self.border_w
        return self.px < w or self.px > SCREEN - w or self.py < w or self.py > SCREEN - w

    @property
    def gold(self):
        return int(self.gold_f)

    @property
    def map_gold(self):
        return 1.0 + 0.25 * (self.map.get("order", 1) - 1)

    def toast(self, text, color=(255, 255, 255), ttl=150):
        self.toasts.append(dict(text=text, color=color, ttl=ttl))
        del self.toasts[:-4]

    def banner(self, text, color=(255, 220, 120), ttl=150):
        self.banners = [dict(text=text, color=color, ttl=ttl, max=ttl)]

    def announce(self, text, color=(255, 226, 140), ttl=170):
        self.announces.append(dict(text=text, color=color, ttl=ttl, max=ttl))
        del self.announces[:-3]

    def float_text(self, x, y, text, color):
        if len(self.texts) < 40:
            self.texts.append(dict(x=x, y=y, text=text, color=color, ttl=40))

    def spark(self, x, y, color=(255, 240, 160), n=4):
        if len(self.parts) > 260:
            return
        for _ in range(n):
            a = random.uniform(0, 6.28)
            self.parts.append(dict(x=x, y=y, vx=math.cos(a) * 2, vy=math.sin(a) * 2, ttl=14, color=color))

    def heal(self, amt, src="food"):
        if src in ("regen", "steal", "spring") and self.wound_t > 0:
            amt *= 0.5
        if src == "regen" and self.rad_t > 0:
            amt *= 0.5
        if src in ("regen", "steal"):
            amt = min(amt, self.sustain)
            self.sustain -= amt
        if amt > 0:
            self.hp = min(self.max_hp, self.hp + amt)

    # --------------------------------------------------------------- skills
    @property
    def cast_ids(self):
        return [a for a in self.actives if a not in data.AUTO_ACTIVES]

    def add_skill(self, sid, toast=True):
        sk = data.SKILL_BY_ID[sid]
        self.skills[sid] = self.skills.get(sid, 0) + 1
        if sk["slot"] == "weapon" and sid not in self.weapons:
            self.weapons.append(sid)
            self.wcd[sid] = 20
        elif sk["slot"] == "active" and sid not in self.actives:
            self.actives.append(sid)
            self.cds[sid] = 0.0
        if sid == "shatter_shield":
            self.shield_ready = True
        elif sid == "sentry":
            self.sentry = dict(x=self.px - 55, y=self.py - 45, cd=20, laser=SENTRY_LASER_CD // 2, charge=0, aim=0.0)
        self.recompute()
        if sk["rarity"] in ("epic", "legendary"):
            self.pity_high = 0
        if sk["rarity"] == "legendary":
            self.pity_leg = 0
        if toast:
            self.toast("Gained: " + sk["name"], art.RARITY_COLORS[sk["rarity"]])

    def rarity_weights(self, boost=False):
        t = clamp((self.level - 1) / float(data.RARITY_SCALE_LEVEL - 1), 0.0, 1.0)
        w = [e + (l - e) * t for e, l in zip(data.RARITY_EARLY_WEIGHTS, data.RARITY_LATE_WEIGHTS)]
        luck = 1 + 0.08 * self.P("luck")
        for i in (2, 3, 4):
            w[i] *= luck
        pity_at = max(3, data.PITY_HIGH_AFTER - self.P("fate"))
        if self.pity_high >= pity_at:
            b = 2.0 + 0.5 * (self.pity_high - pity_at)
            w[3] *= b
            w[4] *= b
        if boost:
            w = [x * m for x, m in zip(w, REWARD_WEIGHT_MULT)]
        return w

    def available_skills(self):
        out = []
        castable = bool(self.cast_ids)
        for s in data.SKILLS:
            if self.skills.get(s["id"], 0) >= s["max"] or s["id"] in self.banned:
                continue
            if s["slot"] == "weapon" and len(self.weapons) >= data.MAX_WEAPONS:
                continue
            if s["slot"] == "active" and len(self.actives) >= data.MAX_ACTIVES:
                continue
            if s["needs"] == "active" and not castable:
                continue
            out.append(s)
        return out

    def roll_choices(self, count=data.CHOICES_PER_LEVEL, pity=True, exclude=(), boost=False):
        by_r = {r: [] for r in RAR}
        for s in self.available_skills():
            if s["id"] not in exclude:
                by_r[s["rarity"]].append(s)
        chosen = []
        self.forced = False
        pity_leg = max(4, data.PITY_LEGENDARY_AFTER - self.P("fate"))
        if pity and self.pity_leg >= pity_leg and by_r["legendary"]:
            s = random.choice(by_r["legendary"])
            by_r["legendary"].remove(s)
            chosen.append(s)
            self.forced = True
        weights = self.rarity_weights(boost)
        if boost and not any(c["rarity"] in ("epic", "legendary") for c in chosen):
            hi = [(i, r) for i, r in enumerate(RAR) if i >= 3 and by_r[r]]       # the guaranteed epic+
            if hi:
                r = random.choices([r for _, r in hi], weights=[weights[i] for i, _ in hi])[0]
                s = random.choice(by_r[r])
                by_r[r].remove(s)
                chosen.append(s)
        while len(chosen) < count:
            avail = [(i, r) for i, r in enumerate(RAR) if by_r[r]]
            if not avail:
                break
            r = random.choices([r for _, r in avail], weights=[weights[i] for i, _ in avail])[0]
            s = random.choice(by_r[r])
            by_r[r].remove(s)
            chosen.append(s)
        random.shuffle(chosen)
        return chosen

    def begin_pick(self):
        self.pick_kind = "reward" if self.reward_pending > 0 else "level"
        self.choices = self.roll_choices(boost=(self.pick_kind == "reward"))
        if not self.choices:
            if self.pick_kind == "reward":
                self.reward_pending = 0
            else:
                self.pending = 0
            return
        self.status = "levelup"

    begin_levelup = begin_pick

    def pick(self, i):
        if self.status != "levelup" or i >= len(self.choices):
            return
        sk = self.choices[i]
        self.add_skill(sk["id"], toast=False)
        if sk["rarity"] not in ("epic", "legendary"):
            self.pity_high += 1
        if sk["rarity"] != "legendary":
            self.pity_leg += 1
        if self.pick_kind == "reward":
            self.reward_pending -= 1
        else:
            self.pending -= 1
        self.status = "playing"
        if self.reward_pending > 0 or self.pending > 0:
            self.begin_pick()

    def reroll(self):
        if self.status == "levelup" and self.rerolls > 0:
            self.rerolls -= 1
            self.choices = self.roll_choices(boost=(self.pick_kind == "reward"))

    def ban(self, i):
        if self.status == "levelup" and self.bans > 0 and i < len(self.choices):
            self.bans -= 1
            self.banned.add(self.choices[i]["id"])
            keep = [c for c in self.choices if c["id"] not in self.banned]
            new = self.roll_choices(1, pity=False, exclude=[c["id"] for c in keep], boost=(self.pick_kind == "reward"))
            self.choices = keep + new
            random.shuffle(self.choices)

    def gain_exp(self, v):
        v *= self.xp_mult
        self.exp += v
        self.total_exp += v
        while self.exp >= data.exp_needed(self.level):
            self.exp -= data.exp_needed(self.level)
            self.level += 1
            self.pending += 1

    # ----------------------------------------------------------- active skills
    def use_active(self, name):
        if self.S("overclock"):
            self.oc_t = 600

    def cast(self, slot):
        if self.status != "playing":
            return False
        ids = self.cast_ids
        if slot < 0 or slot >= len(ids):
            return False
        sid = ids[slot]
        if self.cds.get(sid, 0) > 0:
            return False
        if self.S("blood_magic"):
            cost = min(0.15 * self.max_hp, self.hp - 1.0)       # never kills: you are left with 1 HP at worst
            if cost > 0:
                self.hp -= cost
                self.float_text(self.px, self.py - 40, "-%d HP" % cost, (200, 40, 70))
            self.bm_t = 600
            self.recompute()                                    # attack x2 for 10s
        getattr(self, "cast_" + sid)()
        self.cds[sid] = data.ACTIVE_COOLDOWN[sid] * 60.0
        self.use_active(sid)
        return True

    def dense_spot(self, maxd=720):
        best, bn = None, -1
        cands = [e for e in self.enemies if not e.untargetable and not e.hidden and 20 < e.x < SCREEN - 20 and 20 < e.y < SCREEN - 20
                 and math.hypot(e.x - self.px, e.y - self.py) < maxd]
        if len(cands) > 40:
            cands = random.sample(cands, 40)
        for e in cands:
            n = sum(1 for o in cands if abs(o.x - e.x) < 150 and abs(o.y - e.y) < 150)
            n += 4 if (e.mini or e.boss) else 0
            if n > bn:
                best, bn = e, n
        if best:
            return best.x, best.y
        return (clamp(self.px + self.last_dir[0] * 220, 80, 820), clamp(self.py + self.last_dir[1] * 220, 80, 820))

    def cast_meteor_shower(self):
        x, y = self.dense_spot()
        self.meteors.append(dict(x=x, y=y, t=50, total=50, r=310))
        self.banner("METEOR SHOWER!", (255, 150, 60), 50)

    def cast_healing_spring(self):
        self.springs.append(dict(x=self.px, y=self.py, life=600, r=100))
        self.fx.append(dict(kind="ring", x=self.px, y=self.py, r=10, max_r=100, ttl=20, color=(120, 255, 170)))

    def cast_blizzard(self):
        self.blizzards.append(dict(t=300, r=135, tick=0))
        self.fx.append(dict(kind="ring", x=self.px, y=self.py, r=10, max_r=135, ttl=20, color=(170, 225, 255)))

    # --------------------------------------------------------------- damage
    def contact_mult(self, n):
        """More bodies touching you = disproportionately more damage (no AFK tanking)."""
        if n <= 4:
            return 1 + 0.1 * (n - 1)
        k = n - 4
        return 1.3 + 0.28 * k + 0.03 * k * k

    def hurt_player(self, dmg, dot=False, pierce=0.0, wound=0, contact=False):
        if self.status != "playing" or self.god:
            return False
        if self.dash_t > 0 or self.rev_invuln > 0:
            return False
        if not dot and self.invuln > 0:
            return False
        if random.random() < self.dodge:
            self.float_text(self.px, self.py - 30, "DODGE", (150, 220, 255))
            if not dot:
                self.invuln = 20
            return False
        if self.shield_ready:
            self.shield_ready, self.shield_t = False, 900
            self.blast(self.px, self.py, 150, 40 + self.atk * 2, (120, 200, 255), knock=9)
            self.invuln = 40
            return False
        red = min(0.8, self.reduction + (0.3 if self.sw_t > 0 else 0))
        dens = max(0.5, 1.0 - 0.035 * max(0, self.near_n - 8))      # surrounded: armour works worse
        red = red * dens * (1.0 - pierce)
        final = dmg * (1 - red) * self.in_mult()
        if self.P("last_stand") and self.hp < 0.35 * self.max_hp:
            final *= 1 - 0.07 * self.P("last_stand")
        self.hp -= final
        self.flash_p = 6
        if wound:
            self.wound_t = max(self.wound_t, wound)
            self.toast("GRIEVOUS WOUND: healing halved!", (255, 120, 120), 100)
        if not dot:
            self.invuln = 18 if (contact and self.near_n >= 6) else 30
            self.shake = max(self.shake, 6)
            if self.P("thorns"):
                self.blast(self.px, self.py, 110, 15 * self.P("thorns") + 0.5 * self.atk, (255, 150, 80), knock=7)
        self.float_text(self.px, self.py - 24, str(int(final)), (255, 90, 90))
        if self.hp <= 0:
            self.lethal()
        return True

    def lethal(self):
        if self.S("time_freeze") and self.tf_cd <= 0:
            self.tf_cd = TIME_FREEZE_CD
            self.hp = max(1.0, 0.15 * self.max_hp)
            self.freeze = 180
            self.rev_invuln = 90
            self.use_active("time_freeze")
            self.banner("TIME FREEZE!", (140, 220, 255), 120)
            return
        if self.revives > 0:
            self.revives -= 1
            self.hp = self.max_hp * (0.75 if self.P("revive") >= 2 else 0.5)
            self.rev_invuln = 120
            self.blast(self.px, self.py, 260, 60 + self.atk * 3, (255, 230, 150), knock=14)
            self.banner("REVIVED!", (255, 230, 150), 120)
            return
        self.hp = 0
        self.status = "dead"

    def blast(self, x, y, r, dmg, color, knock=0):
        self.fx.append(dict(kind="ring", x=x, y=y, r=8, max_r=r, ttl=18, color=color))
        for e in self.enemies:
            if e.dying or e.remove:
                continue
            dx, dy = e.x - x, e.y - y
            if dx * dx + dy * dy <= (r + e.r) ** 2:
                d = math.hypot(dx, dy) or 1.0
                self.damage_enemy(e, dmg, False, "aoe", (dx / d * knock, dy / d * knock) if knock else None)

    def explode(self, x, y, r, dmg):
        self.fx.append(dict(kind="ring", x=x, y=y, r=8, max_r=r, ttl=14, color=(255, 120, 50)))
        self.spark(x, y, (255, 160, 60), 10)
        if math.hypot(self.px - x, self.py - y) < r + self.pr:
            self.hurt_player(dmg)

    def damage_enemy(self, e, dmg, crit, src, kb=None, fr=0.0):
        if e.dying or e.remove or e.intangible:
            return 0
        if e.invuln or e.stone:
            self.spark(e.x, e.y - e.r * 0.3, (190, 210, 240), 2)
            return 0
        if src != "env":
            dmg *= self.out_mult()
            if (e.elite or e.mini or e.boss) and self.P("boss_slayer"):
                dmg *= 1 + 0.05 * self.P("boss_slayer")
            if self.S("executioner") and e.hp < 0.3 * e.max_hp:
                dmg *= 1.5
            if self.S("giant_slayer"):                    # % max HP bonus, scaled to the hit and hard-capped on big targets
                frac = 0.04 if not (e.boss or e.mini) else 0.002
                cap = 40 * self.atk if not (e.boss or e.mini) else 2.5 * self.atk
                dmg += min(e.max_hp * frac, cap) * min(1.0, dmg / max(1.0, self.atk))
        if e.boss or e.mini:                              # adaptive armour: absurd DPS gets partly absorbed
            e.acc += dmg
            est = e.acc / 5.0
            ref = 450.0 if e.boss else 250.0
            e.adapt = min(0.85, 1 - (ref / est) ** 0.7) if est > ref else 0.0
            dmg *= 1 - e.adapt
        armor = clamp(e.armor + (0.4 if e.buffed else 0.0) - self.pen, 0.0, 0.9)
        if fr:
            armor = 1.0 - (1.0 - armor) * (1.0 - fr)
        dmg *= (1 - armor)
        if e.eshield > 0:
            ab = min(e.eshield, dmg)
            e.eshield -= ab
            dmg -= ab
            e.flash = 3
        if dmg <= 0:
            return 0
        e.hp -= dmg
        e.flash = 5
        if crit:
            self.float_text(e.x, e.y - e.r, str(int(dmg)), (255, 120, 240))
        if src != "env":
            rate = 0.005 * self.berserk_steps() + 0.004 * self.P("bloodthirst")
            if rate > 0:
                self.heal(dmg * rate, "steal")
        e.on_damaged()
        if kb is not None and not (e.boss or e.mini):
            e.kbx += kb[0]
            e.kby += kb[1]
        if e.hp <= 0 and not e.dying:
            if e.pre_death():
                e.hp = max(1.0, e.max_hp * 0.001)
            else:
                e.dying = True
                self.kill_queue.append(e)
        return dmg

    def chain(self, src_e, dmg):
        cand = []
        for e in self.enemies:
            if e is src_e or e.untargetable:
                continue
            d = math.hypot(e.x - src_e.x, e.y - src_e.y)
            if d < 200:
                cand.append((d, e))
        cand.sort(key=lambda t: t[0])
        for _, e in cand[:3]:
            self.damage_enemy(e, dmg, False, "aoe")
            self.fx.append(dict(kind="line", x=src_e.x, y=src_e.y, x2=e.x, y2=e.y, ttl=8, color=(190, 230, 255)))

    def bullet_hit(self, b, e, fr=0.0):
        kb = (b.vx / 11.0 * self.knock, b.vy / 11.0 * self.knock) if self.knock else None
        self.damage_enemy(e, b.dmg, b.crit, "bullet", kb, fr)
        self.spark(b.x, b.y, (255, 240, 160) if not b.crit else (255, 130, 240), 2 if b.weapon else 3)
        if b.shard:
            return
        if self.S("splinter") and not b.weapon:
            n = 5 if "Shrapnel Storm" in self.fusions else 3
            base = random.uniform(0, 6.28)
            for i in range(n):
                a = base + i * 2 * math.pi / n
                self.bullets.append(self.mk_bullet(b.x, b.y, a, 8, b.dmg * 0.4, False, 4, 18, shard=True, ignore=e, img="shard"))
        ch = self.S("chain_lightning")
        if ch and random.random() < (0.25 + 0.10 * (ch - 1)) * (0.4 if b.weapon else 1.0):
            self.chain(e, b.dmg * 0.6)
        if self.aoe_lvl and not b.weapon:
            rad = 24 + 8 * self.aoe_lvl
            self.fx.append(dict(kind="ring", x=b.x, y=b.y, r=4, max_r=rad, ttl=8, color=(255, 220, 140)))
            for o in self.enemies:
                if o is e or o.untargetable:
                    continue
                if math.hypot(o.x - b.x, o.y - b.y) < rad + o.r:
                    self.damage_enemy(o, b.dmg * 0.35, False, "aoe")

    # ----------------------------------------------------------------- kills
    def process_kills(self):
        n = 0
        while self.kill_queue and n < 500:
            e = self.kill_queue.pop()
            n += 1
            if not e.remove:
                self.on_kill(e)

    def drop_pickup(self, lst, x, y, v):
        if lst is self.gems and len(lst) > 220:
            random.choice(lst).v += v
            return
        lst.append(SimpleNamespace(x=x + random.uniform(-8, 8), y=y + random.uniform(-8, 8), v=v, magnet=False))

    def on_kill(self, e):
        e.remove = True
        d = e.d
        self.kills[e.kind] = self.kills.get(e.kind, 0) + 1
        self.spark(e.x, e.y, (230, 230, 230), 6)
        if d["exp"]:
            self.drop_pickup(self.gems, e.x, e.y, d["exp"])
        S = self.S
        luck = self.P("luck")
        scav = S("scavenger")
        mg = self.map_gold
        if e.mini or e.elite:
            g = d["gold"] * (1 + 0.1 * self.P("bounty")) * mg
            n = 6 if e.mini else 4
            for _ in range(n):
                self.drop_pickup(self.coins, e.x, e.y, g / float(n))
            if random.random() < (1.0 if e.mini else 0.6):
                self.drop_pickup(self.foods, e.x, e.y, 1)
        elif d["gold"]:
            if random.random() < 0.15 + 0.12 * scav + 0.02 * luck:
                self.drop_pickup(self.coins, e.x, e.y, d["gold"] * mg)
            if random.random() < 0.012 + 0.04 * scav + 0.004 * luck:
                self.drop_pickup(self.foods, e.x, e.y, 1)
        if S("vampiric"):
            self.heal(0.01 * S("vampiric") * self.max_hp, "steal")
        if S("adrenaline"):
            self.adr, self.adr_t = min(10, self.adr + 1), 300
        if S("explosive_finale") and e.max_hp > 0 and not e.boss:
            frac = 0.45 if "Reaper's Blast" in self.fusions else 0.30
            self.fx.append(dict(kind="ring", x=e.x, y=e.y, r=6, max_r=90, ttl=14, color=(255, 150, 60)))
            for o in self.enemies:
                if o.untargetable or o is e:
                    continue
                if math.hypot(o.x - e.x, o.y - e.y) < 90 + o.r:
                    self.damage_enemy(o, frac * e.max_hp, False, "aoe")
        if e.kind == "slime":
            for sgn in (-1, 1):
                self.spawn_enemy("slimelet", e.x + sgn * 10, e.y)
        # late game: the dead poison the floor (anti-AFK)
        if not (e.mini or e.boss or e.elite) and d["cost"] > 0 and self.time > 540 and len(self.pools) < 45 \
                and e.kind not in ("pod", "guard", "vespera_clone", "slimelet"):
            if random.random() < min(0.24, 0.05 + (self.time - 540) / 2600.0):
                self.add_pool(e.x, e.y, 30, 330, self.corpse_kind, 3.5 * self.dmg_scale())
        if e.mini:
            self.mini_defeated(e)
        if e.boss and d["ai"] != "vclone":
            self.win()

    def mini_defeated(self, e):
        self.mini = None
        self.minis_done += 1
        self.mini_next = self.time + data.MINI_GAP
        self.reward_pending += 1
        self.ebullets, self.zones, self.beam_list, self.bushes, self.ringq = [], [], [], [], []
        self.hazes, self.mines, self.lobs = [], [], []
        for o in self.enemies:
            if o is not e and o.boss_ref is e:
                o.remove = True
        self.banner("MINI-BOSS DEFEATED!", (255, 226, 140), 150)
        self.fx.append(dict(kind="ring", x=e.x, y=e.y, r=10, max_r=260, ttl=24, color=(255, 226, 140)))
        for g in self.gems:
            g.magnet = True

    def win(self):
        for o in self.enemies:
            if o is not self.boss and not o.remove:
                o.remove = True
        self.ebullets, self.lobs, self.pools, self.walls = [], [], [], []
        self.zones, self.beam_list, self.mines, self.hazes, self.bushes = [], [], [], [], []
        self.dark_target = 0.0
        order = self.map.get("order", 1)
        self.boss_bonus = int(300 * (1 + 0.1 * self.P("bounty")) * (1.0 + 0.4 * (order - 1)))
        self.gold_f += self.boss_bonus
        for g in self.gems:
            self.gain_exp(g.v)
        self.gems = []
        self.status = "won"

    # ---------------------------------------------------------- projectiles
    def mk_bullet(self, x, y, ang, speed, dmg, crit, r, life, shard=False, ignore=None, img="bolt", weapon=False, pierce=0):
        return SimpleNamespace(x=x, y=y, vx=math.cos(ang) * speed, vy=math.sin(ang) * speed, dmg=dmg, crit=crit,
                               r=r, life=life, shard=shard, ignore=ignore, img=img, weapon=weapon, pierce=pierce, hits=None, ang=ang)

    def roll_crit(self, atk, crit_c=None, crit_d=None):
        crit_c = self.crit_chance if crit_c is None else crit_c
        crit_d = self.crit_dmg if crit_d is None else crit_d
        crit = random.random() * 100 < crit_c
        return (atk * (1 + crit_d / 100.0), True) if crit else (atk, False)

    def fire_volley(self, tgt, atk, crit_c, crit_d, n, size_mult=1.0, from_xy=None):
        sx, sy = from_xy or (self.px, self.py)
        base = math.atan2(tgt.y - sy, tgt.x - sx)
        if len(self.bullets) > 300:
            return
        for i in range(n):
            a = base + (i - (n - 1) / 2.0) * 0.13
            dmg, crit = self.roll_crit(atk, crit_c, crit_d)
            r = 5 * (1 + 0.08 * self.aoe_lvl) * size_mult * self.size_mult
            self.bullets.append(self.mk_bullet(sx, sy, a, 11, dmg, crit, r, 70, img="bolt_crit" if crit else "bolt"))

    def nearest(self, x, y, maxd):
        best, bd = None, maxd * maxd
        for e in self.enemies:
            if e.untargetable or e.hidden:
                continue
            if e.x < -20 or e.x > SCREEN + 20 or e.y < -20 or e.y > SCREEN + 20:
                continue
            d = (e.x - x) ** 2 + (e.y - y) ** 2
            if d < bd:
                best, bd = e, d
        return best

    # ------------------------------------------------------------- spawning
    def spawn_enemy(self, kind, x, y, heading=None):
        e = Enemy(self, kind, x, y, heading)
        e.acc, e.adapt = 0.0, 0.0
        self.enemies.append(e)
        d = e.d
        if e.boss and d["ai"] != "vclone":
            self.boss = e
        if e.mini:
            self.mini = e
        elif d.get("plural") and kind not in self.seen and not d.get("quiet") and not e.boss:
            self.seen.add(kind)
            self.announce("%s Appear!" % d["plural"], (255, 150, 90) if e.elite else (255, 226, 140))
        return e

    def edge_pos(self, side=None, buf=40):
        side = random.randrange(4) if side is None else side
        if side == 0:
            return random.uniform(0, SCREEN), -buf
        if side == 1:
            return SCREEN + buf, random.uniform(0, SCREEN)
        if side == 2:
            return random.uniform(0, SCREEN), SCREEN + buf
        return -buf, random.uniform(0, SCREEN)

    def add_telegraph(self, x, y, r, frames, spawns):
        self.telegraphs.append(dict(x=x, y=y, r=r, t=frames, total=frames, spawns=spawns))

    def phase(self):
        ph = self.map["phases"][0]
        for p in self.map["phases"]:
            if self.time >= p["start"]:
                ph = p
        return ph

    def threat_cap(self):
        pts = self.map["threat_curve"]
        t = self.time
        cap = pts[-1][1]
        for (t0, c0), (t1, c1) in zip(pts, pts[1:]):
            if t0 <= t <= t1:
                cap = c0 + (c1 - c0) * (t - t0) / float(t1 - t0)
                break
        if self.mini is not None and not self.mini.remove:
            cap *= 0.45                           # the mini-boss is the main event
        return cap

    def start_boss(self):
        self.boss_spawned = True
        for e in self.enemies:
            e.remove = True
            self.fx.append(dict(kind="ring", x=e.x, y=e.y, r=4, max_r=26, ttl=12, color=(230, 230, 230)))
        self.mini = None
        self.enemies, self.ebullets, self.lobs, self.pools = [], [], [], []
        self.walls, self.telegraphs, self.kill_queue = [], [], []
        self.zones, self.beam_list, self.mines, self.hazes, self.bushes, self.ringq = [], [], [], [], [], []
        self.border, self.border_w = True, 48
        self.spawn_enemy(self.map["boss"], 450, -110)
        self.banner(self.boss_name.upper() + " APPROACHES", (255, 90, 70), 200)

    def mini_manager(self):
        if self.mini is not None and not self.mini.remove:
            return
        self.mini = None
        if self.minis_done >= len(self.mini_picks) or self.time < self.mini_next:
            return
        kind = self.mini_picks[self.minis_done]
        far = max(range(4), key=lambda s: math.hypot(self.edge_pos(s, 60)[0] - self.px, self.edge_pos(s, 60)[1] - self.py) + random.random() * 80)
        x, y = self.edge_pos(far, 60)
        self.spawn_enemy(kind, clamp(x, 40, 860), clamp(y, 40, 860))
        self.banner("MINI-BOSS: " + data.ENEMIES[kind]["name"].upper(), (255, 226, 140), 170)

    def director(self):
        if self.boss_spawned:
            return
        if self.time >= self.map["duration"]:
            self.start_boss()
            return
        if self.frame % 12:
            return
        self.mini_manager()
        ph = self.phase()
        for k in list(self.form_cd):
            self.form_cd[k] = max(0, self.form_cd[k] - 12)
        cur = sum(e.threat for e in self.enemies if not e.dying and not e.remove)
        for tl in self.telegraphs:
            cur += sum(data.ENEMIES[s[0]]["cost"] for s in tl["spawns"])
        if not self.corpse_warned and self.time >= 540:
            self.corpse_warned = True
            self.announce("The fallen now poison the ground!", (150, 230, 90), 220)
        mini_up = self.mini is not None
        if ph["elites"] and not mini_up and self.time >= self.next_elite and sum(1 for e in self.enemies if e.elite and not e.dying) < 2:
            kind = random.choice(self.map["elite_kinds"])
            x, y = self.edge_pos()
            self.spawn_enemy(kind, x, y)
            self.next_elite = self.time + random.uniform(90, 130) * (0.75 if ph["start"] >= 700 else 1.0)
        room = self.threat_cap() - cur
        if room < 1:
            return
        costs = dict(trickle=1, swarm=10, ring=16, wall=18, ambush=12, phalanx=24)
        opts = [(f, w) for f, w in ph["forms"].items() if self.form_cd.get(f, 0) <= 0 and room >= costs[f]
                and not (f == "phalanx" and not self.map.get("phalanx_kind"))]
        if not opts:
            return
        form = random.choices([f for f, _ in opts], weights=[w for _, w in opts])[0]
        getattr(self, "form_" + form)(ph, room)

    def form_trickle(self, ph, room):
        if random.random() > 0.6:
            return
        ranged_alive = sum(1 for e in self.enemies if e.d.get("ranged") and not e.dying and not e.elite)
        swarm_kind = self.map["swarm_kind"]
        nph = len([p for p in self.map["phases"] if p["start"] <= self.time])
        for _ in range(random.randint(1, 3)):
            ch = [(k, w) for k, w in ph["types"].items() if data.ENEMIES[k]["cost"] <= room]
            if not ch:
                break
            kind = random.choices([k for k, _ in ch], weights=[w for _, w in ch])[0]
            if data.ENEMIES[kind].get("ranged") and ranged_alive >= 2 + nph:
                kind = swarm_kind
            if data.ENEMIES[kind].get("ranged"):
                ranged_alive += 1
            room -= data.ENEMIES[kind]["cost"]
            if kind == "spinner":
                x, y = 450, 300
                for _try in range(10):
                    x, y = random.uniform(80, 820), random.uniform(80, 820)
                    if math.hypot(x - self.px, y - self.py) > 240:
                        break
                self.add_telegraph(x, y, 26, 60, [(kind, x, y, None)])
            else:
                x, y = self.edge_pos()
                self.spawn_enemy(kind, x, y)

    def form_swarm(self, ph, room):
        kind = self.map["swarm_kind"]
        cost = data.ENEMIES[kind]["cost"]
        n = int(min(room // cost, random.randint(10, 22)))
        side = random.randrange(4)
        along = self.px if side in (0, 2) else self.py
        for _ in range(n):
            x, y = self.edge_pos(side, 40 + random.randint(0, 70))
            if side in (0, 2):
                x = clamp(along + random.uniform(-260, 260), 0, SCREEN)
            else:
                y = clamp(along + random.uniform(-260, 260), 0, SCREEN)
            self.spawn_enemy(kind, x, y)
        self.form_cd["swarm"] = 420

    def form_ring(self, ph, room):
        kind = self.map["swarm_kind"]
        n = int(min(room // data.ENEMIES[kind]["cost"], random.randint(16, 22)))
        self.banner("SURROUNDED!", (255, 120, 90), 70)
        for i in range(n):
            a = i / float(n) * 2 * math.pi
            x = clamp(self.px + math.cos(a) * 270, 24, 876)
            y = clamp(self.py + math.sin(a) * 270, 24, 876)
            self.add_telegraph(x, y, 16, 75, [(kind, x, y, None)])
        self.form_cd["ring"] = 1500

    def form_wall(self, ph, room):
        kind = self.map["swarm_kind"]
        side = random.randrange(4)
        along = self.px if side in (0, 2) else self.py
        gap = clamp(along + random.uniform(-200, 200), 80, 820)
        speed = 2.5
        heading = {0: math.pi / 2, 1: math.pi, 2: -math.pi / 2, 3: 0.0}[side]
        count = 0
        for pos in range(20, 900, 42):
            if abs(pos - gap) < 64 or count >= room:
                continue
            x, y = self.edge_pos(side, 40)
            if side in (0, 2):
                x = pos
            else:
                y = pos
            e = self.spawn_enemy(kind, x, y, heading)
            e.vx, e.vy = math.cos(heading) * speed, math.sin(heading) * speed
            if e.ai != "straight":
                e.state, e.timer = "march", 170
            count += 1
        self.form_cd["wall"] = 1500

    def form_ambush(self, ph, room):
        kind = self.map["ambush_kind"]
        cost = data.ENEMIES[kind]["cost"]
        n = int(min(room // cost, random.randint(4, 6)))
        for _ in range(n):
            if kind == "crawler":
                a, d = random.uniform(0, 6.28), random.uniform(190, 260)
                x, y = clamp(self.px + math.cos(a) * d, 30, 870), clamp(self.py + math.sin(a) * d, 30, 870)
                self.add_telegraph(x, y, 22, 55, [(kind, x, y, None)])
            elif kind == "dust_crawler":
                a, d = random.uniform(0, 6.28), random.uniform(380, 520)
                self.spawn_enemy(kind, clamp(self.px + math.cos(a) * d, 20, 880), clamp(self.py + math.sin(a) * d, 20, 880))
            else:
                x, y = self.edge_pos()
                self.spawn_enemy(kind, x, y)
        self.form_cd["ambush"] = 900

    def form_phalanx(self, ph, room):
        kind = self.map["phalanx_kind"]
        n = int(min(room // data.ENEMIES[kind]["cost"], random.randint(5, 8)))
        side = random.randrange(4)
        along = self.px if side in (0, 2) else self.py
        for i in range(n):
            pos = clamp(along + (i - (n - 1) / 2.0) * 66, 30, 870)
            x, y = self.edge_pos(side, 50)
            if side in (0, 2):
                x = pos
            else:
                y = pos
            self.spawn_enemy(kind, x, y)
        self.announce("A phalanx of Cursed Armor advances!", (190, 200, 240), 150)
        self.form_cd["phalanx"] = 1500

    # --------------------------------------------------------------- weapons
    def update_weapons(self):
        aspd = self.atk_speed_now()
        for wid in self.weapons:
            self.wcd[wid] -= 1
            if self.wcd[wid] > 0:
                continue
            getattr(self, "w_" + wid)(aspd)

    def w_bow(self, aspd):
        tgt = self.nearest(self.px, self.py, 700)
        if not tgt:
            self.wcd["bow"] = 6
            return
        n = self.weapon_n()
        base = math.atan2(tgt.y - self.py, tgt.x - self.px)
        for i in range(n):
            a = base + (i - (n - 1) / 2.0) * 0.14
            dmg, crit = self.roll_crit(self.atk * 1.0)
            self.bullets.append(self.mk_bullet(self.px, self.py, a, 13, dmg, crit, 6 * self.size_mult, 80, img="arrow", weapon=True, pierce=3))
        self.wcd["bow"] = max(6, int(34 / aspd))

    def w_gunner(self, aspd):
        tgt = self.nearest(self.px, self.py, 650)
        if not tgt:
            self.wcd["gunner"] = 5
            return
        n = self.weapon_n()
        base = math.atan2(tgt.y - self.py, tgt.x - self.px) + random.uniform(-0.05, 0.05)
        for i in range(n):
            if len(self.bullets) >= 300:
                break
            a = base + (i - (n - 1) / 2.0) * 0.09
            dmg, crit = self.roll_crit(self.atk * 0.33)
            self.bullets.append(self.mk_bullet(self.px, self.py, a, 14, dmg, crit, 4 * self.size_mult, 55, img="gunshot", weapon=True))
        self.wcd["gunner"] = max(2, int(8 / aspd))

    def w_axe(self, aspd):
        if not self.nearest(self.px, self.py, 800):
            self.wcd["axe"] = 10
            return
        n = self.weapon_n()
        for _ in range(n):
            dmg, crit = self.roll_crit(self.atk * 1.5)
            self.axes.append(dict(x=self.px, y=self.py - 10, vx=random.uniform(-3.4, 3.4), vy=-random.uniform(11.0, 13.5),
                                  dmg=dmg, crit=crit, hits=set(), spin=0.0))
        self.wcd["axe"] = max(25, int(95 / aspd))

    def w_acid_potion(self, aspd):
        tgt = self.nearest(self.px, self.py, 520)
        if not tgt:
            self.wcd["acid_potion"] = 10
            return
        for i in range(self.weapon_n()):
            j = 24 if i == 0 else 80
            self.potions.append(dict(sx=self.px, sy=self.py, tx=tgt.x + random.uniform(-j, j), ty=tgt.y + random.uniform(-j, j), t=0, total=40))
        self.wcd["acid_potion"] = max(30, int(105 / aspd))

    def w_spinning_swords(self, aspd):
        self.wcd["spinning_swords"] = 1                       # always active; handled in step_swords

    def step_swords(self):
        if "spinning_swords" not in self.weapons:
            return
        self.sword_ang += 0.085 * min(2.0, 0.7 + 0.3 * self.atk_speed_now())
        n = 4 + self.S("extra_barrel")
        hit_r = 16 * self.size_mult
        for k in range(n):
            a = self.sword_ang + k * 2 * math.pi / n
            sx, sy = self.px + math.cos(a) * 80, self.py + math.sin(a) * 80
            for e in self.enemies:
                if e.untargetable or e.sw_cd > 0:
                    continue
                if abs(e.x - sx) < e.r + hit_r and abs(e.y - sy) < e.r + hit_r and math.hypot(e.x - sx, e.y - sy) < e.r + hit_r:
                    e.sw_cd = 26
                    dmg, crit = self.roll_crit(self.atk * 1.2)
                    d = math.hypot(e.x - self.px, e.y - self.py) or 1.0
                    self.damage_enemy(e, dmg, crit, "aoe", ((e.x - self.px) / d * 4, (e.y - self.py) / d * 4))
                    self.spark(sx, sy, (230, 240, 255), 2)

    def step_axes(self):
        keep = []
        for a in self.axes:
            a["x"] += a["vx"]
            a["y"] += a["vy"]
            a["vy"] += 0.42
            a["spin"] += 0.35
            if a["vy"] > 0:                                      # falling: hits everything it passes through
                for e in self.enemies:
                    if e.untargetable or id(e) in a["hits"]:
                        continue
                    if abs(e.x - a["x"]) < e.r + 22 * self.size_mult and abs(e.y - a["y"]) < e.r + 22 * self.size_mult:
                        a["hits"].add(id(e))
                        self.damage_enemy(e, a["dmg"], a["crit"], "aoe")
                        self.spark(a["x"], a["y"], (255, 220, 160), 3)
            if a["y"] < SCREEN + 70 and -80 < a["x"] < SCREEN + 80:
                keep.append(a)
        self.axes = keep

    def step_potions(self):
        keep = []
        for p in self.potions:
            p["t"] += 1
            if p["t"] >= p["total"]:
                self.ppools.append(dict(x=p["tx"], y=p["ty"], r=64 * self.size_mult, life=210, tick=0))
                self.fx.append(dict(kind="ring", x=p["tx"], y=p["ty"], r=6, max_r=64 * self.size_mult, ttl=12, color=(120, 240, 90)))
            else:
                keep.append(p)
        self.potions = keep
        for pp in self.ppools:
            pp["life"] -= 1
            pp["tick"] += 1
            if pp["tick"] % 10 == 0:
                for e in self.enemies:
                    if e.untargetable:
                        continue
                    if math.hypot(e.x - pp["x"], e.y - pp["y"]) < pp["r"] + e.r:
                        self.damage_enemy(e, self.atk * 0.10, False, "aoe")
        self.ppools = [p for p in self.ppools if p["life"] > 0]

    def step_actives(self):
        rate = self.cd_rate()
        for sid in self.actives:
            if self.cds.get(sid, 0) > 0:
                self.cds[sid] = max(0.0, self.cds[sid] - rate)
        if self.bm_t > 0:
            self.bm_t -= 1
            if self.bm_t == 0:
                self.recompute()
        keep = []
        for m in self.meteors:
            m["t"] -= 1
            if m["t"] <= 0:
                self.shake = 16
                self.fx.append(dict(kind="ring", x=m["x"], y=m["y"], r=10, max_r=m["r"], ttl=22, color=(255, 150, 60)))
                self.fx.append(dict(kind="ring", x=m["x"], y=m["y"], r=6, max_r=m["r"] * 0.6, ttl=16, color=(255, 230, 150)))
                for e in self.enemies:
                    if e.untargetable:
                        continue
                    d = math.hypot(e.x - m["x"], e.y - m["y"])
                    if d < m["r"] + e.r:
                        dmg, crit = self.roll_crit(self.atk * 3.0, self.crit_chance * 0.5)
                        kb = ((e.x - m["x"]) / (d or 1) * 9, (e.y - m["y"]) / (d or 1) * 9)
                        self.damage_enemy(e, dmg, crit, "skill", kb)
                self.spark(m["x"], m["y"], (255, 170, 70), 14)
            else:
                keep.append(m)
        self.meteors = keep
        keep = []
        for s in self.springs:
            s["life"] -= 1
            if math.hypot(self.px - s["x"], self.py - s["y"]) < s["r"]:
                self.heal(0.05 * self.max_hp / FPS, "spring")
            if s["life"] > 0:
                keep.append(s)
        self.springs = keep
        keep = []
        for b in self.blizzards:
            b["t"] -= 1
            b["tick"] += 1
            for e in self.enemies:
                if e.untargetable:
                    continue
                if math.hypot(e.x - self.px, e.y - self.py) < b["r"] + e.r:
                    e.slow_t = max(e.slow_t, 30)
                    if b["tick"] % 30 == 0:
                        self.damage_enemy(e, self.atk * 0.20, False, "skill")
            if b["t"] > 0:
                keep.append(b)
        self.blizzards = keep

    def sentry_laser(self, s):
        """Every few seconds the sentry charges and fires a screen-long laser for 200% of your attack."""
        length = 1300.0
        if s["charge"] > 0:
            s["charge"] -= 1
            ex, ey = s["x"] + math.cos(s["aim"]) * length, s["y"] + math.sin(s["aim"]) * length
            if s["charge"] > 0:
                self.fx.append(dict(kind="line", x=s["x"], y=s["y"], x2=ex, y2=ey, ttl=2, color=(120, 220, 255)))
                return
            self.fx.append(dict(kind="beamflash", x=s["x"], y=s["y"], x2=ex, y2=ey, ttl=8))
            self.fx.append(dict(kind="line", x=s["x"], y=s["y"], x2=ex, y2=ey, ttl=8, color=(255, 255, 255)))
            dx, dy = math.cos(s["aim"]), math.sin(s["aim"])
            half = 14 * self.size_mult
            for e in self.enemies:
                if e.untargetable or e.hidden:
                    continue
                t = (e.x - s["x"]) * dx + (e.y - s["y"]) * dy
                if t < 0 or t > length:
                    continue
                if abs((e.x - s["x"]) * dy - (e.y - s["y"]) * dx) <= e.r + half:
                    dmg, crit = self.roll_crit(self.atk * 2.0)
                    self.damage_enemy(e, dmg, crit, "aoe")
            return
        s["laser"] -= 1
        if s["laser"] <= 0:
            tgt = self.nearest(s["x"], s["y"], 1200)
            if tgt:
                s["aim"] = math.atan2(tgt.y - s["y"], tgt.x - s["x"])
                s["charge"] = 24
                s["laser"] = SENTRY_LASER_CD
            else:
                s["laser"] = 30

    def desperate_surge(self):
        self.surge_cd = 3600
        self.invuln = max(self.invuln, 45)
        self.shake = 16
        self.ebullets = []
        self.zones = []
        self.banner("DESPERATE SURGE!", (255, 90, 90), 90)
        self.fx.append(dict(kind="ring", x=self.px, y=self.py, r=10, max_r=760, ttl=26, color=(255, 120, 120)))
        self.fx.append(dict(kind="ring", x=self.px, y=self.py, r=10, max_r=500, ttl=20, color=(255, 230, 200)))
        for e in self.enemies:
            if e.untargetable:
                continue
            if e.boss or e.mini:
                dmg = e.max_hp * 0.03
            elif e.elite:
                dmg = e.max_hp * 0.35
            else:
                dmg = e.max_hp * 10
            self.damage_enemy(e, dmg, False, "env")

    # --------------------------------------------------------------- update
    def update(self, pressed, dash_pressed, casts=()):
        if self.status != "playing":
            return
        self.frame += 1
        self.time = self.frame / float(FPS) * TIME_SCALE
        frozen = self.freeze > 0
        if frozen:
            self.freeze -= 1
        for name in ("invuln", "rev_invuln", "flash_p", "shake", "dash_cd", "oc_t", "surge_cd", "tf_cd"):
            v = getattr(self, name)
            if v > 0:
                setattr(self, name, v - 1)
        if self.adr_t > 0:
            self.adr_t -= 1
            if self.adr_t == 0:
                self.adr = 0
        self.step_status()
        cap = SUSTAIN_CAP * self.max_hp
        self.sustain = min(cap, self.sustain + cap / FPS)
        self.dark += (self.dark_target - self.dark) * 0.04
        if self.boss_flash > 0:
            self.boss_flash -= 1
        for c in casts:
            self.cast(c)

        # ---- movement
        ox0, oy0 = self.px, self.py
        ux = (1 if pressed[self.keys["right"]] else 0) - (1 if pressed[self.keys["left"]] else 0)
        uy = (1 if pressed[self.keys["down"]] else 0) - (1 if pressed[self.keys["up"]] else 0)
        n = math.hypot(ux, uy)
        if n:
            ux, uy = ux / n, uy / n
            self.last_dir = (ux, uy)
            if ux:
                self.facing = 1 if ux > 0 else -1
        spd = self.cur_speed()
        if dash_pressed and self.P("dash") > 0 and self.dash_cd <= 0 and self.dash_t <= 0:
            self.dash_t, self.dash_dir, self.dash_cd = 11, ((ux, uy) if n else self.last_dir), self.dash_cooldown()
            self.root_t = 0
            self.use_active("dash")
        if self.dash_t > 0:
            self.px += self.dash_dir[0] * spd * 3.4
            self.py += self.dash_dir[1] * spd * 3.4
            self.dash_t -= 1
            self.fx.append(dict(kind="ghost", x=self.px, y=self.py, ttl=8))
        elif self.root_t <= 0:
            self.px += ux * spd
            self.py += uy * spd
        if self.push:
            self.px += self.push[0]
            self.py += self.push[1]
            self.push[0] *= 0.86
            self.push[1] *= 0.86
            self.push[2] -= 1
            if self.push[2] <= 0:
                self.push = None
        self.collide_walls()
        self.px = clamp(self.px, self.pr, SCREEN - self.pr)
        self.py = clamp(self.py, self.pr, SCREEN - self.pr)
        self.pvx += ((self.px - ox0) - self.pvx) * 0.35
        self.pvy += ((self.py - oy0) - self.pvy) * 0.35

        # ---- sustain / passives
        if self.regen:
            self.heal(self.regen / FPS, "regen")
        if self.S("second_wind"):
            if self.sw_t > 0:
                self.sw_t -= 1
            elif self.sw_cd > 0:
                self.sw_cd -= 1
            elif self.hp < 0.2 * self.max_hp:
                self.sw_t, self.sw_cd = 360, 2400
                self.toast("Second Wind!", (255, 200, 120), 90)
        if self.S("shatter_shield") and not self.shield_ready:
            self.shield_t -= 1
            if self.shield_t <= 0:
                self.shield_ready = True
        if self.S("desperate_surge") and self.surge_cd <= 0 and self.hp < 0.15 * self.max_hp:
            self.desperate_surge()
        if self.S("repulsion"):
            self.rep_t -= 1
            if self.rep_t <= 0:
                self.rep_t = 600
                self.blast(self.px, self.py, 260, 0, (200, 240, 255), knock=14)
                self.use_active("repulsion")
        if self.S("xp_magnet"):
            self.mag_t -= 1
            if self.mag_t <= 0:
                self.mag_t, self.pull_t = 1800, 120
                self.toast("XP Magnet!", (120, 200, 255), 60)
        if self.pull_t > 0:
            self.pull_t -= 1
        if self.border and self.in_border():
            self.border_tick += 1
            if self.border_tick % 24 == 0:
                self.hurt_player(4 + (self.border_w - 48) / 22.0, dot=True)

        # ---- aura / orbs / sentry
        bn = self.S("burn_aura")
        if bn:
            self.aura_t += 1
            rad = self.aura_rad()
            if self.aura_t % 12 == 0:
                for e in self.enemies:
                    if not e.untargetable and math.hypot(e.x - self.px, e.y - self.py) < rad + e.r:
                        e.burn = 120
            if "Storm Aura" in self.fusions and self.aura_t % 90 == 0:
                near = [e for e in self.enemies if not e.untargetable and math.hypot(e.x - self.px, e.y - self.py) < rad + 60]
                for e in random.sample(near, min(2, len(near))):
                    self.damage_enemy(e, 0.8 * self.atk, False, "aoe")
                    self.fx.append(dict(kind="line", x=self.px, y=self.py, x2=e.x, y2=e.y, ttl=8, color=(190, 230, 255)))
        if self.S("orbital_barrage"):
            self.orb_ang += 0.06
            n_orb = 3 + self.S("extra_barrel")
            for k in range(n_orb):
                a = self.orb_ang + k * 2 * math.pi / n_orb
                ox, oy = self.px + math.cos(a) * 95, self.py + math.sin(a) * 95
                for e in self.enemies:
                    if e.untargetable or e.orb_cd > 0:
                        continue
                    if math.hypot(e.x - ox, e.y - oy) < e.r + 10 * self.size_mult:
                        e.orb_cd = 20
                        self.damage_enemy(e, 0.6 * self.atk, False, "aoe")
        if self.sentry:
            s = self.sentry
            s["x"] += (self.px - 55 - s["x"]) * 0.1
            s["y"] += (self.py - 45 - s["y"]) * 0.1
            s["cd"] -= 1
            if s["cd"] <= 0:
                tgt = self.nearest(s["x"], s["y"], 560)
                if tgt:
                    self.fire_volley(tgt, self.atk, self.crit_chance, self.crit_dmg, 1 + self.S("extra_barrel"), 1.0, (s["x"], s["y"]))
                s["cd"] = max(5, int(24 / self.atk_speed_now()))
            self.sentry_laser(s)

        # ---- player attacks
        self.fire_cd -= 1
        if self.fire_cd <= 0:
            tgt = self.nearest(self.px, self.py, 600)
            if tgt:
                self.fire_volley(tgt, self.atk, self.crit_chance, self.crit_dmg, self.n_proj)
                self.fire_cd = max(5, int(24 / self.atk_speed_now()))
            else:
                self.fire_cd = 4
        self.update_weapons()
        self.step_swords()
        self.step_axes()
        self.step_potions()
        self.step_actives()

        # ---- world
        self.director()
        for tl in self.telegraphs:
            tl["t"] -= 1
            if tl["t"] <= 0:
                for kind, x, y, hd in tl["spawns"]:
                    self.spawn_enemy(kind, x, y, hd)
        self.telegraphs = [t for t in self.telegraphs if t["t"] > 0]
        if not frozen:
            self.beam_list = []
            for e in self.enemies:
                e.buffed = False
            for c in self.enemies:
                if c.ai == "commander" and not c.dying:
                    for e in self.enemies:
                        if e is not c and not e.elite and not e.boss and not e.mini and abs(e.x - c.x) < 190 and abs(e.y - c.y) < 190 \
                                and math.hypot(e.x - c.x, e.y - c.y) < 190:
                            e.buffed = True
            for e in list(self.enemies):
                if not e.dying and not e.remove:
                    e.update()
                    if e.acc > 0:
                        e.acc *= 0.99667
            self.process_beams()
            self.contact_step()
            self.step_ebullets()
            self.step_lobs()
            self.step_zones()
            self.step_pools()
            self.step_mines()
            self.step_hazes()
        self.step_bullets()
        self.process_kills()
        self.enemies = [e for e in self.enemies if not e.remove]
        self.step_walls()
        self.step_pickups()
        self.step_effects()
        if self.status == "playing" and (self.reward_pending > 0 or self.pending > 0):
            self.begin_pick()

    def contact_step(self):
        px, py, pr = self.px, self.py, self.pr
        touching, near = [], 0
        for e in self.enemies:
            if e.dying or e.remove:
                continue
            dx, dy = px - e.x, py - e.y
            if abs(dx) < 130 and abs(dy) < 130 and not e.d.get("nocontact") and not e.mini and not e.boss:
                near += 1
            if e.d.get("nocontact") or e.intangible or e.hidden:
                continue
            rr = e.r + pr - 2
            if abs(dx) < rr and abs(dy) < rr and dx * dx + dy * dy < rr * rr:
                cd = e.contact_dmg()
                if cd > 0:
                    touching.append((cd, e))
        self.near_n = near
        if not touching:
            return
        n = len(touching)
        best = max(c for c, _ in touching)
        pierce = max(e.pierce for _, e in touching)
        if self.hurt_player(best * self.contact_mult(n), pierce=pierce, contact=True):
            for _, e in touching:
                if e.d.get("drain"):                               # blood bats feed their friends
                    for o in self.enemies:
                        if o is not e and not o.dying and not o.remove and not o.boss and not o.mini and abs(o.x - e.x) < 130 \
                                and abs(o.y - e.y) < 130:
                            o.hp = min(o.max_hp, o.hp + 0.10 * o.max_hp)
                    self.fx.append(dict(kind="ring", x=e.x, y=e.y, r=4, max_r=100, ttl=10, color=(220, 60, 90)))
                    break

    # ---- sub-steps
    def step_bullets(self):
        keep = []
        walls = [w["rect"] for w in self.walls if w["t"] <= 0]
        for b in self.bullets:
            b.x += b.vx
            b.y += b.vy
            b.life -= 1
            if b.life <= 0 or b.x < -20 or b.x > SCREEN + 20 or b.y < -20 or b.y > SCREEN + 20:
                continue
            if walls and any(r.collidepoint(b.x, b.y) for r in walls):
                self.spark(b.x, b.y)
                continue
            if self.bushes:
                hb = None
                for bu in self.bushes:
                    if abs(bu["x"] - b.x) < bu["r"] + b.r and abs(bu["y"] - b.y) < bu["r"] + b.r:
                        hb = bu
                        break
                if hb is not None:
                    hb["hp"] -= b.dmg
                    self.spark(b.x, b.y, (150, 220, 90), 3)
                    continue
            hit = None
            for e in self.enemies:
                if e.dying or e.remove or e.intangible or e is b.ignore:
                    continue
                if b.hits is not None and id(e) in b.hits:
                    continue
                rr = e.r + b.r
                dx = e.x - b.x
                if dx > rr or dx < -rr:
                    continue
                dy = e.y - b.y
                if dy > rr or dy < -rr:
                    continue
                if dx * dx + dy * dy <= rr * rr:
                    hit = e
                    break
            if hit is None:
                keep.append(b)
                continue
            if hit.invuln or hit.stone:
                self.spark(b.x, b.y, (190, 210, 240))
                continue
            fr = hit.front_reduction(b.x, b.y)
            if fr >= 1.0:
                self.spark(b.x, b.y, (190, 210, 240))
                continue
            self.bullet_hit(b, hit, fr)
            if b.pierce > 0:
                b.pierce -= 1
                if b.hits is None:
                    b.hits = set()
                b.hits.add(id(hit))
                keep.append(b)
        self.bullets = keep

    def step_pickups(self):
        pr2 = self.pickup_r ** 2
        pull = self.pull_t > 0
        for lst, kind in ((self.gems, "gem"), (self.coins, "coin"), (self.foods, "food")):
            keep = []
            for g in lst:
                dx, dy = self.px - g.x, self.py - g.y
                d2 = dx * dx + dy * dy
                if d2 < (pr2 if kind != "food" else 1600) or (pull and kind == "gem"):
                    g.magnet = True
                if g.magnet:
                    d = math.sqrt(d2) or 1.0
                    s = 7.5 + max(0.0, (300 - d) / 60.0)
                    g.x += dx / d * s
                    g.y += dy / d * s
                if d2 < 26 * 26:
                    if kind == "gem":
                        self.gain_exp(g.v)
                    elif kind == "coin":
                        self.gold_f += g.v * self.gold_mult
                    else:
                        self.heal(0.12 * self.max_hp, "food")
                    continue
                keep.append(g)
            lst[:] = keep

    def step_effects(self):
        for l in (self.fx, self.parts, self.texts, self.toasts, self.banners, self.announces):
            for o in l:
                o["ttl"] -= 1
            l[:] = [o for o in l if o["ttl"] > 0]
        for p in self.parts:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
        for t in self.texts:
            t["y"] -= 0.8

    # ----------------------------------------------------------------- draw
    def draw(self, surf, bg):
        ox = random.randint(-3, 3) if self.shake > 0 else 0
        oy = random.randint(-3, 3) if self.shake > 0 else 0
        surf.blit(bg, (ox, oy))
        if self.border:
            self.draw_border(surf)
        self.draw_world_under(surf, ox, oy)
        for pp in self.ppools:
            fade = min(1.0, pp["life"] / 50.0)
            disc(surf, pp["x"] + ox, pp["y"] + oy, pp["r"], (90, 220, 70), int(110 * fade))
            art.pixel_ring(surf, pp["x"] + ox, pp["y"] + oy, pp["r"], (190, 255, 120), density=0.5)
        for s in self.springs:
            fade = min(1.0, s["life"] / 50.0)
            disc(surf, s["x"] + ox, s["y"] + oy, s["r"], (90, 230, 150), int(80 * fade))
            art.pixel_ring(surf, s["x"] + ox, s["y"] + oy, s["r"], (190, 255, 220), density=0.5)
            for k in range(4):
                a = self.frame * 0.05 + k * 1.57
                surf.fill((220, 255, 240), (int(s["x"] + math.cos(a) * s["r"] * 0.6) + ox, int(s["y"] - ((self.frame + k * 15) % 60)) + oy, 4, 4))
            art.pixel_disc(surf, s["x"] + ox, s["y"] + oy, 12, (80, 170, 255))
        for b in self.blizzards:
            disc(surf, self.px + ox, self.py + oy, b["r"], (170, 220, 255), 55)
            art.pixel_ring(surf, self.px + ox, self.py + oy, b["r"], (210, 240, 255), density=0.5)
            for k in range(14):
                a = self.frame * 0.07 + k * 0.45
                rr = (k * 37 + self.frame * 2) % b["r"]
                surf.fill((255, 255, 255), (int(self.px + math.cos(a * 2 + k) * rr) + ox, int(self.py + math.sin(a * 2 + k) * rr) + oy, 4, 4))
        for tl in self.telegraphs:
            if (tl["t"] // 5) % 2 == 0:
                art.pixel_ring(surf, tl["x"] + ox, tl["y"] + oy, tl["r"], (255, 70, 70), density=0.8)
            art.pixel_disc(surf, tl["x"] + ox, tl["y"] + oy, 6, (255, 90, 90))
        for e in self.enemies:
            e.draw_tele(surf)
        for m in self.meteors:
            frac = 1 - m["t"] / float(m["total"])
            art.pixel_ring(surf, m["x"] + ox, m["y"] + oy, m["r"], (255, 90, 60), density=0.8)
            art.pixel_ring(surf, m["x"] + ox, m["y"] + oy, m["r"] * frac, (255, 200, 90), density=0.8)
        gem = art.misc("gem")
        for g in self.gems:
            surf.blit(gem, gem.get_rect(center=(int(g.x) + ox, int(g.y) + oy + int(math.sin(self.frame * 0.1 + g.x) * 2))))
        for g in self.coins:
            surf.blit(art.misc("coin"), art.misc("coin").get_rect(center=(int(g.x) + ox, int(g.y) + oy)))
        for g in self.foods:
            surf.blit(art.misc("food"), art.misc("food").get_rect(center=(int(g.x) + ox, int(g.y) + oy)))
        bn = self.S("burn_aura")
        if bn:
            art.pixel_ring(surf, self.px + ox, self.py + oy, self.aura_rad(), (255, 120, 40), density=0.5)
        for e in sorted(self.enemies, key=lambda q: q.y):
            e.draw(surf, ox, oy)
        for f in self.fx:
            if f["kind"] == "ghost":
                g = art.sprite("player", "ghost", self.facing < 0)
                surf.blit(g, g.get_rect(center=(int(f["x"]) + ox, int(f["y"]) + oy)))
        if self.sentry:
            art.pixel_disc(surf, self.sentry["x"] + ox, self.sentry["y"] + oy, 9, (120, 220, 255))
            art.pixel_ring(surf, self.sentry["x"] + ox, self.sentry["y"] + oy, 12, (255, 255, 255), density=0.6)
        if self.S("orbital_barrage"):
            n_orb = 3 + self.S("extra_barrel")
            for k in range(n_orb):
                a = self.orb_ang + k * 2 * math.pi / n_orb
                art.pixel_disc(surf, self.px + ox + math.cos(a) * 95, self.py + oy + math.sin(a) * 95, 9 * self.size_mult, (255, 190, 60))
        blink = self.invuln > 0 and (self.frame // 3) % 2 == 0
        if not blink:
            mode = "flash" if self.flash_p > 0 else "normal"
            spr = art.sprite("player", mode, self.facing < 0)
            bob = int(math.sin(self.frame * 0.2) * 2)
            surf.blit(spr, spr.get_rect(center=(int(self.px) + ox, int(self.py) + oy + bob)))
        if self.shield_ready:
            art.pixel_ring(surf, self.px + ox, self.py + oy, 32, (130, 210, 255), density=0.8)
        if self.bm_t > 0:
            art.pixel_ring(surf, self.px + ox, self.py + oy, 30 + (self.frame // 4) % 3 * 2, (220, 40, 80), density=0.7)
        if self.root_t > 0:
            art.pixel_ring(surf, self.px + ox, self.py + oy, 24, (190, 130, 255), density=0.9)
            art.pixel_ring(surf, self.px + ox, self.py + oy, 18, (130, 90, 200), density=0.9)
        if "spinning_swords" in self.weapons:
            sw = art.misc("sword")
            n_sw = 4 + self.S("extra_barrel")
            for k in range(n_sw):
                a = self.sword_ang + k * 2 * math.pi / n_sw
                img = scaled(art.rot(sw, a), self.size_mult)
                surf.blit(img, img.get_rect(center=(int(self.px + math.cos(a) * 80) + ox, int(self.py + math.sin(a) * 80) + oy)))
        for b in self.bullets:
            if b.img in ("arrow", "gunshot"):
                img = art.rot(art.misc(b.img), math.atan2(b.vy, b.vx))
            else:
                img = art.misc(b.img)
            img = scaled(img, self.size_mult)
            surf.blit(img, img.get_rect(center=(int(b.x) + ox, int(b.y) + oy)))
        axe = art.misc("axe")
        for a in self.axes:
            img = scaled(art.rot(axe, a["spin"]), self.size_mult)
            surf.blit(img, img.get_rect(center=(int(a["x"]) + ox, int(a["y"]) + oy)))
        pot = art.misc("potion")
        for p in self.potions:
            frac = p["t"] / float(p["total"])
            x = p["sx"] + (p["tx"] - p["sx"]) * frac
            y = p["sy"] + (p["ty"] - p["sy"]) * frac - math.sin(frac * math.pi) * 90
            img = scaled(art.rot(pot, frac * 14), self.size_mult)
            surf.blit(img, img.get_rect(center=(int(x) + ox, int(y) + oy)))
        for m in self.meteors:
            frac = m["t"] / float(m["total"])
            img = art.misc("meteor")
            surf.blit(img, img.get_rect(center=(int(m["x"]) + ox, int(m["y"] - frac * 520) + oy)))
        dark_on = self.dark > 0.03
        if not dark_on:
            self.draw_ebullets(surf, ox, oy)
        self.draw_fx(surf, ox, oy)
        for p in self.parts:
            surf.fill(p["color"], (int(p["x"]) + ox, int(p["y"]) + oy, 4, 4))
        for t in self.texts:
            art.draw_text(surf, t["text"], (int(t["x"]) + ox, int(t["y"]) + oy), 20, t["color"])
        if dark_on:
            self.draw_darkness(surf)
            self.draw_ebullets(surf, ox, oy)
        if self.haze_in > 0.02:
            v = art.vignette((230, 200, 90))
            v.set_alpha(int(255 * min(1.0, self.haze_in)))
            surf.blit(v, (0, 0))
        self.draw_hud(surf)

    def draw_ebullets(self, surf, ox, oy):
        for b in self.ebullets:
            if abs(b.vx) + abs(b.vy) > 0.2:
                b.ang = math.atan2(b.vy, b.vx)
            img = art.bullet_img(b.kind, getattr(b, "ang", 0.0))
            surf.blit(img, img.get_rect(center=(int(b.x) + ox, int(b.y) + oy)))

    def draw_border(self, surf):
        w = self.border_w
        pulse = 130 + int(60 * math.sin(self.frame * 0.1))
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
        """Eclipse Realm: everything black except a glow around the player and brief flashes at Vespera."""
        if self._dark_surf is None:
            self._dark_surf = pygame.Surface((SCREEN // 2, SCREEN // 2), pygame.SRCALPHA)
        ds = self._dark_surf
        ds.fill((4, 2, 12, int(236 * min(1.0, self.dark))))
        hole = art.light_hole(66)
        ds.blit(hole, (int(self.px / 2) - 66, int(self.py / 2) - 66), special_flags=pygame.BLEND_RGBA_MIN)
        if self.boss_flash > 0:
            h2 = art.light_hole(30)
            for e in self.enemies:
                if e.ai in ("vespera", "vclone") and not e.dying:
                    ds.blit(h2, (int(e.x / 2) - 30, int(e.y / 2) - 30), special_flags=pygame.BLEND_RGBA_MIN)
        surf.blit(pygame.transform.scale(ds, (SCREEN, SCREEN)), (0, 0))

    # ------------------------------------------------------------------ HUD
    def draw_hud(self, surf):
        surf.blit(art.misc("heart"), (24, 22))
        art.draw_bar(surf, (60, 22, 270, 26), self.hp / self.max_hp, (206, 52, 62))
        art.draw_text(surf, "%d / %d" % (max(0, self.hp), self.max_hp), (195, 35), 18, art.CREAM)
        art.draw_text(surf, "Lv %d" % self.level, (28, 62), 24, art.GOLD, "topleft")
        surf.blit(art.misc("coin_ui"), (28, 92))
        art.draw_text(surf, str(self.gold), (56, 92), 22, art.GOLD, "topleft")
        y = 124
        if self.P("dash"):
            ready = self.dash_cd <= 0
            art.draw_bar(surf, (28, y, 110, 14), 1.0 - self.dash_cd / float(max(1, self.dash_cooldown())), (100, 200, 255) if ready else (80, 110, 150))
            art.draw_text(surf, "DASH", (142, y + 7), 14, art.CREAM, "midleft")
            y += 22
        tags = []
        if self.wound_t > 0:
            tags.append(("WOUNDED  heal -50%", (255, 110, 110)))
        if self.rad_t > 0:
            tags.append(("IRRADIATED  regen -50%", (130, 255, 120)))
        if self.suppress_t > 0:
            tags.append(("SUPPRESSED  speed/cooldowns -50%", (190, 130, 255)))
        if self.slow_t > 0:
            tags.append(("SLOWED", (150, 200, 255)))
        if self.root_t > 0:
            tags.append(("ROOTED  (dash breaks free)", (210, 160, 255)))
        if self.bm_t > 0:
            tags.append(("BLOOD MAGIC  attack x2  %ds" % (self.bm_t // 60 + 1), (255, 90, 120)))
        if self.S("glass_cannon"):
            tags.append(("GLASS CANNON", (255, 190, 120)))
        for text, col in tags:
            art.draw_text(surf, text, (28, y), 15, col, "topleft")
            y += 18
        # timer plate (no wave names any more; new enemies are announced instead)
        shown = max(0, self.map["duration"] - self.time) if not self.boss_spawned else 0
        mm, ss = divmod(int(shown), 60)
        art.draw_panel(surf, (370, 14, 160, 46), art.PANEL_FILL, art.GOLD_DK)
        art.draw_text(surf, "BOSS" if self.boss_spawned else "%02d:%02d" % (mm, ss), (450, 37), 30, art.CREAM)
        # boss / mini-boss bar
        tgt, col = None, (190, 60, 220)
        if self.boss and not self.boss.remove and self.boss.state != "intro":
            tgt = self.boss
        elif self.mini and not self.mini.remove:
            tgt, col = self.mini, (230, 160, 60)
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
        art.draw_text(surf, "WEAPONS %d/%d" % (len(self.weapons), data.MAX_WEAPONS), (70, 823), 13, art.PARCHMENT, shadow=False)
        for i in range(data.MAX_WEAPONS):
            bx = 16 + i * 38
            pygame.draw.rect(surf, art.SHADOW, (bx, 834, 32, 32))
            if i < len(self.weapons):
                sk = data.SKILL_BY_ID[self.weapons[i]]
                c = art.RARITY_COLORS[sk["rarity"]]
                ic = art.icon(self.weapons[i])
                if ic:
                    surf.blit(ic, (bx + 4, 838))
                pygame.draw.rect(surf, c, (bx, 834, 32, 32), 2)
            else:
                pygame.draw.rect(surf, (70, 60, 76), (bx, 834, 32, 32), 1)
        # passive skill chips
        x, row = 142, 0
        for sid, n in self.skills.items():
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
        art.draw_text(surf, "ACTIVE SKILLS %d/%d" % (len(self.actives), data.MAX_ACTIVES), (799, 808), 13, art.PARCHMENT, shadow=False)
        key_i = 0
        for i in range(data.MAX_ACTIVES):
            bx = 712 + i * 60
            pygame.draw.rect(surf, art.SHADOW, (bx, 818, 52, 50))
            if i < len(self.actives):
                sid = self.actives[i]
                sk = data.SKILL_BY_ID[sid]
                c = art.RARITY_COLORS[sk["rarity"]]
                ic = art.icon(sid)
                if ic:
                    surf.blit(ic, (bx + 14, 822))
                if sid in data.AUTO_ACTIVES:
                    cdv = self.tf_cd
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
                    cdv = self.cds.get(sid, 0)
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
        art.draw_bar(surf, (0, SCREEN - 20, SCREEN, 20), self.exp / float(data.exp_needed(self.level)), (90, 170, 255))
        # toasts, announcements & banners
        ty = 150
        for t in self.toasts:
            art.draw_text(surf, t["text"], (450, ty), 20, t["color"])
            ty += 24
        ay = 215
        for a in self.announces:
            al = min(1.0, a["ttl"] / 30.0)
            col = tuple(int(c * al + 20 * (1 - al)) for c in a["color"])
            art.draw_text(surf, a["text"], (450, ay), 34, col, title=True)
            ay += 40
        for b in self.banners:
            al = min(1.0, b["ttl"] / 30.0)
            col = tuple(int(c * al + 20 * (1 - al)) for c in b["color"])
            art.draw_text(surf, b["text"], (450, 330), 44, col, title=True)
