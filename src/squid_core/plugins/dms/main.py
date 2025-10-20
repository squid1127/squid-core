"""Main module for the DMS plugin."""

from squid_core.framework import Framework
from squid_core.components.cli import CLIContext, EmbedLevel
from squid_core.plugin_base import Plugin as PluginBase, PluginCog, PluginComponent
from squid_core.decorators import DiscordEventListener, CLICommandDec
from discord.ext import commands
import discord
import io
from dataclasses import dataclass

from .config import DMConfig

class DMPlugin(PluginBase):
    def __init__(self, framework: Framework) -> None:
        super().__init__(framework)
        self.cog = DMCog(self)
        self.config: DMConfig | None = None
        self.cli = DMCommandLine(self)
        self.thread_generator = ThreadGenerator(self)

    async def load(self) -> None:
        self.logger.info("DM plugin loading...")

        # Load configuration
        self.config = await DMConfig.resolve(self.fw.config, self)

        # Add Cog to the bot
        await self.fw.bot.auto_add_cog(self.cog, reload=True)

    async def unload(self) -> None:
        self.logger.info("DM plugin unloading...")
        await self.fw.bot.remove_cog(self.cog.qualified_name)

class DMCommandLine(PluginComponent):
    """CLI commands for the DM plugin."""

    def __init__(self, plugin: DMPlugin) -> None:
        super().__init__(plugin)
        self.plugin: DMPlugin = plugin
        
    @CLICommandDec(
        name="dm",
        aliases=["dms"],
        description="Fetch a DM thread for a user.",
    )
    async def dm_command(self, context: CLIContext) -> None:
        """A sample DM command."""
        
        target = context.args[0] if context.args else ""
        if not target:
            await context.respond(
                "Please provide a user ID, username, or mention to fetch the DM thread.",
                title="DM Command | Missing Target",
                level=EmbedLevel.ERROR,
            )
            return
        
        # Parse the target into a uid, username, or mention
        user: discord.User | None = None
        if target.isdigit():
            uid = int(target)
            try:
                user = await self.plugin.fw.bot.fetch_user(uid)
            except Exception as e:
                await context.respond_exception(
                    title=f"DM Command | Fetch Error",
                    exception=e,
                )
        elif target.startswith("<@") and target.endswith(">"):
            # Mention format
            uid_str = target.replace("<@", "").replace("!", "").replace(">", "")
            if uid_str.isdigit():
                uid = int(uid_str)
                try:
                    user = await self.plugin.fw.bot.fetch_user(uid)
                except Exception as e:
                    await context.respond(
                        f"Failed to fetch user with ID {uid}: {e}",
                        title="DM Command | Fetch Error",
                        level=EmbedLevel.ERROR,
                    )
                    return
        else:
            # Try to find by username (not guaranteed to be unique)
            for member in self.plugin.fw.bot.users:
                if member.name == target or f"{member.name}#{member.discriminator}" == target:
                    user = member
                    break
            if not user:
                await context.respond(
                    f"Could not find a user with username '{target}'.",
                    title="DM Command | User Not Found",
                    level=EmbedLevel.ERROR,
                )
                return
            
        # Get or create the DM thread
        thread = await self.plugin.thread_generator.get_for_user(user)
        if not thread:
            await context.respond(
                f"Failed to get or create a DM thread for user {user}.",
                title="DM Command | Error",
                level=EmbedLevel.ERROR,
            )
            return
        await context.respond(
            f"DM thread for user {user} is available: {thread.mention}",
            title="DM Command | Success",
            level=EmbedLevel.SUCCESS,
        )

