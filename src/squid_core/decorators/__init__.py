"""Decorator system for Squid Core."""

# Import decorators
from .discord_dec import DiscordEventListener
from .event_dec import FwEventListener
from .cli_dec import CLICommand as CLICommandDec
from .redis import RedisSubscribe

# Expose decorators in the package namespace
__all__ = [
    "DiscordEventListener",
    "FwEventListener",
    "CLICommandDec",
    "RedisSubscribe",
]