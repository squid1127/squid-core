# Basic Usage Guide

This document provides a quick overview of using the squid-core framework.

## Initialization

To get started with squid-core, you need to initialize the framework and its components. Here's a basic example:

```python
from squid_core import Framework

fw = Framework.create()
fw.run()
```

You can also override the manifest path if your `framework.toml` is located elsewhere:

```python
from pathlib import Path
from squid_core import Framework

fw = Framework.create(manifest_path=Path("path/to/your/framework.toml"))
fw.run()
```

### Manifest File

You will typically have a `framework.toml` file in your project root that defines the framework settings and plugins to load.

```toml
[project]
name = "squidbot" # Internal name of your bot
friendly_name = "Squid Bot" # Display name of your bot

[bot]
command_prefix = "!" # Command prefix for your bot
intents = ["messages", "guilds", "members", "message_content"] # Intents to enable

[log]
level = "INFO" # Log level -> DEBUG, INFO, WARNING, ERROR, CRITICAL
debug_mode = false # Enable debug mode for verbose output
console = true # Output logs to console
file = "logs/bot.log" # Optional: path to log file (comment out to disable)

[plugins]
plugins = ["core:*", "mybot:custom_plugin"] # Plugins to load (group:name or group:* for all)
```

## Plugins

Plugins are where most of the functionality of squid-core comes from. You can load core plugins as well as your own custom plugins by specifying them in the `framework.toml` file under the `[plugins]` section.

### Creating a Custom Plugin

Plugin file structure:

```bash
plugins/my_custom_plugin/ # Custom plugins located in the plugins/ directory
    __init__.py # Import the plugin class from .main
    main.py # Main plugin logic, optional
    plugin.toml # Plugin manifest
```

To create a custom plugin, you need to subclass the `Plugin` base class:

```python
from squid_core.plugin_base import Plugin

class MyCustomPlugin(Plugin):
    def __init__(self, framework):
        super().__init__(framework)

        self.logger.info("MyCustomPlugin initialized") # Built-in logger
    async def load(self): # Called when the plugin is loaded
        self.logger.info("MyCustomPlugin loaded")
    async def unload(self): # Called when the plugin is unloaded
        self.logger.info("MyCustomPlugin unloaded")
```

Plugins also have manifest files similar to the framework manifest:

```toml
[plugin]
name = "my_custom_plugin" # Internal name of the plugin
description = "A custom plugin for squid-core" # Description of the plugin
class = "MyCustomPlugin" # The class name of the plugin (Located in the __init__.py in the same directory as this manifest)
```
