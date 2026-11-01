"""
SERVICE layer: the rules of the game's meta-progression (accounts, saves, skill tree, unlocks).

The UI calls services; services call the Repository (database layer) and use game
data from core/. Composition happens once, in `build_services`.
"""
from types import SimpleNamespace

from services.accounts import AccountService
from services.profile import ProfileService
from services.progression import ProgressionService


def build_services(repo):
    """Wire the three services to one Repository and sync the static reference tables."""
    progression = ProgressionService(repo)
    progression.sync_reference_data()
    return SimpleNamespace(accounts=AccountService(repo), profile=ProfileService(repo), progression=progression)


__all__ = ["AccountService", "ProfileService", "ProgressionService", "build_services"]
