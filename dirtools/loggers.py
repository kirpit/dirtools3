import asyncio
import logging
import os
import sys

DEBUG = bool(os.environ.get('DIRTOOLS3_DEBUG'))

# Mostly for debugging asyncio
logger = logging.getLogger('asyncio')
log_handler = logging.StreamHandler(sys.stdout)
log_formatter = logging.Formatter('[%(name)s][%(levelname)s] %(asctime)s - %(message)s')
log_handler.setFormatter(log_formatter)
logger.addHandler(log_handler)

if DEBUG is True:
    logger.setLevel(logging.DEBUG)
    loop = asyncio.get_event_loop()
    loop.set_debug(DEBUG)
else:
    logger.setLevel(logging.WARNING)
