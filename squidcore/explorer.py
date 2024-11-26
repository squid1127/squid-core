"""v2 of the discord data explorer."""

import discord
from discord.ext import commands, tasks

from .shell import ShellCore, ShellCommand
from .db import DatabaseCore, DiscordData

import logging  

logger = logging.getLogger('core.explorer')

class DiscordExplorer(commands.Cog):
    """A cog that allows for the exploration of discord data."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db: DatabaseCore = bot.db
        self.shell: ShellCore = bot.shell

        self.shell.add_command(command="explore", cog="DiscordExplorer", description="Explore discord data.")
        self.shell.add_command(command="xp", cog="DiscordExplorer", description="(Alias for explore) Explore discord data.")
        
    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Discord Explorer loaded.")
        
    @commands.Cog.listener()
    async def shell_callback(self, command: ShellCommand):
        pass