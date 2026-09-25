"""Charge and drain rate from the battery history, for "full in" and "time left" estimates.

Works on the raw 0-255 reading, where one step is ~0.4%. A single step is too coarse and the
reading jumps when a charger connects, so the rate is a least-squares fit over a window.
"""
import os
import time

RAW_FULL = 255
CHARGE_SETTLE = 3 * 60  # the reading jumps for a few minutes after a charger connects
CHARGE_WINDOW, CHARGE_MIN_SPAN = 20 * 60, 5 * 60
DRAIN_WINDOW, DRAIN_MIN_SPAN = 3 * 3600, 30 * 60
MIN_STEPS = 3


def slope_per_hour(points):
    n = len(points)
    mean_t = sum(t for t, _ in points) / n
    mean_r = sum(r for _, r in points) / n
    var = sum((t - mean_t) ** 2 for t, _ in points)
    if var == 0:
        return None
    return sum((t - mean_t) * (r - mean_r) for t, r in points) / var * 3600


def duration(hours):
    if hours >= 5:
        return f"{round(hours)} h"
    minutes = round(hours * 60 / 5) * 5 or 5
    if minutes < 60:
        return f"{minutes} min"
    h, m = divmod(minutes, 60)
    return f"{h} h {m} min" if m else f"{h} h"


class Session:
    """Readings since the charging state last flipped: (unix time, raw) at each raw change."""

    def __init__(self):
        self.charging = None
        self.started = None
        self.points = []

    def add(self, t, raw, charging):
        if charging != self.charging:
            self.charging, self.started, self.points = charging, t, [(t, raw)]
        elif raw != self.points[-1][1]:
            self.points.append((t, raw))

    def load(self, path):
        """Resume from the history file, so a restart keeps the rate it had measured."""
        try:
            with open(path) as f:
                rows = [line.strip().split(",") for line in f]
        except OSError:
            return
        for row in rows:
            if len(row) < 5 or not row[4].isdigit():
                continue
            try:
                t = time.mktime(time.strptime(row[0], "%Y-%m-%dT%H:%M:%S"))
            except ValueError:
                continue
            self.add(t, int(row[4]), row[2] == "1")

    def rate(self, now):
        """Raw steps per hour, or None until there is enough history to trust it."""
        if self.charging:
            since, min_span = max(self.started + CHARGE_SETTLE, now - CHARGE_WINDOW), CHARGE_MIN_SPAN
        else:
            since, min_span = max(self.started, now - DRAIN_WINDOW), DRAIN_MIN_SPAN
        points = [(t, r) for t, r in self.points if t >= since]
        if len(points) < MIN_STEPS or points[-1][0] - points[0][0] < min_span:
            return None
        if abs(points[-1][1] - points[0][1]) < MIN_STEPS:
            return None
        return slope_per_hour(points)

    def summary(self, now, raw):
        """One tooltip line, or None when there is nothing to say yet."""
        if self.charging is None:
            return None
        rate = self.rate(now)
        if self.charging:
            if raw >= RAW_FULL:
                return None
            if not rate or rate <= 0:
                return "ETA: Calculating"
            return f"Full in about {duration((RAW_FULL - raw) / rate)} (+{rate * 100 / RAW_FULL:.0f}%/h)"
        if not rate or rate >= 0:
            return "ETA: Calculating"
        return f"About {duration(raw / -rate)} left (-{-rate * 100 / RAW_FULL:.1f}%/h)"
