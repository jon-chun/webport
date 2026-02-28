"""
WebPort Notification System

Webhook and notification support for Slack, Discord, and email.

Addresses Critique #24: Missing Webhook/Notification Support
"""

from __future__ import annotations

import asyncio
import json
import logging
import smtplib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum, auto
from typing import Any, Dict, List, Optional

import httpx

from webport.core.config import NotificationConfig

logger = logging.getLogger(__name__)


class NotificationLevel(Enum):
    INFO = auto()
    SUCCESS = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL = auto()


@dataclass
class Notification:
    """A notification to send."""
    title: str
    message: str
    level: NotificationLevel = NotificationLevel.INFO
    timestamp: datetime = None
    details: Dict[str, Any] = None
    url: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.details is None:
            self.details = {}


class NotificationProvider(ABC):
    """Base class for notification providers."""
    
    @abstractmethod
    async def send(self, notification: Notification) -> bool:
        """Send a notification. Returns True if successful."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass


class SlackNotifier(NotificationProvider):
    """Slack webhook notifier."""
    
    LEVEL_COLORS = {
        NotificationLevel.INFO: "#3498db",
        NotificationLevel.SUCCESS: "#2ecc71",
        NotificationLevel.WARNING: "#f39c12",
        NotificationLevel.ERROR: "#e74c3c",
        NotificationLevel.CRITICAL: "#9b59b6",
    }
    
    def __init__(self, webhook_url: str, channel: Optional[str] = None):
        self.webhook_url = webhook_url
        self.channel = channel
    
    @property
    def name(self) -> str:
        return "Slack"
    
    async def send(self, notification: Notification) -> bool:
        payload = {
            "attachments": [{
                "color": self.LEVEL_COLORS.get(notification.level, "#3498db"),
                "title": notification.title,
                "text": notification.message,
                "footer": "WebPort",
                "ts": int(notification.timestamp.timestamp()),
            }]
        }
        
        if self.channel:
            payload["channel"] = self.channel
        
        if notification.details:
            fields = [
                {"title": k, "value": str(v), "short": True}
                for k, v in notification.details.items()
            ]
            payload["attachments"][0]["fields"] = fields
        
        if notification.url:
            payload["attachments"][0]["title_link"] = notification.url
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10.0,
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False


class DiscordNotifier(NotificationProvider):
    """Discord webhook notifier."""
    
    LEVEL_COLORS = {
        NotificationLevel.INFO: 3447003,
        NotificationLevel.SUCCESS: 3066993,
        NotificationLevel.WARNING: 15105570,
        NotificationLevel.ERROR: 15158332,
        NotificationLevel.CRITICAL: 10181046,
    }
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    @property
    def name(self) -> str:
        return "Discord"
    
    async def send(self, notification: Notification) -> bool:
        embed = {
            "title": notification.title,
            "description": notification.message,
            "color": self.LEVEL_COLORS.get(notification.level, 3447003),
            "timestamp": notification.timestamp.isoformat(),
            "footer": {"text": "WebPort"},
        }
        
        if notification.details:
            embed["fields"] = [
                {"name": k, "value": str(v), "inline": True}
                for k, v in notification.details.items()
            ]
        
        if notification.url:
            embed["url"] = notification.url
        
        payload = {"embeds": [embed]}
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10.0,
                )
                return response.status_code in (200, 204)
        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")
            return False


class EmailNotifier(NotificationProvider):
    """Email notifier via SMTP."""
    
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        from_address: str,
        to_addresses: List[str],
        use_tls: bool = True,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_address = from_address
        self.to_addresses = to_addresses
        self.use_tls = use_tls
    
    @property
    def name(self) -> str:
        return "Email"
    
    async def send(self, notification: Notification) -> bool:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[WebPort] {notification.title}"
            msg["From"] = self.from_address
            msg["To"] = ", ".join(self.to_addresses)
            
            # Plain text version
            text_content = f"{notification.title}\n\n{notification.message}"
            if notification.details:
                text_content += "\n\nDetails:\n"
                for k, v in notification.details.items():
                    text_content += f"  {k}: {v}\n"
            
            # HTML version
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2 style="color: #333;">{notification.title}</h2>
                <p>{notification.message}</p>
                {"<h3>Details</h3><ul>" + "".join(f"<li><strong>{k}:</strong> {v}</li>" for k, v in notification.details.items()) + "</ul>" if notification.details else ""}
                <hr>
                <p style="color: #888; font-size: 12px;">WebPort Notification</p>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(text_content, "plain"))
            msg.attach(MIMEText(html_content, "html"))
            
            # Send email
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._send_email, msg)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return False
    
    def _send_email(self, msg: MIMEMultipart) -> None:
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            if self.use_tls:
                server.starttls()
            server.login(self.username, self.password)
            server.send_message(msg)


class NotificationManager:
    """
    Manages multiple notification providers.
    
    Example:
        >>> manager = NotificationManager()
        >>> manager.add_provider(SlackNotifier(webhook_url="..."))
        >>> 
        >>> await manager.notify(
        ...     title="Crawl Complete",
        ...     message="Successfully crawled 100 pages",
        ...     level=NotificationLevel.SUCCESS,
        ... )
    """
    
    def __init__(self, config: Optional[NotificationConfig] = None):
        self.config = config
        self._providers: List[NotificationProvider] = []
        
        if config:
            self._setup_from_config(config)
    
    def _setup_from_config(self, config: NotificationConfig) -> None:
        """Setup providers from config."""
        if config.slack_enabled and config.slack_webhook_url:
            self.add_provider(SlackNotifier(
                webhook_url=config.slack_webhook_url.get_secret_value(),
                channel=config.slack_channel,
            ))
        
        if config.discord_enabled and config.discord_webhook_url:
            self.add_provider(DiscordNotifier(
                webhook_url=config.discord_webhook_url.get_secret_value(),
            ))
        
        if config.email_enabled and config.smtp_host:
            self.add_provider(EmailNotifier(
                smtp_host=config.smtp_host,
                smtp_port=config.smtp_port,
                username=config.smtp_username or "",
                password=config.smtp_password.get_secret_value() if config.smtp_password else "",
                from_address=config.email_from or "",
                to_addresses=config.email_to,
            ))
    
    def add_provider(self, provider: NotificationProvider) -> None:
        """Add a notification provider."""
        self._providers.append(provider)
        logger.info(f"Added notification provider: {provider.name}")
    
    async def notify(
        self,
        title: str,
        message: str,
        level: NotificationLevel = NotificationLevel.INFO,
        details: Optional[Dict[str, Any]] = None,
        url: Optional[str] = None,
    ) -> Dict[str, bool]:
        """
        Send notification to all providers.
        
        Returns:
            Dict mapping provider names to success status
        """
        notification = Notification(
            title=title,
            message=message,
            level=level,
            details=details,
            url=url,
        )
        
        results = {}
        
        tasks = [
            self._send_to_provider(provider, notification)
            for provider in self._providers
        ]
        
        if tasks:
            provider_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for provider, result in zip(self._providers, provider_results):
                if isinstance(result, Exception):
                    results[provider.name] = False
                    logger.error(f"Error sending to {provider.name}: {result}")
                else:
                    results[provider.name] = result
        
        return results
    
    async def _send_to_provider(
        self,
        provider: NotificationProvider,
        notification: Notification,
    ) -> bool:
        """Send notification to a single provider."""
        try:
            return await provider.send(notification)
        except Exception as e:
            logger.error(f"Error sending to {provider.name}: {e}")
            return False
    
    async def notify_crawl_complete(
        self,
        url: str,
        pages_crawled: int,
        duration_seconds: float,
        errors: int = 0,
    ) -> Dict[str, bool]:
        """Send crawl completion notification."""
        level = NotificationLevel.SUCCESS if errors == 0 else NotificationLevel.WARNING
        
        return await self.notify(
            title="Crawl Complete",
            message=f"Finished crawling {url}",
            level=level,
            details={
                "Pages Crawled": pages_crawled,
                "Duration": f"{duration_seconds:.1f}s",
                "Errors": errors,
            },
            url=url,
        )
    
    async def notify_crawl_error(
        self,
        url: str,
        error: str,
    ) -> Dict[str, bool]:
        """Send crawl error notification."""
        return await self.notify(
            title="Crawl Error",
            message=f"Error crawling {url}: {error}",
            level=NotificationLevel.ERROR,
            url=url,
        )


__all__ = [
    "NotificationLevel",
    "Notification",
    "NotificationProvider",
    "SlackNotifier",
    "DiscordNotifier",
    "EmailNotifier",
    "NotificationManager",
]
