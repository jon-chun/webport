"""
WebPort Notifications

Webhook and email notifications for crawl events.

Addresses Critique #24: No Webhook/Notification Support
"""

from __future__ import annotations

import asyncio
import json
import logging
import smtplib
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class NotificationEvent:
    """Notification event data."""
    
    event_type: str  # crawl_started, crawl_completed, crawl_failed, warning
    crawl_id: str
    target_url: str
    timestamp: str = ""
    message: str = ""
    details: Dict[str, Any] = None
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()
        if self.details is None:
            self.details = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class NotificationChannel(ABC):
    """Base notification channel."""
    
    @abstractmethod
    async def send(self, event: NotificationEvent) -> bool:
        """Send notification."""
        pass
    
    @abstractmethod
    def is_configured(self) -> bool:
        """Check if channel is configured."""
        pass


class SlackNotifier(NotificationChannel):
    """Slack webhook notifications."""
    
    def __init__(self, webhook_url: str, channel: Optional[str] = None):
        self.webhook_url = webhook_url
        self.channel = channel
    
    def is_configured(self) -> bool:
        return bool(self.webhook_url)
    
    async def send(self, event: NotificationEvent) -> bool:
        if not self.is_configured():
            return False
        
        color_map = {
            "crawl_started": "#36a64f",
            "crawl_completed": "#2eb886",
            "crawl_failed": "#dc3545",
            "warning": "#ffc107",
        }
        
        payload = {
            "attachments": [{
                "color": color_map.get(event.event_type, "#6c757d"),
                "title": f"WebPort: {event.event_type.replace('_', ' ').title()}",
                "text": event.message,
                "fields": [
                    {"title": "Crawl ID", "value": event.crawl_id, "short": True},
                    {"title": "Target", "value": event.target_url, "short": True},
                ],
                "footer": "WebPort",
                "ts": int(datetime.fromisoformat(event.timestamp).timestamp()),
            }]
        }
        
        if self.channel:
            payload["channel"] = self.channel
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.webhook_url, json=payload, timeout=10)
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Slack notification failed: {e}")
            return False


class DiscordNotifier(NotificationChannel):
    """Discord webhook notifications."""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    def is_configured(self) -> bool:
        return bool(self.webhook_url)
    
    async def send(self, event: NotificationEvent) -> bool:
        if not self.is_configured():
            return False
        
        color_map = {
            "crawl_started": 0x36a64f,
            "crawl_completed": 0x2eb886,
            "crawl_failed": 0xdc3545,
            "warning": 0xffc107,
        }
        
        payload = {
            "embeds": [{
                "title": f"WebPort: {event.event_type.replace('_', ' ').title()}",
                "description": event.message,
                "color": color_map.get(event.event_type, 0x6c757d),
                "fields": [
                    {"name": "Crawl ID", "value": event.crawl_id, "inline": True},
                    {"name": "Target", "value": event.target_url, "inline": True},
                ],
                "footer": {"text": "WebPort"},
                "timestamp": event.timestamp,
            }]
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.webhook_url, json=payload, timeout=10)
                return response.status_code in (200, 204)
        except Exception as e:
            logger.error(f"Discord notification failed: {e}")
            return False


class EmailNotifier(NotificationChannel):
    """Email notifications via SMTP."""
    
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int = 587,
        username: Optional[str] = None,
        password: Optional[str] = None,
        from_addr: Optional[str] = None,
        to_addrs: Optional[List[str]] = None,
        use_tls: bool = True,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_addr = from_addr or username
        self.to_addrs = to_addrs or []
        self.use_tls = use_tls
    
    def is_configured(self) -> bool:
        return bool(self.smtp_host and self.from_addr and self.to_addrs)
    
    async def send(self, event: NotificationEvent) -> bool:
        if not self.is_configured():
            return False
        
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._send_sync, event)
    
    def _send_sync(self, event: NotificationEvent) -> bool:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[WebPort] {event.event_type.replace('_', ' ').title()}: {event.crawl_id}"
            msg["From"] = self.from_addr
            msg["To"] = ", ".join(self.to_addrs)
            
            text = f"""
WebPort Notification

Event: {event.event_type}
Crawl ID: {event.crawl_id}
Target: {event.target_url}
Time: {event.timestamp}

{event.message}

Details:
{json.dumps(event.details, indent=2)}
"""
            
            html = f"""
<html>
<body>
<h2>WebPort Notification</h2>
<table>
<tr><td><strong>Event:</strong></td><td>{event.event_type}</td></tr>
<tr><td><strong>Crawl ID:</strong></td><td>{event.crawl_id}</td></tr>
<tr><td><strong>Target:</strong></td><td>{event.target_url}</td></tr>
<tr><td><strong>Time:</strong></td><td>{event.timestamp}</td></tr>
</table>
<p>{event.message}</p>
<pre>{json.dumps(event.details, indent=2)}</pre>
</body>
</html>
"""
            
            msg.attach(MIMEText(text, "plain"))
            msg.attach(MIMEText(html, "html"))
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                if self.username and self.password:
                    server.login(self.username, self.password)
                server.sendmail(self.from_addr, self.to_addrs, msg.as_string())
            
            return True
        except Exception as e:
            logger.error(f"Email notification failed: {e}")
            return False


class NotificationManager:
    """Central notification management."""
    
    def __init__(self):
        self.channels: List[NotificationChannel] = []
        self.enabled_events: set = {"crawl_completed", "crawl_failed"}
    
    def add_channel(self, channel: NotificationChannel) -> None:
        if channel.is_configured():
            self.channels.append(channel)
    
    def enable_event(self, event_type: str) -> None:
        self.enabled_events.add(event_type)
    
    def disable_event(self, event_type: str) -> None:
        self.enabled_events.discard(event_type)
    
    async def notify(self, event: NotificationEvent) -> int:
        if event.event_type not in self.enabled_events:
            return 0
        
        results = await asyncio.gather(
            *[channel.send(event) for channel in self.channels],
            return_exceptions=True
        )
        
        return sum(1 for r in results if r is True)
    
    async def notify_crawl_started(self, crawl_id: str, target_url: str) -> int:
        return await self.notify(NotificationEvent(
            event_type="crawl_started",
            crawl_id=crawl_id,
            target_url=target_url,
            message=f"Started crawling {target_url}",
        ))
    
    async def notify_crawl_completed(
        self, crawl_id: str, target_url: str, 
        pages_crawled: int, duration_seconds: float
    ) -> int:
        return await self.notify(NotificationEvent(
            event_type="crawl_completed",
            crawl_id=crawl_id,
            target_url=target_url,
            message=f"Completed crawling {target_url}",
            details={
                "pages_crawled": pages_crawled,
                "duration_seconds": round(duration_seconds, 1),
            },
        ))
    
    async def notify_crawl_failed(
        self, crawl_id: str, target_url: str, error: str
    ) -> int:
        return await self.notify(NotificationEvent(
            event_type="crawl_failed",
            crawl_id=crawl_id,
            target_url=target_url,
            message=f"Crawl failed: {error}",
            details={"error": error},
        ))


_notification_manager: Optional[NotificationManager] = None


def get_notification_manager() -> NotificationManager:
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager


__all__ = [
    "NotificationEvent",
    "NotificationChannel",
    "SlackNotifier",
    "DiscordNotifier",
    "EmailNotifier",
    "NotificationManager",
    "get_notification_manager",
]
