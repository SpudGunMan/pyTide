from __future__ import annotations

import math
from datetime import datetime, timedelta
from pathlib import Path

try:
    import pygame
except ImportError:  # pragma: no cover - runtime dependency is optional in tests
    pygame = None


_BACKGROUND_CACHE: dict[tuple[str, int, int], pygame.Surface] = {}


def init_display(width: int, height: int, fullscreen: bool = False):
    if pygame is None:
        raise RuntimeError("pygame-ce is required to render the clock")

    pygame.init()
    pygame.display.set_caption("pyTide Tide Clock")
    if fullscreen:
        info = pygame.display.Info()
        screen = pygame.display.set_mode((info.current_w, info.current_h), pygame.FULLSCREEN)
    else:
        screen = pygame.display.set_mode((width, height))
    return screen


def _make_label(font_name: str, size: int, text: str, color: tuple[int, int, int]) -> pygame.Surface:
    font = pygame.font.SysFont(font_name, size)
    return font.render(text, True, color)


def _draw_text_block(surface, x: int, y: int, title: str, value: str, color: tuple[int, int, int], title_size: int = 12, value_size: int = 18) -> None:
    title_surface = _make_label("DejaVu Sans", title_size, title.upper(), (25, 55, 120))
    value_surface = _make_label("DejaVu Sans", value_size, value, color)
    surface.blit(title_surface, (x, y))
    surface.blit(value_surface, (x, y + title_surface.get_height() + 4))


def _format_level(value) -> str:
    return "--" if value is None else f"{float(value):.1f}"


def _future_readings(readings, now: datetime):
    if not readings:
        return []
    return [reading for reading in sorted(readings, key=lambda event: event.timestamp) if reading.timestamp >= now]


def _event_display_name(event_type: str) -> str:
    name = (event_type or "").strip().upper()
    mapping = {
        "HIGH": "HIGH",
        "LOW": "LOW",
        "SUNRISE": "SUNRISE",
        "SUNSET": "SUNSET",
        "MOONRISE": "MOON RISE",
        "MOONSET": "MOON SET",
    }
    return mapping.get(name, name.replace("_", " ").replace("-", " "))


def _get_forecast_cards(forecast, now: datetime, days: int = 3):
    days = max(1, int(days))
    fallback_labels = ["TODAY", "TOMORROW", "WEDNESDAY", "THURSDAY", "FRIDAY"]
    fallback_cards = [
        (fallback_labels[idx] if idx < len(fallback_labels) else f"DAY {idx + 1}", "HIGH: --\nLOW: --")
        for idx in range(days)
    ]

    if not forecast or not getattr(forecast, "readings", None):
        return fallback_cards

    future = _future_readings(forecast.readings, now)
    if not future:
        return fallback_cards

    cards = []
    current_day = now.date()
    for day_offset in range(days):
        day = current_day + timedelta(days=day_offset)
        day_events = [r for r in future if r.timestamp.date() == day]
        high = next((r for r in day_events if r.event_type.lower() == "high"), None)
        low = next((r for r in day_events if r.event_type.lower() == "low"), None)
        label = day.strftime("%A").upper()
        cards.append((label, f"HIGH: {_format_level(high.level) if high else '--'}\nLOW: {_format_level(low.level) if low else '--'}"))
    return cards


def _get_right_panel_events(forecast, now: datetime):
    if not forecast or not getattr(forecast, "readings", None):
        return [
            ("HIGH", "12:20 AM"),
            ("LOW", "06:30 AM"),
            ("HIGH", "12:35 PM"),
            ("LOW", "07:23 PM"),
        ]

    future = _future_readings(forecast.readings, now)[:8]
    rows = []
    for reading in future:
        if len(rows) >= 4:
            break
        rows.append((_event_display_name(reading.event_type), reading.timestamp.strftime("%I:%M %p")))
    if len(rows) < 4:
        while len(rows) < 4:
            rows.append(("HIGH", "--:--"))
    return rows


