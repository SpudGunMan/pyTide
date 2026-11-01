from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path


def parse_coordinate(value, axis: str) -> float:
    if isinstance(value, (int, float)):
        numeric = float(value)
    else:
        text = str(value).strip()
        if not text:
            raise ValueError(f"{axis} cannot be empty")
        match = __import__("re").match(r"^([-+]?\d+(?:\.\d+)?)\s*([NSEW])?$", text, __import__("re").IGNORECASE)
        if match:
            numeric = float(match.group(1))
            direction = (match.group(2) or "").upper()
            if axis == "latitude":
                if direction in {"S"}:
                    numeric *= -1
                elif direction in {"N", ""}:
                    pass
                else:
                    raise ValueError(f"Invalid latitude direction '{direction}'")
            elif axis == "longitude":
                if direction in {"W"}:
                    numeric *= -1
                elif direction in {"E", ""}:
                    pass
                else:
                    raise ValueError(f"Invalid longitude direction '{direction}'")
            else:
                raise ValueError(f"Unsupported axis '{axis}'")
            return numeric
        numeric = float(text)

    if axis == "latitude" and not -90 <= numeric <= 90:
        raise ValueError(f"Latitude must be between -90 and 90, got {numeric}")
    if axis == "longitude" and not -180 <= numeric <= 180:
        raise ValueError(f"Longitude must be between -180 and 180, got {numeric}")
    return float(numeric)


