"""
WebPort Checkpoint & Resume System

Production-ready checkpoint mechanism for:
- Saving crawl state at regular intervals
- Resuming interrupted crawls
- Content change detection

Addresses Critique #4: No Incremental/Resume Capability
Addresses Critique #18: No Partial Result Persistence
Addresses Critique #19: No Content Change Detection
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from webport.core.exceptions import CheckpointSaveError, CheckpointLoadError, CheckpointCorruptError

logger = logging.getLogger(__name__)


class CrawlStatus(Enum):
    NOT_STARTED = auto()
    IN_PROGRESS = auto()
    PAUSED = auto()
    COMPLETED = auto()
    FAILED = auto()
    INTERRUPTED = auto()


@dataclass
class CrawlProgress:
    total_discovered: int = 0
    total_processed: int = 0
    total_completed: int = 0
    total_failed: int = 0
    total_skipped: int = 0
    start_time: Optional[str] = None
    last_update_time: Optional[str] = None
    elapsed_seconds: float = 0.0
    pages_per_minute: float = 0.0
    bytes_downloaded: int = 0
    
    @property
    def completion_percentage(self) -> float:
        if self.total_discovered == 0:
            return 0.0
        return (self.total_processed / self.total_discovered) * 100
    
    @property
    def estimated_remaining_seconds(self) -> float:
        if self.pages_per_minute <= 0:
            return 0.0
        remaining = self.total_discovered - self.total_processed
        return (remaining / self.pages_per_minute) * 60
    
    def update_rate(self) -> None:
        if self.elapsed_seconds > 0:
            self.pages_per_minute = (self.total_processed / self.elapsed_seconds) * 60


@dataclass 
class CrawlCheckpoint:
    """Complete checkpoint of a crawl operation."""
    
    checkpoint_id: str
    crawl_id: str
    target_url: str
    status: CrawlStatus = CrawlStatus.NOT_STARTED
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    version: str = "1.0.0"
    progress: CrawlProgress = field(default_factory=CrawlProgress)
    pending_urls: List[str] = field(default_factory=list)
    completed_urls: Set[str] = field(default_factory=set)
    failed_urls: Dict[str, str] = field(default_factory=dict)
    url_queue: List[Tuple[str, int]] = field(default_factory=list)
    config_hash: Optional[str] = None
    content_hashes: Dict[str, str] = field(default_factory=dict)
    data_files: List[str] = field(default_factory=list)
    error_counts: Dict[str, int] = field(default_factory=dict)
    
    def mark_url_completed(self, url: str, content_hash: Optional[str] = None) -> None:
        self.completed_urls.add(url)
        self.progress.total_completed += 1
        self.progress.total_processed += 1
        if content_hash:
            self.content_hashes[url] = content_hash
        if url in self.pending_urls:
            self.pending_urls.remove(url)
        self._update_timestamp()
    
    def mark_url_failed(self, url: str, error: str) -> None:
        self.failed_urls[url] = error
        self.progress.total_failed += 1
        self.progress.total_processed += 1
        error_type = error.split(":")[0] if ":" in error else error
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
        if url in self.pending_urls:
            self.pending_urls.remove(url)
        self._update_timestamp()
    
    def add_discovered_url(self, url: str, depth: int = 0) -> bool:
        if url in self.completed_urls or url in self.failed_urls:
            return False
        if url not in self.pending_urls:
            self.pending_urls.append(url)
            self.url_queue.append((url, depth))
            self.progress.total_discovered += 1
            return True
        return False
    
    def get_next_url(self) -> Optional[Tuple[str, int]]:
        if self.url_queue:
            return self.url_queue.pop(0)
        return None
    
    def has_changed(self, url: str, new_hash: str) -> bool:
        old_hash = self.content_hashes.get(url)
        return old_hash is None or old_hash != new_hash
    
    def _update_timestamp(self) -> None:
        now = datetime.utcnow()
        self.updated_at = now.isoformat()
        self.progress.last_update_time = self.updated_at
        if self.progress.start_time:
            start = datetime.fromisoformat(self.progress.start_time)
            self.progress.elapsed_seconds = (now - start).total_seconds()
            self.progress.update_rate()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "crawl_id": self.crawl_id,
            "target_url": self.target_url,
            "status": self.status.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
            "progress": asdict(self.progress),
            "pending_urls": self.pending_urls,
            "completed_urls": list(self.completed_urls),
            "failed_urls": self.failed_urls,
            "url_queue": self.url_queue,
            "config_hash": self.config_hash,
            "content_hashes": self.content_hashes,
            "data_files": self.data_files,
            "error_counts": self.error_counts,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CrawlCheckpoint":
        data["status"] = CrawlStatus[data["status"]]
        data["progress"] = CrawlProgress(**data["progress"])
        data["completed_urls"] = set(data["completed_urls"])
        data["url_queue"] = [tuple(x) for x in data["url_queue"]]
        return cls(**data)


class FileCheckpointStorage:
    """File-based checkpoint storage with compression."""
    
    def __init__(self, checkpoint_dir: Path, compress: bool = True, keep_backups: int = 3):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.compress = compress
        self.keep_backups = keep_backups
        self._lock = threading.Lock()
    
    def _get_path(self, checkpoint_id: str) -> Path:
        ext = ".json.gz" if self.compress else ".json"
        return self.checkpoint_dir / f"{checkpoint_id}{ext}"
    
    def save(self, checkpoint: CrawlCheckpoint) -> None:
        path = self._get_path(checkpoint.checkpoint_id)
        temp_path = path.with_suffix(".tmp")
        
        try:
            with self._lock:
                data = json.dumps(checkpoint.to_dict(), indent=2)
                if self.compress:
                    with gzip.open(temp_path, "wt", encoding="utf-8") as f:
                        f.write(data)
                else:
                    with open(temp_path, "w", encoding="utf-8") as f:
                        f.write(data)
                temp_path.replace(path)
                logger.debug(f"[Checkpoint] Saved: {checkpoint.checkpoint_id}")
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise CheckpointSaveError(str(path), cause=e)
    
    def load(self, checkpoint_id: str) -> Optional[CrawlCheckpoint]:
        path = self._get_path(checkpoint_id)
        if not path.exists():
            return None
        
        try:
            if self.compress:
                with gzip.open(path, "rt", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            return CrawlCheckpoint.from_dict(data)
        except json.JSONDecodeError as e:
            raise CheckpointCorruptError(str(path), f"Invalid JSON: {e}")
        except Exception as e:
            raise CheckpointLoadError(str(path), cause=e)
    
    def exists(self, checkpoint_id: str) -> bool:
        return self._get_path(checkpoint_id).exists()
    
    def delete(self, checkpoint_id: str) -> None:
        path = self._get_path(checkpoint_id)
        if path.exists():
            path.unlink()
    
    def list_checkpoints(self, crawl_id: Optional[str] = None) -> List[str]:
        checkpoints = []
        for path in self.checkpoint_dir.glob("*.json*"):
            if ".bak" in path.name:
                continue
            name = path.name
            for ext in [".json.gz", ".json"]:
                if name.endswith(ext):
                    name = name[:-len(ext)]
                    break
            checkpoints.append(name)
        return sorted(checkpoints)


class CheckpointManager:
    """High-level checkpoint management with automatic saving."""
    
    def __init__(
        self,
        checkpoint_dir: Optional[Path] = None,
        auto_save_interval: float = 60.0,
        save_on_n_urls: int = 100,
    ):
        checkpoint_dir = checkpoint_dir or Path("./.webport/checkpoints")
        self.storage = FileCheckpointStorage(checkpoint_dir)
        self.auto_save_interval = auto_save_interval
        self.save_on_n_urls = save_on_n_urls
        self._current_checkpoint: Optional[CrawlCheckpoint] = None
        self._auto_save_thread: Optional[threading.Thread] = None
        self._stop_auto_save = threading.Event()
        self._urls_since_save = 0
        self._lock = threading.Lock()
    
    @property
    def current(self) -> Optional[CrawlCheckpoint]:
        return self._current_checkpoint
    
    def get_or_create(self, target_url: str, crawl_id: Optional[str] = None, 
                      force_new: bool = False) -> CrawlCheckpoint:
        from urllib.parse import urlparse
        crawl_id = crawl_id or f"crawl_{urlparse(target_url).netloc.replace('.', '_')}"
        
        if not force_new:
            existing_ids = self.storage.list_checkpoints(crawl_id)
            for checkpoint_id in existing_ids:
                checkpoint = self.storage.load(checkpoint_id)
                if checkpoint and checkpoint.status in (
                    CrawlStatus.IN_PROGRESS, CrawlStatus.PAUSED, CrawlStatus.INTERRUPTED
                ):
                    logger.info(f"[Checkpoint] Resuming: {checkpoint_id}")
                    checkpoint.status = CrawlStatus.IN_PROGRESS
                    self._current_checkpoint = checkpoint
                    return checkpoint
        
        checkpoint_id = f"{crawl_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        checkpoint = CrawlCheckpoint(
            checkpoint_id=checkpoint_id,
            crawl_id=crawl_id,
            target_url=target_url,
            status=CrawlStatus.IN_PROGRESS,
        )
        checkpoint.progress.start_time = datetime.utcnow().isoformat()
        checkpoint.add_discovered_url(target_url, depth=0)
        self._current_checkpoint = checkpoint
        self.save()
        logger.info(f"[Checkpoint] Created: {checkpoint_id}")
        return checkpoint
    
    def save(self) -> None:
        if not self._current_checkpoint:
            return
        with self._lock:
            self._current_checkpoint._update_timestamp()
            self.storage.save(self._current_checkpoint)
            self._urls_since_save = 0
    
    def mark_completed(self, url: str, content_hash: Optional[str] = None) -> None:
        if not self._current_checkpoint:
            return
        self._current_checkpoint.mark_url_completed(url, content_hash)
        self._urls_since_save += 1
        if self._urls_since_save >= self.save_on_n_urls:
            self.save()
    
    def mark_failed(self, url: str, error: str) -> None:
        if not self._current_checkpoint:
            return
        self._current_checkpoint.mark_url_failed(url, error)
        self._urls_since_save += 1
        if self._urls_since_save >= self.save_on_n_urls:
            self.save()
    
    def mark_complete(self) -> None:
        if not self._current_checkpoint:
            return
        self._current_checkpoint.status = CrawlStatus.COMPLETED
        self.save()
    
    def start_auto_save(self, interval_seconds: Optional[float] = None) -> None:
        if self._auto_save_thread and self._auto_save_thread.is_alive():
            return
        interval = interval_seconds or self.auto_save_interval
        self._stop_auto_save.clear()
        
        def auto_save_loop():
            while not self._stop_auto_save.wait(interval):
                if self._current_checkpoint:
                    self.save()
        
        self._auto_save_thread = threading.Thread(target=auto_save_loop, daemon=True)
        self._auto_save_thread.start()
    
    def stop_auto_save(self) -> None:
        self._stop_auto_save.set()
        if self._auto_save_thread:
            self._auto_save_thread.join(timeout=5.0)
    
    def get_progress_report(self) -> str:
        if not self._current_checkpoint:
            return "No active crawl"
        cp = self._current_checkpoint
        p = cp.progress
        return f"""
{'='*60}
CRAWL PROGRESS: {cp.crawl_id}
{'='*60}
Status: {cp.status.name}
Progress: {p.completion_percentage:.1f}%
  Discovered: {p.total_discovered}
  Completed:  {p.total_completed}
  Failed:     {p.total_failed}
  Remaining:  {p.total_discovered - p.total_processed}
Rate: {p.pages_per_minute:.1f} pages/min
ETA: {p.estimated_remaining_seconds / 60:.1f} min
"""


def compute_content_hash(content: Union[str, bytes]) -> str:
    """Compute hash for change detection."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()


__all__ = [
    "CrawlStatus", "CrawlProgress", "CrawlCheckpoint", "FileCheckpointStorage",
    "CheckpointManager", "compute_content_hash",
]
