"""v2 of the discord data explorer."""

import asyncio
import discord
from discord.ext import commands, tasks

from .shell import ShellCore, ShellCommand

import logging

import datetime
import copy

logger = logging.getLogger("core.explorer")


class DiscordExplorer(commands.Cog):
    """A cog that allows for the exploration of discord data."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.shell: ShellCore = bot.shell

        self.interactive_state = {}
        self.interactive_state_history = []

        self.shell.add_command(
            command="explore",
            cog="DiscordExplorer",
            description="Explore discord data.",
        )
        self.shell.add_command(
            command="xp",
            cog="DiscordExplorer",
            description="(Alias for explore) Explore discord data.",
        )

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Discord Explorer loaded.")

    @commands.Cog.listener()
    async def shell_callback(self, command: ShellCommand):
        if command.name == "explore" or command.name == "xp":
            await command.log(
                "Entering interactive mode.",
                title="Discord Explorer",
            )
            self.shell.interactive_mode = ("DiscordExplorer", "explore-interactive")
            await self.interactive(command, init=True)
            return

        elif command.name == "explore-interactive":
            await self.interactive(command)
            return

    async def interactive(
        self,
        command: ShellCommand,
        init: bool = False,
        internal: bool = False,
        history: bool = True,
    ):
        help_message = """
**Query Syntax:**
- type:guild | channel | member
- guild:guild_id
- channel:channel_id
- member:member_id