@dataclass
class TideClockConfig:
    station: str = "LOCAL STATION"
    xtide_path: str = "/usr/local/bin/tide"
    harmonics_dir: str = "/usr/local/share/xtide"
    harmonics_url: str = "https://api.github.com/repos/openwatersio/slackwater-database/releases/latest"
    tide_height_unit: str = "m"
    cache_dir: str = ".pytide-cache"
    latitude: float | None = None
    longitude: float | None = None
    weather_enabled: bool = True
    weather_refresh_seconds: int = 14400
    fullscreen: bool = False
    windowed: bool = True
    width: int = 1280
    height: int = 800
    refresh_seconds: int = 300
    harmonics_refresh_hours: int = 336
    theme: str = "light"
    background_image: str | None = "img/beach.jpeg"
    background_overlay_alpha: int = 88
    panel_alpha: int = 188
    card_alpha: int = 188
    rail_alpha: int = 212
    table_alpha: int = 210
    clock_face_alpha: int = 140
    bg_color: tuple[int, int, int] = (222, 232, 241)
    accent_color: tuple[int, int, int] = (18, 66, 137)
    safety_margin: int = 64
    log_path: str = "pytide.log"
    last_known_good_harmonics: str = "last_known_good.tcd"

    @classmethod
    def _project_root(cls) -> Path:
        return Path(__file__).resolve().parent.parent

    @classmethod
    def _load_json_config(cls, file_name: str) -> dict:
        path = cls._project_root() / file_name
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Failed to read {file_name}: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError(f"{file_name} must contain a JSON object")
        return data

    @classmethod
    def _merged_defaults(cls) -> dict:
        defaults = {name: getattr(cls, name) for name in cls.__dataclass_fields__.keys()}
        defaults.update(cls._load_json_config("settings.example.json"))
        defaults.update(cls._load_json_config("settings.json"))

        if defaults.get("latitude") is not None:
            defaults["latitude"] = parse_coordinate(defaults["latitude"], "latitude")
        if defaults.get("longitude") is not None:
            defaults["longitude"] = parse_coordinate(defaults["longitude"], "longitude")

        for key in (
            "weather_refresh_seconds",
            "width",
            "height",
            "refresh_seconds",
            "harmonics_refresh_hours",
            "background_overlay_alpha",
            "panel_alpha",
            "card_alpha",
            "rail_alpha",
            "table_alpha",
            "clock_face_alpha",
        ):
            if key in defaults and defaults[key] is not None:
                defaults[key] = int(defaults[key])

        defaults["theme"] = str(defaults.get("theme", "light")).strip().lower()
        defaults["tide_height_unit"] = str(defaults.get("tide_height_unit", "m")).strip().lower()
        if defaults["tide_height_unit"] in {"meter", "meters"}:
            defaults["tide_height_unit"] = "m"
        elif defaults["tide_height_unit"] in {"foot", "feet"}:
            defaults["tide_height_unit"] = "ft"
        defaults["weather_enabled"] = bool(defaults.get("weather_enabled", True))
        defaults["fullscreen"] = bool(defaults.get("fullscreen", False))
        defaults["windowed"] = bool(defaults.get("windowed", True))
        return defaults

    @classmethod
    def from_args(cls, argv: list[str] | None = None) -> "TideClockConfig":
        defaults = cls._merged_defaults()

        parser = argparse.ArgumentParser(description="Run the pyTide tide clock")
        parser.add_argument("--station", default=defaults["station"])
        parser.add_argument("--xtide-path", default=defaults["xtide_path"])
        parser.add_argument("--harmonics-dir", default=defaults["harmonics_dir"])
        parser.add_argument("--harmonics-url", default=defaults["harmonics_url"])
        parser.add_argument("--cache-dir", default=defaults["cache_dir"])
        parser.add_argument("--tide-height-unit", choices=["m", "meter", "meters", "ft", "feet", "foot"], default=defaults["tide_height_unit"])
        parser.add_argument("--latitude", type=lambda value: parse_coordinate(value, "latitude"), default=defaults.get("latitude"))
        parser.add_argument("--longitude", type=lambda value: parse_coordinate(value, "longitude"), default=defaults.get("longitude"))
        parser.add_argument("--weather-refresh-seconds", type=int, default=defaults["weather_refresh_seconds"])
        parser.add_argument("--disable-weather", action="store_true", default=False)
        parser.add_argument("--fullscreen", action="store_true", default=False)
        parser.add_argument("--windowed", action="store_true", default=False)
        parser.add_argument("--width", type=int, default=defaults["width"])
        parser.add_argument("--height", type=int, default=defaults["height"])
        parser.add_argument("--refresh-seconds", type=int, default=defaults["refresh_seconds"])
        parser.add_argument("--harmonics-refresh-hours", type=int, default=defaults["harmonics_refresh_hours"])
        parser.add_argument("--theme", choices=["light", "dark"], default=defaults["theme"])
        parser.add_argument("--background-image", default=defaults.get("background_image"))
        parser.add_argument("--background-overlay-alpha", type=int, default=defaults["background_overlay_alpha"])
        parser.add_argument("--disable-background-image", action="store_true", default=False)
        parser.add_argument("--panel-alpha", type=int, default=defaults["panel_alpha"])
        parser.add_argument("--card-alpha", type=int, default=defaults["card_alpha"])
        parser.add_argument("--rail-alpha", type=int, default=defaults["rail_alpha"])
        parser.add_argument("--table-alpha", type=int, default=defaults["table_alpha"])
        parser.add_argument("--clock-face-alpha", type=int, default=defaults["clock_face_alpha"])
        args = parser.parse_args(argv)

        if args.fullscreen:
            fullscreen = True
            windowed = False
        elif args.windowed:
            fullscreen = False
            windowed = True
        else:
            fullscreen = bool(defaults.get("fullscreen", False))
            windowed = bool(defaults.get("windowed", True))
            if not fullscreen and not windowed:
                windowed = True

        theme = args.theme.lower().strip()
        tide_height_unit = args.tide_height_unit.lower().strip()
        if tide_height_unit in {"meter", "meters"}:
            tide_height_unit = "m"
        elif tide_height_unit in {"foot", "feet"}:
            tide_height_unit = "ft"
        background_image = None if args.disable_background_image else args.background_image
        background_overlay_alpha = max(0, min(255, int(args.background_overlay_alpha)))
        panel_alpha = max(0, min(255, int(args.panel_alpha)))
        card_alpha = max(0, min(255, int(args.card_alpha)))
        rail_alpha = max(0, min(255, int(args.rail_alpha)))
        table_alpha = max(0, min(255, int(args.table_alpha)))
        clock_face_alpha = max(0, min(255, int(args.clock_face_alpha)))

        cfg = cls(
            station=args.station,
            xtide_path=args.xtide_path,
            harmonics_dir=args.harmonics_dir,
            harmonics_url=args.harmonics_url,
            tide_height_unit=tide_height_unit,
            cache_dir=args.cache_dir,
            latitude=args.latitude,
            longitude=args.longitude,
            weather_enabled=(False if args.disable_weather else bool(defaults.get("weather_enabled", True))),
            weather_refresh_seconds=args.weather_refresh_seconds,
            fullscreen=fullscreen,
            windowed=windowed,
            width=args.width,
            height=args.height,
            refresh_seconds=args.refresh_seconds,
            harmonics_refresh_hours=args.harmonics_refresh_hours,
            theme=theme,
            background_image=background_image,
            background_overlay_alpha=background_overlay_alpha,
            panel_alpha=panel_alpha,
            card_alpha=card_alpha,
            rail_alpha=rail_alpha,
            table_alpha=table_alpha,
            clock_face_alpha=clock_face_alpha,
        )

        if theme == "dark":
            cfg.bg_color = (22, 30, 38)
            cfg.accent_color = (128, 190, 244)

        return cfg

    def cache_path(self) -> Path:
        return Path(self.cache_dir)

    def last_good_harmonics_path(self) -> Path:
        return self.cache_path() / self.last_known_good_harmonics
