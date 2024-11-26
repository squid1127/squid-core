"""A bot designed to be the most minimal example of a squid-core bot."""

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

# Optional: Add a database (Required by discord explorer)
# postgres_pool = os.getenv("POSTGRES_POOL") if os.getenv("POSTGRES_POOL") else 20
# bot.add_db(os.getenv("POSTGRES_CONNECTION"), os.getenv("POSTGRES_PASSWORD"), int(postgres_pool))

# Run the bot
bot.run()
