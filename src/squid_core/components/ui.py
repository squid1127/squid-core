"""
Enhanced UI system based on discord.ui
"""

import discord
from enum import Enum
from typing import Callable

from ..plugin_base import Plugin


class UIType(Enum):
    """Enum for different UI origins."""

    INTERACTION = 1
    MESSAGE = 2


class UIView:
    """Base class for creating UI views."""

    # * Setup
    def __init__(
        self,
        ui_type: UIType,
        timeout: float | None = 300.0,
        embed: discord.Embed | None = None,
        plugin: Plugin | None = None,
    ) -> None:
        """
        Initialize the UI view.

        Args:
            ui_type (UIType): The type of UI (interaction or message).
            timeout (float | None): The timeout duration for the view.
            embed (discord.Embed | None): Initial embed for the view.
            plugin (Plugin | None): Attach plugin for context (optional).
        """
        self.ui_type = ui_type
        self.view = discord.ui.View(timeout=timeout)
        self.timeout = timeout
        self.embed = embed
        self.plugin = plugin

        self._message: discord.Message | None = None
        self._interaction: discord.Interaction | None = None

        self._setup_timeout()

    def _setup_timeout(self) -> None:
        """Setup the timeout method for the view."""

        async def on_timeout() -> None:
            """Handle the timeout event."""
            self.view.stop()
            await self.render(destroy=True)

        self.view.on_timeout = on_timeout
        
    def add_button(
        self,
        label: str,
        style: discord.ButtonStyle,
        custom_id: str | None = None,
        url: str | None = None,
        callback: Callable[[discord.Interaction], None] | None = None,
        skip_defer: bool = False,
        **kwargs,
    ) -> None:
        """Add a button to the UI view."""


        _btn = discord.ui.Button(label=label, style=style, custom_id=custom_id, url=url, **kwargs)

        async def button_callback(interaction: discord.Interaction) -> None:
            if not skip_defer:
                await interaction.response.defer(thinking=False)
            if callback:
                await callback(interaction)

        if not url:
            _btn.callback = button_callback
        self.view.add_item(_btn)
        
    # * Initialization Methods
    async def init_interaction(self, interaction: discord.Interaction) -> None:
        """Initialize the view with an interaction."""
        if not self.ui_type == UIType.INTERACTION:
            raise ValueError(
                "UIType must be INTERACTION to initialize with interaction."
            )
        self._interaction = interaction

        # Send the initial response
        if not interaction.response.is_done():
            await interaction.response.defer()

        # Render the view
        await self.render()
        await self.on_load()

    async def init_message(self, message: discord.Message) -> None:
        """Initialize the view with a message."""
        if not self.ui_type == UIType.MESSAGE:
            raise ValueError("UIType must be MESSAGE to initialize with message.")
        self._message = message

        # Render the view
        await self.render()
        await self.on_load()
        
    #* Destruction Methods
    async def destroy(self, show_expired: bool = False) -> None:
        """Destroy the UI view."""
        self.view.stop()
        await self.render(destroy=True, show_expired=show_expired)

    # * Rendering Methods
    async def render(self, destroy: bool = False, show_expired: bool = True) -> None:
        """Render the UI view."""
        kwargs = {}
        if self.embed:
            kwargs["embed"] = self.embed

        if destroy:
            if show_expired:
                view = discord.ui.View()
                view.add_item(discord.ui.Button(label="Expired", style=discord.ButtonStyle.gray, disabled=True))
            else:
                view = None
            kwargs["view"] = view
        else:
            kwargs["view"] = self.view

        if self.ui_type == UIType.INTERACTION and self._interaction:
            await self._interaction.edit_original_response(**kwargs)
        elif self.ui_type == UIType.MESSAGE and self._message:
            await self._message.edit(**kwargs)
        else:
            raise ValueError("UI view is not properly initialized for rendering.")

    async def view_transition(self, new_view: "UIView") -> None:
        """Transition to a new UI view."""
        self.view.stop()
        # await self.render(destroy=True, show_expired=False)

        if self.ui_type != new_view.ui_type:
            raise ValueError("UIType must match for view transition.")
        if self.ui_type == UIType.INTERACTION:
            await new_view.init_interaction(self._interaction)
        elif self.ui_type == UIType.MESSAGE:
            await new_view.init_message(self._message)
            
    #* Subclassing Methods
    async def on_load(self) -> None:
        """Called when the view is loaded."""
        pass
