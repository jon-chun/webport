"""
WebPort Security Module

URL validation, SSRF protection, and security utilities.

Addresses Critique #6: Missing URL Sanitization/SSRF Protection
Addresses Critique #37: No Data Anonymization
"""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple
from urllib.parse import urlparse, urljoin

logger = logging.getLogger(__name__)


@dataclass
class SecurityConfig:
    """Security configuration."""
    
    ssrf_protection: bool = True
    blocked_ip_ranges: List[str] = field(default_factory=lambda: [
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "0.0.0.0/8",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
    ])
    allowed_schemes: List[str] = field(default_factory=lambda: ["http", "https"])
    max_url_length: int = 2048
    max_redirects: int = 10
    
    # Domain restrictions
    allowed_domains: Optional[List[str]] = None
    blocked_domains: List[str] = field(default_factory=list)
    
    # PII patterns for anonymization
    pii_patterns: List[Tuple[str, str]] = field(default_factory=lambda: [
        (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL]"),
        (r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "[PHONE]"),
        (r"\b\d{3}-\d{2}-\d{4}\b", "[SSN]"),
        (r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", "[CARD]"),
    ])


class URLValidator:
    """
    URL validation with SSRF protection.
    
    Prevents access to:
    - Internal IP ranges (10.x, 172.16-31.x, 192.168.x, 127.x)
    - Cloud metadata endpoints (169.254.169.254)
    - localhost and local hostnames
    """
    
    def __init__(self, config: Optional[SecurityConfig] = None):
        self.config = config or SecurityConfig()
        self._blocked_networks = [
            ipaddress.ip_network(cidr) for cidr in self.config.blocked_ip_ranges
        ]
    
    def validate_url(self, url: str, base_url: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
        """
        Validate URL for security.
        
        Args:
            url: URL to validate
            base_url: Base URL for resolving relative URLs
            
        Returns:
            Tuple of (is_valid, normalized_url, error_message)
        """
        # Normalize URL
        if base_url and not url.startswith(("http://", "https://")):
            url = urljoin(base_url, url)
        
        # Check length
        if len(url) > self.config.max_url_length:
            return False, url, f"URL exceeds maximum length of {self.config.max_url_length}"
        
        try:
            parsed = urlparse(url)
        except Exception as e:
            return False, url, f"Invalid URL format: {e}"
        
        # Check scheme
        if parsed.scheme not in self.config.allowed_schemes:
            return False, url, f"Scheme '{parsed.scheme}' not allowed"
        
        # Check hostname exists
        if not parsed.netloc:
            return False, url, "Missing hostname"
        
        hostname = parsed.hostname
        if not hostname:
            return False, url, "Invalid hostname"
        
        # Check blocked domains
        if self.config.blocked_domains:
            for blocked in self.config.blocked_domains:
                if hostname == blocked or hostname.endswith(f".{blocked}"):
                    return False, url, f"Domain '{hostname}' is blocked"
        
        # Check allowed domains (if specified)
        if self.config.allowed_domains:
            allowed = False
            for domain in self.config.allowed_domains:
                if hostname == domain or hostname.endswith(f".{domain}"):
                    allowed = True
                    break
            if not allowed:
                return False, url, f"Domain '{hostname}' not in allowed list"
        
        # SSRF protection - check IP address
        if self.config.ssrf_protection:
            is_safe, error = self._check_ssrf(hostname)
            if not is_safe:
                return False, url, error
        
        return True, url, None
    
    def _check_ssrf(self, hostname: str) -> Tuple[bool, Optional[str]]:
        """Check hostname for SSRF vulnerability."""
        
        # Check for IP address in hostname
        try:
            ip = ipaddress.ip_address(hostname)
            if self._is_blocked_ip(ip):
                return False, f"IP address {ip} is in blocked range"
            return True, None
        except ValueError:
            pass  # Not an IP address, continue with DNS resolution
        
        # Check for suspicious hostnames
        suspicious_hostnames = [
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
            "metadata.google.internal",
            "169.254.169.254",
        ]
        
        if hostname.lower() in suspicious_hostnames:
            return False, f"Hostname '{hostname}' is blocked for security"
        
        if hostname.lower().endswith(".local"):
            return False, f"Local hostname '{hostname}' is blocked"
        
        # Resolve DNS and check IP
        try:
            ips = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            for family, _, _, _, addr in ips:
                ip_str = addr[0]
                try:
                    ip = ipaddress.ip_address(ip_str)
                    if self._is_blocked_ip(ip):
                        return False, f"Hostname '{hostname}' resolves to blocked IP {ip}"
                except ValueError:
                    continue
        except socket.gaierror:
            # DNS resolution failed - might be temporary, allow but log
            logger.warning(f"DNS resolution failed for {hostname}")
        
        return True, None
    
    def _is_blocked_ip(self, ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
        """Check if IP is in blocked ranges."""
        for network in self._blocked_networks:
            try:
                if ip in network:
                    return True
            except TypeError:
                continue  # IP version mismatch
        return False
    
    def sanitize_url(self, url: str) -> str:
        """Remove potentially dangerous parts from URL."""
        parsed = urlparse(url)
        
        # Remove credentials from URL
        if parsed.username or parsed.password:
            netloc = parsed.hostname
            if parsed.port:
                netloc += f":{parsed.port}"
            url = parsed._replace(netloc=netloc).geturl()
        
        return url


class ContentAnonymizer:
    """
    Content anonymizer for PII removal.
    
    Addresses Critique #37: No Data Anonymization
    """
    
    def __init__(self, config: Optional[SecurityConfig] = None):
        self.config = config or SecurityConfig()
        self._patterns = [
            (re.compile(pattern, re.IGNORECASE), replacement)
            for pattern, replacement in self.config.pii_patterns
        ]
    
    def anonymize(self, text: str) -> str:
        """Remove PII from text."""
        result = text
        for pattern, replacement in self._patterns:
            result = pattern.sub(replacement, result)
        return result
    
    def detect_pii(self, text: str) -> List[Tuple[str, str, int, int]]:
        """Detect PII in text without removing."""
        findings = []
        for pattern, pii_type in self._patterns:
            for match in pattern.finditer(text):
                findings.append((
                    pii_type,
                    match.group(),
                    match.start(),
                    match.end()
                ))
        return findings


class RequestSanitizer:
    """Sanitize HTTP requests for security."""
    
    # Headers that should not be forwarded
    BLOCKED_HEADERS = {
        "authorization",
        "cookie",
        "set-cookie",
        "x-forwarded-for",
        "x-real-ip",
        "x-forwarded-host",
        "x-forwarded-proto",
    }
    
    @classmethod
    def sanitize_headers(cls, headers: dict) -> dict:
        """Remove sensitive headers."""
        return {
            k: v for k, v in headers.items()
            if k.lower() not in cls.BLOCKED_HEADERS
        }
    
    @classmethod
    def safe_user_agent(cls, custom_ua: Optional[str] = None) -> str:
        """Generate safe user agent string."""
        if custom_ua:
            # Remove potentially identifying info
            custom_ua = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '[IP]', custom_ua)
            return custom_ua
        return "WebPort/1.0 (+https://webport.dev/bot)"


def is_safe_url(url: str, base_url: Optional[str] = None) -> bool:
    """Quick check if URL is safe to request."""
    validator = URLValidator()
    is_valid, _, _ = validator.validate_url(url, base_url)
    return is_valid


def validate_url(url: str, base_url: Optional[str] = None) -> str:
    """Validate and return URL, raising on error."""
    from webport.core.exceptions import URLValidationError, SSRFProtectionError
    
    validator = URLValidator()
    is_valid, normalized, error = validator.validate_url(url, base_url)
    
    if not is_valid:
        if "blocked" in error.lower() or "ssrf" in error.lower():
            raise SSRFProtectionError(url)
        raise URLValidationError(url, error)
    
    return normalized


def anonymize_content(text: str) -> str:
    """Anonymize PII in text content."""
    return ContentAnonymizer().anonymize(text)


__all__ = [
    "SecurityConfig",
    "URLValidator", 
    "ContentAnonymizer",
    "RequestSanitizer",
    "is_safe_url",
    "validate_url",
    "anonymize_content",
]
