"""
Project Strikers
================
Entry point and composition root.   Run:  python project_strikers.py

Layers (each one only talks to the layer below it):
    ui/        screens, drawing                 (pygame)
    services/  accounts, profile, progression   (game meta-rules)
    database/  Repository                       (SQL / MySQL via XAMPP)
    core/      game data + the run engine       (no screen, no SQL)
"""
import sys

import pygame

from ui import app as ui                       
from database import DatabaseError, Repository
from services import build_services


def main():
    try:
        services = build_services(Repository())
    except DatabaseError as e:
        ui.show_db_error(str(e))
        pygame.quit()
        sys.exit(1)
    ui.App(services).loop()
    pygame.quit()


if __name__ == "__main__":
    main()
