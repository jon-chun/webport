"""
WebPort Core Module

Core functionality including configuration, logging, exceptions, and utilities.
"""

from webport.core.config import WebPortConfig, Environment, SiteType, MigrationTarget
from webport.core.exceptions import WebPortError, ErrorSummary
from webport.core.logger import setup_logging, get_logger, LogConfig
from webport.core.retry import with_retry, with_async_retry, get_circuit_manager
from webport.core.checkpoint import CheckpointManager, CrawlCheckpoint, compute_content_hash
from webport.core.shutdown import get_shutdown_manager, graceful_shutdown
from webport.core.plugins import BasePlugin, PluginRegistry, get_plugin_registry, plugin
from webport.core.container import Container, ContainerBuilder, Lifetime, get_container

__all__ = [
    # Config
    "WebPortConfig",
    "Environment",
    "SiteType", 
    "MigrationTarget",
    # Exceptions
    "WebPortError",
    "ErrorSummary",
    # Logging
    "setup_logging",
    "get_logger",
    "LogConfig",
    # Retry
    "with_retry",
    "with_async_retry",
    "get_circuit_manager",
    # Checkpoint
    "CheckpointManager",
    "CrawlCheckpoint",
    "compute_content_hash",
    # Shutdown
    "get_shutdown_manager",
    "graceful_shutdown",
    # Plugins
    "BasePlugin",
    "PluginRegistry",
    "get_plugin_registry",
    "plugin",
    # DI Container
    "Container",
    "ContainerBuilder",
    "Lifetime",
    "get_container",
]
