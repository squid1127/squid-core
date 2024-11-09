# * External Packages & Imports
# Discord Packages
import discord
from discord.ext import commands, tasks

# Async Packages for discord & rest apis
import asyncio

# * Internal Packages & Imports
from .shell import ShellCore, ShellHandler, ShellCommand  # Shell
from .db import *  # Database
from .status import RandomStatus, Status  # Random Status
from .files import *  # File management
from .impersonate import *  # Impersonation (Talking as the bot and dm handling)

# * Core
class Bot(commands.Bot):
    """
    Bot class for managing a Discord bot with various functionalities including shell commands,
    database integration, and status management.
    Attributes:
        token (str): The token for the Discord bot.
        name (str): The name of the Discord bot.
        shell_channel (int): The ID of the shell channel.
        has_db (bool): Indicates whether the bot has a database connected.
        shell (ShellCore): The shell core instance for managing shell commands.
        db (DatabaseCore): The database core instance for managing database operations.
        static_status (Status): The static status to be set for the bot.
    Methods:
        __init__(token: str, name: str, shell_channel: int):
            Initializes the bot with the given token, name, and shell channel.
        add_db(postgres_connection: str, postgres_password: str = None, postgres_pool: int = 20):
        set_status(random_status: list[Status] = None, static_status: Status = None):
            Sets the status of the bot, either randomly from a list or a static status.
        run():
            Starts the bot.
        _load_cogs():
            Asynchronously loads the necessary cogs for the bot.
        on_ready():
            Event handler for when the bot is ready.
    """
    
    def __init__(
        self,
        token: str,
        name: str,
        shell_channel: int,
    ):
        self.token = token
        self.name = name
        self.shell_channel = shell_channel
        self.has_db = False
        
        self.cog_cache = {}

        # Shell
        self.shell = ShellCore(self, self.shell_channel, self.name)

        super().__init__(
            command_prefix=f"{self.name.lower()}:",
            intents=discord.Intents.all(),
            case_insensitive=True,
            help_command=None,
        )

        # Load cogs
        print("[Core] Loading cogs...")
        asyncio.run(self._load_cogs())
        print("[Core] Cogs loaded")

        print(f"[Core] {self.name.title()} bot initialized")

    def add_db(
        self,
        postgres_connection: str,
        postgres_password: str = None,
        postgres_pool: int = 20,
    ):
        """
        Adds a database to the core system and initializes the database handler.
        This method sets up a database connection using the provided PostgreSQL connection string
        and attempts to add a database handler cog to the core system.
        Args:
            postgres_connection (str): The connection string for the PostgreSQL database.
            postgres_password (str, optional): The password for the PostgreSQL database. Defaults to None (Specified in the connection string).
            postgres_pool (int, optional): The maximum number of connections to the PostgreSQL database. Defaults to 20.
        Raises:
            Exception: If adding the database handler fails.
        """

        self.has_db = True
        self.db = DatabaseCore(
            self,
            shell=self.shell,
            postgres_connection=postgres_connection,
            postgres_password=postgres_password,
            postgres_pool=postgres_pool,
        )

        # Add the database handler
        try:
            asyncio.run(
                self.add_cog(
                    DatabaseHandler(
                        self,
                        self.db,
                        self.shell,
                    )
                )
            )
        except Exception as e:
            print(f"[Core] Failed to add database handler: {e}")
            
    def set_status(self, random_status: list[Status] = None, static_status: Status = None):
        
        if random_status:
            asyncio.run(self.add_cog(RandomStatus(self, random_status)))
        elif static_status:
            self.static_status = static_status
        else:
            raise ValueError("No status provided")
        

    def run(self):
        """Start the bot"""
        print(f"[Core] Running bot {self.name}")
        super().run(token=self.token)

    async def on_ready(self):
        """On ready message"""
        print(f"[Core] {self.user} is ready")
            
        # Sync application commands
        print("[Core] Syncing application commands")
        await self.tree.sync()
        print("[Core] Application commands synced")

        
        # Set static status if provided
        if hasattr(self, "static_status"):
            await self.change_presence(activity=self.static_status())
        else:
            print("[Core] No static status provided")
            
    async def add_cog(self, cog, *args, **kwargs):
        """Adds a cog to the bot"""
        await super().add_cog(cog, *args, **kwargs)
        self.cog_cache[cog.__class__.__name__] = cog
        
    async def add_cog_unloaded(self, cog, *args, **kwargs):
        """Adds a cog to the bot without loading it, to be manually loaded later"""
        self.cog_cache[cog.__class__.__name__] = cog
        
    async def load_cog(self, cog_name):
        """Loads a cog that was previously added without loading"""
        if cog_name in self.cog_cache:
            raise ValueError(f"Cog {cog_name} not found in cache")
        await self.add_cog(self.cog_cache[cog_name])

    async def _load_cogs(self):
        await self.add_cog(ShellHandler(self, self.shell))
        await self.add_cog(ImpersonateGuild(self, self.shell))
        await self.add_cog(ImpersonateDM(self, self.shell))
