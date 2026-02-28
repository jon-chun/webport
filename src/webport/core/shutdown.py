"""
WebPort Graceful Shutdown System

Signal handling with state preservation.

Addresses Critique #3: No Graceful Shutdown Handling
"""

from __future__ import annotations

import asyncio
import atexit
import logging
import os
import signal
import threading
from contextlib import contextmanager, asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from functools import wraps
from typing import Any, Callable, Coroutine, Dict, List, Optional, TypeVar

logger = logging.getLogger(__name__)
T = TypeVar("T")
CleanupCallback = Callable[[], None]
AsyncCleanupCallback = Callable[[], Coroutine[Any, Any, None]]


class ShutdownReason(Enum):
    NORMAL = auto()
    USER_INTERRUPT = auto()
    TERMINATE = auto()
    HANGUP = auto()
    ERROR = auto()
    TIMEOUT = auto()
    MANUAL = auto()


class ShutdownPhase(Enum):
    RUNNING = auto()
    INITIATED = auto()
    SAVING_STATE = auto()
    CLOSING_CONNECTIONS = auto()
    CLEANUP = auto()
    COMPLETE = auto()


@dataclass
class ShutdownState:
    phase: ShutdownPhase = ShutdownPhase.RUNNING
    reason: Optional[ShutdownReason] = None
    initiated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    interrupt_count: int = 0
    force_threshold: int = 3
    errors: List[str] = field(default_factory=list)
    
    @property
    def is_shutting_down(self) -> bool:
        return self.phase not in (ShutdownPhase.RUNNING, ShutdownPhase.COMPLETE)
    
    @property
    def duration_seconds(self) -> float:
        if not self.initiated_at:
            return 0.0
        end = self.completed_at or datetime.utcnow()
        return (end - self.initiated_at).total_seconds()


