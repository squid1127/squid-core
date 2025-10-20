"""Redis-related decorators."""

from .base import Decorator, DecoratorManager
from ..plugin_base import Plugin
from ..components.redis_comp import Redis as RedisType

@DecoratorManager.add
class RedisSubscribe(Decorator):
    """Decorator to register a Redis channel subscriber."""

    def __init__(self, channel: str) -> None:
        """Initialize the decorator with the Redis channel name."""
        super().__init__()
        self.channel = channel

    async def apply(self, plugin: Plugin, func: callable, *args, **kwargs) -> None:
        """Apply the decorator logic to register the Redis subscriber."""
        try:
            redis: RedisType = plugin.fw.redis
            redis.add_listener(self.channel, func)
            plugin.fw.logger.info(
                f"Registered Redis subscriber for channel '{self.channel}' in plugin '{plugin.name}'"
            )
        except Exception as e:
            plugin.fw.logger.error(
                f"Failed to register Redis subscriber for channel '{self.channel}' in plugin '{plugin.name}': {e}"
            )
            raise e