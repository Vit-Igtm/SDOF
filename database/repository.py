"""
Project Strikers - DATABASE layer: the Repository pattern.

"""
import os

try:
    import mysql.connector as mysql
    from mysql.connector import errors as mysql_errors
except ImportError:                                  
    mysql = None
    mysql_errors = None

# XAMPP defaults. Override with environment variables if yours differ.
DB_CONFIG = {
    "host": os.environ.get("STRIKERS_DB_HOST", "127.0.0.1"),
    "port": int(os.environ.get("STRIKERS_DB_PORT", "3306")),
    "user": os.environ.get("STRIKERS_DB_USER", "root"),
    "password": os.environ.get("STRIKERS_DB_PASSWORD", ""),
}
DB_NAME = os.environ.get("STRIKERS_DB_NAME", "strikers")
SCHEMA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")


class DatabaseError(Exception):
    """Raised with a message that is safe to show the player."""


class DuplicateAccountError(Exception):
    """The username already exists."""


def _schema_statements():
    with open(SCHEMA_FILE, encoding="utf-8") as f:
        lines = [ln for ln in f if not ln.strip().startswith("--")]
    return [st.strip() for st in "".join(lines).split(";") if st.strip()]


class Repository:
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

    # -- reference data (maps, perks, enemy types) -------------------------
    def sync_reference_data(self, maps, perks, enemies):
        """Insert or refresh the static tables. Each argument is a list of tuples (see below)."""
        def go():
            for row in maps:       # (map_id, name, map_order, duration_seconds, is_final_boss)
                self._x("INSERT INTO maps (map_id, name, map_order, duration_seconds, is_final_boss) VALUES (%s,%s,%s,%s,%s) "
                        "ON DUPLICATE KEY UPDATE name=VALUES(name), duration_seconds=VALUES(duration_seconds), is_final_boss=VALUES(is_final_boss)",
                        row).close()
            for row in perks:      # (code, name, description, is_unique)
                self._x("INSERT INTO upgrades (code, name, description, is_unique) VALUES (%s,%s,%s,%s) "
                        "ON DUPLICATE KEY UPDATE name=VALUES(name), description=VALUES(description), is_unique=VALUES(is_unique)",
                        row).close()
            for row in enemies:    # (name, max_hp, damage, speed_pct, exp_reward)
                self._x("INSERT IGNORE INTO enemy_types (name, max_hp, damage, speed_pct, exp_reward) VALUES (%s,%s,%s,%s,%s)",
                        row).close()
        self._txn(go)

    def upgrade_ids(self):
        """{perk code: upgrade_id}"""
        return {r["code"]: r["upgrade_id"] for r in self._rows("SELECT upgrade_id, code FROM upgrades")}

    def enemy_type_ids(self):
        """{enemy name: enemy_type_id}"""
        return {r["name"]: r["enemy_type_id"] for r in self._rows("SELECT enemy_type_id, name FROM enemy_types")}

    # -- accounts ----------------------------------------------------------
    def find_account(self, username):
        """Row with account_id and password_hash, or None."""
        return self._one("SELECT account_id, password_hash FROM accounts WHERE username=%s", (username,))

    def username_of(self, account_id):
        return self._one("SELECT username FROM accounts WHERE account_id=%s", (account_id,))["username"]

    def create_account(self, username, password_hash, default_keys, first_map_id):
        """Account + default key bindings + first save slot, in one transaction. Returns account_id."""
        def go():
            cur = self._x("INSERT INTO accounts (username, password_hash, last_login) VALUES (%s,%s,NOW())",
                          (username, password_hash))
            aid = cur.lastrowid
            cur.close()
            for action, code in default_keys.items():
                self._x("INSERT INTO keybindings (account_id, action, key_code) VALUES (%s,%s,%s)", (aid, action, code)).close()
            self._x("INSERT INTO saves (account_id, current_map_id, slot_number) VALUES (%s,%s,1)", (aid, first_map_id)).close()
            return aid
        try:
            return self._txn(go)
        except mysql_errors.IntegrityError:
            raise DuplicateAccountError(username)

    def touch_login(self, account_id):
        self._txn(lambda: self._x("UPDATE accounts SET last_login=NOW() WHERE account_id=%s", (account_id,)).close())

    # -- keybindings -------------------------------------------------------
    def get_keybinds(self, account_id):
        """{action: key_code} (only the rows that exist)."""
        return {r["action"]: r["key_code"] for r in
                self._rows("SELECT action, key_code FROM keybindings WHERE account_id=%s", (account_id,))}

    def save_keybinds(self, account_id, keys):
        def go():
            for action, code in keys.items():
                self._x("INSERT INTO keybindings (account_id, action, key_code) VALUES (%s,%s,%s) "
                        "ON DUPLICATE KEY UPDATE key_code=VALUES(key_code)", (account_id, action, code)).close()
        self._txn(go)

    # -- saves / perks / gold ---------------------------------------------
    def get_save(self, account_id, slot=1):
        return self._one("SELECT * FROM saves WHERE account_id=%s AND slot_number=%s", (account_id, slot))

    def create_save(self, account_id, map_id, slot=1):
        self._txn(lambda: self._x("INSERT INTO saves (account_id, current_map_id, slot_number) VALUES (%s,%s,%s)",
                                  (account_id, map_id, slot)).close())

    def get_perk_ranks(self, save_id):
        """{perk code: rank}"""
        q = ("SELECT u.code, su.times_taken FROM save_upgrades su JOIN upgrades u ON u.upgrade_id = su.upgrade_id "
             "WHERE su.save_id=%s")
        return {r["code"]: r["times_taken"] for r in self._rows(q, (save_id,))}

    def get_gold(self, save_id):
        return self._one("SELECT gold FROM saves WHERE save_id=%s", (save_id,))["gold"]

    def purchase_perk(self, save_id, upgrade_id, cost):
        """Spend gold and raise the perk's rank by one, atomically."""
        def go():
            self._x("UPDATE saves SET gold=gold-%s, updated_at=NOW() WHERE save_id=%s", (cost, save_id)).close()
            self._x("INSERT INTO save_upgrades (save_id, upgrade_id, times_taken) VALUES (%s,%s,1) "
                    "ON DUPLICATE KEY UPDATE times_taken = times_taken + 1", (save_id, upgrade_id)).close()
        self._txn(go)

    # -- run history -------------------------------------------------------
    def record_run(self, save_id, map_id, result, level_reached, duration, kill_rows, exp_gained, gold_gained):
        """Store one finished run and add its rewards to the save. kill_rows = [(enemy_type_id, kills)]."""
        def go():
            cur = self._x("INSERT INTO runs (save_id, map_id, result, level_reached, duration_seconds) VALUES (%s,%s,%s,%s,%s)",
                          (save_id, map_id, result, int(level_reached), int(duration)))
            run_id = cur.lastrowid
            cur.close()
            for enemy_type_id, n in kill_rows:
                self._x("INSERT INTO run_kills (run_id, enemy_type_id, kills) VALUES (%s,%s,%s)",
                        (run_id, enemy_type_id, int(n))).close()
            self._x("UPDATE saves SET gold=gold+%s, exp=exp+%s, level=GREATEST(level, %s), current_map_id=%s, updated_at=NOW() "
                    "WHERE save_id=%s", (int(gold_gained), float(exp_gained), int(level_reached), map_id, save_id)).close()
            return run_id
        return self._txn(go)

    def victory_map_ids(self, save_id):
        """Ids of the maps this save has won at least once."""
        return {r["map_id"] for r in self._rows(
            "SELECT DISTINCT map_id FROM runs WHERE save_id=%s AND result='victory'", (save_id,))}
