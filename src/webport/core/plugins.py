"""
WebPort Plugin System

Extensible plugin architecture for crawlers, extractors, and migrators.

Addresses Critique #30: No Plugin Architecture
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar

logger = logging.getLogger(__name__)


# Type variable for plugin classes
T = TypeVar("T", bound="BasePlugin")


@dataclass
class PluginInfo:
    """Information about a registered plugin."""
    
    name: str
    version: str
    description: str
    author: Optional[str] = None
    plugin_class: Optional[Type["BasePlugin"]] = None
    enabled: bool = True
    priority: int = 100  # Lower = higher priority
    hooks: List[str] = field(default_factory=list)


class BasePlugin(ABC):
    """
    Base class for all plugins.
    
    Plugins can hook into various stages of the WebPort pipeline:
    - pre_crawl: Before crawling starts
    - post_crawl: After crawling completes
    - on_page_crawled: After each page is crawled
    - pre_extract: Before content extraction
    - post_extract: After content extraction
    - pre_migrate: Before migration starts
    - post_migrate: After migration completes
    """
    
    # Plugin metadata (override in subclasses)
    name: str = "base_plugin"
    version: str = "0.1.0"
    description: str = "Base plugin"
    author: Optional[str] = None
    priority: int = 100
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._enabled = True
    
    @property
    def enabled(self) -> bool:
        return self._enabled
    
    def enable(self) -> None:
        self._enabled = True
    
    def disable(self) -> None:
        self._enabled = False
    
    def get_info(self) -> PluginInfo:
        """Get plugin information."""
        hooks = []
        for method_name in dir(self):
            if method_name.startswith("on_") or method_name.startswith(("pre_", "post_")):
                method = getattr(self, method_name)
                if callable(method) and not method_name.startswith("_"):
                    hooks.append(method_name)
        
        return PluginInfo(
            name=self.name,
            version=self.version,
            description=self.description,
            author=self.author,
            plugin_class=type(self),
            enabled=self._enabled,
            priority=self.priority,
            hooks=hooks,
        )
    
    # Hook methods (override as needed)
    
    async def pre_crawl(self, context: Dict[str, Any]) -> None:
        """Called before crawling starts."""
        pass
    
    async def post_crawl(self, context: Dict[str, Any]) -> None:
        """Called after crawling completes."""
        pass
    
    async def on_page_crawled(self, page: Any, context: Dict[str, Any]) -> None:
        """Called after each page is crawled."""
        pass
    
    async def pre_extract(self, html: str, context: Dict[str, Any]) -> str:
        """Called before content extraction. Can modify HTML."""
        return html
    
    async def post_extract(self, content: Any, context: Dict[str, Any]) -> Any:
        """Called after content extraction. Can modify content."""
        return content
    
    async def pre_migrate(self, context: Dict[str, Any]) -> None:
        """Called before migration starts."""
        pass
    
    async def post_migrate(self, context: Dict[str, Any]) -> None:
        """Called after migration completes."""
        pass


class PluginRegistry:
    """
    Registry for managing plugins.
    
    Example:
        >>> registry = PluginRegistry()
        >>> registry.register(MyPlugin)
        >>> 
        >>> # Load plugins from directory
        >>> registry.load_from_directory(Path("./plugins"))
        >>> 
        >>> # Execute hooks
        >>> await registry.execute_hook("pre_crawl", context)
    """
    
    def __init__(self):
        self._plugins: Dict[str, BasePlugin] = {}
        self._plugin_classes: Dict[str, Type[BasePlugin]] = {}
    
    def register(
        self,
        plugin_class: Type[BasePlugin],
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a plugin class."""
        if not issubclass(plugin_class, BasePlugin):
            raise TypeError(f"{plugin_class} must be a subclass of BasePlugin")
        
        name = plugin_class.name
        self._plugin_classes[name] = plugin_class
        self._plugins[name] = plugin_class(config)
        
        logger.info(f"Registered plugin: {name} v{plugin_class.version}")
    
    def unregister(self, name: str) -> None:
        """Unregister a plugin."""
        if name in self._plugins:
            del self._plugins[name]
            del self._plugin_classes[name]
            logger.info(f"Unregistered plugin: {name}")
    
    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        """Get a plugin by name."""
        return self._plugins.get(name)
    
    def list_plugins(self) -> List[PluginInfo]:
        """List all registered plugins."""
        return [p.get_info() for p in self._plugins.values()]
    
    def enable_plugin(self, name: str) -> None:
        """Enable a plugin."""
        if plugin := self._plugins.get(name):
            plugin.enable()
    
    def disable_plugin(self, name: str) -> None:
        """Disable a plugin."""
        if plugin := self._plugins.get(name):
            plugin.disable()
    
    def load_from_directory(self, directory: Path) -> int:
        """
        Load plugins from a directory.
        
        Each plugin should be in its own subdirectory with a plugin.py file.
        
        Returns:
            Number of plugins loaded
        """
        loaded = 0
        directory = Path(directory)
        
        if not directory.exists():
            logger.warning(f"Plugin directory not found: {directory}")
            return 0
        
        for plugin_dir in directory.iterdir():
            if not plugin_dir.is_dir():
                continue
            
            plugin_file = plugin_dir / "plugin.py"
            if not plugin_file.exists():
                continue
            
            try:
                # Load module
                spec = importlib.util.spec_from_file_location(
                    f"webport_plugin_{plugin_dir.name}",
                    plugin_file,
                )
                
                if not spec or not spec.loader:
                    continue
                
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Find plugin class
                for name, obj in inspect.getmembers(module):
                    if (
                        inspect.isclass(obj)
                        and issubclass(obj, BasePlugin)
                        and obj is not BasePlugin
                    ):
                        self.register(obj)
                        loaded += 1
                        break
                
            except Exception as e:
                logger.error(f"Failed to load plugin from {plugin_dir}: {e}")
        
        logger.info(f"Loaded {loaded} plugins from {directory}")
        return loaded
    
    def load_from_entrypoints(self, group: str = "webport.plugins") -> int:
        """
        Load plugins from entry points.
        
        Uses the standard Python entry points mechanism.
        
        Returns:
            Number of plugins loaded
        """
        loaded = 0
        
        try:
            from importlib.metadata import entry_points
            
            eps = entry_points()
            
            # Handle different Python versions
            if hasattr(eps, "select"):
                plugin_eps = eps.select(group=group)
            else:
                plugin_eps = eps.get(group, [])
            
            for ep in plugin_eps:
                try:
                    plugin_class = ep.load()
                    self.register(plugin_class)
                    loaded += 1
                except Exception as e:
                    logger.error(f"Failed to load plugin {ep.name}: {e}")
            
        except Exception as e:
            logger.warning(f"Could not load entry points: {e}")
        
        logger.info(f"Loaded {loaded} plugins from entry points")
        return loaded
    
    async def execute_hook(
        self,
        hook_name: str,
        *args,
        **kwargs,
    ) -> List[Any]:
        """
        Execute a hook on all enabled plugins.
        
        Plugins are executed in priority order (lower = first).
        
        Returns:
            List of results from each plugin
        """
        results = []
        
        # Sort plugins by priority
        sorted_plugins = sorted(
            self._plugins.values(),
            key=lambda p: p.priority,
        )
        
        for plugin in sorted_plugins:
            if not plugin.enabled:
                continue
            
            hook = getattr(plugin, hook_name, None)
            
            if hook and callable(hook):
                try:
                    result = await hook(*args, **kwargs)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Plugin {plugin.name} hook {hook_name} failed: {e}")
        
        return results
    
    async def execute_transform_hook(
        self,
        hook_name: str,
        value: Any,
        context: Dict[str, Any],
    ) -> Any:
        """
        Execute a transform hook that passes data through plugins.
        
        Each plugin can modify the value before passing to the next.
        
        Returns:
            Final transformed value
        """
        sorted_plugins = sorted(
            self._plugins.values(),
            key=lambda p: p.priority,
        )
        
        for plugin in sorted_plugins:
            if not plugin.enabled:
                continue
            
            hook = getattr(plugin, hook_name, None)
            
            if hook and callable(hook):
                try:
                    value = await hook(value, context)
                except Exception as e:
                    logger.error(f"Plugin {plugin.name} hook {hook_name} failed: {e}")
        
        return value


