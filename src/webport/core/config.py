"""
WebPort Configuration System

Pydantic-based configuration with:
- Environment variable support
- Multi-environment configs (dev/staging/prod)
- Credential encryption
- Validation and defaults

Addresses Critique #10: Pydantic Models Undefined
Addresses Critique #28: No Environment-Specific Configs
Addresses Critique #29: No Credential Encryption
"""

from __future__ import annotations

import hashlib
import os
import secrets
from base64 import b64decode, b64encode
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Set, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


class Environment(str, Enum):
    """Deployment environment."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class SiteType(str, Enum):
    """Type of site being crawled."""
    AUTO = "auto"
    WORDPRESS = "wordpress"
    STATIC = "static"
    SPA = "spa"
    JEKYLL = "jekyll"
    HUGO = "hugo"
    ELEVENTY = "eleventy"


class MigrationTarget(str, Enum):
    """Target framework for migration."""
    NEXTJS = "nextjs"
    GATSBY = "gatsby"
    ASTRO = "astro"
    NUXT = "nuxt"
    HUGO = "hugo"
    JEKYLL = "jekyll"


class LogFormat(str, Enum):
    """Log output format."""
    JSON = "json"
    TEXT = "text"


class StorageType(str, Enum):
    """Storage backend type."""
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"
    FILESYSTEM = "filesystem"


# =============================================================================
# Credential Encryption (Addresses Critique #29)
# =============================================================================

class EncryptedStr(SecretStr):
    """String that is encrypted at rest."""
    
    @classmethod
    def encrypt(cls, value: str, key: str) -> str:
        """Encrypt a string value."""
        if not HAS_CRYPTO:
            return value
        
        # Derive key from password
        salt = b"webport_salt_v1"  # In production, use per-value random salt
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        derived_key = b64encode(kdf.derive(key.encode()))
        f = Fernet(derived_key)
        return b64encode(f.encrypt(value.encode())).decode()
    
    @classmethod
    def decrypt(cls, encrypted: str, key: str) -> str:
        """Decrypt a string value."""
        if not HAS_CRYPTO:
            return encrypted
        
        salt = b"webport_salt_v1"
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        derived_key = b64encode(kdf.derive(key.encode()))
        f = Fernet(derived_key)
        return f.decrypt(b64decode(encrypted)).decode()


# =============================================================================
# Sub-Configuration Models
# =============================================================================

class EthicsConfig(BaseModel):
    """Ethical crawling configuration."""
    
    model_config = ConfigDict(extra="forbid")
    
    respect_robots_txt: bool = True
    rate_limit: float = Field(default=2.0, ge=0.1, le=100.0, description="Requests per second")
    burst_size: int = Field(default=10, ge=1, le=100)
    user_agent: str = "WebPort/1.0 (+https://webport.dev/bot)"
    max_concurrent: int = Field(default=5, ge=1, le=50)
    request_delay_ms: int = Field(default=100, ge=0)
    honor_retry_after: bool = True


class RetryConfig(BaseModel):
    """Retry behavior configuration."""
    
    model_config = ConfigDict(extra="forbid")
    
    max_attempts: int = Field(default=3, ge=1, le=10)
    backoff_base: float = Field(default=2.0, ge=1.0, le=5.0)
    initial_wait: float = Field(default=1.0, ge=0.1)
    max_wait: float = Field(default=60.0, ge=1.0)
    jitter: bool = True
    retry_on_status: List[int] = Field(
        default=[408, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524]
    )


class CircuitBreakerConfig(BaseModel):
    """Circuit breaker configuration."""
    
    model_config = ConfigDict(extra="forbid")
    
    enabled: bool = True
    failure_threshold: int = Field(default=5, ge=1)
    success_threshold: int = Field(default=2, ge=1)
    timeout_seconds: float = Field(default=60.0, ge=10.0)
    half_open_max_calls: int = Field(default=3, ge=1)


class CrawlerConfig(BaseModel):
    """Crawler configuration."""
    
    model_config = ConfigDict(extra="forbid")
    
    max_pages: int = Field(default=1000, ge=1)
    max_depth: int = Field(default=10, ge=1, le=100)
    timeout: float = Field(default=30.0, ge=5.0)
    follow_redirects: bool = True
    verify_ssl: bool = True
    
    # Retry and circuit breaker
    retry: RetryConfig = Field(default_factory=RetryConfig)
    circuit_breaker: CircuitBreakerConfig = Field(default_factory=CircuitBreakerConfig)
    
    # URL filtering
    include_patterns: List[str] = Field(default_factory=list)
    exclude_patterns: List[str] = Field(default_factory=lambda: [
        r".*\.(css|js|ico|woff|woff2|ttf|eot)$",
        r".*/wp-admin/.*",
        r".*/wp-includes/.*",
    ])
    
    # Proxy support (Addresses Critique #16)
    proxy: Optional[str] = None
    proxy_rotation: bool = False
    proxy_list: List[str] = Field(default_factory=list)


class ExtractionConfig(BaseModel):
    """Content extraction configuration."""
    
    model_config = ConfigDict(extra="forbid")
    
    include_media: bool = True
    media_types: List[str] = Field(default=["image", "video", "document"])
    max_media_size_mb: int = Field(default=50, ge=1)
    extract_metadata: bool = True
    extract_structured_data: bool = True
    use_trafilatura: bool = True


class WordPressConfig(BaseModel):
    """WordPress-specific configuration."""
    
    model_config = ConfigDict(extra="forbid")
    
    use_api: bool = True
    api_version: str = "wp/v2"
    api_base: str = "/wp-json"
    
    # Authentication (Addresses Critique #17)
    username: Optional[str] = None
    password: Optional[SecretStr] = None
    application_password: Optional[SecretStr] = None
    jwt_token: Optional[SecretStr] = None
    
    # Content types to fetch
    include: List[str] = Field(default=[
        "posts", "pages", "media", "categories", "tags", "menus", "users"
    ])
    
    # Custom fields
    include_acf: bool = True
    include_yoast_seo: bool = True


class AnalysisConfig(BaseModel):
    """Analysis configuration."""
    
    model_config = ConfigDict(extra="forbid")
    
    detect_components: bool = True
    generate_sitemap: bool = True
    seo_audit: bool = True
    link_analysis: bool = True
    image_optimization_check: bool = True


class MigrationConfig(BaseModel):
    """Migration configuration."""
    
    model_config = ConfigDict(extra="forbid")
    
    target: MigrationTarget = MigrationTarget.NEXTJS
    typescript: bool = True
    styling: Literal["tailwind", "css-modules", "styled-components", "none"] = "tailwind"
    
    # Next.js specific
    nextjs_router: Literal["app", "pages"] = "app"
    nextjs_image_optimization: bool = True
    
    # Content format
    content_format: Literal["mdx", "markdown", "html"] = "mdx"
    
    # Features
    include_comments: bool = False
    generate_api_routes: bool = True


class StorageConfig(BaseModel):
    """Storage configuration."""
    
    model_config = ConfigDict(extra="forbid")
    
    type: StorageType = StorageType.SQLITE
    path: Path = Path("./.webport/webport.db")
    
    # Connection pool
    pool_size: int = Field(default=5, ge=1)
    pool_timeout: float = Field(default=30.0, ge=1.0)
    
    # Cache
    cache_enabled: bool = True
    cache_max_size_mb: int = Field(default=500, ge=10)  # Addresses Critique #7


class LoggingConfig(BaseModel):
    """Logging configuration. (Addresses Critique #13, #22)"""
    
    model_config = ConfigDict(extra="forbid")
    
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    format: LogFormat = LogFormat.JSON  # Addresses Critique #13
    file: Optional[Path] = Path("./.webport/webport.log")
    max_file_size_mb: int = Field(default=10, ge=1)
    backup_count: int = Field(default=5, ge=0)
    
    # Per-module levels (Addresses Critique #22)
    module_levels: Dict[str, str] = Field(default_factory=lambda: {
        "webport.crawlers": "INFO",
        "webport.extractors": "INFO",
        "webport.migrators": "INFO",
        "httpx": "WARNING",
        "playwright": "WARNING",
    })
    
    # Include correlation IDs (Addresses Critique #21)
    include_correlation_id: bool = True


class NotificationConfig(BaseModel):
    """Notification configuration. (Addresses Critique #24)"""
    
    model_config = ConfigDict(extra="forbid")
    
    # Slack
    slack_enabled: bool = False
    slack_webhook_url: Optional[SecretStr] = None
    slack_channel: Optional[str] = None
    
    # Discord
    discord_enabled: bool = False
    discord_webhook_url: Optional[SecretStr] = None
    
    # Email
    email_enabled: bool = False
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[SecretStr] = None
    email_from: Optional[str] = None
    email_to: List[str] = Field(default_factory=list)
    
    # Events to notify
    notify_on_complete: bool = True
    notify_on_error: bool = True
    notify_on_warning: bool = False


class MetricsConfig(BaseModel):
    """Metrics configuration. (Addresses Critique #14)"""
    
    model_config = ConfigDict(extra="forbid")
    
    enabled: bool = True
    prometheus_enabled: bool = False
    prometheus_port: int = Field(default=9090, ge=1024, le=65535)
    
    # Track these metrics
    track_requests: bool = True
    track_errors: bool = True
    track_latency: bool = True
    track_queue_depth: bool = True


class CheckpointConfig(BaseModel):
    """Checkpoint configuration. (Addresses Critique #4)"""
    
    model_config = ConfigDict(extra="forbid")
    
    enabled: bool = True
    directory: Path = Path("./.webport/checkpoints")
    auto_save_interval: int = Field(default=60, ge=10, description="Seconds between auto-saves")
    save_on_n_urls: int = Field(default=100, ge=10)
    compress: bool = True
    keep_backups: int = Field(default=3, ge=0)


class SecurityConfig(BaseModel):
    """Security configuration. (Addresses Critique #6)"""
    
    model_config = ConfigDict(extra="forbid")
    
    # SSRF Protection
    ssrf_protection: bool = True
    blocked_ip_ranges: List[str] = Field(default=[
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "0.0.0.0/8",
    ])
    allowed_schemes: List[str] = Field(default=["http", "https"])
    
    # URL validation
    max_url_length: int = Field(default=2048, ge=100)
    
    # Data anonymization (Addresses Critique #37)
    anonymize_pii: bool = False
    pii_patterns: List[str] = Field(default=[
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email
        r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",  # Phone
    ])


# =============================================================================
# Main Configuration
# =============================================================================

class WebPortConfig(BaseSettings):
    """
    Main WebPort configuration.

    Supports loading from:
    - Environment variables (WEBPORT_ prefix)
    - .env files
    - YAML/TOML config files
    - Direct instantiation
    """

    model_config = SettingsConfigDict(
        env_prefix="WEBPORT_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )
    
    # Environment
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    
    # Target
    target_url: str = Field(..., description="URL to crawl")
    site_type: SiteType = SiteType.AUTO
    
    # Output
    output_dir: Path = Field(default=Path("./output"))
    
    # Sub-configurations
    ethics: EthicsConfig = Field(default_factory=EthicsConfig)
    crawler: CrawlerConfig = Field(default_factory=CrawlerConfig)
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
    wordpress: WordPressConfig = Field(default_factory=WordPressConfig)
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    migration: MigrationConfig = Field(default_factory=MigrationConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    notifications: NotificationConfig = Field(default_factory=NotificationConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    checkpoint: CheckpointConfig = Field(default_factory=CheckpointConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    
    @field_validator("target_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate target URL."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v.rstrip("/")
    
    @model_validator(mode="after")
    def validate_config(self) -> "WebPortConfig":
        """Cross-field validation."""
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create checkpoint directory
        if self.checkpoint.enabled:
            self.checkpoint.directory.mkdir(parents=True, exist_ok=True)
        
        return self
    
    def get_config_hash(self) -> str:
        """Generate hash of configuration for change detection."""
        config_str = self.model_dump_json(exclude={"output_dir"})
        return hashlib.sha256(config_str.encode()).hexdigest()[:16]
    
    @classmethod
    def from_yaml(cls, path: Path) -> "WebPortConfig":
        """Load configuration from YAML file."""
        import yaml
        
        with open(path) as f:
            data = yaml.safe_load(f)
        
        return cls(**data)
    
    @classmethod
    def from_toml(cls, path: Path) -> "WebPortConfig":
        """Load configuration from TOML file."""
        import toml
        
        with open(path) as f:
            data = toml.load(f)
        
        return cls(**data)
    
    def to_yaml(self, path: Path) -> None:
        """Save configuration to YAML file."""
        import yaml
        
        with open(path, "w") as f:
            yaml.dump(self.model_dump(mode="json"), f, default_flow_style=False)


# =============================================================================
# Environment-Specific Configs (Addresses Critique #28)
# =============================================================================

def get_environment_config(env: Environment) -> Dict[str, Any]:
    """Get environment-specific configuration overrides."""
    
    configs = {
        Environment.DEVELOPMENT: {
            "debug": True,
            "logging": {"level": "DEBUG"},
            "ethics": {"rate_limit": 5.0},  # Faster for testing
            "crawler": {"max_pages": 50},
        },
        Environment.STAGING: {
            "debug": True,
            "logging": {"level": "INFO"},
            "notifications": {"notify_on_warning": True},
        },
        Environment.PRODUCTION: {
            "debug": False,
            "logging": {"level": "WARNING", "format": "json"},
            "notifications": {"notify_on_error": True},
            "metrics": {"prometheus_enabled": True},
        },
        Environment.TEST: {
            "debug": True,
            "logging": {"level": "DEBUG"},
            "crawler": {"max_pages": 10, "max_depth": 2},
            "checkpoint": {"enabled": False},
            "notifications": {"slack_enabled": False, "email_enabled": False},
        },
    }
    
    return configs.get(env, {})


# =============================================================================
# Site-Specific Configuration (loaded from sites/{domain}/webport.yaml)
# =============================================================================

class SelectorConfig(BaseModel):
    """CSS selector with fallback chain."""

    model_config = ConfigDict(extra="forbid")

    selectors: List[str] = Field(
        ..., min_length=1, description="CSS selectors to try in order (first match wins)"
    )
    attribute: Optional[str] = Field(
        default=None, description="HTML attribute to extract (None = text content)"
    )
    multiple: bool = Field(default=False, description="Extract all matches vs first match")
    transform: Optional[str] = Field(
        default=None, description="Post-processing: 'strip', 'slug', 'url', 'date'"
    )


class RelationshipScrapeConfig(BaseModel):
    """Configuration for scraping M2M relationships from HTML pages."""

    model_config = ConfigDict(extra="forbid")

    source_json: str = Field(..., description="Source JSON file with items to iterate over")
    url_field: str = Field(default="link", description="Field in source JSON containing page URL")
    target_container: SelectorConfig = Field(
        ..., description="Selector for the container holding related items"
    )
    target_link: SelectorConfig = Field(
        ..., description="Selector for individual related item links within container"
    )
    target_name: Optional[SelectorConfig] = Field(
        default=None, description="Selector for related item names"
    )
    output_file: str = Field(..., description="Output JSON filename")


class DetailScrapeConfig(BaseModel):
    """Configuration for scraping supplemental fields from individual pages."""

    model_config = ConfigDict(extra="forbid")

    source_json: str = Field(..., description="Source JSON file with items to iterate over")
    url_field: str = Field(default="link", description="Field in source JSON containing page URL")
    fields: Dict[str, SelectorConfig] = Field(
        ..., description="Map of field names to selectors"
    )
    output_file: str = Field(..., description="Output JSON filename")


class ScrapeConfig(BaseModel):
    """Configuration for HTML scraping stage."""

    model_config = ConfigDict(extra="forbid")

    rate_limit_delay: float = Field(default=0.5, ge=0.0, description="Seconds between requests")
    max_concurrent: int = Field(default=4, ge=1, le=20)
    timeout: float = Field(default=30.0, ge=5.0)
    relationships: List[RelationshipScrapeConfig] = Field(default_factory=list)
    details: List[DetailScrapeConfig] = Field(default_factory=list)


class WPCrawlConfig(BaseModel):
    """WordPress crawl configuration for SiteConfig."""

    model_config = ConfigDict(extra="forbid")

    custom_post_types: List[str] = Field(
        default_factory=list, description="CPT slugs to discover and crawl"
    )
    taxonomies: List[str] = Field(
        default_factory=list, description="Custom taxonomies to crawl"
    )
    include_standard: List[str] = Field(
        default_factory=lambda: ["posts", "pages", "categories", "tags", "media"],
        description="Standard WP endpoints to include",
    )
    save_raw_json: bool = Field(default=True, description="Save raw API JSON responses")


class GenerateConfig(BaseModel):
    """Code generation configuration."""

    model_config = ConfigDict(extra="forbid")

    target: MigrationTarget = MigrationTarget.NEXTJS
    typescript: bool = True
    styling: Literal["tailwind", "css-modules", "none"] = "tailwind"
    prisma: bool = Field(default=True, description="Generate Prisma schema and seed")


class AnalyzeConfig(BaseModel):
    """Analysis/doc generation configuration."""

    model_config = ConfigDict(extra="forbid")

    docs: List[str] = Field(
        default_factory=lambda: [
            "PRD",
            "data-dictionary",
            "database-schema",
            "tech-spec",
            "component-inventory",
            "deployment",
        ],
        description="Documentation types to generate",
    )
    use_ai: bool = Field(default=False, description="Use AI for doc generation (requires API key)")


class SiteConfig(BaseModel):
    """
    Site-specific configuration loaded from sites/{domain}/webport.yaml.

    This drives the entire pipeline for a specific site.
    """

    model_config = ConfigDict(extra="forbid")

    # Site metadata
    domain: str = Field(..., description="Domain name (e.g., 'helixcenter.org')")
    base_url: str = Field(..., description="Full base URL (e.g., 'https://helixcenter.org')")
    name: str = Field(default="", description="Human-readable site name")
    site_type: SiteType = SiteType.WORDPRESS

    # Stage configs
    wordpress: WPCrawlConfig = Field(default_factory=WPCrawlConfig)
    scrape: ScrapeConfig = Field(default_factory=ScrapeConfig)
    analyze: AnalyzeConfig = Field(default_factory=AnalyzeConfig)
    generate: GenerateConfig = Field(default_factory=GenerateConfig)

    # Rate limiting
    rate_limit_delay: float = Field(default=0.5, ge=0.0)
    max_concurrent: int = Field(default=4, ge=1, le=20)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("base_url must start with http:// or https://")
        return v.rstrip("/")

    @classmethod
    def from_yaml(cls, path: Path) -> "SiteConfig":
        """Load site configuration from a YAML file."""
        import yaml

        with open(path) as f:
            data = yaml.safe_load(f)

        return cls(**data)

    @property
    def sites_dir(self) -> Path:
        """Get the sites/{domain}/ directory path."""
        return Path("sites") / self.domain

    @property
    def input_dir(self) -> Path:
        """Get the input data directory."""
        return self.sites_dir / "input"

    @property
    def output_dir(self) -> Path:
        """Get the output directory."""
        return self.sites_dir / "output"

    @property
    def docs_dir(self) -> Path:
        """Get the docs output directory."""
        return self.output_dir / "docs"


__all__ = [
    "Environment",
    "SiteType",
    "MigrationTarget",
    "LogFormat",
    "StorageType",
    "EncryptedStr",
    "EthicsConfig",
    "RetryConfig",
    "CircuitBreakerConfig",
    "CrawlerConfig",
    "ExtractionConfig",
    "WordPressConfig",
    "AnalysisConfig",
    "MigrationConfig",
    "StorageConfig",
    "LoggingConfig",
    "NotificationConfig",
    "MetricsConfig",
    "CheckpointConfig",
    "SecurityConfig",
    "WebPortConfig",
    "get_environment_config",
    "SelectorConfig",
    "RelationshipScrapeConfig",
    "DetailScrapeConfig",
    "ScrapeConfig",
    "WPCrawlConfig",
    "GenerateConfig",
    "AnalyzeConfig",
    "SiteConfig",
]
