"""Charge and drain rate from the battery history, for "full in" and "time left" estimates.

The mouse's gauge moves in whole percents (2-3 raw steps of 255), ticking about once a minute
on the cable. So the rate comes from the times of those ticks, and the tray polls fast while
charging to time them closely. Rates are kept per source (cable, dock, in use) and remembered,
so the next session has an estimate before its own ticks arrive.
"""
import json
import os
import time

RAW_FULL = 255
WINDOW = {"cable": 20 * 60, "dock": 20 * 60, "use": 3 * 3600}
MIN_INTERVALS = 2  # three ticks
LEARN_AFTER = 5  # intervals before a session's rate is worth remembering


def source_of(link, charging):
    if not charging:
        return "use"
    return "cable" if link == "USB cable" else "dock"


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
    """Ticks since the charging source last changed: (unix time, raw) at each change of level."""

    def __init__(self, learned_path=None):
        self.source = None
        self.points = []
        self.learned_path = learned_path
        self.learned = {}
        if learned_path:
            try:
                with open(learned_path) as f:
                    self.learned = json.load(f)
            except (OSError, ValueError):
                pass

    def add(self, t, raw, link, charging, learn=True):
        source = source_of(link, charging)
        if source != self.source:
            self.source, self.points = source, [(t, raw)]
        elif raw != self.points[-1][1]:
            self.points.append((t, raw))
            if learn:
                self._learn(t)

    def load(self, path):
        """Resume from the history file, so a restart keeps the ticks it had seen."""
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
            self.add(t, int(row[4]), row[3], row[2] == "1", learn=False)

    def measured(self, now):
        """Raw steps per hour from this session's own ticks, and how many intervals it rests on."""
        # The first point is where the session began, not a tick, so its time says nothing.
        ticks = [(t, r) for t, r in self.points[1:] if t >= now - WINDOW[self.source]]
        if len(ticks) < MIN_INTERVALS + 1:
            return None, 0
        return slope_per_hour(ticks), len(ticks) - 1

    def _learn(self, now):
        rate, intervals = self.measured(now)
        if rate and intervals >= LEARN_AFTER and self.learned_path:
            self.learned[self.source] = rate
            try:
                os.makedirs(os.path.dirname(self.learned_path), exist_ok=True)
                with open(self.learned_path, "w") as f:
                    json.dump(self.learned, f)
            except OSError:
                pass

    def summary(self, now, raw):
        """One line for the tooltip and menu, or None when there is nothing to say."""
        if self.source is None or (self.source != "use" and raw >= RAW_FULL):
            return None
        rate, _ = self.measured(now)
        guess = rate is None
        if guess:
            rate = self.learned.get(self.source)
        if self.source == "use":
            if not rate or rate >= 0:
                return "ETA: Calculating"
            text = f"About {duration(raw / -rate)} left (-{-rate * 100 / RAW_FULL:.1f}%/h)"
        else:
            if not rate or rate <= 0:
                return "ETA: Calculating"
            text = f"Full in about {duration((RAW_FULL - raw) / rate)} (+{rate * 100 / RAW_FULL:.0f}%/h)"
        return text + (", from last time" if guess else "")
