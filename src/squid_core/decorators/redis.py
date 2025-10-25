"""Redis-related decorators."""

from .base import Decorator, DecoratorManager
from ..plugin_base import Plugin
from ..components.redis_comp import Redis as RedisType

@DecoratorManager.add
class RedisSubscribe(Decorator):
    """Decorator to register a Redis channel subscriber."""

    def __init__(self, channel: str|list[str], manual: bool = False, **kwargs) -> None:
        """
        Initialize the decorator with the Redis channel name.
        
        Args:
            channel (str | list[str]): The Redis channel name, on one (str) or more (list[str]) levels.
            manual (bool, optional): If True, the decorator will not namespace the channel automatically. Defaults to False.
            **kwargs: Additional arguments for namespacing.
        """
        super().__init__()
        self.channel = channel
        self.manual = manual
        self.kwargs = kwargs

    async def apply(self, plugin: Plugin, func: callable, *args, **kwargs) -> None:
        """Apply the decorator logic to register the Redis subscriber."""
        try:
            redis: RedisType = plugin.fw.redis
            if self.manual:
                redis.add_listener(self.channel, func)
            else:
                redis.add_listener(
                    self.channel,
                    func,
                    plugin_name=plugin.name,
                    **self.kwargs,
                )
            plugin.fw.logger.info(
                f"Registered Redis subscriber for channel '{self.channel}' in plugin '{plugin.name}'"
            )
        except Exception as e:
            plugin.fw.logger.error(
                f"Failed to register Redis subscriber for channel '{self.channel}' in plugin '{plugin.name}': {e}"
            )
            raise e