#!/usr/bin/env python3
#
# Copyright 2021 Okko Hartikainen <okko.hartikainen@gmail.com>
#
# This work is licensed under the GNU GPLv3. See LICENSE.

"""Warehouse Management System."""

import ipaddress
import logging
import multiprocessing
import os
import socket
import sys
import time
from contextlib import suppress
from functools import partial
import urllib3
from auxiliary import conf, db
from clients.webruntime import launch_runtime
from wsgi.server import wsgi_server

def main():
    """Run the program."""

    # Command-line arguments.
    args = conf.parse_command_line_args()
    if args.version:
        print(conf.VERSION)
        sys.exit()

    # Legal notice.
    print("Copyright 2021 Okko Hartikainen <okko.hartikainen@gmail.com>\n\n"
          "This program comes with ABSOLUTELY NO WARRANTY. "
          "See the GNU General Public\nLicence, version 3 "
          "<https://www.gnu.org/licenses/gpl-3.0.html> for details.\n")

    # Logging.
    queue = multiprocessing.Queue(-1)
    logging_listener = multiprocessing.Process(target=conf.listener_process,
                                               args=(queue,))
    logging_listener.start()
    configurer = partial(conf.worker_logger_configurer, queue, args.loglevel)
    configurer()
    if os.name == "posix":
        configurer = None  # root logger propagates its handler
    logger = logging.getLogger(__name__)

    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as sock:
        if not args.client_only:
            database = db.ensure_database(args.database)
            sock.bind((args.host, args.port, args.flowinfo, args.scope_id))
            logger.debug(f"Socket: {sock}")
            server = multiprocessing.Process(target=wsgi_server,
                                             args=([sock],
                                                   database,
                                                   args.translogger,
                                                   args.dev,
                                                   configurer))
        if not args.server_only:
            scheme, host, port = args.scheme, args.host, args.port
            if not args.client_only:
                port = sock.getsockname()[1]
            with suppress(ValueError):
                if ipaddress.ip_address(host).version == 6:
                    host = f"[{host}]"
            url = f"{scheme}://{host}:{port}"
            logger.debug(f"URL: {url}")
            client = multiprocessing.Process(target=launch_runtime,
                                             args=(url,
                                                   args.runtime,
                                                   args.window_mode,
                                                   args.window_size,
                                                   args.window_pos,
                                                   configurer))
        if args.server_only:
            server.start()
        elif args.client_only:
            client.start()
        else:
            logger.debug("Starting server...")
            server.start()
            logger.debug("Waiting for server to respond...")
            http = urllib3.PoolManager(timeout=10.0, retries=1)
            time.sleep(0.1)
            try:
                for _ in range(10):
                    time.sleep(1)
                    with suppress(urllib3.exceptions.HTTPError):
                        if http.request("HEAD", url).status == 200:
                            break
                else:
                    logger.critical("Maximum retries exceeded.")
                    raise ConnectionError
            except ConnectionError:
                raise ConnectionError("Server failed to respond.")
            else:
                logger.debug("Starting client...")
                client.start()
                client.join()  # wait until the client terminates
            finally:
                server.terminate()
                queue.put_nowait(None)  # command logging listener to quit
                logging_listener.join()

if __name__ == "__main__":
    multiprocessing.freeze_support()  # required for pyinstaller on windows
    main()
