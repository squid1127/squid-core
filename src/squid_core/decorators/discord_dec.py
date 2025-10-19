"""Discord-specific decorators for Squid Core."""
from .base import Decorator, DecoratorManager
from ..plugin_base import Plugin

class DiscordEventListener(Decorator):
    """Decorator to register a Discord event listener."""

    def __init__(self, event_name: str = None) -> None:
        """Initialize the decorator with the event name."""
        super().__init__()
        self.event_name = event_name
 
    async def apply(self, plugin: Plugin, func:callable, *args, **kwargs) -> None:
        """Apply the decorator logic to register the event listener."""
        if not self.event_name:
            self.event_name = func.__name__
        try:
            bot = plugin.fw.bot
            bot.add_listener(func, self.event_name)
            plugin.fw.logger.info(
                f"Registered Discord event listener '{func.__name__}' for event '{self.event_name}' in plugin '{plugin.name}'"
            )
        except Exception as e:
            plugin.fw.logger.error(
                f"Failed to register Discord event listener '{func.__name__}' for event '{self.event_name}' in plugin '{plugin.name}': {e}"
            )
            raise e
        
# Register the decorator
DecoratorManager.add(DiscordEventListener)