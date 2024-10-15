# Random status cog for SquidCore

# Discord modules
import discord
from discord.ext import commands, tasks

# Random module
import random


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
        if type not in RandomStatus.STATUS_TYPES:
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
        else:
            return discord.Activity(
                type=discord.ActivityType.custom, name=self.message, **self.activity_kwargs
            )


class RandomStatus(commands.cog):
    def __init__(self, bot: commands.Bot, status_list: list["Status"]):
        self.bot = bot

        self.status_list = status_list
        self.interval_hours = 24  #! Currently hardcoded because decorators are selly

    # Status task
    @tasks.loop(hours=24)
    async def change_status(self):
        status = random.choice(self.status_list)
        await self.bot.change_presence(activity=status())

    # Start the loop
    @commands.Cog.listener()
    async def on_ready(self):
        self.change_status.start()
        print(f"[Core.RandomStatus] Random status loop started (Daily)")

    # Constants
    STATUS_TYPES = ["playing", "watching", "listening", "streaming", "custom"]
    FUNNY_MESSAGES = [
        Status("playing", "hit the unsell button"),
        Status("watching", "you procrastinate"),
        Status("custom", "🥔"),
        Status("custom", "There is nothing we can do."),
        Status("listening", "to the sound of silence"),
        Status("streaming", "absolutely nothing"),
    ]
