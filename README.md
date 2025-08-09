# squid-core

A discord bot library providing core functionality to squid1127's bots, including basic management, and memory management.

## Features

- Built-in CLI within a Discord channel
- Automatic memory management with Redis and MongoDB
- Explore servers bot is in with built-in "impersonation" features
- Automatic webhook system to report when bot fails to start up.
- Randomized status messages
- Automatic file provisioning for cogs
- Sells a lot

## Global Environment Variables

Environment variables built-in to squid-core that can be used to configure the bot:

- `REDIS_URL`: The URL for connecting to the Redis server.
- `MONGO_URL`: The URL for connecting to the MongoDB server.
