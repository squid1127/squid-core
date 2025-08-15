"""Simple bot permissions management module. Also provides user information management."""

import discord
from discord.ext import commands

import os
import logging
from enum import Enum
from traceback import format_exc
from typing import List, Optional, Union

from .memory import Memory
from .shell import ShellCore, ShellCommand

logger = logging.getLogger("core.perms")


class PermissionLevel(Enum):
    """Enum for permission levels."""

    ADMIN = "admin"
    MANAGER = "manager"
    APPROVED = "approved"

    @classmethod
    def choices(cls):
        """Return a list of all permission levels."""
        return [level.value for level in cls]


class Constants:
    """Constants for permissions management."""

    PERMISSIONS_COLLECTION = "global.users.permissions"
    PERMISSIONS_INDEX = "user_id"
    COLLECTION_SEARCH_INDEX = [
        ("attributes.username", "text"),
    ]
    COLLECTION_SEARCH_INDEX_WEIGHT = {
        "attributes.username": 10,
    }

    PERMISSION_SCHEMA = {
        "$jsonSchema": {
            "bsonType": "object",
            "properties": {
                "user_id": {"bsonType": "long"},
                "permissions": {
                    "bsonType": "array",
                    "items": {"bsonType": "string", "enum": PermissionLevel.choices()},
                },
                "attributes": {
                    "bsonType": "object",
                }
            },
            "required": ["user_id"],
        }
    }


class Permissions:
    """Permissions management and user information management."""

    def __init__(self, memory: Memory):
        self.memory = memory

    def get_collection(self):
        """Get the permissions collection."""
        if self.memory.mongo_db is None:
            logger.error("MongoDB connection is not initialized.")
            raise ValueError("MongoDB connection is not initialized.")

        return self.memory.mongo_db[Constants.PERMISSIONS_COLLECTION]
    
    async def user_exists(self, user_id: int) -> bool:
        """Check if a user exists in the permissions collection."""
        collection = self.get_collection()
        document = await collection.find_one({"user_id": user_id})
        return document is not None

    async def get_permissions(self, user_id: int):
        """Get permissions for a user, creating entry if it doesn't exist."""
        collection = self.get_collection()
        document = await collection.find_one({"user_id": user_id})
        if not document:
            # Auto-create user entry with no permissions
            await self._create_user_entry(user_id)
            return []
        return document.get("permissions", [])

    async def _create_user_entry(self, user_id: int):
        """Create a new user entry in the database."""
        collection = self.get_collection()
        try:
            await collection.insert_one({
                "user_id": user_id,
                "permissions": [],
                "attributes": {},
                "created_at": discord.utils.utcnow().isoformat()
            })
            logger.info(f"Created user entry for {user_id}")
        except Exception as e:
            logger.warning(f"Failed to create user entry for {user_id}: {e}")

    async def has_permission(self, user_id: int, permission: Union[str, PermissionLevel]):
        """Check if a user has a specific permission."""
        if isinstance(permission, PermissionLevel):
            permission = permission.value
        permissions = await self.get_permissions(user_id)  # This will auto-create if needed
        return permission in permissions

    async def add_permission(self, user_id: int, permission: str) -> str:
        """Add a permission to a user. Returns a message indicating success or failure."""
        if permission not in PermissionLevel.choices():
            logger.error(f"Invalid permission: {permission}")
            return f"Invalid permission: {permission}. Valid permissions are: {', '.join(PermissionLevel.choices())}."
        
        collection = self.get_collection()
        document = await collection.find_one({"user_id": user_id})

        if not document:
            document = {"user_id": user_id, "permissions": []}

        if permission not in document["permissions"]:
            document["permissions"].append(permission)
            try:
                await collection.update_one(
                    {"user_id": user_id},
                    {"$set": {"permissions": document["permissions"]}},
                    upsert=True,
                )
            except Exception as e:
                logger.error(f"Error adding permission: {e}")
                return f"Error adding permission: {e}"
            logger.info(f"Added permission '{permission}' for user {user_id} (<@{user_id}>).")
            return f"Permission '{permission}' added for user {user_id} (<@{user_id}>)."
        else:
            logger.warning(f"User {user_id} already has permission '{permission}'.")
            return f"User {user_id} already has permission '{permission}' (<@{user_id}>)."

    async def remove_permission(self, user_id: int, permission: str):
        """Remove a permission from a user."""
        collection = self.get_collection()
        document = await collection.find_one({"user_id": user_id})

        if document and permission in document.get("permissions", []):
            document["permissions"].remove(permission)
            await collection.update_one(
                {"user_id": user_id},
                {"$set": {"permissions": document["permissions"]}},
            )
            logger.info(f"Removed permission '{permission}' for user {user_id}.")
        else:
            logger.warning(f"User {user_id} does not have permission '{permission}'.")

    async def interaction_check(
        self, interaction: discord.Interaction, permission: Union[str, PermissionLevel]
    ):
        """Check if a user has a specific permission for an interaction. Gives feedback if not. Returns True if they have it, False otherwise."""
        user_id = interaction.user.id
        if await self.has_permission(user_id, permission):
            return True
        else:
            if isinstance(permission, PermissionLevel):
                permission = permission.value
            permission = permission.title()
            
            await interaction.response.send_message(
                f"You do not have the required permission: {permission}. Please contact a bot admin if you believe this is an error. (These permissions are global and managed by the bot admins, not per server.)",
                ephemeral=True,
            )
            return False
        
    async def apply_attributes(self, user_id: int, attributes: dict):
        """Apply attributes to a user."""
        collection = self.get_collection()
        document = await collection.find_one({"user_id": user_id})

        if not document:
            await self._create_user_entry(user_id)
            document = await collection.find_one({"user_id": user_id})

        # Update attributes
        if "attributes" not in document:
            document["attributes"] = {}
        document["attributes"].update(attributes)
        await collection.update_one(
            {"user_id": user_id},
            {"$set": {"attributes": document["attributes"]}},
        )
        logger.info(f"Updated attributes for user {user_id} (<@{user_id}>).")
        
    def base_user_attributes(self, user: discord.User) -> dict:
        """Generate base user attributes for a user."""
        return {
            "username": user.name,
            "discriminator": user.discriminator if user.discriminator else None,
            "avatar_url": user.display_avatar.url if user.display_avatar else None,
            "id": user.id,
            "created_at": user.created_at.isoformat(),
        }
        
    async def get_user_attributes(self, user_id: int) -> Optional[dict]:
        """Get user attributes from the database."""
        collection = self.get_collection()
        document = await collection.find_one({"user_id": user_id})
        if document and "attributes" in document:
            return document["attributes"]
        return None
    
    async def get_user_attribute(
        self, user_id: int, attribute: str
    ) -> Optional[Union[str, int, float, bool]]:
        """Get a specific user attribute from the database."""
        attributes = await self.get_user_attributes(user_id)
        if attributes and attribute in attributes:
            return attributes[attribute]
        return None
    
    async def search_user_by_username(
        self, username: str, limit: int = 10
    ) -> List[dict]:
        """Search for users by username."""
        collection = self.get_collection()
        cursor = collection.find(
            {"$text": {"$search": username}},
            {"score": {"$meta": "textScore"}}
        ).sort([("score", {"$meta": "textScore"})]).limit(limit)

        users = []
        async for document in cursor:
            users.append(document)
        return users


