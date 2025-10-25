"""Redis support component for Squid Core."""

from redis import asyncio as aioredis
import json
import asyncio

from ..logging import get_framework_logger

class Redis:
    def __init__(
        self,
        url: str,
        namespace: str = "squid_core",
    ):
        """Initialize the Redis client.

        Args:
            url (str): The Redis server URL.
            namespace (str, optional): The base namespace for keys. Defaults to "squid_core".
        """
        self.url = url
        self.client: aioredis.Redis | None = None
        self._listeners: dict[str, list] = {}
        self.namespace = namespace
        self.logger = get_framework_logger("redis")

    async def connect(self) -> None:
        """Establish a connection to the Redis server."""
        self.client = aioredis.from_url(self.url)

        self.logger.info(f"Connected to Redis")
        # Start the subscription listener loop
        asyncio.create_task(self._subscribe_loop())

    async def disconnect(self) -> None:
        """Close the connection to the Redis server."""
        if self.client:
            await self.client.close()
            self.client = None

    def namespace_generator(
        self,
        plugin_name: str = None,
        component_name: str = None,
        internal: bool = False,
        name: list[str] = [],
    ) -> str:
        """Generate a namespaced Redis key.

        Args:
            plugin_name (str, optional): The plugin name. Defaults to None.
            component_name (str, optional): The component name. Defaults to None.
            internal (bool, optional): Whether it's an internal namespace. Defaults to False.
            name (list[str], optional): Additional name segments. Defaults to [].

        Returns:
            str: The generated namespaced key.
        """
        parts = [self.namespace]
        if internal:
            parts.append("internal")
        if plugin_name:
            parts.append("plugin")
            parts.append(plugin_name)
        if component_name:
            parts.append("component")
            parts.append(component_name)
        parts.extend(name)
        return ":".join(parts)

    def add_listener(self, channel: str|list[str], callback, plugin_name: str = None, component_name: str = None, **kwargs) -> None:
        """Add a listener for a specific Redis channel.

        Args:
            channel (str | list[str]): The Redis channel name, on one (str) or more (list[str]) levels.
            callback (callable): The callback function to invoke on message.
            plugin_name (str, optional): The plugin name. Defaults to None.
            component_name (str, optional): The component name. Defaults to None.
            **kwargs: Additional arguments for namespacing.
        """
        
        channel = self.namespace_generator(
            plugin_name=plugin_name,
            component_name=component_name,
            name=[channel] if isinstance(channel, str) else channel,
            **kwargs,
        )
        if channel not in self._listeners:
            self._listeners[channel] = []
        self._listeners[channel].append(callback)
        self.logger.info(f"Added listener for channel: {channel}")

    def remove_listener(self, channel: str, callback) -> None:
        """Remove a listener from a specific Redis channel.

        Args:
            channel (str): The Redis channel.
            callback (callable): The callback function to remove.
        """
        if channel in self._listeners:
            self._listeners[channel].remove(callback)
            if not self._listeners[channel]:
                del self._listeners[channel]

    async def _handle_message(self, channel: str, message: dict) -> None:
        """Invoke all listeners for a specific channel with the message.

        Args:
            channel (str): The Redis channel.
            message (dict): The message received.
        """
        if channel in self._listeners:
            for callback in self._listeners[channel]:
                asyncio.create_task(callback(message))

    async def publish(self, channel: str, message: dict) -> None:
        """Publish a message to a Redis channel.

        Args:
            channel (str): The Redis channel.
            message (dict): The message to publish.
        """
        if not self.client:
            raise RuntimeError("Redis client is not connected.")
        await self.client.publish(channel, json.dumps(message))

    async def _subscribe_loop(self) -> None:
        """Internal loop to subscribe and listen for messages."""
        if not self.client:
            raise RuntimeError("Redis client is not connected.")
        
        self.logger.info(f"Starting Redis subscription with {len(self._listeners)} channels.")
        pubsub = self.client.pubsub()
        await pubsub.subscribe(*self._listeners.keys())

        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    channel = message["channel"].decode()
                    try:
                        data = json.loads(message["data"].decode())
                    except json.JSONDecodeError:
                        data = message["data"].decode()
                    self.logger.info(f"Received message on {channel}: {data}")
                    await self._handle_message(channel, data)
                except Exception as e:
                    self.logger.error(f"Error processing message from {channel}: {e}") 
