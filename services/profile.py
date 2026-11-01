"""SERVICE layer: a player's key bindings, save slot and owned perks."""
from core import game_data as data


class ProfileService:
    def __init__(self, repo):
        self.repo = repo

    def load_keybinds(self, account_id):
        keys = dict(data.DEFAULT_KEYS)
        keys.update(self.repo.get_keybinds(account_id))
        return keys

    def save_keybinds(self, account_id, keys):
        self.repo.save_keybinds(account_id, {action: keys[action] for action in data.ACTIONS})

    def get_save(self, account_id):
        """Slot 1 of this account; created on first use."""
        row = self.repo.get_save(account_id)
        if row is None:
            self.repo.create_save(account_id, data.MAPS[0]["id"])
            row = self.repo.get_save(account_id)
        return row

    def get_perks(self, save_id):
        return self.repo.get_perk_ranks(save_id)
