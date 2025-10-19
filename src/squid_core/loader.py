"""Plugin discovery and loading for squid-core framework."""

import importlib
from importlib.resources import path
import pkgutil
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from .logging import get_framework_logger
from .config import ConfigManager
from .plugin_base import Plugin as PluginObject
from .decorators.base import DecoratorApplyError, DecoratorManager

PLUGIN_CLASS_NAME = "Plugin"


class PluginType(Enum):
    CORE = "core"
    CUSTOM = "custom"


class PluginState(Enum):
    UNLOADED = "unloaded"
    PRE_LOADED = "pre_loaded"
    LOADED = "loaded"
    ERROR = "error"


@dataclass
class Plugin:
    # Identity
    name: str
    description: str

    # Location
    module_path: str
    os_path: Path

    # Plugin Class
    plugin_class: type
    plugin_instance: object | None = None

    # State
    state: PluginState = PluginState.UNLOADED

    # Tortoise ORM Models (Realative to module path)
    db_models: list[str] | None = None

    # Dependencies
    dependencies: list[str] | None = None


class PluginManager:
    """Manages loading and unloading of plugins."""

    def __init__(
        self, framework, core_base_package: str, custom_packages: dict[str, str]
    ):
        """
        Initialize the PluginManager.

        Args:
            framework: The main framework instance.
            core_base_package (str): The base package path for core plugins.
            custom_packages (dict[str, str]): A mapping of custom plugin packages to their module paths.
        """
        self.framework = framework
        self.config: ConfigManager = framework.config
        self.core_base_package = core_base_package
        self.custom_packages = custom_packages or {}
        self.logger = get_framework_logger("plugin_manager")
        self.plugins: dict[str, Plugin] = {}

        self.logger.info(f"PluginManager initialized with core package '{core_base_package}' and custom packages: {list(self.custom_packages.keys())}")

    def resolve_path(self, module_name: str) -> Path:
        """Resolve the filesystem path of a module given its name."""
        module = importlib.import_module(module_name)
        return Path(module.__file__).parent
    
    def package_paths(self) -> dict[str, str]:
        """Get all package paths including core and custom packages."""
        paths = self.custom_packages.copy()
        if "core" in paths:
            raise ValueError(
                "The 'core' key is reserved in custom_packages. Cannot use 'core' as a custom package name."
            )
        paths["core"] = self.core_base_package
        return paths

    def get_by_string(self, names: list[str]) -> list[Plugin]:
        """Get Plugin objects by string query (names, group wildcard)."""
        names = names.copy() # Bruh python references are so annoying
        found_plugins: list[Plugin] = []
        
        # Group wildcards
        for group in self.package_paths().keys():
            if f"{group}:*" in names:
                # Add all plugins from this group
                for plugin in self.plugins.values():
                    if plugin.name.startswith(f"{group}:"):
                        found_plugins.append(plugin)
                names.remove(f"{group}:*")
        
        # Specific names
        for name in names:
            plugin = self.plugins.get(name)
            if plugin:
                found_plugins.append(plugin)
            else:
                self.logger.warning(f"Plugin '{name}' not found in loaded plugins.")
        return found_plugins

    def make_plugin(
        self, manifest: dict, module_path: str, os_path: Path, source: str = "unknown"
    ) -> Plugin:
        """
        Create a Plugin object from its manifest and module information.

        Args:
            manifest (dict): The plugin manifest data.
            module_path (str): The module path of the plugin.
            os_path (Path): The filesystem path of the plugin.
            source (str): The source package name of the plugin.
        """
        plugin_options: dict = manifest.get("plugin", {})
        models: list[str] = manifest.get("db", {}).get("models", [])
        deps_options: dict = manifest.get("dependencies", {})
        plugin_class = None

        # Import the module to get the Plugin class
        module = importlib.import_module(module_path)
        class_name = plugin_options.get("class", PLUGIN_CLASS_NAME)
        if not hasattr(module, class_name):
            raise ImportError(
                f"Module {module_path} does not have a '{class_name}' class."
            )
        plugin_class = getattr(module, class_name)

        # Enforce naming convention (lowercase, no spaces)
        name = plugin_options.get("name", "unknown").lower().replace(" ", "_")

        # Create Plugin object
        plugin = Plugin(
            name=f"{source}:{name}",
            description=plugin_options.get("description", ""),
            module_path=module_path,
            os_path=os_path,
            plugin_class=plugin_class,
            db_models=models,
            dependencies=deps_options.get("plugins", []),
        )
        return plugin

    async def find_all(self) -> list[Plugin]:
        """Find and return all plugins from a given source."""
        paths = self.package_paths()

        discovered_plugins: list[Plugin] = []
        for package_name, package_path in paths.items():
            # Resolve os path
            os_path = self.resolve_path(package_path)

            # Iterate through directories looking for plugin.toml files
            for item in os_path.iterdir():
                if item.is_dir():
                    manifest_path = item / "plugin.toml"
                    if manifest_path.exists():
                        # Load manifest
                        contents = await self.config.read_toml(manifest_path)
                        # Determine module path
                        module_path = f"{package_path}.{item.name}"
                        # Create Plugin object
                        plugin = self.make_plugin(
                            contents, module_path, item, package_name
                        )
                        if plugin:
                            self.logger.info(
                                f"Discovered plugin: {plugin.name} (from {package_name})"
                            )
                            discovered_plugins.append(plugin)

        # Update internal plugins list
        for plugin in discovered_plugins:
            self.plugins[plugin.name] = plugin
        return discovered_plugins

    async def preload_one(self, plugin: Plugin) -> None:
        """Pre-load a single plugin (instantiate, register DB models, execute preload)."""
        if plugin.state != PluginState.UNLOADED:
            self.logger.warning(
                f"Plugin {plugin.name} is not in UNLOADED state. Current state: {plugin.state}. Skipping preload."
            )
            return

        self.logger.info(f"Pre-loading plugin: {plugin.name}")
        try:
            # Instantiate plugin
            plugin.plugin_instance = plugin.plugin_class(framework=self.framework)
            # Register DB models if any
            if plugin.db_models:
                for model_path in plugin.db_models:
                    self.framework.db.register_model(
                        f"{plugin.module_path}.{model_path}"
                    )  # Register model module (relative path)
                    
            # Apply decorators
            try:
                await DecoratorManager.apply(plugin.plugin_instance)
            except DecoratorApplyError as dae:
                self.logger.error(
                    f"Failed to apply decorators for plugin {plugin.name}: {dae}"
                )
                raise dae

            # Call preload method if exists
            if hasattr(plugin.plugin_instance, "preload"):
                await plugin.plugin_instance.preload()
            plugin.state = PluginState.PRE_LOADED
            self.logger.debug(f"Plugin {plugin.name} pre-loaded successfully.")

        except Exception as e:
            plugin.state = PluginState.ERROR
            self.logger.error(f"Error pre-loading plugin {plugin.name}: {e}")

    async def load_one(self, plugin: Plugin) -> None:
        """Load a single plugin (execute load)."""
        if plugin.state != PluginState.PRE_LOADED:
            self.logger.warning(
                f"Plugin {plugin.name} is not in PRE_LOADED state. Current state: {plugin.state}. Skipping load."
            )
            return

        self.logger.info(f"Loading plugin: {plugin.name}")
        try:
            # Call load method if exists
            if hasattr(plugin.plugin_instance, "load"):
                await plugin.plugin_instance.load()
            plugin.state = PluginState.LOADED
            self.logger.debug(f"Plugin {plugin.name} loaded successfully.")

        except Exception as e:
            plugin.state = PluginState.ERROR
            self.logger.error(f"Error loading plugin {plugin.name}: {e}")

    async def unload_one(self, plugin: Plugin) -> None:
        """Unload a single plugin (execute unload)."""
        if plugin.state != PluginState.LOADED:
            self.logger.warning(
                f"Plugin {plugin.name} is not in LOADED state. Current state: {plugin.state}. Skipping unload."
            )
            return

        self.logger.info(f"Unloading plugin: {plugin.name}")
        try:
            # Call unload method if exists
            if hasattr(plugin.plugin_instance, "unload"):
                await plugin.plugin_instance.unload()
            plugin.state = PluginState.UNLOADED
            self.logger.debug(f"Plugin {plugin.name} unloaded successfully.")

        except Exception as e:
            plugin.state = PluginState.ERROR
            self.logger.error(f"Error unloading plugin {plugin.name}: {e}")

    async def preload(self, plugins: list[str]) -> None:
        """Pre-load a list of plugins by their names."""
        self.logger.debug(f"Pre-loading plugins: {plugins}")
        for plugin in self.get_by_string(plugins):
            await self.preload_one(plugin)

    async def load(self, plugins: list[str]) -> None:
        """Load a list of plugins by their names."""
        self.logger.debug(f"Loading plugins: {plugins}")
        for plugin in self.get_by_string(plugins):
            await self.load_one(plugin)

    async def unload_all(self) -> None:
        """Unload all loaded plugins."""
        self.logger.debug("Unloading all plugins...")
        for plugin in self.plugins.values():
            if plugin.state == PluginState.LOADED:
                await self.unload_one(plugin)

    async def get_plugin(self, name: str) -> PluginObject | None:
        """Get the plugin instance by its name."""
        plugin = self.plugins.get(name)
        if plugin and plugin.plugin_instance:
            return plugin.plugin_instance
        return None