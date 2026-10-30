"""
Project Strikers - static game data.

Game data (Game balance, perks, skills, enemies, map)
"""

# ----------------------------------------------------------------------------
# Rarity / leveling 
# ----------------------------------------------------------------------------
RARITIES = ["common", "uncommon", "rare", "epic", "legendary"]
RARITY_LABEL = {r: r.capitalize() for r in RARITIES}

# Base rarity weights: interpolated from level 1 to RARITY_SCALE_LEVEL, then flat.
RARITY_EARLY_WEIGHTS = [80, 12, 5, 2, 1]      # 80% common, 1% legendary
RARITY_LATE_WEIGHTS = [15, 25, 25, 17, 18]    # ~18% legendary, commons drop hard
RARITY_SCALE_LEVEL = 30

CHOICES_PER_LEVEL = 4
PITY_HIGH_AFTER = 10        # 10 level-ups without an epic/legendary -> boosted odds
PITY_LEGENDARY_AFTER = 14   # 14 level-ups without a legendary -> the 15th guarantees one

MAX_WEAPONS = 3             # extra weapons a player can hold in one run
MAX_ACTIVES = 3             # active skills a player can hold in one run (keys 1, 2, 3)

SOFT_LEVEL = 30             # past this level every level costs far more XP


def exp_needed(level):
    """EXP required to go from `level` to `level + 1`."""
    base = 30 + 8 * level + 0.30 * level * level
    if level >= SOFT_LEVEL:
        base *= 1.9 * (1.12 ** (level - SOFT_LEVEL + 1))
    return int(base)


# ----------------------------------------------------------------------------
# Permanent skill tree (kept forever, bought with Gold)
#   cost of next rank = base + step * current_rank
#   req = (perk_code, min_rank) that must be owned first
#   tier = row in the tree (0 top .. 2 bottom); max 3 perks per row
# ----------------------------------------------------------------------------
PERK_BRANCHES = [
    {"id": "offense", "name": "Offense"},
    {"id": "defense", "name": "Defense"},
    {"id": "mobility", "name": "Mobility"},
    {"id": "meta", "name": "Synergy"},
]

