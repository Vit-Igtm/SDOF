"""DATABASE layer: MySQL/MariaDB access (XAMPP). Only SQL lives here - no game rules."""
from database.repository import DatabaseError, DuplicateAccountError, Repository

__all__ = ["Repository", "DatabaseError", "DuplicateAccountError"]