def _wrap_station_lines(station: str | None, max_chars: int = 20) -> list[str]:
    text = (station or "LOCAL STATION").strip()
    if not text:
        return ["LOCAL STATION"]
    if len(text) <= max_chars:
        return [text]

    pieces = [part.strip() for part in text.split(",") if part.strip()]
    if not pieces:
        return [text[:max_chars]]

    lines: list[str] = []
    current = ""
    for piece in pieces:
        candidate = f"{current}, {piece}" if current else piece
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = piece
    if current:
        lines.append(current)
    return lines or [text[:max_chars]]


def _wrap_text_lines(text: str, max_chars: int = 32) -> list[str]:
    if not text:
        return [""]
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}" if current else word
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text[:max_chars]]


def _format_lat_lon(latitude, longitude) -> str:
    if latitude is None or longitude is None:
        return "LAT/LON: --"
    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError):
        return "LAT/LON: --"
    return f"LAT/LON: {lat:.4f}, {lon:.4f}"


def _fit_text_width(text: str, font, max_width: int) -> str:
    if max_width <= 0:
        return ""
    if font.size(text)[0] <= max_width:
        return text
    ellipsis = "..."
    if font.size(ellipsis)[0] > max_width:
        return ""
    trimmed = text
    while trimmed and font.size(trimmed + ellipsis)[0] > max_width:
        trimmed = trimmed[:-1]
    return (trimmed + ellipsis) if trimmed else ellipsis


def _sorted_tide_events(forecast):
    if not forecast or not getattr(forecast, "readings", None):
        return []
    return [
        reading for reading in sorted(forecast.readings, key=lambda event: event.timestamp)
        if _tide_kind(reading.event_type) is not None
    ]


def _current_tide_transition(forecast, now: datetime):
    tide_events = _sorted_tide_events(forecast)
    if not tide_events:
        return None

    previous = None
    upcoming = None
    for event in tide_events:
        if event.timestamp <= now:
            previous = event
        else:
            upcoming = event
            break

    if upcoming is None:
        return None

    next_kind = _tide_kind(upcoming.event_type)
    if next_kind is None:
        return None

    if previous is not None and _tide_kind(previous.event_type) == "high" and next_kind == "low":
        trend = "EBB"
    elif previous is not None and _tide_kind(previous.event_type) == "low" and next_kind == "high":
        trend = "FLOOD"
    else:
        trend = "FLOOD" if next_kind == "high" else "EBB"

    seconds_to_next = max(0, int((upcoming.timestamp - now).total_seconds()))
    return {
        "trend": trend,
        "next_kind": next_kind,
        "seconds_to_next": seconds_to_next,
    }


def _format_countdown(total_seconds: int) -> str:
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return f"{hours:02d}:{minutes:02d}"


def _draw_tide_countdown_scale(surface, center: tuple[int, int], radius: float, color: tuple[int, int, int]) -> None:
    number_radius = radius * 0.73
    font = pygame.font.SysFont("DejaVu Sans", 22, bold=True)

    # Skip endpoint labels so 6/0 anchors are implied by HIGH/LOW and do not clutter the dial.
    for idx in range(1, 6):
        value = str(6 - idx)

        # Left side: LOW -> HIGH (rising)
        angle_left = (math.pi / 2) + (idx / 6) * math.pi
        x_left = center[0] + math.cos(angle_left) * number_radius
        y_left = center[1] + math.sin(angle_left) * number_radius
        left_surface = font.render(value, True, color)
        left_rect = left_surface.get_rect(center=(x_left, y_left))
        surface.blit(left_surface, left_rect)

        # Right side: HIGH -> LOW (falling)
        angle_right = (-math.pi / 2) + (idx / 6) * math.pi
        x_right = center[0] + math.cos(angle_right) * number_radius
        y_right = center[1] + math.sin(angle_right) * number_radius
        right_surface = font.render(value, True, color)
        right_rect = right_surface.get_rect(center=(x_right, y_right))
        surface.blit(right_surface, right_rect)


