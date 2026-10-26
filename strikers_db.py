"""
Project Strikers - MySQL / MariaDB persistence (XAMPP).


"""
import hashlib
import hmac
import os
import re
import secrets

try:
    import mysql.connector as mysql
    from mysql.connector import errors as mysql_errors
except ImportError:                                   # handled with a friendly message in Database()
    mysql = None
    mysql_errors = None

import strikers_data as data

# XAMPP defaults. Override with environment variables if yours differ.
DB_CONFIG = {
    "host": os.environ.get("STRIKERS_DB_HOST", "127.0.0.1"),
    "port": int(os.environ.get("STRIKERS_DB_PORT", "3306")),
    "user": os.environ.get("STRIKERS_DB_USER", "root"),
    "password": os.environ.get("STRIKERS_DB_PASSWORD", ""),
}
DB_NAME = os.environ.get("STRIKERS_DB_NAME", "strikers")
SCHEMA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "strikers_schema.sql")


class DatabaseError(Exception):
    """Raised with a message that is safe to show the player."""


ACTIONS = ["up", "down", "left", "right"]
DEFAULT_KEYS = {"up": 119, "down": 115, "left": 97, "right": 100}   # W S A D (pygame key codes)

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,16}$")


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return salt.hex() + "$" + digest.hex()


def verify_password(password, stored):
    try:
        salt_hex, digest_hex = stored.split("$")
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return hmac.compare_digest(digest.hex(), digest_hex)


def _schema_statements():
    with open(SCHEMA_FILE, encoding="utf-8") as f:
        lines = [ln for ln in f if not ln.strip().startswith("--")]
    return [st.strip() for st in "".join(lines).split(";") if st.strip()]


