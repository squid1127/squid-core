"""Simple event bus for Squid Core framework."""

class EventBus:
    """A simple event bus to manage and dispatch events."""

    def __init__(self) -> None:
        """Initialize the event bus."""
        self._listeners: dict[str, list[callable]] = {}

    def register_listener(self, event_name: str, listener: callable) -> None:
        """Register a listener for a specific event."""
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        self._listeners[event_name].append(listener)

    async def dispatch(self, event_name: str, *args, **kwargs) -> None:
        """Dispatch an event to all registered listeners."""
        listeners = self._listeners.get(event_name, [])
        for listener in listeners:
            await listener(*args, **kwargs)