import math
from datetime import datetime

from app.config import TideClockConfig, parse_coordinate
from app.tide_model import TideModel, TideReading
from app.render import _build_day_rows, _get_forecast_cards, _resolve_tide_angle
from app.xtide import parse_station_coordinates, parse_tide_output


SAMPLE_OUTPUT = """
2026-10-29 04:15 AM High Tide 5.82
2026-10-29 10:55 AM Low Tide 1.14
2026-10-29 05:06 PM High Tide 6.08
2026-10-29 11:48 PM Low Tide 0.62
"""


def test_parse_tide_output_extracts_events():
    forecast = parse_tide_output(SAMPLE_OUTPUT, station="Test Station")
    assert forecast.station == "Test Station"
    assert len(forecast.events) == 4
    assert forecast.events[0].event_type == "High"
    assert forecast.events[0].height == 5.82
    assert forecast.events[1].event_type == "Low"
    assert forecast.events[1].height == 1.14


def test_parse_tide_output_extracts_sunrise_and_sunset():
    forecast = parse_tide_output(
        """
        2026-10-29 06:18 AM Sunrise
        2026-10-29 04:15 AM High Tide 5.82
        2026-10-29 10:55 AM Low Tide 1.14
        2026-10-29 05:06 PM High Tide 6.08
        2026-10-29 11:48 PM Low Tide 0.62
        2026-10-29 06:40 PM Sunset
        2026-10-29 07:14 PM Moonrise
        2026-10-30 02:17 AM Moonset
        """,
        station="Test Station",
    )

    event_types = {event.event_type for event in forecast.events}
    assert "Sunrise" in event_types
    assert "Sunset" in event_types
    assert "Moonrise" in event_types
    assert "Moonset" in event_types
    assert len(forecast.events) == 8


def test_parse_tide_output_matches_xtide_output_with_timezone_and_moon_events():
    forecast = parse_tide_output(
        """
        2026-10-29 12:44 PM Moonset
        2026-10-29 02:36 PM PDT 7.37 feet Low Tide
        2026-10-29 05:55 PM PDT Sunset
        2026-10-29 07:02 PM PDT 9.78 feet High Tide
        2026-10-29 08:16 PM PDT Moonrise
        2026-10-30 02:44 AM PDT -2.57 feet Low Tide
        """,
        station="Test Station",
    )
    event_types = {event.event_type for event in forecast.events}
    assert "Moonset" in event_types
    assert "Moonrise" in event_types
    assert "Low" in event_types
    assert "High" in event_types
    assert "Sunset" in event_types
    assert len(forecast.events) == 6


def test_future_filter_keeps_only_upcoming_events():
    now = datetime(2026, 10, 29, 12, 0)
    events = [
        TideReading(datetime(2026, 10, 28, 5, 0), "Low", 1.2),
        TideReading(datetime(2026, 10, 29, 12, 30), "High", 5.9),
        TideReading(datetime(2026, 10, 29, 18, 15), "Low", 1.1),
        TideReading(datetime(2026, 10, 30, 6, 0), "Sunrise", None),
    ]
    future = [event for event in sorted(events, key=lambda item: item.timestamp) if event.timestamp >= now]
    assert len(future) == 3
    assert future[0].timestamp.date() == now.date()
    assert future[-1].timestamp.date() != datetime(2026, 10, 28, 5, 0).date()


def test_default_location_is_not_palo_alto():
    cfg = TideClockConfig()
    assert cfg.station != "Palo Alto Yacht Harbor, San Francisco Bay, California"
    assert cfg.latitude is None
    assert cfg.longitude is None


def test_config_defaults_are_valid():
    cfg = TideClockConfig()
    assert cfg.station
    assert cfg.xtide_path
    assert cfg.refresh_seconds > 0
    assert cfg.harmonics_refresh_hours > 0
    assert cfg.latitude is None or -90 <= cfg.latitude <= 90
    assert cfg.longitude is None or -180 <= cfg.longitude <= 180


def test_parse_coordinate_handles_cardinal_directions():
    assert parse_coordinate("48.4N", "latitude") == 48.4
    assert parse_coordinate("48.4S", "latitude") == -48.4
    assert parse_coordinate("122.6W", "longitude") == -122.6
    assert parse_coordinate("73.1E", "longitude") == 73.1
    assert TideClockConfig.from_args(["--latitude", "48.4N", "--longitude", "122.6W"]).latitude == 48.4
    assert TideClockConfig.from_args(["--latitude", "48.4N", "--longitude", "122.6W"]).longitude == -122.6


def test_xtide_station_output_parses_lat_lon():
    sample = '''
La Conner, Swinomish Channel, Washington
48.3917° N, 122.4970° W
'''
    assert parse_station_coordinates(sample) == (48.3917, -122.497)


