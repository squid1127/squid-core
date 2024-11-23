"""The most minimal example of a squid-core bot."""

import squidcore

# Environment variables
import os
from dotenv import load_dotenv

load_dotenv()
bot_token = os.getenv('BOT_TOKEN')
bot_shell = int(os.getenv('BOT_SHELL'))
print(f"Bot token: {bot_token} | Bot shell: {bot_shell}")

# Create a bot
bot = squidcore.Bot(token=bot_token, shell_channel=bot_shell, name='TestBot')

# Run the bot
bot.run()
