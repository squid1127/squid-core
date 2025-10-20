"""A command line interface plugin for managing permissions."""

import discord
from squid_core.components import Perms, CLIContext, EmbedLevel, PermissionLevel
from squid_core.plugin_base import Plugin as BasePlugin, PluginCog
from squid_core.framework import Framework
from squid_core.decorators import CLICommandDec, RedisSubscribe
from squid_core.config_types import ConfigOption

from discord import app_commands


class PermsCLIPlugin(BasePlugin):
    """A command line interface plugin for managing permissions."""

    def __init__(self, framework: Framework):
        """
        Initialize the PermsCLIPlugin.

        Args:
            framework (Framework): The core framework instance.
        """
        super().__init__(framework)
        self.perms: Perms = framework.perms
        self.cog = PermsCog(self)
        self.use_cog = False
        self.use_cog_opt = ConfigOption(
            name=["plugins", "perms_cli", "use_cog"],
            default=False,
            description="Whether to use the Discord cog for permission commands. (Adds /perms-check command)",
        )

    # Load and unload methods (required, unused here)
    async def load(self) -> None:
        """Load the plugin."""
        self.use_cog = await self.fw.config.get_config_option(self.use_cog_opt, self)
        
        if self.use_cog:
            await self.framework.bot.add_cog(self.cog)

    async def unload(self) -> None:
        """Unload the plugin."""
        if self.use_cog:
            await self.framework.bot.remove_cog(self.cog)

    def _user_id(self, identifier: str) -> int | None:
        """Convert a user identifier (ID, username, mention) to a user ID.

        Args:
            identifier (str): The user identifier.

        Returns:
            int | None: The user ID if found, else None.
        """
        # Check if it's a mention
        if identifier.startswith("<@") and identifier.endswith(">"):
            try:
                return int(identifier[2:-1])
            except ValueError:
                return None
        # Check if it's a numeric ID
        try:
            return int(identifier)
        except ValueError:
            pass
        # Otherwise, treat it as a username from bot
        for user in self.framework.bot.users:
            if user.name == identifier:
                return user.id
        return None

    def _user_readable(self, user_id: str) -> str:
        """Convert a user ID to a readable string (mention or username).

        Args:
            user_id (str): The user ID.

        Returns:
            str: The readable user string.
        """
        user = self.framework.bot.get_user(int(user_id))
        if user:
            return f"{user.name} ({user.mention} | ID: {user.id})"
        return f"<@{user_id}> (ID: {user_id})"

    @CLICommandDec(
        name="perms",
        description="Manage user permissions and attributes.",
    )
    async def perms_command(
        self,
        context: CLIContext,
    ) -> None:
        """Handle the 'perms' CLI command.

        Args:
            context (CLIContext): The CLI command context.
        """

        # Parse subcommands
        args = context.args

        if not args:
            subcommand = "help"
        else:
            subcommand = args[0]

        if subcommand in ["get", "list", "ls", "l"] and len(args) == 2:
            user_id = self._user_id(args[1])
            readable = self._user_readable(user_id)
            if user_id is None:
                await context.respond(
                    "Invalid user identifier.",
                    title="Error",
                    level=EmbedLevel.ERROR,
                )
                return
            perms = await self.perms.get_user_permissions(user_id)
            attrs = await self.perms.get_user_attributes(user_id)

            # Format attributes for display
            attr_list = (
                "- " + "\n- ".join(f"{k}: {v}" for k, v in attrs.items())
                if attrs
                else "No attributes."
            )

            # Format timeout
            if perms.temp_ban_until:
                from datetime import datetime

                timeout_str = perms.temp_ban_until.strftime("%Y-%m-%d %H:%M:%S")
            else:
                timeout_str = "None"

            message = f"### {readable}\n**Level**: {perms.level.name}\n**Banned**: {'__***Yes***__' if perms.banned else 'No'}\n**Timeout**: {timeout_str}\n**Attributes**:\n{attr_list}"
            await context.respond(
                message,
                title=f"User Permissions",
                level=EmbedLevel.INFO,
            )
            return

        elif subcommand == "set_perm" and len(args) == 3:
            user_id = self._user_id(args[1])
            readable = self._user_readable(user_id)
            permission = args[2]
            # Convert permission string to PermissionLevel
            try:
                permission = PermissionLevel[permission.upper()]
            except KeyError:
                await context.respond(
                    f"Invalid permission level '{args[2]}'. Valid levels are: {', '.join([level.name for level in PermissionLevel])}.",
                    title="Error",
                    embed_level=EmbedLevel.ERROR,
                )
                return

            if user_id is None:
                await context.respond(
                    "Invalid user identifier.",
                    title="Error",
                    embed_level=EmbedLevel.ERROR,
                )
                return

            await self.perms.set_user_permission_level(user_id, permission)
            await context.respond(
                f"Set permission '{permission}' for user {readable}.",
                title="Permission Set",
                level=EmbedLevel.SUCCESS,
            )
            return

        elif subcommand == "ban" and len(args) >= 2:
            user_id = self._user_id(args[1])
            readable = self._user_readable(user_id)
            if user_id is None:
                await context.respond(
                    "Invalid user identifier.",
                    title="Error",
                    level=EmbedLevel.ERROR,
                )
                return

            permanent = True
            temp_ban_until = None
            revoke = False

            if len(args) == 3:
                if args[2] == "permanent":
                    permanent = True
                elif args[2].startswith("temp"):
                    try:
                        duration = int(args[2].split()[1])
                        from datetime import datetime, timedelta

                        temp_ban_until = datetime.now() + timedelta(minutes=duration)
                        permanent = False
                    except (IndexError, ValueError):
                        await context.respond(
                            "Invalid temporary ban format. Use 'temp <duration_in_minutes>'.",
                            title="Error",
                            level=EmbedLevel.ERROR,
                        )
                        return
                elif args[2] == "revoke":
                    revoke = True
                else:
                    await context.respond(
                        "Invalid ban option. Use 'permanent', 'temp <duration>', or 'revoke'.",
                        title="Error",
                        level=EmbedLevel.ERROR,
                    )
                    return
            else:
                permanent = True  # Default to permanent ban if no option provided

            await self.perms.ban_user(
                user_id,
                permanent=permanent,
                temp_ban_until=temp_ban_until,
                revoke=revoke,
            )
            action = "Unbanned" if revoke else "Banned"
            await context.respond(
                f"{action} user {readable}.",
                title="Ban Update",
                level=EmbedLevel.SUCCESS,
            )
            return

        elif subcommand == "set_attr" and len(args) == 4:
            user_id = self._user_id(args[1])
            readable = self._user_readable(user_id)
            key = args[2]
            value = args[3]
            if user_id is None:
                await context.respond(
                    "Invalid user identifier.",
                    title="Error",
                    level=EmbedLevel.ERROR,
                )
                return
            await self.perms.set_user_attribute(user_id, key, value)
            await context.respond(
                f"Set attribute '{key}' to '{value}' for user {readable}.",
                title="Attribute Set",
                level=EmbedLevel.SUCCESS,
            )
            return

        # Default help message
        help_message = (
            "**Permissions CLI Help**\n"
            "`perms help` - Show this help message.\n"
            "`perms list <user>` - List permissions and attributes for a user.\n"
            "`perms set_perm <user> <permission>` - Set a permission level for a user.\n"
            "`perms set_attr <user> <attribute> <value>` - Set an attribute for a user.\n"
            "`perms ban <user> [permanent|temp <duration>|revoke]` - Ban or unban a user.\n"
            "`<user>` can be a user ID, username, or mention."
        )
        await context.respond(
            help_message, title="Permissions CLI Help", level=EmbedLevel.INFO
        )
        return
    
    @RedisSubscribe(channel="perms_ban_check")
    async def handle_ban_check(self, message: dict) -> None:
        """Handle incoming Redis messages to check user bans.

        Args:
            message (dict): The Redis message containing user ID to check.
        """
        user_id = message.get("user_id")
        if not user_id:
            return

        is_banned = await self.perms.is_user_banned(user_id)
        # Here you would typically publish the result back to a Redis channel
        # or handle it as needed. This is just a placeholder.
        self.fw.logger.info(f"Ban check for user {user_id}: {'BANNED' if is_banned else 'NOT BANNED'}")

class PermsCog(PluginCog):
    """A cog for permission management commands."""

    def __init__(self, plugin: PermsCLIPlugin):
        """
        Initialize the PermsCog.

        Args:
            plugin (PermsCLIPlugin): The parent plugin instance.
        """
        super().__init__(plugin)
        self.plugin = plugin

    @app_commands.command(
        name="perms-check",
        description="Check your permission level.",
    )
    async def perms_check(self, interaction: discord.Interaction) -> None:
        """Handle the 'perms-check' slash command.

        Args:
            interaction (discord.Interaction): The interaction context.
        """
        # Interaction check
        if not await self.plugin.perms.interaction_check(interaction):
            return

        user_id = str(interaction.user.id)
        perms = await self.plugin.perms.get_user_permissions(user_id)

        await interaction.response.send_message(
            "",
            embed=discord.Embed(
                description=f"Your permission level is: **{perms.level.name}**",
                color=discord.Color.green(),
            ),
            ephemeral=True,
        )