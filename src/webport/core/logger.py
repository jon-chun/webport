"""
WebPort Logging System

Production-ready logging with:
- Structured JSON output
- Correlation IDs for request tracing
- Per-module log levels
- Rich console output for development
- Rotating file handlers

Addresses Critique #13: No Structured Logging (JSON Format)
Addresses Critique #21: No Log Correlation IDs
Addresses Critique #22: No Per-Module Log Level Configuration
"""

from __future__ import annotations

import json
import logging
import sys
import threading
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional, Union

from rich.console import Console
from rich.logging import RichHandler
from rich.traceback import install as install_rich_traceback


# =============================================================================
# Correlation ID Management (Addresses Critique #21)
# =============================================================================

_correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> str:
    """Get current correlation ID or generate new one."""
    cid = _correlation_id.get()
    if cid is None:
        cid = generate_correlation_id()
        _correlation_id.set(cid)
    return cid


def set_correlation_id(correlation_id: str) -> None:
    """Set correlation ID for current context."""
    _correlation_id.set(correlation_id)


def generate_correlation_id() -> str:
    """Generate a new correlation ID."""
    return str(uuid.uuid4())[:12]


class CorrelationIdFilter(logging.Filter):
    """Add correlation ID to all log records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id()
        return True


# =============================================================================
# JSON Formatter (Addresses Critique #13)
# =============================================================================

class JSONFormatter(logging.Formatter):
    """
    JSON log formatter for structured logging.
    
    Output format:
    {
        "timestamp": "2024-01-15T10:30:00.000Z",
        "level": "INFO",
        "logger": "webport.crawlers",
        "message": "Crawled page",
        "correlation_id": "abc123",
        "extra": {...}
    }
    """
    
    def __init__(
        self,
        include_extra: bool = True,
        include_exception: bool = True,
        timestamp_format: str = "%Y-%m-%dT%H:%M:%S.%f",
    ):
        super().__init__()
        self.include_extra = include_extra
        self.include_exception = include_exception
        self.timestamp_format = timestamp_format
        
        # Standard log record attributes to exclude from extra
        self._standard_attrs = {
            "name", "msg", "args", "created", "filename", "funcName",
            "levelname", "levelno", "lineno", "module", "msecs",
            "pathname", "process", "processName", "relativeCreated",
            "stack_info", "exc_info", "exc_text", "thread", "threadName",
            "message", "correlation_id", "taskName",
        }
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Build base log entry
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.utcfromtimestamp(record.created).strftime(
                self.timestamp_format
            )[:-3] + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add correlation ID
        if hasattr(record, "correlation_id"):
            log_entry["correlation_id"] = record.correlation_id
        
        # Add location info for errors
        if record.levelno >= logging.ERROR:
            log_entry["location"] = {
                "file": record.filename,
                "line": record.lineno,
                "function": record.funcName,
            }
        
        # Add extra fields
        if self.include_extra:
            extra = {}
            for key, value in record.__dict__.items():
                if key not in self._standard_attrs:
                    try:
                        # Ensure value is JSON serializable
                        json.dumps(value)
                        extra[key] = value
                    except (TypeError, ValueError):
                        extra[key] = str(value)
            
            if extra:
                log_entry["extra"] = extra
        
        # Add exception info
        if self.include_exception and record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry, default=str)


# =============================================================================
# Text Formatter (Development)
# =============================================================================

class ColoredFormatter(logging.Formatter):
    """Colored text formatter for development."""
    
    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"
    
    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        
        # Format correlation ID
        cid = getattr(record, "correlation_id", "")[:8] if hasattr(record, "correlation_id") else ""
        cid_str = f"[{cid}] " if cid else ""
        
        # Build message
        timestamp = datetime.utcfromtimestamp(record.created).strftime("%H:%M:%S.%f")[:-3]
        level = f"{color}{record.levelname:8s}{self.RESET}"
        name = f"\033[90m{record.name:30s}\033[0m"
        
        formatted = f"{timestamp} {level} {name} {cid_str}{record.getMessage()}"
        
        if record.exc_info:
            formatted += "\n" + self.formatException(record.exc_info)
        
        return formatted


# =============================================================================
# Logger Configuration
# =============================================================================

@dataclass
class LogConfig:
    """Logger configuration."""
    
    level: str = "INFO"
    format: str = "json"  # json or text
    file: Optional[Path] = None
    max_file_size_mb: int = 10
    backup_count: int = 5
    include_correlation_id: bool = True
    module_levels: Dict[str, str] = field(default_factory=dict)
    console_enabled: bool = True
    rich_console: bool = True  # Use rich for console output


class LoggerManager:
    """
    Centralized logger management.
    
    Example:
        >>> manager = LoggerManager(LogConfig(level="DEBUG"))
        >>> manager.setup()
        >>> 
        >>> logger = manager.get_logger("webport.crawlers")
        >>> logger.info("Starting crawl", extra={"url": "https://example.com"})
    """
    
    _instance: Optional["LoggerManager"] = None
    _lock = threading.Lock()
    
    def __new__(cls, config: Optional[LogConfig] = None) -> "LoggerManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self, config: Optional[LogConfig] = None):
        if self._initialized:
            return
        
        self.config = config or LogConfig()
        self._handlers: list[logging.Handler] = []
        self._initialized = True
    
    def setup(self) -> None:
        """Set up logging system."""
        # Get root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)  # Set to DEBUG, handlers will filter
        
        # Remove existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Add correlation ID filter
        if self.config.include_correlation_id:
            root_logger.addFilter(CorrelationIdFilter())
        
        # Console handler
        if self.config.console_enabled:
            self._add_console_handler(root_logger)
        
        # File handler
        if self.config.file:
            self._add_file_handler(root_logger)
        
        # Set per-module levels (Addresses Critique #22)
        for module, level in self.config.module_levels.items():
            module_logger = logging.getLogger(module)
            module_logger.setLevel(getattr(logging, level.upper()))
        
        # Install rich traceback for better exception display
        if self.config.rich_console:
            install_rich_traceback(show_locals=True, suppress=[])
    
    def _add_console_handler(self, logger: logging.Logger) -> None:
        """Add console handler."""
        if self.config.rich_console and self.config.format == "text":
            # Use Rich handler for pretty output
            console = Console(stderr=True)
            handler = RichHandler(
                console=console,
                show_time=True,
                show_path=False,
                rich_tracebacks=True,
                tracebacks_show_locals=True,
            )
        else:
            handler = logging.StreamHandler(sys.stderr)
            
            if self.config.format == "json":
                handler.setFormatter(JSONFormatter())
            else:
                handler.setFormatter(ColoredFormatter())
        
        handler.setLevel(getattr(logging, self.config.level.upper()))
        logger.addHandler(handler)
        self._handlers.append(handler)
    
    def _add_file_handler(self, logger: logging.Logger) -> None:
        """Add rotating file handler."""
        # Ensure directory exists
        self.config.file.parent.mkdir(parents=True, exist_ok=True)
        
        handler = RotatingFileHandler(
            self.config.file,
            maxBytes=self.config.max_file_size_mb * 1024 * 1024,
            backupCount=self.config.backup_count,
            encoding="utf-8",
        )
        
        # Always use JSON for file logs
        handler.setFormatter(JSONFormatter())
        handler.setLevel(getattr(logging, self.config.level.upper()))
        
        logger.addHandler(handler)
        self._handlers.append(handler)
    
    def get_logger(self, name: str) -> logging.Logger:
        """Get a logger by name."""
        return logging.getLogger(name)
    
    def set_level(self, level: str, module: Optional[str] = None) -> None:
        """Set log level for a module or globally."""
        log_level = getattr(logging, level.upper())
        
        if module:
            logging.getLogger(module).setLevel(log_level)
        else:
            for handler in self._handlers:
                handler.setLevel(log_level)
    
    def shutdown(self) -> None:
        """Shutdown logging system."""
        for handler in self._handlers:
            handler.close()
        self._handlers.clear()


# =============================================================================
# Convenience Functions
# =============================================================================

def setup_logging(
    level: str = "INFO",
    format: str = "json",
    file: Optional[Path] = None,
    module_levels: Optional[Dict[str, str]] = None,
) -> LoggerManager:
    """
    Quick setup for logging.
    
    Args:
        level: Default log level
        format: Output format (json or text)
        file: Optional log file path
        module_levels: Per-module log levels
        
    Returns:
        Configured LoggerManager
        
    Example:
        >>> setup_logging(level="DEBUG", format="text")
        >>> logger = get_logger(__name__)
        >>> logger.info("Ready to go!")
    """
    config = LogConfig(
        level=level,
        format=format,
        file=file,
        module_levels=module_levels or {},
    )
    
    manager = LoggerManager(config)
    manager.setup()
    
    return manager


def get_logger(name: str) -> logging.Logger:
    """Get a logger by name."""
    return logging.getLogger(name)


# =============================================================================
# Context Managers
# =============================================================================

class LogContext:
    """
    Context manager for log context.
    
    Example:
        >>> with LogContext(correlation_id="req-123", operation="crawl"):
        ...     logger.info("Processing")  # Will include correlation_id
    """
    
    def __init__(
        self,
        correlation_id: Optional[str] = None,
        **extra: Any,
    ):
        self.correlation_id = correlation_id
        self.extra = extra
        self._token = None
    
    def __enter__(self) -> "LogContext":
        if self.correlation_id:
            set_correlation_id(self.correlation_id)
        return self
    
    def __exit__(self, *args) -> None:
        pass


# =============================================================================
# Metrics Logger (Addresses Critique #14)
# =============================================================================

class MetricsLogger:
    """
    Specialized logger for metrics and statistics.
    
    Outputs metrics in a structured format suitable for
    ingestion by monitoring systems.
    """
    
    def __init__(self, logger_name: str = "webport.metrics"):
        self.logger = logging.getLogger(logger_name)
    
    def record(
        self,
        metric_name: str,
        value: Union[int, float],
        unit: str = "",
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record a metric value."""
        self.logger.info(
            f"METRIC {metric_name}={value}{unit}",
            extra={
                "metric_type": "gauge",
                "metric_name": metric_name,
                "metric_value": value,
                "metric_unit": unit,
                "tags": tags or {},
            }
        )
    
    def increment(
        self,
        metric_name: str,
        value: int = 1,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Increment a counter metric."""
        self.logger.info(
            f"METRIC {metric_name}+={value}",
            extra={
                "metric_type": "counter",
                "metric_name": metric_name,
                "metric_value": value,
                "tags": tags or {},
            }
        )
    
    def timing(
        self,
        metric_name: str,
        duration_ms: float,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record a timing metric."""
        self.logger.info(
            f"METRIC {metric_name}={duration_ms}ms",
            extra={
                "metric_type": "timing",
                "metric_name": metric_name,
                "metric_value": duration_ms,
                "metric_unit": "ms",
                "tags": tags or {},
            }
        )


# Module-level logger
logger = get_logger(__name__)


__all__ = [
    "get_correlation_id",
    "set_correlation_id",
    "generate_correlation_id",
    "CorrelationIdFilter",
    "JSONFormatter",
    "ColoredFormatter",
    "LogConfig",
    "LoggerManager",
    "setup_logging",
    "get_logger",
    "LogContext",
    "MetricsLogger",
]