class ShutdownManager:
    """Centralized shutdown management with signal handling."""
    
    _instance: Optional["ShutdownManager"] = None
    
    def __new__(cls) -> "ShutdownManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, timeout_seconds: float = 30.0, force_after_interrupts: int = 3):
        if getattr(self, "_initialized", False):
            return
        
        self.timeout_seconds = timeout_seconds
        self.force_after_interrupts = force_after_interrupts
        self.state = ShutdownState(force_threshold=force_after_interrupts)
        self._sync_callbacks: List[tuple[int, str, CleanupCallback]] = []
        self._async_callbacks: List[tuple[int, str, AsyncCleanupCallback]] = []
        self._lock = threading.RLock()
        self._shutdown_event = threading.Event()
        self._original_handlers: Dict[int, Any] = {}
        self._initialized = True
    
    def on_shutdown(self, priority: int = 50, name: Optional[str] = None):
        """Decorator to register shutdown callback."""
        def decorator(func: CleanupCallback) -> CleanupCallback:
            callback_name = name or func.__name__
            with self._lock:
                self._sync_callbacks.append((priority, callback_name, func))
                self._sync_callbacks.sort(key=lambda x: x[0])
            return func
        return decorator
    
    def on_async_shutdown(self, priority: int = 50, name: Optional[str] = None):
        """Decorator to register async shutdown callback."""
        def decorator(func: AsyncCleanupCallback) -> AsyncCleanupCallback:
            callback_name = name or func.__name__
            with self._lock:
                self._async_callbacks.append((priority, callback_name, func))
                self._async_callbacks.sort(key=lambda x: x[0])
            return func
        return decorator
    
    def register_callback(self, callback: CleanupCallback, priority: int = 50, 
                          name: Optional[str] = None) -> None:
        callback_name = name or getattr(callback, "__name__", "anonymous")
        with self._lock:
            self._sync_callbacks.append((priority, callback_name, callback))
            self._sync_callbacks.sort(key=lambda x: x[0])
    
    def install_handlers(self) -> None:
        """Install signal handlers."""
        signals_to_handle = [signal.SIGINT, signal.SIGTERM]
        if hasattr(signal, "SIGHUP"):
            signals_to_handle.append(signal.SIGHUP)
        
        for sig in signals_to_handle:
            try:
                self._original_handlers[sig] = signal.getsignal(sig)
                signal.signal(sig, self._signal_handler)
            except (ValueError, OSError):
                pass
        
        atexit.register(self._atexit_handler)
        logger.info("[Shutdown] Signal handlers installed")
    
    def uninstall_handlers(self) -> None:
        """Restore original signal handlers."""
        for sig, handler in self._original_handlers.items():
            try:
                signal.signal(sig, handler)
            except (ValueError, OSError):
                pass
        self._original_handlers.clear()
        atexit.unregister(self._atexit_handler)
    
    def _signal_handler(self, signum: int, frame: Any) -> None:
        sig = signal.Signals(signum)
        with self._lock:
            self.state.interrupt_count += 1
            
            reason_map = {signal.SIGINT: ShutdownReason.USER_INTERRUPT, 
                         signal.SIGTERM: ShutdownReason.TERMINATE}
            if hasattr(signal, "SIGHUP"):
                reason_map[signal.SIGHUP] = ShutdownReason.HANGUP
            
            reason = reason_map.get(sig, ShutdownReason.TERMINATE)
            logger.warning(f"\n[Shutdown] Received {sig.name}")
            
            if self.state.interrupt_count >= self.state.force_threshold:
                logger.critical("[Shutdown] Force exit!")
                os._exit(1)
            
            if self.state.is_shutting_down:
                return
            
            self._start_shutdown(reason)
    
    def _atexit_handler(self) -> None:
        if not self.state.is_shutting_down:
            self.shutdown(ShutdownReason.NORMAL)
    
    def _start_shutdown(self, reason: ShutdownReason) -> None:
        self.state.phase = ShutdownPhase.INITIATED
        self.state.reason = reason
        self.state.initiated_at = datetime.utcnow()
        self._shutdown_event.set()
        
        shutdown_thread = threading.Thread(target=self._run_shutdown, daemon=False)
        shutdown_thread.start()
    
    def shutdown(self, reason: ShutdownReason = ShutdownReason.NORMAL, 
                 timeout: Optional[float] = None) -> None:
        if self.state.is_shutting_down:
            return
        
        with self._lock:
            self.state.phase = ShutdownPhase.INITIATED
            self.state.reason = reason
            self.state.initiated_at = datetime.utcnow()
        
        self._shutdown_event.set()
        self._run_shutdown(timeout)
    
    def _run_shutdown(self, timeout: Optional[float] = None) -> None:
        try:
            self.state.phase = ShutdownPhase.SAVING_STATE
            logger.info("[Shutdown] Saving state...")
            self._run_callbacks_by_priority_range(0, 30)
            
            self.state.phase = ShutdownPhase.CLOSING_CONNECTIONS
            logger.info("[Shutdown] Closing connections...")
            self._run_callbacks_by_priority_range(30, 60)
            
            self.state.phase = ShutdownPhase.CLEANUP
            logger.info("[Shutdown] Cleanup...")
            self._run_callbacks_by_priority_range(60, 1000)
            
            self.state.phase = ShutdownPhase.COMPLETE
            self.state.completed_at = datetime.utcnow()
            logger.info(f"[Shutdown] Complete ({self.state.duration_seconds:.2f}s)")
            
        except Exception as e:
            logger.error(f"[Shutdown] Error: {e}")
            self.state.errors.append(str(e))
    
    def _run_callbacks_by_priority_range(self, min_p: int, max_p: int) -> None:
        for priority, name, callback in self._sync_callbacks:
            if min_p <= priority < max_p:
                try:
                    callback()
                except Exception as e:
                    self.state.errors.append(f"{name}: {e}")
    
    @property
    def is_shutting_down(self) -> bool:
        return self.state.is_shutting_down
    
    def wait_for_shutdown(self, timeout: Optional[float] = None) -> bool:
        return self._shutdown_event.wait(timeout)
    
    def check_shutdown(self) -> None:
        if self.state.is_shutting_down:
            raise KeyboardInterrupt("Shutdown requested")


_shutdown_manager: Optional[ShutdownManager] = None


def get_shutdown_manager() -> ShutdownManager:
    global _shutdown_manager
    if _shutdown_manager is None:
        _shutdown_manager = ShutdownManager()
    return _shutdown_manager


def install_shutdown_handlers() -> ShutdownManager:
    manager = get_shutdown_manager()
    manager.install_handlers()
    return manager


@contextmanager
def graceful_shutdown(timeout_seconds: float = 30.0, 
                      save_state_callback: Optional[CleanupCallback] = None):
    """Context manager for graceful shutdown."""
    manager = get_shutdown_manager()
    manager.timeout_seconds = timeout_seconds
    manager.install_handlers()
    
    if save_state_callback:
        manager.register_callback(save_state_callback, priority=5, name="save_state")
    
    try:
        yield manager
        manager.shutdown(ShutdownReason.NORMAL)
    except KeyboardInterrupt:
        manager.shutdown(ShutdownReason.USER_INTERRUPT)
    except Exception as e:
        manager.shutdown(ShutdownReason.ERROR)
        raise
    finally:
        manager.uninstall_handlers()


def interruptible(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator that makes a function respect shutdown signals."""
    @wraps(func)
    def wrapper(*args, **kwargs) -> T:
        manager = get_shutdown_manager()
        if manager.is_shutting_down:
            raise KeyboardInterrupt("Shutdown in progress")
        return func(*args, **kwargs)
    return wrapper


__all__ = [
    "ShutdownReason", "ShutdownPhase", "ShutdownState", "ShutdownManager",
    "get_shutdown_manager", "install_shutdown_handlers", "graceful_shutdown",
    "interruptible",
]
