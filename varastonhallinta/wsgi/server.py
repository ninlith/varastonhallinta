# Copyright 2021 Okko Hartikainen <okko.hartikainen@gmail.com>
#
# This work is licensed under the GNU GPLv3. See LICENSE.

"""WSGI server startup wrapper."""

import logging
from contextlib import redirect_stdout
from paste.translogger import TransLogger  # middleware for logging requests
from waitress import serve
from wsgi.application import app

def wsgi_server(sockets, database, translogger=False, dev=False,
                configurer=None):
    """Start WSGI server."""
    if configurer is not None:
        configurer()
    logger = logging.getLogger(__name__)

    app.config["database"] = database
    if dev:
        app.debug = True
        logger.info("Flask debug mode enabled.")

    if translogger:
        log_format = ('%(REMOTE_ADDR)s - %(REMOTE_USER)s "%(REQUEST_METHOD)s '
                      '%(REQUEST_URI)s %(HTTP_VERSION)s" %(status)s %(bytes)s '
                      '"%(HTTP_REFERER)s" "%(HTTP_USER_AGENT)s"')
        wsgi_app = TransLogger(app,
                               setup_console_handler=False,
                               format=log_format,
                               logger_name="translogger")
    else:
        wsgi_app = app

    # Redirect waitress stdout to log, start waitress.
    logger = logging.getLogger("waitress")
    logging.write = lambda msg: logger.info(msg) if msg != "\n" else None
    with redirect_stdout(logging):
        serve(wsgi_app, sockets=sockets, threads=6)
