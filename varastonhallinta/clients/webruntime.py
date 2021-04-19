# Copyright 2021 Okko Hartikainen <okko.hartikainen@gmail.com>
#
# This work is licensed under the GNU GPLv3 only. See LICENSE.

"""Webruntime startup wrapper."""

import logging
import time
from webruntime import launch
from auxiliary.conf import PROJECT_NAME

def launch_runtime(url, runtime="app", windowmode=None, size=None, pos=None,
                   configurer=None):
    """Launch runtime."""
    if configurer is not None:
        configurer()
    logger = logging.getLogger(__name__)

    logger.debug(f"runtime = {runtime}")
    try:
        rt = launch(url,
                    runtime,
                    title=PROJECT_NAME.capitalize(),
                    windowmode=windowmode,
                    size=size,
                    pos=pos)
        if "browser" not in runtime:
            rt._streamreader.join()  # wait until the process terminates
            rt.close()
        else:
            while True:
                time.sleep(60)
    except ValueError as e:
        logger.error(e)
        launch(url, "browser")
        while True:
            time.sleep(60)
