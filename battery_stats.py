"""Charge and drain estimates from the battery history.

The gauge moves in whole percents and batteries do not charge or drain at a constant rate,
so the history is turned into a curve: seconds per percent at each level band, per source
(cable, dock, in use). An estimate walks the remaining levels along that curve, scaled by
how this session compares, and falls back to the live rate where the curve has no data yet.
"""
import statistics
import time

BAND = 5  # percent per curve band
MAX_TICK = {"cable": 15 * 60, "dock": 30 * 60, "use": 6 * 3600}  # longer gaps are downtime, not a tick
RECENT_TICKS = 6  # the live rate is read from this many recent ticks
MIN_TICKS = 3


def source_of(link, charging):
    if not charging:
        return "use"
    return "cable" if link == "USB cable" else "dock"


def pct(raw):
    return round(raw * 100 / 255)


def duration(hours):
    if hours >= 5:
        return f"{round(hours)} h"
    minutes = round(hours * 60 / 5) * 5 or 5
    if minutes < 60:
        return f"{minutes} min"
    h, m = divmod(minutes, 60)
    return f"{h} h {m} min" if m else f"{h} h"


class Session:
    """Ticks since the source last changed, plus the curve learned from every past session."""

    def __init__(self):
        self.source = None
        self.ticks = []  # (unix time, percent) at each change of level; the first is the session start
        self.curve = {}  # source -> band -> [seconds per percent, ...]

    def add(self, t, raw, link, charging):
        source, level = source_of(link, charging), pct(raw)
        if source != self.source:
            self.source, self.ticks = source, [(t, level)]
            return
        if level == self.ticks[-1][1]:
            return
        # The session's first point is when it began, not a tick, so the first interval is partial.
        if len(self.ticks) > 1:
            (t0, p0) = self.ticks[-1]
            steps = abs(level - p0)
            if 0 < t - t0 <= MAX_TICK[source] and steps <= 2:
                band = min(p0, level) // BAND
                self.curve.setdefault(source, {}).setdefault(band, []).append((t - t0) / steps)
        self.ticks.append((t, level))

    def load(self, path):
        """Rebuild the curve and the current session from the history file."""
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
            self.add(t, int(row[4]), row[3], row[2] == "1")

    def live_seconds_per_percent(self):
        ticks = self.ticks[1:][-RECENT_TICKS:]
        if len(ticks) < MIN_TICKS:
            return None
        span = ticks[-1][0] - ticks[0][0]
        steps = abs(ticks[-1][1] - ticks[0][1])
        return span / steps if steps else None

    def curve_at(self, level):
        samples = self.curve.get(self.source, {}).get(level // BAND)
        return statistics.median(samples) if samples else None

    def remaining_hours(self, level):
        """Hours to full (charging) or to empty (in use), and the live %/h. None until there is data."""
        charging = self.source != "use"
        live = self.live_seconds_per_percent()
        here = self.curve_at(level)
        # This session against the curve at the same level: a warm or worn battery runs off the curve.
        scale = max(0.7, min(1.4, live / here)) if live and here else 1.0
        levels = range(level, 100) if charging else range(level - 1, -1, -1)
        total = 0.0
        for p in levels:
            per = self.curve_at(p)
            if per is None:
                per = live or here
                if per is None:
                    return None, None
                total += per
            else:
                total += per * scale
        return total / 3600, (3600 / live if live else None)

    def summary(self, level):
        """One line for the tooltip and menu, or None when there is nothing to say."""
        if self.source is None or (self.source != "use" and level >= 100):
            return None
        hours, live_rate = self.remaining_hours(level)
        if hours is None:
            return "ETA: Calculating"
        if live_rate:
            sign = "+" if self.source != "use" else "-"
            rate = f" ({sign}{live_rate:.1f}%/h now)" if live_rate < 10 else f" ({sign}{live_rate:.0f}%/h now)"
        else:
            rate = ", from past charges" if self.source != "use" else ", from past use"
        if self.source == "use":
            return f"About {duration(hours)} left" + rate
        return f"Full in about {duration(hours)}" + rate
