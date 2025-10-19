"""Discord-interactive CLI component, allowing command execution via Discord channels."""

from discord.ext import commands
import discord
from dataclasses import dataclass
from shlex import split as shell_split
from enum import Enum
from ..logging import get_framework_logger


class EmbedLevel(Enum):
    """Represents the level of detail for an embed."""
    SUCCESS = 0 # Extra details for successful operations
    INFO = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4


@dataclass(frozen=True, order=True)
class CLICommand:
    """Represents a CLI command."""

    name: str
    aliases: list[str]
    description: str
    execute: callable
    plugin: str | None = None  # Plugin association
    internal: bool = False  # Internal command flag (Non-plugin)


@dataclass(frozen=True, order=True)
class CLIContext:
    """Represents a CLI command request."""

    command: CLICommand
    args: list[str]
    message: discord.Message | None = None  # Original Discord message
    
    # Built-in methods for convenience
    async def respond(self, title: str, description: str, level: EmbedLevel) -> discord.Message:
        """Respond to the command with an embed."""
        embed = EmbedGenerator.generate_embed(title, description, level, self)
        return await self.message.channel.send(embed=embed)
    async def respond_exception(self, title: str, exception: Exception) -> discord.Message:
        """Respond to the command with an exception embed."""
        embed = EmbedGenerator.exception(title, exception, self)
        attachment = EmbedGenerator.exception_attach(exception)
        return await self.message.channel.send(embed=embed, file=attachment)


class CLIManager:
    """Manager for Discord-interactive CLI commands."""

    def __init__(
        self, bot: commands.Bot, allowed_channel_ids: list[int], cli_prefix: str
    ) -> None:
        """
        Initialize the CLI Manager.
        Args:
            bot (commands.Bot): The Discord bot instance.
            allowed_channel_ids (list[int]): List of channel IDs where CLI commands are allowed. Note: These channels should be private - Any user with the ability to send messages in these channels can execute CLI commands.
            cli_prefix (str): The prefix for CLI commands.
        """
        self.logger = get_framework_logger("cli")
        self.bot = bot
        self.allowed_channel_ids = [int(cid) for cid in allowed_channel_ids]
        self.cli_prefix = cli_prefix
        self.bot.add_listener(self.on_message)

        self.commands: list[CLICommand] = []

    async def on_message(self, message: discord.Message) -> None:
        """Listener for messages to process CLI commands."""
        if message.channel.id not in self.allowed_channel_ids:
            return  # Ignore messages from unauthorized channels
        if message.author.bot:
            return  # Ignore messages from bots
        
        self.logger.info(f"Received CLI message from {message.author} in channel {message.channel}")


        if not message.content.startswith(self.cli_prefix):
            return  # Ignore messages that don't start with the CLI prefix


        # Parse command and arguments
        content = message.content[len(self.cli_prefix) :].strip()
        if not content:
            return  # No command provided

        # Split the content into command and arguments
        parts = shell_split(content)
        command_name = parts[0]
        command_args = parts[1:]

        # Retrieve the command
        command = self.get_command(command_name)
        if not command:
            return  # Command not found
        
        # Create context object
        context = CLIContext(command=command, args=command_args, message=message)
        
        self.logger.info(f"Executing CLI command: {command.name} with args: {command_args} from user: {message.author} in channel: {message.channel}")

        # Execute the command
        try:
            await command.execute(context)
        except Exception as e:
            await context.respond_exception("CLI - Execution Error", e)

    async def notify(self, title: str, description: str, level: EmbedLevel, plugin: str = None) -> list[discord.Message]:
        """Send a notification to all allowed CLI channels."""
        embed = EmbedGenerator.generate_embed(title, description, level, CLIContext(
            command=CLICommand(
                name="notify",
                aliases=[],
                description="Notification",
                execute=lambda x: None,
                plugin=plugin,
            ),
            args=[],
        ))
        messages = []
        for channel in self.get_channels():
            messages.append(await channel.send(embed=embed))
        return messages

    def register_command(self, command: CLICommand) -> None:
        """Register a CLI command."""
        self.commands.append(command)

    def unregister_command(self, command: CLICommand) -> None:
        """Unregister a CLI command."""
        self.commands.remove(command)

    def get_command(self, name: str) -> CLICommand | None:
        """Retrieve a CLI command by name or alias."""
        name = name.lower().strip()
        for command in self.commands:
            if command.name == name or name in command.aliases:
                return command
        return None
    
    def get_channels(self) -> list[discord.TextChannel]:
        """Get the Discord channel objects for allowed CLI channels."""
        channels = []
        for channel_id in self.allowed_channel_ids:
            channel = self.bot.get_channel(channel_id)
            if isinstance(channel, discord.TextChannel):
                channels.append(channel)
        return channels
    
class EmbedGenerator:
    """Utility class for generating command responses as embeds."""

    level_colors = {
        EmbedLevel.SUCCESS: discord.Color.green(),
        EmbedLevel.INFO: discord.Color.blurple(),
        EmbedLevel.WARNING: discord.Color.gold(),
        EmbedLevel.ERROR: discord.Color.red(),
        EmbedLevel.CRITICAL: discord.Color.dark_red(),
    }
    level_headings = {
        EmbedLevel.SUCCESS: "✅",
        EmbedLevel.INFO: "ℹ️",
        EmbedLevel.WARNING: "⚠️",
        EmbedLevel.ERROR: "❌",
        EmbedLevel.CRITICAL: "💥"
        }
        
    @classmethod
    def generate_embed(cls, title: str, description: str, level: EmbedLevel, ctx: CLIContext) -> discord.Embed:
        """Generate a Discord embed for command responses."""
        color = cls.level_colors.get(level, discord.Color.default())
        embed = discord.Embed(title=title, description=description, color=color)
        if ctx.command.plugin:
            embed.set_footer(text=f"{ctx.command.plugin}")
        return embed
    
    @classmethod
    def exception(cls, title: str, exception: Exception, ctx: CLIContext) -> discord.Embed:
        """Generate an embed for exceptions."""
        description = f"```{type(exception).__name__}: {str(exception)}```"
        return cls.generate_embed(title, description, EmbedLevel.ERROR, ctx)
    
    @classmethod
    def exception_attach(cls, exception: Exception) -> discord.File:
        """Generate an attachment containing exception traceback."""
        import traceback
        from io import StringIO

        buffer = StringIO()
        traceback.print_exception(type(exception), exception, exception.__traceback__, file=buffer)
        buffer.seek(0)
        return discord.File(fp=buffer, filename="traceback.txt")