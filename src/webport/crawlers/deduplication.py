"""
WebPort Request Deduplication

URL normalization and deduplication.

Addresses Critique #15: No Request Deduplication
"""

from __future__ import annotations

import hashlib
import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

logger = logging.getLogger(__name__)


@dataclass
class DedupeConfig:
    """Deduplication configuration."""
    
    # URL normalization
    normalize_trailing_slash: bool = True
    remove_fragments: bool = True
    remove_default_ports: bool = True
    sort_query_params: bool = True
    lowercase_hostname: bool = True
    
    # Params to ignore
    ignore_params: Set[str] = field(default_factory=lambda: {
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "fbclid", "gclid", "ref", "source", "_ga", "mc_cid", "mc_eid",
        "sessionid", "sid", "token", "timestamp", "t", "cb",
    })
    
    # Content-based deduplication
    content_hash_enabled: bool = True
    min_content_length: int = 100


class URLNormalizer:
    """Normalizes URLs for deduplication."""
    
    DEFAULT_PORTS = {"http": 80, "https": 443}
    
    def __init__(self, config: Optional[DedupeConfig] = None):
        self.config = config or DedupeConfig()
    
    def normalize(self, url: str) -> str:
        """Normalize URL for comparison."""
        try:
            parsed = urlparse(url)
        except Exception:
            return url
        
        scheme = parsed.scheme.lower()
        
        # Lowercase hostname
        hostname = parsed.hostname or ""
        if self.config.lowercase_hostname:
            hostname = hostname.lower()
        
        # Handle port
        port = parsed.port
        if self.config.remove_default_ports:
            if port == self.DEFAULT_PORTS.get(scheme):
                port = None
        
        netloc = hostname
        if port:
            netloc = f"{hostname}:{port}"
        
        # Handle path
        path = parsed.path
        if self.config.normalize_trailing_slash:
            # Remove trailing slash except for root
            if path != "/" and path.endswith("/"):
                path = path.rstrip("/")
            # Ensure root has slash
            if not path:
                path = "/"
        
        # Normalize path components
        path = self._normalize_path(path)
        
        # Handle query string
        query = parsed.query
        if query:
            query = self._normalize_query(query)
        
        # Handle fragment
        fragment = ""
        if not self.config.remove_fragments:
            fragment = parsed.fragment
        
        # Reconstruct URL
        normalized = urlunparse((scheme, netloc, path, "", query, fragment))
        
        return normalized
    
    def _normalize_path(self, path: str) -> str:
        """Normalize URL path."""
        # Decode percent-encoded characters that don't need encoding
        path = re.sub(r'%([0-9A-Fa-f]{2})', lambda m: self._decode_if_safe(m.group(1)), path)
        
        # Remove double slashes
        while "//" in path:
            path = path.replace("//", "/")
        
        # Remove . and .. components
        components = []
        for component in path.split("/"):
            if component == ".":
                continue
            elif component == "..":
                if components:
                    components.pop()
            else:
                components.append(component)
        
        return "/".join(components)
    
    def _decode_if_safe(self, hex_code: str) -> str:
        """Decode percent-encoded character if it's safe."""
        char = chr(int(hex_code, 16))
        if char.isalnum() or char in "-_.~":
            return char
        return f"%{hex_code.upper()}"
    
    def _normalize_query(self, query: str) -> str:
        """Normalize query string."""
        params = parse_qs(query, keep_blank_values=True)
        
        # Remove ignored params
        for param in self.config.ignore_params:
            params.pop(param, None)
        
        if not params:
            return ""
        
        # Sort params
        if self.config.sort_query_params:
            sorted_params = sorted(params.items())
        else:
            sorted_params = list(params.items())
        
        # Rebuild query string
        parts = []
        for key, values in sorted_params:
            for value in sorted(values):
                parts.append((key, value))
        
        return urlencode(parts)
    
    def get_url_fingerprint(self, url: str) -> str:
        """Get a fingerprint for URL deduplication."""
        normalized = self.normalize(url)
        return hashlib.md5(normalized.encode()).hexdigest()


