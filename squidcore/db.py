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

# Dict output
import json

# Logging
import logging

logger = logging.getLogger("core.db")

class DatabaseItem:
    """Represents an item in a database table, useful for fetching and modifying data"""

    def __init__(self, table: "DatabaseTable", refrence_key: str, refrence_value: str):
        self.table = table
        self.data = None
        self.refrence_key = refrence_key
        self.refrence_value = refrence_value

    async def update(self, data: dict):
        """Update the item"""
        if not await self.check_exsists():
            logger.info("Item does not exist -- Creating new item")
            await self.table.insert(data)
            logger.info("Item created")
            return await self.fetch_data()

        logger.info("Item exists -- Updating item")
        await self.table.update(data, {self.refrence_key: self.refrence_value})
        logger.info("Item updated")
        return await self.fetch_data()

    async def delete(self):
        """Delete the item"""
        try:
            self.fetch_data()
        except ValueError:
            raise ValueError("Item does not exist")

        await self.table.delete({self.refrence_key: self.refrence_value})
        return True

    async def fetch_data(self):
        """Fetch the data for the item"""
        logger.info(
            f"Fetching data for {self.table} -> {self.refrence_key} -> {self.refrence_value}"
        )
        result = await self.table.fetch({self.refrence_key: self.refrence_value})

        if len(result) > 1:
            raise Exception("Multiple items found for specified refrence key")
        if not result or len(result) == 0:
            raise ValueError("Item does not exist")

        self.data = result[0]

        return self.data

    async def check_exsists(self) -> bool:
        """Check if the item exists"""
        result = await self.table.fetch({self.refrence_key: self.refrence_value})

        return len(result) == 1

    def __str__(self) -> str:
        return f"Item {self.refrence_key} -> {self.refrence_value} in {self.table}"

    def __repr__(self) -> str:
        return f"DatabaseItem({self.table}, {self.refrence_key}, {self.refrence_value})"


class DatabaseTable:
    """(v2) Represents a table in a database schema, including its columns"""

    def __init__(self, schema: "DatabaseSchema", name: str):
        self.schema = schema
        self.name = name
        self.columns = []

        self.random = int(random.random() * 10**10)

    # * Core Functions | Basic Queries

    async def fetch(self, filters: dict = None):
        """Fetch data from the table"""
        if filters:
            # Convert filter dictionary to SQL string (with placeholders)
            filter_string = " AND ".join(
                [f"{key} = '{value}'" for key, value in filters.items()]
            )

            # Execute query
            result = await self.schema.db.core.query(
                f"SELECT * FROM {self.schema}.{self} WHERE {filter_string}"
            )

            # Convert to list of dictionaries
            data = self.schema.db.core.table_to_list_dict(result)
            return data

        # Fetch all data
        result = await self.schema.db.core.query(f"SELECT * FROM {self.schema}.{self}")
        data = self.schema.db.core.table_to_list_dict(result)
        return data

    async def insert(self, data: dict):
        """Insert data into the table"""
        # Configure placeholders
        placeholders = ", ".join(["${}".format(i + 1) for i in range(len(data))])
        columns = ", ".join(data.keys())
        values = list(data.values())

        # Execute query
        await self.schema.db.core.execute(
            f"INSERT INTO {self.schema}.{self} ({columns}) VALUES ({placeholders})",
            *values,
        )

        return True

    async def update(self, data: dict, filters: dict):
        """Update data in the table"""
        # Configure placeholders
        set_placeholders = ", ".join(
            [f"{key} = ${i+1}" for i, key in enumerate(data.keys())]
        )
        filter_placeholders = " AND ".join(
            [f"{key} = ${i+1+len(data)}" for i, key in enumerate(filters.keys())]
        )
        values = list(data.values()) + list(filters.values())

        # Execute query
        await self.schema.db.core.execute(
            f"UPDATE {self.schema}.{self} SET {set_placeholders} WHERE {filter_placeholders}",
            *values,
        )

        return True

    async def delete(self, filters: dict):
        """Remove data from the table"""
        # Configure filter
        filter_string = " AND ".join(
            [f"{key} = '{value}'" for key, value in filters.items()]
        )

        # Execute query
        await self.schema.db.core.execute(
            f"DELETE FROM {self.schema}.{self} WHERE {filter_string}"
        )

        return True

    def __str__(self) -> str:
        return self.name

    # * Indexing

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
        """Subcommand of index all"""
        logger.debug(f"Indexing -> {self.schema} -> {self.name}")
        await self.get_columns()
        for column in self.columns:
                logger.debug(
                    f"Indexing -> {self.schema} -> {self.name} -> {column.get('column_name')}"
                )
            

        return self

    # * Working with Items
    async def get_item(self, value: str, refrence_key: str = "id") -> DatabaseItem:
        """Get an item by a refrence key. This instance will not check if the item exists or fetch data"""
        return DatabaseItem(self, refrence_key, value)

    async def get_items(self, filters: dict, refrence_key: str = "id") -> list:
        """Get a list of items based on filters"""
        data = await self.fetch(filters)
        items = []

        for item in data:
            items.append(DatabaseItem(self, refrence_key, item.get(refrence_key)))

        return items


