# External imports
from discord.ext import commands, tasks
import discord

# Postgres database
import asyncpg

# Bot Shell
from .shell import ShellCore, ShellCommand, ShellCommandEntry

# Async
import asyncio

# Typing
from typing import Literal

# Managing time
import time
import datetime

# For testing; random string
import random


class DatabaseTable:
    def __init__(self, schema: "DatabaseSchema", name: str):
        self.schema = schema
        self.name = name
        self.columns = []
        self.data = []

        self.random = int(random.random() * 10**10)

        self.last_fetch = None

        self._cache_filter = {}
        self._cache_all = []

        # Setup default fetch interval values
        self.configure()

    def configure(self, fetch_interval_minutes: int = 15):
        """
        Configures the periodic fetch behavior of the database table.
        Args:
            fetch_interval_minutes (int): The interval in minutes for fetching data.
                                          If set to 0, periodic fetching is disabled.
        Sets:
            self.do_periodic_fetch (bool): Indicates whether periodic fetching is enabled.
            self.fetch_interval (int): The interval in minutes for fetching data, if periodic fetching is enabled.
        """

        if fetch_interval_minutes == 0:
            self.do_periodic_fetch = False
        else:
            self.do_periodic_fetch = True
            self.fetch_interval = fetch_interval_minutes

    async def get_data(self):
        """
        Asynchronously retrieves data for the database schema and name.
        This method checks if the data is stale or if it has never been fetched before.
        If the data is stale or has never been fetched, it fetches all data.
        Otherwise, it returns the cached data.

        To force a fetch, use the `fetch_all` method.

        Returns:
            The data for the database schema and name, either fetched or cached.
        """

        print(
            f"[Core.Database] Data requested for {self.schema} -> {self.name} ({self.random})"
        )
        print(f"[Core.Database] Last fetch: {self.last_fetch}")
        if self.last_fetch == None or self.do_periodic_fetch == False:
            print(f"[Core.Database] Fetching all data for {self.schema} -> {self.name}")
            return await self.fetch_all()

        # Check if the data is stale
        if time.time() - self.last_fetch > self.fetch_interval * 60:
            print(f"[Core.Database] Data stale for {self.schema} -> {self.name}")
            return await self.fetch_all()

        print(f"[Core.Database] Using cached data for {self.schema} -> {self.name}")
        return self._cache_all

    async def fetch_all(self):
        """Retrieve all data from the database"""
        result = await self.schema.db.core.query(f"SELECT * FROM {self.schema}.{self}")

        print(
            f"[Core.Database] Data fetched, converting for {self.schema} -> {self.name} ({self.random})"
        )

        self._cache_all = self.schema.db.core.table_to_list_dict(result)
        self.data = self._cache_all  # Data variable for some reason

        self.last_fetch = time.time()
        print(
            f"[Core.Database] Data fetched for {self.schema} -> {self.name} ({self.random})"
        )

        return self._cache_all

    async def get_columns(self):
        """Get all columns in the table"""
        result = await self.schema.db.core.query(
            f"""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = '{self.name}';
            """
        )

        self.columns = self.schema.db.core.table_to_list_dict(result)
        return self.columns

    async def index_all(self):
        """Get all columns"""
        print(f"[Core.Database] Indexing -> {self.schema} -> {self.name}")
        await self.get_columns()
        for column in self.columns:
            print(
                f"[Core.Database] Indexing -> {self.schema} -> {self.name} -> {column.get('column_name')}"
            )
        return self

    async def insert(self, data: dict):
        """Add a row to the table"""
        # COnfigure placeholders
        placeholders = ", ".join(["${}".format(i + 1) for i in range(len(data))])
        columns = ", ".join(data.keys())
        values = list(data.values())

        print(
            f"[Core.Database] Executing query: INSERT INTO {self.schema}.{self.name} ({columns}) VALUES ({placeholders})"
        )
        # Execute query
        await self.schema.db.core.execute(
            f"INSERT INTO {self.schema}.{self.name} ({columns}) VALUES ({placeholders})",
            *values,
        )

        return True

    # Improved Methods
    async def get(self, filters: dict, cache: bool = True):
        """
        Get a row from the table based on filters
        Args:
            filters (dict): The filters to apply to the query
            cache (bool): Whether to use the cache
        Returns:
            The row from the table
        """
        # Configure filter
        filter_string = " AND ".join(
            [f"{key} = '{value}'" for key, value in filters.items()]
        )

        if cache:
            # Check if the data is in the cache
            if filter_string in self._cache_filter:
                if time.time() - self._cache_filter[filter_string]["time"] < 60:
                    print(
                        f"[Core.Database] Using cached data for {self.schema} -> {self.name} ({self.random}) -> {filter_string}"
                    )
                    return self._cache_filter[filter_string]["result"]

                print(
                    f"[Core.Database] Data stale for {self.schema} -> {self.name} ({self.random}) -> {filter_string}"
                )

        print(
            f"[Core.Database] Fetching data for {self.schema} -> {self.name} ({self.random}) -> {filter_string}"
        )

        # Execute query
        result = await self.schema.db.core.query(
            f"SELECT * FROM {self.schema}.{self} WHERE {filter_string}"
        )

        # Convert to list of dictionaries
        data = self.schema.db.core.table_to_list_dict(result)

        # Cache the result
        self._cache_filter[filter_string] = {"result": data, "time": time.time()}
        
        return data

    def clear_cache(self):
        """Clear the cache"""
        self._cache_all = []
        self._cache_filter = {}

        return True

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"DatabaseObject().get_schema('{self.schema}').get_table('{self.name}')"


