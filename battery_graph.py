"""A minute-by-minute battery timeline, and a window that graphs it.

battery.csv only logs changes, for the ETA curve. The timeline logs a sample every minute
whatever happens, so sleep, unplugging and time on the dock show up as well as the level.
"""
import os
import time
from datetime import datetime, timedelta

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPalette, QPen
from PyQt6.QtWidgets import QButtonGroup, QHBoxLayout, QLabel, QPushButton, QToolTip, QVBoxLayout, QWidget

TIMELINE = os.path.expanduser("~/.local/state/razer-naga-tray/timeline.csv")
KEEP_DAYS = 7
SAMPLE_SECONDS = 60
RANGES = {"24 hours": (24 * 3600, 15 * 60), "7 days": (7 * 86400, 2 * 3600)}  # span, bar width

# Strip states, in legend order.
STATES = {
    "dock": ("Charging on dock", QColor("#46a758")),
    "cable": ("Charging by cable", QColor("#2f9e8f")),
    "battery": ("On battery", QColor("#3b82f6")),
    "asleep": ("Asleep", QColor("#8a8a8a")),
    "away": ("Not connected", QColor("#f5a524")),
}
CHARGING = QColor("#46a758")
LOW = QColor("#e5484d")
LOW_AT = 20


def strip_state(state, charging, link):
    if state == "ok":
        if charging:
            return "cable" if link == "USB cable" else "dock"
        return "battery"
    return {"asleep": "asleep", "no-receiver": "away"}.get(state)


def record(state, level, charging, link, path=TIMELINE):
    """One sample: time, strip state, level (blank if never read), charging, link."""
    kind = strip_state(state, charging, link)
    if kind is None:
        return
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a") as f:
            f.write(f"{int(time.time())},{kind},{'' if level is None else level},{int(bool(charging))},{link or ''}\n")
    except OSError:
        pass


def prune(path=TIMELINE, days=KEEP_DAYS):
    cutoff = time.time() - days * 86400
    try:
        with open(path) as f:
            lines = f.readlines()
    except OSError:
        return
    kept = [line for line in lines if line.split(",", 1)[0].isdigit() and int(line.split(",", 1)[0]) >= cutoff]
    if len(kept) == len(lines):
        return
    try:
        with open(path + ".tmp", "w") as f:
            f.writelines(kept)
        os.replace(path + ".tmp", path)
    except OSError:
        pass


def load(since, path=TIMELINE):
    """[(unix time, state, level or None)] from `since` on, oldest first."""
    rows = []
    try:
        with open(path) as f:
            for line in f:
                parts = line.rstrip("\n").split(",")
                if len(parts) < 3 or not parts[0].isdigit() or parts[1] not in STATES:
                    continue
                t = int(parts[0])
                if t >= since:
                    rows.append((t, parts[1], int(parts[2]) if parts[2].isdigit() else None))
    except OSError:
        pass
    return rows


