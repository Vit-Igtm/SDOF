-- Project Strikers - MySQL / MariaDB schema (XAMPP)
-- Import with phpMyAdmin (Import tab) or: mysql -u root < strikers_schema.sql
-- The game also runs this file automatically on start, so importing is optional.

CREATE DATABASE IF NOT EXISTS strikers CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE strikers;

CREATE TABLE IF NOT EXISTS accounts (
    account_id    INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(16)  NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login    DATETIME NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS maps (
    map_id           INT PRIMARY KEY,
    name             VARCHAR(64) NOT NULL,
    map_order        INT NOT NULL UNIQUE,
    duration_seconds INT NOT NULL,
    is_final_boss    TINYINT(1) NOT NULL DEFAULT 0
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS keybindings (
    keybind_id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    action     ENUM('up','down','left','right') NOT NULL,
    key_code   INT NOT NULL,
    UNIQUE KEY uq_key (account_id, action),
    FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS saves (
    save_id        INT AUTO_INCREMENT PRIMARY KEY,
    account_id     INT NOT NULL,
    current_map_id INT NULL,
    slot_number    INT NOT NULL DEFAULT 1,
    level          INT NOT NULL DEFAULT 1,
    exp            DOUBLE NOT NULL DEFAULT 0,
    gold           INT NOT NULL DEFAULT 0,
    updated_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_slot (account_id, slot_number),
    FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE CASCADE,
    FOREIGN KEY (current_map_id) REFERENCES maps(map_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS upgrades (
    upgrade_id  INT AUTO_INCREMENT PRIMARY KEY,
    code        VARCHAR(48) NOT NULL UNIQUE,
    name        VARCHAR(64) NOT NULL,
    description VARCHAR(255) NOT NULL,
    is_unique   TINYINT(1) NOT NULL DEFAULT 0
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS save_upgrades (
    save_id     INT NOT NULL,
    upgrade_id  INT NOT NULL,
    times_taken INT NOT NULL DEFAULT 1,
    PRIMARY KEY (save_id, upgrade_id),
    FOREIGN KEY (save_id) REFERENCES saves(save_id) ON DELETE CASCADE,
    FOREIGN KEY (upgrade_id) REFERENCES upgrades(upgrade_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS enemy_types (
    enemy_type_id INT AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(64) NOT NULL UNIQUE,
    max_hp        INT NOT NULL,
    damage        INT NOT NULL,
    speed_pct     INT NOT NULL,
    exp_reward    INT NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS runs (
    run_id           INT AUTO_INCREMENT PRIMARY KEY,
    save_id          INT NOT NULL,
    map_id           INT NOT NULL,
    result           ENUM('victory','defeat','abandoned') NOT NULL,
    level_reached    INT NOT NULL,
    duration_seconds INT NOT NULL,
    ended_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (save_id) REFERENCES saves(save_id) ON DELETE CASCADE,
    FOREIGN KEY (map_id) REFERENCES maps(map_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS run_kills (
    run_id        INT NOT NULL,
    enemy_type_id INT NOT NULL,
    kills         INT NOT NULL,
    PRIMARY KEY (run_id, enemy_type_id),
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
    FOREIGN KEY (enemy_type_id) REFERENCES enemy_types(enemy_type_id)
) ENGINE=InnoDB;
