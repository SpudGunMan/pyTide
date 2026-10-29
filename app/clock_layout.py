from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ClockLayout:
    center_x: float
    center_y: float
    radius: float

    @staticmethod
    def from_surface(surface) -> "ClockLayout":
        width, height = surface.get_size()
        radius = min(width, height) * 0.35
        return ClockLayout(center_x=width / 2, center_y=height / 2, radius=radius)

    def tick_position(self, angle_radians: float, distance: float) -> tuple[float, float]:
        return (
            self.center_x + __import__("math").cos(angle_radians) * distance,
            self.center_y + __import__("math").sin(angle_radians) * distance,
        )
