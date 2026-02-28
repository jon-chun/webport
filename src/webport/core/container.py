"""
WebPort Dependency Injection Container

Simple dependency injection for managing component lifecycles.

Addresses Critique #42: No Dependency Injection Container
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from enum import Enum, auto
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
    get_type_hints,
)

logger = logging.getLogger(__name__)


T = TypeVar("T")


class Lifetime(Enum):
    """Service lifetime options."""
    
    TRANSIENT = auto()    # New instance every time
    SCOPED = auto()       # One instance per scope
    SINGLETON = auto()    # One instance for application


@dataclass
class ServiceDescriptor(Generic[T]):
    """Describes a registered service."""
    
    service_type: Type[T]
    implementation: Union[Type[T], Callable[..., T], T]
    lifetime: Lifetime
    factory: Optional[Callable[..., T]] = None


class ServiceScope:
    """A scope for scoped services."""
    
    def __init__(self, container: "Container"):
        self._container = container
        self._instances: Dict[Type, Any] = {}
        self._disposed = False
    
    def get(self, service_type: Type[T]) -> T:
        """Get a service from this scope."""
        if self._disposed:
            raise RuntimeError("Scope has been disposed")
        
        # Check if already instantiated in this scope
        if service_type in self._instances:
            return self._instances[service_type]
        
        # Get descriptor
        descriptor = self._container._get_descriptor(service_type)
        
        if descriptor is None:
            raise KeyError(f"Service not registered: {service_type}")
        
        if descriptor.lifetime == Lifetime.SINGLETON:
            # Singleton - get from container
            return self._container.get(service_type)
        
        # Create instance
        instance = self._container._create_instance(descriptor, self)
        
        if descriptor.lifetime == Lifetime.SCOPED:
            self._instances[service_type] = instance
        
        return instance
    
    def dispose(self) -> None:
        """Dispose of scoped instances."""
        for instance in self._instances.values():
            if hasattr(instance, "dispose"):
                try:
                    instance.dispose()
                except Exception as e:
                    logger.error(f"Error disposing {type(instance)}: {e}")
            elif hasattr(instance, "close"):
                try:
                    instance.close()
                except Exception as e:
                    logger.error(f"Error closing {type(instance)}: {e}")
        
        self._instances.clear()
        self._disposed = True
    
    async def dispose_async(self) -> None:
        """Dispose of scoped instances asynchronously."""
        for instance in self._instances.values():
            if hasattr(instance, "dispose_async"):
                try:
                    await instance.dispose_async()
                except Exception as e:
                    logger.error(f"Error disposing {type(instance)}: {e}")
            elif hasattr(instance, "aclose"):
                try:
                    await instance.aclose()
                except Exception as e:
                    logger.error(f"Error closing {type(instance)}: {e}")
            elif hasattr(instance, "dispose"):
                try:
                    instance.dispose()
                except Exception as e:
                    logger.error(f"Error disposing {type(instance)}: {e}")
        
        self._instances.clear()
        self._disposed = True


class Container:
    """
    Dependency injection container.
    
    Example:
        >>> container = Container()
        >>> 
        >>> # Register services
        >>> container.register(ILogger, ConsoleLogger, Lifetime.SINGLETON)
        >>> container.register(IDatabase, PostgresDatabase, Lifetime.SCOPED)
        >>> container.register(IService, MyService, Lifetime.TRANSIENT)
        >>> 
        >>> # Resolve services
        >>> logger = container.get(ILogger)
        >>> 
        >>> # Use scopes
        >>> with container.create_scope() as scope:
        ...     db = scope.get(IDatabase)
    """
    
    def __init__(self):
        self._descriptors: Dict[Type, ServiceDescriptor] = {}
        self._singletons: Dict[Type, Any] = {}
        self._disposed = False
    
    def register(
        self,
        service_type: Type[T],
        implementation: Union[Type[T], Callable[..., T], T, None] = None,
        lifetime: Lifetime = Lifetime.TRANSIENT,
    ) -> "Container":
        """
        Register a service.
        
        Args:
            service_type: The service interface/type
            implementation: The implementation class, factory, or instance
            lifetime: Service lifetime
            
        Returns:
            Self for chaining
        """
        if implementation is None:
            implementation = service_type
        
        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation=implementation,
            lifetime=lifetime,
        )
        
        self._descriptors[service_type] = descriptor
        logger.debug(f"Registered {service_type.__name__} as {lifetime.name}")
        
        return self
    
    def register_factory(
        self,
        service_type: Type[T],
        factory: Callable[..., T],
        lifetime: Lifetime = Lifetime.TRANSIENT,
    ) -> "Container":
        """Register a factory function."""
        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation=factory,
            lifetime=lifetime,
            factory=factory,
        )
        
        self._descriptors[service_type] = descriptor
        return self
    
    def register_instance(self, service_type: Type[T], instance: T) -> "Container":
        """Register an existing instance as a singleton."""
        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation=instance,
            lifetime=Lifetime.SINGLETON,
        )
        
        self._descriptors[service_type] = descriptor
        self._singletons[service_type] = instance
        return self
    
    def _get_descriptor(self, service_type: Type[T]) -> Optional[ServiceDescriptor[T]]:
        """Get descriptor for a service type."""
        return self._descriptors.get(service_type)
    
    def _create_instance(
        self,
        descriptor: ServiceDescriptor[T],
        scope: Optional[ServiceScope] = None,
    ) -> T:
        """Create an instance from a descriptor."""
        impl = descriptor.implementation
        
        # If it's already an instance
        if not isinstance(impl, type) and not callable(impl):
            return impl
        
        # If it's a factory
        if descriptor.factory:
            return self._invoke_factory(descriptor.factory, scope)
        
        # If it's a class, resolve dependencies
        if isinstance(impl, type):
            return self._instantiate_class(impl, scope)
        
        # If it's a callable (but not a class)
        if callable(impl):
            return self._invoke_factory(impl, scope)
        
        raise TypeError(f"Cannot create instance from {impl}")
    
    def _instantiate_class(
        self,
        cls: Type[T],
        scope: Optional[ServiceScope] = None,
    ) -> T:
        """Instantiate a class with dependency injection."""
        # Get constructor parameters
        try:
            hints = get_type_hints(cls.__init__)
        except Exception:
            hints = {}
        
        sig = inspect.signature(cls.__init__)
        kwargs = {}
        
        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
            
            # Get type hint
            param_type = hints.get(param_name)
            
            if param_type and param_type in self._descriptors:
                # Resolve dependency
                if scope:
                    kwargs[param_name] = scope.get(param_type)
                else:
                    kwargs[param_name] = self.get(param_type)
            elif param.default is not inspect.Parameter.empty:
                # Use default
                pass
            else:
                # Required parameter without registration
                raise TypeError(
                    f"Cannot resolve parameter '{param_name}' of type "
                    f"'{param_type}' for {cls.__name__}"
                )
        
        return cls(**kwargs)
    
    def _invoke_factory(
        self,
        factory: Callable[..., T],
        scope: Optional[ServiceScope] = None,
    ) -> T:
        """Invoke a factory function with dependency injection."""
        try:
            hints = get_type_hints(factory)
        except Exception:
            hints = {}
        
        sig = inspect.signature(factory)
        kwargs = {}
        
        for param_name, param in sig.parameters.items():
            param_type = hints.get(param_name)
            
            if param_type and param_type in self._descriptors:
                if scope:
                    kwargs[param_name] = scope.get(param_type)
                else:
                    kwargs[param_name] = self.get(param_type)
            elif param.default is not inspect.Parameter.empty:
                pass
            else:
                raise TypeError(
                    f"Cannot resolve parameter '{param_name}' for factory"
                )
        
        return factory(**kwargs)
    
    def get(self, service_type: Type[T]) -> T:
        """Get a service instance."""
        if self._disposed:
            raise RuntimeError("Container has been disposed")
        
        descriptor = self._get_descriptor(service_type)
        
        if descriptor is None:
            raise KeyError(f"Service not registered: {service_type}")
        
        # Check for singleton
        if descriptor.lifetime == Lifetime.SINGLETON:
            if service_type not in self._singletons:
                self._singletons[service_type] = self._create_instance(descriptor)
            return self._singletons[service_type]
        
        # For scoped/transient, create new instance
        return self._create_instance(descriptor)
    
    def try_get(self, service_type: Type[T]) -> Optional[T]:
        """Try to get a service, returning None if not found."""
        try:
            return self.get(service_type)
        except KeyError:
            return None
    
    def is_registered(self, service_type: Type) -> bool:
        """Check if a service is registered."""
        return service_type in self._descriptors
    
    def create_scope(self) -> ServiceScope:
        """Create a new service scope."""
        return ServiceScope(self)
    
    @contextmanager
    def scope(self):
        """Context manager for service scope."""
        scope = self.create_scope()
        try:
            yield scope
        finally:
            scope.dispose()
    
    @asynccontextmanager
    async def scope_async(self):
        """Async context manager for service scope."""
        scope = self.create_scope()
        try:
            yield scope
        finally:
            await scope.dispose_async()
    
    def dispose(self) -> None:
        """Dispose of the container and all singletons."""
        for instance in self._singletons.values():
            if hasattr(instance, "dispose"):
                try:
                    instance.dispose()
                except Exception as e:
                    logger.error(f"Error disposing {type(instance)}: {e}")
        
        self._singletons.clear()
        self._descriptors.clear()
        self._disposed = True
    
    async def dispose_async(self) -> None:
        """Dispose of the container asynchronously."""
        for instance in self._singletons.values():
            if hasattr(instance, "dispose_async"):
                try:
                    await instance.dispose_async()
                except Exception as e:
                    logger.error(f"Error disposing {type(instance)}: {e}")
            elif hasattr(instance, "dispose"):
                try:
                    instance.dispose()
                except Exception as e:
                    logger.error(f"Error disposing {type(instance)}: {e}")
        
        self._singletons.clear()
        self._descriptors.clear()
        self._disposed = True


class ContainerBuilder:
    """
    Builder for creating configured containers.
    
    Example:
        >>> builder = ContainerBuilder()
        >>> builder.add_singleton(IConfig, AppConfig)
        >>> builder.add_scoped(IDatabase, Database)
        >>> builder.add_transient(IService, MyService)
        >>> 
        >>> container = builder.build()
    """
    
    def __init__(self):
        self._registrations: List[tuple] = []
    
    def add_singleton(
        self,
        service_type: Type[T],
        implementation: Union[Type[T], Callable[..., T], T, None] = None,
    ) -> "ContainerBuilder":
        """Add a singleton service."""
        self._registrations.append(
            (service_type, implementation, Lifetime.SINGLETON)
        )
        return self
    
    def add_scoped(
        self,
        service_type: Type[T],
        implementation: Union[Type[T], Callable[..., T], None] = None,
    ) -> "ContainerBuilder":
        """Add a scoped service."""
        self._registrations.append(
            (service_type, implementation, Lifetime.SCOPED)
        )
        return self
    
    def add_transient(
        self,
        service_type: Type[T],
        implementation: Union[Type[T], Callable[..., T], None] = None,
    ) -> "ContainerBuilder":
        """Add a transient service."""
        self._registrations.append(
            (service_type, implementation, Lifetime.TRANSIENT)
        )
        return self
    
    def build(self) -> Container:
        """Build the container."""
        container = Container()
        
        for service_type, implementation, lifetime in self._registrations:
            container.register(service_type, implementation, lifetime)
        
        return container


# Global container
_container: Optional[Container] = None


def get_container() -> Container:
    """Get the global container."""
    global _container
    if _container is None:
        _container = Container()
    return _container


def configure_container(builder_fn: Callable[[ContainerBuilder], None]) -> Container:
    """Configure and set the global container."""
    global _container
    
    builder = ContainerBuilder()
    builder_fn(builder)
    _container = builder.build()
    
    return _container


__all__ = [
    "Lifetime",
    "ServiceDescriptor",
    "ServiceScope",
    "Container",
    "ContainerBuilder",
    "get_container",
    "configure_container",
]