# Global plugin registry
_registry: Optional[PluginRegistry] = None


def get_plugin_registry() -> PluginRegistry:
    """Get the global plugin registry."""
    global _registry
    if _registry is None:
        _registry = PluginRegistry()
    return _registry


def register_plugin(
    plugin_class: Type[BasePlugin],
    config: Optional[Dict[str, Any]] = None,
) -> None:
    """Register a plugin with the global registry."""
    get_plugin_registry().register(plugin_class, config)


# Decorator for easy plugin registration
def plugin(
    name: Optional[str] = None,
    version: str = "0.1.0",
    description: str = "",
    priority: int = 100,
) -> Callable[[Type[T]], Type[T]]:
    """
    Decorator to register a plugin class.
    
    Example:
        >>> @plugin(name="my_plugin", version="1.0.0")
        ... class MyPlugin(BasePlugin):
        ...     async def on_page_crawled(self, page, context):
        ...         print(f"Crawled: {page.url}")
    """
    def decorator(cls: Type[T]) -> Type[T]:
        cls.name = name or cls.__name__.lower()
        cls.version = version
        cls.description = description
        cls.priority = priority
        
        register_plugin(cls)
        return cls
    
    return decorator


__all__ = [
    "BasePlugin",
    "PluginInfo",
    "PluginRegistry",
    "get_plugin_registry",
    "register_plugin",
    "plugin",
]
