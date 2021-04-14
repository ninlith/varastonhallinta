# Copyright 2021 Okko Hartikainen <okko.hartikainen@gmail.com>
#
# This work is licensed under the GNU GPLv3. See LICENSE.

"""Database initialization."""

import errno
import importlib.resources
import logging
import os
import pathlib
import sqlite3
import appdirs
from auxiliary.conf import PROJECT_NAME, DB_VERSION

logger = logging.getLogger(__name__)

def ensure_user_data_dir() -> pathlib.Path:
    """Create user application data directory if it doesn't exist."""
    project_data_path = pathlib.Path(appdirs.user_data_dir(PROJECT_NAME))
    if not project_data_path.exists():
        project_data_path.mkdir(parents=True)
    return project_data_path

def ensure_database(database: str) -> pathlib.Path:
    """Create database if it doesn't exist."""
    # Get database path.
    if database is None:
        database = ensure_user_data_dir() / f"varasto-v{DB_VERSION}.sqlite3"
    else:
        database = pathlib.Path(database)
    logger.info(f"database = {database}")

    # Create database conditionally.
    if not database.exists():
        logger.info("Initializing database...")
        if database.parent.is_file():
            raise NotADirectoryError(errno.ENOTDIR,
                                     os.strerror(errno.ENOTDIR),
                                     str(database.parent))
        elif not database.parent.exists():
            raise FileNotFoundError(errno.ENOENT,
                                    os.strerror(errno.ENOENT),
                                    str(database.parent))
        create_database(database)

    return database

def create_database(pathname: pathlib.Path):
    """Create database."""
    connection = sqlite3.connect(pathname)
    connection.executescript(
        importlib.resources.read_text(__package__, "schema.sql"))
    connection.executescript(
        importlib.resources.read_text(__package__, "initial_data.sql"))
    connection.commit()
    connection.close()
