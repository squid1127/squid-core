"""A command line interface plugin for managing permissions."""

import discord
from squid_core.plugin_base import Plugin as BasePlugin, PluginCog
from squid_core.framework import Framework
from squid_core.decorators import DiscordEventListener, FwEventListener

class BotEventsCLIPlugin(BasePlugin):
    """A plugin for sending bot events through the CLI."""


    def __init__(self, framework: Framework):
        super().__init__(framework)
        
    async def notify(self, title:str, message:str, color:int=discord.Color.green().value, footer:str=None, **kwargs):
        """Notify about a bot event via the CLI."""
        try:
            embed = discord.Embed(title=title, description=message, color=color, **kwargs)
            if footer:
                embed.set_footer(text=footer)
            for channel in self.framework.cli.get_channels():
                await channel.send(embed=embed)

        except Exception as e:
            self.framework.logger.error(f"Failed to notify CLI: {e}")
            
    async def load(self):
        """Load the plugin."""
        pass # Requried by ABC but nothing to do here.
    async def unload(self):
        """Unload the plugin."""
        pass

    @DiscordEventListener()
    async def on_ready(self):
        await self.notify("Bot Ready", f"Got a ready event as {self.framework.bot.user}!", footer="(This could be a reconnect.)")
        
    @DiscordEventListener()
    async def on_guild_join(self, guild: discord.Guild):
        await self.notify("Joined Server", f"Joined server: {guild.name} (ID: {guild.id})]", footer=f"Owned by: {guild.owner} (ID: {guild.owner_id})")
        
    @DiscordEventListener()
    async def on_guild_remove(self, guild: discord.Guild):
        await self.notify("Left Server", f"Left server: {guild.name} (ID: {guild.id})")