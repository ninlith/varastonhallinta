# Copyright 2021 Okko Hartikainen <okko.hartikainen@gmail.com>
#
# This work is licensed under the GNU GPLv3 only. See LICENSE.

"""Flask application."""

import logging
import secrets
import sqlite3
from datetime import datetime, timezone
from flask import Flask, g
from auxiliary.conf import PROJECT_NAME, VERSION

logger = logging.getLogger(__name__)

def get_db_connection() -> sqlite3.Connection:
    """Open database connection."""
    conn = getattr(g, '_database', None)
    if conn is None:
        logger.debug("Opening database connection...")
        conn = g._database = sqlite3.connect(app.config["database"],
                                             factory=LoggingConnection)
    conn.row_factory = sqlite3.Row  # enables access by index or key
    return conn

class LoggingConnection(sqlite3.Connection):
    """Extend superclass for commit logging."""

    class StatementContainer:
        """Contain statements."""
        def __init__(self):
            self._data = []

        def add_data(self, s):
            s = s.strip()
            if s not in ("BEGIN", "COMMIT"):
                lines = s.splitlines()
                self._data.append(" ".join([line.strip() for line in lines]))
                logger.debug(self.data)

        @property
        def data(self):
            return "; ".join(self._data)

        def clear_data(self):
            self._data.clear()

    def cursor(self):
        self.container = self.StatementContainer()
        self.set_trace_callback(self.container.add_data)
        return super().cursor()

    def commit(self):
        self.execute(
            "INSERT INTO Muutosloki (aikaleima, komento) VALUES (?, ?)",
            (datetime.now(timezone.utc).astimezone().isoformat(),
             self.container.data))
        self.container.clear_data()
        super().commit()

app = Flask(__name__)
app.config["SECRET_KEY"] = secrets.token_urlsafe(16)  # for the session cookie

@app.teardown_appcontext
def close_connection(exception):
    """Close database connection on application context destruction."""
    conn = getattr(g, '_database', None)
    if conn is not None:
        logger.debug("Closing database connection...")
        conn.close()

@app.context_processor
def inject_variables():
    """Inject variables into the template context."""
    return dict(project_name=PROJECT_NAME.capitalize(), version=VERSION)
