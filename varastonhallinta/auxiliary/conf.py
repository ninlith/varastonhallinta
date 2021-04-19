# Copyright 2021 Okko Hartikainen <okko.hartikainen@gmail.com>
#
# This work is licensed under the GNU GPLv3 only. See LICENSE.

"""Configuration-related classes and functions."""

import argparse
import importlib.resources
import logging
import logging.config

PROJECT_NAME = "varastonhallinta"
VERSION = "0.1.0"
DB_VERSION = "0.1"  # VERSION.split(".")[0]

def parse_command_line_args() -> argparse.Namespace:
    """Define and parse command-line options."""

    def collect_as(coll_type: type) -> argparse.Action:
        """Convert argument list produced by nargs to a given type."""
        # https://stackoverflow.com/a/50365836
        class CollectAsAction(argparse.Action):
            """Custom action with type conversion."""
            def __call__(self, parser, namespace, values, options_string=None):
                setattr(namespace, self.dest, coll_type(values))
        return CollectAsAction

    class ClientOnlyAction(argparse.Action):
        """Custom action to set client_only and scheme values."""
        def __init__(self, *args, **kwargs):
            setattr(argparse.Namespace, "scheme", "http")  # XXX, set default
            super(ClientOnlyAction, self).__init__(*args, **kwargs)
        def __call__(self, parser, namespace, values, option_string=None):
            if isinstance(values, bool):
                setattr(namespace, self.dest, values)
            else:
                setattr(namespace, self.dest, True)
                setattr(namespace, "scheme", values)

    parser = argparse.ArgumentParser(description="Warehouse Management System",
                                     allow_abbrev=False)

    # Hidden options.
    parser.add_argument("--dev", action="store_true", help=argparse.SUPPRESS)

    # Optional arguments section.
    parser.add_argument(
        "--database", metavar="PATHNAME",
        help="relative or absolute path to a database file (defaults to using "
             "an .sqlite3 file within user application data directory)")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--server-only", action="store_true", help="run in server mode")
    mode_group.add_argument(
        "--client-only", nargs="?", const=True, default=False,
        choices=["http", "https"], action=ClientOnlyAction,
        help="run in client mode [URI scheme (default: http)]")
    parser.add_argument(
        "--debug", action="store_const", dest="loglevel", const=logging.DEBUG,
        default=logging.INFO, help="enable DEBUG logging level")
    parser.add_argument(
        "--translogger", action="store_true", help="enable request logging")
    parser.add_argument(
        "--version", action="store_true", help="output version and exit")

    # Socket address section.
    socket_group = parser.add_argument_group(
        "socket address", "AF_INET6 address family")
    socket_group.add_argument(
        "--host", default="::1", help="host (default: %(default)s)")
    socket_group.add_argument(
        "--port", default="0", type=int,
        help="port (default: 0 (bind to a free port provided by the operating "
             "system))")
    socket_group.add_argument(
        "--flowinfo", default="0", type=int, help="flow label")
    socket_group.add_argument(
        "--scope_id", default="0", type=int,
        help="scope identifier (e.g. interface number for link-local "
             "addresses)")

    # Client options section.
    client_group = parser.add_argument_group(
        "client options", "see Webruntime's documentation")
    client_group.add_argument(
        "--runtime", metavar="{firefox-browser,firefox-app,nw-app...}",
        default="chrome-app", help="browser or desktop-like runtime "
                                   "(default: chrome-app, fallback: browser)")
    client_group.add_argument(
        "--window-size", metavar=("X", "Y"), nargs=2, type=int,
        default=(1920, 1080), action=collect_as(tuple),
        help="initial window size (default: 1920 1080)")
    client_group.add_argument(
        "--window-pos", metavar=("X", "Y"), nargs=2, type=int, default=None,
        action=collect_as(tuple), help="initial window position")
    client_group.add_argument(
        "--window-mode",
        choices=("normal", "maximized", "fullscreen", "kiosk"),
        help="initial window mode "
             "(not all modes are supported by all runtimes)")
    return parser.parse_args()

def output_logger_configurer():
    """Configure output logger."""
    with importlib.resources.path(__package__, "logging.ini") as config_file:
        logging.config.fileConfig(config_file, disable_existing_loggers=False)

def worker_logger_configurer(queue, loglevel):
    """Configure worker logger."""
    handler = logging.handlers.QueueHandler(queue)
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(loglevel)

def listener_process(queue):
    """Forward logging messages from queue to output logger."""
    output_logger_configurer()
    while True:
        try:
            record = queue.get()
            if record is None:  # sentinel to tell the listener to quit
                break
            logger = logging.getLogger(record.name)
            logger.handle(record)
        except Exception:
            import sys
            import traceback
            print("Whoops! Problem:", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
