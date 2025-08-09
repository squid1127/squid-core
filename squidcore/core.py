# * External Packages & Imports
# Discord Packages
import discord
from discord.ext import commands, tasks

# Async Packages for discord & rest apis
import asyncio

# System/OS Packages
import os
from pathlib import Path
from traceback import format_exc

# Simple Hashing
import hashlib

# * Internal Packages & Imports
from .shell import ShellCore, ShellHandler, ShellCommand  # Shell
from .status import RandomStatus  # Random Status
from .files import FileBroker  # File management
from .impersonate import ImpersonateDM, ImpersonateGuild  # Impersonation (Talking as the bot and dm handling)
from .explorer import DiscordExplorer # Discord Explorer
from .downreport import DownReportManager, down_report  # Downreport
from .uptime import UptimeManager  # Uptime
from .memory import Memory  # Memory management (Redis, MongoDB, etc.)
from .perms import PermissionLevel, PermissionsManager, Permissions  # Permissions management

# Logs
import logging
from .log_setup import logger


# * Core
class Bot(commands.Bot):
    """
    Bot class for managing a Discord bot with various functionalities including shell commands,
    database integration, and status management.
    Attributes:
        token (str): The token for the Discord bot.
        name (str): The name of the Discord bot.
        shell_channel (int): The ID of the shell channel.
        shell (ShellCore): The shell core instance for managing shell commands.
        static_status (Status): The static status to be set for the bot.
    Args:
        token (str): The token for the Discord bot.
        name (str): The name of the Discord bot.
        shell_channel (int): The ID of the shell channel.
        data_path (str, optional): The path to the data directory. Defaults to "./config".
        memory (Memory, optional): An instance of the Memory class for managing memory. Defaults to None.
        
    """

    def __init__(
        self,
        token: str,
        name: str,
        shell_channel: int,
        data_path: str = "./config",
        memory: Memory = None,
    ):
        self.token = token
        self.name = name
        self.shell_channel = shell_channel
        self.sync_commands = True

        self.cog_cache = {}

        #* Core Components
        # Shell
        self.shell = ShellCore(self, self.shell_channel, self.name)
        
        # File management
        self.filebroker = FileBroker(self, data_path)
        self.filebroker.init()
        
        # DB
        self.memory = memory
        
        # Permissions
        if self.memory:
            self.permissions = Permissions(self.memory)
        
        # Init bot
        super().__init__(
            command_prefix=f"{self.name.lower()}:",
            intents=discord.Intents.all(),
            case_insensitive=True,
            help_command=None,
        )
        
        logger.info(f"{self.name.title()} bot initialized")
        

    def is_docker(self):
        """Check if the bot is running in a Docker container"""

        cgroup = Path("/proc/self/cgroup")
        return (
            Path("/.dockerenv").is_file()
            or cgroup.is_file()
            and "docker" in cgroup.read_text()
        )
        
    async def load_cogs(self):
        """
        Load all cogs for the bot.
        This method is called when the bot is started.
        It loads all cogs from the 'cogs' directory.
        """
        logger.info(f"Loading cogs for {self.name.title()} bot...")
        
        # Load cogs
        #! Manual for now, can be automated later
        await self.add_cog(ShellHandler(self, self.shell))
        await self.add_cog(ImpersonateDM(self, self.shell))
        await self.add_cog(ImpersonateGuild(self, self.shell))
        await self.add_cog(DiscordExplorer(self))
        await self.add_cog(DownReportManager(self, self.shell))
        await self.add_cog(UptimeManager(self, self.shell))
        
        if self.memory:
            # Load memory management cogs
            await self.add_cog(PermissionsManager(self, self.shell))

        
    async def main(self):
        """
        Main method to run the bot.
        This method is called when the bot is started.
        It sets up the shell and starts the bot.
        
        Initialization order:
        1. Initialize memory management if provided.
        2. Load cogs.
        3. Start the bot.
        """
        logger.info(f"Starting {self.name.title()} bot...")
        
        async with self:
            # Start memory
            if self.memory:
                logger.info("Initializing memory management")
                await self.memory.init()
                logger.info("Memory management initialized")
            else:
                logger.warning("No memory management provided, skipping initialization")
            
            # Load cogs
            await self.load_cogs()
            
            # Run the bot
            await self.start(self.token)
            
    def run(self):
        """
        Run the bot.
        This method is called to start the bot.
        It runs the main method in an asyncio event loop.
        """
        logger.info(f"Running {self.name.title()} bot...")
        
        # Run the main method in an asyncio event loop
        try:
            asyncio.run(self.main())
        except KeyboardInterrupt:
            logger.info(f"{self.name.title()} bot stopped by user")
            down_report(f"{self.name.title()} bot stopped by user")
        except Exception as e:
            logger.error(f"Error occurred while running {self.name.title()} bot: {e}")
            down_report(f"{self.name.title()} bot failed to start\n## Error\n {str(e)}\n## Traceback:\n```\n{format_exc()}\n```")

    async def on_ready(self):
        """On ready message"""
        logger.info(f"{self.user} is ready")

        # Sync application
        if self.sync_commands:
            logger.info("Syncing application commands")
            await self.tree.sync()
            logger.info("Application commands synced")
        else:
            logger.warning("Skipping application command sync")

        # Set static status if provided
        if hasattr(self, "static_status"):
            await self.change_presence(activity=self.static_status())
        else:
            logger.info("No static status provided")
            
    def set_status(
        self,
        random_status: list[discord.Activity] = None,
        static_status: discord.Activity = None,
    ):

        if random_status:
            asyncio.run(self.add_cog(RandomStatus(self, random_status)))
        elif static_status:
            self.static_status = static_status
        else:
            raise ValueError("No status provided")
        