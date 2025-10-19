"""Discord.py bot wrapper"""

from discord.ext import commands
from discord import Intents

from .logging import get_framework_logger

class Bot(commands.Bot):
    """Discord.py bot wrapper with extended functionality."""

    def __init__(self, intents: Intents | None = None, *args, **kwargs):
        self.logger = get_framework_logger("bot")
        super().__init__(intents=self._generate_intents(intents), *args, **kwargs)
        
    def _generate_intents(self, intents: list[str] | None):
        """Generate Discord intents from a list of intent names."""
        if intents is None:
            self.logger.info("No intents specified; defaulting to default intents.")
            return Intents.default()

        detected_intents = []
        intent_flags = Intents.none()
        for intent_name in intents:
            if hasattr(Intents, intent_name):
                setattr(intent_flags, intent_name, True)
                detected_intents.append(intent_name)
        
        if detected_intents:
            self.logger.info(f"Enabled intents: {', '.join(detected_intents)}")
        else:
            self.logger.warning("No valid intents specified; defaulting to no intents.")
        return intent_flags
    
    async def auto_add_cog(self, cog: commands.Cog, reload:bool=True) -> None:
        """
        (squid-core extension)
        Automatically add a Cog to the bot.
        
        Args:
            cog (commands.Cog): The Cog to add.
            reload (bool): Whether to reload the Cog if it already exists. (Otherwise, skips adding.)
        """
        if cog.qualified_name in self.cogs:
            if reload:
                self.logger.info(f"Reloading existing Cog: {cog.qualified_name}")
                await self.remove_cog(cog.qualified_name)
            else:
                self.logger.info(f"Cog {cog.qualified_name} already exists; skipping add.")
                return
        await self.add_cog(cog)
        self.logger.info(f"Added Cog: {cog.qualified_name}")
        
    async def run(self, token: str, **kwargs):
        """Run the bot with the given token."""
        self.logger.info("Starting bot...")
        await super().start(token, **kwargs)
        
    async def on_ready(self):
        """Event handler for when the bot is ready."""
        self.logger.info(f"Got ready event.")
        self.logger.info(f"Bot connected as {self.user} (ID: {self.user.id})")

        await self.tree.sync()
        self.logger.info("Command tree synced.")