def _build_day_rows(forecast, now: datetime, days: int = 2, start_offset: int = 1):
    if not forecast or not getattr(forecast, "readings", None):
        return [
            ("11/27", "06:55 AM", "--:--", "01:55 AM", "08:05 AM", "04:38 PM", "--:--"),
            ("11/28", "06:56 AM", "--:--", "02:53 AM", "09:09 AM", "04:37 PM", "--:--"),
        ]

    future = _future_readings(forecast.readings, now)
    grouped: dict[datetime.date, dict[str, list]] = {}
    for reading in future:
        day = reading.timestamp.date()
        bucket = grouped.setdefault(day, {"Sunrise": None, "Sunset": None, "Moonrise": None, "Moonset": None, "High": [], "Low": []})
        event_name = (reading.event_type or "").lower().replace(" ", "")
        if event_name == "sunrise":
            bucket["Sunrise"] = reading
        elif event_name == "sunset":
            bucket["Sunset"] = reading
        elif event_name == "moonrise":
            bucket["Moonrise"] = reading
        elif event_name == "moonset":
            bucket["Moonset"] = reading
        elif event_name == "high":
            bucket["High"].append(reading)
        elif event_name == "low":
            bucket["Low"].append(reading)

    rows = []
    date_cursor = now.date() + timedelta(days=start_offset)
    for _ in range(days):
        bucket = grouped.get(date_cursor, {"Sunrise": None, "Sunset": None, "Moonrise": None, "Moonset": None, "High": [], "Low": []})
        high_events = sorted(bucket["High"], key=lambda event: event.timestamp)
        low_events = sorted(bucket["Low"], key=lambda event: event.timestamp)
        sunrise = bucket["Sunrise"].timestamp if bucket["Sunrise"] else None
        moonrise = bucket["Moonrise"].timestamp if bucket["Moonrise"] else None
        sunset = bucket["Sunset"].timestamp if bucket["Sunset"] else None
        moonset = bucket["Moonset"].timestamp if bucket["Moonset"] else None
        row = (
            date_cursor.strftime("%m/%d"),
            sunrise.strftime("%I:%M %p") if sunrise else "--:--",
            moonrise.strftime("%I:%M %p") if moonrise else "--:--",
            high_events[0].timestamp.strftime("%I:%M %p") if len(high_events) > 0 else "--:--",
            low_events[0].timestamp.strftime("%I:%M %p") if len(low_events) > 0 else "--:--",
            sunset.strftime("%I:%M %p") if sunset else "--:--",
            moonset.strftime("%I:%M %p") if moonset else "--:--",
        )
        rows.append(row)
        date_cursor += timedelta(days=1)
    return rows


def _theme_palette(config):
    theme = (getattr(config, "theme", "light") or "light").strip().lower()
    if theme == "dark":
        return {
            "background": (22, 30, 38),
            "shade_rgb": (10, 16, 24),
            "shade_alpha": 130,
            "panel": (24, 38, 52),
            "rail": (18, 28, 40),
            "card": (38, 62, 86),
            "card_value": (186, 220, 255),
            "clock_outer": (18, 24, 30),
            "clock_face": (44, 54, 66),
            "clock_ring": (78, 94, 110),
            "tick": (118, 134, 150),
            "muted_text": (205, 219, 234),
            "value_text": (232, 241, 247),
            "table_bg": (26, 38, 50),
            "footer_label": (128, 190, 244),
            "center_cap": (18, 25, 33),
            "center_dot": (225, 231, 237),
        }

    return {
        "background": getattr(config, "bg_color", (222, 232, 241)),
        "shade_rgb": (16, 30, 48),
        "shade_alpha": 78,
        "panel": (255, 255, 255),
        "rail": (230, 240, 245),
        "card": (200, 220, 240),
        "card_value": (18, 90, 180),
        "clock_outer": (45, 45, 45),
        "clock_face": (240, 240, 240),
        "clock_ring": (40, 40, 40),
        "tick": (30, 30, 30),
        "muted_text": (30, 30, 30),
        "value_text": (30, 30, 30),
        "table_bg": (238, 244, 248),
        "footer_label": (20, 60, 110),
        "center_cap": (25, 25, 25),
        "center_dot": (255, 255, 255),
    }


