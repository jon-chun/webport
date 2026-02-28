"""
WebPort Health Check System

Pre-crawl health checks for target sites.

Addresses Critique #20: No Health Check Before Crawl
"""

from __future__ import annotations

import asyncio
import logging
import socket
import ssl
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    HEALTHY = auto()
    DEGRADED = auto()
    UNHEALTHY = auto()
    UNKNOWN = auto()


@dataclass
class HealthCheckResult:
    """Result of a single health check."""
    name: str
    status: HealthStatus
    message: str
    duration_ms: float
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SiteHealthReport:
    """Complete health report for a site."""
    url: str
    overall_status: HealthStatus = HealthStatus.UNKNOWN
    checks: List[HealthCheckResult] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    duration_ms: float = 0.0
    
    @property
    def is_healthy(self) -> bool:
        return self.overall_status == HealthStatus.HEALTHY
    
    @property
    def can_crawl(self) -> bool:
        return self.overall_status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)
    
    def add_check(self, result: HealthCheckResult) -> None:
        self.checks.append(result)
    
    def compute_overall_status(self) -> None:
        if not self.checks:
            self.overall_status = HealthStatus.UNKNOWN
            return
        
        statuses = [c.status for c in self.checks]
        
        if all(s == HealthStatus.HEALTHY for s in statuses):
            self.overall_status = HealthStatus.HEALTHY
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            self.overall_status = HealthStatus.UNHEALTHY
        elif any(s == HealthStatus.DEGRADED for s in statuses):
            self.overall_status = HealthStatus.DEGRADED
        else:
            self.overall_status = HealthStatus.UNKNOWN
    
    def report(self) -> str:
        lines = [
            f"\n{'='*60}",
            f"HEALTH CHECK REPORT: {self.url}",
            f"{'='*60}",
            f"Overall Status: {self.overall_status.name}",
            f"Duration: {self.duration_ms:.0f}ms",
            "",
            "Checks:",
        ]
        
        for check in self.checks:
            icon = "✓" if check.status == HealthStatus.HEALTHY else "✗" if check.status == HealthStatus.UNHEALTHY else "!"
            lines.append(f"  {icon} {check.name}: {check.status.name}")
            lines.append(f"    {check.message}")
        
        if self.recommendations:
            lines.extend(["", "Recommendations:"])
            for rec in self.recommendations:
                lines.append(f"  • {rec}")
        
        return "\n".join(lines)