class DatabaseSchema:
    def __init__(self, db: "DatabaseObject", name: str):
        self.db = db
        self.name = name
        self.tables = {}

    async def get_all_tables(self):
        """
        Retrieves all tables from the database schema specified by `self.name`.
        This method queries the information schema to get the names and schemas of all tables
        in the specified database schema. It then adds any tables that are not already present
        in `self.tables` to the list of tables.
        Returns:
            list: A list of tables present in the database schema in the form of DatabaseTable objects.
        """
        result = self.db.core.table_to_list_dict(
            await self.db.core.query(
                f"""
                SELECT table_name, table_schema
                FROM information_schema.tables
                WHERE table_schema = '{self.name}';
                """
            )
        )

        for table in result:
            if not table["table_name"] in self.tables:
                self._add_table(table["table_name"])

        return self.tables

    def get_table(self, name: str) -> DatabaseTable:
        """Get a table by name"""
        if not name in self.tables:
            self._add_table(name)
        return self.tables[name]

    async def check_exsists(self) -> bool:
        """Check if the schema exists"""
        # List all schemas
        result = self.db.core.table_to_list_dict(
            await self.db.core.query(
                """
            SELECT schema_name
            FROM information_schema.schemata;
            """
            )
        )

        # Check if the schema exists
        for schema in result:
            if schema["schema_name"] == self.name:
                return True
        return False

    async def index_all(self):
        """Get all tables"""
        print(f"[Core.Database] Indexing -> {self.name}")
        await self.get_all_tables()
        for table in self.tables:
            await self.tables[table].index_all()

    def _add_table(self, name: str):
        """Add a table to the schema"""
        table = DatabaseTable(self, name)
        self.tables[name] = table
        return table

    def __str__(self) -> str:
        return self.name


class DatabaseObject:
    def __init__(self, core: "DatabaseCore", ignore_schema: list = []):
        self.core = core
        self.schemas = {}

        self.ignore = ignore_schema

    def get_schema(self, name: str) -> DatabaseSchema:
        """Get a schema by name"""
        if not name in self.schemas:
            self._add_schema(name)
        return self.schemas[name]

    async def get_all_schemas(self):
        """
        Asynchronously retrieves all schemas from the database and adds them to the internal schema list if they are not already present.
        This method performs the following steps:
        1. Executes a query to list all schema names from the information schema.
        2. Converts the query result into a list of dictionaries.
        3. Iterates through the list of schemas and adds each schema to the internal schema list if it is not already included.
        Returns:
            list: A list of all schemas present in the internal schema list in the form of DatabaseSchema objects.
        """

        # List all schemas
        result = self.core.table_to_list_dict(
            await self.core.query(
                """
            SELECT schema_name
            FROM information_schema.schemata;
            """
            )
        )

        # Add all schemas to list
        for schema in result:
            if schema["schema_name"] in self.ignore:
                continue
            if not schema["schema_name"] in self.schemas:
                self._add_schema(schema["schema_name"])
        return self.schemas

    async def index_all(self):
        """Get all schemas and tables"""
        print("[Core.Database] Indexing")
        await self.get_all_schemas()
        for schema in self.schemas:
            await self.schemas[schema].index_all()

        print("[Core.Database] Indexing complete")

    def _add_schema(self, name: str):
        """Add a schema to the database"""
        schema = DatabaseSchema(self, name)
        self.schemas[name] = schema
        return schema