def _resolve_background_path(image_path: str | None) -> Path | None:
    if not image_path:
        return None
    candidate = Path(image_path)
    if candidate.exists():
        return candidate

    root = Path(__file__).resolve().parent.parent
    joined = (root / image_path).resolve()
    if joined.exists():
        return joined

    variants = []
    if str(joined).lower().endswith(".jpg"):
        variants.append(Path(str(joined)[:-4] + ".jpeg"))
    elif str(joined).lower().endswith(".jpeg"):
        variants.append(Path(str(joined)[:-5] + ".jpg"))
    for variant in variants:
        if variant.exists():
            return variant
    return None


def _get_background_surface(image_path: str | None, width: int, height: int):
    if pygame is None:
        return None
    resolved = _resolve_background_path(image_path)
    if resolved is None:
        return None
    cache_key = (str(resolved), width, height)
    cached = _BACKGROUND_CACHE.get(cache_key)
    if cached is not None:
        return cached
    try:
        loaded = pygame.image.load(str(resolved)).convert()
        scaled = pygame.transform.smoothscale(loaded, (width, height))
    except Exception:
        return None
    _BACKGROUND_CACHE[cache_key] = scaled
    return scaled


def _draw_alpha_rect(surface, rect: pygame.Rect, color: tuple[int, int, int], alpha: int, border_radius: int = 0) -> None:
    alpha = max(0, min(255, int(alpha)))
    layer = pygame.Surface((max(1, int(rect.width)), max(1, int(rect.height))), pygame.SRCALPHA)
    pygame.draw.rect(layer, (*color, alpha), layer.get_rect(), border_radius=border_radius)
    surface.blit(layer, rect.topleft)


