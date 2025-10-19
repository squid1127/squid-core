"""Base class for decorators."""
from abc import ABC, abstractmethod
from ..plugin_base import Plugin, PluginComponent

class DecoratorError(Exception):
    """Custom exception for decorator-related errors."""
    pass
class DecoratorApplyError(DecoratorError):
    """Exception raised when applying a decorator fails."""
    pass

class Decorator(ABC):
    """Abstract base class for decorators."""

    def __init__(self, **kwargs) -> None:
        """Initialize the decorator with given keyword arguments."""
        self.params = kwargs
    
    def __call__(self, func):
        """Apply the decorator to a function."""
        setattr(func, '__decorator_instance__', self)
        return func
    
    @abstractmethod
    async def apply(self, plugin: Plugin, func: callable, *args, **kwargs) -> None:
        """
        Apply the decorator logic.
        
        Args:
            plugin (Plugin): The plugin instance to which the decorator is applied.
            func (callable): The function being decorated.
        """
        pass
    
class DecoratorManager:
    """Manager for handling decorators."""

    decorators: dict[str, type[Decorator]] = {}
    
    @classmethod
    def add(cls, decorator_cls: type[Decorator]) -> type[Decorator]:
        """Register a new decorator class. Can be used as a class decorator."""
        cls.decorators[decorator_cls.__name__] = decorator_cls
        return decorator_cls
        
    @classmethod
    def get(cls, name: str) -> type[Decorator] | None:
        """Retrieve a decorator class by name."""
        return cls.decorators.get(name, None)
    
    @classmethod
    def get_all(cls) -> dict[str, type[Decorator]]:
        """Retrieve all registered decorators."""
        return cls.decorators
    
    @classmethod
    async def apply(
        cls, instance: PluginComponent | Plugin, plugin: Plugin = None
    ) -> None:
        """Apply all registered decorators to the given instance."""
        if not plugin:
            if isinstance(instance, Plugin):
                plugin = instance
            else:
                raise DecoratorApplyError(
                    "Plugin instance must be provided when applying decorators "
                    "to a PluginComponent."
                )
        # Iterate over all attributes of the instance
        for attr_name in dir(instance):
            attr = getattr(instance, attr_name)
            if isinstance(attr, PluginComponent):
                # Recursively apply decorators to nested PluginComponents
                await cls.apply(attr, plugin=plugin)
                continue
            
            if not callable(attr):
                continue
            # Check if the attribute has a decorator instance
            decorator_instance: Decorator | None = getattr(
                attr, '__decorator_instance__', None)
            if decorator_instance:
                try:
                    await decorator_instance.apply(plugin=plugin, func=attr)
                except Exception as e:
                    raise DecoratorApplyError(
                        f"Failed to apply decorator {type(decorator_instance).__name__} "
                        f"to {attr_name}: {str(e)}"
                    ) from e