PERKS = [
    # ---- Offense (Damage & Scale)
    dict(code="atk_speed", branch="offense", tier=0, name="Fire Rate", max=10, base=40, step=30, req=None,
         desc="+5% attack speed per rank."),
    dict(code="crit", branch="offense", tier=0, name="Critical Eye", max=10, base=50, step=35, req=None,
         desc="+2% crit chance and +5% crit damage per rank."),
    dict(code="might", branch="offense", tier=0, name="Might", max=10, base=45, step=30, req=None,
         desc="+3% attack per rank. (new)"),
    dict(code="aoe", branch="offense", tier=1, name="Area of Effect", max=5, base=80, step=60, req=("atk_speed", 1),
         desc="+8% shot size and a small splash blast on impact."),
    dict(code="pen", branch="offense", tier=1, name="Armor Break", max=5, base=70, step=50, req=("crit", 1),
         desc="Ignore 6% enemy armor and add knockback per rank."),
    dict(code="big_hits", branch="offense", tier=1, name="Big Hits", max=1, base=250, step=0, req=("might", 1),
         desc="+20% projectile size. Also enlarges swords, axes, orbiting orbs and the burning aura."),
    dict(code="multishot", branch="offense", tier=2, name="Projectile Multiplier", max=2, base=600, step=700, req=("aoe", 2),
         desc="+1 projectile on your attacks per rank."),
    dict(code="boss_slayer", branch="offense", tier=2, name="Boss Slayer", max=5, base=150, step=110, req=("pen", 2),
         desc="+5% damage to elites, mini-bosses and bosses per rank. (new)"),
    # ---- Defense & Survival
    dict(code="max_hp", branch="defense", tier=0, name="Vigor", max=10, base=40, step=30, req=None,
         desc="+10 max HP per rank."),
    dict(code="armor", branch="defense", tier=0, name="Armor", max=10, base=50, step=35, req=None,
         desc="+4 defense per rank (reduces incoming damage)."),
    dict(code="regen", branch="defense", tier=1, name="HP Regeneration", max=5, base=90, step=70, req=("max_hp", 1),
         desc="Heal +0.5 HP per second per rank."),
    dict(code="dodge", branch="defense", tier=1, name="Evasion", max=5, base=100, step=90, req=("armor", 1),
         desc="+2% chance to ignore a hit completely."),
    dict(code="bloodthirst", branch="defense", tier=1, name="Bloodthirst", max=5, base=110, step=90, req=("max_hp", 2),
         desc="Heal 0.4% of the damage you deal per rank (sustain is capped). (new)"),
    dict(code="thorns", branch="defense", tier=2, name="Reactive Blast", max=5, base=100, step=80, req=("dodge", 1),
         desc="Getting hit emits a shockwave that damages and shoves foes."),
    dict(code="last_stand", branch="defense", tier=2, name="Last Stand", max=3, base=220, step=200, req=("armor", 3),
         desc="Below 35% HP, take 7% less damage per rank. (new)"),
    # ---- Mobility & Utility
    dict(code="move_speed", branch="mobility", tier=0, name="Fleet Foot", max=5, base=60, step=50, req=None,
         desc="+3% movement speed per rank."),
    dict(code="magnet", branch="mobility", tier=0, name="Magnet", max=5, base=40, step=30, req=None,
         desc="+20% pickup radius for XP gems and gold."),
    dict(code="dash", branch="mobility", tier=1, name="Dash", max=3, base=150, step=200, req=("move_speed", 1),
         desc="Rank 1 unlocks Dash (SPACE, brief invulnerability). Later ranks cut its cooldown."),
    dict(code="yield", branch="mobility", tier=1, name="Plunder & Wisdom", max=5, base=120, step=90, req=("magnet", 1),
         desc="+5% gold and XP gained per rank."),
    dict(code="luck", branch="mobility", tier=2, name="Luck", max=5, base=200, step=150, req=("yield", 1),
         desc="Rare+ skills appear more often; drops are more frequent."),
    dict(code="arcane", branch="mobility", tier=2, name="Arcane Focus", max=5, base=180, step=140, req=("yield", 2),
         desc="Active skills recharge 5% faster per rank. (new)"),
    # ---- Synergy & Meta
    dict(code="reroll", branch="meta", tier=0, name="Rerolls", max=3, base=150, step=200, req=None,
         desc="+1 level-up reroll per run per rank."),
    dict(code="ban", branch="meta", tier=0, name="Bans", max=3, base=150, step=200, req=None,
         desc="+1 ban per run per rank: remove a skill from the pool for the run."),
    dict(code="veteran", branch="meta", tier=0, name="Veteran", max=2, base=300, step=500, req=None,
         desc="Start each run 1 level higher per rank, with a free skill pick. (new)"),
    dict(code="head_start", branch="meta", tier=1, name="Head Start", max=3, base=120, step=120, req=("reroll", 1),
         desc="Begin each run with a random Common skill per rank. (custom perk)"),
    dict(code="bounty", branch="meta", tier=1, name="Bounty Hunter", max=5, base=100, step=80, req=("ban", 1),
         desc="+10% gold from elites, mini-bosses and bosses per rank. (custom perk)"),
    dict(code="revive", branch="meta", tier=2, name="Second Chance", max=2, base=800, step=1200, req=("head_start", 1),
         desc="Once per run, revive at 50% HP (rank 2: 75% HP)."),
    dict(code="synergy", branch="meta", tier=2, name="Synergy Mastery", max=1, base=900, step=0, req=("bounty", 1),
         desc="Pairs of run skills unlock special fusion traits."),
    dict(code="fate", branch="meta", tier=2, name="Fate's Favor", max=3, base=350, step=300, req=("head_start", 2),
         desc="Pity timers trigger 1 level sooner per rank. (new)"),
]
PERK_BY_CODE = {p["code"]: p for p in PERKS}


def perk_cost(code, rank):
    p = PERK_BY_CODE[code]
    return p["base"] + p["step"] * rank


# ----------------------------------------------------------------------------
# Temporary run skills 
#   slot="weapon": counts toward MAX_WEAPONS      slot="active": MAX_ACTIVES (hotkeys 1-3)
#   needs="active": only offered once you own a castable active skill
# ----------------------------------------------------------------------------
def _s(id, name, desc, rarity, mx=1, kind="Offense", custom=False, slot=None, needs=None):
    return dict(id=id, name=name, desc=desc, rarity=rarity, max=mx, kind=kind, custom=custom, slot=slot, needs=needs)