class DMCog(PluginCog):
    """Cog for handling DM-related commands and events."""

    def __init__(self, plugin: DMPlugin) -> None:
        super().__init__(plugin)  # Sidenote, this is kinda unnecessary
        self.plugin: DMPlugin = plugin  # Override type for convenience
        self.plugin.logger.info("DMCog initialized.")

    # @commands.Cog.listener()
    @DiscordEventListener()
    async def on_message(self, message: discord.Message) -> None:
        if isinstance(message.channel, discord.DMChannel):
            await self.on_dm(message)
        elif isinstance(message.channel, discord.Thread):
            await self.on_thread(message.channel, message)

    async def on_dm(self, message: discord.Message, skip_checks: bool = False) -> None:
        # Capture bot messages that are not from the bot itself
        if not skip_checks:
            if message.author.bot and message.author == self.bot.user:
                return  # Ignore messages this bot sends

        # Determine user
        user = self.plugin.thread_generator.cache_get_dm_channel_recipient(message.channel)
        if user:
            self.plugin.logger.info(f"Using cached user for DM channel {message.channel.id}: {user.id}")
        else:
            channel_info = self.fw.bot.get_channel(message.channel.id)
            user = channel_info.recipient if channel_info else None
            if not user:
                # Fallback: Message author
                user = message.author

        # Handle incoming DM
        thread = await self.plugin.thread_generator.get_for_user(user)
        if not thread:
            self.plugin.logger.error(
                f"Failed to get or create thread for user {user.id}"
            )
            return

        # Forward the message to the thread
        response = await self.plugin.thread_generator.transform_message(
            message, embed_mode=True, send_method=thread.send
        )

    async def on_thread(self, thread: discord.Thread, message: discord.Message) -> None:
        """Handle messages in threads where the parent is a CLI channel."""
        if not thread.parent_id in self.plugin.fw.cli.allowed_channel_ids:
            return  # Not a CLI channel thread
        if message.author.bot and (
            message.author == self.bot.user
            or not self.plugin.config.capture_bot_messages
        ):
            return  # Ignore messages this bot sends or all bot messages if configured

        # Get the user associated with this thread
        user = await self.plugin.thread_generator.get_user_from_thread(thread)
        if not user:
            self.plugin.logger.error(f"Failed to get user from thread {thread.id}")
            return

        # Forward the message to the user
        try:
            dm_channel = user.dm_channel
            if dm_channel is None:
                dm_channel = await user.create_dm()
            response = await self.plugin.thread_generator.transform_message(
                message,
                embed_mode=False,
                native_reply_mode=True,
                destination=dm_channel,
                send_method=dm_channel.send,
                native_reply_mode_auto_send=True,
            )  # False to make it appear the bot is sending directly + native replies
        except Exception as e:
            self.plugin.logger.error(
                f"Failed to send message to user {user.id} from thread {thread.id}: {e}"
            )
            await message.add_reaction("❌")  # Indicate failure
            return
        

        try:
            new_message = response[0] if isinstance(response, list) else response
            # Delete the original message and create a transformed message
            await message.delete()
            await self.on_dm(
                new_message, skip_checks=True
            )  # Process the new message as a DM
        except Exception:
            # Fallback: Just react
            try:
                await message.add_reaction("✅")  # Acknowledge the message was sent
            except discord.NotFound:
                pass
