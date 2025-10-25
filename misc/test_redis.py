"""Connect to Redis and test Redis pub/sub functionality."""

import asyncio
from redis import asyncio as aioredis
import os
from dotenv import load_dotenv

ENV_VAR = "REDIS_URL"

async def main():
    load_dotenv()
    redis_url = os.getenv(ENV_VAR, "redis://localhost:6379")

    redis = aioredis.from_url(redis_url)
    pubsub = redis.pubsub()

    channel_name = "squid_core:plugin:RandomPlugin:test_channel"

    async def message_handler():
        await pubsub.subscribe(channel_name)
        print(f"Subscribed to {channel_name}")
        async for message in pubsub.listen():
            if message['type'] == 'message':
                print(f"Received message: {message['data'].decode()}")

    async def publisher():
        await asyncio.sleep(1)  # Wait a moment to ensure subscription is set up
        i = 0
        while True:
            message = f"Hello {i}"
            await redis.publish(channel_name, message)
            print(f"Published message: {message}")
            i += 1
            await asyncio.sleep(1)

    await asyncio.gather(message_handler(), publisher())
    
if __name__ == "__main__":
    asyncio.run(main())