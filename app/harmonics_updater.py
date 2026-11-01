from __future__ import annotations

import json
import shutil
import tarfile
import urllib.request
from urllib.parse import urlparse
from datetime import datetime
from pathlib import Path


DEFAULT_HARMONICS_URLS = [
    "https://api.github.com/repos/openwatersio/slackwater-database/releases/latest",
    "https://flaterco.com/xtide/files/harmonics-dwf-20251228-free.tar.xz",
]

_GITHUB_ACCEPT_HEADER = "application/vnd.github+json"


def _open_url(url: str):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "pyTide/1.0",
            "Accept": _GITHUB_ACCEPT_HEADER if "api.github.com" in url else "*/*",
        },
    )
    return urllib.request.urlopen(request, timeout=30)


def _resolve_github_release_asset_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc != "api.github.com":
        return url
    if "/releases/latest" not in parsed.path:
        return url

    with _open_url(url) as response:
        payload = json.load(response)

    assets = payload.get("assets", []) if isinstance(payload, dict) else []
    if not isinstance(assets, list):
        raise ValueError("Invalid GitHub release payload: assets is not a list")

    preferred = [
        asset
        for asset in assets
        if isinstance(asset, dict)
        and str(asset.get("name", "")).lower().endswith(".tcd")
        and asset.get("browser_download_url")
    ]
    if preferred:
        preferred.sort(key=lambda item: len(str(item.get("name", ""))))
        return str(preferred[0]["browser_download_url"])

    fallback = [
        asset
        for asset in assets
        if isinstance(asset, dict)
        and str(asset.get("name", "")).lower().endswith((".tar.xz", ".tar.gz", ".tgz", ".tar"))
        and asset.get("browser_download_url")
    ]
    if fallback:
        fallback.sort(key=lambda item: len(str(item.get("name", ""))))
        return str(fallback[0]["browser_download_url"])

    raise FileNotFoundError("No compatible harmonics asset found in latest GitHub release")


def _resolve_download_url(url: str) -> str:
    if "api.github.com" in url and "/releases/latest" in url:
        return _resolve_github_release_asset_url(url)
    return url


def _download_bytes(url: str, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with _open_url(url) as response, open(destination, "wb") as handle:
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
    resolved_url = _resolve_download_url(url)
    target = Path(destination)
    is_archive = resolved_url.lower().endswith((".tar.xz", ".tar.gz", ".tgz", ".tar"))

    if is_archive:
        archive_path = target.with_suffix(target.suffix + ".download") if target.suffix else target.parent / (target.name + ".download")
        _download_bytes(resolved_url, archive_path)
        extracted = _extract_tcd_from_archive(archive_path, target.parent)
        archive_path.unlink(missing_ok=True)
        return extracted

    return _download_bytes(resolved_url, target)


def ensure_harmonics_file(harmonics_dir: str | Path, remote_url: str | None = None, backup_path: str | Path | None = None) -> Path:
    harmonics_dir = Path(harmonics_dir)
    harmonics_dir.mkdir(parents=True, exist_ok=True)

    if remote_url is None:
        remote_url = DEFAULT_HARMONICS_URLS[0]

    backup = Path(backup_path) if backup_path is not None else harmonics_dir / "last_known_good.tcd"
    expected_name = Path(_resolve_download_url(remote_url)).name
    target_path = harmonics_dir / expected_name
    if target_path.exists() and target_path.suffix.lower() == ".tcd":
        return target_path

    installed_candidates = [path for path in harmonics_dir.iterdir() if path.suffix.lower() == ".tcd"]
    if installed_candidates:
        installed = max(installed_candidates, key=lambda item: item.stat().st_mtime)
        return installed

    try:
        downloaded = download_harmonics(remote_url, target_path)
        if downloaded.exists():
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
        downloaded = download_harmonics(remote_url, harmonics_dir / "harmonics-latest.tcd")
        if downloaded.exists():
            shutil.copy2(downloaded, backup)
        return downloaded
    except Exception:
        if candidate is not None:
            return candidate
        if backup.exists():
            return backup
        raise