class DatabaseCore:
    def __init__(
        self,
        bot: commands.Bot,
        shell: ShellCore,
        postgres_connection: str,
        postgres_password: str = None,
        postgres_pool: int = 20,
    ):
        self.bot = bot
        self.shell = shell
        self.postgres_connection = postgres_connection
        self.postgres_password = postgres_password
        self.postgres_max_pool = postgres_pool
        self.pool = None
        self.working = False
        self.indexed = False

        ignore = [
            "pg_toast",
            "pg_catalog",
            "information_schema",
            "__msar",
            "msar",
            "mathesar_types",
        ]

        self.data = DatabaseObject(self, ignore_schema=ignore)
        self.discord = DiscordData(self)

    async def start(self) -> bool:
        """
        Continuously attempts to establish a connection to the database and create a connection pool.
        This method will keep trying to connect to the database until successful. Once connected, it will
        check the status of the database and set the `working` attribute accordingly. If the connection
        fails, it will retry after a 10-second delay.
        Returns:
            bool: True if the database connection is successful and the connection pool is created, False otherwise.
        """
        # Continuously attempt to connect to the database
        while True:
            # Attempt to create the connection pool
            reason_failed = "Who knows"
            try:
                await self.create_pool()
            except asyncpg.exceptions.InvalidPasswordError:
                print("[Core.Database] Invalid password")
                reason_failed = "Invalid password"
            except asyncpg.exceptions.InvalidCatalogNameError:
                print("[Core.Database] Invalid catalog name")
                reason_failed = "Invalid catalog name"
            except asyncpg.exceptions.ConnectionRejectionError:
                print("[Core.Database] Connection rejected")
                reason_failed = "Connection rejected"
            except Exception as e:
                print(f"[Core.Database] Failed to connect to database: {e}")
                reason_failed = e
            else:
                print("[Core.Database] Database connection pool created")

                # If the connection pool is created, check the status of the database
                try:
                    status = await self.check_status()
                    if status == 2:
                        print("[Core.Database] Database connection successful")
                        try:
                            post_start = await self.post_start()
                        except Exception as e:
                            reason_failed = e
                        else:
                            if post_start == True:
                                self.working = True
                                return True
                            else:
                                reason_failed = (
                                    post_start if post_start else "Post-startup failed"
                                )

                    elif status == 1:
                        print("[Core.Database] Database connected but no tables found")
                        self.working = True
                        return True
                    else:
                        print("[Core.Database] Database connection failed")
                        reason_failed = "Status check failed"
                except Exception as e:
                    print(f"[Core.Database] Failed to check database status: {e}")
                    reason_failed = e

            # If the connection fails, retry after a 10-second delay
            await self.shell.log(
                f"Failed to connect to database.\nReason: {reason_failed}",
                title="Database Connection Error",
                msg_type="error",
                cog="DatabaseHandler",
            )
            print(
                "[Core.Database] Failed to connect to database, retrying in 10 seconds"
            )
            await asyncio.sleep(10)

    async def post_start(self):
        """Post-startup tasks"""
        # Check if the database is ready
        print("[Core.Database] Processing post-startup tasks")
        await self.discord.setup(trycatch=False)
        print("[Core.Database] Post-startup tasks complete")
        return True

    # * Database Queries & Functions
    # Create connection pool
    async def create_pool(self):
        """
        Creates a connection pool for the database.
        """
        self.pool = await asyncpg.create_pool(
            dsn=self.postgres_connection,
            password=self.postgres_password,
            max_size=self.postgres_max_pool,
        )

    # Basic query function
    async def query(self, query: str, *args):
        """
        Fetches a SQL query from the database and returns the result.
        Note: This fuction should be used to retrieve data from the database, not to modify it.
        Args:
            query (str): The SQL query to be executed.
            *args: Additional arguments to be passed to the query.
        Returns:
            The result of the query execution.
        """

        async with self.pool.acquire() as connection:
            async with connection.transaction():
                return await connection.fetch(query, *args)

    async def execute(self, query: str, *args):
        """
        Executes a given SQL query with the provided arguments.
        Note: This function should be used to modify the database. It (should) not return any data.
        Args:
            query (str): The SQL query to be executed.
            *args: Variable length argument list to be used in the SQL query.
        Returns:
            The result of the executed query.
        """
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                return await connection.execute(query, *args)

    async def check_status(self) -> int:
        """
        Checks the status of the database connection.
        Returns:
            The status of the database connection as an integer:
                0: Not connected
                1: Connected but no tables found
                2: Connected and ready
        """
        try:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    tables = await connection.fetch(
                        """
                            SELECT table_schema,table_name 
                            FROM information_schema.tables 
                            ORDER BY table_schema,table_name;
                        """
                    )
            if tables:
                return 2
            return 1
        except Exception as e:
            return 0

    async def wait_until_ready(self):
        """
        Waits until the database is ready to be used.
        """
        while (not self.working) or (not self.indexed):
            await asyncio.sleep(1)
        return

    # Tables
    def table_to_list_dict(self, data: list) -> list:
        """
        Converts a list of asyncpg.Record objects to a list of dictionaries.
        Args:
            data (list): The data to be converted.
        Returns:
            The converted data as a list of dictionaries.
        """
        return [dict(row) for row in data]

    def table_to_dict(self, data: list) -> dict:
        """
        Converts a list of asyncpg.Record objects to a dictionary.
        Args:
            data (list): The data to be converted.
        Returns:
            The converted data as a dictionary.
        """
        return {row[0]: row[1] for row in data}

    async def table_read_all(self, table: str, list: bool = True):
        """
        Reads all the data from a table.
        Args:
            table (str): The table to read from.
        Returns:
            The data from the table. (list of dict)
        """
        data = await self.query(f"SELECT * FROM {table}")

        if list:
            return self.table_to_list_dict(data)
        return self.table_to_dict(data)


