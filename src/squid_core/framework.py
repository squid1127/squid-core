"""Core framework class"""

import asyncio
from pathlib import Path

from .bot import Bot
from .config import ConfigManager
from .logging import LoggerManager, get_framework_logger
from .loader import PluginManager
from .fw_settings import FWSettings


class Framework:
    """A core framework class for bot and utility management."""

    def __init__(self, config: ConfigManager, settings: FWSettings):
        """
        Initialize the Framework. Use `create` or `create_async` factory methods instead.

        Args:
            config (ConfigManager): Configuration manager instance for the framework.
            settings (FWSettings): Resolved framework settings. Should be loaded before initialization.
        """
        self.config: ConfigManager = config
        self.settings: FWSettings = (
            settings  # Must be loaded before initialization, asynchronously
        )

        # Initialize logging
        log_file: Path = (
            Path(self.settings.log_file) if self.settings.log_file else None
        )
        self.logger_manager: LoggerManager = LoggerManager(
            log_level=self.settings.log_level,
            debug_mode=self.settings.debug_mode,
            log_file=log_file,
            console_output=self.settings.log_to_console,
        )
        self.logger = get_framework_logger("core")
        self.logger.info("Hi!")

        # Initialize services and bot
        self.bot: Bot = Bot(
            command_prefix=self.settings.bot_cmd_prefix,
            intents=self.settings.bot_intents,
        )
        self.init_core_components()

        # Initialize plugin manager (pass self reference)
        self.plugins: PluginManager = PluginManager(
            framework=self,
            core_base_package=self.settings.plugins_package_core,
            custom_packages=self.settings.plugins_packages,
        )

        self.logger.info("Framework initialized")

    @classmethod
    async def create_async(cls, manifest: Path = Path("framework.toml")) -> "Framework":
        """Asynchronous factory method to create a Framework instance."""

        # Init Config
        config = ConfigManager(global_manifest=manifest)

        # Fetch framework settings
        settings: FWSettings = await FWSettings.resolve(config, None)
        return cls(config=config, settings=settings)

    @classmethod
    def create(cls, manifest: Path = Path("framework.toml")) -> "Framework":
        """
        Synchronous factory method to create a Framework instance. Uses asyncio.run internally.
        Use `create_async` for fully asynchronous initialization.
        
        Args:
            manifest (Path): Path to the framework manifest file. Defaults to "framework.toml".
        """
        return asyncio.run(cls.create_async(manifest=manifest))

    async def start(self):
        """Asynchronous start method to launch the framework."""
        self.logger.info("Starting framework...")

        # Initialize and load plugins + core components
        plugins_to_load = self.settings.plugins or ["core:*"]
        await self.plugins.find_all()
        await self.plugins.preload(
            plugins_to_load
        )  # Preload to import db models before core components init
        await self.async_init_core_components()
        await self.plugins.load(plugins_to_load)  # Regular load to call load methods

        # Start the bot
        try:
            self.logger.info(f"Starting {self.settings.friendly_name}...")
            await self.event_bus.dispatch("framework_bot_init")
            await self.bot.start(token=self.settings.bot_token)
            self.logger.info("Received exit signal. Shutting down...")
        finally:
            await self.teardown()

    async def teardown(self):
        """Asynchronous teardown method to clean up resources."""
        self.logger.info("Tearing down framework...")

        # Unload all plugins first
        await self.plugins.unload_all()

        # Close bot connection
        await self.bot.close()

        # Close core components
        await self.close_core_components()

        # Shutdown logging
        self.logger_manager.shutdown()
        self.logger.info("Framework shut down successfully.")

    def run(self):
        """Synchronous start method to launch the framework."""
        try:
            asyncio.run(self.start())
        except KeyboardInterrupt:
            self.logger.warning("Keyboard interrupt received")

    # "Core components" initialization methods
    def init_core_components(self):
        """Initialize core components like database, CLI, etc."""
        from .components.db import Database
        from .components.cli import CLIManager
        from .components.events import EventBus

        self.db: Database = Database(
            url=self.settings.database_url,
        )

        self.cli: CLIManager = CLIManager(
            bot=self.bot,
            allowed_channel_ids=self.settings.cli_channels or [],
            cli_prefix=self.settings.cli_prefix,
        )

        self.event_bus: EventBus = EventBus()

    async def async_init_core_components(self):
        """Asynchronously initialize core components like database, CLI, etc."""
        self.logger.info("Initializing core components...")
        await self.config.attach_db(self.db)  # Attach DB to config manager
        await self.db.init()
        await self.event_bus.dispatch("framework_core_initialized", framework=self)

    async def close_core_components(self):
        """Asynchronously close core components like database, CLI, etc."""
        await self.db.close()
        await self.event_bus.dispatch("framework_core_terminated", framework=self)