class HealthChecker:
    """
    Perform health checks on target sites before crawling.
    
    Checks:
    - DNS resolution
    - SSL certificate validity
    - HTTP connectivity
    - Response time
    - robots.txt accessibility
    - Common error pages
    """
    
    def __init__(
        self,
        user_agent: str = "WebPort/1.0",
        timeout: float = 10.0,
    ):
        self.user_agent = user_agent
        self.timeout = timeout
    
    async def check(self, url: str) -> SiteHealthReport:
        start = time.perf_counter()
        report = SiteHealthReport(url=url)
        
        parsed = urlparse(url)
        hostname = parsed.netloc
        
        report.add_check(await self._check_dns(hostname))
        
        if parsed.scheme == "https":
            report.add_check(await self._check_ssl(hostname))
        
        report.add_check(await self._check_http(url))
        
        report.add_check(await self._check_robots(url))
        
        report.add_check(await self._check_wordpress_api(url))
        
        report.compute_overall_status()
        report.duration_ms = (time.perf_counter() - start) * 1000
        
        self._generate_recommendations(report)
        
        return report
    
    async def _check_dns(self, hostname: str) -> HealthCheckResult:
        start = time.perf_counter()
        
        try:
            host = hostname.split(":")[0]
            
            loop = asyncio.get_event_loop()
            addresses = await loop.run_in_executor(None, socket.gethostbyname_ex, host)
            
            duration = (time.perf_counter() - start) * 1000
            
            return HealthCheckResult(
                name="DNS Resolution",
                status=HealthStatus.HEALTHY,
                message=f"Resolved to {len(addresses[2])} IP(s)",
                duration_ms=duration,
                details={"addresses": addresses[2]},
            )
            
        except socket.gaierror as e:
            duration = (time.perf_counter() - start) * 1000
            return HealthCheckResult(
                name="DNS Resolution",
                status=HealthStatus.UNHEALTHY,
                message=f"DNS resolution failed: {e}",
                duration_ms=duration,
            )
    
    async def _check_ssl(self, hostname: str) -> HealthCheckResult:
        start = time.perf_counter()
        
        try:
            host = hostname.split(":")[0]
            port = int(hostname.split(":")[1]) if ":" in hostname else 443
            
            context = ssl.create_default_context()
            
            loop = asyncio.get_event_loop()
            
            def check_cert():
                with socket.create_connection((host, port), timeout=self.timeout) as sock:
                    with context.wrap_socket(sock, server_hostname=host) as ssock:
                        cert = ssock.getpeercert()
                        return cert
            
            cert = await loop.run_in_executor(None, check_cert)
            duration = (time.perf_counter() - start) * 1000
            
            not_after = cert.get("notAfter", "")
            
            return HealthCheckResult(
                name="SSL Certificate",
                status=HealthStatus.HEALTHY,
                message=f"Valid certificate, expires: {not_after}",
                duration_ms=duration,
                details={"subject": cert.get("subject"), "expires": not_after},
            )
            
        except ssl.SSLError as e:
            duration = (time.perf_counter() - start) * 1000
            return HealthCheckResult(
                name="SSL Certificate",
                status=HealthStatus.UNHEALTHY,
                message=f"SSL error: {e}",
                duration_ms=duration,
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return HealthCheckResult(
                name="SSL Certificate",
                status=HealthStatus.DEGRADED,
                message=f"Could not verify: {e}",
                duration_ms=duration,
            )
    
    async def _check_http(self, url: str) -> HealthCheckResult:
        start = time.perf_counter()
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    headers={"User-Agent": self.user_agent},
                    follow_redirects=True,
                )
                
                duration = (time.perf_counter() - start) * 1000
                
                if response.status_code == 200:
                    status = HealthStatus.HEALTHY
                    message = f"HTTP 200 OK ({duration:.0f}ms)"
                elif response.status_code < 400:
                    status = HealthStatus.HEALTHY
                    message = f"HTTP {response.status_code} ({duration:.0f}ms)"
                elif response.status_code < 500:
                    status = HealthStatus.DEGRADED
                    message = f"HTTP {response.status_code} - client error"
                else:
                    status = HealthStatus.UNHEALTHY
                    message = f"HTTP {response.status_code} - server error"
                
                return HealthCheckResult(
                    name="HTTP Connectivity",
                    status=status,
                    message=message,
                    duration_ms=duration,
                    details={
                        "status_code": response.status_code,
                        "final_url": str(response.url),
                        "content_type": response.headers.get("content-type"),
                    },
                )
                
        except httpx.TimeoutException:
            duration = (time.perf_counter() - start) * 1000
            return HealthCheckResult(
                name="HTTP Connectivity",
                status=HealthStatus.UNHEALTHY,
                message=f"Request timed out after {self.timeout}s",
                duration_ms=duration,
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return HealthCheckResult(
                name="HTTP Connectivity",
                status=HealthStatus.UNHEALTHY,
                message=f"Connection failed: {e}",
                duration_ms=duration,
            )
    
    async def _check_robots(self, url: str) -> HealthCheckResult:
        start = time.perf_counter()
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    robots_url,
                    headers={"User-Agent": self.user_agent},
                )
                
                duration = (time.perf_counter() - start) * 1000
                
                if response.status_code == 200:
                    content = response.text
                    has_sitemap = "sitemap:" in content.lower()
                    
                    return HealthCheckResult(
                        name="robots.txt",
                        status=HealthStatus.HEALTHY,
                        message=f"Found ({len(content)} bytes)" + 
                               (", contains sitemap" if has_sitemap else ""),
                        duration_ms=duration,
                        details={"has_sitemap": has_sitemap, "size": len(content)},
                    )
                elif response.status_code == 404:
                    return HealthCheckResult(
                        name="robots.txt",
                        status=HealthStatus.HEALTHY,
                        message="Not found (all URLs allowed)",
                        duration_ms=duration,
                    )
                else:
                    return HealthCheckResult(
                        name="robots.txt",
                        status=HealthStatus.DEGRADED,
                        message=f"HTTP {response.status_code}",
                        duration_ms=duration,
                    )
                    
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return HealthCheckResult(
                name="robots.txt",
                status=HealthStatus.DEGRADED,
                message=f"Could not fetch: {e}",
                duration_ms=duration,
            )
    
    async def _check_wordpress_api(self, url: str) -> HealthCheckResult:
        start = time.perf_counter()
        parsed = urlparse(url)
        api_url = f"{parsed.scheme}://{parsed.netloc}/wp-json/wp/v2"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    api_url,
                    headers={"User-Agent": self.user_agent},
                )
                
                duration = (time.perf_counter() - start) * 1000
                
                if response.status_code == 200:
                    return HealthCheckResult(
                        name="WordPress API",
                        status=HealthStatus.HEALTHY,
                        message="WordPress REST API available",
                        duration_ms=duration,
                        details={"is_wordpress": True},
                    )
                elif response.status_code == 404:
                    return HealthCheckResult(
                        name="WordPress API",
                        status=HealthStatus.HEALTHY,
                        message="Not a WordPress site (or API disabled)",
                        duration_ms=duration,
                        details={"is_wordpress": False},
                    )
                else:
                    return HealthCheckResult(
                        name="WordPress API",
                        status=HealthStatus.DEGRADED,
                        message=f"API returned {response.status_code}",
                        duration_ms=duration,
                    )
                    
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return HealthCheckResult(
                name="WordPress API",
                status=HealthStatus.HEALTHY,
                message="Not a WordPress site",
                duration_ms=duration,
                details={"is_wordpress": False},
            )
    
    def _generate_recommendations(self, report: SiteHealthReport) -> None:
        for check in report.checks:
            if check.status == HealthStatus.UNHEALTHY:
                if check.name == "DNS Resolution":
                    report.recommendations.append(
                        "Verify the domain name is correct and DNS is properly configured"
                    )
                elif check.name == "SSL Certificate":
                    report.recommendations.append(
                        "Consider using HTTP instead or verify SSL certificate is valid"
                    )
                elif check.name == "HTTP Connectivity":
                    report.recommendations.append(
                        "Check if the site is online and accessible from your network"
                    )
            
            elif check.status == HealthStatus.DEGRADED:
                if check.name == "HTTP Connectivity":
                    report.recommendations.append(
                        "Site returned non-200 status - crawl may be incomplete"
                    )


async def check_site_health(url: str) -> SiteHealthReport:
    """Quick health check for a URL."""
    checker = HealthChecker()
    return await checker.check(url)


__all__ = [
    "HealthStatus",
    "HealthCheckResult",
    "SiteHealthReport",
    "HealthChecker",
    "check_site_health",
]
