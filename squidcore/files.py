"""Submodule for handling configuration files and handle path assignments."""

# General file handling
import os
import time

# For processing specific file types
import json, yaml

# Discord
from discord.ext import commands

# Watch file changes
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
from functools import wraps

# Logger
import logging

logger = logging.getLogger("core.files")


class FileBroker:
    """Class for handling configuration files and path assignments."""

    def __init__(self, bot: commands.Bot, root_path: str):
        self.bot = bot
        self.root_path = root_path
        self.cogs = {}

    def init(self):
        # Create the root directory
        try:
            os.makedirs(self.root_path, exist_ok=True)
            os.makedirs(os.path.join(self.root_path, "config"), exist_ok=True)
            os.makedirs(os.path.join(self.root_path, "cache"), exist_ok=True)
            os.makedirs(os.path.join(self.root_path, "data"), exist_ok=True)
        except OSError as e:
            logger.error(f"Error creating directories: {e}")
            return None

        return True

    def configure_cog(
        self,
        cog: str,
        config_file: bool = False,
        config_default: str = None,
        config_dir: bool = False,
        config_do_cache: int = 0,
        cache: bool = False,
        cache_clear_on_init: bool = False,
        perm: bool = False,
    ):
        """
        Configure a cog with the given settings.
        Args:
            cog (str): The name of the cog to configure.
            config_file (bool, optional): Indicates whether the cog needs a configuration file. Defaults to False.
            config_default (str, optional): The default configuration for the cog. Defaults to None.
            config_do_cache (int, optional): The number of seconds to cache the configuration file to prevent excessive reads. Defaults to 0 (no caching).
            config_dir (bool, optional): Indicates whether the cog needs a configuration directory. Defaults to False.
            cache (bool, optional): Indicates whether the cog needs a cache directory. Defaults to False.
            cache_clear_on_init (bool, optional): Indicates whether the cache should be cleared on initialization. Defaults to False.
            perm (bool, optional): Indicates whether the cog needs a permanent data directory. Defaults to False.
        """

        # Set the cog settings
        config = {
            "config": config_file,
            "config_default": config_default,
            "config_dir": config_dir,
            "config_cache_enabled": config_do_cache > 0,
            "config_cache_set_time": config_do_cache,
            "cache": cache,
            "cache_clear_on_init": cache_clear_on_init,
            "perm": perm,
        }

        # Create class
        cogfile = CogFiles(
            bot=self.bot, cog=cog, config=config, root_path=self.root_path
        )
        self.cogs[cog] = cogfile

        return cogfile


