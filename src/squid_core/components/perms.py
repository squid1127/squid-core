"""Permission manager component for Squid Core."""

"""Permission Objects for Squid Core."""

from enum import Enum, auto
from dataclasses import dataclass
from typing import List, Union
from tortoise import Model, fields
import datetime as dt
import discord

from .db import Database
from .redis_comp import Redis


class PermissionLevel(Enum):
    """Enumeration of permission levels."""

    USER = "user"
    APPROVED = "approved"
    MODERATOR = "moderator"
    ADMIN = "admin"

    def to_int(self) -> int:
        """Convert permission level to an integer for comparison."""
        mapping = {
            PermissionLevel.USER: 1,
            PermissionLevel.APPROVED: 2,
            PermissionLevel.MODERATOR: 3,
            PermissionLevel.ADMIN: 4,
        }
        return mapping[self]


class UserPermissionModel(Model):
    """Database model for user permissions."""

    id = fields.IntField(pk=True)
    user_id = fields.CharField(max_length=64, unique=True)
    level = fields.CharEnumField(PermissionLevel, default=PermissionLevel.USER)
    banned = fields.BooleanField(default=False)
    temp_ban_until = fields.DatetimeField(null=True)

    class Meta:
        table = "squidcore_user_permissions"


class UserAttributeModel(Model):
    """Key-value store for user attributes."""

    id = fields.IntField(pk=True)
    user_id = fields.CharField(max_length=64, index=True)
    key = fields.CharField(max_length=128)
    value = fields.TextField()

    class Meta:
        table = "squidcore_user_attributes"
        unique_together = (("user_id", "key"),)


class Perms:
    def __init__(self, db: Database, redis: Redis):
        """Initialize the permission manager."""
        self.db = db
        self.redis = redis

    def _default(self, user_id: str) -> UserPermissionModel:
        """Create a default permission model for a user."""
        return UserPermissionModel(
            user_id=user_id,
            level=PermissionLevel.USER,
            banned=False,
            temp_ban_until=None,
        )

    async def get_user_permissions(self, user_id: str) -> UserPermissionModel:
        """Retrieve or create the permission model for a user."""
        user_id = str(user_id)

        perm = await UserPermissionModel.get_or_none(user_id=user_id)
        if perm is None:
            perm = self._default(user_id)
            await perm.save()
        return perm

    async def set_user_permission_level(
        self, user_id: str, level: PermissionLevel
    ) -> None:
        """Set the permission level for a user."""
        user_id = str(user_id)

        perm = await self.get_user_permissions(user_id)
        perm.level = level
        await perm.save()

    async def ban_user(
        self,
        user_id: str,
        permanent: bool = True,
        temp_ban_until: dt.datetime = None,
        revoke: bool = False,
    ) -> None:
        """Ban or unban a user."""
        user_id = str(user_id)

        perm = await self.get_user_permissions(user_id)
        if revoke:
            perm.banned = False
            perm.temp_ban_until = None
        else:
            perm.banned = True
            if not permanent:
                perm.temp_ban_until = temp_ban_until

        await perm.save()

    async def is_user_banned(self, user_id: str) -> bool:
        """Check if a user is banned."""
        user_id = str(user_id)

        perm = await self.get_user_permissions(user_id)
        if perm.banned:
            if perm.temp_ban_until and perm.temp_ban_until < dt.datetime.now():
                # Temporary ban has expired
                perm.banned = False
                perm.temp_ban_until = None
                await perm.save()
                return False
            return True
        return False

    async def set_user_attribute(self, user_id: str, key: str, value: str) -> None:
        """Set a user attribute."""
        user_id = str(user_id)

        attr, created = await UserAttributeModel.get_or_create(
            user_id=user_id, key=key, defaults={"value": value}
        )
        if not created:
            attr.value = value
            await attr.save()

    async def get_user_attribute(self, user_id: str, key: str) -> Union[str, None]:
        """Get a user attribute."""
        user_id = str(user_id)

        attr = await UserAttributeModel.get_or_none(user_id=user_id, key=key)
        if attr:
            return attr.value
        return None

    async def get_user_attributes(self, user_id: str) -> dict:
        """Get all attributes for a user."""
        user_id = str(user_id)

        attrs = await UserAttributeModel.filter(user_id=user_id)
        return {attr.key: attr.value for attr in attrs}

    async def interaction_check(
        self,
        interaction: discord.Interaction,
        required_level: PermissionLevel = None,
        attr: str = None,
        attr_value: str = None,
    ) -> bool:
        """
        Check if a user has the required permission level for an interaction, and automatically provide feedback.

        Args:
            interaction (discord.Interaction): The interaction context.
            required_level (PermissionLevel, optional): The required permission level. Defaults to None.
            attr (str, optional): Required user attribute key. Defaults to None.
            attr_value (str, optional): Expected value for the user attribute. Defaults to None.
        """
        user_id = str(interaction.user.id)
        perm = await self.get_user_permissions(user_id)

        try:
            if await self.is_user_banned(user_id):
                await interaction.response.send_message(
                    "",
                    embed=discord.Embed(
                        title="Access Denied",
                        description="You are banned from using this bot.",
                        color=discord.Color.red(),
                    ),
                    ephemeral=True,
                )
                return False

            if required_level and perm.level.to_int() < required_level.to_int():
                await interaction.response.send_message(
                    "",
                    embed=discord.Embed(
                        title="Insufficient Permissions",
                        description=f"You need {required_level.value} permissions to use this command.",
                        color=discord.Color.red(),
                    ),
                    ephemeral=True,
                )
                return False

            if attr:
                user_attr_value = await self.get_user_attribute(user_id, attr)
                if user_attr_value != attr_value:
                    await interaction.response.send_message(
                        "",
                        embed=discord.Embed(
                            title="Insufficient Permissions",
                            description=f"You lack the required attribute '{attr}' to use this command.",
                            color=discord.Color.red(),
                        ),
                        ephemeral=True,
                    )
                    return False
        except Exception as e:
            await interaction.response.send_message(
                "",
                embed=discord.Embed(
                    title="Permission Check Failed",
                    description="Something went wrong while checking your permissions. Please contact bot admins if the issue persists.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return False

        # User has sufficient permissions
        return True
