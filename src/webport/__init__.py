"""
WebPort - Production-grade WordPress and static site reverse engineering,
migration, and code generation toolkit.

Example:
    >>> from webport import WebPort, WebPortConfig
    >>> 
    >>> config = WebPortConfig(target_url="https://example.com")
    >>> forge = WebPort(config)
    >>> result = await forge.run()
"""

from __future__ import annotations

try:
    from webport._version import __version__, __version_tuple__
except ImportError:
    __version__ = "0.1.0.dev0"
    __version_tuple__ = (0, 1, 0, "dev0")

from webport.core.config import WebPortConfig, Environment, MigrationTarget, SiteType
from webport.core.exceptions import (
    WebPortError,
    CrawlerError,
    HTTPError,
    RateLimitError,
    ValidationError,
)
from webport.core.models import CrawledPage, CrawlResult, MigrationResult
from webport.forge import WebPort

__all__ = [
    # Version
    "__version__",
    "__version_tuple__",
    # Main classes
    "WebPort",
    "WebPortConfig",
    # Config enums
    "Environment",
    "MigrationTarget",
    "SiteType",
    # Exceptions
    "WebPortError",
    "CrawlerError",
    "HTTPError",
    "RateLimitError",
    "ValidationError",
    # Models
    "CrawledPage",
    "CrawlResult",
    "MigrationResult",
]

# Package metadata
__author__ = "WebPort Contributors"
__email__ = "webport@example.com"
__license__ = "MIT"
__url__ = "https://github.com/jon-chun/webport"
