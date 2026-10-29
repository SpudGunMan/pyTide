from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class TideEvent:
    timestamp: datetime
    event_type: str
    height: float | None = None
    raw: str = ""


@dataclass(frozen=True)
class TideForecast:
    station: str
    events: list[TideEvent]
    source: str = "xtide"


def _normalize_event_type(raw: str) -> str:
    value = (raw or "").strip().lower().replace("_", " ")
    if "high" in value:
        return "High"
    if "low" in value:
        return "Low"
    if "sunrise" in value:
        return "Sunrise"
    if "sunset" in value:
        return "Sunset"
    if "moonrise" in value or "moon rise" in value:
        return "Moonrise"
    if "moonset" in value or "moon set" in value:
        return "Moonset"
    return raw.strip() or "Unknown"


def parse_station_coordinates(text: str) -> tuple[float, float] | None:
    if not text:
        return None
    for line in text.splitlines():
        match = re.search(
            r"(?P<lat>\d+(?:\.\d+)?)\s*°\s*(?P<lat_dir>[NS])\s*,\s*"
            r"(?P<lon>\d+(?:\.\d+)?)\s*°\s*(?P<lon_dir>[EW])",
            line,
            flags=re.IGNORECASE,
        )
        if not match:
            continue
        lat = float(match.group("lat"))
        lon = float(match.group("lon"))
        if match.group("lat_dir").upper() == "S":
            lat *= -1
        if match.group("lon_dir").upper() == "W":
            lon *= -1
        return lat, lon
    return None


def get_station_coordinates(xtide_path: str, station: str) -> tuple[float, float] | None:
    if not station or not Path(xtide_path).exists():
        return None
    try:
        result = subprocess.run(
            [xtide_path, "-l", station],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return parse_station_coordinates(result.stdout)


def parse_tide_output(text: str, station: str = "") -> TideForecast:
    events: list[TideEvent] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = re.search(
            r"^(?P<date>\d{4}-\d{2}-\d{2})\s+"
            r"(?P<time>\d{1,2}:\d{2}\s*(?:AM|PM)?)"
            r"(?:\s+(?P<tz>[A-Z]{3,5}))?"
            r"(?:\s+(?P<height>[-+]?\d+(?:\.\d+)?)\s*(?:feet|ft)?)?"
            r"\s+(?P<event>High\s+Tide|Low\s+Tide|Sunrise|Sunset|Moon(?:\s+)?Rise|Moon(?:\s+)?Set|First\s+Quarter|Last\s+Quarter|Full\s+Moon|New\s+Moon)"
            r"\s*$",
            stripped,
            flags=re.IGNORECASE,
        )
        if not match:
            continue
        dt_text = f"{match.group('date')} {match.group('time')}"
        try:
            dt = datetime.strptime(dt_text, "%Y-%m-%d %I:%M %p")
        except ValueError:
            try:
                dt = datetime.strptime(dt_text, "%Y-%m-%d %H:%M")
            except ValueError:
                continue
        event_type = _normalize_event_type(match.group("event"))
        height_value = match.group("height")
        height = float(height_value) if height_value is not None else None
        events.append(TideEvent(timestamp=dt, event_type=event_type, height=height, raw=stripped))

    return TideForecast(station=station, events=events, source="xtide")


def get_station_list(xtide_path: str) -> list[str]:
    if not Path(xtide_path).exists():
        return []
    try:
        result = subprocess.run(
            [xtide_path, "-l"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode != 0:
        return []
    stations = []
    for line in result.stdout.splitlines():
        if line.strip() and "No" not in line and "Available" not in line:
            stations.append(line.strip())
    return stations


def fetch_forecast(xtide_path: str, station: str, days: int = 7) -> TideForecast:
    if not Path(xtide_path).exists():
        raise FileNotFoundError(f"XTide executable not found at {xtide_path}")

    command = [xtide_path, "-l", station]
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"XTide command failed: {exc}") from exc

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "XTide returned a non-zero exit status")

    forecast = parse_tide_output(result.stdout, station=station)
    if not days:
        return TideForecast(station=station, events=forecast.events, source="xtide")

    now = datetime.now()
    start = now - timedelta(hours=18)
    cutoff = now + timedelta(days=days)
    future_events = [
        event for event in sorted(forecast.events, key=lambda item: item.timestamp)
        if start <= event.timestamp < cutoff
    ]
    return TideForecast(station=station, events=future_events, source="xtide")
