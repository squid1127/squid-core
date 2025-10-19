"""Plugin Configuration"""

from dataclasses import dataclass
from squid_core import ConfigSchema, ConfigOption

@dataclass
class DMConfig(ConfigSchema):
    """Configuration for the DM Plugin."""

    thread_prefix: int
    capture_bot_messages: bool
    auto_archive_threads: bool
    
    _options = {
        "thread_prefix": ConfigOption(
            name=["plugin", "core", "dms", "thread_prefix"],
            enforce_type=str,
            default="&&dm-",
            description="Prefix for DM thread names.",
        ),
        "capture_bot_messages": ConfigOption(
            name=["plugin", "core", "dms", "capture_bot_messages"],
            enforce_type=bool,
            default=True,
            description="Whether to capture messages sent by bots.",
        ),
        "auto_archive_threads": ConfigOption(
            name=["plugin", "core", "dms", "auto_archive_threads"],
            enforce_type=bool,
            default=False,
            description="Whether to auto-archive DM threads after inactivity. [Not yet implemented]",
        ),
    }