SKILLS = [
    # Offensive
    _s("extra_barrel", "Extra Barrel", "+1 projectile on your attacks, weapons and projectile skills (+1 sword, +1 orbital orb, +1 sentry shot). Does not affect auras.", "uncommon", 3),
    _s("chain_lightning", "Chain Lightning", "Hits have a 25% chance to arc to 3 nearby enemies.", "common", 3),
    _s("executioner", "Executioner", "+50% damage to enemies below 30% HP.", "uncommon"),
    _s("splinter", "Splinter Shot", "Projectiles shatter into 3 shards on impact.", "uncommon"),
    _s("burn_aura", "Burn Aura", "Ignites enemies in a short radius, dealing damage over time.", "rare", 3),
    _s("giant_slayer", "Giant Slayer", "Bonus damage based on the target's max health.", "epic"),
    _s("berserker", "Berserker's Blood", "+1% attack speed and +0.5% life steal for every 2% of max HP missing.", "epic"),
    _s("glass_cannon", "Glass Cannon", "+50% damage dealt, but +25% damage taken.", "legendary", 1, "Capstone"),
    # Defensive & survival
    _s("shatter_shield", "Shatter Shield", "Absorbs 1 hit every 15s and blasts nearby enemies when broken.", "common", 1, "Defense"),
    _s("vampiric", "Vampiric Touch", "Restore 1% HP whenever you defeat an enemy.", "uncommon", 3, "Defense"),
    _s("second_wind", "Second Wind", "Below 20% HP, gain a burst of speed and armor.", "rare", 1, "Defense"),
    _s("vitality", "Vitality", "+10% max HP.", "common", 10, "Defense"),
    _s("strength", "Strength", "+10% attack.", "common", 10, "Offense"),
    _s("crit_rate", "Critical Rate", "+5% crit rate.", "common", 8, "Offense"),
    _s("crit_dmg", "Critical Damage", "+10% crit damage.", "common", 8, "Offense"),
    _s("fast_hands", "Fast Hands", "+15% attack speed.", "common", 6, "Offense"),
    _s("hardened", "Hardened", "+10% damage reduction.", "common", 5, "Defense"),
    _s("fortress", "Fortress", "+20% armor, but -5% movement speed.", "common", 2, "Defense"),
    _s("repulsion", "Repulsion Wave", "Every 10s, push back all nearby enemies.", "rare", 1, "Defense"),
    _s("desperate_surge", "Desperate Surge", "Below 15% HP, instantly unleash a screen-clearing pulse (once every 60s).",
       "legendary", 1, "Capstone"),
    # Utility & economy
    _s("xp_magnet", "XP Magnet", "Every 30s, pull every XP gem on the map to you.", "rare", 1, "Utility"),
    _s("scholar", "Scholar", "+20% XP gain for the rest of the current run.", "uncommon", 3, "Utility"),
    _s("scavenger", "Scavenger", "Enemies have a higher chance to drop healing food or gold.", "uncommon", 3, "Utility"),
    _s("greed", "Greed", "+30% gold this run, but enemies have +10% HP.", "rare", 1, "Utility"),
    _s("adrenaline", "Adrenaline", "+2% move speed for 5s after each kill (stacks to 10).", "rare", 1, "Utility"),
    _s("blood_magic", "Blood Magic", "Casting an active skill costs 15% of your max HP (never kills you: you are left at 1 HP) but doubles your attack for 10s.",
       "rare", 1, "Utility", needs="active"),
    # Weapons (Max 3 per run)
    _s("bow", "Bow", "Adds a Bow: piercing arrows that deal 100% of your attack.", "common", 1, "Weapon", slot="weapon"),
    _s("axe", "Axe", "Hurls axes skyward; they crash back down through the screen dealing 150% of your attack to every enemy hit.",
       "uncommon", 1, "Weapon", slot="weapon"),
    _s("acid_potion", "Acid Potion", "Hurls a potion that leaves an acid pool dealing 10% of your attack over and over.",
       "rare", 1, "Weapon", slot="weapon"),
    _s("spinning_swords", "Spinning Swords", "4 swords orbit you, each hit dealing 120% of your attack.",
       "rare", 1, "Weapon", slot="weapon"),
    _s("gunner", "Gunner", "Adds a Gun: fires 3x as fast as your basic attack for 33% of your attack. Attack speed applies.",
       "epic", 1, "Weapon", slot="weapon"),
    # Active skills (Max 3 per run)
    _s("healing_spring", "Healing Spring", "Active: a spring heals you 5% max HP per second for 10s. 20s cooldown.",
       "rare", 1, "Active", slot="active"),
    _s("blizzard", "Blizzard", "Active: a blizzard follows you for 5s, slowing enemies and dealing 5% of your attack every 0.5s. 20s cooldown.",
       "rare", 1, "Active", slot="active"),
    _s("meteor_shower", "Meteor Shower", "Active: a meteor crashes down for 300% of your attack in a gigantic area. 25s cooldown.",
       "epic", 1, "Active", slot="active"),
    # Epic Tier
    _s("titan", "Titan's Might", "+25% attack and +15% max HP.", "epic", 2, "Offense", True),
    _s("gale", "Gale Force", "+20% attack speed and +10% movement speed.", "epic", 2, "Offense", True),
    # Legendary Tier
    _s("overclock", "Overclock", "Doubles attack speed for 10s whenever you use an active ability.", "legendary", 1, "Capstone"),
    _s("explosive_finale", "Explosive Finale", "Enemies explode on death, dealing 30% of their Max HP to nearby targets.", "legendary", 1, "Capstone"),
    _s("orbital_barrage", "Orbital Barrage", "Summons floating projectiles that continually circle your character.", "legendary", 1, "Capstone"),
    _s("time_freeze", "Time Freeze", "Active: on lethal damage, survive and freeze all enemies for 3s. 3 minute cooldown. Triggers by itself.",
       "legendary", 1, "Capstone", slot="active"),
    _s("sentry", "Sentry", "A sentry fights beside you with 100% of your attack, crit and attack speed, and fires a long-range laser for 200% of your attack every 5s.", "legendary", 1, "Capstone"),
]
SKILL_BY_ID = {s["id"]: s for s in SKILLS}
AUTO_ACTIVES = {"time_freeze"}          # occupy an active slot but need no key press

