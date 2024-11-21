import asyncio
import discord
from discord.ext import commands


class ShellCore:
    """
    Core shell functionality for the bot. Contains methods for sending messages in the shell channel, as well as attributes for the bot, channel, interactive mode, and name
    """

    def __init__(self, bot: commands.Bot, channel_id: int, name: str):
        self.bot = bot

        self.channel_id = channel_id
        self.interactive_mode = (None, None)
        self.name = name

        self.commands = []

        self.presets = {
            "CogNoCommandError": {
                "title": "Command Error",
                "msg_type": "error",
                "description": "Command not found in cog. How the ~~~~ did this happen?",
            },
        }

    # Start the shell
    async def start(self):
        """Start the shell (find the channel and start logging)"""
        try:
            self.channel = self.bot.get_channel(self.channel_id)
            print("[Core.Shell] Shell channel found!")
            print("[Core.Shell] Starting logging...")
            await asyncio.sleep(1)
            await self.log(
                f"{self.name.title()} has successfully started.",
                title="Bot Started",
                msg_type="success",
                cog="Shell",
            )
        except:
            print("[Core.Shell] Shell channel not found!")
            return

    def add_command(
        self,
        command: str = None,
        cog: str = None,
        description: str = None,
        entry: "ShellCommandEntry" = None,
        **kwargs,
    ):
        """
        Adds a command to the shell's command list.
        This method can either take a pre-constructed `ShellCommandEntry` object
        or the individual components of a command to create a new `ShellCommandEntry`.
        Args:
            entry (ShellCommandEntry, optional): A pre-constructed command entry. Defaults to None.
            command (str, optional): The command string. Defaults to None.
            cog (str, optional): The cog associated with the command. Defaults to None.
            description (str, optional): A brief description of the command. Defaults to None.
            **kwargs: Additional keyword arguments to be passed to the `ShellCommandEntry` constructor.
        """

        if entry:
            self.commands.append(entry)
        else:
            self.commands.append(ShellCommandEntry(command, cog, description, **kwargs))

    async def create_embed(
        self,
        message: str = None,
        title: str = None,
        msg_type: str = "info",
        cog: str = None,
        preset: str = None,
    ):
        if preset:
            title = self.presets[preset]["title"]
            msg_type = self.presets[preset]["msg_type"]
            message = self.presets[preset]["description"]
        try:
            message
            title
        except:
            raise ValueError("Message or title must be provided")
        if msg_type == "error" or msg_type == "fatal_error":
            color = discord.Color.red()
        elif msg_type == "success":
            color = discord.Color.green()
        elif msg_type == "warning":
            color = discord.Color.orange()
        else:
            color = discord.Color.blurple()
        embed = discord.Embed(
            title=f"[{msg_type.upper()}] {title}",
            description=message,
            color=color,
        )
        embed.set_author(name=cog)
        embed.set_footer(text=f"Powered by {self.name.title()} Bot")
        return embed

    # Send a log message
    async def log(
        self,
        message: str = None,
        title: str = None,
        msg_type: str = "info",
        cog: str = None,
        plain_text: str = None,
        preset: str = None,
        edit: discord.Message = None,
    ):
        """
        Logs a message to a Discord channel with an optional embed.
        Parameters:
        -----------
        message : str, optional
            The main content of the log message.
        title : str, optional
            The title of the embed.
        msg_type : str, default "info"
            The type of the message (e.g., "info", "warning", "error", "fatal_error").
        cog : str, optional
            The name of the cog from which the log is being sent.
        plain_text : str, optional
            Plain text content to send instead of the embed.
        preset : str, optional
            Preset configuration for the embed.
        edit : discord.Message, optional
            A Discord message object to edit instead of sending a new message.
        Returns:
        --------
        discord.Message
            The Discord message object that was sent or edited.
        """
        embed = await self.create_embed(
            message=message,
            title=title,
            msg_type=msg_type,
            cog=cog,
            preset=preset,
        )

        if edit:
            msg_object = await edit.edit(
                content=(
                    plain_text
                    if plain_text
                    else ("@everyone" if msg_type == "fatal_error" else "")
                ),
                embed=embed,
            )
            return msg_object

        msg_object = await self.channel.send(
            (
                plain_text
                if plain_text
                else ("@everyone" if msg_type == "fatal_error" else "")
            ),
            embed=embed,
        )
        return msg_object

    def get_channel(self):
        if self.channel:
            return self.channel
        else:
            # Check if bot is ready
            if not self.bot.is_ready():
                return

            self.channel = self.bot.get_channel(self.channel_id)
            return self.channel