class DatabaseTableV1:
    """Represents a table in a database schema, including its columns"""

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

        logger.info(
            f"Data requested for {self.schema} -> {self.name} ({self.random})"
        )
        logger.info(f"Last fetch: {self.last_fetch}")
        if self.last_fetch == None or self.do_periodic_fetch == False:
            logger.info(f"Fetching all data for {self.schema} -> {self.name}")
            return await self.fetch_all()

        # Check if the data is stale
        if time.time() - self.last_fetch > self.fetch_interval * 60:
            logger.info(f"Data stale for {self.schema} -> {self.name}")
            return await self.fetch_all()

        logger.info(f"Using cached data for {self.schema} -> {self.name}")
        return self._cache_all

    async def fetch_all(self):
        """Retrieve all data from the database"""
        result = await self.schema.db.core.query(f"SELECT * FROM {self.schema}.{self}")

        logger.info(
            f"Data fetched, converting for {self.schema} -> {self.name} ({self.random})"
        )

        self._cache_all = self.schema.db.core.table_to_list_dict(result)
        self.data = self._cache_all  # Data variable for some reason

        self.last_fetch = time.time()
        logger.info(
            f"Data fetched for {self.schema} -> {self.name} ({self.random})"
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
        logger.debug(f"Indexing -> {self.schema} -> {self.name}")
        await self.get_columns()
        for column in self.columns:
                logger.debug(
                    f"Indexing -> {self.schema} -> {self.name} -> {column.get('column_name')}"
                )
        return self

    async def insert(self, data: dict):
        """Add a row to the table"""
        # COnfigure placeholders
        placeholders = ", ".join(["${}".format(i + 1) for i in range(len(data))])
        columns = ", ".join(data.keys())
        values = list(data.values())
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
                    logger.info(
                        f"Using cached data for {self.schema} -> {self.name} ({self.random}) -> {filter_string}"
                    )
                    return self._cache_filter[filter_string]["result"]

                logger.info(
                    f"Data stale for {self.schema} -> {self.name} ({self.random}) -> {filter_string}"
                )

        logger.info(
            f"Fetching data for {self.schema} -> {self.name} ({self.random}) -> {filter_string}"
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
    """Represents a database schema, including its tables"""

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
        logger.debug(f"Indexing -> {self.name}")
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
    """Represents a database, including its schemas"""

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
        logger.info("Indexing")
        await self.get_all_schemas()
        for schema in self.schemas:
            await self.schemas[schema].index_all()

        logger.info("Indexing complete")

    def _add_schema(self, name: str):
        """Add a schema to the database"""
        schema = DatabaseSchema(self, name)
        self.schemas[name] = schema
        return schema


class DatabaseCore:
    """
    Core database handler for the bot, including database connection and data management.
    
    Args:
        bot (Bot): The bot object.
        shell (ShellCore): The shell object.
        postgres_connection (str): The connection string for the PostgreSQL database.
        postgres_password (str, optional): The password for the PostgreSQL database. (Optional if specified in the connection string)
        postgres_pool (int, optional): The maximum number of connections to the PostgreSQL database. Defaults to 20.
    """

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
                logger.error("Invalid password")
                reason_failed = "Invalid password"
            except asyncpg.exceptions.InvalidCatalogNameError:
                logger.error("Invalid catalog name")
                reason_failed = "Invalid catalog name"
            except asyncpg.exceptions.ConnectionRejectionError:
                logger.error("Connection rejected")
                reason_failed = "Connection rejected"
            except Exception as e:
                logger.error(f"Failed to connect to database: {e}")
                reason_failed = e
            else:
                logger.info("Database connection pool created")

                # If the connection pool is created, check the status of the database
                try:
                    status = await self.check_status()
                    if status == 2:
                        logger.info("Database connection successful")
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
                        logger.warning("Database connected but no tables found")
                        self.working = True
                        return True
                    else:
                        logger.error("Database connection failed")
                        reason_failed = "Status check failed"
                except Exception as e:
                    logger.error(f"Failed to check database status: {e}")
                    reason_failed = e

            # If the connection fails, retry after a 10-second delay
            await self.shell.log(
                f"Failed to connect to database.\nReason: {reason_failed}",
                title="Database Connection Error",
                msg_type="error",
                cog="DatabaseHandler",
            )
            logger.error(
                "Failed to connect to database, retrying in 10 seconds"
            )
            await asyncio.sleep(10)

    async def post_start(self):
        """Post-startup tasks"""
        # Check if the database is ready
        logger.info("Processing post-startup tasks")
        await self.discord.setup(trycatch=False)
        logger.info("Post-startup tasks complete")
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


class DiscordEntry(DatabaseItem):
    """
    Represents a Discord entity in the database, including any configuration and associated data (e.g. guild, channel, member)

    Attributes:
        db (DatabaseCore): The database core object.
        id (int): The ID of the entity.
        table (DatabaseTable): The table object associated with the entity.
        type (str): The type of entity (guild, channel, member).
        name (str): The name of the entity.
        discord (discord.Object): The Discord object associated with the entity.
    """

    def __init__(
        self,
        # Database Attributes
        db: DatabaseCore,
        table: DatabaseTable,
        # Discord Attributes
        id: int,
        type: Literal["guild", "channel", "member"],
        parent_id: int = None,
    ):
        self.db_core = db
        self.id = id
        self.table = table
        self.db_data = DatabaseItem(table, "id", id)
        self.type = type

        self.parent = None
        self.discord = None

        if type == "channel":
            self.parent_id = parent_id
            if not self.parent_id:
                raise Exception("Channel entry must have a parent ID (guild ID)")

    async def pull_discord(self):
        """Fetch the data from Discord"""
        if self.type == "guild":
            self.discord = self.db_core.bot.get_guild(self.id)

        elif self.type == "channel":
            self.parent = self.db_core.bot.get_guild(self.parent_id)
            if not self.parent:
                return None
            self.discord = self.parent.get_channel(self.id)

        elif self.type == "member":
            self.discord = self.db_core.bot.get_user(self.id)

        if self.discord:
            self.name = self.discord.name

        return self.discord

    async def pull_db(self):
        """Fetch the data from the database"""
        return await self.db_data.fetch_data()

    async def push_db(self, data: dict):
        """Push data to the database"""
        return await self.db_data.update(data)

    async def discord_to_db(self):
        """Sync the Discord data with the database"""
        await self.pull_discord()
        data = {}

        data_exists = await self.db_data.check_exsists()

        if self.type == "guild":
            if not data_exists:
                data["id"] = self.id

            data["name"] = self.discord.name
            data["owner_id"] = self.discord.owner_id
        elif self.type == "channel":
            if not data_exists:
                data["id"] = self.id
                data["guild_id"] = self.parent_id

            data["name"] = self.discord.name
            data["type"] = str(self.discord.__class__)
        elif self.type == "member":
            if not data_exists:
                data["id"] = self.id
            data["username"] = self.discord.name
            data["discriminator"] = self.discord.discriminator

            # Guilds
            guilds = self.discord.mutual_guilds
            guild_list = [guild.id for guild in guilds]

            # Convert to JSON
            data["guilds"] = json.dumps(guild_list)

        logger.info(f"Syncing {self.type} {self.id} -> {data}")
        await self.push_db(data)


class DiscordData:
    """Specialized class for managing Discord data, such as servers, channels, and members"""

    def __init__(self, db: DatabaseCore):
        self.db = db

        self.schema_object = self.db.data.get_schema(self.SCHEMA)
        self.guild_table_object = self.schema_object.get_table(self.GUILD_TABLE)
        self.channel_table_object = self.schema_object.get_table(self.CHANNEL_TABLE)
        self.member_table_object = self.schema_object.get_table(self.MEMBER_TABLE)

        self.interactive_state = {
            "page": "main",
            "subpage": None,
        }

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
        logger.info("Setting up server data tables")
        if trycatch:
            try:
                await self.db.execute(self.POSTGRES)
            except Exception as e:
                logger.error(
                    f"Error setting up server data tables: {e}"
                )
                return e
            return True
        else:
            await self.db.execute(self.POSTGRES)
            return True

    def get_entry(
        self,
        id: int = None,
        type: Literal["guild", "channel", "member"] = None,
        parent_id: int = None,
        obj=None,
    ):
        """Get a Discord entry by ID or object"""
        if obj:
            # logger.info(f"Debug -> Object class: {obj.__class__}")
            if isinstance(obj, discord.Guild):
                return DiscordEntry(
                    db=self.db,
                    table=self.guild_table_object,
                    id=obj.id,
                    type="guild",
                )
            elif isinstance(obj, discord.TextChannel):
                return DiscordEntry(
                    db=self.db,
                    table=self.channel_table_object,
                    id=obj.id,
                    type="channel",
                    parent_id=obj.guild.id,
                )
            elif isinstance(obj, discord.User) or isinstance(obj, discord.Member):
                return DiscordEntry(
                    db=self.db,
                    table=self.member_table_object,
                    id=obj.id,
                    type="member",
                )
            else:
                return None

        if type == "guild":
            return DiscordEntry(
                db=self.db,
                table=self.guild_table_object,
                id=id,
                type="guild",
            )
        elif type == "channel":
            return DiscordEntry(
                db=self.db,
                table=self.channel_table_object,
                id=id,
                type="channel",
                parent_id=parent_id,
            )
        elif type == "member":
            return DiscordEntry(
                db=self.db,
                table=self.member_table_object,
                id=id,
                type="member",
            )

    async def register(
        self,
        guild: discord.Guild = None,
        user: discord.User = None,
        channel: discord.TextChannel = None,
    ):
        """Universal registration function for Discord data"""
        if guild:
            guild_entry = self.get_entry(obj=guild)
            if guild_entry:
                await guild_entry.discord_to_db()

        if channel:
            channel_entry = self.get_entry(obj=channel)
            if channel_entry:
                await channel_entry.discord_to_db()

        if user:
            # Ignore if webhook
            if user.bot:
                return

            user_entry = self.get_entry(obj=user)
            if user_entry:
                await user_entry.discord_to_db()

    async def index_all(self) -> tuple:
        """Try to register all Discord data"""
        log = []

        try:

            logger.info("Indexing all Discord data")
            log.append("Indexing all Discord data")
            log.append("~" * 10)

            logger.info("Indexing guilds")
            log.append("Indexing guilds")
            guilds = self.db.bot.guilds

            try:
                for guild in guilds:
                    try:
                        await self.register(guild=guild)
                    except Exception as e:
                        logger.error(f"Error indexing guild: {e}")
                        log.append(f"[ERROR] Error indexing guild {guild.name}: {e}")

            except Exception as e:
                logger.error(f"Error indexing guilds: {e}")
                log.append("~" * 10)
                log.append(f"[FATAL] Error indexing guilds: {e}")
                return (False, log)

            logger.info("Indexing channels")
            log.append("Indexing channels")
            channels = self.db.bot.get_all_channels()

            try:
                for channel in channels:
                    try:
                        await self.register(channel=channel)
                    except Exception as e:
                        logger.error(f"Error indexing channel: {e}")
                        log.append(
                            f"[ERROR] Error indexing channel {guild.name} -> {channel.name}: {e}"
                        )

            except Exception as e:
                logger.error(f"Error indexing channels: {e}")
                log.append("~" * 10)
                log.append(f"[FATAL] Error indexing channels: {e}")
                return (False, log)

            logger.info("Indexing members")
            log.append("Indexing members")
            members = self.db.bot.get_all_members()

            try:
                for member in members:
                    try:
                        await self.register(user=member)
                    except Exception as e:
                        logger.error(f"Error indexing member: {e}")
                        log.append(f"[ERROR] Error indexing member {member.name}: {e}")

            except Exception as e:
                logger.error(f"Error indexing members: {e}")
                log.append("~" * 10)

                log.append(f"[FATAL] Error indexing members: {e}")
                return (False, log)

            logger.info("Indexing complete")
            log.append("~" * 10)
            log.append("Indexing completed successfully")

            return (True, log)

        except Exception as e:
            logger.error(f"Uncaught Error indexing Discord data: {e}")
            log.append("~" * 10)

            log.append(f"[FATAL] Uncaught error: {e}")

            return (False, log)

    async def interactive(self, command: ShellCommand, init=False, internal=False):
        """Interactive mode for exploring Discord data"""

        def process_query(query: str) -> dict:
            """Process a query. Returns a dictionary with the query type and data if valid"""
            query = query.split(":")
            data = {
                "failed": False,
            }

            if query[0] == "history":
                data["action"] = "history"
                data["type"] = None
                return data

            if query is None or len(query) == 0:
                return {"failed": True, "error": "No query provided"}
            elif len(query) == 1:
                if query[0] == "guilds":
                    data["type"] = "guild"
                elif query[0] == "channels":
                    data["type"] = "channel"
                elif query[0] == "members":
                    data["type"] = "member"
                else:
                    return {
                        "failed": True,
                        "error": "Invalid type specified for list all query",
                    }
                data["action"] = "list"

            elif len(query) > 1:
                if not query[0] in ["guild", "member"]:
                    return {"failed": True, "error": "Invalid type specified for query"}
                data["type"] = query[0]
                data["action"] = "view"
                # Check if ID is valid
                try:
                    data["id"] = int(query[1])
                except:
                    return {"failed": True, "error": "Invalid ID specified for query"}

                if data["type"] == "guild" and len(query) > 2:
                    if query[2] == "channels":
                        data["action"] = "list_channels"
                    elif query[2] == "members":
                        data["action"] = "list_members"
                    elif query[2] == "channel":
                        data["action"] = "view"
                        data["type"] = "channel"

                        try:
                            data["channel_id"] = int(query[3])
                        except:
                            return {
                                "failed": True,
                                "error": "Invalid channel ID specified for query",
                            }
                    else:
                        return {
                            "failed": True,
                            "error": "Invalid action specified for guild query",
                        }
            return data

        async def return_home():
            """Return to the home page"""
            self.interactive_state["page"] = "main"
            self.interactive_state["subpage"] = None
            self.interactive_state["query"] = None

            await self.interactive(command, internal=True)
            return

        async def show_query(query: str, history=True) -> bool:
            if self.interactive_state["debug"]:
                await command.raw(f"Parsing query: {query}")
            
            result = process_query(query)
            
            if self.interactive_state["debug"]:
                await command.raw(f"Query result: {result}")
            
            if result["failed"]:
                await command.raw(f"Failed to parse query: {result['error']}")
                return False

            if result["action"] == "history":
                self.interactive_state["page"] = "history"
                self.interactive_state["subpage"] = None
                self.interactive_state["query"] = None

                await self.interactive(command, internal=True)
                return True

            self.interactive_state["query"] = result
            self.interactive_state["page"] = "query"
            self.interactive_state["subpage"] = result["action"]

            if history:
                self.interactive_state["history"].append(query)

            await self.interactive(command, internal=True)
            return True

        if init:
            self.interactive_state = {
                "page": "main",
                "subpage": None,
                "query": None,
                "debug": False,
                "history": [],
            }
            command.query = None
        if internal:
            command.query = None

        logger.info(
            f"Discord Data Explorer - Processing query: {command.query}"
        )

        if self.interactive_state.get("debug", False):
            try:
                fields = [
                    {"name": "Query", "value": command.query},
                    {
                        "name": "Interactive State",
                        "value": "```json\n"
                        + json.dumps(self.interactive_state, indent=4)
                        + "```",
                    },
                    {
                        "name": "Page",
                        "value": self.interactive_state["page"]
                        + (
                            " -> " + self.interactive_state["subpage"]
                            if self.interactive_state.get("subpage")
                            else ""
                        ),
                    },
                ]
            except:
                fields = [
                    {"name": "Query", "value": command.query},
                    {
                        "name": "Interactive State",
                        "value": "```python\n"
                        + str(self.interactive_state)
                        + "```\n(Failed to convert to JSON)",
                    },
                    {
                        "name": "Page",
                        "value": self.interactive_state["page"]
                        + (
                            " -> " + self.interactive_state["subpage"]
                            if self.interactive_state.get("subpage")
                            else ""
                        ),
                    },
                ]

            try:
                await command.log(
                    (
                        "Iinitial trigger"
                        if init
                        else ("Internal trigger" if internal else "User trigger")
                    ),
                    title="Discord Data Explorer - Debug",
                    fields=fields,
                )
            except Exception as e:
                await command.raw(f"Failed to log debug information: {e}")

            try:
                json_debug = {
                    "query": command.query,
                    "interactive_state": self.interactive_state,
                    "init": init,
                    "internal": internal,
                    "page": self.interactive_state["page"],
                    "subpage": self.interactive_state["subpage"],
                }

                # ALlow overwriting of debug file
                json_file = f"./tmp/discord_data_explorer_debug.json"
                with open(json_file, "w") as f:
                    json.dump(json_debug, f, indent=4)
            except Exception as e:
                logger.error(
                    f"Discord Data Explorer - Debug: Failed to write debug file: {e}"
                )

        if self.interactive_state["page"] == "main":
            # Remove unecessary data in interactive state
            # new_state = {}
            # for key in self.interactive_state:
            #     if key not in ["page", "subpage", "query", "debug"]:
            #         new_state[key] = self.interactive_state[key]
            # self.interactive_state = new_state

            if command.query:
                if command.query.lower() == "debug":
                    self.interactive_state["debug"] = not self.interactive_state.get(
                        "debug", False
                    )
                    await command.raw(
                        f"Debug mode {'enabled' if self.interactive_state['debug'] else 'disabled'}"
                    )
                    return

                await show_query(command.query)
                return

            await command.raw(
                """# Discord Data Explorer
Welcome to the Discord data explorer! Enter a query to get started!
### Queries
- `guilds` - List all guilds
  - `guild:<id>` - View a specific guild
- `channels` - List all channels
  - `guild:<id>:channels` - List all channels in a guild
  - `guild:<id>:channel:<id>` - View a specific channel
- `members` - List all members
  - `guild:<id>:members` - List all members in a guild
  - `member:<id>` - View a specific member
- `history` - View the query history
"""
            )
            return

        if self.interactive_state["page"] == "query":
            # Set default actions upon initialization
            if (not self.interactive_state.get("query_actions")) or internal:
                self.interactive_state["query_actions"] = [
                    "return",
                    "reload",
                    "query",
                    "back",
                ]

            # Process actions
            action = (command.query.lower().split(" ")[0]) if not internal else None
            try:
                action = int(action)
            except:
                pass
            # if action:
            #     await command.raw(f"Action: {action}")

            if action == "return":
                await return_home()
                return
            elif action == "back":
                if len(self.interactive_state["history"]) > 1:
                    self.interactive_state["history"].pop(-1)
                    await show_query(
                        self.interactive_state["history"][-1], history=False
                    )
                else:
                    await return_home()
                return
            elif action == "reload":
                self.interactive_state["query_actions"] = [
                    "return",
                    "reload",
                    "query",
                    "back",
                ]
            elif (
                action == "select" or isinstance(action, int)
            ) and "select" in self.interactive_state["query_actions"]:
                self.interactive_state["subpage"] = "view"
                try:
                    if isinstance(action, int):
                        index = int(action)
                    else:
                        index = int(command.query.split(" ")[1])
                    item = self.interactive_state["query_list_index_map"][index]
                except:
                    await command.raw("Invalid index specified")
                    return

                if (
                    self.interactive_state["query"]["type"] == "guild"
                    and self.interactive_state["query"]["action"] == "list"
                ):
                    await show_query(f"guild:{item}")

                elif (
                    self.interactive_state["query"]["type"] == "member"
                    and self.interactive_state["query"]["action"] == "list"
                ) or (
                    self.interactive_state["query"]["type"] == "guild"
                    and self.interactive_state["query"]["action"] == "list_members"
                ):
                    await show_query(f"member:{item}")

                elif (
                    self.interactive_state["query"]["type"] == "guild"
                    and self.interactive_state["query"]["action"] == "list_channels"
                ):
                    guild_id = self.interactive_state["query"]["id"]
                    await show_query(f"guild:{guild_id}:channel:{item}")

                else:
                    await command.raw(f"Invalid type for select action")

            elif (
                action == "attach"
                and ("attach" in self.interactive_state["query_actions"])
            ) or (action == "dm" and ("dm" in self.interactive_state["query_actions"])):
                if self.interactive_state["query"]["type"] == "channel":
                    channel_id = self.interactive_state["query"]["channel_id"]
                    guild_id = self.interactive_state["query"]["id"]

                    request = f"{guild_id}::{channel_id}"
                    request_command = ShellCommand(
                        name="impersonate-guild",
                        query=request,
                        shell=command.core,
                        channel=command.channel,
                        message=command.message,
                        cog="ImpersonateGuild",
                    )

                    try:
                        cog = self.db.bot.get_cog(request_command.cog)
                        await cog.shell_callback(request_command)
                    except Exception as e:
                        await command.raw(f"Failed to attach to channel: {e}")
                        return
                    else:
                        await command.raw("Created thread successfully")
                        return

                elif self.interactive_state["query"]["type"] == "member":
                    member_id = self.interactive_state["query"]["id"]
                    request = f"<@{member_id}>"
                    request_command = ShellCommand(
                        name="impersonate-dm",
                        query=request,
                        shell=command.core,
                        channel=command.channel,
                        message=command.message,
                        cog="ImpersonateDM",
                    )

                    try:
                        cog = self.db.bot.get_cog(request_command.cog)
                        await cog.shell_callback(request_command)
                    except Exception as e:
                        await command.raw(f"Failed to attach to member: {e}")
                        return
                    else:
                        await command.raw("Created thread successfully")
                        return

                else:
                    await command.raw("Invalid type for attach action")
                    return

            elif action == "query":
                query = " ".join(command.query.split(" ")[1:])

                await show_query(query)
                return

            elif (
                action == "owner" and "owner" in self.interactive_state["query_actions"]
            ):
                if self.interactive_state["query"]["type"] == "guild":
                    guild_id = self.interactive_state["query"]["id"]
                    guild = self.db.bot.get_guild(guild_id)

                    if not guild:
                        await command.raw(f"Guild {guild_id} not found")
                        await return_home()
                        return

                    await show_query(f"member:{guild.owner_id}")

            elif (
                action == "channels"
                and "channels" in self.interactive_state["query_actions"]
            ):
                guild_id = self.interactive_state["query"]["id"]
                await show_query(f"guild:{guild_id}:channels")

            elif (
                action == "members"
                and "members" in self.interactive_state["query_actions"]
            ):
                guild_id = self.interactive_state["query"]["id"]
                await show_query(f"guild:{guild_id}:members")

            elif (
                action == "guild" and "guild" in self.interactive_state["query_actions"]
            ):
                id = self.interactive_state["query"]["id"]
                if self.db.bot.get_guild(id):
                    await show_query(f"guild:{id}")
                else:
                    await command.raw("This operation is not supported by this query")
                    return

            # Show query
            if internal or action == "reload":
                if self.interactive_state["subpage"] == "list":
                    if self.interactive_state["query"]["type"] == "guild":
                        guilds = self.db.bot.guilds
                        index = 1
                        index_map = {}
                        send = []
                        for guild in guilds:
                            index_map[index] = guild.id
                            send.append(f"{index}. {guild.name} ({guild.id})")
                            index += 1

                        await command.raw("## Guilds")
                        # Send 10 at a time
                        for i in range(0, len(send), 10):
                            await command.raw("\n".join(send[i : i + 10]))

                        self.interactive_state["query_list_index_map"] = index_map
                        # Add actions for guilds
                        self.interactive_state["query_actions"].append("select")

                    elif self.interactive_state["query"]["type"] == "member":
                        members = self.db.bot.get_all_members()

                        # Remove duplicates
                        members = list(set(members))

                        index = 1
                        index_map = {}
                        send = []

                        for member in members:
                            index_map[index] = member.id
                            send.append(f"{index}. {member.name} ({member.id})")
                            index += 1

                        await command.raw("## Members")
                        # Send 10 at a time
                        for i in range(0, len(send), 10):
                            await command.raw("\n".join(send[i : i + 10]))

                        self.interactive_state["query_list_index_map"] = index_map
                        # Add actions for members
                        self.interactive_state["query_actions"].append("select")

                    elif self.interactive_state["query"]["type"] == "channel":
                        await command.raw("This action is not supported for channels")
                        await return_home()
                        return

                elif self.interactive_state["subpage"] == "view":
                    if self.interactive_state["query"]["type"] == "guild":
                        guild_id = self.interactive_state["query"]["id"]

                        guild_obj = self.db.bot.get_guild(guild_id)
                        if not guild_obj:
                            await command.raw(f"Guild {guild_id} not found")
                            await return_home()
                            return

                        guild_entry = self.get_entry(id=guild_id, type="guild")
                        await guild_entry.discord_to_db()

                        output = f"## Server: {guild_obj.name}\n"
                        output += f"**ID**: {guild_obj.id}\n"
                        output += f"**Owner**: {guild_obj.owner.name} ({guild_obj.owner.id})\n"
                        output += f"**Members**: {guild_obj.member_count}\n"
                        output += f"**Channels**: {len(guild_obj.channels)}\n"

                        self.interactive_state["query_actions"].extend(
                            ["channels", "members", "owner"]
                        )

                    elif self.interactive_state["query"]["type"] == "channel":
                        guild_id = self.interactive_state["query"]["id"]
                        channel_id = self.interactive_state["query"]["channel_id"]

                        guild_obj = self.db.bot.get_guild(guild_id)
                        if not guild_obj:
                            await command.raw(f"Guild {guild_id} not found")
                            await return_home()
                            return

                        channel_obj = guild_obj.get_channel(channel_id)
                        if not channel_obj:
                            await command.raw(
                                f"Channel {channel_id} not found within guild {guild_obj.name}"
                            )
                            await return_home()
                            return

                        channel_entry = self.get_entry(
                            id=channel_id, type="channel", parent_id=guild_id
                        )
                        await channel_entry.discord_to_db()

                        output = f"## \#{channel_obj.name} - {guild_obj.name}\n"
                        output += f"**ID**: {channel_obj.id}\n"
                        output += f"**Guild ID**: {channel_obj.guild.id}\n"
                        output += f"**Type**: {channel_obj.type}\n"
                        output += f"**Category**: {channel_obj.category.name if channel_obj.category else 'None'}\n"
                        output += f"**View**: {channel_obj.mention}\n"

                        self.interactive_state["query_actions"].extend(
                            ["guild", "attach"]
                        )

                    elif self.interactive_state["query"]["type"] == "member":
                        member_id = self.interactive_state["query"]["id"]

                        member_obj = self.db.bot.get_user(member_id)
                        if not member_obj:
                            await command.raw(
                                f"Could not find member {member_id}. Make sure the member is in a guild the bot is in."
                            )
                            await return_home()
                            return

                        member_entry = self.get_entry(id=member_id, type="member")
                        await member_entry.discord_to_db()

                        output = f"## @{member_obj.name}\n"
                        output += f"**ID**: {member_obj.id}\n"
                        output += f"**Discriminator**: {member_obj.discriminator}\n"
                        output += f"**Profile**: {member_obj.mention}\n"
                        output += f"**Bot**: {'Yep' if member_obj.bot else 'Nahh'}\n"

                        output += f"**Mutual Guilds**:\n"
                        for guild in member_obj.mutual_guilds:
                            output += f" - {guild.name} ({guild.id})\n"

                        self.interactive_state["query_actions"].extend(["dm"])

                    else:
                        await command.raw("Invalid type for view query")
                        return

                    await command.raw(output)

                elif self.interactive_state["subpage"] == "list_channels":
                    guild_id = self.interactive_state["query"]["id"]
                    guild_obj = self.db.bot.get_guild(guild_id)

                    channels = guild_obj.channels

                    if not guild_obj:
                        await command.raw(f"Guild {guild_id} not found")
                        await return_home()
                        return

                    index = 1
                    index_map = {}
                    send = []
                    for channel in channels:
                        index_map[index] = channel.id
                        send.append(f"{index}. {channel.name} ({channel.id})")
                        index += 1

                    await command.raw(f"## Channels in {guild_obj.name}")
                    # Send 10 at a time
                    for i in range(0, len(send), 10):
                        await command.raw("\n".join(send[i : i + 10]))

                    self.interactive_state["query_list_index_map"] = index_map
                    # Add actions for guilds
                    self.interactive_state["query_actions"].extend(["select", "guild"])

                elif self.interactive_state["subpage"] == "list_members":
                    guild_id = self.interactive_state["query"]["id"]
                    guild_obj = self.db.bot.get_guild(guild_id)

                    members = guild_obj.members

                    if not guild_obj:
                        await command.raw(f"Guild {guild_id} not found")
                        await return_home()
                        return

                    index = 1
                    index_map = {}
                    send = []
                    for member in members:
                        index_map[index] = member.id
                        send.append(f"{index}. {member.name} ({member.id})")
                        index += 1

                    await command.raw(f"## Members in {guild_obj.name}")
                    # Send 10 at a time
                    for i in range(0, len(send), 10):
                        await command.raw("\n".join(send[i : i + 10]))

                    self.interactive_state["query_list_index_map"] = index_map
                    # Add actions for guilds
                    self.interactive_state["query_actions"].extend(["select", "guild"])

            else:
                await command.raw("Please choose an action")
                return

            actions_str = "### Actions\n"
            actions_desc = {
                "return": "`return` - Return to the main page",
                "back": "`back` - Go back to the previous query",
                "select": "`select <index|id>` - Select an item from the list",
                "reload": "`reload` - Show content again",
                "channels": "`channels` - List all channels",
                "members": "`members` - List all members",
                "guilds": "`guilds` - List all guilds the member is in",
                "guild": "`guild` - View the referenced guild",
                "attach": "`attach` - Attach a thread to the channel (ImpersonateGuild)",
                "dm": "`dm` - Direct message a member (ImpersonateDM)",
                "owner": "`owner` - View the owner of the guild",
                "query": "`query <query>` - Discard current query and enter a new one",
            }
            for action in self.interactive_state["query_actions"]:
                actions_str += (
                    f"{actions_desc[action] if action in actions_desc else action}\n"
                )

            actions_str += "Choose an action:"
            await command.raw(actions_str)
            return
        elif self.interactive_state["page"] == "history":
            if command.query:
                if command.query.lower() == "return":
                    await return_home()
                    return

            if (
                not self.interactive_state["history"]
                or len(self.interactive_state["history"]) == 0
            ):
                await command.raw("No history available")
                await return_home()
                return
            
            try:
                command.query  = int(command.query)
            except:
                pass
                

            if isinstance(command.query, int):
                index = int(command.query)

                query = self.interactive_state["history"][index - 1]
                if not query:
                    await command.raw("Invalid index")
                    return

                await show_query(query)
                return

            await command.raw("## History")

            # Create 10-line groups
            history = self.interactive_state["history"]
            history_strings = []
            
            for item in history:
                history_strings.append(f"{len(history_strings) + 1}. {item}")
            
            for i in range(0, len(history_strings), 10):
                await command.raw(
                    "\n".join(history_strings[i : i + 10])
                )

            await command.raw("Enter a number to view the query or `return` to go back")
            return


class DatabaseHandler(commands.Cog):
    """Cog for intergrating the database with the bot"""

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
        self.shell.add_command(
            command="explorer",
            cog="DatabaseHandler",
            description="Interactive Discord data explorer",
        )

        logger.info("Database enabled")

    # Start database connection
    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Connecting to database")

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

        logger.info("Database connected; starting indexing task")
        self.periodic_index.start()
        logger.info("Database indexing task started")

    @tasks.loop(hours=1)
    async def periodic_index(self):
        logger.info("Periodic indexing")
        await self.core.data.index_all()
        self.core.indexed = True

    # * Discord Data -- Automatic Registration
    # Listen to on guild join
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        if not self.core.working:
            return

        try:
            await self.core.discord.register(guild=guild)
        except Exception as e:
            logger.error(f"Error when registering guild: {e}")
            await self.shell.log(
                f"Error registering Discord data: {e}",
                title="Database Error (Discord Data)",
                msg_type="error",
                cog="DatabaseHandler",
            )

    # Listen to on channel create
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.TextChannel):
        if not self.core.working:
            return

        try:
            await self.core.discord.register(channel=channel)
        except Exception as e:
            logger.error(f"Error when registering channel: {e}")
            await self.shell.log(
                f"Error registering Discord data: {e}",
                title="Database Error (Discord Data)",
                msg_type="error",
                cog="DatabaseHandler",
            )

    # Listen to on guild update
    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        if not self.core.working:
            return

        try:
            await self.core.discord.register(guild=after)
        except Exception as e:
            logger.error(f"Error when registering guild: {e}")
            await self.shell.log(
                f"Error registering Discord data: {e}",
                title="Database Error (Discord Data)",
                msg_type="error",
                cog="DatabaseHandler",
            )

    # Listen to on channel create
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.TextChannel):
        if not self.core.working:
            return

        try:
            await self.core.discord.register(channel=channel)
        except Exception as e:
            logger.error(f"Error when registering channel: {e}")
            await self.shell.log(
                f"Error registering Discord data: {e}",
                title="Database Error (Discord Data)",
                msg_type="error",
                cog="DatabaseHandler",
            )

    # Listen to on channel update
    @commands.Cog.listener()
    async def on_guild_channel_update(
        self, before: discord.TextChannel, after: discord.TextChannel
    ):
        if not self.core.working:
            return

        try:
            await self.core.discord.register(channel=after)
        except Exception as e:
            logger.error(f"Error when registering channel: {e}")
            await self.shell.log(
                f"Error registering Discord data: {e}",
                title="Database Error (Discord Data)",
                msg_type="error",
                cog="DatabaseHandler",
            )

    # Listen to on member join
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not self.core.working:
            return

        try:
            await self.core.discord.register(user=member)
        except Exception as e:
            logger.error(f"Error when registering member: {e}")
            await self.shell.log(
                f"Error registering Discord data: {e}",
                title="Database Error (Discord Data)",
                msg_type="error",
                cog="DatabaseHandler",
            )

    # Cog Status
    async def cog_status(self) -> str:
        """Check the status of the database connection by checking the schema"""
        logger.info("Checking database status")

        # Connection status (Check schema)
        status = await self.core.check_status()
        if status == 2:
            return "Database connection successful"
        elif status == 1:
            return "Connected but no tables found"
        else:
            return "Database connection failed"

    async def shell_callback(self, command: ShellCommand):
        if command.name == "explorer":
            await command.log(
                "Launching interactive Discord data explorer...",
                title="Discord Data Exploration",
                msg_type="info",
            )
            self.core.shell.interactive_mode = (
                "DatabaseHandler",
                "discord-explore",
            )
            await self.core.discord.interactive(command, init=True)
            return

        elif command.name == "db":
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

            elif subcommand == "discord":
                subsubcommand = (
                    command.query.split(" ")[1]
                    if " " in command.query
                    else command.query
                )

                if subsubcommand == "index-all":
                    message = await command.log(
                        "Indexing all Discord data...\nThis may take a while.",
                        title="Discord Data Indexing",
                        msg_type="info",
                    )

                    result, log = await self.core.discord.index_all()
                    logger.info(result, log)
                    fields = [
                        {
                            "name": "Log",
                            "value": "```" + "\n".join(log) + "```",
                        },
                    ]
                    if result:
                        await command.log(
                            "Successfully indexed all Discord data.",
                            title="Discord Data Indexing",
                            msg_type="success",
                            fields=fields,
                            edit=message,
                        )
                    else:
                        await command.log(
                            "Failed to index all Discord data.",
                            title="Discord Data Indexing",
                            msg_type="error",
                            fields=fields,
                            edit=message,
                        )
                    return
                elif subsubcommand == "explore":
                    await command.log(
                        "Launching interactive Discord data explorer...",
                        title="Discord Data Exploration",
                        msg_type="info",
                    )
                    self.core.shell.interactive_mode = (
                        "DatabaseHandler",
                        "discord-explore",
                    )
                    await self.core.discord.interactive(command, init=True)
                    return
                fields = [
                    {
                        "name": "db discord index-all",
                        "value": "Index all Discord data",
                    },
                    {
                        "name": "db discord explore",
                        "value": "Explore Discord data (Interactive)",
                    },
                ]
                await command.log(
                    "Manage Discord data. Here are the available Discord commands:",
                    fields=fields,
                    title="Discord Commands",
                    msg_type="info",
                )
                return

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
                    {
                        "name": "db discord",
                        "value": "Manage Discord data",
                    },
                ]
                await command.log(
                    "Manage database. Here are the available database commands:",
                    fields=fields,
                    title="Database Commands",
                    msg_type="info",
                )

        elif command.name == "discord-explore":
            await self.core.discord.interactive(command)
            return

        else:
            await command.log(
                preset="CogNoCommandError",
            )

    async def test_script(self, command: ShellCommand):
        # Test script
        try:
            await command.raw("Testing script")
            await command.raw("Fetching server_data.guilds")

            schema = self.core.data.get_schema("server_data")
            table = schema.get_table("guilds")

            data = await table.fetch()

            await command.raw(f"Data: \n```python\n{data}\n```")

            table_channels = schema.get_table("channels")
            data_channels = await table_channels.fetch()

            await command.raw(f"Channels: \n```python\n{data_channels}\n```")

        except Exception as e:
            await command.log(f"Error: {e}")
