"""
squid-core: A modular, batteries-included Discord bot framework built on top of Discord.py.
"""

__version__ = "0.1.0"
__author__ = "squid1127"
__license__ = "MIT"

from .framework import Framework
from .logging import LoggerManager, get_framework_logger
from .plugin_base import Plugin, PluginComponent, PluginCog
from .config import ConfigManager, ConfigSchema, ConfigOption