class DiscordData:
    """Specialized class for managing Discord data, such as servers, channels, and members"""

    def __init__(self, db: DatabaseCore):
        self.db = db

        self.schema_object = self.db.data.get_schema(self.SCHEMA)
        self.guild_table_object = self.schema_object.get_table(self.GUILD_TABLE)
        self.channel_table_object = self.schema_object.get_table(self.CHANNEL_TABLE)
        self.member_table_object = self.schema_object.get_table(self.MEMBER_TABLE)

        self._guilds = {}
        self._channels = {}
        self._members = {}

    SCHEMA = "server_data"
    GUILD_TABLE = "guilds"
    CHANNEL_TABLE = "channels"
    MEMBER_TABLE = "members"

    POSTGRES = f"""
    CREATE SCHEMA IF NOT EXISTS {SCHEMA};
    CREATE TABLE IF NOT EXISTS {SCHEMA}.{GUILD_TABLE} (
        id BIGINT PRIMARY KEY NOT NULL,
        name TEXT NOT NULL,
        owner_id BIGINT,
        locked BOOLEAN DEFAULT FALSE,
        options JSON,
        info JSON
    );
    CREATE TABLE IF NOT EXISTS {SCHEMA}.{CHANNEL_TABLE} (
        id BIGINT PRIMARY KEY NOT NULL,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        guild_id BIGINT REFERENCES {SCHEMA}.{GUILD_TABLE}(id),
        options JSON,
        info JSON
    );
    CREATE TABLE IF NOT EXISTS {SCHEMA}.{MEMBER_TABLE} (
        id BIGINT PRIMARY KEY NOT NULL,
        username TEXT NOT NULL,
        discriminator TEXT,
        guilds JSON,
        options JSON,
        info JSON
    );
    """

    async def setup(self, trycatch: bool = True):
        print("[Core.Database.ServerData] Setting up server data tables")
        if trycatch:
            try:
                await self.db.execute(self.POSTGRES)
            except Exception as e:
                print(
                    f"[Core.Database.ServerData] Error setting up server data tables: {e}"
                )
                return e
            return True
        else:
            await self.db.execute(self.POSTGRES)
            return True

    async def get_guild(self, id: int, create: bool = True) -> 'DBDiscordGuild':
        """
        Asynchronously retrieves a guild by its ID.
        If the guild is already cached in the internal dictionary, it returns the cached guild.
        Otherwise, it fetches the guild data from the database, creates a new DBDiscordGuild object,
        caches it, and then returns it.
        Args:
            id (int): The ID of the guild to retrieve.
        Returns:
            DBDiscordGuild or None: The guild object if found, otherwise None.
        """

        if id in self._guilds:
            return self._guilds[id]

        if not create:
            data = await self.guild_table_object.get({"id": id})
            if not data:
                return None

        guild = DBDiscordGuild(self.db, id, self.guild_table_object)
        await guild.sync()

        self._guilds[id] = guild
        return guild


