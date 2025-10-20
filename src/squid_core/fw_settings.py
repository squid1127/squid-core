"""Framework settings/configuration schema"""

from .config import ConfigSchema, ConfigOption, ConfigSource, ConfigRequired
from dataclasses import dataclass

@dataclass(frozen=True)
class FWSettings(ConfigSchema):
    """Framework settings loaded from environment variables."""

    # General Settings
    name: str
    friendly_name: str
    # Bot Settings
    bot_token: str
    bot_cmd_prefix: str
    bot_intents: list[str] | None
    # Logging Settings
    log_level: str
    debug_mode: bool
    log_file: str | None
    log_to_console: bool
    # Plugin Settings
    plugins: list[str] | None
    plugins_packages: dict[str, str] | None
    plugins_package_core: str
    
    # Database Settings
    database_url: str | None
    redis_url: str | None
    # CLI Settings
    cli_prefix: str
    cli_channels: list[int] | None
    # FS Settings
    data_dir:str

    _options = {
        "name": ConfigOption(
            name=["project", "name"],
            default="squidbot",
            enforce_type=str,
            enforce_type_coerce=True,
            description="The internal name of the framework instance.",
        ),
        "friendly_name": ConfigOption(
            name=["project", "friendly_name"],
            default="Squid Bot",
            enforce_type=str,
            enforce_type_coerce=True,
            description="The friendly name of the framework instance.",
        ),
        "bot_token": ConfigOption(
            name=["bot", "token"],
            sources=[ConfigSource.ENVIRONMENT],
            default=ConfigRequired,
            enforce_type=str,
            enforce_type_coerce=True,
            description="The bot token for authenticating with the Discord API.",
        ),
        "bot_cmd_prefix": ConfigOption(
            name=["bot", "command_prefix"],
            default="!",
            enforce_type=str,
            enforce_type_coerce=True,
            description="The command prefix for bot commands.",
        ),
        "bot_intents": ConfigOption(
            name=["bot", "intents"],
            default=None,
            enforce_type=list,
            description="The Discord bot intents to enable. Eg: ['messages', 'guilds']",
        ),
        "log_level": ConfigOption(
            name=["log", "level"],
            default="INFO",
            enforce_type=str,
            enforce_type_coerce=True,
            description="The logging level for the framework. Can be DEBUG, INFO, WARNING, ERROR, CRITICAL.",
        ),
        "debug_mode": ConfigOption(
            name=["log", "debug_mode"],
            default=False,
            enforce_type=bool,
            enforce_type_coerce=True,
            description="Enable debug mode for the framework.",
        ),
        "log_file": ConfigOption(
            name=["log", "file"],
            default=None,
            enforce_type=str,
            enforce_type_coerce=True,
            description="The file path to log output to. If not set, logging to file is disabled.",
        ),
        "log_to_console": ConfigOption(
            name=["log", "console"],
            default=True,
            enforce_type=bool,
            enforce_type_coerce=True,
            description="Enable logging output to the console.",
        ),
        "plugins": ConfigOption(
            name=["plugins", "plugins"],
            default=None,
            enforce_type=list,
            description="A list of plugins to load at framework startup.",
        ),
        "plugins_packages": ConfigOption(
            name=["plugins", "packages"],
            default=None,
            sources=[ConfigSource.MANIFEST_GLOBAL, ConfigSource.DEFAULT], # Required for plugin module discovery | Defined in global manifest
            enforce_type=dict,
            description="A mapping of plugin package names to their module paths.",
        ),
        "plugins_package_core": ConfigOption(
            name=["plugins", "package_core"],
            default="squid_core.plugins",
            sources=[ConfigSource.MANIFEST_GLOBAL, ConfigSource.DEFAULT], # Required for plugin module discovery | Defined in global manifest
            enforce_type=str,
            enforce_type_coerce=True,
            description="Override the core plugins package module path.",
        ),
        "database_url": ConfigOption(
            name=["database", "url"],
            sources=[ConfigSource.ENVIRONMENT, ConfigSource.DEFAULT], # DB must be set via env var if used
            default=ConfigRequired,
            enforce_type=str,
            enforce_type_coerce=True,
        ),
        "cli_prefix": ConfigOption(
            name=["bot", "cli", "prefix"],
            default="> ",
            enforce_type=str,
            enforce_type_coerce=True,
            description="The prefix for CLI commands sent via Discord.",
        ),
        "cli_channels": ConfigOption(
            name=["bot", "cli", "channels"],
            default=ConfigRequired,
            sources=[ConfigSource.ENVIRONMENT, ConfigSource.KV_STORE, ConfigSource.DEFAULT], # User-defined via env var or KV store
            enforce_type=list,
            enforce_type_coerce=True, # Needed to coerce from env var string
            description="A list of channel IDs where CLI commands are allowed.",
        ),
        "redis_url": ConfigOption(
            name=["redis", "url"],
            sources=[ConfigSource.ENVIRONMENT, ConfigSource.DEFAULT], # Redis must be set via env var if used
            default=ConfigRequired,
            enforce_type=str,
            enforce_type_coerce=True,
            description="The URL for the Redis instance used by the framework.",
        ),
        "data_dir": ConfigOption(
            name=["filesystem", "data_dir"],
            default="./data",
            enforce_type=str,
            enforce_type_coerce=True,
            description="Root directory for all framework data storage.",
        ),
    }