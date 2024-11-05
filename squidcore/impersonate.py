"""Talk as the bot to users in channels or DMs."""

import discord
from discord.ext import commands, tasks
from .shell import ShellCore, ShellCommand

import math
import datetime


class ImpersonateCore:
    def __init__(self, bot: commands.Bot, shell: ShellCore):
        self.bot = bot
        self.shell = shell

    async def active_threads(self, guildMode: bool = False, forceUpdate: bool = False):
        """Get all active threads in the shell channel."""
        # print("[Impersonate] Getting active threads.")

        if guildMode:
            if (
                hasattr(self, "active_threads_guild")
                and hasattr(self, "active_threads_guild_time")
                and not forceUpdate
            ):
                if (
                    datetime.datetime.now() - self.active_threads_guild_time
                ).seconds < 1800:
                    # print("[Impersonate] Returning cached threads.")
                    return self.active_threads_guild
        else:
            if (
                hasattr(self, "active_threads_dm")
                and hasattr(self, "active_threads_dm_time")
                and not forceUpdate
            ):
                if (
                    datetime.datetime.now() - self.active_threads_dm_time
                ).seconds < 1800:
                    # print("[Impersonate] Returning cached threads.")
                    return self.active_threads_dm

        print("[Impersonate] Updating active threads.")

        shell = self.shell.get_channel()
        threads: list[discord.Thread] = shell.threads

        threads = [
            thread for thread in threads if thread.name.split('//')[1].startswith("&&guild." if guildMode else "&&dm.")
        ]

        # Check for duplicate threads
        print("[Impersonate] Checking for duplicate threads.")
        threads_processed = []
        modified = False
        for thread in threads:
            name = thread.name.split("//")[1]
            print(f"[Impersonate] Processing thread: {name} from {thread.name}")
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

        self.active_threads_guild = (threads, thread_names)
        self.active_threads_guild_time = datetime.datetime.now()
        return (
            threads,
            thread_names,
        )
    
    async def handle(
        self, message: discord.Message = None, incoming: bool = False, dm: bool = False
    ):
        if incoming:
            if dm:
                thread = await self.get_thread(user=message.author)
                channel = message.channel
                print(
                    "[Impersonate] Incoming message from: ",
                    message.author.name,
                    " in DMs",
                )
            else:
                thread = await self.get_thread(channel=message.channel)
                guild = message.guild
                channel = message.channel
                print(
                    "[Impersonate] Incoming message from: ",
                    message.author.name,
                    " in ",
                    guild.name,
                    " - ",
                    channel.name,
                )

            # Attachments handling
            if message.attachments:
                files = []
                for attachment in message.attachments:
                    files.append(await attachment.to_file())
            else:
                files = None

            # Embeds + Embedded Message & Reply handling
            embeds = []

            if message.reference:
                ref_message = await channel.fetch_message(message.reference.message_id)

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
                description=message.content if message.content else "Empty message.",
                color=discord.Color.blurple(),
            )
            msg_embed.set_author(
                name=message.author.display_name,
                icon_url=message.author.avatar.url,
            )
            msg_embed.set_footer(
                text=f"||MSGID.{message.id}||",
            )
            embeds.append(msg_embed)

            if message.embeds:
                for embed in message.embeds:
                    embeds.append(embed)

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
                    print("[Impersonate] Creating DM channel with: ", user.name)
                    channel = await user.create_dm()
                print("[Impersonate] Outgoing message to: ", user.name)
            else:
                guild_id = thread.name.split(".")[-2]
                channel_id = thread.name.split(".")[-1].split("//")[0]
                print("[Impersonate] Outgoing message to: ", guild_id, " - ", channel_id)
                guild = self.bot.get_guild(int(guild_id))
                channel = guild.get_channel(int(channel_id))

            if message.attachments:
                files = []
                for attachment in message.attachments:
                    files.append(await attachment.to_file())
            else:
                files = None

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
                    ref_message = await channel.fetch_message(msg_id)

                    await ref_message.reply(
                        message.content,
                        embed=message.embeds[0] if message.embeds else None,
                        files=files,
                    )
                    return

            try:
                await channel.send(
                    message.content,
                    embed=message.embeds[0] if message.embeds else None,
                    files=files,
                )
            except discord.Forbidden:
                if dm:
                    await message.reply("They blocked me 😭 (Cannot send messages to user)")
                else:   
                    await message.reply("I cannot send messages to this channel.")
                    
                await message.add_reaction("❌")
                    
            except Exception as e:
                await message.reply(f"Failed to send message: {e}")             
                await message.add_reaction("❌")
                
            else:
                await message.add_reaction("✅")          

    async def get_thread(
        self, channel: discord.TextChannel = None, user: discord.User = None, **kwargs
    ):
        """Create a thread to impersonate the bot inside the shell channel."""
        print(
            "[Impersonate] Getting thread for:",
            channel.name if channel is not None else user.name,
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
            
        print("[Impersonate] Constructed thread name: ", name_readable)

        if name in thread_names:
            # Get the thread
            print("[Impersonate] Thread exists.")
            thread = thread_names[name]
        else:
            # Create a new thread
            print("[Impersonate] Thread does not exist, creating.")
            message = await self.shell.log(
                f"Creating thread for {f'{channel.guild.name} - {channel.name}' if user is None else f'{user.name}#{user.discriminator}'}.",
                title="Impersonation Thread",
                cog="ImpersonateCore",
            )
            thread = await message.create_thread(
                name=name_readable, auto_archive_duration=60
            )
            print("[Impersonate] Thread created, updating active threads.")
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


class ImpersonateGuild(commands.Cog):
    def __init__(self, bot: commands.Bot, shell: ShellCore):
        self.bot = bot
        self.shell = shell
        self.core = ImpersonateCore(bot, shell)

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
        print("[ImpersonateGuild] Ready, starting tasks.")

    async def cog_status(self):
        return f"Ready: Listening to {self.core.active_threads(guildMode=True)} active channels."

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user:
            return

        if message.guild is None:
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
            print(
                "[ImpersonateGuild] Incoming message has matching thread, processing."
            )
            await self.core.handle(message=message, incoming=True)

    async def shell_callback(self, command: ShellCommand):
        if command.name == "impersonate-guild" or command.name == "ig":
            query = command.query
            print("[ImpersonateGuild] Thread requseted with query:", query)
            
            if query == "clear":
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

            print(f"[ImpersonateGuild] {guild.name} - {channel.name}")

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
        print("[ImpersonateDM] Ready, starting tasks.")

    async def cog_status(self):
        return f"Ready: Listening to {self.core.active_threads(guildMode=False)} users."

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user:
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
        
        name = f"&&dm.{message.author.id}"
        if name in thread_names.keys():
            print(
                "[ImpersonateGuild] Incoming message has matching thread, processing."
            )
        else:
            print("[ImpersonateDM] Incoming message does not have a matching thread; creating one.")
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
            
            if query == "clear":
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
            
            print("[ImpersonateDM] Looking for user -> ", query)
            

            # Parse input
            if query.startswith("<@") and query.endswith(">"):
                try:
                    print(f"[ImpersonateDM] Looking for mention: {query}")
                    user_id = int(query[2:-1])
                    print(f"[ImpersonateDM] Found user ID: {user_id}")
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
                print(f"[ImpersonateDM] Looking for username: {query}")
                user = discord.utils.get(self.bot.users, name=query)
                if user is None:
                    await command.log(
                        f"User not found: '{query}'. Note: The user must share a mutual server with the bot. Accepted formats: @mention or username.",
                        title="DM Impersonation Parse Error",
                        msg_type="error",
                    )
                    return

            print(f"[ImpersonateDM] {user.name} (ID: {user.id})")

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

            print(f"[ImpersonateDM] Impersonation thread: {thread.name}")

            await command.log(
                f"Impersonation Thread: {thread.mention}",
                title="DM Impersonation",
                msg_type="success",
            )
