"""
Project Strikers
================

"""
import math
import sys

import pygame

pygame.init()
SCREEN_SIZE = 900
screen = pygame.display.set_mode((SCREEN_SIZE, SCREEN_SIZE))
pygame.display.set_caption("Project Strikers")
clock = pygame.time.Clock()

import strikers_art as art          # noqa: E402  
import strikers_data as data        # noqa: E402
from strikers_db import Database, DatabaseError, ACTIONS, DEFAULT_KEYS    # noqa: E402
from strikers_run import Run, FPS   # noqa: E402

T = art.draw_text
CREAM, GOLD, GOLD_DK = art.CREAM, art.GOLD, art.GOLD_DK
CARD_W, CARD_H, CARD_GAP = 200, 310, 16
CARD_X0 = (SCREEN_SIZE - (4 * CARD_W + 3 * CARD_GAP)) // 2
CARD_RECTS = [pygame.Rect(CARD_X0 + i * (CARD_W + CARD_GAP), 235, CARD_W, CARD_H) for i in range(4)]
REROLL_RECT = pygame.Rect(240, 575, 190, 56)
BAN_RECT = pygame.Rect(470, 575, 190, 56)


def fmt_time(sec):
    m, s = divmod(int(sec), 60)
    return "%d:%02d" % (m, s)


