"""Redis support component for Squid Core."""

from redis import asyncio as aioredis
import json
import asyncio

class Redis:
    def __init__(self, url: str):
        """Initialize the Redis client.

        Args:
            url (str): The Redis server URL.
        """
        self.url = url
        self.client: aioredis.Redis | None = None
        self._listeners: dict[str, list] = {}

    async def connect(self) -> None:
        """Establish a connection to the Redis server."""
        self.client = aioredis.from_url(self.url)
        
        # Start the subscription listener loop
        asyncio.create_task(self._subscribe_loop())
        
    async def disconnect(self) -> None:
        """Close the connection to the Redis server."""
        if self.client:
            await self.client.close()
            self.client = None
            
            
    def add_listener(self, channel: str, callback) -> None:
        """Add a listener for a specific Redis channel.

        Args:
            channel (str): The Redis channel to listen to.
            callback (callable): The callback function to invoke on message.
        """
        if channel not in self._listeners:
            self._listeners[channel] = []
        self._listeners[channel].append(callback)
        
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
        
        pubsub = self.client.pubsub()
        await pubsub.subscribe(*self._listeners.keys())
        
        async for message in pubsub.listen():
            if message['type'] == 'message':
                channel = message['channel'].decode()
                data = json.loads(message['data'].decode())
                await self._handle_message(channel, data)