class ShellCommand:
    """
    A class to represent a shell command. Contains methods for sending messages in the shell channel, as well as attributes for the command name, cog, and shell
    """

    def __init__(
        self,
        name: str,
        cog: str,
        shell: ShellCore,
        channel: discord.TextChannel = None,
        query: str = None,
        message: discord.Message = None,
    ):
        self.name = name
        self.cog = cog
        self.core = shell
        self.query = query
        self.message = message
        if channel:
            self.channel = channel
        else:
            self.channel = self.core.channel

    def __call__(self):
        return (self.name, self.query)

    def params_to_dict(self, params: str):
        if params is None:
            params = self.query
        params = params.split(" ")
        previous = None
        params_dict = {}
        for param in params:
            if param.startswith("--"):
                if previous:
                    params_dict[previous] = True
                if params_dict.get(param):
                    raise SyntaxError(f"Duplicate parameter: {param}")
                previous = param
            elif param.startswith("-"):
                if previous:
                    params_dict[previous] = True
                if params_dict.get(param[:2]):
                    raise SyntaxError(f"Duplicate parameter: {param}")
                previous = param[:2]
                if len(param) > 2:
                    raise SyntaxError(f"Invalid parameter: {param}")

            elif previous:
                params_dict[previous] = param
                previous = None
            else:
                raise SyntaxError(f"Invalid parameter: {param}")

        if previous:
            params_dict[previous] = True

        return params_dict

    async def log(
        self,
        description: str = None,
        title: str = None,
        fields: list = None,
        footer: str = None,
        msg_type: str = "info",
        preset: str = None,
        edit: discord.Message = None,
    ):
        """
        Logs a message by creating and sending an embed to the specified channel.
        Args:
            description (str): The description text for the embed.
            title (str): The title of the embed.
            fields (list, optional): A list of dictionaries representing fields to add to the embed.
                                     Each dictionary should have 'name' and 'value' keys, and optionally an 'inline' key.
            footer (str, optional): The footer text for the embed.
            msg_type (str, optional): The type of message, which determines the embed color. Defaults to "info".
            edit (discord.Message, optional): An existing message to edit with the new embed. If None, a new message is sent.
        Returns:
            discord.Message: The message object that was sent or edited.
        """
        embed = await self.core.create_embed(
            description, title, msg_type, self.cog, preset=preset
        )
        if fields:
            for field in fields:
                embed.add_field(
                    name=field["name"],
                    value=field["value"],
                    inline=field.get("inline", False),
                )
        if footer:
            embed.set_footer(text=footer)
        if edit:
            msg_object = await edit.edit(embed=embed)
        else:
            msg_object = await self.channel.send(embed=embed)
        return msg_object

    async def raw(self, message: str, edit: discord.Message = None, **kwargs):
        """
        Sends a raw message to the shell channel.
        Args:
            message (str): The message to send.
        Returns:
            discord.Message: The message object that was sent.
        """
        if edit:
            msg_object = await edit.edit(content=message, **kwargs)
        else:
            msg_object = await self.channel.send(message, **kwargs)
        return msg_object


class ShellCommandEntry:
    """
    ShellCommandEntry class represents a shell command entry with its associated metadata.
    Attributes:
        command (str): The command string.
        cog (str): The cog (category) to which the command belongs.
        description (str): A brief description of the command.
        callback (callable, optional): An optional callback function to be executed when the command is invoked.
    Methods:
        __init__(command: str, cog: str, description: str, callback: callable = None):
            Initializes a new instance of the ShellCommandEntry class.
        __str__():
            Returns a string representation of the shell command entry.
    """

    def __init__(
        self,
        command: str,
        cog: str,
        description: str,
        callback: callable = None,
    ):
        self.command = command
        self.cog = cog
        self.description = description
        self.callback = callback

    def __str__(self):
        return f"`{self.command}` - {self.description}"


