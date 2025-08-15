# squid-core

A discord bot library providing core functionality to squid1127's bots, including basic management, and memory management.

## Disclaimer

This library is not intended for public use and is designed specifically for squid1127's bots. Please do not use this library for your own bots, as its structure and functionality may change without notice (a lot).

## Features

- Built-in CLI within a Discord channel
- Memory management using Redis and MongoDB
- Basic bot management features
- Basic permissions system (CLI is still accessible to everyone with access to its channel, which is used to set permissions)
- Support for multiple cogs and extensions
- DM system that allows admins to send direct messages to users via the bot
- Discord explorer for viewing server information and user data (Use in private servers only, limited support)
- Basic error handling and logging
- Support for Uptime Kuma for monitoring bot status (passive monitors)

## Global Environment Variables

Environment variables built-in to squid-core that can be used to configure the bot:

- `REDIS_URL`: The URL for connecting to the Redis server.
- `MONGO_URL`: The URL for connecting to the MongoDB server.

Note: These variables are only used if the bot is configured to use Redis and MongoDB for memory management.