# Active skill cooldowns (seconds)
ACTIVE_COOLDOWN = {"meteor_shower": 25, "healing_spring": 20, "blizzard": 20}

# Synergy Mastery fusions: (skill_a, skill_b, name, description)
FUSIONS = [
    ("extra_barrel", "splinter", "Shrapnel Storm", "Splinter Shot bursts into 5 shards."),
    ("chain_lightning", "burn_aura", "Storm Aura", "Burn Aura pulses lightning at nearby enemies."),
    ("explosive_finale", "executioner", "Reaper's Blast", "Death explosions deal 45% of max HP."),
]

# ----------------------------------------------------------------------------
# Enemies
#   plural   -> used for the "<Name> Appear!" announcement the first time they show up
#   elite    -> tougher mob 
#   mini     -> mini-boss (rewards a skill pick)       boss -> end-of-run boss
#   front_armor: fraction of damage ignored when hit from the front
# ----------------------------------------------------------------------------
BASE_PLAYER_SPEED = 4.4


def _e(name, plural, ai, cost, hp, speed, dmg, r, exp, gold, sprite, **kw):
    d = dict(name=name, plural=plural, ai=ai, cost=cost, hp=hp, speed=speed, dmg=dmg, r=r, exp=exp, gold=gold, sprite=sprite)
    d.update(kw)
    return d