**Examples:**
- `guild:1234` - Fetch guild with id 1234.
- `guild:1234 channel:5678` - Fetch channel 5678 in guild 1234.
- `type:member` - Fetch all members.
- `type:channel guild:1234` - Fetch all channels in guild 1234.
        """

        async def go_home():
            self.interactive_state["page"] = "main"
            await self.interactive(command, internal=True)
            return

        async def show_query(query: str):
            if "help" in query:
                await command.raw(f"## Help\n\n{help_message}")
                return

            query_result = await self.query(query)
            if query_result["failed"]:
                await command.raw(f"Query failed: {query_result['error']}")
                return
            else:
                self.interactive_state["query"] = query
                self.interactive_state["query_result"] = query_result
                self.interactive_state["page"] = "query"

                await self.interactive(command, internal=True)
                return

        async def go_back():
            logger.debug("Going back.")
            logger.debug(f"History: {len(self.interactive_state_history)} Items.")
            if len(self.interactive_state_history) > 2:
                self.interactive_state_history.pop()
                self.interactive_state_history.pop() # The back request adds one so we need to remove it.

                logger.debug(
                    f"New history: {len(self.interactive_state_history)} Items."
                )
                self.interactive_state = self.interactive_state_history[-1]

                await self.interactive(command, internal=True, history=False)

                logger.debug(
                    f"Went back. | Currently {len(self.interactive_state_history)} items in history."
                )
            else:
                await go_home()
            return

        if init:
            self.interactive_state = {
                "page": "main",
                "subpage": None,
                "query": "",
            }
            self.interactive_state_history = [self.interactive_state]
            self.interactive_state_history.append(copy.deepcopy(self.interactive_state))

        if internal:
            query = None
        else:
            query = command.query

        logger.debug(f"Interactive state: {self.interactive_state}")

        if self.interactive_state["page"] == "main":
            if query:
                await show_query(query)
                return
            else:
                if init:
                    await command.raw(
                        "# Discord Explorer\n\n"
                        + help_message
                        + "\n\nEnter a query to get started."
                    )
                else:
                    await command.raw(
                        "## New query\n\n"
                        + help_message
                        + "\n\nPlease enter a new query."
                    )
                return

        elif self.interactive_state["page"] == "query":
            query_info = self.interactive_state["query_result"]["request"]

            # * Actions
            if query:
                # Check if query is an interger
                try:
                    int(query)
                    query_is_int = True
                    logger.debug("Query is an integer.")
                except ValueError:
                    query_is_int = False

                if query.startswith("new"):
                    if query == "new":
                        await go_home()
                        return
                    try:
                        new_query = " ".join(query.split(" ")[1:])
                    except:
                        await go_home()
                    else:
                        await show_query(new_query)
                    return
                elif query == "back":
                    await go_back()
                    return

                # Select an item.
                elif "select" in self.interactive_state["actions"] and (
                    query_is_int or query.startswith("select")
                ):
                    logger.debug("Got select request.")

                    if query_is_int:
                        query = int(query)
                    else:
                        try:
                            query = int(query.split(" ")[1])
                        except ValueError:
                            await command.raw("Invalid selection. (`select [number]`)")
                            return
                    logger.debug(f"Selecting item: {query}")

                    if query in self.interactive_state["count_map"]:
                        # Construct a query with the selected item.
                        item = self.interactive_state["count_map"][query]
                        if isinstance(item, discord.Guild):
                            new_query = f"guild:{item.id}"
                        elif isinstance(item, discord.TextChannel):
                            new_query = f"guild:{item.guild.id}&channel:{item.id}"
                        elif isinstance(item, discord.Member):
                            new_query = f"member:{item.id}"
                        else:
                            await command.raw(f"Unknown item type: {type(item)}")
                            return

                        logger.debug(f"New query: {new_query}")

                        await show_query(new_query)
                        return
                    else:
                        await command.raw("Invalid selection.")
                        return

                # Show channels or members.
                elif (
                    query in ["channels", "members"]
                    and query in self.interactive_state["actions"]
                ):
                    logger.debug("Got channels/members request.")
                    new_query = f"guild:{query_info['guild']}&type:{'channel' if query == 'channels' else 'member'}"
                    logger.debug(f"New query: {new_query}")
                    await show_query(new_query)
                    return

                elif (
                    query == "attach" and "attach" in self.interactive_state["actions"]
                ) or (query == "dm" and "dm" in self.interactive_state["actions"]):
                    logger.info("Got attach request.")
                    if query == "attach":
                        guild_id = query_info["guild"]
                        channel_id = query_info["channel"]
                        attach_query = f"{guild_id}::{channel_id}"
                    elif query == "dm":
                        member_id = query_info["member"]
                        attach_query = f"<@{member_id}>"

                    logger.info(f"Attemping to attach: {attach_query}")
                    await command.raw(f"Attemping to attach: {attach_query}")

                    new_message = command.message
                    new_message.content = f"{'impersonate-guild' if query == 'attach' else 'impersonate-dm'} {attach_query}"

                    logger.info(f"Full request: {new_message.content}")
                    await self.shell.execute_command(
                        new_message, override_interactive=True, internal=True
                    )

                    await command.raw("Attach request sent.")
                    logger.info("Attach request sent.")
                    return

            # * Show query results.
            if internal:
                logger.debug("Showing query results.")

                query_result = self.interactive_state["query_result"]
                # Format the query result.
                formatted_result, count_map = await self.query_format(
                    query_result["result"], split=True
                )
                self.interactive_state["count_map"] = count_map
                self.interactive_state["formatted_result"] = formatted_result

                logger.debug(f"Determining actions.")

                # * Determine actions.
                actions = ["new", "back"]

                query_info = self.interactive_state["query_result"]["request"]
                if len(query_result["result"]) > 1:
                    actions.append("select")
                elif query_info.get("type") == "guild":
                    actions.extend(["channels", "members", "lock"])
                elif query_info.get("type") == "channel":
                    actions.extend(["members", "lock", "attach"])
                elif query_info.get("type") == "member":
                    actions.extend(["dm", "lock"])

                action_descriptions = {
                    "new": "Make a new query.",
                    "back": "Go back to the previous page.",
                    "select": "Select a result to view more details.",
                    "channels": "View all channels in this guild.",
                    "members": "View all members in this guild/channel.",
                    "lock": "Block all interactions with this server or user.",
                    "attach": "Attach a ImpersonateGuild thread to this channel.",
                    "dm": "Attach a ImpersonateDM thread to this user.",
                }

                self.interactive_state["actions"] = actions

                action_string = "### Available Actions\n"
                for action in actions:
                    action_string += f"- `{action}` - {action_descriptions.get(action, 'No description.')}\n"
                action_string += "Please choose an action."

                logger.debug("Showing query results.")

                # * Show the results.
                await command.raw(f"## Query: `{self.interactive_state['query']}`")
                for result in formatted_result:
                    await command.raw(result)
                await command.raw(action_string)
            else:
                await command.raw("Please choose an action.")

    async def query(self, query: str) -> dict:
        """
        Make a query to fetch discord data.

        Args:
            query (str): The query to make.

        Returns:
            dict: The fetched data. (and metadata)

        Queries are comprised of filters, such as type:guild or channel:1234, and are separated by a space, comma, or &.

        Examples:
            type:channel guild:1234 channel:5678 # Fetch channel 5678 in guild 1234.
            member:1234 # Fetch member with id 1234.
            type:channel guild:1234 # Fetch all channels in guild 1234.
        """

        # * Parse the query.
        parse_result = self._parse(query)
        if parse_result["failed"]:
            return parse_result

        # * Fetch the data.
        entries = []

        # * Search for guilds.
        if parse_result["type"] == "guild":
            # Search for specific guild.
            if "guild" in parse_result:
                guild = self.bot.get_guild(parse_result["guild"])
                if guild is None:
                    return {"failed": True, "error": "Guild not found."}
                entries.append(guild)

            # Search for all guilds.
            else:
                entries.extend(self.bot.guilds)

        # * Search for channels.
        elif parse_result["type"] == "channel":
            channels = []

            # Search for specific channel.
            if "channel" in parse_result:
                channel = self.bot.get_channel(parse_result["channel"])
                if channel is None:
                    return {"failed": True, "error": "Channel not found."}
                channels.append(channel)

            # Search for all channels in a guild.
            elif "guild" in parse_result:
                guild = self.bot.get_guild(parse_result["guild"])
                if guild is None:
                    return {"failed": True, "error": "Guild not found."}
                channels.extend(guild.channels)

            # Search for all channels in all guilds.
            else:
                for guild in self.bot.guilds:
                    channels.extend(guild.channels)

            # Filter out non-text channels.
            entries.extend(
                [
                    channel
                    for channel in channels
                    if isinstance(channel, discord.TextChannel)
                ]
            )

        # * Search for members.
        elif parse_result["type"] == "member":
            members = []

            # Search for specific member.
            if "member" in parse_result:
                member = self.bot.get_user(parse_result["member"])
                if member is None:
                    return {"failed": True, "error": "Member not found."}
                members.append(member)

            # Search for all members in a guild.
            elif "guild" in parse_result:
                guild = self.bot.get_guild(parse_result["guild"])
                if guild is None:
                    return {"failed": True, "error": "Guild not found."}
                members.extend(guild.members)

            # Search for all members in all guilds.
            else:
                for guild in self.bot.guilds:
                    members.extend(guild.members)

            # Remove duplicates.
            entries.extend(list(set(members)))
            
        parse_result = self._post_process(parse_result, entries)

        return {"failed": False, "result": entries, "request": parse_result}

    def _parse(self, query: str) -> dict:
        """
        Parse a query into a dictionary.

        Args:
            query (str): The query to parse.

        Returns:
            dict: The parsed query.
        """

        result = {
            "failed": False,
            "missing": [],
        }

        # * Pre-programed filter vaild syntax.
        filter_syntax = {
            "type": {"type": "str", "values": ["guild", "channel", "member"]},
            "guild": {"type": "int", "validates": discord.Guild},
            "channel": {"type": "int", "validates": discord.TextChannel},
            "member": {"type": "int", "validates": discord.Member},
        }

        # * Split the query into filters.
        # Ensure there is only one space between each filter.
        query = " ".join(query.split())
        query = query.replace(" ", "&")
        query = query.replace(",", "&")
        query_filters = query.split("&")

        # * Parse each filter.
        query_filter_dict = {}
        try:
            for query_filter in query_filters:
                # Split the filter into key and value.
                key, value = query_filter.split(":")
                query_filter_dict[key] = value
        except ValueError:
            return {"failed": True, "error": "Invalid query filter syntax."}

        # * Validate the filters.
        try:
            for key, value in query_filter_dict.items():
                if key in filter_syntax:
                    if filter_syntax[key]["type"] == "int":
                        try:
                            result[key] = int(value)
                        except ValueError:
                            return {
                                "failed": True,
                                "error": f"Invalid filter value: {value} (Must be an integer)",
                            }
                    elif filter_syntax[key]["type"] == "str":
                        result[key] = value
                    else:
                        return {
                            "failed": True,
                            "error": f"Invalid filter type: {filter_syntax[key]['type']}",
                        }
                else:
                    return {"failed": True, "error": f"Unknown filter: {key}"}

                if "values" in filter_syntax[key]:
                    if value not in filter_syntax[key]["values"]:
                        return {
                            "failed": True,
                            "error": f"Invalid value for filter {key}: {value}",
                        }

        except Exception as e:
            return {
                "failed": True,
                "error": f"An error occured while parsing filters: {e}",
            }

        # * Apply type filter if not present based on the other filters.
        if "type" not in result:
            if "member" in result:
                result["type"] = "member"
            elif "channel" in result:
                result["type"] = "channel"
            elif "guild" in result:
                result["type"] = "guild"
            else:
                return {
                    "failed": True,
                    "error": "Type is neither specified nor can be inferred.",
                }

        return result
    
    def _post_process(self, query_data: dict, query_result:list) -> dict:
        """Post-process the query data, adding additional information."""
        
        if query_data["type"] == "guild":
            if not "guild" in query_data and len(query_result) == 1:
                query_data["guild"] = query_result[0].id
                
        elif query_data["type"] == "channel":
            for channel in query_result:
                if not "guild" in query_data:
                    query_data["guild"] = channel.guild.id
                    
            if not "channel" in query_data and len(query_result) == 1:
                query_data["channel"] = query_result[0].id
                
        return query_data
            
        

    async def query_format(self, items: list, split: bool = False, view: str = None):
        """Transform a list of discord objects into a markdown string (or list of strings)."""

        logger.debug(f"Formatting {len(items)} items.")

        formatted_strings = []
        count_map = {}

        if not view:
            if len(items) == 1:
                view = "single"

            elif len(items) <= 8:
                view = "detailed"
            else:
                view = "compact"

        logger.debug(f"View: {view}")

        count = 1
        for item in items:
            current_string = ""
            # Guilds
            if isinstance(item, discord.Guild):
                # Grab first channel.
                first_channel = (
                    item.text_channels[0] if len(item.text_channels) > 0 else None
                )

                # One guild.
                if view == "single":
                    current_string += f"### {item.name}\n"
                    current_string += f"**ID:** {item.id}\n"
                    current_string += f"**Members:** {item.member_count}\n"
                    current_string += f"**Owner:** {item.owner}\n"
                    current_string += f"**Channels:** {len(item.channels)}\n"
                    current_string += f"**First Channel:** {first_channel.mention if first_channel else 'No channels'}"

                # Multiple guilds.
                elif view == "detailed":
                    current_string += f"**{count}. {item.name} ({item.id})**\n"
                    current_string += (
                        f"Members: {item.member_count} | Owner: {item.owner.mention}\n"
                    )
                    current_string += f"Channels: {len(item.channels)} | First Channel: {first_channel.mention if first_channel else 'No channels'}"

                # A lot of guilds.
                else:
                    current_string += f"{count}. {item.name} ({item.id}) | {item.member_count} Members | Owned by {item.owner.mention} | {first_channel.mention if first_channel else 'No channels'}"

            # Channels
            elif isinstance(item, discord.TextChannel):
                # One channel.
                if view == "single":
                    current_string += f"### #{item.name} ({item.id})\n"
                    current_string += item.topic + "\n" if item.topic else "No topic.\n"
                    current_string += f"**ID:** {item.id}\n"
                    current_string += (
                        f"**Guild:** {item.guild.name} ({item.guild.id})\n"
                    )
                    current_string += f"**Members:** {len(item.members)}\n"
                    current_string += f"**Jump:** {item.mention}\n"

                # Multiple channels.
                elif view == "detailed":
                    current_string += f"**{count}. #{item.name} ({item.id})**\n"
                    current_string += item.topic + "\n" if item.topic else "No topic.\n"
                    current_string += f"Guild: {item.guild.name} ({item.guild.id})\n"
                    current_string += (
                        f"Members: {len(item.members)} | Jump: {item.mention}"
                    )

                # A lot of channels.
                else:
                    current_string += f"{count}. #{item.name} ({item.id}) | {item.guild.name} ({item.guild.id}) | {item.mention} | {len(item.members)} Members"

            # Members
            elif isinstance(item, discord.Member) or isinstance(item, discord.User):
                # One member.
                if view == "single":
                    # Mutual Guilds list
                    mutual_guilds = ""
                    for guild in item.mutual_guilds:
                        mutual_guilds += f"- {guild.name} ({guild.id})\n"

                    current_string += f"### @{item.name}\n"
                    current_string += f"**ID:** {item.id}\n"
                    if hasattr(item, "joined_at"):
                        current_string += (
                            f"**Joined:** {item.joined_at.strftime('%Y-%m-%d')}\n"
                        )
                    current_string += f"**Profile:** {item.mention}\n"
                    current_string += f"**Guilds:**\n{mutual_guilds}"

                # Multiple members.
                elif view == "detailed":
                    current_string += f"**{count}. @{item.name} ({item.id})**\n"
                    if hasattr(item, "joined_at"):
                        current_string += (
                            f"Joined: {item.joined_at.strftime('%Y-%m-%d')} | "
                        )
                    current_string += f"Profile: {item.mention} | {len(item.mutual_guilds)} Mutual Guilds"

                # A lot of members.
                else:
                    current_string += f"{count}. @{item.name} ({item.id}) | {len(item.mutual_guilds)} Mutual Guilds"

            else:
                logger.error(f"Could not format item: {item}; Unknown type.")
                current_string = f"{count}. Unknown item type: {type(item)} | ID: {item.id if hasattr(item, 'id') else 'N/A'} | Name: {item.name if hasattr(item, 'name') else 'N/A'}"

            logger.debug(f"Formatted: {current_string}")
            formatted_strings.append(current_string)
            count_map[count] = item
            count += 1

        # Split the strings if needed. (They need to be under 2000 characters)
        if split:
            split_strings = []
            current_string = ""
            for string in formatted_strings:
                if len(current_string + string) > 2000:
                    split_strings.append(current_string)
                    current_string = ""
                current_string += string + "\n"
            split_strings.append(current_string)
            return split_strings, count_map
        else:
            return formatted_strings, count_map
