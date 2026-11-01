from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from app.harmonics_updater import _resolve_download_url, refresh_harmonics_if_needed


class _DummyResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def __enter__(self):
        import io

        self._stream = io.BytesIO(self._payload)
        return self._stream

    def __exit__(self, exc_type, exc, tb):
        return False


def test_resolve_download_url_picks_tcd_asset(monkeypatch):
    payload = {
        "assets": [
            {
                "name": "slackwater-20261031.tcd",
                "browser_download_url": "https://example.com/slackwater-20261031.tcd",
            },
            {
                "name": "notes.txt",
                "browser_download_url": "https://example.com/notes.txt",
            },
        ]
    }

    def fake_open_url(_url):
        return _DummyResponse(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr("app.harmonics_updater._open_url", fake_open_url)

    resolved = _resolve_download_url("https://api.github.com/repos/openwatersio/slackwater-database/releases/latest")
    assert resolved.endswith("slackwater-20261031.tcd")


def test_refresh_returns_existing_local_file_when_download_fails(tmp_path, monkeypatch):
    harmonics_dir = tmp_path / "xtide"
    harmonics_dir.mkdir(parents=True, exist_ok=True)

    local_tcd = harmonics_dir / "local.tcd"
    local_tcd.write_bytes(b"local")
    stale_time = (datetime.now() - timedelta(days=30)).timestamp()
    local_tcd.touch()
    import os

    os.utime(local_tcd, (stale_time, stale_time))

    def fail_download(_url, _destination):
        raise RuntimeError("network error")

    monkeypatch.setattr("app.harmonics_updater.download_harmonics", fail_download)

    selected = refresh_harmonics_if_needed(
        harmonics_dir=harmonics_dir,
        remote_url="https://api.github.com/repos/openwatersio/slackwater-database/releases/latest",
        backup_path=harmonics_dir / "last_known_good.tcd",
        max_age_hours=1,
    )
    assert selected == local_tcd


def test_refresh_returns_backup_when_no_local_tcd_and_download_fails(tmp_path, monkeypatch):
    harmonics_dir = tmp_path / "xtide"
    harmonics_dir.mkdir(parents=True, exist_ok=True)
    backup = harmonics_dir / "last_known_good.tcd"
    backup.write_bytes(b"backup")

    def fail_download(_url, _destination):
        raise RuntimeError("network error")

    monkeypatch.setattr("app.harmonics_updater.download_harmonics", fail_download)

    selected = refresh_harmonics_if_needed(
        harmonics_dir=harmonics_dir,
        remote_url="https://api.github.com/repos/openwatersio/slackwater-database/releases/latest",
        backup_path=backup,
        max_age_hours=1,
    )
    assert selected == backup


def test_refresh_raises_when_no_local_or_backup_and_download_fails(tmp_path, monkeypatch):
    harmonics_dir = tmp_path / "xtide"
    harmonics_dir.mkdir(parents=True, exist_ok=True)

    def fail_download(_url, _destination):
        raise RuntimeError("network error")

    monkeypatch.setattr("app.harmonics_updater.download_harmonics", fail_download)

    with pytest.raises(RuntimeError):
        refresh_harmonics_if_needed(
            harmonics_dir=harmonics_dir,
            remote_url="https://api.github.com/repos/openwatersio/slackwater-database/releases/latest",
            backup_path=harmonics_dir / "last_known_good.tcd",
            max_age_hours=1,
        )
