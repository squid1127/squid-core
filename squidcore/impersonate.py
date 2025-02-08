"""Talk as the bot to users in channels or DMs."""

import discord
from discord.ext import commands, tasks
from .shell import ShellCore, ShellCommand

import math
import time

import datetime, timedelta

import logging

logger = logging.getLogger("core.impersonate")


class ImpersonateCore:
    def __init__(self, bot: commands.Bot, shell: ShellCore):
        self.bot = bot
        self.shell = shell

        self.active_threads_dm = None
        self.active_threads_dm_time = 0
        self.active_threads_guild = None
        self.active_threads_guild_time = 0

    async def active_threads(self, guildMode: bool = False, forceUpdate: bool = False):
        """Get all active threads in the shell channel."""

        logger.debug(f"Request for active {'guild' if guildMode else 'DM'} threads.")

        if forceUpdate:
            logger.info("Forcing update of active threads.")

        else:
            if guildMode:
                if hasattr(self, "active_threads_guild") and hasattr(
                    self, "active_threads_guild_time"
                ):
                    # logger.info(f"Cached threads found. | Cached time: {self.active_threads_guild_time} | Current time: {time.time()} | Time difference: {time.time() - self.active_threads_guild_time}")
                    if time.time() - self.active_threads_guild_time < 1800:
                        # logger.info("Returning cached threads.")
                        logger.debug("Using cached guild threads.")
                        return self.active_threads_guild
                    else:
                        logger.warning("Cached threads found, but expired.")
                else:
                    logger.warning("No cached threads found.")

            else:
                if hasattr(self, "active_threads_dm") and hasattr(
                    self, "active_threads_dm_time"
                ):
                    # logger.info(f"Cached threads found. | Cached time: {self.active_threads_dm_time} | Current time: {time.time()} | Time difference: {time.time() - self.active_threads_dm_time}")
                    if time.time() - self.active_threads_dm_time < 1800:
                        # logger.info("Returning cached threads.")
                        logger.debug("Using cached DM threads.")
                        return self.active_threads_dm
                    else:
                        logger.warning("Cached threads found, but expired.")
                else:
                    logger.warning("No cached threads found.")

        logger.info(f"Updating active { 'guild' if guildMode else 'DM' } threads.")

        shell = self.shell.get_channel()

        if shell is None:
            logger.error("Failed to fetch threads: Shell channel not found.")
            return

        threads: list[discord.Thread] = shell.threads

        threads = [
            thread
            for thread in threads
            if thread.name.split("//")[1].startswith(
                "&&guild." if guildMode else "&&dm."
            )
        ]

        # Check for duplicate threads
        logger.info("Checking for duplicate threads.")
        threads_processed = []
        modified = False
        for thread in threads:
            name = thread.name.split("//")[1]
            # logger.info(f"Processing thread: {name} from {thread.name}")
            if name not in threads_processed:
                threads_processed.append(name)
            else:
                try:
                    await thread.delete()
                    modified = True
                except:
                    await self.shell.log(
                        f"Failed to delete duplicate thread: {thread.name}",
                        title="Impersonate Thread Cleanup",
                        cog="ImpersonateCore",
                    )

        thread_names = {}
        for thread in threads:
            name = thread.name.split("//")[1]
            thread_names[name] = thread

        logger.info("Active threads updated.")

        if guildMode:
            self.active_threads_guild = (threads, thread_names)
            self.active_threads_guild_time = time.time()

            return self.active_threads_guild
        else:
            self.active_threads_dm = (threads, thread_names)
            self.active_threads_dm_time = time.time()

            return self.active_threads_dm

    async def generate_embeds(self, message: discord.Message) -> list[discord.Embed]:
        """Generate embeds for a given message."""
        embeds = []
        
        empty_message = "Empty message."
        if len(message.embeds) > 0:
            empty_message = "See Embeds"
        if len(message.attachments) > 0:
            empty_message = "See Attachments"
            

        if message.reference:
            try:
                ref_message = await message.channel.fetch_message(
                    message.reference.message_id
                )
            except:
                ref_message = None
            else:
                ref_embed = discord.Embed(
                    description=(
                        ref_message.content if ref_message.content else "Empty message."
                    ),
                    title="Replying to:",
                    color=discord.Color.red(),
                )
                ref_embed.set_author(
                    name=ref_message.author.display_name,
                    icon_url=ref_message.author.avatar.url,
                )
                embeds.append(ref_embed)
                if ref_message.embeds:
                    for embed in ref_message.embeds:
                        embeds.append(embed)

        msg_embed = discord.Embed(
            description=message.content if message.content else empty_message,
            color=discord.Color.blurple(),
        )
        
        # Special user handling
        if message.author == self.bot.user:
            msg_embed.color = discord.Color.green()
            msg_embed.set_author(
                name=f"{self.bot.user.display_name} (Me)",
                icon_url=self.bot.user.avatar.url,
            )
        else:
            msg_embed.set_author(
                name=message.author.display_name,
                icon_url=message.author.avatar.url,
            )
            

        msg_embed.set_footer(
            text=f"||MSGID.{message.id}||",
        )
        msg_embed.timestamp = message.created_at
        embeds.append(msg_embed)

        if message.embeds:
            for embed in message.embeds:
                embeds.append(embed)

        return embeds

    async def handle(
        self, message: discord.Message = None, incoming: bool = False, dm: bool = False
    ):
        if incoming:
            if dm:
                thread = await self.get_thread(user=message.author)
                channel = message.channel
                logger.info(
                    "Incoming message from: " + message.author.name + " in DMs",
                )
            else:
                thread = await self.get_thread(channel=message.channel)
                guild = message.guild
                channel = message.channel
                logger.info(
                    "Incoming message from: "
                    + message.author.name
                    + " in "
                    + guild.name
                    + " - "
                    + channel.name,
                )

            # Attachments handling
            if message.attachments:
                files = []
                for attachment in message.attachments:
                    files.append(await attachment.to_file())
            else:
                files = None

            # Embeds + Embedded Message & Reply handling
            embeds = await self.generate_embeds(message)

            if len(embeds) > 10:
                # Split the embeds into chunks of 10
                embeds_chunks = [embeds[i : i + 10] for i in range(0, len(embeds), 10)]
                for embeds_chunk in embeds_chunks:
                    await thread.send(embeds=embeds_chunk)
                    if files:
                        await thread.send(files=files)

            await thread.send(embeds=embeds, files=files)

        else:
            thread = message.channel

            if dm:
                user_id = thread.name.split(".")[-1]
                user = self.bot.get_user(int(user_id))
                channel = user.dm_channel
                if channel is None:
                    logger.info("Creating DM channel with: ", user.name)
                    channel = await user.create_dm()
                logger.info("Outgoing message to: ", user.name)
            else:
                guild_id = thread.name.split(".")[-2]
                channel_id = thread.name.split(".")[-1].split("//")[0]
                logger.info("Outgoing message to: " + guild_id + " - " + channel_id)
                guild = self.bot.get_guild(int(guild_id))
                channel = guild.get_channel(int(channel_id))

            if message.attachments:
                files = []
                for attachment in message.attachments:
                    files.append(await attachment.to_file())
            else:
                files = None

            reply_to = None
            if message.reference:
                ref_message = await thread.fetch_message(message.reference.message_id)

                ref_embeds = []
                for embed in ref_message.embeds:
                    if embed.footer.text is None:
                        continue
                    if embed.footer.text.startswith("||MSGID."):
                        text = embed.footer.text
                        # Extract the message ID from the footer
                        # Extract digits from the text
                        msg_id = int("".join(filter(str.isdigit, text)))
                        break
                else:
                    msg_id = None

                if msg_id:
                    reply_to = await channel.fetch_message(msg_id)

            try:
                if reply_to:
                    await reply_to.reply(
                        message.content,
                        embed=message.embeds[0] if message.embeds else None,
                        files=files,
                    )
                else:
                    await channel.send(
                        message.content,
                        embed=message.embeds[0] if message.embeds else None,
                        files=files,
                    )

            except discord.Forbidden:
                if dm:
                    await message.reply(
                        "They blocked me 😭 (Cannot send messages to user)"
                    )
                else:
                    # Check for timeout
                    if channel.guild.me.is_timed_out():
                        await message.reply("Somebody put me in the timeout corner 😭")
                    else:
                        await message.reply("I cannot send messages to this channel.")

                await message.add_reaction("❌")

            except Exception as e:
                await message.reply(f"Failed to send message: {e}")
                await message.add_reaction("❌")

            else:
                if dm:
                    await message.add_reaction("✅")
                else:
                    await message.delete()
                # await message.add_reaction("✅")

    async def get_thread(
        self, channel: discord.TextChannel = None, user: discord.User = None, **kwargs
    ):
        """Create a thread to impersonate the bot inside the shell channel."""
        logger.info(
            "Getting thread for:" + channel.name if channel is not None else user.name,
        )

        if channel is None and user is None:
            return

        shell = self.shell.get_channel()
        # Get all threads in shell channel
        threads, thread_names = await self.active_threads(guildMode=(user is None))

        if user is None:
            name = f"&&guild.{channel.guild.id}.{channel.id}"
            guild_name = channel.guild.name.replace("//", "slashslash")
            channel_name = channel.name

            name_readable = f"{guild_name} - {channel_name}//{name}"
            if len(name_readable) > 100:
                # Shorten the name if it's too long
                max_len = math.floor((100 - len(name)) // 2)

                if len(guild_name) > max_len:
                    guild_name = guild_name[: max_len - 3] + "..."
                if len(channel_name) > max_len:
                    channel_name = channel_name[: max_len - 3] + "..."

                name_readable = f"{guild_name} - {channel_name}//{name}"

        else:
            name = f"&&dm.{user.id}"
            name_readable = f"{user.name}//{name}"

        logger.info("Constructed thread name: " + name_readable)

        if name in thread_names:
            # Get the thread
            logger.info("Thread exists.")
            thread = thread_names[name]
        else:
            # Create a new thread
            logger.info("Thread does not exist, creating.")
            message = await self.shell.log(
                f"Creating thread for {f'{channel.guild.name} - {channel.name}' if user is None else f'{user.name}#{user.discriminator}'}.",
                title="Impersonation Thread",
                cog="ImpersonateCore",
            )
            thread = await message.create_thread(
                name=name_readable, auto_archive_duration=60
            )

            # Populate the thread
            if user is None:
                await self.populate_thread(thread, channel=channel)
            else:
                await self.populate_thread(thread, user=user)

            logger.info("Thread created, updating active threads.")
            await self.active_threads(guildMode=(user is None), forceUpdate=True)
            await thread.send(
                embed=discord.Embed(
                    description="Thread created for impersonation.",
                    title="Impersonation Thread",
                )
            )

        return thread

    async def clear(self, guild: bool = False, dm: bool = False):
        if (not guild) and (not dm):
            raise ValueError("No mode selected (guild or dm)")

        if guild:
            threads, thread_names = await self.active_threads(guildMode=True)
            for thread in threads:
                await thread.delete()
            await self.active_threads(guildMode=True, forceUpdate=True)

        if dm:
            threads, thread_names = await self.active_threads(guildMode=False)
            for thread in threads:
                await thread.delete()
            await self.active_threads(guildMode=False, forceUpdate=True)

    async def populate_thread(
        self,
        thread: discord.Thread,
        channel: discord.TextChannel = None,
        user: discord.User = None,
        hours: int = 24,
    ):
        """Populate a thread with messages from a channel.

        Args:
            thread (discord.Thread): The thread to populate.
            channel (discord.TextChannel): The channel to populate the thread with. (Channel mode)
            user (discord.User): The user to populate the thread with. (DM mode)
            hours (int): The number of hours to populate the thread with. Use None to populate all messages.

        Returns:
            discord.Thread: The populated thread.
        """

        if channel is None and user is None:
            raise ValueError("No channel or user specified.")

        if channel is None and user is not None:
            channel = user.dm_channel

        # Retrieve messages
        try:
            messages = []
            async for message in channel.history(
                limit=None,
                after=(datetime.datetime.now() - datetime.timedelta(hours=hours)),
            ):
                messages.append(message)
        except AttributeError:
            logger.info("No message history found.")
            return thread

        if not messages:
            return thread

        # Sort messages by time
        messages.sort(key=lambda message: message.created_at)

        # Populate the thread
        for message in messages:
            try:
                embeds = await self.generate_embeds(message)
                await thread.send(
                    content="",
                    embeds=embeds,
                    files=[
                        await attachment.to_file() for attachment in message.attachments
                    ],
                )
            except Exception as e:
                await self.shell.log(
                    f"Failed to populate thread: {e}",
                    title="Impersonation Thread Population Error",
                    cog="ImpersonateCore",
                )
                break

        return thread


class ImpersonateGuild(commands.Cog):
    def __init__(self, bot: commands.Bot, shell: ShellCore):
        self.bot = bot
        self.shell = shell
        self.core = ImpersonateCore(bot, shell)

        self.logger = logging.getLogger("core.impersonate.guild")

        shell.add_command(
            "impersonate-guild",
            "ImpersonateGuild",
            "Impersonate the bot in a guild channel",
        )
        shell.add_command(
            "ig",
            "ImpersonateGuild",
            "(Alias for impersonate-guild) Impersonate the bot in a guild channel",
        )

    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.info("Ready, starting tasks.")

    async def cog_status(self):
        active_threads = await self.core.active_threads(guildMode=True)

        return f"Ready: Listening to {len(active_threads[0])} guild channels."

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # if message.author == self.bot.user:
        #     return

        if message.guild is None:
            return

        if self.bot.is_ready() is False:
            self.logger.error("Failed to process message: Bot is not ready.")
            return

        threads, thread_names = await self.core.active_threads(guildMode=True)

        if not hasattr(self, "active_threads"):
            try:
                self.active_threads = await self.core.active_threads(guildMode=True)
            except:
                return

        if isinstance(message.channel, discord.Thread):
            if message.author.bot:
                return
            name_without_slash = message.channel.name.split("//")[1]
            if name_without_slash is None or name_without_slash == "":
                return
            if (
                name_without_slash.startswith("&&guild.")
                and message.channel.parent_id == self.shell.channel_id
            ):
                await self.core.handle(message=message, incoming=False)
            return

        name = f"&&guild.{message.guild.id}.{message.channel.id}"
        if name in thread_names.keys():
            self.logger.info("Incoming message has matching thread, processing.")
            await self.core.handle(message=message, incoming=True)

    async def shell_callback(self, command: ShellCommand):
        if command.name == "impersonate-guild" or command.name == "ig":
            query = command.query
            self.logger.info("Thread requseted with query:", query)

            # * Special commands
            if query == "!clear":
                try:
                    await self.core.clear(guild=True)
                except Exception as e:
                    await command.log(
                        f"Failed to clear guild threads: {e}",
                        title="Guild Impersonation Clear Error",
                        msg_type="error",
                    )
                    return
                await command.log(
                    "Cleared all active guild threads.",
                    title="Guild Impersonation Clear",
                    msg_type="success",
                )
                return
            elif query == "!list" or query == "!ls":
                threads, thread_names = await self.core.active_threads(guildMode=True)
                if not threads:
                    await command.log(
                        "No active guild threads found.",
                        title="Guild Impersonation List",
                        msg_type="info",
                    )
                    return
                thread_list = []
                for thread in threads:
                    name = thread.name.split("//")[0]
                    thread_list.append(name)
                seperator = "\n- "
                await command.log(
                    f"Active guild threads: \n- {seperator.join(thread_list)}",
                    title="Guild Impersonation List",
                    msg_type="info",
                )
                return
            elif query == "!update":
                await self.core.active_threads(guildMode=True, forceUpdate=True)
                await command.log(
                    "Updated active guild threads.",
                    title="Guild Impersonation Update",
                    msg_type="success",
                )
                return

            elif query == "" or query is None or query == "!help":
                await command.log(
                    "Impersonate the bot in a guild channel. Accepted formats: Guild ID::Channel ID, Discord URL, or Channel Mention. Special commands: !clear, !list, !update.",
                    title="Guild Impersonation Help",
                    msg_type="info",
                )
                return

            # Discord url parsing
            if query.startswith("https://discord.com/channels/"):
                query = query.split("channels/")[1]
                guild_id = query.split("/")[0]
                channel_id = query.split("/")[1]
                try:
                    guild = self.bot.get_guild(int(guild_id))
                    if guild is None:
                        await command.log(
                            f"Guild not found: {guild_id}",
                            title="Guild Impersonation Parse Error",
                            msg_type="error",
                        )
                        return
                    channel = guild.get_channel(int(channel_id))
                    if channel is None:
                        await command.log(
                            f"Channel not found: {channel_id} in {guild.name}",
                            title="Guild Impersonation Parse Error",
                            msg_type="error",
                        )
                        return
                except Exception as e:
                    await command.log(
                        f"Failed to get guild and channel: {e} (Discord URL)",
                        title="Guild Impersonation Parse Error",
                        msg_type="error",
                    )
                    return
            elif len(query.split("::")) == 2:
                guild_id = query.split("::")[0]
                channel_id = query.split("::")[1]
                try:
                    guild = self.bot.get_guild(int(guild_id))
                    channel = guild.get_channel(int(channel_id))
                except Exception as e:
                    await command.log(
                        f"Failed to get guild and channel: {e} (Guild ID::Channel ID)",
                        title="Guild Impersonation Parse Error",
                        msg_type="error",
                    )
                    return
            elif query.startswith("<#") and query.endswith(">"):
                channel_id = query[2:-1]
                try:
                    guild = command.channel.guild
                    channel = guild.get_channel(int(channel_id))
                except Exception as e:
                    await command.log(
                        f"Failed to get channel: {e} (Channel Mention). Note: The channel must be in the same guild as the shell channel. To impersonate a channel in another guild, use the Guild ID::Channel ID format or a Discord URL.",
                        title="Guild Impersonation Parse Error",
                        msg_type="error",
                    )
            else:
                await command.log(
                    f"Invalid query: {query}",
                    title="Guild Impersonation Parse Error",
                    msg_type="error",
                )
                return

            self.logger.info(
                f"Requesting thread for {guild.name} - {channel.name} ({guild.id}::{channel.id})"
            )

            try:
                thread = await self.core.get_thread(channel=channel)
            except Exception as e:
                await command.log(
                    f"Failed to impersonate guild: {e}",
                    title="Guild Impersonation Error",
                    msg_type="error",
                )
                return

            await command.log(
                f"Impersonation Thread: {thread.mention}",
                title="Guild Impersonation",
                msg_type="success",
            )


class ImpersonateDM(commands.Cog):
    def __init__(self, bot: commands.Bot, shell: ShellCore):
        self.bot = bot
        self.shell = shell
        self.core = ImpersonateCore(bot, shell)

        self.logger = logging.getLogger("core.impersonate.dm")

        shell.add_command(
            "impersonate-dm",
            "ImpersonateDM",
            "DM a user as the bot",
        )
        shell.add_command(
            "idm",
            "ImpersonateDM",
            "(Alias for impersonate-dm) DM a user as the bot",
        )

    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.info("Ready, starting tasks.")

    async def cog_status(self):
        active_threads = await self.core.active_threads(guildMode=False)

        return f"Ready: Listening to {len(active_threads[0])} DMs."

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

        if self.bot.is_ready() is False:
            self.logger.error("Could not process message: Bot is not ready.")
            return

        threads, thread_names = await self.core.active_threads(guildMode=False)

        if not hasattr(self, "active_threads"):
            try:
                self.active_threads = await self.core.active_threads(guildMode=False)
            except:
                return

        if isinstance(message.channel, discord.Thread):
            if message.author.bot:
                return
            name_without_slash = message.channel.name.split("//")[1]
            if name_without_slash is None or name_without_slash == "":
                return
            if (
                name_without_slash.startswith("&&dm.")
                and message.channel.parent_id == self.shell.channel_id
            ):
                await self.core.handle(message=message, incoming=False, dm=True)

        if not isinstance(message.channel, discord.DMChannel):
            return
        
        if message.author == self.bot.user:
            return

        name = f"&&dm.{message.author.id}"
        if name in thread_names.keys():
            self.logger.info("Incoming message has matching thread, processing.")
        else:
            self.logger.info(
                "Incoming message does not have a matching thread; creating one."
            )
            await self.shell.log(
                f"Detected incoming message from {message.author.mention} ({message.author.name}). Creating thread for DM impersonation.",
                title="DM Impersonation",
                cog="ImpersonateDM",
            )
            try:
                thread = await self.core.get_thread(user=message.author)
            except Exception as e:
                await self.shell.log(
                    f"Error while launching DM thread: {e}",
                    title="DM Impersonation Error",
                    cog="ImpersonateDM",
                )
                return

        await self.core.handle(message=message, incoming=True, dm=True)

    async def shell_callback(self, command: ShellCommand):
        if command.name == "impersonate-dm" or command.name == "idm":
            query = command.query
            self.logger.info("Thread requested with query:", query)

            # * Special commands
            if query == "!clear":
                try:
                    await self.core.clear(dm=True)
                except Exception as e:
                    await command.log(
                        f"Failed to clear DM threads: {e}",
                        title="DM Impersonation Clear Error",
                        msg_type="error",
                    )
                    return
                await command.log(
                    "Cleared all active DM threads.",
                    title="DM Impersonation Clear",
                    msg_type="success",
                )
                return
            elif query == "!list" or query == "!ls":
                threads, thread_names = await self.core.active_threads(guildMode=False)
                if not threads:
                    await command.log(
                        "No active DM threads found.",
                        title="DM Impersonation List",
                        msg_type="info",
                    )
                    return
                thread_list = []
                for thread in threads:
                    name = thread.name.split("//")[0]
                    thread_list.append(name)
                seperator = "\n- "
                await command.log(
                    f"Active DM threads: \n- {seperator.join(thread_list)}",
                    title="DM Impersonation List",
                    msg_type="info",
                )
                return
            elif query == "!update":
                await self.core.active_threads(guildMode=False, forceUpdate=True)
                await command.log(
                    "Updated active DM threads.",
                    title="DM Impersonation Update",
                    msg_type="success",
                )
                return
            elif query == "" or query is None or query == "!help":
                await command.log(
                    "DM a user as the bot. Accepted formats: @mention or username. Special commands: !clear, !list, !update.",
                    title="DM Impersonation Help",
                    msg_type="info",
                )
                return

            # Parse input
            if query.startswith("<@") and query.endswith(">"):
                try:
                    self.logger.info(f"Looking for mention: {query}")
                    user_id = int(query[2:-1])
                    self.logger.info(f"Found user ID: {user_id}")
                    user = self.bot.get_user(user_id)
                except:
                    await command.log(
                        f"Failed to get user: {query} (User Mention). Note: The user must share a mutual server with the bot. Accepted formats: @mention or username.",
                        title="DM Impersonation Parse Error",
                        msg_type="error",
                    )
                    return
                if user is None:
                    await command.log(
                        f"User not found: {query}. Note: The user must share a mutual server with the bot. Accepted formats: @mention or username.",
                        title="DM Impersonation Parse Error",
                        msg_type="error",
                    )
                    return
            else:
                self.logger.info(f"Looking for username: {query}")
                user = discord.utils.get(self.bot.users, name=query)
                if user is None:
                    await command.log(
                        f"User not found: '{query}'. Note: The user must share a mutual server with the bot. Accepted formats: @mention or username.",
                        title="DM Impersonation Parse Error",
                        msg_type="error",
                    )
                    return

            self.logger.info(f"Requesting thread for {user.name} ({user.id})")

            try:
                thread = await self.core.get_thread(user=user)
            except Exception as e:
                await command.log(
                    f"Error while launching DM thread: {e}",
                    title="DM Impersonation Error",
                    msg_type="error",
                )
                return

            if thread is None:
                await command.log(
                    f"Failed to create thread for {user.mention} ({user.name}): Something went wrong when creating the thread.",
                    title="DM Impersonation Error",
                    msg_type="error",
                )
                return

            self.logger.info(f"Impersonation thread: {thread.name}")

            await command.log(
                f"Impersonation Thread: {thread.mention}",
                title="DM Impersonation",
                msg_type="success",
            )
