# squid-core

A discord bot library providing core functionality to squid1127's bots, including basic management, and db connection.

## Features

- Built-in CLI within a Discord channel
- Basic PostgreSQL support for data storage
- Explore servers bot is in with built-in "impersonation" features
- Automatic webhook system to report when bot fails to start up.
- Randomized status messages
- Automatic file provisioning for cogs
- Sells a lot

## Global Environment Variables

Environment variables built-in to squid-core that can be used to configure the bot:

- PostgreSQL Connection:
  - `POSTGRES_DSN`: The full DSN string for connecting to the PostgreSQL database.
  - `POSTGRES_HOST`: The hostname or IP address of the PostgreSQL server.
  - `POSTGRES_PORT`: The port number on which the PostgreSQL server is listening.
  - `POSTGRES_DB`: The name of the PostgreSQL database.
  - `POSTGRES_USER`: The username for the PostgreSQL database.
  - `POSTGRES_PASSWORD`: The password for the PostgreSQL database user.