class DatabaseHandler(commands.Cog):
    def __init__(self, bot: commands.Bot, core: DatabaseCore, shell: ShellCore):
        self.core = core
        self.bot = bot
        self.shell = shell

        # Add shell commands
        self.shell.add_command(
            command="db",
            cog="DatabaseHandler",
            description="Database commands",
        )

        print("[Core.Database] Database enabled")

    # Start database connection
    @commands.Cog.listener()
    async def on_ready(self):
        print("[Core.Database] Connecting to database")

        success = await self.core.start()
        if success != True:
            if success == False:
                await self.shell.log(
                    f"Failed to connect to database: {self.core.postgres_connection}",
                    title="Database Connection Error",
                    msg_type="error",
                    cog="DatabaseHandler",
                )
                return
            else:
                await self.shell.log(
                    f"Failed to connect to database: {success}",
                    title="Database Connection Error",
                    msg_type="error",
                    cog="DatabaseHandler",
                )
                return

        print("[Core.Database] Database connected; starting indexing task")
        self.periodic_index.start()
        print("[Core.Database] Database indexing task started")

    @tasks.loop(hours=1)
    async def periodic_index(self):
        print("[Core.Database] Periodic indexing")
        await self.core.data.index_all()
        self.core.indexed = True

    # * Discord Data -- Automatic Registration
    # General registration
    async def register(
        self,
        guild: discord.Guild = None,
        user: discord.User = None,
        channel: discord.TextChannel = None,
    ):
        """Register a user, guild, or member to the database"""
        if guild:
            guild_entry = await self.core.discord.get_guild(guild.id, create=True)

        # try:
        #     guild_entry = await self.core.discord.get_guild(guild.id, create=True)
        # except Exception as e:
        #     print(f"[Core.Database] Error registering guild {guild.name} ({guild.id}): {e}")
        #     await self.shell.log(
        #         f"Error registering guild {guild.name} ({guild.id}): {e}",
        #         title="Database Registration Error",
        #         msg_type="error",
        #         cog="DatabaseHandler",
        #     )

        if user:
            pass
        if channel:
            pass

    # Listen to join events
    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        await self.register(guild=guild)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        await self.register(member=member, guild=member.guild)

    @commands.Cog.listener()
    async def on_message(self, message):
        await self.register(
            user=message.author, guild=message.guild, channel=message.channel
        )

    # Cog Status
    async def cog_status(self) -> str:
        """Check the status of the database connection by checking the schema"""
        print("[Core.Database] Checking database status")

        # Connection status (Check schema)
        status = await self.core.check_status()
        if status == 2:
            return "Database connection successful"
        elif status == 1:
            return "Connected but no tables found"
        else:
            return "Database connection failed"

    async def shell_callback(self, command: ShellCommand):
        if command.name == "db":
            subcommand = (
                command.query.split(" ")[0] if " " in command.query else command.query
            )
            if subcommand == "status":
                # Check the status of the database
                status = await self.cog_status()
                await self.shell.log(
                    status,
                    title="Database Status",
                    msg_type="info",
                    cog="DatabaseHandler",
                )

            if subcommand == "get":
                # Get data from a table
                table = command.query.split(" ")[1]
                try:
                    params = command.params_to_dict(
                        " ".join(command.query.split(" ")[2:])
                    )
                except:
                    params = {}

                dict_mode = params.get("--dict", False) or params.get("-d", False)
                data = await self.core.table_read_all(table, not dict_mode)

                await command.log(
                    f"```python\n{data}\n```",
                    title=f"Table {table}",
                    msg_type="info",
                )
            elif subcommand == "test":
                await self.test_script(command)
            else:
                # Do help command
                fields = [
                    {
                        "name": "db status",
                        "value": "Check the status of the database",
                    },
                    {
                        "name": "db get <table> [--dict]",
                        "value": "Get data from a table",
                    },
                ]
                await command.log(
                    "Here are the available database commands:",
                    fields=fields,
                    title="Database Commands",
                    msg_type="info",
                )

        else:
            await command.log(
                preset="CogNoCommandError",
            )

    # async def test_script(self, command: ShellCommand):
    #     # Test script
    #     try:
    #         await command.raw("Testing script")

    #         public = DatabaseSchema(self.core, "public")

    #         if not await public.check_exsists():
    #             await command.raw("Schema does not exist")
    #             return
    #         await command.raw("Schema exists")

    #         tables = await public.get_tables()
    #         await command.raw(f"Tables:\n```python\n{tables}\n```")
    #     except Exception as e:
    #         await command.raw(f"Error:\n```python\n{e}\n```")


