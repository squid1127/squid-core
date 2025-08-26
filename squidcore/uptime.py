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

        self.fails = 0

        self.enabled = False
        self.uptime_url = None
        self.provider = None

        self.files = self.bot.filebroker.configure_cog(
            "UptimeManager",
            config_file=True,
            config_default=self.DEFAULT_CONFIG,
            config_do_cache=300,
            cache=True,
            cache_clear_on_init=True,
        )
        self.files.init()
        self.push_uptime.start()

    async def load_config(self, reload: bool = False):
        self.config = self.files.get_config(cache=not reload)
        self.enabled = self.config.get("enabled", False)
        self.provider = self.config.get("provider", "uptime_kuma")
        self.uptime_url = self.config.get("url", None)
        self.interval = self.config.get("interval", 120)
        if (not self.enabled) or (self.uptime_url is None):
            logger.warning("Uptime Manager is disabled or URL is not set.")
            return

    @tasks.loop(seconds=120)
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
                        if self.fails > 0:
                            logger.info(
                                f"Uptime check recovered after {self.fails} failures."
                            )
                        self.fails = 0  # Reset on success
                        logger.info(f"Uptime check successful: {response.status}")
                    else:
                        error = f"Uptime check failed: {response.status}"
        except aiohttp.ClientError as e:
            error = f"Uptime check failed: {e}"
        except asyncio.TimeoutError:
            error = "Uptime check timed out"
        except Exception as e:
            error = f"Uptime check failed: {e}"

        if error:
            self.fails += 1
            logger.error(f"Uptime check failure #{self.fails}: {error}")
            if self.fails == 1:  # First failure
                await self.shell.log(
                    error,
                    title="Uptime Update Failed",
                    msg_type="error",
                )
            elif self.fails == 10:  # 10th failure
                await self.shell.log(
                    "Uptime check failed 10 times in a row. Something is very wrong!",
                    title="Uptime Manager 10x Failures",
                    msg_type="warning",
                )

    @push_uptime.before_loop
    async def before_push_uptime(self):
        logger.info("Preparing to push uptime status...")
        await self.bot.wait_until_ready()
        # Load configuration
        await self.load_config()
        if not self.enabled:
            logger.warning("Uptime Manager is disabled. Task will not start.")
            self.push_uptime.cancel()
            return
        # Update the loop interval
        self.push_uptime.change_interval(seconds=self.interval)
        logger.info(f"Uptime check interval set to {self.interval} seconds.")

    async def cog_unload(self):
        """Stop the uptime check task when the cog is unloaded."""
        self.push_uptime.cancel()

    async def cog_status(self) -> str:
        """Return the status of the uptime manager."""
        if not self.enabled:
            return "Uptime Manager is disabled."
        if self.fails > 0:
            return f"Uptime Failed! Errors: {self.fails}"
        return f"Uptime Manager is running with provider: {self.provider}, URL: {self.uptime_url}, Interval: {self.interval} seconds."

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
