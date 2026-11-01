from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pygame

from app.config import TideClockConfig
from app.harmonics_updater import refresh_harmonics_if_needed
from app.render import init_display, render_stub
from app.weather import fetch_weather
from app.xtide import fetch_forecast, get_station_coordinates
from app.tide_model import TideModel, TideReading


def _latest_tcd_info(harmonics_dir: str) -> tuple[Path, float] | None:
    root = Path(harmonics_dir)
    if not root.exists():
        return None
    candidates = [path for path in root.iterdir() if path.is_file() and path.suffix.lower() == ".tcd"]
    if not candidates:
        return None
    newest = max(candidates, key=lambda item: item.stat().st_mtime)
    return newest, newest.stat().st_mtime


def _build_model(config: TideClockConfig) -> TideModel:
    try:
        forecast = fetch_forecast(config.xtide_path, config.station, days=10)
        default_unit = (config.tide_height_unit or "m").strip().lower()
        if default_unit in {"meter", "meters"}:
            default_unit = "m"
        if default_unit in {"feet", "foot"}:
            default_unit = "ft"
        readings = [
            TideReading(
                timestamp=event.timestamp,
                event_type=event.event_type,
                level=event.height,
                level_unit=event.height_unit or default_unit,
                raw=event.raw,
            )
            for event in forecast.events
        ]
        return TideModel(station=config.station, readings=readings, updated_at=datetime.now())
    except Exception:
        return TideModel(station=config.station, readings=[], updated_at=datetime.now())


def _resolve_weather_coordinates(config: TideClockConfig) -> tuple[float, float] | None:
    if config.latitude is not None and config.longitude is not None:
        return float(config.latitude), float(config.longitude)
    if config.station and config.station != "LOCAL STATION":
        coords = get_station_coordinates(config.xtide_path, config.station)
        if coords is not None:
            config.latitude, config.longitude = coords
            return coords
    return None


def _build_weather(config: TideClockConfig):
    if not config.weather_enabled:
        return None
    coords = _resolve_weather_coordinates(config)
    if coords is None:
        print(
            "Weather is disabled because no latitude/longitude were supplied. "
            "Use --latitude and --longitude for your region, or choose an XTide station "
            "that includes coordinates, for example: --latitude 48.3917 --longitude -122.4970",
            file=sys.stderr,
        )
        return None
    try:
        return fetch_weather(coords[0], coords[1])
    except Exception:
        return None


def _refresh_harmonics(config: TideClockConfig) -> None:
    before = _latest_tcd_info(config.harmonics_dir)
    try:
        refreshed_path = refresh_harmonics_if_needed(
            harmonics_dir=config.harmonics_dir,
            remote_url=config.harmonics_url,
            backup_path=config.last_good_harmonics_path(),
            max_age_hours=config.harmonics_refresh_hours,
        )
        after = _latest_tcd_info(config.harmonics_dir)
        now = datetime.now().timestamp()
        if before is None and after is not None:
            print(f"Harmonics check: installed {after[0].name}", file=sys.stderr)
            return
        if before is not None and after is not None and before[0] == after[0] and abs(before[1] - after[1]) < 1e-6:
            age_hours = max(0.0, (now - after[1]) / 3600.0)
            print(
                f"Harmonics check: current ({after[0].name}, age {age_hours:.1f}h, threshold {config.harmonics_refresh_hours}h)",
                file=sys.stderr,
            )
            return
        if after is not None:
            print(f"Harmonics check: refreshed to {after[0].name}", file=sys.stderr)
            return
        print(f"Harmonics check: refreshed {Path(refreshed_path).name}", file=sys.stderr)
    except Exception as exc:
        print(f"Harmonics refresh skipped: {exc}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    config = TideClockConfig.from_args(argv)
    if config.station == "LOCAL STATION":
        print(
            "No station was configured. Pass --station with your XTide station name, "
            "for example: --station 'La Conner, Washington'",
            file=sys.stderr,
        )

    try:
        _refresh_harmonics(config)
        screen = init_display(config.width, config.height, fullscreen=config.fullscreen)
        clock = pygame.time.Clock()
        tide_model = _build_model(config)
        weather = _build_weather(config)
        last_weather_fetch = datetime.now()
        last_harmonics_check = datetime.now()
        running = True

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_q):
                        running = False
                    elif event.key == pygame.K_f:
                        config.fullscreen = not config.fullscreen
                        pygame.display.set_mode((0, 0), pygame.FULLSCREEN if config.fullscreen else 0)

            if not tide_model.readings:
                try:
                    tide_model = _build_model(config)
                except Exception:
                    pass

            now = datetime.now()
            if config.weather_enabled and (now - last_weather_fetch).total_seconds() >= config.weather_refresh_seconds:
                weather = _build_weather(config)
                last_weather_fetch = now

            if (now - last_harmonics_check).total_seconds() >= max(3600, config.refresh_seconds):
                _refresh_harmonics(config)
                last_harmonics_check = now

            render_stub(screen, config, now=now, station=config.station, forecast=tide_model, weather=weather)
            clock.tick(10)

        pygame.quit()
        return 0
    except RuntimeError as exc:
        print(f"pyTide startup failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
