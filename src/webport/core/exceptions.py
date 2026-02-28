"""
WebPort Exception Hierarchy

Comprehensive exception tree for standardized error handling across the package.
All exceptions include context for debugging, error categorization, and recovery hints.

Addresses Critique #2: No Exception Hierarchy Implementation
Addresses Critique #25: No Error Categorization Report
"""

from __future__ import annotations

import logging
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Type


logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Categories for error aggregation and reporting."""
    NETWORK = auto()
    HTTP = auto()
    AUTHENTICATION = auto()
    RATE_LIMIT = auto()
    PARSING = auto()
    VALIDATION = auto()
    IO = auto()
    CONFIGURATION = auto()
    MIGRATION = auto()
    SECURITY = auto()
    RESOURCE = auto()
    UNKNOWN = auto()


class ErrorSeverity(Enum):
    """Severity levels for error handling decisions."""
    DEBUG = 10
    WARNING = 20
    ERROR = 30
    CRITICAL = 40
    FATAL = 50


class RecoveryStrategy(Enum):
    """Suggested recovery strategies for error handlers."""
    RETRY = auto()
    SKIP = auto()
    ABORT = auto()
    ABORT_ALL = auto()
    WAIT_AND_RETRY = auto()
    FALLBACK = auto()
    MANUAL = auto()


@dataclass
class ErrorContext:
    """Rich context container for debugging and error reporting."""
    
    timestamp: datetime = field(default_factory=datetime.utcnow)
    correlation_id: Optional[str] = None
    url: Optional[str] = None
    operation: Optional[str] = None
    component: Optional[str] = None
    http_method: Optional[str] = None
    http_status: Optional[int] = None
    response_headers: Optional[Dict[str, str]] = None
    attempt_number: int = 1
    max_attempts: int = 3
    elapsed_time_ms: Optional[float] = None
    request_payload: Optional[Dict[str, Any]] = None
    response_body_preview: Optional[str] = None
    stack_trace: Optional[str] = None
    caused_by: Optional[Exception] = None
    related_errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON logging."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "correlation_id": self.correlation_id,
            "url": self.url,
            "operation": self.operation,
            "component": self.component,
            "http_method": self.http_method,
            "http_status": self.http_status,
            "attempt": f"{self.attempt_number}/{self.max_attempts}",
            "elapsed_ms": self.elapsed_time_ms,
            "caused_by": str(self.caused_by) if self.caused_by else None,
        }
    
    def with_traceback(self) -> "ErrorContext":
        """Capture current stack trace."""
        self.stack_trace = traceback.format_exc()
        return self


class WebPortError(Exception):
    """Base exception for all WebPort errors."""
    
    default_category: ErrorCategory = ErrorCategory.UNKNOWN
    default_severity: ErrorSeverity = ErrorSeverity.ERROR
    default_recovery: RecoveryStrategy = RecoveryStrategy.SKIP
    
    def __init__(
        self,
        message: str,
        *,
        category: Optional[ErrorCategory] = None,
        severity: Optional[ErrorSeverity] = None,
        recovery: Optional[RecoveryStrategy] = None,
        context: Optional[ErrorContext] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.message = message
        self.category = category or self.default_category
        self.severity = severity or self.default_severity
        self.recovery = recovery or self.default_recovery
        self.context = context or ErrorContext()
        
        if cause:
            self.__cause__ = cause
            self.context.caused_by = cause
        
        if self.severity.value >= ErrorSeverity.ERROR.value:
            self.context.with_traceback()
    
    @property
    def is_retryable(self) -> bool:
        return self.recovery in (RecoveryStrategy.RETRY, RecoveryStrategy.WAIT_AND_RETRY)
    
    @property
    def should_abort(self) -> bool:
        return self.recovery in (RecoveryStrategy.ABORT, RecoveryStrategy.ABORT_ALL)


# Network Errors
class NetworkError(WebPortError):
    default_category = ErrorCategory.NETWORK
    default_recovery = RecoveryStrategy.RETRY


class ConnectionError(NetworkError):
    default_severity = ErrorSeverity.ERROR
    
    def __init__(self, url: str, cause: Optional[Exception] = None, **kwargs):
        super().__init__(
            f"Failed to connect to {url}",
            context=ErrorContext(url=url),
            cause=cause,
            **kwargs
        )


class TimeoutError(NetworkError):
    default_severity = ErrorSeverity.WARNING
    
    def __init__(self, url: str, timeout_seconds: float, cause: Optional[Exception] = None, **kwargs):
        super().__init__(
            f"Request timed out after {timeout_seconds}s",
            context=ErrorContext(url=url, elapsed_time_ms=timeout_seconds * 1000),
            cause=cause,
            **kwargs
        )


class DNSError(NetworkError):
    default_severity = ErrorSeverity.ERROR
    default_recovery = RecoveryStrategy.SKIP


class SSLError(NetworkError):
    default_category = ErrorCategory.SECURITY
    default_severity = ErrorSeverity.ERROR


# HTTP Errors
class HTTPError(WebPortError):
    default_category = ErrorCategory.HTTP
    
    def __init__(self, url: str, status_code: int, status_text: Optional[str] = None, 
                 response_body: Optional[str] = None, **kwargs):
        message = f"HTTP {status_code}"
        if status_text:
            message += f" {status_text}"
        
        if status_code >= 500:
            severity = ErrorSeverity.ERROR
            recovery = RecoveryStrategy.RETRY
        elif status_code == 429:
            severity = ErrorSeverity.WARNING
            recovery = RecoveryStrategy.WAIT_AND_RETRY
        elif status_code in (401, 403):
            severity = ErrorSeverity.ERROR
            recovery = RecoveryStrategy.ABORT
        elif status_code == 404:
            severity = ErrorSeverity.WARNING
            recovery = RecoveryStrategy.SKIP
        else:
            severity = ErrorSeverity.WARNING
            recovery = RecoveryStrategy.SKIP
        
        super().__init__(
            message,
            severity=severity,
            recovery=recovery,
            context=ErrorContext(
                url=url,
                http_status=status_code,
                response_body_preview=response_body[:500] if response_body else None,
            ),
            **kwargs
        )
        self.status_code = status_code


class NotFoundError(HTTPError):
    def __init__(self, url: str, **kwargs):
        super().__init__(url, 404, "Not Found", **kwargs)


class ForbiddenError(HTTPError):
    default_category = ErrorCategory.AUTHENTICATION
    def __init__(self, url: str, **kwargs):
        super().__init__(url, 403, "Forbidden", **kwargs)


class UnauthorizedError(HTTPError):
    default_category = ErrorCategory.AUTHENTICATION
    def __init__(self, url: str, **kwargs):
        super().__init__(url, 401, "Unauthorized", **kwargs)


class RateLimitError(HTTPError):
    default_category = ErrorCategory.RATE_LIMIT
    default_recovery = RecoveryStrategy.WAIT_AND_RETRY
    
    def __init__(self, url: str, retry_after: Optional[int] = None, **kwargs):
        super().__init__(url, 429, "Too Many Requests", **kwargs)
        self.retry_after = retry_after or 60


class ServerError(HTTPError):
    def __init__(self, url: str, status_code: int, **kwargs):
        super().__init__(url, status_code, "Server Error", **kwargs)


# Crawler Errors
class CrawlerError(WebPortError):
    default_category = ErrorCategory.NETWORK


class RobotsBlockedError(CrawlerError):
    default_category = ErrorCategory.SECURITY
    default_severity = ErrorSeverity.WARNING
    default_recovery = RecoveryStrategy.SKIP


class CircuitBreakerOpenError(CrawlerError):
    default_severity = ErrorSeverity.WARNING
    default_recovery = RecoveryStrategy.WAIT_AND_RETRY
    
    def __init__(self, domain: str, open_until: datetime, **kwargs):
        wait_seconds = (open_until - datetime.utcnow()).total_seconds()
        super().__init__(
            f"Circuit breaker open for {domain}, retry in {wait_seconds:.0f}s",
            context=ErrorContext(url=domain),
            **kwargs
        )
        self.domain = domain
        self.open_until = open_until


class MaxDepthExceededError(CrawlerError):
    default_severity = ErrorSeverity.WARNING
    default_recovery = RecoveryStrategy.SKIP


class MaxPagesExceededError(CrawlerError):
    default_severity = ErrorSeverity.WARNING
    default_recovery = RecoveryStrategy.ABORT


# Parsing Errors
class ParsingError(WebPortError):
    default_category = ErrorCategory.PARSING
    default_recovery = RecoveryStrategy.SKIP


class HTMLParsingError(ParsingError):
    pass


class JSONParsingError(ParsingError):
    pass


class XMLParsingError(ParsingError):
    pass


class ExtractionError(WebPortError):
    default_category = ErrorCategory.PARSING


# WordPress Errors
class WordPressError(WebPortError):
    pass


class WordPressAPIError(WordPressError):
    def __init__(self, url: str, wp_code: str, wp_message: str, status_code: int, **kwargs):
        super().__init__(
            f"WordPress API error: {wp_code} - {wp_message}",
            context=ErrorContext(url=url, http_status=status_code),
            **kwargs
        )
        self.wp_code = wp_code
        self.wp_message = wp_message


class WordPressNotDetectedError(WordPressError):
    default_severity = ErrorSeverity.ERROR
    default_recovery = RecoveryStrategy.ABORT


# Validation Errors
class ValidationError(WebPortError):
    default_category = ErrorCategory.VALIDATION
    default_recovery = RecoveryStrategy.SKIP


class URLValidationError(ValidationError):
    default_category = ErrorCategory.SECURITY


class SSRFProtectionError(ValidationError):
    """URL blocked by SSRF protection. (Addresses Critique #6)"""
    default_category = ErrorCategory.SECURITY
    default_severity = ErrorSeverity.WARNING


class DataValidationError(ValidationError):
    pass


# Resource Errors
class ResourceError(WebPortError):
    default_category = ErrorCategory.RESOURCE
    default_severity = ErrorSeverity.CRITICAL


class MemoryLimitError(ResourceError):
    """Memory limit exceeded. (Addresses Critique #7)"""
    pass


class DiskSpaceError(ResourceError):
    """Insufficient disk space. (Addresses Critique #9)"""
    default_recovery = RecoveryStrategy.ABORT


# Configuration Errors
class ConfigurationError(WebPortError):
    default_category = ErrorCategory.CONFIGURATION
    default_severity = ErrorSeverity.FATAL
    default_recovery = RecoveryStrategy.ABORT_ALL


class MissingConfigError(ConfigurationError):
    pass


class InvalidConfigError(ConfigurationError):
    pass


# Migration Errors
class MigrationError(WebPortError):
    default_category = ErrorCategory.MIGRATION


class TemplateError(MigrationError):
    pass


class UnsupportedFeatureError(MigrationError):
    default_severity = ErrorSeverity.WARNING
    default_recovery = RecoveryStrategy.SKIP


# I/O Errors
class IOError(WebPortError):
    default_category = ErrorCategory.IO


class FileWriteError(IOError):
    pass


class FileReadError(IOError):
    pass


# Checkpoint Errors
class CheckpointError(WebPortError):
    default_category = ErrorCategory.IO


class CheckpointSaveError(CheckpointError):
    pass


class CheckpointLoadError(CheckpointError):
    pass


class CheckpointCorruptError(CheckpointError):
    default_recovery = RecoveryStrategy.ABORT


# Scraper Errors
class ScraperError(WebPortError):
    """Error during HTML scraping stage."""
    default_category = ErrorCategory.PARSING
    default_recovery = RecoveryStrategy.SKIP


class SelectorError(ScraperError):
    """CSS selector evaluation failed."""
    pass


# Analysis Errors
class AnalysisError(WebPortError):
    """Error during analysis/doc generation stage."""
    default_category = ErrorCategory.PARSING
    default_recovery = RecoveryStrategy.SKIP


class GeneratorError(WebPortError):
    """Error during code generation stage."""
    default_category = ErrorCategory.MIGRATION
    default_recovery = RecoveryStrategy.SKIP


class ArchiveError(WebPortError):
    """Error during ZIP archive creation."""
    default_category = ErrorCategory.IO
    default_recovery = RecoveryStrategy.ABORT


# Error Aggregator (Addresses Critique #25)
@dataclass
class ErrorSummary:
    """Summary of errors for reporting."""
    
    total_errors: int = 0
    by_category: Dict[ErrorCategory, int] = field(default_factory=dict)
    by_severity: Dict[ErrorSeverity, int] = field(default_factory=dict)
    by_type: Dict[str, int] = field(default_factory=dict)
    sample_errors: List[WebPortError] = field(default_factory=list)
    
    def add(self, error: WebPortError) -> None:
        self.total_errors += 1
        self.by_category[error.category] = self.by_category.get(error.category, 0) + 1
        self.by_severity[error.severity] = self.by_severity.get(error.severity, 0) + 1
        error_type = error.__class__.__name__
        self.by_type[error_type] = self.by_type.get(error_type, 0) + 1
        
        if len([e for e in self.sample_errors if type(e).__name__ == error_type]) < 10:
            self.sample_errors.append(error)
    
    def report(self) -> str:
        lines = [
            f"\n{'='*60}",
            f"ERROR SUMMARY: {self.total_errors} total errors",
            f"{'='*60}",
            "",
            "By Category:",
        ]
        for cat, count in sorted(self.by_category.items(), key=lambda x: -x[1]):
            lines.append(f"  {cat.name}: {count}")
        lines.extend(["", "By Type:"])
        for err_type, count in sorted(self.by_type.items(), key=lambda x: -x[1]):
            lines.append(f"  {err_type}: {count}")
        return "\n".join(lines)


__all__ = [
    "ErrorCategory", "ErrorSeverity", "RecoveryStrategy", "ErrorContext",
    "WebPortError", "NetworkError", "ConnectionError", "TimeoutError",
    "DNSError", "SSLError", "HTTPError", "NotFoundError", "ForbiddenError",
    "UnauthorizedError", "RateLimitError", "ServerError", "CrawlerError",
    "RobotsBlockedError", "CircuitBreakerOpenError", "MaxDepthExceededError",
    "MaxPagesExceededError", "ParsingError", "HTMLParsingError", "JSONParsingError",
    "XMLParsingError", "ExtractionError", "WordPressError", "WordPressAPIError",
    "WordPressNotDetectedError", "ValidationError", "URLValidationError",
    "SSRFProtectionError", "DataValidationError", "ResourceError", "MemoryLimitError",
    "DiskSpaceError", "ConfigurationError", "MissingConfigError", "InvalidConfigError",
    "MigrationError", "TemplateError", "UnsupportedFeatureError", "IOError",
    "FileWriteError", "FileReadError", "CheckpointError", "CheckpointSaveError",
    "CheckpointLoadError", "CheckpointCorruptError", "ScraperError", "SelectorError",
    "AnalysisError", "GeneratorError", "ArchiveError", "ErrorSummary",
]
