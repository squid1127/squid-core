"""A minimal example of a bot using squidcore."""


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

# Create a bot
bot = squidcore.Bot(token=bot_token, shell_channel=bot_shell, name='TestBot')

# Optional: Add a database (Required by discord explorer)
if use_db:
    postgres_pool = os.getenv("POSTGRES_POOL") if os.getenv("POSTGRES_POOL") else 20
    bot.add_db(os.getenv("POSTGRES_CONNECTION"), os.getenv("POSTGRES_PASSWORD"), int(postgres_pool))

# Run the bot
logger.info("Running bot")
bot.run()