class App:
    def __init__(self):
        self.db = Database()
        self.state = "title"
        self.frame = 0
        self.mouse = (0, 0)
        self.bg_title = art.make_title_bg()
        self.bg_lobby = art.make_lobby_bg()
        self.bg_maps = {}
        self.thumbs = {}
        self.dim = art.cover_overlay(150)
        self.dim_dark = art.cover_overlay(190)
        self.hero2 = pygame.transform.scale(art.sprite("player"), (96, 96))
        # account
        self.account_id = self.username = self.save = None
        self.perks = {}
        self.keybinds = dict(DEFAULT_KEYS)
        # auth form
        self.auth_mode = "login"
        self.fields = {"user": "", "pass": "", "confirm": ""}
        self.focus = "user"
        self.auth_msg = ("", CREAM)
        # settings / skills
        self.waiting = None
        self.set_msg = ""
        self.branch = 0
        self.sel_perk = None
        self.skill_msg = ""
        # run
        self.run = None
        self.map_def = None
        self.dash = False
        self.ban_mode = False
        self.end_timer = None
        self.result = None
        self.casts = []
        self.victories = set()
        self.map_msg = ""

    # ------------------------------------------------------------------ util
    def hover(self, rect):
        return pygame.Rect(rect).collidepoint(self.mouse)

    def button(self, rect, text, size=28, disabled=False, selected=False):
        art.draw_button(screen, rect, text, hover=self.hover(rect) and not disabled, disabled=disabled, size=size, selected=selected)

    def refresh_save(self):
        self.save = self.db.get_save(self.account_id)
        self.perks = self.db.get_perks(self.save["save_id"])
        self.victories = self.db.victories(self.save["save_id"])

    def is_unlocked(self, m):
        return m.get("requires") is None or m["requires"] in self.victories

    def enter_account(self, aid):
        self.account_id = aid
        self.username = self.db.username(aid)
        self.keybinds = self.db.load_keybinds(aid)
        self.refresh_save()
        self.state = "lobby"

    def logout(self):
        self.account_id = self.username = self.save = None
        self.perks = {}
        self.fields = {"user": "", "pass": "", "confirm": ""}
        self.focus = "user"
        self.auth_msg = ("", CREAM)
        self.state = "auth"

    def map_bg(self, m):
        if m["theme"] not in self.bg_maps:
            self.bg_maps[m["theme"]] = art.make_map_bg(m["theme"])
        return self.bg_maps[m["theme"]]

    # ---------------------------------------------------------------- events
    def handle(self, event):
        getattr(self, "ev_" + self.state)(event)

    @staticmethod
    def lclick(event):
        return event.type == pygame.MOUSEBUTTONDOWN and event.button == 1

    def ev_title(self, event):
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
            self.state = "auth"

    # ---- auth
    def auth_rects(self):
        create = self.auth_mode == "create"
        r = {"tab_login": pygame.Rect(215, 262, 230, 50), "tab_create": pygame.Rect(455, 262, 230, 50),
             "user": pygame.Rect(250, 360, 400, 50), "pass": pygame.Rect(250, 450, 400, 50)}
        y = 540
        if create:
            r["confirm"] = pygame.Rect(250, 540, 400, 50)
            y = 630
        r["submit"] = pygame.Rect(300, y, 300, 60)
        return r

    def ev_auth(self, event):
        rects = self.auth_rects()
        order = ["user", "pass"] + (["confirm"] if self.auth_mode == "create" else [])
        if self.lclick(event):
            if rects["tab_login"].collidepoint(event.pos):
                self.auth_mode, self.auth_msg = "login", ("", CREAM)
            elif rects["tab_create"].collidepoint(event.pos):
                self.auth_mode, self.auth_msg = "create", ("", CREAM)
            elif rects["submit"].collidepoint(event.pos):
                self.submit_auth()
            else:
                for k in order:
                    if rects[k].collidepoint(event.pos):
                        self.focus = k
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_TAB:
                if self.focus not in order:
                    self.focus = "user"
                self.focus = order[(order.index(self.focus) + 1) % len(order)]
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.submit_auth()
            elif event.key == pygame.K_BACKSPACE:
                self.fields[self.focus] = self.fields[self.focus][:-1]
            elif event.unicode and event.unicode.isprintable():
                ch = event.unicode
                if self.focus == "user":
                    if (ch.isalnum() or ch == "_") and ch.isascii() and len(self.fields["user"]) < 16:
                        self.fields["user"] += ch
                elif len(self.fields[self.focus]) < 32:
                    self.fields[self.focus] += ch

    def submit_auth(self):
        u, p = self.fields["user"].strip(), self.fields["pass"]
        if self.auth_mode == "create":
            if p != self.fields["confirm"]:
                self.auth_msg = ("Passwords do not match.", art.CRIMSON_LT)
                return
            aid, msg = self.db.create_account(u, p)
        else:
            aid, msg = self.db.login(u, p)
        if aid is None:
            self.auth_msg = (msg, art.CRIMSON_LT)
        else:
            self.fields = {"user": "", "pass": "", "confirm": ""}
            self.enter_account(aid)

    # ---- lobby
    LOBBY_BTNS = ["PLAY", "SKILL TREE", "SETTINGS", "LOG OUT"]

    def lobby_rects(self):
        return [pygame.Rect(30 + i * 217, 760, 190, 74) for i in range(4)]

    def ev_lobby(self, event):
        if self.lclick(event):
            for name, rect in zip(self.LOBBY_BTNS, self.lobby_rects()):
                if rect.collidepoint(event.pos):
                    if name == "PLAY":
                        self.state = "maps"
                    elif name == "SKILL TREE":
                        self.state, self.skill_msg = "skills", ""
                    elif name == "SETTINGS":
                        self.state, self.waiting, self.set_msg = "settings", None, ""
                    else:
                        self.logout()

    # ---- settings
    BACK_RECT = pygame.Rect(30, 28, 150, 54)

    def key_rects(self):
        return {a: pygame.Rect(470, 300 + i * 90, 260, 62) for i, a in enumerate(ACTIONS)}

    def ev_settings(self, event):
        if self.waiting:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.waiting = None
                elif event.key == pygame.K_SPACE:
                    self.set_msg = "SPACE is reserved for Dash."
                else:
                    for a in ACTIONS:       # swap if the key is already used
                        if a != self.waiting and self.keybinds[a] == event.key:
                            self.keybinds[a] = self.keybinds[self.waiting]
                    self.keybinds[self.waiting] = event.key
                    self.db.save_keybinds(self.account_id, self.keybinds)
                    self.waiting, self.set_msg = None, "Key bindings saved."
            return
        if self.lclick(event):
            if self.BACK_RECT.collidepoint(event.pos):
                self.state = "lobby"
            for a, rect in self.key_rects().items():
                if rect.collidepoint(event.pos):
                    self.waiting, self.set_msg = a, ""

    # ---- skill tree
    def perk_rects(self, branch_id):
        perks = [p for p in data.PERKS if p["branch"] == branch_id]
        rects = {}
        for tier in range(3):
            row = [p for p in perks if p["tier"] == tier]
            for i, p in enumerate(row):
                cx = 450 + (i - (len(row) - 1) / 2.0) * 250
                rects[p["code"]] = pygame.Rect(int(cx - 80), 205 + tier * 175, 160, 120)
        return rects

    def tab_rects(self):
        return [pygame.Rect(30 + i * 217, 112, 190, 52) for i in range(4)]

    UPGRADE_RECT = pygame.Rect(690, 790, 170, 58)

    def perk_state(self, p):
        rank = self.perks.get(p["code"], 0)
        unlocked = p["req"] is None or self.perks.get(p["req"][0], 0) >= p["req"][1]
        cost = data.perk_cost(p["code"], rank) if rank < p["max"] else None
        can = unlocked and cost is not None and self.save["gold"] >= cost
        return rank, unlocked, cost, can

    def ev_skills(self, event):
        if not self.lclick(event):
            return
        if self.BACK_RECT.collidepoint(event.pos):
            self.state = "lobby"
            return
        for i, r in enumerate(self.tab_rects()):
            if r.collidepoint(event.pos):
                self.branch, self.sel_perk = i, None
        bid = data.PERK_BRANCHES[self.branch]["id"]
        for code, r in self.perk_rects(bid).items():
            if r.collidepoint(event.pos):
                self.sel_perk, self.skill_msg = code, ""
        if self.sel_perk and self.UPGRADE_RECT.collidepoint(event.pos):
            ok, msg = self.db.buy_perk(self.save["save_id"], self.sel_perk)
            self.skill_msg = msg
            self.refresh_save()

    # ---- map select
    def map_rects(self):
        n = len(data.MAPS)
        w = min(380, (840 - 30 * (n - 1)) // n)
        x0 = (SCREEN_SIZE - (n * w + 30 * (n - 1))) // 2
        return [pygame.Rect(x0 + i * (w + 30), 150, w, 640) for i in range(n)]

    def ev_maps(self, event):
        if self.lclick(event):
            if self.BACK_RECT.collidepoint(event.pos):
                self.state = "lobby"
                return
            for m, r in zip(data.MAPS, self.map_rects()):
                if pygame.Rect(r.x + 20, r.bottom - 80, r.w - 40, 60).collidepoint(event.pos):
                    if self.is_unlocked(m):
                        self.start_run(m)
                    else:
                        need = data.MAP_BY_ID[m["requires"]]
                        self.map_msg = "Locked! Defeat %s on %s first." % (data.ENEMIES[need["boss"]]["name"], need["name"])

    def start_run(self, m):
        self.map_msg = ""
        self.casts = []
        self.victories_before = set(self.victories)
        self.map_def = m
        self.map_bg(m)
        self.run = Run(dict(self.perks), dict(self.keybinds), m)
        self.dash = False
        self.ban_mode = False
        self.end_timer = None
        self.state = "play"

    # ---- play / level-up
    def ev_play(self, event):
        run = self.run
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE and run.status == "playing":
                self.state = "pause"
            elif event.key == pygame.K_SPACE:
                self.dash = True
            elif run.status == "levelup" and pygame.K_1 <= event.key <= pygame.K_4:
                self.levelup_action(event.key - pygame.K_1)
            elif run.status == "playing" and pygame.K_1 <= event.key <= pygame.K_3:
                self.casts.append(event.key - pygame.K_1)             # active skills: 1, 2, 3
        elif self.lclick(event) and run.status == "levelup":
            for i, r in enumerate(CARD_RECTS[:len(run.choices)]):
                if r.collidepoint(event.pos):
                    self.levelup_action(i)
                    return
            if REROLL_RECT.collidepoint(event.pos):
                run.reroll()
            elif BAN_RECT.collidepoint(event.pos) and run.bans > 0:
                self.ban_mode = not self.ban_mode

    def levelup_action(self, i):
        run = self.run
        if i >= len(run.choices):
            return
        if self.ban_mode:
            run.ban(i)
            self.ban_mode = False
        else:
            run.pick(i)

    def ev_pause(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.state = "play"
        elif self.lclick(event):
            if pygame.Rect(300, 740, 300, 58).collidepoint(event.pos):
                self.state = "play"
            elif pygame.Rect(300, 810, 300, 58).collidepoint(event.pos):
                self.finish_run("abandoned")

    def finish_run(self, result):
        r = self.run
        self.db.record_run(self.save["save_id"], self.map_def["id"], result, r.level, int(r.time), r.kills, r.total_exp, r.gold)
        self.refresh_save()
        newly = [m for m in data.MAPS if m["id"] not in self.victories_before and m.get("requires") in self.victories
                 and m.get("requires") not in self.victories_before]
        self.result = dict(result=result, time=int(r.time), level=r.level, kills=sum(r.kills.values()), gold=r.gold,
                           bonus=r.boss_bonus, skills=sum(r.skills.values()), boss=r.boss_name, minis=r.minis_done,
                           unlocked=[m["name"] for m in newly], map=self.map_def["name"])
        self.state = "result"

    def ev_result(self, event):
        if self.lclick(event) and pygame.Rect(280, 700, 340, 70).collidepoint(event.pos):
            self.state = "lobby"
        elif event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.state = "lobby"

    # ------------------------------------------------------------------ draw
    def draw(self):
        getattr(self, "dr_" + self.state)()

    def dr_title(self):
        screen.blit(self.bg_title, (0, 0))
        bob = int(math.sin(self.frame * 0.04) * 4)
        T(screen, "PROJECT", (450, 150 + bob), 76, art.PARCHMENT, title=True)
        T(screen, "STRIKERS", (450, 235 + bob), 112, GOLD, title=True)
        T(screen, "~ slay the swarm, claim the realm ~", (450, 320), 24, art.PARCHMENT_DK)
        if (self.frame // 30) % 2 == 0:
            T(screen, "- CLICK TO BEGIN -", (450, 800), 34, CREAM)

    def input_box(self, rect, label, text, focused, masked=False):
        T(screen, label, (rect.x, rect.y - 8), 20, art.PARCHMENT, "bottomleft")
        art.draw_panel(screen, rect, (28, 18, 30), GOLD if focused else (110, 84, 52))
        shown = ("*" * len(text)) if masked else text
        if focused and (self.frame // 30) % 2 == 0:
            shown += "|"
        T(screen, shown, (rect.x + 18, rect.centery), 26, CREAM, "midleft", shadow=False)

    def dr_auth(self):
        screen.blit(self.bg_title, (0, 0))
        screen.blit(self.dim, (0, 0))
        create = self.auth_mode == "create"
        rects = self.auth_rects()
        art.draw_panel(screen, (170, 90, 560, 680 if create else 590), art.PANEL_FILL, GOLD_DK, hi=(255, 214, 120))
        T(screen, "ADVENTURER'S GUILD", (450, 160), 46, GOLD, title=True)
        T(screen, "Sign your name in the ledger to enter the realm.", (450, 215), 18, art.PARCHMENT_DK)
        art.draw_button(screen, rects["tab_login"], "LOG IN", self.hover(rects["tab_login"]), size=24, selected=not create)
        art.draw_button(screen, rects["tab_create"], "CREATE ACCOUNT", self.hover(rects["tab_create"]), size=22, selected=create)
        self.input_box(rects["user"], "Hero name", self.fields["user"], self.focus == "user")
        self.input_box(rects["pass"], "Password", self.fields["pass"], self.focus == "pass", True)
        if create:
            self.input_box(rects["confirm"], "Confirm password", self.fields["confirm"], self.focus == "confirm", True)
        self.button(rects["submit"], "ENTER THE REALM" if not create else "FORGE ACCOUNT", 26)
        if self.auth_msg[0]:
            T(screen, self.auth_msg[0], (450, rects["submit"].bottom + 28), 20, self.auth_msg[1])
        T(screen, "TAB switches fields  -  ENTER confirms", (450, 748 if create else 658), 16, art.PARCHMENT_DK)

    def dr_lobby(self):
        screen.blit(self.bg_lobby, (0, 0))
        art.draw_fire(screen, 570, 640, self.frame)
        for tx in (22 * 3, 278 * 3):
            art.draw_fire(screen, tx + 4, 498, self.frame + tx, 2)
        bob = int(math.sin(self.frame * 0.08) * 3)
        screen.blit(self.hero2, self.hero2.get_rect(midbottom=(450, 640 + bob)))
        T(screen, self.username, (450, 570), 22, GOLD)
        # status bar
        art.draw_panel(screen, (20, 16, 860, 78), art.PANEL_FILL, GOLD_DK)
        T(screen, "Hero: " + self.username, (48, 36), 24, CREAM, "midleft")
        T(screen, "Best level: %d" % self.save["level"], (48, 70), 18, art.PARCHMENT, "midleft")
        screen.blit(art.misc("coin_ui"), (620, 28))
        T(screen, "%d gold" % self.save["gold"], (652, 38), 28, GOLD, "midleft")
        T(screen, "Perks: %d ranks" % sum(self.perks.values()), (652, 70), 18, art.PARCHMENT, "midleft")
        T(screen, "THE CAMP", (450, 150), 52, art.PARCHMENT, title=True)
        T(screen, "Gather your strength, then venture out.", (450, 196), 20, art.PARCHMENT_DK)
        for name, rect in zip(self.LOBBY_BTNS, self.lobby_rects()):
            self.button(rect, name, 26)

    def back_button(self, title, sub=None, size=50):
        self.button(self.BACK_RECT, "BACK", 26)
        T(screen, title, (450, 56), size, GOLD, title=True)
        if sub:
            T(screen, sub, (450, 98), 18, art.PARCHMENT_DK)

    def gold_badge(self):
        screen.blit(art.misc("coin_ui"), (722, 30))
        T(screen, "%d" % self.save["gold"], (754, 42), 28, GOLD, "midleft")

    def dr_settings(self):
        screen.blit(self.bg_lobby, (0, 0))
        screen.blit(self.dim_dark, (0, 0))
        art.draw_panel(screen, (90, 130, 720, 680), art.PANEL_FILL, GOLD_DK, hi=(255, 214, 120))
        self.back_button("SETTINGS")
        T(screen, "Movement key bindings", (450, 195), 30, CREAM)
        T(screen, "Click a key, then press the new one  (ESC cancels)", (450, 235), 18, art.PARCHMENT_DK)
        for a, rect in self.key_rects().items():
            T(screen, a.upper(), (190, rect.centery), 34, art.PARCHMENT, "midleft")
            label = "PRESS A KEY..." if self.waiting == a else pygame.key.name(self.keybinds[a]).upper()
            self.button(rect, label, 24 if self.waiting == a else 28, selected=self.waiting == a)
        T(screen, "Dash: SPACE  (unlock it in the Skill Tree)", (450, 700), 20, art.PARCHMENT)
        T(screen, "Pause: ESC     Active skills: 1 / 2 / 3", (450, 732), 20, art.PARCHMENT)
        if self.set_msg:
            T(screen, self.set_msg, (450, 776), 20, art.EMERALD)

    def dr_skills(self):
        screen.blit(self.bg_lobby, (0, 0))
        screen.blit(self.dim_dark, (0, 0))
        self.back_button("SKILL TREE")
        self.gold_badge()
        for i, (b, r) in enumerate(zip(data.PERK_BRANCHES, self.tab_rects())):
            self.button(r, b["name"].upper(), 24, selected=i == self.branch)
        bid = data.PERK_BRANCHES[self.branch]["id"]
        branch_perks = {p["code"]: p for p in data.PERKS if p["branch"] == bid}
        rects = self.perk_rects(bid)
        art.draw_panel(screen, (30, 180, 840, 570), (30, 20, 34), (90, 66, 44))
        # connectors
        for code, p in branch_perks.items():
            if p["req"] and p["req"][0] in rects:
                a, b = rects[p["req"][0]], rects[code]
                lit = self.perks.get(p["req"][0], 0) >= p["req"][1]
                art.pixel_line(screen, a.centerx, a.bottom, b.centerx, b.top, GOLD if lit else (70, 56, 60), 6)
        for code, p in branch_perks.items():
            r = rects[code]
            rank, unlocked, cost, can = self.perk_state(p)
            maxed = rank >= p["max"]
            border = GOLD if maxed else (art.EMERALD if can else ((176, 130, 70) if unlocked else (70, 62, 74)))
            if self.sel_perk == code:
                border = (255, 255, 255)
            fill = (66, 46, 40) if unlocked else (36, 30, 40)
            art.draw_panel(screen, r, fill, border)
            col = CREAM if unlocked else (120, 112, 124)
            for li, line in enumerate(art.wrap_text(p["name"], 19, r.w - 24)[:2]):
                T(screen, line, (r.centerx, r.y + 24 + li * 22), 19, col)
            T(screen, "%d / %d" % (rank, p["max"]), (r.centerx, r.y + 72), 22, GOLD if unlocked else (110, 100, 110))
            tag = "MAX" if maxed else ("%d g" % cost if unlocked else "LOCKED")
            T(screen, tag, (r.centerx, r.y + 98), 17, (art.EMERALD if can else (art.PARCHMENT_DK if unlocked else (130, 90, 90))))
        # info panel
        art.draw_panel(screen, (30, 760, 640, 124), art.PANEL_FILL, GOLD_DK)
        if self.sel_perk:
            p = data.PERK_BY_CODE[self.sel_perk]
            rank, unlocked, cost, can = self.perk_state(p)
            T(screen, p["name"], (52, 776), 24, GOLD, "topleft")
            yy = 806
            for line in art.wrap_text(p["desc"], 17, 590)[:2]:
                T(screen, line, (52, yy), 17, CREAM, "topleft")
                yy += 22
            req = ""
            if p["req"] and not unlocked:
                req = "Requires %s rank %d" % (data.PERK_BY_CODE[p["req"][0]]["name"], p["req"][1])
            T(screen, req or self.skill_msg, (52, 856), 16, art.CRIMSON_LT if req else art.EMERALD, "topleft")
            label = "MAXED" if cost is None else "UPGRADE  %dg" % cost
            self.button(self.UPGRADE_RECT, label, 20, disabled=not can)
        else:
            T(screen, "Select a perk to see details.", (350, 822), 22, art.PARCHMENT_DK)
            T(screen, "Perks are permanent - they stay even if you fall.", (350, 852), 16, art.PARCHMENT_DK)

    def dr_maps(self):
        screen.blit(self.bg_lobby, (0, 0))
        screen.blit(self.dim_dark, (0, 0))
        self.back_button("CHOOSE YOUR QUEST", "Defeat the boss of the Glade to open the other realms.", 40)
        for m, r in zip(data.MAPS, self.map_rects()):
            locked = not self.is_unlocked(m)
            cleared = m["id"] in self.victories
            art.draw_panel(screen, r, art.PANEL_FILL if not locked else (28, 22, 32), GOLD_DK if not locked else (80, 70, 84), hi=(255, 214, 120))
            side = r.w - 40
            key = (m["theme"], side)
            if key not in self.thumbs:
                self.thumbs[key] = pygame.transform.scale(self.map_bg(m), (side, side))
            screen.blit(self.thumbs[key], (r.x + 20, r.y + 20))
            pygame.draw.rect(screen, GOLD_DK if not locked else (80, 70, 84), (r.x + 20, r.y + 20, side, side), 3)
            if locked:
                shade = pygame.Surface((side, side), pygame.SRCALPHA)
                shade.fill((8, 4, 14, 190))
                screen.blit(shade, (r.x + 20, r.y + 20))
                cx, cy = r.centerx, r.y + 20 + side // 2
                pygame.draw.rect(screen, (150, 146, 158), (cx - 30, cy - 6, 60, 46))          # padlock body
                pygame.draw.rect(screen, (70, 66, 80), (cx - 30, cy - 6, 60, 46), 4)
                art.pixel_arc(screen, cx, cy - 4, 20, math.pi, 2 * math.pi, (150, 146, 158), thick=2)
                pygame.draw.rect(screen, (40, 30, 40), (cx - 5, cy + 10, 10, 18))
                T(screen, "LOCKED", (cx, cy + 66), 26, art.CRIMSON_LT)
            elif cleared:
                T(screen, "CLEARED", (r.x + 34, r.y + 32), 18, art.EMERALD, "topleft")
            T(screen, m["name"], (r.centerx, r.y + side + 48), 26, GOLD if not locked else (130, 122, 134), title=True)
            yy = art.draw_wrapped(screen, m["blurb"], r.centerx, r.y + side + 74, r.w - 36, 15, art.CREAM if not locked else (120, 112, 124))
            T(screen, "Boss: %s" % data.ENEMIES[m["boss"]]["name"], (r.centerx, yy + 8), 15, art.PARCHMENT, "midtop")
            T(screen, "Length %s  |  Difficulty %s" % (fmt_time(m["duration"]), "*" * m["order"]), (r.centerx, yy + 30), 14, art.PARCHMENT_DK, "midtop")
            if locked:
                need = data.MAP_BY_ID[m["requires"]]
                art.draw_wrapped(screen, "Defeat %s to unlock" % data.ENEMIES[need["boss"]]["name"], r.centerx, yy + 54, r.w - 36, 14, art.CRIMSON_LT)
            self.button((r.x + 20, r.bottom - 80, r.w - 40, 60), "ENTER" if not locked else "LOCKED", 28, disabled=locked)
        if self.map_msg:
            T(screen, self.map_msg, (450, 826), 20, art.CRIMSON_LT)

    def dr_play(self):
        run = self.run
        if run.status == "playing":
            run.update(pygame.key.get_pressed(), self.dash, self.casts)
            self.dash = False
            self.casts = []
        run.draw(screen, self.map_bg(self.map_def))
        if run.status == "levelup":
            self.draw_levelup()
        elif run.status in ("won", "dead"):
            if self.end_timer is None:
                self.end_timer = 100
            self.end_timer -= 1
            if run.status == "dead":
                screen.blit(self.dim, (0, 0))
                T(screen, "YOU HAVE FALLEN", (450, 430), 70, art.CRIMSON_LT, title=True)
            else:
                T(screen, "BOSS DEFEATED!", (450, 390), 64, GOLD, title=True)
                T(screen, run.boss_name, (450, 450), 30, art.CREAM, title=True)
            if self.end_timer <= 0:
                self.finish_run("victory" if run.status == "won" else "defeat")

    def draw_levelup(self):
        run = self.run
        screen.blit(self.dim_dark, (0, 0))
        if run.pick_kind == "reward":
            T(screen, "MINI-BOSS REWARD!", (450, 118), 60, GOLD, title=True)
            T(screen, "Choose a prize - better odds, at least one Epic or higher%s" % (("   (%d more waiting)" % (run.reward_pending - 1)) if run.reward_pending > 1 else ""),
              (450, 170), 20, CREAM)
        else:
            T(screen, "LEVEL UP!", (450, 118), 64, GOLD, title=True)
            T(screen, "Level %d   -   choose a skill%s" % (run.level - run.pending + 1, ("   (%d more waiting)" % (run.pending - 1)) if run.pending > 1 else ""),
              (450, 170), 22, CREAM)
        if run.forced:
            T(screen, "Fate smiles upon you: a Legendary awaits!", (450, 205), 20, art.RARITY_COLORS["legendary"])
        elif run.pity_high >= data.PITY_HIGH_AFTER:
            T(screen, "Your luck is turning... higher rarities are more likely.", (450, 205), 18, art.RARITY_COLORS["epic"])
        for i, (sk, r) in enumerate(zip(run.choices, CARD_RECTS)):
            col = art.RARITY_COLORS[sk["rarity"]]
            hov = self.hover(r)
            rr = r.move(0, -8) if hov else r
            fill = (70, 44, 50) if (self.ban_mode and hov) else ((58, 42, 62) if hov else art.PANEL_FILL)
            art.draw_panel(screen, rr, fill, col, hi=col)
            label = data.RARITY_LABEL[sk["rarity"]].upper()
            if sk["slot"] == "weapon":
                label += " WEAPON"
            elif sk["slot"] == "active":
                label += " ACTIVE"
            T(screen, label, (rr.centerx, rr.y + 26), 16, col)
            pygame.draw.rect(screen, SHADOW_C, (rr.centerx - 24, rr.y + 48, 48, 48))
            pygame.draw.rect(screen, col, (rr.centerx - 22, rr.y + 50, 44, 44), 3)
            ic = art.icon(sk["id"])
            if ic:
                screen.blit(ic, ic.get_rect(center=(rr.centerx, rr.y + 72)))
            else:
                T(screen, self.abbr(sk["name"]), (rr.centerx, rr.y + 72), 26, col)
            if sk["slot"]:
                tag = "Weapon slot %d / %d" % (len(run.weapons) + 1, data.MAX_WEAPONS) if sk["slot"] == "weapon" else \
                    ("Triggers automatically" if sk["id"] in data.AUTO_ACTIVES else "Hotkey %d" % (len(run.cast_ids) + 1))
                T(screen, tag, (rr.centerx, rr.bottom - 34), 15, (255, 226, 140))
            yy = rr.y + 112
            for line in art.wrap_text(sk["name"], 24, rr.w - 24)[:2]:
                T(screen, line, (rr.centerx, yy), 24, CREAM, "midtop")
                yy += 26
            art.draw_wrapped(screen, sk["desc"], rr.centerx, yy + 8, rr.w - 28, 16, art.PARCHMENT, 3)
            have = run.skills.get(sk["id"], 0)
            if sk["max"] > 1:
                T(screen, "Owned %d / %d" % (have, sk["max"]), (rr.centerx, rr.bottom - 34), 15, art.PARCHMENT_DK)
            T(screen, str(i + 1), (rr.x + 14, rr.y + 12), 14, art.PARCHMENT_DK, "topleft")
            if self.ban_mode:
                T(screen, "BAN", (rr.centerx, rr.bottom - 14), 18, art.CRIMSON_LT)
        self.button(REROLL_RECT, "Reroll (%d)" % run.rerolls, 24, disabled=run.rerolls <= 0)
        self.button(BAN_RECT, "Ban (%d)" % run.bans, 24, disabled=run.bans <= 0, selected=self.ban_mode)
        if self.ban_mode:
            T(screen, "Click a card to ban it from this run", (450, 660), 20, art.CRIMSON_LT)
        T(screen, "Press 1-4 or click a card", (450, 700), 16, art.PARCHMENT_DK)

    @staticmethod
    def abbr(name):
        w = name.replace("'", "").split()
        return (w[0][0] + w[1][0]) if len(w) > 1 else name[:2]

    def dr_pause(self):
        self.run.draw(screen, self.map_bg(self.map_def))
        screen.blit(self.dim_dark, (0, 0))
        art.draw_panel(screen, (150, 90, 600, 780), art.PANEL_FILL, GOLD_DK, hi=(255, 214, 120))
        T(screen, "PAUSED", (450, 140), 56, GOLD, title=True)
        T(screen, "Skills this run (lost when the run ends)", (450, 192), 18, art.PARCHMENT_DK)
        items = list(self.run.skills.items())
        for i, (sid, n) in enumerate(items):
            sk = data.SKILL_BY_ID[sid]
            col = art.RARITY_COLORS[sk["rarity"]]
            x = (172, 362, 552)[i % 3]
            y = 225 + (i // 3) * 26
            T(screen, "%s%s" % (sk["name"], (" x%d" % n) if n > 1 else ""), (x, y), 16, col, "topleft")
        if not items:
            T(screen, "No skills yet.", (450, 300), 22, art.PARCHMENT)
        self.button((300, 740, 300, 58), "RESUME", 26)
        self.button((300, 810, 300, 58), "ABANDON RUN", 24)

    def dr_result(self):
        r = self.result
        screen.blit(self.bg_lobby, (0, 0))
        screen.blit(self.dim_dark, (0, 0))
        art.draw_panel(screen, (180, 110, 540, 700), art.PANEL_FILL, GOLD_DK, hi=(255, 214, 120))
        title, col = {"victory": ("QUEST COMPLETE!", GOLD), "defeat": ("YOU HAVE FALLEN", art.CRIMSON_LT),
                      "abandoned": ("RUN ABANDONED", art.PARCHMENT)}[r["result"]]
        T(screen, title, (450, 190), 58, col, title=True)
        if r["result"] == "victory":
            T(screen, "%s is vanquished." % r["boss"], (450, 245), 22, art.PARCHMENT)
        else:
            T(screen, "Your perks remain - your gold is kept.", (450, 245), 22, art.PARCHMENT)
        rows = [("Time survived", fmt_time(r["time"])), ("Level reached", str(r["level"])),
                ("Enemies slain", str(r["kills"])), ("Mini-bosses slain", "%d / 2" % r["minis"])]
        for i, (k, v) in enumerate(rows):
            y = 330 + i * 56
            T(screen, k, (240, y), 26, CREAM, "midleft")
            T(screen, v, (660, y), 26, GOLD, "midright")
        screen.blit(art.misc("coin_ui"), (240, 556))
        T(screen, "Gold earned", (275, 570), 28, CREAM, "midleft")
        T(screen, "+%d" % r["gold"], (660, 570), 34, GOLD, "midright")
        if r["bonus"]:
            T(screen, "(includes %d boss bonus)" % r["bonus"], (660, 606), 16, art.PARCHMENT_DK, "midright")
        T(screen, "Total gold: %d" % self.save["gold"], (450, 640), 22, art.PARCHMENT)
        for i, name in enumerate(r["unlocked"]):
            T(screen, "NEW REALM UNLOCKED: %s" % name, (450, 668 + i * 20), 17, art.EMERALD)
        self.button((280, 700, 340, 70), "RETURN TO CAMP", 28)

    # ------------------------------------------------------------------ loop
    def loop(self):
        while True:
            self.frame += 1
            self.mouse = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                self.handle(event)
            self.draw()
            pygame.display.flip()
            clock.tick(FPS)


SHADOW_C = art.SHADOW


def show_db_error(msg):
    print("\n[Project Strikers] " + msg + "\n")
    try:
        scr = pygame.display.set_mode((900, 900))
        font = pygame.font.SysFont("arial", 22, bold=True)
        lines = ["DATABASE NOT AVAILABLE", ""] + msg.split("\n") + ["", "Press any key to close."]
        scr.fill((24, 16, 30))
        y = 280
        for ln in lines:
            for i in range(0, max(1, len(ln)), 60):
                img = font.render(ln[i:i + 60], True, (240, 220, 180))
                scr.blit(img, (450 - img.get_width() // 2, y))
                y += 30
        pygame.display.flip()
        while True:
            ev = pygame.event.wait()
            if ev.type in (pygame.QUIT, pygame.KEYDOWN):
                break
    except Exception:
        pass


if __name__ == "__main__":
    try:
        app = App()
    except DatabaseError as e:
        show_db_error(str(e))
        pygame.quit()
        sys.exit(1)
    app.loop()
    pygame.quit()
    sys.exit()