class Chart(QWidget):
    """Level as bars, Apple style, with a state strip under the time axis."""

    PAD_L, PAD_R, PAD_T = 16, 48, 14
    STRIP_GAP, STRIP_H, AXIS_H = 8, 12, 22

    def __init__(self):
        super().__init__()
        self.span, self.bar = RANGES["24 hours"]
        self.rows = []
        self.bars = []  # (start, end, level, charging, low)
        self.setMouseTracking(True)
        self.setMinimumSize(560, 260)

    def set_range(self, name):
        self.span, self.bar = RANGES[name]
        self.reload()

    def reload(self):
        now = time.time()
        # Bars end on a whole bar boundary in local time, so 15-minute bars sit on :00, :15, :30 and :45.
        offset = datetime.now().astimezone().utcoffset().total_seconds()
        self.end = (now + offset) // self.bar * self.bar + self.bar - offset
        self.start = self.end - self.span
        self.now = now
        self.rows = load(self.start - SAMPLE_SECONDS * 2)
        self.bars = []
        i = 0
        for k in range(int(self.span // self.bar)):
            a, b = self.start + k * self.bar, self.start + (k + 1) * self.bar
            inside = []
            while i < len(self.rows) and self.rows[i][0] < b:
                if self.rows[i][0] >= a:
                    inside.append(self.rows[i])
                i += 1
            levels = [r[2] for r in inside if r[2] is not None]
            if levels:
                # The bar shows where the level ended, like the phone's graph does.
                charging = sum(r[1] in ("dock", "cable") for r in inside) * 2 >= len(inside)
                self.bars.append((a, b, levels[-1], charging, levels[-1] <= LOW_AT))
        self.update()

    def plot(self):
        h = self.height() - self.PAD_T - self.STRIP_GAP - self.STRIP_H - self.AXIS_H
        return QRectF(self.PAD_L, self.PAD_T, self.width() - self.PAD_L - self.PAD_R, max(40, h))

    def x_of(self, t, plot):
        return plot.left() + (t - self.start) / self.span * plot.width()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = self.palette()
        text = pal.color(QPalette.ColorRole.WindowText)
        faint = QColor(text)
        faint.setAlpha(45)
        soft = QColor(text)
        soft.setAlpha(150)
        plot = self.plot()
        small = QFont(self.font())
        small.setPointSizeF(max(7.5, small.pointSizeF() * 0.85))
        p.setFont(small)

        # Gridlines at 0, 50 and 100%, labelled on the right.
        for level in (0, 50, 100):
            y = plot.bottom() - plot.height() * level / 100
            pen = QPen(faint, 1, Qt.PenStyle.SolidLine if level == 0 else Qt.PenStyle.DashLine)
            p.setPen(pen)
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            p.setPen(soft)
            p.drawText(QRectF(plot.right() + 6, y - 9, self.PAD_R - 6, 18),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"{level}%")

        # Day boundaries, so a week reads as days.
        if self.span > 86400:
            day = datetime.fromtimestamp(self.start).replace(hour=0, minute=0, second=0, microsecond=0)
            while day.timestamp() < self.end:
                if day.timestamp() > self.start:
                    x = self.x_of(day.timestamp(), plot)
                    p.setPen(QPen(faint, 1))
                    p.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom() + self.STRIP_GAP + self.STRIP_H))
                day += timedelta(days=1)

        slot = plot.width() * self.bar / self.span
        width = max(1.5, slot * 0.72)
        p.setPen(Qt.PenStyle.NoPen)
        for a, _, level, charging, low in self.bars:
            x = self.x_of(a, plot) + (slot - width) / 2
            hgt = max(1.5, plot.height() * level / 100)
            path = QPainterPath()
            r = min(2.5, width / 2)
            path.addRoundedRect(QRectF(x, plot.bottom() - hgt, width, hgt + r), r, r)
            p.save()
            p.setClipRect(QRectF(x, plot.top(), width, plot.height()))
            p.setBrush(LOW if low else CHARGING if charging else STATES["battery"][1])
            p.drawPath(path)
            p.restore()

        # State strip: each sample covers the minute after it, or up to the next one.
        strip = QRectF(plot.left(), plot.bottom() + self.STRIP_GAP, plot.width(), self.STRIP_H)
        track = QPainterPath()
        track.addRoundedRect(strip, 3, 3)
        p.setClipPath(track)
        p.fillRect(strip, faint)
        for n, (t, state, _) in enumerate(self.rows):
            nxt = self.rows[n + 1][0] if n + 1 < len(self.rows) else self.now
            t2 = min(nxt, t + SAMPLE_SECONDS * 1.5)
            x1, x2 = self.x_of(max(t, self.start), plot), self.x_of(min(t2, self.end), plot)
            if x2 > x1:
                p.fillRect(QRectF(x1, strip.top(), x2 - x1 + 0.6, strip.height()), STATES[state][1])
        p.setClipping(False)

        # Time axis.
        p.setPen(soft)
        axis_y = strip.bottom() + 4
        if self.span <= 86400:
            first = datetime.fromtimestamp(self.start).replace(minute=0, second=0, microsecond=0)
            first += timedelta(hours=(3 - first.hour % 3) % 3)
            tick, step, fmt = first, timedelta(hours=3), "%H:%M"
        else:
            tick = datetime.fromtimestamp(self.start).replace(hour=12, minute=0, second=0, microsecond=0)
            step, fmt = timedelta(days=1), "%a %d"
        while tick.timestamp() <= self.end:
            if tick.timestamp() >= self.start:
                x = self.x_of(tick.timestamp(), plot)
                p.drawText(QRectF(x - 40, axis_y, 80, self.AXIS_H - 4), Qt.AlignmentFlag.AlignHCenter, tick.strftime(fmt))
            tick += step

        if not self.bars:
            p.setPen(soft)
            p.drawText(plot, Qt.AlignmentFlag.AlignCenter, "No readings yet. The tray records one every minute.")
        p.end()

    def mouseMoveEvent(self, event):
        plot = self.plot()
        x = event.position().x()
        if not plot.left() <= x <= plot.right():
            QToolTip.hideText()
            return
        t = self.start + (x - plot.left()) / plot.width() * self.span
        bar = next((b for b in self.bars if b[0] <= t < b[1]), None)
        sample = next((r for r in reversed(self.rows) if r[0] <= t), None)
        if bar is None and (sample is None or t - sample[0] > SAMPLE_SECONDS * 1.5):
            QToolTip.hideText()
            return
        fmt = "%H:%M" if self.span <= 86400 else "%a %H:%M"
        lines = []
        if bar:
            a, b = (datetime.fromtimestamp(v).strftime(fmt) for v in bar[:2])
            lines.append(f"{bar[2]}% at {b}" if self.span <= 86400 else f"{bar[2]}%, {a} to {b}")
        if sample and t - sample[0] <= SAMPLE_SECONDS * 1.5:
            lines.append(f"{datetime.fromtimestamp(sample[0]).strftime(fmt)}: {STATES[sample[1]][0]}")
        QToolTip.showText(event.globalPosition().toPoint(), "\n".join(lines), self)

    def leaveEvent(self, _):
        QToolTip.hideText()


class GraphWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mouse battery")
        self.resize(760, 380)
        self.chart = Chart()

        title = QLabel("Battery level")
        font = title.font()
        font.setPointSizeF(font.pointSizeF() * 1.25)
        font.setWeight(QFont.Weight.DemiBold)
        title.setFont(font)

        # A segmented control: two checkable buttons that read as one.
        self.buttons = QButtonGroup(self)
        segments = QHBoxLayout()
        segments.setSpacing(0)
        for name in RANGES:
            button = QPushButton(f"Last {name}", checkable=True)
            button.setChecked(name == "24 hours")
            button.clicked.connect(lambda _, name=name: self.chart.set_range(name))
            self.buttons.addButton(button)
            segments.addWidget(button)

        header = QHBoxLayout()
        header.addWidget(title)
        header.addStretch()
        header.addLayout(segments)

        legend = QHBoxLayout()
        legend.setSpacing(14)
        for label, colour in STATES.values():
            dot = QLabel()
            dot.setFixedSize(10, 10)
            dot.setStyleSheet(f"background: {colour.name()}; border-radius: 3px;")
            row = QHBoxLayout()
            row.setSpacing(5)
            row.addWidget(dot)
            row.addWidget(QLabel(label))
            legend.addLayout(row)
        legend.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.addLayout(header)
        layout.addWidget(self.chart, 1)
        layout.addLayout(legend)

        self.timer = QTimer(self, interval=SAMPLE_SECONDS * 1000, timeout=self.chart.reload)

    def showEvent(self, event):
        self.chart.reload()
        self.timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)