def test_noaa_forecast_parser_extracts_current_conditions():
    payload = {
        "properties": {
            "forecast": "https://api.weather.gov/gridpoints/OKX/38,35/forecast",
            "periods": [
                {
                    "name": "This Afternoon",
                    "temperature": 68,
                    "temperatureUnit": "F",
                    "windSpeed": "8 mph",
                    "shortForecast": "Sunny",
                    "startTime": "2026-10-29T15:00:00-07:00",
                    "endTime": "2026-10-29T18:00:00-07:00",
                },
                {
                    "name": "Tonight",
                    "temperature": 58,
                    "temperatureUnit": "F",
                    "windSpeed": "6 mph",
                    "shortForecast": "Clear",
                    "startTime": "2026-10-29T18:00:00-07:00",
                    "endTime": "2026-10-30T06:00:00-07:00",
                },
            ],
        }
    }

    from app.weather import parse_weather_payload

    weather = parse_weather_payload(payload)
    assert weather.current_temp == 68
    assert weather.wind_speed == "8 mph"
    assert weather.short_forecast == "Sunny"
    assert weather.summary.startswith("Sunny")
    assert "This Afternoon" in weather.today_summary

    night_payload = {
        "properties": {
            "forecast": "https://api.weather.gov/gridpoints/OKX/38,35/forecast",
            "periods": [
                {
                    "name": "This Afternoon",
                    "temperature": 68,
                    "temperatureUnit": "F",
                    "windSpeed": "8 mph",
                    "shortForecast": "Sunny",
                    "startTime": "2026-10-29T15:00:00-07:00",
                    "endTime": "2026-10-29T18:00:00-07:00",
                },
                {
                    "name": "Tonight",
                    "temperature": 58,
                    "temperatureUnit": "F",
                    "windSpeed": "6 mph",
                    "shortForecast": "Clear",
                    "startTime": "2026-10-29T18:00:00-07:00",
                    "endTime": "2026-10-30T06:00:00-07:00",
                },
            ],
        }
    }

    import app.weather as weather_module
    original_now = weather_module.datetime
    weather_module.datetime = datetime
    try:
        now = datetime.now().astimezone()
        if now.hour >= 18:
            night_weather = weather_module.parse_weather_payload(night_payload)
            assert night_weather.current_temp == 58
            assert "Tonight" in night_weather.today_summary
        else:
            weather = weather_module.parse_weather_payload(payload)
            assert weather.current_temp == 68
    finally:
        weather_module.datetime = original_now


def test_forecast_cards_use_the_current_day_and_state():
    now = datetime(2026, 10, 29, 9, 0)
    model = TideModel(
        station="Test Station",
        readings=[
            TideReading(datetime(2026, 10, 29, 5, 0), "Low", 1.2),
            TideReading(datetime(2026, 10, 29, 11, 0), "High", 5.8),
            TideReading(datetime(2026, 10, 30, 5, 30), "Low", 1.1),
            TideReading(datetime(2026, 10, 30, 11, 30), "High", 6.0),
        ],
    )

    cards = _get_forecast_cards(model, now)
    assert cards[0][0] == "THURSDAY"
    assert "5.8" in cards[0][1]
    assert model.current_state(now) == "Rising"


def test_bottom_summary_only_shows_the_next_two_days():
    now = datetime(2026, 10, 29, 9, 0)
    model = TideModel(
        station="Test Station",
        readings=[
            TideReading(datetime(2026, 10, 29, 6, 0), "Sunrise", None),
            TideReading(datetime(2026, 10, 29, 12, 0), "High", 5.8),
            TideReading(datetime(2026, 10, 30, 6, 30), "Sunrise", None),
            TideReading(datetime(2026, 10, 30, 12, 0), "High", 6.1),
            TideReading(datetime(2026, 10, 31, 6, 45), "Sunrise", None),
            TideReading(datetime(2026, 10, 31, 12, 5), "High", 6.4),
            TideReading(datetime(2026, 11, 1, 7, 0), "Sunrise", None),
            TideReading(datetime(2026, 11, 1, 12, 10), "High", 6.8),
        ],
    )

    rows = _build_day_rows(model, now, days=2, start_offset=1)
    assert len(rows) == 2
    assert rows[0][0] == "10/30"
    assert rows[1][0] == "10/31"


def test_fetch_forecast_keeps_late_day_events_within_day_window(tmp_path):
    now = datetime(2026, 10, 29, 12, 0)
    xtide_path = tmp_path / "xtide"
    xtide_path.write_text("#!/bin/sh\ntrue\n")
    output = "\n".join(
        [
            "2026-10-29 12:30 PM High Tide 7.2",
            "2026-10-30 06:20 AM Sunrise",
            "2026-10-30 05:30 PM Sunset",
            "2026-10-30 08:00 PM High Tide 8.4",
            "2026-10-31 07:15 AM Low Tide 1.1",
            "2026-10-31 06:40 PM Sunset",
            "2026-11-01 01:10 AM Low Tide 0.8",
        ]
    )

    import app.xtide as xtide_module

    original_now = xtide_module.datetime
    xtide_module.datetime = type("FixedDateTime", (datetime,), {"now": staticmethod(lambda: now)})
    try:
        import subprocess

        def fake_run(*args, **kwargs):
            return subprocess.CompletedProcess(args[0], 0, stdout=output, stderr="")

        original_run = xtide_module.subprocess.run
        xtide_module.subprocess.run = fake_run
        try:
            forecast = xtide_module.fetch_forecast(str(xtide_path), "Test Station", days=2)
        finally:
            xtide_module.subprocess.run = original_run
    finally:
        xtide_module.datetime = original_now

    dates = {event.timestamp.date() for event in forecast.events}
    assert max(dates) == datetime(2026, 10, 31).date()
    assert min(dates) == datetime(2026, 10, 29).date()
    assert any(event.event_type == "Sunset" for event in forecast.events)


def test_tide_angle_does_not_snap_to_low_before_low_time_when_previous_extrema_missing():
    now = datetime(2026, 10, 29, 13, 0)
    model = TideModel(
        station="Test Station",
        readings=[
            TideReading(datetime(2026, 10, 29, 14, 36), "Low", -2.6),
            TideReading(datetime(2026, 10, 29, 19, 2), "High", 9.8),
        ],
    )

    angle = _resolve_tide_angle(model, now)
    assert angle is not None
    assert 0.0 < angle < (math.pi / 2)
