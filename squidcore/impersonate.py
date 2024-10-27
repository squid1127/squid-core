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
        print("[Impersonate] Getting active threads.")
        
        if guildMode:
            if hasattr(self, "active_threads_guild") and hasattr(self, "active_threads_guild_time") and not forceUpdate:
                if (datetime.datetime.now() - self.active_threads_guild_time).seconds < 1800:
                    print("[Impersonate] Returning cached threads.")
                    return self.active_threads_guild
        else:
            if hasattr(self, "active_threads_dm") and hasattr(self, "active_threads_dm_time") and not forceUpdate:
                if (datetime.datetime.now() - self.active_threads_dm_time).seconds < 1800:
                    print("[Impersonate] Returning cached threads.")
                    return self.active_threads_dm
                
        print("[Impersonate] Updating active threads.")

        shell = self.shell.get_channel()
        threads: list[discord.Thread] = shell.threads

        if guildMode:
            threads = [
                thread for thread in threads if thread.name.startswith("&&guild.")
            ]

            # Check for duplicate threads
            threads_processed = []
            for thread in threads:
                name = thread.name.split("//")[0]
                if name not in threads_processed:
                    threads_processed.append(name)
                else:
                    await thread.delete()

            thread_names = {}
            for thread in threads:
                name = thread.name.split("//")[0]
                thread_names[name] = thread
                
            self.active_threads_guild = (threads, thread_names)
            self.active_threads_guild_time = datetime.datetime.now()
            return (
                threads,
                thread_names,
            )
        else:
            threads = [
                thread for thread in threads if thread.name.startswith("&&DM.")
            ]

            thread_names = {}
            for thread in threads:
                name = thread.name.split("//")[0]
                thread_names[name] = thread
            self.active_threads_dm = (threads, thread_names)
            self.active_threads_dm_time = datetime.datetime.now()
            return (
                threads,
                thread_names,
            )

    async def handle(
        self, message: discord.Message = None, incoming: bool = False, **kwargs
    ):
        if incoming:
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
                embeds_chunks = [
                    embeds[i : i + 10] for i in range(0, len(embeds), 10)
                ]
                for embeds_chunk in embeds_chunks:
                    await thread.send(embeds=embeds_chunk)
                    if files:
                        await thread.send(files=files)

            await thread.send(embeds=embeds, files=files)
            
        else:
            thread = message.channel

            guild_id = thread.name.split(".")[1]
            channel_id = thread.name.split(".")[2].split("//")[0]
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

            await channel.send(
                message.content,
                embed=message.embeds[0] if message.embeds else None,
                files=files,
            )

    async def get_thread(
        self, channel: discord.TextChannel = None, user: discord.User = None, **kwargs
    ):
        """Create a thread to impersonate the bot inside the shell channel."""
        print(
            "[Impersonate] Getting thread for:",
            channel.name if channel is not None else user.name,
        )

        if channel is None:
            return

        shell = self.shell.get_channel()
        # Get all threads in shell channel
        threads, thread_names = await self.active_threads(guildMode=(user is None))

        if user is None:
            name = f"&&guild.{channel.guild.id}.{channel.id}"
            name_readable = f"{name}//{channel.guild.name} - {channel.name}"
            if len(name_readable) > 100:
                # Shorten the name if it's too long
                max_len = math.floor((100 - len(name)) // 2)

                guild_name = channel.guild.name
                if len(guild_name) > max_len:
                    guild_name = guild_name[: max_len - 3] + "..."
                channel_name = channel.name
                if len(channel_name) > max_len:
                    channel_name = channel_name[: max_len - 3] + "..."

                name_readable = f"{name}//{guild_name} - {channel_name}"

        elif user is not None:
            name = f"&&DM.{user.id}"
            name_readable = f"{name}//{user.name}#{user.discriminator}"

        print("[Impersonate] Thread name:", name_readable)

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
        print("[Impersonate] Ready, starting tasks.")

    async def cog_status(self):
        return f"Ready."
    

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
            if (
                message.channel.name.startswith("&&guild.")
                and message.channel.parent_id == self.shell.channel_id
            ):
                await self.core.handle(message=message, incoming=False)
            return

        name = f"&&guild.{message.guild.id}.{message.channel.id}"
        print(
            f"[Impersonate] Checking for thread: {name} against {self.active_threads[1]}"
        )
        if name in thread_names.keys():
            print("[Impersonate] Thread found.")
            await self.core.handle(message=message, incoming=True)

    async def shell_callback(self, command: ShellCommand):
        if command.name == "impersonate-guild" or command.name == "ig":
            query = command.query
            print("[Impersonate] Thread requseted with query:", query)

            # Discord url parsing
            if query.startswith("https://discord.com/channels/"):
                query = query.split("channels/")[1]
                guild_id = query.split("/")[0]
                channel_id = query.split("/")[1]
                try:
                    guild = self.bot.get_guild(int(guild_id))
                    channel = guild.get_channel(int(channel_id))
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

            print(f"[Impersonate] {guild.name} - {channel.name}")

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
