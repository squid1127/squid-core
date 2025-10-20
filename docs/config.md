# squid-core Configuration

squid-core has a centralized configuration system that allows you to define various settings for your bot, including logging, plugins, and bot-specific options. The configuration is typically stored in a `framework.toml` file associated with your project (e.g., in the root directory). Runtime variables can also be set via environment variables, which take precedence over the configuration file settings.

## Configuration File Structure

The `framework.toml` file is organized into sections, each corresponding to a specific aspect of the bot's configuration. Here's a typical manifest might look like:

```toml
# Project Metadata
[project]
name = "My Discord Bot"
description = "A Discord bot built with squid-core"
version = "0.1.0"

# Bot settings
[bot]
command_prefix = "squid " # Command prefix for CLI commands, notice the space
intents = ["messages", "guilds", "members", "message_content"] # Intents to enable

# Logging configuration
[logging]
level = "INFO"
file = "logs/bot.log"

# Plugin configuration
[plugins]
enabled = ["core:*", "my_custom_plugin"]

# Plugin-specific configuration
[plugins.perms_cli]
use_cog = true
```

## Other Configuration Sources

> [!NOTE]
> Configuration Options often support multiple sources for flexibility. `*` in the Source column indicates that the option can be set via all available sources (configuration file, environment variable, db, etc.).

| Source      | Description                                                                                    | Naming Convention (Ex)                         |
| ----------- | ---------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| Database/KV | Configuration settings can be stored in a database or knowledge base and retrieved at runtime. | some_group/some_var                            |
| Environment | Environment variables can be used to override configuration settings.                          | SOME_GROUP_SOME_VAR                            |
| Manifest    | The `framework.toml` file contains the primary configuration settings for the bot.             | some_group.some_var \| [some_group]\nsome_name |
| Default     | Hardcoded default values are used if no other source provides a value.                         | N/A                                            |

## Framework Configuration Options

The following table summarizes some of the key configuration options available in squid-core.

| Option                | Type         | Default              | Source      | Description                                                                        |
| --------------------- | ------------ | -------------------- | ----------- | ---------------------------------------------------------------------------------- |
| project.name          | String       | "squidbot"           | \*          | The internal name of the framework instance.                                       |
| project.friendly_name | String       | "Squid Bot"          | \*          | The friendly name of the framework instance.                                       |
| bot.token             | String       | Required             | Env         | The bot token for authenticating with the Discord API.                             |
| bot.command_prefix    | String       | "!"                  | \*          | The command prefix for bot commands.                                               |
| bot.intents           | List[String] | None                 | \*          | The Discord bot intents to enable. Eg: ['messages', 'guilds']                      |
| bot.cli.prefix        | String       | "> "                 | \*          | The prefix for CLI commands sent via Discord.                                      |
| bot.cli.channels      | List[Int]    | Required             | Env/KV/File | A list of channel IDs where CLI commands are allowed.                              |
| log.level             | String       | "INFO"               | \*          | The logging level for the framework. Can be DEBUG, INFO, WARNING, ERROR, CRITICAL. |
| log.debug_mode        | Boolean      | False                | \*          | Enable debug mode for the framework.                                               |
| log.file              | String       | None                 | \*          | The file path to log output to. If not set, logging to file is disabled.           |
| log.console           | Boolean      | True                 | \*          | Enable logging output to the console.                                              |
| plugins.plugins       | List[String] | None                 | \*          | A list of plugins to load at framework startup.                                    |
| plugins.packages      | Dict         | None                 | Global/File | A mapping of plugin package names to their module paths.                           |
| plugins.package_core  | String       | "squid_core.plugins" | Global/File | Override the core plugins package module path.                                     |
| database.url          | String       | Required             | Env         | The connection string for the database used by the framework.                      |
| redis.url             | String       | Required             | Env         | The connection string for the Redis instance used by the framework.                |
