# Random status cog for SquidCore

# Discord modules
import discord
from discord.ext import commands, tasks

# Random module
import random

# Shell
from .shell import ShellCommand

class Status:
    """
    A class to represent a Discord status.
    
    Attributes
    ----------
    type : str
        The type of the status (e.g., "playing", "streaming", "listening", "watching").
    message : str
        The message associated with the status.
    **kwargs : dict
        Additional keyword arguments for the status.
        
    Methods
    -------
    __call__() -> discord.Activity:
        Returns a discord.Activity object based on the status type and message.
    """
    
    def __init__(self, type: str, message: str, **kwargs):
        self.message = message
        if type not in self.STATUS_TYPES:
            raise ValueError(f"Invalid status type: {type}")
        self.type = type
        self.activity_kwargs = kwargs

    def __call__(self) -> discord.Activity:
        if self.type == "playing":
            return discord.Game(name=self.message, **self.activity_kwargs)
        elif self.type == "streaming":
            return discord.Streaming(name=self.message, **self.activity_kwargs)
        elif self.type == "listening":
            return discord.Activity(
                type=discord.ActivityType.listening, name=self.message, **self.activity_kwargs
            )
        elif self.type == "watching":
            return discord.Activity(
                type=discord.ActivityType.watching, name=self.message, **self.activity_kwargs
            )
        elif self.type == "custom":
            return discord.Activity(
                type=discord.ActivityType.custom, name=self.message, **self.activity_kwargs
            )
            
    
    STATUS_TYPES = ["playing", "watching", "listening", "streaming", "custom"]



class RandomStatus(commands.Cog):
    def __init__(self, bot: commands.Bot, status_list: list["Status"]):
        self.bot = bot

        self.status_list = status_list
        self.interval_hours = 24  #! Currently hardcoded because decorators are selly
        
        self.bot.shell.add_command("rand_status", description="Change the bot's status", cog="RandomStatus")

    # Status task
    @tasks.loop(hours=24)
    async def change_status(self):
        print("[Core.RandomStatus] Changing status")
        status = random.choice(self.status_list)
        await self.bot.change_presence(activity=status())
        print(f"[Core.RandomStatus] Status changed to {status.type} {status.message}")

    # Start the loop
    @commands.Cog.listener()
    async def on_ready(self):
        self.change_status.start()
        print(f"[Core.RandomStatus] Random status loop started (Daily)")
        
    # Shell command
    async def shell_callback(self, command: ShellCommand):
        if command.name == "rand_status":
            if command.query:
                try:
                    content = command.query.split("--type")[0].strip()
                    params = command.params_to_dict(command.query.replace(content, ""))
                    status = Status(params["--type"], params["--content"])
                except KeyError or ValueError:
                    await command.log(
                        "Invalid parameters. Usage: status [content] --type [type]",
                        title="Invalid Parameters",
                        msg_type="error",
                    )
                    return
                except Exception as e:
                    await command.log(
                        f"An error occurred: {e}", title="Error", msg_type="error"
                    )
                    return
            else:
                            status = random.choice(self.status_list)
            await self.bot.change_presence(activity=status())
            await command.log(
                f"Status changed to {status.type} {status.message}",
                title="Status Changed",
                msg_type="success",
            )
    async def cog_status(self):
        return f"Ready: {len(self.status_list)} statuses"

    # Constants
    FUNNY_MESSAGES = [
        Status("playing", "hit the unsell button"),
        Status("watching", "you procrastinate"),
        Status("custom", "🥔"),
        Status("custom", "There is nothing we can do."),
        Status("listening", "to the sound of silence"),
        Status("watching", "absolutely nothing"),
        Status("playing", "don't get a BSOD"),
    ]