# Discord data (servers, channels, members)
class DBDiscordGuild:
    """Represents a Discord guild in the database, including any configuration and associated data"""

    def __init__(self, db: DatabaseCore, id: int, table: DatabaseTable):
        self.db = db
        self.id = id
        self.table = table

        self.name = None
        self.discord = None

    async def update_discord(self):
        """Update the data from Discord"""
        # Check if the guild exists
        guild = self.db.bot.get_guild(self.id)
        if not guild:
            return False

        # Update the guild name
        self.name = guild.name
        self.discord = guild

        self.locked = None
        self.options = None
        self.info = None

        return True

    async def sync(self):
        """Sync the guild data with the database and Discord"""
        try:
            await self.update_discord()
        except:
            print(
                f"[Core.Database.ServerData] Warning: Failed to fetch guild info for {self.id}"
            )

        # Check if the guild exists
        if not self.db.working:
            raise Exception("Database not ready")

        data = await self.table.get({"id": self.id})
        print(
            f"[Core.Database.ServerData] Fetched guild data for {self.name} ({self.id}) -> {data}"
        )
        
        print(f"[Core.Database.ServerData] Fetched guild data for {self.name} ({self.id}) -> {data}")
        
        
        if data is None or len(data) == 0:
            print(
                f"[Core.Database.ServerData] Guild {self.name} ({self.id}) not found in database; registering"
            )
            if self.name == None:
                raise Exception("Unable to register guild; could not fetch guild data")
            # Add the guild to the database
            await self.table.insert(
                {
                    "id": self.id,
                    "name": self.name,
                    "owner_id": self.discord.owner_id if self.discord else None,
                }
            )

            print(f"[Core.Database.ServerData] Added guild {self.name} ({self.id})")
            
            return True

        # Update the guild data
        if self.locked is None:
            self.locked = data[0]["locked"]
        elif self.locked != data[0]["locked"]:
            print(
                f"[Core.Database.ServerData] Warning: Guild {self.name} ({self.id}) locked status mismatch"
            )
        if self.options is None:
            self.options = data[0]["options"]
        elif self.options != data[0]["options"]:
            print(
                f"[Core.Database.ServerData] Warning: Guild {self.name} ({self.id}) options mismatch"
            )
        if self.info is None:
            self.info = data[0]["info"]
        elif self.info != data[0]["info"]:
            print(
                f"[Core.Database.ServerData] Warning: Guild {self.name} ({self.id}) info mismatch"
            )

        return True
