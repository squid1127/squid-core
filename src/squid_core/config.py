"""Configuration management, including project+plugin manifests, environment variable handling, and kv storage."""

from .config_types import (
    ConfigOption,
    ConfigSource,
    ConfigRequired,
    ConfigSchema,
    ConfigMissingRequiredError,
    ConfigTypeCoercionError,
)
from .logging import get_framework_logger
from .components.db import Database

from tortoise import Model, fields, exceptions

from typing import Any, Dict
from pathlib import Path
from dotenv import load_dotenv

class TypeCoercion:
    """A set of class methods for coercing common types from strings."""
    
    @classmethod
    def convert(cls, value: Any, target_type: type, use_builtin: bool = True) -> Any:
        """
        Convert a value to the target type using either built-in conversion or custom logic.
        
        Probably assumes more than even JS coercion 🤯
        """
        if target_type == bool:
            try:
                return cls.to_bool(value)
            except TypeError:
                pass
        elif target_type == list:
            try:
                return cls.to_list(value)
            except TypeError:
                pass
        
        # Fallback to built-in conversion
        if use_builtin:
            try:
                return target_type(value)
            except (ValueError, TypeError):
                pass
            
        raise ConfigTypeCoercionError(f"No method exists to convert from {type(value)} to {target_type}.")
    
    @classmethod
    def to_bool(cls, value: Any) -> bool:
        """Convert a value to boolean."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            val_lower = value.lower()
            if val_lower in ("true", "1", "yes", "on"):
                return True
            elif val_lower in ("false", "0", "no", "off"):
                return False
        if isinstance(value, (int, float)):
            return value != 0
        raise TypeError(f"Cannot convert {value} to bool.")
    
    @classmethod
    def to_list(cls, value: Any) -> list:
        """Convert a value to a list."""
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            # string list -> assume its a json array
            try:
                json_list = cls.try_json(value)
                if isinstance(json_list, list):
                    return json_list
            except ValueError:
                pass
        raise TypeError(f"Cannot convert {value} to list.")
    
    @classmethod
    def try_json(cls, value: str) -> Any:
        """Attempt to parse a JSON string into a Python object."""
        import json

        try:
            return json.loads(value)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON string: {value}") from e
    
class ConfigManager:
    """Manages configuration options from various sources with defined precedence."""

    def __init__(
        self,
        global_manifest: Path = Path("framework.toml"),
        env_file: Path = None,
    ) -> None:
        self.global_manifest_path = global_manifest
        self.global_manifest: Dict[str, Any] = {}
        self.env_file_path = env_file
        self.db: Database | None = None
        self.logger = get_framework_logger("config")

        if env_file is None:
            load_dotenv()
        else:
            load_dotenv(dotenv_path=env_file)

    async def attach_db(self, db: Any) -> None:
        """Attach a database connection for KV store access."""
        self.logger.info("Attaching database connection to ConfigManager")
        self.db = db

    async def read_toml(self, path: Path) -> Dict[str, Any]:
        """Read a TOML file and return its contents as a dictionary."""
        import tomllib, aiofiles

        async with aiofiles.open(path, "rb") as f:
            content = await f.read()
        return tomllib.loads(content.decode())

    async def get_value_env(self, name: str) -> Any:
        """Retrieve an environment variable by name. Why is this an async function? Good question."""
        import os

        return os.getenv(name)

    def recursive_get(self, data: Dict[str, Any], keys: list[str]) -> Any:
        """Recursively get a value from nested dictionaries."""
        for key in keys:
            if isinstance(data, dict) and key in data:
                data = data[key]
            else:
                return None
        return data

    async def get_value_global_manifest(self, name: list[str]) -> Any:
        """Retrieve a value from the global manifest."""
        if not self.global_manifest:
            self.global_manifest = await self.read_toml(self.global_manifest_path)

        return self.recursive_get(self.global_manifest, name)

    async def get_value_plugin_manifest(self, plugin: Any, name: list[str]) -> Any:
        """Retrieve a value from a plugin's manifest."""
        # TODO: Assign a type for plugin
        raise NotImplementedError("Plugin manifest retrieval not implemented yet.")

    async def get_value_kv_store(self, name: str) -> Any:
        """Retrieve a value from the KV store."""
        if self.db is None:
            raise RuntimeError("Database connection not attached.")
        kv_entry = await KVTable.filter(key=name).first()
        if kv_entry:
            return kv_entry.value
        return None
    
    async def set_value_kv_store(self, name: str, value: Any) -> None:
        """Set a value in the KV store."""
        if self.db is None:
            raise RuntimeError("Database connection not attached.")
        kv_entry = await KVTable.filter(key=name).first()
        if kv_entry:
            kv_entry.value = value
            await kv_entry.save()
        else:
            await KVTable.create(key=name, value=value)

    def enforce_type(
        self, value: Any, expected_type: type | Any, coerce: bool = False
    ) -> Any:
        """Enforce or coerce a value to the expected type. To disable type enforcement, set expected_type to `typing.Any`."""
        if expected_type is Any or isinstance(value, expected_type):
            return value
        if coerce:
                return TypeCoercion.convert(value, expected_type, use_builtin=True)
        raise TypeError(f"Value {value} is not of type {expected_type}.")

    async def get_config_option(self, option: ConfigOption, plugin: Any | None) -> Any:
        """Retrieve a configuration option based on its source and precedence."""
        ordered_sources = sorted(option.sources, key=lambda src: src.value.precedence)
        result: Any = None
        for source in ordered_sources:
            value = None
            source_name = option.source_names.get(source, None)
            self.logger.debug(f"Attempting to retrieve config option '{option.name}' from source '{source.name}' using name '{source_name}'")
            try:
                if source == ConfigSource.ENVIRONMENT:
                    value = await self.get_value_env(source_name)  # type: ignore
                elif source == ConfigSource.MANIFEST_GLOBAL:
                    value = await self.get_value_global_manifest(source_name)  # type: ignore
                elif source == ConfigSource.MANIFEST_PLUGIN and plugin is not None:
                    value = await self.get_value_plugin_manifest(plugin, source_name)  # type: ignore
                elif source == ConfigSource.KV_STORE:
                    value = await self.get_value_kv_store(source_name)  # type: ignore
                elif source == ConfigSource.DEFAULT:
                    if option.default is ConfigRequired:
                        raise ConfigMissingRequiredError(
                            f"Required configuration option missing: {option.name} from sources {option.sources_friendly()}"
                        )
                    value = option.default
            except ConfigMissingRequiredError as e:
                raise e
            except TypeError as e:
                self.logger.warning(
                    f"Type error retrieving config option '{option.name}' from source '{source.name}': {e}"
                )
                continue
            except Exception as e:
                continue
            # Validate and return the first found value
            if value is not None:
                # Attempt to enforce type if specified
                if option.enforce_type is not None:
                    try:
                        value = self.enforce_type(
                            value, option.enforce_type, option.enforce_type_coerce
                        )
                        if value is None:
                            raise ConfigTypeCoercionError(
                                f"Type enforcement resulted in None for config option '{option.name}' from source '{source.name}'"
                            )
                    except ConfigTypeCoercionError as e:
                        self.logger.warning(
                            f"Type enforcement failed for config option '{option.name}' from source '{source.name}': {e}"
                        )
                        continue  # Try the next source if type enforcement fails
                result = value
                self.logger.debug(
                    f"Config option '{option.name}' resolved from source '{source.name}' with value: {result} of type {type(result)}"
                )
                # print(f"Config option '{option.name}' resolved from source '{source.name}' with value: {result}")
                break
        return result

    async def resolve_config(
        self, schema: type[ConfigSchema], plugin: Any | None
    ) -> ConfigSchema:
        """Resolve all configuration options defined in a schema."""
        self.logger.info(f"Resolving config schema: {schema.__name__}")
        resolved_fields: Dict[str, Any] = {}
        for field_name, option in schema.get_options().items():
            resolved_fields[field_name] = await self.get_config_option(option, plugin)
        return schema(**resolved_fields)

    async def get_plugin_manifest(self, path: Path) -> Dict[str, Any]:
        """Retrieve the plugin manifest from the specified path."""
        manifest_path = path / "plugin.toml"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Plugin manifest not found at {manifest_path}")
        manifest = await self.read_toml(manifest_path)
        return manifest

class KVTable(Model):
    """Base class for KV store configuration ORM models."""

    key = fields.CharField(pk=True, max_length=255)
    value = fields.JSONField()