class CogFiles:
    """Per cog class to handle configuration files and path assignments."""

    def __init__(self, bot: commands.Bot, cog: str, config: dict, root_path: str):
        self.bot = bot
        self.cog = cog
        self.config = config
        self.root_path = root_path

        self.configs = {}

    def init(self):
        """
        Initialize the cog directories and files.
        """

        try:
            # Create the config directory
            if self.config["config_dir"]:
                config_dir = os.path.join(self.root_path, "config", self.cog)
                os.makedirs(config_dir, exist_ok=True)
            else:
                config_dir = None

            # Create the config file
            if self.config["config"]:
                config_file = (
                    os.path.join(self.root_path, "config", f"{self.cog}.yaml")
                    if not self.config["config_dir"]
                    else os.path.join(config_dir, f"configuration.yaml")
                )
                if not os.path.exists(config_file):
                    # Confirm default configuration is valid yaml
                    if not self.config["config_default"]:
                        logger.warning(
                            f"No default configuration provided for cog {self.cog}"
                        )
                        self.config["config_default"] = ""
                        with open(config_file, "w") as f:
                            f.write("")
                    else:
                        try:
                            yaml.safe_load(self.config["config_default"])
                        except yaml.YAMLError as e:
                            logger.warning(
                                f"Invalid default configuration for cog {self.cog}: {e} - Using empty configuration"
                            )
                            self.config["config_default"] = ""
                        with open(config_file, "w") as f:
                            f.write(self.config["config_default"])
            else:
                config_file = None

            # Create the cache directory
            if self.config["cache"]:
                cache_dir = os.path.join(self.root_path, "cache", self.cog)
                os.makedirs(cache_dir, exist_ok=True)
                
                # Clear cache on init
                if self.config["cache_clear_on_init"]:
                    for filename in os.listdir(cache_dir):
                        file_path = os.path.join(cache_dir, filename)
                        try:
                            if os.path.isfile(file_path):
                                os.unlink(file_path)
                        except Exception as e:
                            logger.error(f"Error clearing cache file {file_path}: {e}")
            else:
                cache_dir = None

            # Create the perm directory
            if self.config["perm"]:
                perm_dir = os.path.join(self.root_path, "data", self.cog)
                os.makedirs(perm_dir, exist_ok=True)
            else:
                perm_dir = None

        except OSError as e:
            logger.error(f"Error creating directories for cog {self.cog}: {e}")
            return None

        return {
            "config": config_file,
            "config_dir": config_dir,
            "cache": cache_dir,
            "perm": perm_dir,
        }

    def get_config(self, name: str = None, cache: bool = True):
        """
        Get the configuration for the cog.
        Args:
            name (str, optional): The name of the configuration file to read. By default, the default configuration file is read.
            cache (bool, optional): Use the cached configuration if available. Defaults to True.
        """

        if name:
            # Check that config directory is enabled
            if not self.config["config_dir"]:
                logger.warning(
                    f"Configuration directory is disabled for cog {self.cog} but a specific configuration file was requested"
                )
                return None

        # Check if the configuration is cached
        if cache and self.config["config_cache_enabled"]:
            # Find current cached configuration information
            config_info = self.configs.get(name if name else "__default__", {})
            last_read = config_info.get("last_read", 0)
            cached_config = config_info.get("config", None)

            # Check if the configuration is still valid
            if last_read:
                if time.time() - last_read < self.config["config_cache_set_time"]:
                    return cached_config

        # Read the configuration
        logger.debug(f"Reading configuration for cog {self.cog}")

        if self.config["config"]:
            # Determine path
            config_file = (
                os.path.join(self.root_path, "config", f"{self.cog}.yaml")
                if not name
                else os.path.join(self.config["config_dir"], f"{name}.yaml")
            )
            
            logger.debug(f"Reading configuration file: {config_file}")
            
            with open(config_file, "r") as f:
                try:
                    config = yaml.safe_load(f)
                except yaml.YAMLError as e:
                    logger.error(f"Error loading configuration for cog {self.cog}: {e}")
                    return None
        else:
            logger.warning(
                f"A configuration file was configured for cog {self.cog} but config is disabled"
            )
            return None

        # Cache the configuration
        if cache and self.config["config_cache_enabled"]:
            self.configs[name if name else "__default__"] = {
                "last_read": time.time(),
                "config": config,
            }

        return config
    
    def set_config(self, config: dict, name: str = None):
        """
        (Not Recommended) Set the configuration for the cog.
        Args:
            config (dict): The configuration to set.
            name (str, optional): The name of the configuration file to set. By default, the default configuration file is set.
        """
        # Determine path
        config_file = (
            os.path.join(self.root_path, "config", f"{self.cog}.yaml")
            if not name
            else os.path.join(self.config["config_dir"], f"{name}.yaml")
        )
        
        with open(config_file, "w") as f:
            yaml.dump(config, f)

    def invalidate_config(self, name: str = None):
        """
        Invalidate the cached configuration for the cog.
        Args:
            name (str, optional): The name of the configuration file to invalidate. By default, the default configuration file is invalidated.
        """
        if name:
            self.configs.pop(name, None)
        else:
            self.configs.pop("__default__", None)

    def get_config_dir(self):
        """
        Get the configuration directory for the cog.
        """

        if not self.config["config_dir"]:
            logger.warning(
                f"Configuration directory is disabled for cog {self.cog} but a specific configuration directory was requested"
            )
            return None

        return os.path.join(self.root_path, "config", self.cog)
    
    def get_cache_dir(self):
        """
        Get the cache directory for the cog.
        """

        if not self.config["cache"]:
            logger.warning(
                f"Cache directory is disabled for cog {self.cog} but a cache directory was requested"
            )
            return None

        return os.path.join(self.root_path, "cache", self.cog)
    
    def get_perm_dir(self):
        """
        Get the permanent data directory for the cog.
        """

        if not self.config["perm"]:
            logger.warning(
                f"Permanent data directory is disabled for cog {self.cog} but a permanent data directory was requested"
            )
            return None

        return os.path.join(self.root_path, "data", self.cog)