"""A minimal example of a bot using squidcore."""

#! WARNING! This example file is probably not up to date with the latest version of squidcore. Use at your own risk! Oh wait, this library is not meant for public use anyway....

#* Variables

# Required
use_db = True # Whether to use a database or not (Will need to pass in environment variables for this)

# Optional if using environment variables
bot_token = "" # The token of the bot (From the Discord Developer Portal)
bot_shell = 0 # The channel ID of the shell channel (Where the bot will listen for commands)

#* Main
import squidcore
import logging

# Configure logging
logger = logging.getLogger('main')

# Environment variables
import os
from dotenv import load_dotenv

load_dotenv()
bot_token = os.getenv('BOT_TOKEN') if bot_token == "" else bot_token
bot_shell = int(os.getenv('BOT_SHELL')) if bot_shell == 0 else bot_shell
logger.info(f"Bot token: {bot_token} | Bot shell: {bot_shell}")

# Optional: Add a database
if use_db:
    memory = squidcore.Memory(redis=True, mongo=True, from_env=True)
else:
    memory = None

# Create a bot
bot = squidcore.Bot(token=bot_token, shell_channel=bot_shell, name='TestBot', memory=memory)

# Run the bot
logger.info("Running bot")
bot.run()