@dataclass
class SeenURL:
    """Record of a seen URL."""
    url: str
    fingerprint: str
    first_seen: datetime = field(default_factory=datetime.utcnow)
    content_hash: Optional[str] = None
    status: str = "pending"  # pending, crawled, failed


class URLDeduplicator:
    """URL deduplication with content fingerprinting."""
    
    def __init__(self, config: Optional[DedupeConfig] = None):
        self.config = config or DedupeConfig()
        self.normalizer = URLNormalizer(config)
        self._seen_urls: Dict[str, SeenURL] = {}  # fingerprint -> SeenURL
        self._content_hashes: Dict[str, str] = {}  # content_hash -> url
        self._lock = threading.Lock()
    
    def is_seen(self, url: str) -> bool:
        """Check if URL has been seen."""
        fingerprint = self.normalizer.get_url_fingerprint(url)
        with self._lock:
            return fingerprint in self._seen_urls
    
    def is_duplicate_content(self, content_hash: str) -> Tuple[bool, Optional[str]]:
        """Check if content hash is duplicate."""
        if not self.config.content_hash_enabled:
            return False, None
        
        with self._lock:
            if content_hash in self._content_hashes:
                return True, self._content_hashes[content_hash]
            return False, None
    
    def mark_seen(
        self,
        url: str,
        content_hash: Optional[str] = None,
        status: str = "pending",
    ) -> bool:
        """Mark URL as seen. Returns False if already seen."""
        fingerprint = self.normalizer.get_url_fingerprint(url)
        
        with self._lock:
            if fingerprint in self._seen_urls:
                # Update status if already seen
                self._seen_urls[fingerprint].status = status
                if content_hash:
                    self._seen_urls[fingerprint].content_hash = content_hash
                return False
            
            self._seen_urls[fingerprint] = SeenURL(
                url=url,
                fingerprint=fingerprint,
                content_hash=content_hash,
                status=status,
            )
            
            if content_hash:
                self._content_hashes[content_hash] = url
            
            return True
    
    def get_canonical(self, url: str) -> Optional[str]:
        """Get the canonical (first seen) URL for a fingerprint."""
        fingerprint = self.normalizer.get_url_fingerprint(url)
        with self._lock:
            if fingerprint in self._seen_urls:
                return self._seen_urls[fingerprint].url
        return None
    
    def filter_new(self, urls: List[str]) -> List[str]:
        """Filter list to only new URLs."""
        with self._lock:
            return [
                url for url in urls
                if self.normalizer.get_url_fingerprint(url) not in self._seen_urls
            ]
    
    def get_stats(self) -> Dict[str, int]:
        """Get deduplication statistics."""
        with self._lock:
            total = len(self._seen_urls)
            by_status = {}
            for seen in self._seen_urls.values():
                by_status[seen.status] = by_status.get(seen.status, 0) + 1
            
            return {
                "total_urls": total,
                "unique_content": len(self._content_hashes),
                "duplicate_content": total - len(self._content_hashes),
                **by_status,
            }
    
    def clear(self) -> None:
        """Clear all seen URLs."""
        with self._lock:
            self._seen_urls.clear()
            self._content_hashes.clear()


def compute_content_hash(content: str, min_length: int = 100) -> Optional[str]:
    """Compute hash of content for deduplication."""
    if len(content) < min_length:
        return None
    
    # Normalize content
    normalized = re.sub(r'\s+', ' ', content.strip().lower())
    
    return hashlib.sha256(normalized.encode()).hexdigest()


def normalize_url(url: str) -> str:
    """Normalize URL for comparison."""
    return URLNormalizer().normalize(url)


__all__ = [
    "DedupeConfig",
    "URLNormalizer",
    "SeenURL",
    "URLDeduplicator",
    "compute_content_hash",
    "normalize_url",
]
