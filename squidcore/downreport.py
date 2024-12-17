"""Automatic system for reporting when the bot disconnects or crashes."""

# Files
from .files import FileBroker, CogFiles

# Discord
import discord
from discord.ext import commands, tasks
from .shell import ShellCore, ShellCommand

# URL File
import json
import os

# HTTP
import aiohttp, asyncio

# Logging
import logging
logger = logging.getLogger("core.downreport")


class DownReportManager(commands.Cog):
    """
    Automatic system for reporting when the bot disconnects or crashes. This cog will create and store webhooks for the bot to use to send messages to the shell channel.

    Args:
        bot (commands.Bot): The bot instance
        shell (ShellCore): The shell core instance
        report_channel (int, optional): The channel ID to report to. Defaults to the shell channel.
    """

    def __init__(self, bot: commands.Bot, shell: ShellCore, report_channel: int = None):
        self.bot = bot
        self.shell = shell
        self.report_channel = report_channel if report_channel else shell.channel_id
        self.webhook = None
        
        self.shell.add_command("downreport", cog="DownReportManager", description="Configure the down report manager")
        broker: FileBroker = self.bot.filebroker
        self.files = broker.configure_cog(
            "DownReportManager",
            cache=True,
        )
        self.files.init()
        
    @commands.Cog.listener()
    async def on_ready(self):
        """Initialize the down report manager when the bot is ready."""
        logger.info("Initializing down report manager")
        await self.initialize()
        logger.info("Down report manager initialized")
        
    async def initialize(self, force: bool = False):
        """Initialize everything needed to report down events."""
        self.webhook = await self.get_webhook(force=force)
        if not self.webhook:
            logger.error("Failed to initialize down report manager | Missing webhook")
            return
        
        # Save the webhook url
        path = os.path.join(self.files.get_cache_dir(), "downreport-webhook.json")
        data = {"url": self.webhook.url}
        
        with open(path, "w") as f:
            json.dump(data, f)


    async def get_webhook(self, force: bool = False) -> discord.Webhook:
        """Automaticly fetch or create the webhook for the report channel."""

        # Get the channel
        channel = self.bot.get_channel(self.report_channel)
        if not channel:
            logger.error("Unable to fetch webhook: Channel not found")
            await self.shell.log(
                "Unable to fetch webhook: Channel not found",
                title="Channel Not Found",
                msg_type="error",
                cog="DownReport",
            )
            return None

        # Get the webhook
        try:
            webhooks = await channel.webhooks()
        except discord.Forbidden:
            logger.error("Missing permissions to fetch webhooks")
            await self.shell.log(
                "'Manage Webhooks' permission is required for downreport to function.",
                title="Permissions Error",
                msg_type="error",
                cog="DownReport",
            )
            return None
        
        # Find the webhook
        webhook_name = f"{self.bot.user.name} | Bot Error Report"
        for webhook in webhooks:
            if webhook.name == webhook_name:
                if force:
                    try:
                        await webhook.delete(reason="Forced webhook recreation for downreport")
                    except discord.Forbidden:
                        logger.error("Missing permissions to delete webhooks")
                        await self.shell.log(
                            "'Manage Webhooks' permission is required for downreport to function.",
                            title="Permissions Error",
                            msg_type="error",
                            cog="DownReport",
                        )
                        return None
                    break
                else:
                    return webhook
        
        # Create the webhook
        try:
            webhook = await channel.create_webhook(name=webhook_name, reason="Error reporting webhook")
        except discord.Forbidden:
            logger.error("Missing permissions to create webhooks")
            await self.shell.log(
                "'Manage Webhooks' permission is required for downreport to function.",
                title="Permissions Error",
                msg_type="error",
                cog="DownReport",
            )
            return None
        
        return webhook
        
    #* Shell Stuff
    async def cog_status(self):
        """Return the status of the down report cog."""
        if not self.webhook:
            return "Error: Missing webhook"
        
        return "Ready"

    async def shell_callback(self, command: ShellCommand):
        """Handle shell commands for the down report manager."""
        if command.name == "downreport":
            if command.query.startswith("get"):
                await command.log(f"Webhook URL: {self.webhook.url}", title="Webhook URL")
            elif command.query.startswith("set"):
                await command.log("Setting the webhook is not supported", title="Error", msg_type="error")
            elif command.query.startswith("new"):
                message = await command.log("Creating a new webhook...", title="New Webhook")
                await self.initialize(force=True)
                if self.webhook:
                    await command.log(f"New webhook created: {self.webhook.url}", title="New Webhook", msg_type="success", edit=message)
                else:
                    await command.log("Failed to create a new webhook", title="New Webhook", msg_type="error", edit=message)
            else:
                await command.log(
                    "Usage: downreport [get|set|new]",
                    title="downreport: Usage",
                )
                
                
        
def down_report(message: str):
    """Report a down event to the shell channel. (No async)"""
    
    # Read the webhook url
    path = "store/cache/DownReportManager/downreport-webhook.json"
    if not os.path.exists(path):
        logger.error("Missing webhook url")
        return
    
    with open(path, "r") as f:
        data = json.load(f)
        
    url = data.get("url")
    if not url:
        if data.get("new"):
            logger.error("Webhook has not been created yet")
        else:
            logger.error("Missing webhook url")
        return
    
    # Format the message
    embed = discord.Embed(
        title="[WARNING] BOT DOWN",
        description=message,
        color=discord.Color.red(),
    )
    
    # Send the message
    asyncio.run(_down_report_send_embed(url, embed))
    
        
    
    
async def _down_report_send_embed(url: str, embed: discord.Embed):
    # Send the message
    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(url, session=session)
        await webhook.send(embed=embed)