class ThreadGenerator(PluginComponent):
    """Utility class to generate and manage threads for DMs."""

    def __init__(self, plugin: DMPlugin) -> None:
        super().__init__(plugin)
        self.plugin: DMPlugin = plugin
        self.cache: list[CachedThread] = []

    def generate_thread_name(self, uid: int) -> str:
        """Generate a thread name based on user ID."""
        return f"{self.plugin.config.thread_prefix}{uid}"

    def generate_thread_name_friendly(self, user: discord.User) -> str:
        """Generate a thread name based on user ID with friendly username."""
        safe_name = "".join(
            c for c in user.name if c.isalnum() or c in (" ", "-", "_")
        ).rstrip()
        return f"{self.plugin.config.thread_prefix}{user.id}//{safe_name}"
    
    def cache_get_thread(self, user: discord.User) -> discord.Thread | None:
        """Get a cached thread for the given user, if it exists."""
        for cached in self.cache:
            if cached.user.id == user.id:
                return cached.thread
        return None

    def cache_get_user(self, thread: discord.Thread) -> discord.User | None:
        """Get a cached user for the given thread, if it exists."""
        for cached in self.cache:
            if cached.thread.id == thread.id:
                return cached.user
        return None
    
    def cache_get_dm_channel_recipient(self, dm_channel: discord.DMChannel) -> discord.User | None:
        """Get a cached user for the given DM channel, if it exists."""
        for cached in self.cache:
            if cached.dm_channel and cached.dm_channel.id == dm_channel.id:
                return cached.user
        return None
    
    def cache_add(self, user: discord.User, thread: discord.Thread, dm_channel: discord.DMChannel | None) -> None:
        """Add a user-thread-dm_channel mapping to the cache."""
        self.cache.append(CachedThread(user=user, thread=thread, dm_channel=dm_channel))

    async def get_for_user(self, user: discord.User) -> discord.Thread | None:
        """Get or create a thread for the given user."""
        name = self.generate_thread_name(
            user.id
        )  # Base name without friendly part (for lookup)
        name_friendly = self.generate_thread_name_friendly(
            user
        )  # Friendly part comment-style for end-users
        
        # Check cache first
        cached_thread = self.cache_get_thread(user)
        if cached_thread:
            self.plugin.logger.info(
                f"Using cached thread for user {user.id}: {cached_thread.id}"
            )
            return cached_thread

        parent = self.plugin.fw.bot.get_channel(
            self.plugin.fw.cli.allowed_channel_ids[0]
        )  # Use the first allowed CLI channel as parent
        if not isinstance(parent, discord.TextChannel):
            self.plugin.logger.error("Parent channel for threads is not a TextChannel.")
            return None

        # Find an existing thread or create a new one
        for thread in parent.threads:
            # remove friendly part for comparison
            thread_name = thread.name.split("//")[0]
            if thread_name == name:
                self.plugin.logger.info(
                    f"Found existing thread for user {user.id}: {thread.id}"
                )
                self.cache_add(user, thread, user.dm_channel)
                return thread

        self.plugin.logger.info(f"Creating new thread for user {user.id}: {name}")

        # Create info message
        messages = await self.plugin.fw.cli.notify(
            title="New DM Thread Created",
            description=f"Creating a DM thread for user {user} (ID: {user.id}).",
            level=EmbedLevel.INFO,
            plugin=self.plugin.name,
        )
        for message in messages:
            if message.channel.id == parent.id:
                message_reference = message
                break
        else:
            message_reference = None
        new_thread = await parent.create_thread(
            message=message_reference, name=name_friendly, auto_archive_duration=60
        )
        # Cache the new thread
        self.cache_add(user, new_thread, user.dm_channel)
        return new_thread

    async def get_user_from_thread(self, thread: discord.Thread) -> discord.User | None:
        """Extract the user associated with a given thread."""
        # Check cache first
        cached_user = self.cache_get_user(thread)
        if cached_user:
            self.plugin.logger.info(
                f"Using cached user for thread {thread.id}: {cached_user.id}"
            )
            return cached_user

        try:
            # Extract user ID from thread name
            base_name = thread.name.split("//")[0]  # Remove friendly part
            uid_str = base_name.replace(f"{self.plugin.config.thread_prefix}", "")
            uid = int(uid_str)
            user = await self.plugin.fw.bot.fetch_user(uid)
            return user
        except Exception as e:
            self.plugin.logger.error(f"Failed to get user from thread {thread.id}: {e}")
            return None

    async def attachment_to_file(self, attachment: discord.Attachment) -> discord.File:
        """Convert a Discord attachment to a Discord file for forwarding."""
        data = await attachment.read()
        return discord.File(fp=io.BytesIO(data), filename=attachment.filename)

    async def transform_message(
        self,
        message: discord.Message,
        embed_mode: bool = False,
        native_reply_mode: bool = False,
        destination: discord.TextChannel | None = None,
        send_method: callable = None,
        native_reply_mode_auto_send: bool = False,
    ) -> dict | list[discord.Message]:
        """
        Format a message for forwarding to a send method.

        Args:
            message (discord.Message): The original message.
            embed_mode (bool): Whether to format the message as an embed, to add additional context.
            native_reply_mode (bool): Use native reply handling if the destination supports it (embed_mode must be enabled on the **destination** and disabled on the **source**). Using native reply will set a "reply_to" parameter, which should be popped and used to reply to the message.
            destination (discord.TextChannel | None): The destination channel where the message will be sent. Required for native reply mode.
            send_method (callable | None): An optional send method to directly send the formatted message.
            native_reply_mode_auto_send (bool): If true and native_reply_mode is enabled, will automatically send the reply using the reply message's reply method.

        Returns:
            dict: A dictionary containing the formatted message parameters, to be passed to a send method.
            list[discord.Message]: If a send method is used, the sent message(s).
        """
        if native_reply_mode:
            if embed_mode:
                raise ValueError("native_reply_mode requires embed_mode to be false.")
            if destination is None:
                raise ValueError(
                    "native_reply_mode requires destination to be provided."
                )
        # Base message structure - Retain embeds and files
        base = {"embeds": message.embeds or [], "files": []}
        for attachment in message.attachments:
            file = await self.attachment_to_file(attachment)
            if file:
                base["files"].append(file)

        # Add content
        if embed_mode:
            embed = discord.Embed(
                description=message.content,
                color=discord.Color.blue(),
            )
            embed.set_author(
                name=f"{message.author.name}",
                icon_url=message.author.display_avatar.url,
            )
            embed.set_footer(text=f"ID-{message.id}")
            base["embeds"].insert(0, embed)
        else:
            base["content"] = message.content

        # Handle replies
        if message.reference:
            if native_reply_mode:
                # Fetch the referenced message
                try:
                    ref_message = await message.channel.fetch_message(
                        message.reference.message_id
                    )
                    if not ref_message.embeds:
                        raise TypeError(
                            "Native reply mode requires the destination to have embed_mode enabled."
                        )
                    # Extract ID from the first embed footer
                    ref_id = None
                    for embed in ref_message.embeds:
                        if embed.footer and embed.footer.text.startswith("ID-"):
                            ref_id = int(embed.footer.text.replace("ID-", ""))
                            break
                    if ref_id:
                        # Get the message object in the destination channel
                        ref_message_dest = (
                            await destination.fetch_message(ref_id)
                            if destination
                            else None
                        )
                        if ref_message_dest:
                            base["reply_to"] = ref_message_dest

                except Exception as e:
                    self.plugin.logger.error(
                        f"Failed to fetch referenced message {message.reference.message_id}: {e}"
                    )
            else:
                if embed_mode:
                    # Add reply context in embed
                    try:
                        reply_embeds = await self._make_reply_embed(message)
                        base["embeds"] = reply_embeds + base["embeds"]
                    except Exception as e:
                        self.plugin.logger.error(
                            f"Failed to fetch referenced message {message.reference.message_id}: {e}"
                        )

        # Return the final message structure
        if send_method:
            if native_reply_mode_auto_send and "reply_to" in base:
                reply: discord.Message = base.pop("reply_to")
                return [await reply.reply(**base)]
            else:
                if len(base["embeds"]) > 10:
                    # Split into multiple messages if too many embeds
                    chunks = [base["embeds"][i:i + 10] for i in range(0, len(base["embeds"]), 10)]
                    send = []
                    for chunk in chunks:
                        chunk_base = base.copy()
                        chunk_base["embeds"] = chunk
                        send.append(await send_method(**chunk_base))
                    return send
                else:
                    return [await send_method(**base)]
        return base

    async def _make_reply_embed(self, message: discord.Message, recursion_depth: int = 1, recursion_limit: int = 4) -> list[discord.Embed]:
        """Create an embed representing a reply to a message."""
        if message.reference:
            ref_message = await message.channel.fetch_message(
                message.reference.message_id
            )
            if not ref_message:
                raise ValueError("Referenced message not found.")
            base_embeds = []
            if ref_message.reference:
                if recursion_depth >= recursion_limit:
                    base_embeds.append(
                        discord.Embed(
                            description="*Reply depth limit reached...*",
                            color=discord.Color.light_grey(),
                        )
                    )
                else:
                    # Handle nested replies
                    base_embeds = await self._make_reply_embed(ref_message, recursion_depth + 1, recursion_limit)
            reply_embed = discord.Embed(
                description=ref_message.content,
                color=discord.Color.light_grey(),
            )
            reply_embed.set_author(
                name=f"{ref_message.author.name} ⤵",
                # icon_url=ref_message.author.display_avatar.url,
            )
            base_embeds.append(reply_embed)
            base_embeds.extend(ref_message.embeds)
            return base_embeds
        else:
            raise ValueError("Message is not a reply.")
    
@dataclass(frozen=True)
class CachedThread:
    user: discord.User
    thread: discord.Thread
    dm_channel: discord.DMChannel | None
