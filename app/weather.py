from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib import error, request


def _parse_period_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        text = value.replace("Z", "+00:00")
        return datetime.fromisoformat(text)
    except ValueError:
        return None


@dataclass
class WeatherForecast:
    current_temp: int | None
    temperature_unit: str
    wind_speed: str
    short_forecast: str
    summary: str
    updated_at: datetime
    source_url: str = ""
    today_summary: str = ""
    tomorrow_summary: str = ""

    @property
    def temperature_label(self) -> str:
        if self.current_temp is None:
            return "--°"
        return f"{self.current_temp}°{self.temperature_unit}"


def _http_json(url: str) -> dict[str, Any]:
    req = request.Request(
        url,
        headers={
            "User-Agent": "pyTide/0.1 (+https://github.com/kellyk/pyTide)",
            "Accept": "application/json",
        },
    )
    with request.urlopen(req, timeout=20) as resp:
        payload = resp.read().decode("utf-8")
    return json.loads(payload)


def parse_weather_payload(payload: dict[str, Any]) -> WeatherForecast:
    if not isinstance(payload, dict):
        return WeatherForecast(None, "F", "--", "Unavailable", "Weather unavailable", datetime.now(), "", "", "")

    properties = payload.get("properties", {}) if isinstance(payload, dict) else {}
    periods = properties.get("periods", [])
    if not periods and isinstance(payload.get("features"), list):
        feature = payload["features"][0]
        properties = feature.get("properties", {}) if isinstance(feature, dict) else {}
        periods = properties.get("periods", [])

    if not periods:
        return WeatherForecast(
            current_temp=None,
            temperature_unit="F",
            wind_speed="--",
            short_forecast="Unavailable",
            summary="Weather unavailable",
            updated_at=datetime.now(),
            source_url=str(properties.get("forecast", "")),
            today_summary="Unavailable",
            tomorrow_summary="Unavailable",
        )

    now = datetime.now().astimezone()
    current = periods[0]
    current_distance = None
    for item in periods:
        start_time = _parse_period_time(item.get("startTime"))
        end_time = _parse_period_time(item.get("endTime"))
        if start_time is not None and start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=now.tzinfo)
        if end_time is not None and end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=now.tzinfo)

        if start_time and end_time:
            if start_time <= now <= end_time:
                current = item
                current_distance = None
                break
            delta = min(abs((start_time - now).total_seconds()), abs((end_time - now).total_seconds()))
            if current_distance is None or delta < current_distance:
                current = item
                current_distance = delta
        elif current_distance is None:
            current = item

    temp = current.get("temperature")
    unit = (current.get("temperatureUnit") or "F").upper()
    wind = current.get("windSpeed") or "--"
    short = current.get("shortForecast") or "Weather unavailable"
    summary = current.get("detailedForecast") or short

    current_name = str(current.get("name") or "Now")
    today_summary = f"Now: {temp}°{unit}, {short}" if temp is not None else f"Now: {short}"

    next_period = next((item for item in periods if item is not current), None)
    if next_period is None:
        tomorrow_summary = "Next: --"
    else:
        next_temp = next_period.get("temperature")
        next_short = next_period.get("shortForecast") or "Weather unavailable"
        next_name = str(next_period.get("name") or "Next")
        tomorrow_summary = (
            f"{next_name}: {next_temp}°{unit}, {next_short}"
            if next_temp is not None
            else f"{next_name}: {next_short}"
        )

    return WeatherForecast(
        current_temp=int(temp) if temp is not None else None,
        temperature_unit=unit,
        wind_speed=str(wind),
        short_forecast=str(short),
        summary=str(summary),
        updated_at=datetime.now(),
        source_url=str(properties.get("forecast", "") or ""),
        today_summary=today_summary,
        tomorrow_summary=tomorrow_summary,
    )


def fetch_weather(latitude: float, longitude: float) -> WeatherForecast:
    if latitude is None or longitude is None:
        raise ValueError("latitude and longitude are required for the NOAA weather lookup")

    lat = float(latitude)
    lon = float(longitude)
    if lat < -90 or lat > 90:
        raise ValueError(f"Latitude out of range: {latitude}")
    if lon < -180 or lon > 180:
        raise ValueError(f"Longitude out of range: {longitude}")

    points_url = f"https://api.weather.gov/points/{lat},{lon}"
    points_payload = _http_json(points_url)
    properties = points_payload.get("properties", {}) if isinstance(points_payload, dict) else {}
    forecast_url = properties.get("forecast") or properties.get("forecastHourly")
    if not forecast_url:
        raise RuntimeError("NOAA weather API did not return a forecast URL")

    forecast_payload = _http_json(forecast_url)
    weather = parse_weather_payload(forecast_payload)
    weather.source_url = forecast_url
    if weather.current_temp is None and weather.short_forecast == "Unavailable":
        raise RuntimeError("NOAA weather payload was empty or malformed")
    return weather
