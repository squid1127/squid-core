"""Configuration types for managing configuration options, sources, and defaults."""

from __future__ import annotations
from typing import TypedDict, Optional, Dict, Any, List, Union
from enum import Enum
from dataclasses import dataclass, field, Field
from collections import namedtuple


SourceInfo = namedtuple("SourceInfo", "precedence")

class ConfigSource(Enum):
    """
    Enumeration of configuration sources.

    Sources are ordered by precedence, from highest to lowest:
    1. KV_STORE - Key-value store (from built-in database)
    2. ENVIRONMENT - Environment variables
    3. MANIFEST_GLOBAL - Project manifest (global, static)
    4. MANIFEST_PLUGIN - Plugin manifest (static)
    5. DEFAULT - Hardcoded default value
    """

    KV_STORE = SourceInfo(precedence=1)
    ENVIRONMENT = SourceInfo(precedence=2)
    MANIFEST_GLOBAL = SourceInfo(precedence=3)
    MANIFEST_PLUGIN = SourceInfo(precedence=4)
    DEFAULT = SourceInfo(precedence=5)

    def __str__(self) -> str:
        return self.name
    def __repr__(self) -> str:
        return f"<ConfigSource.{self.name}>"

class ConfigDefault:
    """Marker class representing a default configuration value."""
    
    def __repr__(self) -> str:
        return "<ConfigDefault>"
    def __str__(self) -> str:
        return "*Default"

class ConfigRequired:
    """Marker class to supplement default values, indicating a required configuration option. Why this isn't its own field is beyond me."""
    
    def __repr__(self) -> str:
        return "<ConfigRequired>"
    def __str__(self) -> str:
        return "*Required"
    
class NameList(list):
    """A list subclass that provides better string representation for configuration names."""
    def __repr__(self) -> str:
        string = ".".join(str(part) for part in self)
        return f"<NameList: {string}>"
    def __str__(self) -> str:
        return ".".join(str(part) for part in self)


@dataclass(frozen=False, order=True)
class ConfigOption:
    """Definition of a configuration option.

    Attributes:
        default: The default value for the configuration option.
        name: The hierarchical name/path of the configuration option.
        description: An optional description of the configuration option.
        sources: An unordered list of configuration sources to consider - automatically ordered by precedence.
        source_names: Optional custom names/paths for each source - if not provided, defaults will be generated.
    """

    default: Any
    name: list[str]  # Name/hierarchy path
    description: str = ""  # Optional description of the config option
    sources: List[ConfigSource] = field(
        default_factory=lambda: [
            ConfigSource.KV_STORE,
            ConfigSource.ENVIRONMENT,
            ConfigSource.MANIFEST_GLOBAL,
            ConfigSource.MANIFEST_PLUGIN,
            ConfigSource.DEFAULT,
        ]
    )
    source_names: Dict[ConfigSource, Union[str, List[str], ConfigDefault]] = field(
        default_factory=dict
    )
    enforce_type: Optional[type] = Any  # Optional type enforcement
    enforce_type_coerce: bool = False  # Whether to coerce types if enforcement is enabled

    def __post_init__(self):
        """Sort sources and generate default source names if not provided."""
        # Sort sources by precedence
        self.sources.sort(key=lambda s: s.value.precedence)
        self._generate_source_names()

    def _generate_source_names(self) -> None:
        """Generate default source names/paths for sources that don't have one."""
        for source in self.sources:
            if source not in self.source_names:
                name = [part.replace(".", "_") for part in self.name]

                if source == ConfigSource.MANIFEST_GLOBAL:
                    self.source_names[source] = NameList(self.name) # Toml files retain hierarchy
                elif source == ConfigSource.MANIFEST_PLUGIN:
                    self.source_names[source] = NameList(self.name) # Toml files retain hierarchy
                elif source == ConfigSource.ENVIRONMENT:
                    self.source_names[source] = "_".join(
                        part.upper() for part in name
                    )
                elif source == ConfigSource.KV_STORE:
                    name = [part.replace("/", "_") for part in name]
                    self.source_names[source] = "/".join(name)
                elif source == ConfigSource.DEFAULT:
                    self.source_names[source] = ConfigDefault() if self.default is not ConfigRequired else ConfigRequired()

    def get_effective_source(self) -> ConfigSource:
        """Get the highest-precedence source available for this option."""
        if not self.sources:
            raise ValueError("No sources defined for this configuration option.")
        return self.sources[0]

    def get_source_name(
        self, source: ConfigSource
    ) -> Union[str, List[str], ConfigDefault]:
        """Get the name/path for a specific source."""
        return self.source_names[source]
    
    def sources_friendly(self) -> str:
        """Get a human-readable string of the sources in order of precedence."""
        return " > ".join(f"{source.name}({self.get_source_name(source)})" for source in self.sources)

class ConfigSchema:
    """
    Base class for configuration schemas.
    Configuration schemas should define configuration options as class attributes.
    Subclasses should be either dataclasses, or dataclass-like structures, such as Pydantic models.
    
    Attributes:
        _options: A dictionary mapping field names to ConfigOption instances.
"""
    _options: Dict[str, ConfigOption] = {}
    
    @classmethod
    def get_options(cls) -> Dict[str, ConfigOption]:
        """Retrieve all configuration options defined in the schema."""
        return cls._options
    
    @classmethod
    async def resolve(cls, config_manager: Any, plugin: Any | None) -> ConfigSchema:
        """Resolve the configuration schema using the provided ConfigManager."""
        return await config_manager.resolve_config(cls, plugin)
    
# Execptions
class ConfigError(Exception):
    """Base exception class for configuration-related errors."""
    pass
class ConfigMissingRequiredError(ConfigError):
    """Exception raised when a required configuration option is missing."""
    pass
class ConfigTypeEnforcementError(ConfigError):
    """Exception raised when type enforcement fails for a configuration option."""
    pass
class ConfigTypeCoercionError(ConfigTypeEnforcementError):
    """Exception raised when type coercion fails for a configuration option."""
    pass