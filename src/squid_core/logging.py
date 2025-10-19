"""Logging utilities for the framework and plugins."""

import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime

from coloredlogs import ColoredFormatter

class LoggerManager:
    """Manages loggers for the framework and plugins with consistent formatting."""

    def __init__(
        self,
        log_level: str = "INFO",
        debug_mode: bool = False,
        log_file: Optional[Path] = None,
        console_output: bool = True,
    ):
        """
        Initialize the logger manager.

        Args:
            log_level: The base log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            debug_mode: Enable debug mode with more verbose output
            log_file: Optional path to a log file
            console_output: Whether to output logs to console
        """
        self.log_level = self._parse_log_level(log_level)
        self.debug_mode = debug_mode
        self.log_file = log_file
        self.console_output = console_output
        self._loggers = {}

        # Configure root logger
        self._configure_root_logger()

    def _parse_log_level(self, level: str) -> int:
        """Parse log level string to logging constant."""
        try:
            return getattr(logging, level.upper())
        except AttributeError:
            return logging.INFO

    def _configure_root_logger(self):
        """Configure the root logger with handlers and formatters."""
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG if self.debug_mode else self.log_level)

        # Remove existing handlers to avoid duplicates
        root_logger.handlers.clear()

        # Create formatter
        if self.debug_mode:
            # More verbose format for debugging
            formatter = ColoredFormatter(
                fmt="[%(asctime)s] [%(levelname)-8s] [%(name)s:%(funcName)s:%(lineno)d] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        else:
            # Cleaner format for production
            formatter = ColoredFormatter(
                fmt="[%(asctime)s] [%(levelname)-8s] [%(name)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )

        # Console handler
        if self.console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(self.log_level)
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)

        # File handler
        if self.log_file:
            self._setup_file_handler(root_logger, formatter)

    def _setup_file_handler(self, logger: logging.Logger, formatter: logging.Formatter):
        """Set up file handler for logging to a file."""
        try:
            # Ensure log directory exists
            self.log_file.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.FileHandler(
                self.log_file, mode="a", encoding="utf-8"
            )
            file_handler.setLevel(logging.DEBUG)  # Log everything to file
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            # Fallback if file logging fails
            logging.error(f"Failed to set up file logging: {e}")

    def get_logger(self, name: str) -> logging.Logger:
        """
        Get or create a logger with the specified name.

        Args:
            name: The logger name (typically module name or plugin name)

        Returns:
            A configured logger instance
        """
        if name not in self._loggers:
            logger = logging.getLogger(name)
            self._loggers[name] = logger

        return self._loggers[name]

    def get_plugin_logger(self, plugin_name: str) -> logging.Logger:
        """
        Get a logger for a plugin with proper namespace.

        Args:
            plugin_name: The name of the plugin

        Returns:
            A configured logger instance for the plugin
        """
        return self.get_logger(f"squidcore.plugins.{plugin_name}")

    def set_level(self, level: str):
        """
        Change the log level dynamically.

        Args:
            level: The new log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        new_level = self._parse_log_level(level)
        self.log_level = new_level

        root_logger = logging.getLogger()
        root_logger.setLevel(new_level)

        # Update all handlers
        for handler in root_logger.handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(
                handler, logging.FileHandler
            ):
                handler.setLevel(new_level)

    def shutdown(self):
        """Shutdown all logging handlers properly."""
        logging.shutdown()


# Convenience function for getting framework logger
def get_framework_logger(component: str = "core") -> logging.Logger:
    """
    Get a logger for a framework component.

    Args:
        component: The framework component name

    Returns:
        A configured logger instance
    """
    return logging.getLogger(f"squidcore.{component}")
