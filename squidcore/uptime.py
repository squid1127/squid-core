"""Passive monitor support for services such as uptime kuma."""

# External imports
from discord.ext import commands, tasks
import discord

# Bot Shell
from .shell import ShellCore

# Async + Http
import aiohttp, asyncio

# Typing
from typing import Literal

# Logging
import logging

logger = logging.getLogger("core.uptime")


class UptimeManager(commands.Cog):
    """
    Passive monitor support for services such as uptime kuma.

    Args:
        bot (commands.Bot): The bot instance
        shell (ShellCore): The shell instance
    """

    def __init__(
        self,
        bot: commands.Bot,
        shell: ShellCore,
    ):
        self.bot = bot
        self.shell = shell

        self.enabled = False
        self.uptime_url = None
        self.provider = None
        self.interval = 120  # Default interval in seconds

        self.files = self.bot.filebroker.configure_cog(
            "UptimeManager",
            config_file=True,
            config_default=self.DEFAULT_CONFIG,
            config_do_cache=300,
            cache=True,
            cache_clear_on_init=True,
        )
        self.files.init()

        # Create a custom task object
        self.push_uptime_task = tasks.loop(seconds=self.interval)(self.push_uptime)

    async def load_config(self, reload: bool = False):
        self.config = self.files.get_config(cache=not reload)
        self.enabled = self.config.get("enabled", False)
        self.provider = self.config.get("provider", "uptime_kuma")
        self.uptime_url = self.config.get("url", None)
        self.interval = self.config.get("interval", 120)
        if (not self.enabled) or (self.uptime_url is None):
            logger.warning("Uptime Manager is disabled or URL is not set.")
            return

    def cog_unload(self):
        """Stop the uptime check task when the cog is unloaded."""
        self.push_uptime_task.stop()

    @commands.Cog.listener()
    async def on_ready(self):
        """Start the uptime check task when the bot is ready."""
        logger.info("Starting Uptime Manager...")
        await self.load_config()
        if self.enabled:
            logger.info("Uptime Manager is ready.")
            self.push_uptime_task.start()
            logger.info(f"Uptime check task started with interval: {self.interval} seconds")
        else:
            logger.warning("Uptime Manager is disabled. Not starting the task.")

    async def push_uptime(self):
        """Push uptime status to the configured URL."""    
        params = {}
        if self.provider == "uptime_kuma":
            params["msg"] = f"{self.bot.user.name} is alive!"
            params["status"] = "up"

        error = None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.uptime_url, params=params) as response:
                    if response.status == 200:
                        logger.info(f"Uptime check successful: {response.status}")
                    else:
                        error = f"Uptime check failed: {response.status}"
        except aiohttp.ClientError as e:
            error = f"Uptime check failed: {e}"
        except asyncio.TimeoutError:
            error = "Uptime check timed out"
        except Exception as e:
            error = f"Uptime check failed: {e}"
        finally:
            if error:
                logger.error(error)
                await self.shell.log(
                    error,
                    title="Uptime Update Failed",
                    msg_type="error",
                )
                return
            logger.info("Uptime check successful")

    DEFAULT_CONFIG = """# Uptime Manager Configuration

# Set to true to enable uptime 
enabled: false

# Provider for uptime monitoring
# Supported providers:
# - uptime_kuma
# (Use 'None' to use a simple get request)
provider: uptime_kuma

# URL for passive monitoring
url: https://example.com/uptime

# Interval for uptime checks in seconds
interval: 120
"""
