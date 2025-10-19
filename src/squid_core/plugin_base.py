"""Base classes and utilities for plugins."""

from __future__ import annotations
from abc import ABC, abstractmethod, ABCMeta
from pathlib import Path
from typing import Any, Dict, TYPE_CHECKING
from discord.ext import commands
from discord.ext.commands.cog import CogMeta
import logging

if TYPE_CHECKING:
    from squid_core.framework import Framework


class Plugin(ABC):
    """A squid-core plugin interface, allowing for asynchronous setup and teardown."""

    def __init__(self, framework: Framework) -> None:
        self.framework = framework
        self.name = self.__class__.__name__
        self.logger = framework.logger_manager.get_plugin_logger(
            self.name.replace(":", ".")
        )

    @abstractmethod
    async def load(self) -> None:
        """Asynchronous setup method for the plugin. Executed during framework initialization."""
        pass

    @abstractmethod
    async def unload(self) -> None:
        """Asynchronous cleanup method for the plugin. Executed during framework shutdown."""
        pass

    async def _import_listeners(self) -> None:
        """Import and register event listeners. Override in subclasses if needed."""
        return []

    @property
    def fw(self) -> Framework:
        """Shortcut to access the framework instance."""
        return self.framework


class PluginComponent(ABC):
    """Abstract base class for components within a plugin, allowing for method decorators."""

    def __init__(self, plugin: Plugin) -> None:
        self.plugin = plugin
        self.framework = plugin.framework
        self.fw = plugin.framework # Shortcut to access the framework instance


class _PluginCogMeta(CogMeta, ABCMeta):
    pass


class PluginCog(commands.Cog, PluginComponent, metaclass=_PluginCogMeta):
    """A plugin component that is also a Discord Cog."""

    def __init__(self, plugin: Plugin) -> None:
        # The order of __init__ calls is important for MRO.
        # PluginComponent.__init__ should be called before commands.Cog.__init__
        # if Cog has dependencies on things set up in PluginComponent.
        # However, given the current implementation, the order doesn't strictly matter,
        # but it's good practice to follow a logical setup sequence.
        PluginComponent.__init__(self, plugin)
        commands.Cog.__init__(self)
        PluginComponent.__init__(self, plugin)
        self.bot = plugin.framework.bot