class Database:
    def __init__(self):
        if mysql is None:
            raise DatabaseError("Missing package. Run:  pip install mysql-connector-python")
        try:
            self.conn = mysql.connect(connection_timeout=5, **DB_CONFIG)
        except Exception as e:
            raise DatabaseError("Cannot reach MySQL at %s:%s.\nOpen the XAMPP Control Panel and press Start next to MySQL.\n(%s)"
                                % (DB_CONFIG["host"], DB_CONFIG["port"], e))
        try:
            cur = self.conn.cursor()
            cur.execute("CREATE DATABASE IF NOT EXISTS `%s` CHARACTER SET utf8mb4" % DB_NAME)
            cur.execute("USE `%s`" % DB_NAME)
            for st in _schema_statements():
                u = st.upper()
                if u.startswith("CREATE DATABASE") or u.startswith("USE "):
                    continue
                cur.execute(st)
            self.conn.commit()
            cur.close()
            self._seed()
        except Exception as e:
            raise DatabaseError("Database setup failed: %s" % e)

    # -- small helpers -----------------------------------------------------
    def _x(self, sql, params=()):
        """Execute and return the cursor (dict rows). Caller commits."""
        cur = self.conn.cursor(dictionary=True)
        cur.execute(sql, params)
        return cur

    def _rows(self, sql, params=()):
        cur = self._x(sql, params)
        rows = cur.fetchall()
        cur.close()
        return rows

    def _one(self, sql, params=()):
        rows = self._rows(sql, params)
        return rows[0] if rows else None

    def _txn(self, fn):
        try:
            res = fn()
            self.conn.commit()
            return res
        except Exception:
            self.conn.rollback()
            raise

    # -- reference data ----------------------------------------------------
    def _seed(self):
        def go():
            for m in data.MAPS:
                self._x("INSERT INTO maps (map_id, name, map_order, duration_seconds, is_final_boss) VALUES (%s,%s,%s,%s,%s) "
                        "ON DUPLICATE KEY UPDATE name=VALUES(name), duration_seconds=VALUES(duration_seconds), is_final_boss=VALUES(is_final_boss)",
                        (m["id"], m["name"], m["order"], m["duration"], int(bool(m["is_final_boss"])))).close()
            for p in data.PERKS:
                unique = 1 if p["max"] == 1 else 0
                self._x("INSERT INTO upgrades (code, name, description, is_unique) VALUES (%s,%s,%s,%s) "
                        "ON DUPLICATE KEY UPDATE name=VALUES(name), description=VALUES(description), is_unique=VALUES(is_unique)",
                        (p["code"], p["name"], p["desc"], unique)).close()
            for kind, e in data.ENEMIES.items():
                pct = int(round(e["speed"] / data.BASE_PLAYER_SPEED * 100))
                self._x("INSERT IGNORE INTO enemy_types (name, max_hp, damage, speed_pct, exp_reward) VALUES (%s,%s,%s,%s,%s)",
                        (e["name"], e["hp"], e["dmg"], pct, e["exp"])).close()
        self._txn(go)
        self.upgrade_ids = {r["code"]: r["upgrade_id"] for r in self._rows("SELECT upgrade_id, code FROM upgrades")}
        names = {r["name"]: r["enemy_type_id"] for r in self._rows("SELECT enemy_type_id, name FROM enemy_types")}
        self.enemy_ids = {k: names[e["name"]] for k, e in data.ENEMIES.items() if e["name"] in names}

    # -- accounts ----------------------------------------------------------
    def create_account(self, username, password):
        """Returns (account_id or None, message)."""
        if not USERNAME_RE.match(username):
            return None, "Name must be 3-16 letters, numbers or _."
        if len(password) < 4:
            return None, "Password must be at least 4 characters."
        if self._one("SELECT account_id FROM accounts WHERE username=%s", (username,)):
            return None, "That name is already taken."

        def go():
            cur = self._x("INSERT INTO accounts (username, password_hash, last_login) VALUES (%s,%s,NOW())",
                          (username, hash_password(password)))
            aid = cur.lastrowid
            cur.close()
            for action, code in DEFAULT_KEYS.items():
                self._x("INSERT INTO keybindings (account_id, action, key_code) VALUES (%s,%s,%s)", (aid, action, code)).close()
            self._x("INSERT INTO saves (account_id, current_map_id, slot_number) VALUES (%s,%s,1)",
                    (aid, data.MAPS[0]["id"])).close()
            return aid
        try:
            return self._txn(go), "Account created."
        except mysql_errors.IntegrityError:
            return None, "That name is already taken."

    def login(self, username, password):
        """Returns (account_id or None, message)."""
        row = self._one("SELECT account_id, password_hash FROM accounts WHERE username=%s", (username,))
        if row is None or not verify_password(password, row["password_hash"]):
            return None, "Wrong name or password."
        self._txn(lambda: self._x("UPDATE accounts SET last_login=NOW() WHERE account_id=%s", (row["account_id"],)).close())
        return row["account_id"], "Welcome back."

    def username(self, account_id):
        return self._one("SELECT username FROM accounts WHERE account_id=%s", (account_id,))["username"]

    # -- keybinds ----------------------------------------------------------
    def load_keybinds(self, account_id):
        keys = dict(DEFAULT_KEYS)
        for r in self._rows("SELECT action, key_code FROM keybindings WHERE account_id=%s", (account_id,)):
            keys[r["action"]] = r["key_code"]
        return keys

    def save_keybinds(self, account_id, keys):
        def go():
            for action in ACTIONS:
                self._x("INSERT INTO keybindings (account_id, action, key_code) VALUES (%s,%s,%s) "
                        "ON DUPLICATE KEY UPDATE key_code=VALUES(key_code)",
                        (account_id, action, keys[action])).close()
        self._txn(go)

    # -- saves / perks / gold ---------------------------------------------
    def get_save(self, account_id):
        row = self._one("SELECT * FROM saves WHERE account_id=%s AND slot_number=1", (account_id,))
        if row is None:
            self._txn(lambda: self._x("INSERT INTO saves (account_id, current_map_id, slot_number) VALUES (%s,%s,1)",
                                      (account_id, data.MAPS[0]["id"])).close())
            row = self._one("SELECT * FROM saves WHERE account_id=%s AND slot_number=1", (account_id,))
        return row

    def get_perks(self, save_id):
        q = ("SELECT u.code, su.times_taken FROM save_upgrades su JOIN upgrades u ON u.upgrade_id = su.upgrade_id "
             "WHERE su.save_id=%s")
        return {r["code"]: r["times_taken"] for r in self._rows(q, (save_id,))}

    def buy_perk(self, save_id, code):
        """Returns (ok, message)."""
        p = data.PERK_BY_CODE[code]
        perks = self.get_perks(save_id)
        rank = perks.get(code, 0)
        if rank >= p["max"]:
            return False, "Already at max rank."
        if p["req"]:
            rc, rr = p["req"]
            if perks.get(rc, 0) < rr:
                return False, "Requires %s rank %d." % (data.PERK_BY_CODE[rc]["name"], rr)
        cost = data.perk_cost(code, rank)
        gold = self._one("SELECT gold FROM saves WHERE save_id=%s", (save_id,))["gold"]
        if gold < cost:
            return False, "Not enough gold."
        uid = self.upgrade_ids[code]

        def go():
            self._x("UPDATE saves SET gold=gold-%s, updated_at=NOW() WHERE save_id=%s", (cost, save_id)).close()
            self._x("INSERT INTO save_upgrades (save_id, upgrade_id, times_taken) VALUES (%s,%s,1) "
                    "ON DUPLICATE KEY UPDATE times_taken = times_taken + 1", (save_id, uid)).close()
        self._txn(go)
        return True, "%s upgraded!" % p["name"]

    # -- run history -------------------------------------------------------
    def record_run(self, save_id, map_id, result, level_reached, duration, kills, exp_gained, gold_gained):
        def go():
            cur = self._x("INSERT INTO runs (save_id, map_id, result, level_reached, duration_seconds) VALUES (%s,%s,%s,%s,%s)",
                          (save_id, map_id, result, int(level_reached), int(duration)))
            run_id = cur.lastrowid
            cur.close()
            for kind, n in kills.items():
                if n > 0 and kind in self.enemy_ids:
                    self._x("INSERT INTO run_kills (run_id, enemy_type_id, kills) VALUES (%s,%s,%s)",
                            (run_id, self.enemy_ids[kind], int(n))).close()
            self._x("UPDATE saves SET gold=gold+%s, exp=exp+%s, level=GREATEST(level, %s), current_map_id=%s, updated_at=NOW() "
                    "WHERE save_id=%s", (int(gold_gained), float(exp_gained), int(level_reached), map_id, save_id)).close()
            return run_id
        return self._txn(go)

    # -- map unlocks -------------------------------------------------------
    def victories(self, save_id):
        """Ids of the maps whose final boss this save has defeated."""
        return {r["map_id"] for r in self._rows(
            "SELECT DISTINCT map_id FROM runs WHERE save_id=%s AND result='victory'", (save_id,))}

    def map_unlocked(self, save_id, map_def):
        req = map_def.get("requires")
        return req is None or req in self.victories(save_id)
