"""Configuration for logging in SquidCore."""

import logging, coloredlogs

# coloredlogs.install(level='DEBUG', fmt='%(asctime)s %(levelname)s %(name)s %(message)s')
coloredlogs.install(level='INFO', fmt='%(asctime)s %(levelname)s - %(name)s %(message)s')
logger = logging.getLogger('core')