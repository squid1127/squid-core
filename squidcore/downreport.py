"""Automatic system for reporting when the bot disconnects or crashes."""

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
        
    async def initialize(self):
        """Initialize everything needed to report down events."""
        self.webhook = await self.get_webhook()
        if not self.webhook:
            logger.error("Failed to initialize down report manager | Missing webhook")
            return
        
        # Save the webhook url
        path = "store/cache/downreport-webhook.json"
        data = {"url": self.webhook.url}
        
        with open(path, "w") as f:
            json.dump(data, f)
            
    @commands.Cog.listener()
    async def on_ready(self):
        """Initialize the down report manager when the bot is ready."""
        logger.info("Initializing down report manager")
        await self.initialize()
        logger.info("Down report manager initialized")
        

    async def get_webhook(self) -> discord.Webhook:
        """Automaticly fetch or create the webhook for the report channel."""

        # Get the channel
        channel = self.bot.get_channel(self.report_channel)
        if not channel:
            logger.error("Unable to fetch webhook: Channel not found")
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
        
def down_report(message: str):
    """Report a down event to the shell channel. (No async)"""
    
    # Read the webhook url
    path = "store/cache/downreport-webhook.json"
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

    