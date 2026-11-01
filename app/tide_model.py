from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List


@dataclass
class TideReading:
    timestamp: datetime
    event_type: str
    level: float | None = None
    level_unit: str | None = None
    raw: str = ""


@dataclass
class TideModel:
    station: str
    readings: List[TideReading] = field(default_factory=list)
    updated_at: datetime = field(default_factory=lambda: datetime.now())

    def next_high_low(self, at_time: datetime | None = None) -> TideReading | None:
        now = at_time or datetime.now()
        future = [r for r in self.readings if r.timestamp >= now]
        return future[0] if future else None

    def upcoming_events(self, count: int = 6, at_time: datetime | None = None) -> List[TideReading]:
        now = at_time or datetime.now()
        future = [r for r in self.readings if r.timestamp >= now]
        return future[:count]

    def current_state(self, at_time: datetime | None = None) -> str:
        now = at_time or datetime.now()
        if not self.readings:
            return "Unknown"
        prev = None
        nxt = None
        for reading in self.readings:
            if reading.timestamp <= now:
                prev = reading
            else:
                nxt = reading
                break
        if prev is None:
            return "Rising" if nxt and nxt.event_type == "High" else "Falling"
        if prev.event_type == "High" and nxt and nxt.event_type == "Low":
            return "Falling"
        if prev.event_type == "Low" and nxt and nxt.event_type == "High":
            return "Rising"
        return "Steady"

    def summary_for_day(self, day: datetime) -> list[TideReading]:
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        return [r for r in self.readings if day_start <= r.timestamp < day_end]