def _draw_alpha_circle(surface, color: tuple[int, int, int], center: tuple[int, int], radius: int, alpha: int, width: int = 0) -> None:
    alpha = max(0, min(255, int(alpha)))
    diameter = max(2, int(radius * 2 + 4))
    layer = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
    local_center = (diameter // 2, diameter // 2)
    pygame.draw.circle(layer, (*color, alpha), local_center, int(radius), width)
    surface.blit(layer, (int(center[0] - diameter / 2), int(center[1] - diameter / 2)))


def _draw_glass_clock_face(
    surface,
    background,
    center: tuple[int, int],
    radius: int,
    tint_color: tuple[int, int, int],
    tint_alpha: int,
) -> None:
    diameter = max(2, int(radius * 2 + 4))
    face = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
    top_left = (int(center[0] - diameter / 2), int(center[1] - diameter / 2))

    # Use the actual background image under the clock so the face is visibly transparent.
    if background is not None:
        src = pygame.Rect(top_left[0], top_left[1], diameter, diameter)
        face.blit(background, (0, 0), src)
    else:
        face.fill((*tint_color, 255))

    tint_alpha = max(0, min(255, int(tint_alpha)))
    if tint_alpha > 0:
        tint = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        tint.fill((*tint_color, tint_alpha))
        face.blit(tint, (0, 0))

    mask = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), (diameter // 2, diameter // 2), int(radius))
    face.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surface.blit(face, top_left)


def _tide_kind(event_type: str) -> str | None:
    name = (event_type or "").strip().lower()
    if name == "high":
        return "high"
    if name == "low":
        return "low"
    return None


def _anchor_angle_for_tide(kind: str) -> float:
    return -math.pi / 2 if kind == "high" else math.pi / 2


def _find_next_opposite(tide_events, start_index: int, kind: str):
    for idx in range(start_index + 1, len(tide_events)):
        candidate_kind = _tide_kind(tide_events[idx].event_type)
        if candidate_kind and candidate_kind != kind:
            return tide_events[idx]
    return None


def _find_prev_opposite(tide_events, start_index: int, kind: str):
    for idx in range(start_index - 1, -1, -1):
        candidate_kind = _tide_kind(tide_events[idx].event_type)
        if candidate_kind and candidate_kind != kind:
            return tide_events[idx]
    return None


def _resolve_tide_angle(forecast, now: datetime) -> float | None:
    if not forecast or not getattr(forecast, "readings", None):
        return None

    tide_events = [
        reading for reading in sorted(forecast.readings, key=lambda event: event.timestamp)
        if _tide_kind(reading.event_type) is not None
    ]
    if not tide_events:
        return None

    previous = None
    previous_idx = -1
    upcoming = None
    upcoming_idx = -1
    for idx, event in enumerate(tide_events):
        if event.timestamp <= now:
            previous = event
            previous_idx = idx
            continue
        upcoming = event
        upcoming_idx = idx
        break

    if previous is None and upcoming is None:
        return None

    if previous is None and upcoming is not None:
        next_kind = _tide_kind(upcoming.event_type)
        if next_kind is None:
            return None
        next_opposite = _find_next_opposite(tide_events, upcoming_idx, next_kind)
        if next_opposite is not None:
            cycle = max(60.0, (next_opposite.timestamp - upcoming.timestamp).total_seconds())
            synthetic_kind = "high" if next_kind == "low" else "low"
            synthetic_previous_time = upcoming.timestamp - timedelta(seconds=cycle)
            previous = type("SyntheticTideEvent", (), {"timestamp": synthetic_previous_time, "event_type": synthetic_kind})
        else:
            return _anchor_angle_for_tide(next_kind)

    if upcoming is None and previous is not None:
        prev_kind = _tide_kind(previous.event_type)
        if prev_kind is None:
            return None
        prev_opposite = _find_prev_opposite(tide_events, previous_idx, prev_kind)
        if prev_opposite is not None:
            cycle = max(60.0, (previous.timestamp - prev_opposite.timestamp).total_seconds())
            synthetic_kind = "high" if prev_kind == "low" else "low"
            synthetic_upcoming_time = previous.timestamp + timedelta(seconds=cycle)
            upcoming = type("SyntheticTideEvent", (), {"timestamp": synthetic_upcoming_time, "event_type": synthetic_kind})
        else:
            return _anchor_angle_for_tide(prev_kind)

    prev_kind = _tide_kind(previous.event_type)
    next_kind = _tide_kind(upcoming.event_type)
    if prev_kind is None:
        return _anchor_angle_for_tide(next_kind or "high")
    if next_kind is None:
        return _anchor_angle_for_tide(prev_kind)
    if prev_kind == next_kind:
        return _anchor_angle_for_tide(prev_kind)

    span_seconds = max(1.0, (upcoming.timestamp - previous.timestamp).total_seconds())
    elapsed = max(0.0, min(span_seconds, (now - previous.timestamp).total_seconds()))
    progress = elapsed / span_seconds

    if prev_kind == "high":
        start = -math.pi / 2
        end = math.pi / 2
    else:
        start = math.pi / 2
        end = 3 * math.pi / 2
    return start + progress * (end - start)


def draw_clock(surface, config, now: datetime | None = None, station: str | None = None, forecast=None, weather=None) -> None:
    if pygame is None:
        return

    now = now or datetime.now()
    width, height = surface.get_size()
    is_low_res = width <= 1280 or height <= 720
    forecast_days = 2 if is_low_res else 3
    theme_name = (getattr(config, "theme", "light") or "light").strip().lower()
    palette = _theme_palette(config)

    background = _get_background_surface(getattr(config, "background_image", None), width, height)
    if background is not None:
        surface.blit(background, (0, 0))
    else:
        surface.fill(palette["background"])

    overlay_alpha = int(getattr(config, "background_overlay_alpha", palette["shade_alpha"]))
    overlay_alpha = max(0, min(255, overlay_alpha))
    overlay = pygame.Surface((width, height), pygame.SRCALPHA)
    overlay.fill((*palette["shade_rgb"], overlay_alpha))
    surface.blit(overlay, (0, 0))

    radius = min(width, height) * 0.33

    panel_width = width * 0.27
    panel_x = width * 0.04
    panel_y = height * 0.06
    rail_x = width * 0.72
    rail_w = width * 0.24
    panel_alpha = int(getattr(config, "panel_alpha", 188))
    card_alpha = int(getattr(config, "card_alpha", 188))
    rail_alpha = int(getattr(config, "rail_alpha", 212))
    table_alpha = int(getattr(config, "table_alpha", 210))
    clock_face_alpha = int(getattr(config, "clock_face_alpha", 140))
    if theme_name == "dark":
        # Dark mode needs a denser tint so bright backgrounds do not wash out the dial.
        clock_face_alpha = max(clock_face_alpha, 210)

    panel = pygame.Rect(panel_x, panel_y, panel_width, height * 0.74)
    _draw_alpha_rect(surface, panel, palette["panel"], panel_alpha, border_radius=16)
    _draw_alpha_rect(surface, pygame.Rect(rail_x, 0, rail_w, height), palette["rail"], rail_alpha, border_radius=0)

    left_title_font = pygame.font.SysFont("DejaVu Sans", 28, bold=True)
    left_title = left_title_font.render("TIDE FORECAST", True, config.accent_color)
    left_title_rect = left_title.get_rect(centerx=panel.centerx, y=int(panel_y + 12))
    surface.blit(left_title, left_title_rect)

    forecast_cards = _get_forecast_cards(forecast, now, days=forecast_days)
    forecast_items = [(name, details, palette["card_value"]) for name, details in forecast_cards]

    for idx, (name, details, color) in enumerate(forecast_items):
        block_y = panel_y + 90 + idx * 150
        _draw_alpha_rect(surface, pygame.Rect(panel_x + 18, block_y, panel_width - 36, 120), palette["card"], card_alpha, border_radius=10)
        title = _make_label("DejaVu Sans", 28, name, config.accent_color)
        surface.blit(title, (panel_x + 26, block_y + 12))
        value_lines = details.split("\n")
        line_y = block_y + 54
        for line in value_lines:
            value = _make_label("DejaVu Sans", 30, line, color)
            surface.blit(value, (panel_x + 26, line_y))
            line_y += 34

    clock_box = pygame.Rect(width * 0.28, height * 0.12, width * 0.42, height * 0.7)
    clock_center = (clock_box.centerx, clock_box.centery)

    pygame.draw.circle(surface, palette["clock_outer"], clock_center, int(radius + 30), 0)
    _draw_glass_clock_face(
        surface,
        background,
        clock_center,
        int(radius + 6),
        palette["clock_face"],
        clock_face_alpha,
    )
    pygame.draw.circle(surface, palette["clock_ring"], clock_center, int(radius + 28), 6)
    for tick in range(60):
        angle = tick / 60 * (2 * math.pi) - math.pi / 2
        inner_len = radius * 0.83 if tick % 5 == 0 else radius * 0.88
        outer_len = radius * 0.96
        x1 = clock_center[0] + math.cos(angle) * inner_len
        y1 = clock_center[1] + math.sin(angle) * inner_len
        x2 = clock_center[0] + math.cos(angle) * outer_len
        y2 = clock_center[1] + math.sin(angle) * outer_len
        pygame.draw.line(surface, palette["tick"], (x1, y1), (x2, y2), 2 if tick % 5 == 0 else 1)

    _draw_tide_countdown_scale(surface, clock_center, radius, config.accent_color)

    hour = now.hour % 12
    minute = now.minute
    second = now.second
    hour_angle = (hour + minute / 60 + second / 3600) * (2 * math.pi / 12) - math.pi / 2
    minute_angle = (minute + second / 60) * (2 * math.pi / 60) - math.pi / 2
    second_angle = second * (2 * math.pi / 60) - math.pi / 2

    tide_angle = _resolve_tide_angle(forecast, now)
    if tide_angle is None:
        tide_angle = minute_angle + (math.pi / 12)

    hand_from = clock_center

    minute_end_x = clock_center[0] + math.cos(minute_angle) * radius * 0.68
    minute_end_y = clock_center[1] + math.sin(minute_angle) * radius * 0.68
    pygame.draw.line(surface, palette["tick"], hand_from, (minute_end_x, minute_end_y), 5)

    hour_end_x = clock_center[0] + math.cos(hour_angle) * radius * 0.48
    hour_end_y = clock_center[1] + math.sin(hour_angle) * radius * 0.48
    pygame.draw.line(surface, palette["clock_ring"], hand_from, (hour_end_x, hour_end_y), 3)

    second_end_x = clock_center[0] + math.cos(second_angle) * radius * 0.76
    second_end_y = clock_center[1] + math.sin(second_angle) * radius * 0.76
    pygame.draw.line(surface, (200, 90, 70), hand_from, (second_end_x, second_end_y), 2)

    tide_end_x = clock_center[0] + math.cos(tide_angle) * radius * 0.76
    tide_end_y = clock_center[1] + math.sin(tide_angle) * radius * 0.76
    pygame.draw.line(surface, config.accent_color, hand_from, (tide_end_x, tide_end_y), 16)

    pygame.draw.circle(surface, palette["center_cap"], clock_center, 14)
    pygame.draw.circle(surface, palette["center_dot"], clock_center, 6)

    for value, angle in [("12", -math.pi / 2), ("3", 0), ("6", math.pi / 2), ("9", math.pi)]:
        x = clock_center[0] + math.cos(angle) * (radius * 0.86)
        y = clock_center[1] + math.sin(angle) * (radius * 0.86)
        label = _make_label("DejaVu Sans", 28, value, config.accent_color)
        label_rect = label.get_rect(center=(x, y))
        surface.blit(label, label_rect)

    # Keep core tide anchors with static rising/falling side labels.
    phase_labels = [
        ("HIGH", -math.pi / 2, radius * 0.62, 18),
        ("LOW", math.pi / 2, radius * 0.62, 18),
        ("RISING TIDE", math.pi, radius * 0.48, 12),
        ("FALLING TIDE", 0.0, radius * 0.48, 12),
    ]
    for label_text, angle, dist, size in phase_labels:
        x = clock_center[0] + math.cos(angle) * dist
        y = clock_center[1] + math.sin(angle) * dist
        label = _make_label("DejaVu Sans", size, label_text, config.accent_color)
        rect = label.get_rect(center=(x, y))
        surface.blit(label, rect)

    transition = _current_tide_transition(forecast, now)
    if transition is not None:
        trend_text = transition["trend"]
        next_text = f"TO {transition['next_kind'].upper()}: {_format_countdown(transition['seconds_to_next'])}"
        trend_surface = _make_label("DejaVu Sans", 16, trend_text, config.accent_color)
        next_surface = _make_label("DejaVu Sans", 14, next_text, palette["value_text"])
        trend_rect = trend_surface.get_rect(center=(clock_center[0], clock_center[1] + radius * 0.22))
        next_rect = next_surface.get_rect(center=(clock_center[0], clock_center[1] + radius * 0.31))
        surface.blit(trend_surface, trend_rect)
        surface.blit(next_surface, next_rect)

    right_panel = pygame.Rect(int(rail_x), 0, int(rail_w), height)
    content_left = right_panel.left + 24
    content_right = right_panel.right - 24
    content_center_x = (content_left + content_right) // 2

    right_y = 16
    title_font_size = 24 if is_low_res else 28
    title_font = pygame.font.SysFont("DejaVu Sans", title_font_size, bold=True)
    title = title_font.render("TIDE PREDICTIONS", True, config.accent_color)
    title_rect = title.get_rect(centerx=content_center_x, y=right_y)
    surface.blit(title, title_rect)

    date_text = now.strftime("%a, %b %d")
    date_surface = _make_label("DejaVu Sans", 22, date_text.upper(), config.accent_color)
    date_rect = date_surface.get_rect(centerx=content_center_x, y=title_rect.bottom + 10)
    surface.blit(date_surface, date_rect)

    station_lines = _wrap_station_lines(station or "LOCAL STATION", max_chars=22)
    station_y = date_rect.bottom + 18
    for line in station_lines[:2]:
        station_surface = _make_label("DejaVu Sans", 18, line.upper(), palette["muted_text"])
        station_rect = station_surface.get_rect(centerx=content_center_x, y=station_y)
        surface.blit(station_surface, station_rect)
        station_y += 24

    entries = _get_right_panel_events(forecast, now)
    row_y = station_y + 16
    row_step = 42
    for idx, (label, time_value) in enumerate(entries):
        label_surface = _make_label("DejaVu Sans", 20, label.upper(), config.accent_color)
        value_surface = _make_label("DejaVu Sans", 20, time_value, palette["value_text"])
        current_y = row_y + idx * row_step
        surface.blit(label_surface, (content_left, current_y))
        value_rect = value_surface.get_rect(topright=(content_right, current_y))
        surface.blit(value_surface, value_rect)

    if weather is not None:
        weather_y = row_y + len(entries) * row_step + 18
        weather_label = _make_label("DejaVu Sans", 18, "WEATHER", config.accent_color)
        surface.blit(weather_label, (content_left, weather_y))

        temp_label = _make_label("DejaVu Sans", 20, weather.temperature_label, palette["value_text"])
        temp_rect = temp_label.get_rect(topright=(content_right, weather_y))
        surface.blit(temp_label, temp_rect)

        now_lines = _wrap_text_lines(weather.today_summary or f"Now: {weather.short_forecast}", max_chars=20)
        next_lines = _wrap_text_lines(weather.tomorrow_summary or "Next: --", max_chars=20)

        line_height = 16
        line_start = weather_y + 30
        for index, line in enumerate(now_lines[:2]):
            surf = _make_label("DejaVu Sans", 15, line, palette["value_text"])
            surface.blit(surf, (content_left, line_start + index * line_height))

        next_block_start = line_start + min(len(now_lines[:2]), 2) * line_height + 10
        for index, line in enumerate(next_lines[:2]):
            surf = _make_label("DejaVu Sans", 15, line, palette["value_text"])
            surface.blit(surf, (content_left, next_block_start + index * line_height))

        wind_y = next_block_start + min(len(next_lines[:2]), 2) * line_height + 8
        wind_label = _make_label("DejaVu Sans", 15, f"Wind: {weather.wind_speed}", palette["value_text"])
        surface.blit(wind_label, (content_left, wind_y))

    bottom = pygame.Rect(0, height - 120, int(rail_x), 120)
    _draw_alpha_rect(surface, bottom, palette["table_bg"], table_alpha)
    table_cols = ["DATE", "SUNRISE", "MOON RISE", "HIGH", "LOW", "SUNSET", "MOON SET"]
    x = 40
    for col in table_cols:
        cell = _make_label("DejaVu Sans", 14, col, config.accent_color)
        surface.blit(cell, (x, height - 100))
        x += 120

    day_rows = _build_day_rows(forecast, now, days=2, start_offset=1)
    row_y = height - 70
    for day_row in day_rows:
        x = 40
        for cell_value in day_row:
            cell = _make_label("DejaVu Sans", 12, cell_value, palette["value_text"])
            surface.blit(cell, (x, row_y))
            x += 120
        row_y += 18

    footer_y = height - 20
    footer_text_y = footer_y - 12
    footer_label = _make_label("DejaVu Sans", 12, "LOCATION:", palette["footer_label"])
    surface.blit(footer_label, (40, footer_text_y))
    location_x = 210

    lat_lon_text = _format_lat_lon(getattr(config, "latitude", None), getattr(config, "longitude", None))
    lat_lon_surface = _make_label("DejaVu Sans", 12, lat_lon_text, palette["value_text"])
    lat_lon_rect = lat_lon_surface.get_rect(topright=(int(rail_x) - 20, footer_text_y))
    surface.blit(lat_lon_surface, lat_lon_rect)

    station_font = pygame.font.SysFont("DejaVu Sans", 12)
    station_text = (station or "LOCAL STATION").strip() or "LOCAL STATION"
    max_station_width = max(0, lat_lon_rect.left - 14 - location_x)
    station_text = _fit_text_width(station_text, station_font, max_station_width)
    location_surface = station_font.render(station_text, True, palette["value_text"])
    surface.blit(location_surface, (location_x, footer_text_y))

    pygame.display.flip()


def render_stub(surface, config, now: datetime | None = None, station: str | None = None, forecast=None, weather=None) -> None:
    draw_clock(surface, config, now=now, station=station, forecast=forecast, weather=weather)