ENEMIES = {
    # ---- Forest: swarm & fodder
    "swarmer": _e("Swarmer Beetle", "Swarmer Beetles", "straight", 1, 14, 2.7, 6, 12, 2, 1, "swarmer"),
    "slime": _e("Splitting Slime", "Splitting Slimes", "chase", 2, 34, 1.5, 8, 14, 4, 1, "slime"),
    "slimelet": _e("Slimelet", None, "chase", 1, 12, 2.5, 5, 9, 1, 1, "slime", small=True),
    "crawler": _e("Explosive Crawler", "Explosive Crawlers", "crawler", 3, 24, 3.3, 18, 12, 5, 2, "crawler"),
    # ---- Forest: area denial & ranged
    "mortar": _e("Spit Mortar", "Spit Mortars", "mortar", 5, 60, 0.9, 14, 17, 10, 3, "mortar", ranged=True),
    "sniper": _e("Sniper Firefly", "Sniper Fireflies", "sniper", 6, 42, 1.3, 28, 13, 11, 3, "sniper", ranged=True),
    "spinner": _e("Bullet Spinner", "Bullet Spinners", "spinner", 6, 100, 0.0, 7, 17, 12, 4, "spinner", ranged=True, nocontact=True),
    # ---- Forest: chasers & disruptors
    "bearer": _e("Shield Bearer", "Shield Bearers", "chase", 8, 130, 1.35, 12, 19, 15, 4, "bearer", armor=0.10, shield=True),
    "vortex": _e("Vortex Orb", "Vortex Orbs", "vortex", 8, 160, 0.8, 9, 18, 16, 5, "vortex"),
    "bull": _e("Charger Bull", "Charger Bulls", "bull", 6, 110, 1.2, 14, 20, 13, 4, "bull"),
    # ---- Forest: elites (suppression aura on the Necromancer)
    "necromancer": _e("Necromancer", "Necromancers", "necro", 25, 750, 1.1, 12, 22, 70, 40, "necromancer", armor=0.10, elite=True, suppress=170),
    "wall_summoner": _e("Wall Summoner", "Wall Summoners", "wallsum", 25, 700, 1.0, 12, 24, 70, 40, "wall_summoner", armor=0.10, elite=True),
    "commander": _e("Commander Beetle", "Commander Beetles", "commander", 25, 900, 1.3, 18, 26, 70, 40, "commander", armor=0.15, elite=True),

    # ---- Wasteland: normal & swarm
    "scrapswarmer": _e("Scrapswarmer", "Scrapswarmers", "straight", 1, 22, 3.0, 7, 14, 2, 1, "scrapswarmer", armor=0.12),
    "hornet": _e("Rad-Hornet", "Rad-Hornets", "hornet", 4, 36, 2.6, 8, 14, 8, 2, "rad_hornet", ranged=True),
    "dust_crawler": _e("Dust Crawler", "Dust Crawlers", "burrow", 4, 50, 2.6, 15, 15, 8, 2, "dust_crawler"),
    # ---- Wasteland: elites
    "slag_thrower": _e("Slag Thrower", "Slag Throwers", "slag", 25, 850, 1.0, 16, 24, 80, 45, "slag_thrower", armor=0.10, elite=True, ranged=True),
    "harvester": _e("Mutated Harvester", "Mutated Harvesters", "harvester", 25, 800, 1.1, 14, 26, 80, 45, "harvester", armor=0.10, elite=True),
    "stalker": _e("Toxic Stalker", "Toxic Stalkers", "stalker", 25, 900, 1.4, 14, 24, 80, 45, "toxic_stalker", armor=0.05, elite=True),

    # ---- Dark Castle: normal & swarm
    "cursed_armor": _e("Cursed Armor", "Cursed Armors", "armor", 5, 120, 0.85, 14, 21, 9, 3, "cursed_armor", front_armor=0.70),
    "gargoyle": _e("Gargoyle", "Gargoyle Swarms", "gargoyle", 3, 40, 2.4, 16, 15, 6, 2, "gargoyle"),
    "bat": _e("Blood Bat", "Blood Bats", "bat", 1, 12, 3.3, 5, 11, 2, 1, "blood_bat", drain=True),
    # ---- Dark Castle: elites
    "executioner": _e("Spectral Executioner", "Spectral Executioners", "executioner", 25, 950, 1.5, 20, 24, 85, 45, "executioner", armor=0.05, elite=True),
    "templar": _e("Vampiric Templar", "Vampiric Templars", "templar", 25, 900, 1.1, 14, 25, 85, 45, "templar", armor=0.10, elite=True),
    "lich": _e("Necromantic Lich", "Necromantic Liches", "lich", 25, 800, 1.0, 12, 23, 85, 45, "lich", armor=0.05, elite=True, ranged=True),

    # ---- Mini-bosses (hp is the BASE; scaled by map difficulty and run time)
    "treant": _e("The Hollowed Treant", None, "treant", 0, 7500, 0.9, 16, 44, 160, 80, "treant", mini=True, fixed_hp=True, armor=0.05),
    "hydra": _e("Bramble Hydra", None, "hydra", 0, 7000, 1.1, 14, 40, 160, 80, "hydra", mini=True, fixed_hp=True, armor=0.05),
    "sylphid": _e("Sylphid, the Pollen Queen", None, "sylphid", 0, 6500, 1.8, 10, 32, 160, 80, "sylphid", mini=True, fixed_hp=True),
    "barkspine": _e("Barkspine the Corrupted Treant", None, "barkspine", 0, 8000, 0.5, 16, 44, 160, 80, "barkspine", mini=True, fixed_hp=True, armor=0.10),
    "dreadnought": _e("Scraptooth Dreadnought", None, "dreadnought", 0, 7500, 1.0, 22, 44, 200, 110, "dreadnought", mini=True, fixed_hp=True, armor=0.12),
    "gorgon": _e("Rad-Gorgon", None, "gorgon", 0, 7500, 1.1, 16, 42, 200, 110, "gorgon", mini=True, fixed_hp=True, armor=0.05),
    "bgargoyle": _e("The Blood-Bound Gargoyle", None, "bgargoyle", 0, 6500, 1.5, 20, 44, 260, 140, "bgargoyle", mini=True, fixed_hp=True, armor=0.08),
    "inquisitor": _e("Cursed High Inquisitor", None, "inquisitor", 0, 6500, 1.4, 14, 32, 260, 140, "inquisitor", mini=True, fixed_hp=True),

    # ---- End-of-run bosses
    "hive_monarch": _e("The Hive Monarch", None, "boss", 0, 45000, 1.3, 20, 56, 0, 0, "boss", boss=True, fixed_hp=True, armor=0.12),
    "construct_zero": _e("Construct Zero", None, "construct", 0, 42000, 0.6, 24, 70, 0, 0, "construct", boss=True, fixed_hp=True, armor=0.15),
    "vespera": _e("The Phantom Monarch, Vespera", None, "vespera", 0, 36000, 3.0, 18, 36, 0, 0, "vespera", boss=True, fixed_hp=True, armor=0.05),
    "vespera_clone": _e("Phantom Clone", None, "vclone", 0, 520, 3.0, 12, 30, 0, 0, "vespera", fixed_hp=True, quiet=True),

    # ---- Boss encounter helpers
    "pod": _e("Hive Pod", None, "pod", 0, 220, 0, 0, 22, 8, 0, "pod", nocontact=True, fixed_hp=True),
    "guard": _e("Hatch Guard", None, "guard", 0, 170, 0, 12, 19, 0, 0, "bearer", armor=0.10, shield=True, fixed_hp=True),
}

