"""
A simple bot for checking what servers a bot is in (Using Discord explorer function). Relies solely on the core functionality of squid-core.


Environment Variables:
    - SCAN_TARGET_BOT_TOKEN: The token of the bot to scan.
    - SCAN_WORKING_CHANNEL: The ID of the channel to use as the shell channel. (To run commands)
    - POSTGRES_CONNECTION: The connection string for the PostgreSQL database. (For Dumping data)
    - POSTGRES_PASSWORD: The password for the PostgreSQL database. (For Dumping data)
    - POSTGRES_POOL: The maximum number of connections to the PostgreSQL database. (For Dumping data)

Note that a database is required for the Discord explorer function to work.
"""

#! WARNING! This example file is probably not up to date with the latest version of squidcore. Use at your own risk! Oh wait, this library is not meant for public use anyway....

#! THIS DEFINITELY WON'T WORK

import squidcore

# Environment variables
import os
from dotenv import load_dotenv

load_dotenv()
bot_token = os.getenv('SCAN_TARGET_BOT_TOKEN')
bot_shell = int(os.getenv('SCAN_WORKING_CHANNEL'))
print(f"Bot token: {bot_token} | Bot shell: {bot_shell}")

# Create a bot
bot = squidcore.Bot(token=bot_token, shell_channel=bot_shell, name='botScan')

# Bot Config
bot.dont_sync_commands()

# Add a database (Optional)
if os.getenv("SCAN_USE_DB"):
    postgres_pool = os.getenv("POSTGRES_POOL") if os.getenv("POSTGRES_POOL") else 20
    bot.add_db(os.getenv("POSTGRES_CONNECTION"), os.getenv("POSTGRES_PASSWORD"), int(postgres_pool))

@bot.listen('on_ready')
async def startup_message():
    await bot.shell.log(
        "Bot ready. To explore servers, use `botscan xp`. To sync with database, use `botscan db discord index-all`.",
        title="BotScan",
        cog="Core",
        msg_type="info",
    )

# Run the bot
bot.run()
