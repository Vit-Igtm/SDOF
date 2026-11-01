"""SERVICE layer: registration and login."""
import re

from core import game_data as data
from database import DuplicateAccountError
from services.security import hash_password, verify_password

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,16}$")
MIN_PASSWORD = 4


class AccountService:
    def __init__(self, repo):
        self.repo = repo

    def create_account(self, username, password):
        """Returns (account_id or None, message)."""
        if not USERNAME_RE.match(username):
            return None, "Name must be 3-16 letters, numbers or _."
        if len(password) < MIN_PASSWORD:
            return None, "Password must be at least 4 characters."
        if self.repo.find_account(username):
            return None, "That name is already taken."
        try:
            aid = self.repo.create_account(username, hash_password(password), data.DEFAULT_KEYS, data.MAPS[0]["id"])
        except DuplicateAccountError:
            return None, "That name is already taken."
        return aid, "Account created."

    def login(self, username, password):
        """Returns (account_id or None, message)."""
        row = self.repo.find_account(username)
        if row is None or not verify_password(password, row["password_hash"]):
            return None, "Wrong name or password."
        self.repo.touch_login(row["account_id"])
        return row["account_id"], "Welcome back."

    def username(self, account_id):
        return self.repo.username_of(account_id)