# Enemy type announced when first spawned
# ----------------------------------------------------------------------------
# Maps 
#   requires:     map id whose boss must be beaten before this one unlocks
#   diff:         difficulty multiplier for this map's mini-bosses and boss scales with level
#   threat_curve: (seconds, threat cap) points, linearly interpolated
#   phases:       wave phases; `types` are trickle weights, `forms` are formation weights
#   minis:        pool of mini-bosses - TWO different ones are picked each run
# ----------------------------------------------------------------------------
RUN_SECONDS = 20 * 60
MINI_FIRST_AT = 5 * 60          # first mini-boss; the next one comes 5:00 after it is defeated
MINI_GAP = 5 * 60

MAPS = [
    dict(
        id=1, order=1, name="Mossveil Glade", theme="glade", requires=None, diff=1.0,
        blurb="A sun-dappled clearing where the Hive Monarch's brood swarms from the treeline.",
        duration=RUN_SECONDS, boss="hive_monarch", is_final_boss=0,
        swarm_kind="swarmer", ambush_kind="crawler", phalanx_kind=None,
        elite_kinds=["necromancer", "wall_summoner", "commander"],
        minis=["treant", "hydra", "sylphid", "barkspine"],
        threat_curve=[(0, 8), (180, 34), (420, 70), (720, 112), (1020, 148), (1200, 180)],
        phases=[
            dict(start=0, elites=False, types={"swarmer": 1}, forms={"trickle": 6, "swarm": 2}),
            dict(start=180, elites=False,
                 types={"swarmer": 6, "slime": 3, "crawler": 3, "bull": 2, "mortar": 2, "sniper": 1},
                 forms={"trickle": 6, "swarm": 2, "ambush": 1.2}),
            dict(start=420, elites=True,
                 types={"swarmer": 6, "slime": 3, "crawler": 2, "bull": 1, "mortar": 1, "sniper": 1,
                        "bearer": 3, "vortex": 1.5, "spinner": 1.2},
                 forms={"trickle": 5, "swarm": 2.5, "ring": 1.5, "wall": 1.2, "ambush": 1}),
            dict(start=720, elites=True,
                 types={"swarmer": 5, "slime": 3, "crawler": 3, "bull": 2, "mortar": 2, "sniper": 2,
                        "bearer": 3, "vortex": 2, "spinner": 2},
                 forms={"trickle": 4, "swarm": 2.5, "ring": 2, "wall": 1.6, "ambush": 1.5}),
            dict(start=1020, elites=True,
                 types={"swarmer": 4, "slime": 3, "crawler": 3, "bull": 3, "mortar": 3, "sniper": 2,
                        "bearer": 4, "vortex": 2.5, "spinner": 2.5},
                 forms={"trickle": 3, "swarm": 2.5, "ring": 2.2, "wall": 2, "ambush": 1.8}),
        ],
    ),
    dict(
        id=2, order=2, name="Ashen Wastelands", theme="wasteland", requires=1, diff=1.25,
        blurb="A poisoned desert of rusted wrecks. Radiation twists everything that still crawls here.",
        duration=RUN_SECONDS, boss="construct_zero", is_final_boss=0,
        swarm_kind="scrapswarmer", ambush_kind="dust_crawler", phalanx_kind=None,
        elite_kinds=["slag_thrower", "harvester", "stalker"],
        minis=["dreadnought", "gorgon"],
        threat_curve=[(0, 9), (180, 38), (420, 76), (720, 120), (1020, 158), (1200, 190)],
        phases=[
            dict(start=0, elites=False, types={"scrapswarmer": 1}, forms={"trickle": 6, "swarm": 2}),
            dict(start=150, elites=False,
                 types={"scrapswarmer": 6, "hornet": 2.5, "dust_crawler": 2.5},
                 forms={"trickle": 6, "swarm": 2, "ambush": 1.4}),
            dict(start=400, elites=True,
                 types={"scrapswarmer": 6, "hornet": 3, "dust_crawler": 3},
                 forms={"trickle": 5, "swarm": 2.5, "ring": 1.5, "wall": 1.3, "ambush": 1.4}),
            dict(start=700, elites=True,
                 types={"scrapswarmer": 5, "hornet": 3.5, "dust_crawler": 3.5},
                 forms={"trickle": 4, "swarm": 2.5, "ring": 2, "wall": 1.8, "ambush": 1.8}),
            dict(start=1000, elites=True,
                 types={"scrapswarmer": 4, "hornet": 4, "dust_crawler": 4},
                 forms={"trickle": 3, "swarm": 2.5, "ring": 2.2, "wall": 2, "ambush": 2.2}),
        ],
    ),
    dict(
        id=3, order=3, name="Gloomspire Castle", theme="castle", requires=1, diff=1.5,
        blurb="A cursed fortress under a bleeding moon. Its hollow knights still guard the throne.",
        duration=RUN_SECONDS, boss="vespera", is_final_boss=1,
        swarm_kind="bat", ambush_kind="gargoyle", phalanx_kind="cursed_armor",
        elite_kinds=["executioner", "templar", "lich"],
        minis=["bgargoyle", "inquisitor"],
        threat_curve=[(0, 9), (180, 38), (420, 78), (720, 124), (1020, 162), (1200, 195)],
        phases=[
            dict(start=0, elites=False, types={"bat": 1}, forms={"trickle": 6, "swarm": 2}),
            dict(start=150, elites=False,
                 types={"bat": 6, "gargoyle": 3.5, "cursed_armor": 2},
                 forms={"trickle": 6, "swarm": 2, "ambush": 1.4, "phalanx": 1}),
            dict(start=400, elites=True,
                 types={"bat": 6, "gargoyle": 3.5, "cursed_armor": 3},
                 forms={"trickle": 5, "swarm": 2.5, "ring": 1.4, "wall": 1.2, "ambush": 1.4, "phalanx": 1.4}),
            dict(start=700, elites=True,
                 types={"bat": 5, "gargoyle": 4, "cursed_armor": 3.5},
                 forms={"trickle": 4, "swarm": 2.5, "ring": 2, "wall": 1.8, "ambush": 1.8, "phalanx": 1.8}),
            dict(start=1000, elites=True,
                 types={"bat": 4, "gargoyle": 4.5, "cursed_armor": 4},
                 forms={"trickle": 3, "swarm": 2.5, "ring": 2.2, "wall": 2, "ambush": 2.2, "phalanx": 2.2}),
        ],
    ),
]
MAP_BY_ID = {m["id"]: m for m in MAPS}
