"""Archive stage — creates ZIP of all site data."""

from __future__ import annotations

import logging
import zipfile
from pathlib import Path
from typing import List, Set

from webport.core.config import SiteConfig
from webport.core.models import StageResult

logger = logging.getLogger(__name__)

# Patterns to exclude from archive
EXCLUDE_PATTERNS: Set[str] = {
    "node_modules",
    ".next",
    "__pycache__",
    ".git",
    "dev.db",
    ".env",
    ".DS_Store",
}


def should_exclude(path: Path) -> bool:
    """Check if a path should be excluded from the archive."""
    for part in path.parts:
        if part in EXCLUDE_PATTERNS:
            return True
    return False


def create_archive(site_config: SiteConfig) -> StageResult:
    """Create a ZIP archive of all site data."""
    sites_dir = site_config.sites_dir
    domain_underscored = site_config.domain.replace(".", "_")
    zip_name = f"site_{domain_underscored}.zip"
    zip_path = Path(zip_name)

    files_added: List[str] = []
    errors: List[str] = []

    if not sites_dir.exists():
        return StageResult(
            stage="archive",
            success=False,
            errors=[f"Site directory not found: {sites_dir}"],
        )

    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in sorted(sites_dir.rglob("*")):
                if file_path.is_dir():
                    continue
                if should_exclude(file_path):
                    continue

                arcname = str(file_path.relative_to(sites_dir.parent))
                try:
                    zf.write(file_path, arcname)
                    files_added.append(arcname)
                except Exception as e:
                    errors.append(f"Failed to add {file_path}: {e}")

            # Also include webport.yaml if it exists at the site level
            config_path = sites_dir / "webport.yaml"
            if config_path.exists():
                arcname = str(config_path.relative_to(sites_dir.parent))
                if arcname not in files_added:
                    zf.write(config_path, arcname)
                    files_added.append(arcname)

    except Exception as e:
        return StageResult(
            stage="archive",
            success=False,
            errors=[f"Failed to create archive: {e}"],
        )

    logger.info(f"Created archive {zip_path} with {len(files_added)} files")

    return StageResult(
        stage="archive",
        success=True,
        files_created=[str(zip_path)],
        file_count=len(files_added),
        metadata={"archive_path": str(zip_path), "size_bytes": zip_path.stat().st_size},
    )
