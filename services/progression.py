"""SERVICE layer: skill-tree purchases, finished runs and map unlocks."""
from core import game_data as data


class ProgressionService:
    def __init__(self, repo):
        self.repo = repo
        self.upgrade_ids = {}       # perk code  -> upgrades.upgrade_id
        self.enemy_ids = {}         # enemy kind -> enemy_types.enemy_type_id

    # -- startup -----------------------------------------------------------
    def sync_reference_data(self):
        """Copy the static game data (maps, perks, enemies) into the database tables."""
        maps = [(m["id"], m["name"], m["order"], m["duration"], int(bool(m["is_final_boss"]))) for m in data.MAPS]
        perks = [(p["code"], p["name"], p["desc"], 1 if p["max"] == 1 else 0) for p in data.PERKS]
        enemies = [(e["name"], e["hp"], e["dmg"], int(round(e["speed"] / data.BASE_PLAYER_SPEED * 100)), e["exp"])
                   for e in data.ENEMIES.values()]
        self.repo.sync_reference_data(maps, perks, enemies)
        self.upgrade_ids = self.repo.upgrade_ids()
        names = self.repo.enemy_type_ids()
        self.enemy_ids = {k: names[e["name"]] for k, e in data.ENEMIES.items() if e["name"] in names}

    # -- skill tree --------------------------------------------------------
    def buy_perk(self, save_id, code):
        """Returns (ok, message)."""
        p = data.PERK_BY_CODE[code]
        perks = self.repo.get_perk_ranks(save_id)
        rank = perks.get(code, 0)
        if rank >= p["max"]:
            return False, "Already at max rank."
        if p["req"]:
            req_code, req_rank = p["req"]
            if perks.get(req_code, 0) < req_rank:
                return False, "Requires %s rank %d." % (data.PERK_BY_CODE[req_code]["name"], req_rank)
        cost = data.perk_cost(code, rank)
        if self.repo.get_gold(save_id) < cost:
            return False, "Not enough gold."
        self.repo.purchase_perk(save_id, self.upgrade_ids[code], cost)
        return True, "%s upgraded!" % p["name"]

    # -- finished runs -----------------------------------------------------
    def record_run(self, save_id, map_id, result, level_reached, duration, kills, exp_gained, gold_gained):
        kill_rows = [(self.enemy_ids[kind], n) for kind, n in kills.items() if n > 0 and kind in self.enemy_ids]
        return self.repo.record_run(save_id, map_id, result, level_reached, duration, kill_rows, exp_gained, gold_gained)

    # -- map unlocks -------------------------------------------------------
    def victories(self, save_id):
        """Ids of the maps whose final boss this save has defeated."""
        return self.repo.victory_map_ids(save_id)

    @staticmethod
    def is_unlocked(map_def, victories):
        req = map_def.get("requires")
        return req is None or req in victories

    @staticmethod
    def newly_unlocked(before, now):
        """Maps that became playable because of the victories gained since `before`."""
        return [m for m in data.MAPS
                if m["id"] not in before and m.get("requires") in now and m.get("requires") not in before]
