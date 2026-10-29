from __future__ import annotations

import shutil
import tarfile
import urllib.request
from datetime import datetime
from pathlib import Path


DEFAULT_HARMONICS_URLS = [
    "https://flaterco.com/xtide/files/harmonics-dwf-20251228-free.tar.xz",
    "https://github.com/openwatersio/tide-database/releases/latest/download/harmonics-dwf.tcd",
]


def _download_bytes(url: str, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=30) as response, open(destination, "wb") as handle:
        shutil.copyfileobj(response, handle)
    return destination


def _extract_tcd_from_archive(archive_path: Path, destination_dir: Path) -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "r:*") as archive:
        member = None
        for candidate in archive.getmembers():
            if candidate.isfile() and candidate.name.lower().endswith(".tcd"):
                member = candidate
                break
        if member is None:
            raise FileNotFoundError(f"No .tcd file found inside {archive_path}")
        archive.extract(member, path=destination_dir)

    extracted_path = destination_dir / Path(member.name).name
    if not extracted_path.exists():
        extracted_path = destination_dir / member.name
    return extracted_path


def download_harmonics(url: str, destination: str | Path) -> Path:
    target = Path(destination)
    is_archive = url.lower().endswith((".tar.xz", ".tar.gz", ".tgz", ".tar"))

    if is_archive:
        archive_path = target.with_suffix(target.suffix + ".download") if target.suffix else target.parent / (target.name + ".download")
        _download_bytes(url, archive_path)
        extracted = _extract_tcd_from_archive(archive_path, target.parent)
        archive_path.unlink(missing_ok=True)
        return extracted

    return _download_bytes(url, target)


def ensure_harmonics_file(harmonics_dir: str | Path, remote_url: str | None = None, backup_path: str | Path | None = None) -> Path:
    harmonics_dir = Path(harmonics_dir)
    harmonics_dir.mkdir(parents=True, exist_ok=True)

    if remote_url is None:
        remote_url = DEFAULT_HARMONICS_URLS[0]

    backup = Path(backup_path) if backup_path is not None else harmonics_dir / "last_known_good.tcd"
    expected_name = Path(remote_url).name
    target_path = harmonics_dir / expected_name
    if target_path.exists() and target_path.suffix.lower() == ".tcd":
        return target_path

    if any(path.suffix.lower() == ".tcd" for path in harmonics_dir.iterdir()):
        installed = next(path for path in harmonics_dir.iterdir() if path.suffix.lower() == ".tcd")
        return installed

    try:
        downloaded = download_harmonics(remote_url, target_path)
        if backup.exists() and downloaded.exists():
            shutil.copy2(downloaded, backup)
        return downloaded
    except Exception:
        if backup.exists():
            return backup
        raise


def refresh_harmonics_if_needed(harmonics_dir: str | Path, remote_url: str | None = None, backup_path: str | Path | None = None, max_age_hours: int = 336) -> Path:
    harmonics_dir = Path(harmonics_dir)
    harmonics_dir.mkdir(parents=True, exist_ok=True)
    backup = Path(backup_path) if backup_path is not None else harmonics_dir / "last_known_good.tcd"

    if remote_url is None:
        remote_url = DEFAULT_HARMONICS_URLS[0]

    candidate = None
    for path in sorted(harmonics_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if path.suffix.lower() == ".tcd":
            candidate = path
            break

    if candidate is not None:
        age_hours = (datetime.now() - datetime.fromtimestamp(candidate.stat().st_mtime)).total_seconds() / 3600
        if age_hours < max_age_hours:
            return candidate

    try:
        downloaded = download_harmonics(remote_url, harmonics_dir / "harmonics-dwf-latest.tcd")
        if backup.exists() and downloaded.exists():
            shutil.copy2(downloaded, backup)
        return downloaded
    except Exception:
        if backup.exists():
            return backup
        raise
