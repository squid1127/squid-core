"""CLI decorator to register CLI commands."""
from .base import Decorator, DecoratorManager
from ..plugin_base import Plugin
from ..components.cli import CLICommand as CLICommandType

class CLICommand(Decorator):
    """Decorator to register a CLI command."""

    def __init__(self, name:str, aliases:list[str], description:str) -> None:
        """Initialize the decorator with the CLI command."""
        super().__init__()
        self.cmd_name = name
        self.cmd_aliases = aliases
        self.cmd_description = description

    async def apply(self, plugin: Plugin, func:callable, *args, **kwargs) -> None:
        """Apply the decorator logic to register the CLI command."""
        # Auto generate the CLICommand instance
        self.command = CLICommandType(
            name=self.cmd_name,
            aliases=self.cmd_aliases,
            description=self.cmd_description,
            execute=func,
            plugin=plugin.name,
        )

        try:
            cli_manager = plugin.fw.cli
            cli_manager.register_command(self.command)
            plugin.fw.logger.info(
                f"Registered CLI command '{func.__name__}' in plugin '{plugin.name}'"
            )
        except Exception as e:
            plugin.fw.logger.error(
                f"Failed to register CLI command '{func.__name__}' in plugin '{plugin.name}': {e}"
            )
            raise e
        
# Register the decorator
DecoratorManager.add(CLICommand)