class ShellHandler(commands.Cog):
    """An extension of the core shell functionality for the bot. Contains methods for executing shell commands and managing cogs"""
    def __init__(self, bot: commands.Bot, core: ShellCore):
        self.bot = bot
        self.core = core

        # Ingreated commands
        self.core.add_command("status", "ShellHandler", "Check the status of the bot")
        self.core.add_command("help", "ShellHandler", "Show this help message")
        self.core.add_command("cog", "ShellHandler", "Manage cogs")
        self.core.add_command("die", "ShellHandler", "Kill the bot")

    @commands.Cog.listener()
    async def on_ready(self):
        """Start the shell"""
        await self.core.start()
        print("[Core.ShellHandler] Shell started!")

    # Shell command Listener
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for shell commands in the shell channel"""
        if message.author == self.bot.user:
            return
        if message.author.bot:
            return
        if message.channel.id == self.core.channel_id:
            if (
                message.content.startswith(f"{self.core.name.lower()}")
                or self.core.interactive_mode[0] is not None
            ):
                result = await self.execute_command(message)

    # Shell command parser
    async def execute_command(self, message: discord.Message) -> str:
        try:
            self.core.channel
        except AttributeError:
            print("[Core.ShellHandler] Shell channel not found!")
            return

        # Interactive mode
        if self.core.interactive_mode[0] is not None:
            print("[Core.ShellHandler] Interactive mode is on")
            cog = self.core.interactive_mode[0]
            callback = self.core.interactive_mode[1]

            if message.content == "exit":
                self.core.interactive_mode = (None, None)
                await self.core.log(
                    f"Returning to normal shell mode.",
                    title="Interactive Mode",
                    msg_type="info",
                    cog="Shell",
                )
                return

            commandClass = ShellCommand(
                name=callback,
                cog=cog,
                shell=self.core,
                query=message.content,
                message=message,
            )

            try:
                await self.bot.cogs[cog].shell_callback(commandClass)
            except Exception as e:
                await self.core.log(
                    f"An unknown error occurred facilitating interactive mode: {e}",
                    title="Interactive Mode Error",
                    msg_type="error",
                    cog="Shell",
                )

            return

        # Check if command is empty
        try:
            command = message.content.split(" ")[1].lower()
        except IndexError:
            command = "help"

        # Find the command in the command list
        # print(self.core.commands)
        for cmd in self.core.commands:
            if cmd.command == command:
                commandEntry: ShellCommandEntry = cmd
                break
        else:
            await self.core.log(
                f"Command `{command}` not found, use `{self.core.name.lower()} help` to see available commands.",
                title="Command Not Found",
                msg_type="error",
                cog="Shell",
            )
            return

        commandClass = ShellCommand(
            name=commandEntry.command,
            cog=commandEntry.cog,
            shell=self.core,
            query=" ".join(message.content.split(" ")[2:]),
            message=message,
        )

        # Execute the command
        try:
            if commandEntry.callback:
                await commandEntry.callback(commandClass)
            else:
                await self.bot.cogs[commandEntry.cog].shell_callback(commandClass)
        except KeyError:
            await self.core.log(
                f"Command `{command}` is registered, but its cog ({commandEntry.cog}) cannot be found.",
                title="Command Error",
                msg_type="error",
                cog="Shell",
            )
        except AttributeError:
            await self.core.log(
                f"Command `{command}` is registered, but the cog `{commandEntry.cog}` does not have a shell implementation.",
                title="Command Error",
                msg_type="error",
                cog="Shell",
            )
        except Exception as e:
            await self.core.log(
                f"An unknown error occurred while executing command `{command}`: {e}",
                title="Command Error",
                msg_type="error",
                cog="Shell",
            )
        return

    async def shell_callback(self, command: ShellCommand):
        """Shell command callback"""
        if command.name == "status":
            print("[Core.ShellHandler] Status command called")
            # Run cog_check on all cogs
            edit = await command.log(
                f"{self.bot.user.name.title()} is currently online and operational.\n\nChecking cogs...",
                title="Bot Status",
                msg_type="info",
            )
            fields = []
            for cog in self.bot.cogs:
                print(f"[Core.ShellHandler] Checking cog {cog}")
                try:
                    check = await self.bot.cogs[cog].cog_status()
                    fields.append({"name": cog, "value": check})
                    print(f"[Core.ShellHandler] Cog {cog} is {check}")
                except AttributeError:
                    fields.append({"name": cog, "value": "Status unknown"})
                    print(
                        f"[Core.ShellHandler] Cog {cog} status unknown (no cog_status method)"
                    )

            await command.log(
                f"{self.bot.user.name.title()} is currently online and operational. {len(fields)} cogs loaded.{' Running as Docker container' if self.bot.is_docker() else ''}",
                title="Bot Status",
                fields=fields,
                msg_type="success",
                edit=edit,
            )
            return
        elif command.name == "help":
            # Show help message
            fields = [
                {
                    "name": "Running Commands",
                    "value": f"To run a command, type `{self.core.name.lower()} <command>` in the shell channel (this channel).",
                },
                {
                    "name": "Commands",
                    "value": "- "
                    + "\n- ".join([str(cmd) for cmd in self.core.commands]),
                },
            ]
            edit = await command.log(
                f"Use this shell to manage bot and view logs",
                title="Help",
                msg_type="info",
                fields=fields,
            )
            return
        elif command.name == "cog":
            # Cog management
            if command.query.startswith("load"):
                action = "load"
            elif command.query.startswith("unload"):
                action = "unload"
            elif command.query.startswith("reload"):
                action = "reload"
            else:
                action = "list"

            if action == "list":
                fields = [
                    {
                        "name": "Cogs",
                        "value": "- " + "\n- ".join([cog for cog in self.bot.cogs]),
                    },
                    {
                        "name": "Commands",
                        "value": "Use the following commands to manage these cogs:\n- `load <cog>`\n- `unload <cog>`\n- `reload <cog>`",
                    },
                ]

                await command.log(
                    f"Cogs are the categories of commands that the bot uses.",
                    title="Cog Management",
                    msg_type="info",
                    fields=fields,
                )
                return
            else:
                cog = " ".join(command.query.split(" ")[1:]).strip()
                confirm = False
                if "-y" in cog:
                    cog = cog.replace("-y", "").strip()
                    confirm = True

                if action == "unload" or action == "reload":
                    if cog == "ShellHandler" and (not confirm or action == "reload"):
                        if action == "reload":
                            await command.log(
                                f"You cannot reload the ShellHandler cog as doing so will result in the shell being unloaded but not reloaded. If you wish to unload the shell, use the `unload` command.",
                                title="Cog Management",
                                msg_type="error",
                            )
                            return

                        await command.log(
                            f"Are you sure you want to {action} the ShellHandler cog? This could cause the shell to stop working. You will need to restart the bot to fix this. To confirm, run the command again with `-y` at the end.",
                            title="Cog Management",
                            msg_type="warning",
                        )
                        return

                    if cog not in self.bot.cogs:
                        await command.log(
                            f"Cog `{cog}` is not loaded or does not exist.",
                            title="Cog Management",
                            msg_type="error",
                        )
                        return

                    try:
                        cog_class = await self.bot.remove_cog(cog)
                        if action == "reload":
                            await command.log(
                                f"Cog `{cog}` has been unloaded, loading...",
                                title="Cog Management",
                                msg_type="info",
                            )
                        else:
                            await command.log(
                                f"Cog `{cog}` has been unloaded.",
                                title="Cog Management",
                                msg_type="success",
                            )
                            if cog == "ShellHandler":
                                await command.raw("Farewell 👋 :(")
                            return

                    except Exception as e:
                        await command.log(
                            f"An error occurred while unloading cog `{cog}`: {e}",
                            title="Cog Management",
                            msg_type="error",
                        )
                        return

                if action == "load" or action == "reload":
                    try:
                        cache = self.bot.cog_cache

                        if action == "load":
                            if cog in cache:
                                cog_class = cache[cog]
                            else:
                                await command.log(
                                    f"Could not find cog `{cog}` in cached cogs. Tip: To add a cog to the cache, use the `add_cog_unloaded` method in the core.",
                                    title="Cog Management",
                                    msg_type="error",
                                )
                                return

                        await self.bot.add_cog(cog_class)
                        await command.log(
                            f"Cog `{cog}` has been {action}ed.",
                            title="Cog Management",
                            msg_type="success",
                        )
                    except Exception as e:
                        await command.log(
                            f"An error occurred while {action}ing cog `{cog}`: {e}",
                            title="Cog Management",
                            msg_type="error",
                        )
                    return
                
        elif command.name == "die":
            # Kill the bot
            if "-y" in command.query:
                await command.log(
                    f"Shutting down...",
                    title="Bot Shutdown",
                    msg_type="info",
                )
                print("[Core.ShellHandler] -> [Command.Die] Shutting down...")
                await self.bot.close()
                return
            await command.log(
                f"Are you sure you want to shut down the bot? To confirm, run the command again with `-y` at the end.",
                title="Bot Shutdown",
                msg_type="warning",
            )
            return

        await command.log(preset="CogNoCommandError")

    async def cog_status(self):
        """Cog status check"""
        return f"Running\nChannel: {self.core.channel.mention}\nInteractive Mode: {self.core.interactive_mode}"