class PermissionsManager(commands.Cog):
    """Cog for managing permissions system."""

    def __init__(self, bot: commands.Bot, shell: ShellCore):
        self.bot = bot
        self.shell = shell
        self.permissions: Permissions = self.bot.permissions

        if not self.bot.memory:
            logger.error(
                "Memory not initialized. PermissionsManager will not function properly."
            )
            return
        else:
            logger.info("PermissionsManager initialized with memory.")
            self.memory: Memory = bot.memory

        shell.add_command(
            "perms",
            "PermissionsManager",
            "Manage permissions for users.",
        )

    async def cog_load(self):
        """Load the permissions manager."""
        logger.info("Loading PermissionsManager cog.")
        if self.memory.mongo_db is None:
            logger.error(
                "MongoDB connection is not initialized. Cannot load PermissionsManager."
            )
            return

        if (
            Constants.PERMISSIONS_COLLECTION
            not in await self.memory.mongo_db.list_collection_names()
        ):
            logger.info(
                f"Creating collection '{Constants.PERMISSIONS_COLLECTION}' with schema."
            )
            await self.memory.mongo_db.create_collection(
                Constants.PERMISSIONS_COLLECTION,
                validator=Constants.PERMISSION_SCHEMA,
                validationLevel="strict",  # optional: strict (default) or moderate
                validationAction="error",  # optional: error (default) or warn
            )
            await self.memory.mongo_db[Constants.PERMISSIONS_COLLECTION].create_index(
                Constants.PERMISSIONS_INDEX, unique=True
            )
            await self.memory.mongo_db[Constants.PERMISSIONS_COLLECTION].create_index(
                Constants.COLLECTION_SEARCH_INDEX,
                weights=Constants.COLLECTION_SEARCH_INDEX_WEIGHT,
                name="username_text_index",
            )

        logger.info("Permissions system initialized.")

    async def cog_status(self):
        """Return the status of the cog."""
        return "Ready" if self.memory else "Not initialized"
    
    async def update_user_base_attributes(self, user: discord.User):
        """Update the base attributes for a user."""
        attributes = self.permissions.base_user_attributes(user)
        await self.permissions.apply_attributes(user.id, attributes)
        logger.info(f"Updated base attributes for user {user.id} (<@{user.id}>).")
    
    async def refresh_all_users(self):
        """Create user entries for all users in the database, then update their base attributes."""
        users = self.bot.get_all_members()
        for user in users:
            if not await self.permissions.user_exists(user.id):
                await self.permissions._create_user_entry(user.id)
                logger.info(f"Created user entry for {user.id} (<@{user.id}>).")
            await self.update_user_base_attributes(user)
        

    async def shell_callback(self, command: ShellCommand):
        """Shell command callback for permissions management."""
        try:
            if command.name == "perms":
                action = command.query.split(" ")[0].lower()
                if not action or action not in ["get", "list", "add", "remove", "refresh-all", "search", "attr"]:
                    await command.log(
                        "**Usage**:\nManage user permissions:\n`perms <get|list|add|remove> <user_id> [permission]`\nRefresh all user entries:\n`perms refresh-all`",
                        title="Permissions Command",
                        msg_type="info",
                    )
                    return
                
                if action == "refresh-all":
                    edit = await command.log(
                        "Refreshing all user entries and updating base attributes. This may take a while...",
                        title="Refreshing Users",
                        msg_type="info",
                    )
                    await self.refresh_all_users()
                    await command.log(
                        "All user entries refreshed and base attributes updated.",
                        title="Refresh All Users",
                        msg_type="success",
                        edit=edit,
                    )
                    return
                
                if action == "search":
                    # Search for users by username
                    if len(command.query.split(" ")) < 2:
                        await command.log(
                            "Usage: perms search <username>",
                            title="Invalid Command",
                            msg_type="error",
                        )
                        return
                    
                    username = command.query.split(" ", 1)[1:]
                    username = " ".join(username).strip()
                    if not username:
                        await command.log(
                            "Usage: perms search <username>",
                            title="Invalid Command",
                            msg_type="error",
                        )
                        return
                    users = await self.permissions.search_user_by_username(username)
                    if not users:
                        await command.log(
                            f"No users found with username '{username}'.",
                            title="Search Results",
                            msg_type="info",
                        )
                        return
                    user_list = "\n".join(
                        f"{user['user_id']} - {user['attributes'].get('username', 'Unknown')} (<@{user['user_id']}>)"
                        for user in users
                    )
                    await command.log(
                        f"Users found:\n{user_list}",
                        title="Search Results",
                        msg_type="info",
                    )
                    return

                # Basic user perms action handling
                if action not in ["get", "list", "add", "remove"]:
                    await command.log(
                        "Usage: perms <get|list|add|remove> <user_id> [permission]",
                        title="Invalid Command",
                        msg_type="error",
                    )
                    return
                
                user_id_full = command.query.split(" ")[1] if len(command.query.split(" ")) > 1 else None
                if not user_id_full.isdigit():
                    # Try to parse user ID from mention
                    user_id_full = user_id_full.strip("<@!>")
                if user_id_full is None or not user_id_full.isdigit():
                    # Try to parse user ID from mention, if user_id_full is not None
                    if user_id_full is not None:
                        user_id_full = user_id_full.strip("<@!>")
                if user_id_full is None or not user_id_full.isdigit():
                    await command.log(
                        "Invalid user ID. Please provide a valid user ID or mention.",
                        title="Invalid Command",
                        msg_type="error",
                    )
                    return
                
                # Debug -> output the user ID
                logger.info(f"User ID parsed: {user_id_full}")
                
                user_id = int(user_id_full)
                permission = (
                    command.query.split(" ")[2]
                    if len(command.query.split(" ")) > 2
                    else None
                )

                if action == "add":
                    if user_id and permission:
                        output = await self.permissions.add_permission(user_id, permission)
                        await command.log(
                            output,
                            title="Permission Added",
                            msg_type="success",
                        )
                    else:
                        await command.log(
                            "Usage: perms add <user_id> <permission>",
                            title="Invalid Command",
                            msg_type="error",
                        )

                elif action == "remove":
                    if user_id and permission:
                        await self.permissions.remove_permission(user_id, permission)
                        await command.log(
                            f"Removed permission '{permission}' for user {user_id} (<@{user_id}>).",
                            title="Permission Removed",
                            msg_type="success",
                        )
                    else:
                        await command.log(
                            "Usage: perms remove <user_id> <permission>",
                            title="Invalid Command",
                            msg_type="error",
                        )
                if action in ["get", "list", "add", "remove"]:
                    if user_id:
                        permissions = await self.permissions.get_permissions(user_id)
                        await command.log(
                            (
                                f"Permissions for user {user_id} (<@{user_id}>): \n- "
                                + "\n- ".join(permissions)
                                if permissions
                                else "None"
                            ),
                            title="Permissions Retrieved",
                            msg_type="info",
                        )
                    else:
                        await command.log(
                            "Usage: perms get <user_id>",
                            title="Invalid Command",
                            msg_type="error",
                        )
                else:
                    await command.log(
                        "Usage: perms <add|remove|get> <user_id> [permission]",
                        title="Invalid Command",
                        msg_type="error",
                    )
        except Exception as e:
            logger.error(f"Error in shell callback: {e}")
            await command.log(
                f"An error occurred while processing the command: {str(e)}\n\n```\n{format_exc()}\n```",
                title="Error",
                msg_type="error",
            )

