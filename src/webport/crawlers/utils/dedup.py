"""
WebPort Request Deduplication

URL normalization and deduplication.

Addresses Critique #15: Missing Request Deduplication
"""

from __future__ import annotations

import hashlib
import logging
import re
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

logger = logging.getLogger(__name__)


@dataclass
class DeduplicationConfig:
    """Deduplication configuration."""
    
    normalize_urls: bool = True
    remove_fragments: bool = True
    remove_tracking_params: bool = True
    lowercase_hostname: bool = True
    sort_query_params: bool = True
    remove_trailing_slash: bool = True
    remove_default_port: bool = True
    
    tracking_params: Set[str] = field(default_factory=lambda: {
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "fbclid", "gclid", "msclkid", "mc_cid", "mc_eid",
        "ref", "source", "affiliate", "partner",
        "_ga", "_gid", "_gl", "ck_subscriber_id",
        "hsCtaTracking", "hsa_",
        "trk", "trkCampaign", "li_fat_id",
    })


class URLNormalizer:
    """
    Normalize URLs for consistent comparison.
    
    Example:
        >>> normalizer = URLNormalizer()
        >>> normalizer.normalize("HTTP://Example.COM/page/?b=2&a=1#section")
        'http://example.com/page?a=1&b=2'
    """
    
    def __init__(self, config: Optional[DeduplicationConfig] = None):
        self.config = config or DeduplicationConfig()
    
    def normalize(self, url: str) -> str:
        if not url:
            return ""
        
        try:
            parsed = urlparse(url.strip())
        except Exception:
            return url
        
        scheme = parsed.scheme.lower()
        
        netloc = parsed.netloc
        if self.config.lowercase_hostname:
            netloc = netloc.lower()
        
        if self.config.remove_default_port:
            if netloc.endswith(":80") and scheme == "http":
                netloc = netloc[:-3]
            elif netloc.endswith(":443") and scheme == "https":
                netloc = netloc[:-4]
        
        path = parsed.path
        if self.config.remove_trailing_slash and path != "/":
            path = path.rstrip("/")
        
        path = re.sub(r"/+", "/", path)
        
        query = parsed.query
        if query and self.config.normalize_urls:
            params = parse_qs(query, keep_blank_values=True)
            
            if self.config.remove_tracking_params:
                params = {
                    k: v for k, v in params.items()
                    if k.lower() not in self.config.tracking_params
                    and not any(k.lower().startswith(p) for p in ["utm_", "hsa_"])
                }
            
            if self.config.sort_query_params and params:
                query = urlencode(sorted(params.items()), doseq=True)
            elif params:
                query = urlencode(params, doseq=True)
            else:
                query = ""
        
        fragment = "" if self.config.remove_fragments else parsed.fragment
        
        normalized = urlunparse((scheme, netloc, path, "", query, fragment))
        
        return normalized
    
    def get_url_hash(self, url: str) -> str:
        normalized = self.normalize(url)
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]


class URLDeduplicator:
    """
    Track seen URLs and filter duplicates.
    
    Example:
        >>> dedup = URLDeduplicator()
        >>> dedup.should_process("https://example.com/page")
        True
        >>> dedup.mark_seen("https://example.com/page")
        >>> dedup.should_process("https://example.com/page")
        False
    """
    
    def __init__(self, config: Optional[DeduplicationConfig] = None):
        self.normalizer = URLNormalizer(config)
        self._seen_hashes: Set[str] = set()
        self._seen_urls: Dict[str, str] = {}
        self._lock = threading.Lock()
    
    def should_process(self, url: str) -> bool:
        url_hash = self.normalizer.get_url_hash(url)
        with self._lock:
            return url_hash not in self._seen_hashes
    
    def mark_seen(self, url: str) -> None:
        normalized = self.normalizer.normalize(url)
        url_hash = self.normalizer.get_url_hash(url)
        
        with self._lock:
            self._seen_hashes.add(url_hash)
            self._seen_urls[url_hash] = normalized
    
    def get_canonical(self, url: str) -> Optional[str]:
        url_hash = self.normalizer.get_url_hash(url)
        with self._lock:
            return self._seen_urls.get(url_hash)
    
    def is_duplicate(self, url: str) -> Tuple[bool, Optional[str]]:
        url_hash = self.normalizer.get_url_hash(url)
        with self._lock:
            if url_hash in self._seen_hashes:
                return True, self._seen_urls.get(url_hash)
            return False, None
    
    def add_and_check(self, url: str) -> Tuple[bool, str]:
        normalized = self.normalizer.normalize(url)
        url_hash = self.normalizer.get_url_hash(url)
        
        with self._lock:
            if url_hash in self._seen_hashes:
                return False, normalized
            
            self._seen_hashes.add(url_hash)
            self._seen_urls[url_hash] = normalized
            return True, normalized
    
    @property
    def seen_count(self) -> int:
        return len(self._seen_hashes)
    
    def clear(self) -> None:
        with self._lock:
            self._seen_hashes.clear()
            self._seen_urls.clear()


class ContentDeduplicator:
    """
    Deduplicate content by hash.
    
    Useful for detecting duplicate pages with different URLs.
    """
    
    def __init__(self, similarity_threshold: float = 0.95):
        self.similarity_threshold = similarity_threshold
        self._content_hashes: Dict[str, str] = {}
        self._lock = threading.Lock()
    
    def get_content_hash(self, content: str) -> str:
        normalized = re.sub(r"\s+", " ", content.lower().strip())
        return hashlib.sha256(normalized.encode()).hexdigest()
    
    def is_duplicate_content(self, url: str, content: str) -> Tuple[bool, Optional[str]]:
        content_hash = self.get_content_hash(content)
        
        with self._lock:
            if content_hash in self._content_hashes:
                return True, self._content_hashes[content_hash]
            
            self._content_hashes[content_hash] = url
            return False, None
    
    def get_duplicate_url(self, content: str) -> Optional[str]:
        content_hash = self.get_content_hash(content)
        with self._lock:
            return self._content_hashes.get(content_hash)


__all__ = [
    "DeduplicationConfig",
    "URLNormalizer",
    "URLDeduplicator",
    "ContentDeduplicator",
]
