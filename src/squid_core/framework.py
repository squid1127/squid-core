"""Core framework class"""

import asyncio, signal
import contextlib
from pathlib import Path

from .bot import Bot
from .config import ConfigManager
from .logging import LoggerManager, get_framework_logger
from .loader import PluginManager
from .fw_settings import FWSettings

class Framework:
    """
    A core framework class for bot and utility management.
    
    Features:
    - Graceful shutdown handling for SIGTERM and SIGINT (Docker/Kubernetes compatible)
    - Plugin system with dynamic loading and unloading
    - Built-in database, Redis, CLI, event bus, and permissions systems
    - Comprehensive logging and error handling
    - Async-first design with synchronous convenience methods
    """

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
        self.path: Path = Path(settings.data_dir) if settings.data_dir else Path("./data")

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
    async def create_async(cls, manifest: Path = Path("framework.toml"), env_file: Path | None = None) -> "Framework":
        """Asynchronous factory method to create a Framework instance."""

        # Init Config
        config = ConfigManager(global_manifest=manifest, env_file=env_file)

        # Fetch framework settings
        settings: FWSettings = await FWSettings.resolve(config, None)
        return cls(config=config, settings=settings)

    @classmethod
    def create(
        cls, manifest: Path = Path("framework.toml"), env_file: Path | None = None
    ) -> "Framework":
        """
        Synchronous factory method to create a Framework instance. Uses asyncio.run internally.
        Use `create_async` for fully asynchronous initialization.

        Args:
            manifest (Path): Path to the framework manifest file. Defaults to "framework.toml".
            env_file (Path | None): Path to the environment file. Defaults to None.
        """
        return asyncio.run(cls.create_async(manifest=manifest, env_file=env_file))

    async def start(self):
        """
        Asynchronous start method to launch the framework.
        
        Handles SIGTERM and SIGINT signals for graceful shutdown (Docker/Kubernetes compatible).
        The method will run until a signal is received or the bot disconnects.
        """
        self.logger.info("Starting framework...")

        # Set up signal handlers for graceful shutdown
        loop = asyncio.get_running_loop()
        shutdown_event = asyncio.Event()
        
        def signal_handler(sig):
            """Handle shutdown signals (SIGTERM, SIGINT)."""
            sig_name = signal.Signals(sig).name
            self.logger.info(f"Received {sig_name} signal. Initiating graceful shutdown...")
            shutdown_event.set()
        
        # Register signal handlers (important for Docker/Kubernetes)
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))

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
            
            # Run bot in a task so we can handle shutdown signals
            bot_task = asyncio.create_task(self.bot.start(token=self.settings.bot_token))
            shutdown_task = asyncio.create_task(shutdown_event.wait())
            
            # Wait for either bot to finish or shutdown signal
            done, pending = await asyncio.wait(
                [bot_task, shutdown_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel pending tasks
            for task in pending:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            
            self.logger.info("Shutting down...")
        except Exception as e:
            self.logger.error(f"Error during framework execution: {e}", exc_info=True)
            raise
        finally:
            await self.teardown()

    async def teardown(self):
        """Asynchronous teardown method to clean up resources."""
        self.logger.info("Tearing down framework...")

        try:
            # Dispatch pre-shutdown event
            await self.event_bus.dispatch("framework_pre_shutdown")
            
            # Unload all plugins first
            await self.plugins.unload_all()

            # Close bot connection gracefully
            if not self.bot.is_closed():
                await self.bot.close()

            # Close core components
            await self.close_core_components()

            self.logger.info("Framework shut down successfully.")
        except Exception as e:
            self.logger.error(f"Error during teardown: {e}", exc_info=True)
        finally:
            # Shutdown logging last
            self.logger_manager.shutdown()

    def run(self):
        """
        Synchronous entry point to launch the framework.
        
        This is the main method to call from your application's entry point.
        Handles signals gracefully and ensures proper cleanup on exit.
        Compatible with Docker, Kubernetes, and standard process managers.
        """
        try:
            asyncio.run(self.start())
        except KeyboardInterrupt:
            # This shouldn't normally be reached due to signal handlers, but kept as fallback
            self.logger.info("Keyboard interrupt received")
        except Exception as e:
            self.logger.error(f"Fatal error: {e}", exc_info=True)
            raise

    # "Core components" initialization methods
    def init_core_components(self):
        """Initialize core components like database, CLI, etc."""
        from .components.db import Database
        from .components.redis_comp import Redis
        from .components.cli import CLIManager
        from .components.events import EventBus
        from .components.perms import Perms

        self.redis: Redis = Redis(
            url=self.settings.redis_url,
        )

        self.db: Database = Database(
            url=self.settings.database_url,
            aerich=self.settings.use_aerich
        )
        self.db.register_model("squid_core.models")  # Register core models

        self.cli: CLIManager = CLIManager(
            bot=self.bot,
            allowed_channel_ids=self.settings.cli_channels or [],
            cli_prefix=self.settings.cli_prefix,
        )

        self.event_bus: EventBus = EventBus()
        self.perms: Perms = Perms(db=self.db, redis=self.redis)

    async def async_init_core_components(self):
        """Asynchronously initialize core components like database, CLI, etc."""
        self.logger.info("Initializing core components...")
        await self.config.attach_db(self.db)  # Bind config models
        await self.db.init()
        await self.redis.connect()
        await self.event_bus.dispatch("framework_core_initialized", framework=self)

    async def close_core_components(self):
        """Asynchronously close core components like database, CLI, etc."""
        # Close each component independently to prevent one failure from blocking others
        close_tasks = []
        
        if self.db:
            close_tasks.append(("Database", self.db.close()))
        if self.redis:
            close_tasks.append(("Redis", self.redis.disconnect()))
        
        # Execute all close operations
        for name, task in close_tasks:
            try:
                await task
                self.logger.debug(f"{name} closed successfully")
            except Exception as e:
                self.logger.error(f"Error closing {name}: {e}", exc_info=True)
        
        # Dispatch termination event
        try:
            await self.event_bus.dispatch("framework_core_terminated", framework=self)
        except Exception as e:
            self.logger.error(f"Error dispatching termination event: {e}", exc_info=True)