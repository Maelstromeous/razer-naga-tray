"""Talk to a Razer Naga V2 Pro over raw HID, without the OpenRazer kernel driver.

Protocol bytes are from openrazer/driver (razerchromacommon.c, razermouse_driver.c).
The Mouse Dock Pro relays commands to the mouse just like the dongle does.
"""
import fcntl
import glob
import os
import time

VERSION = "1.0.0"
VENDOR = "00001532"
# Probe order: dock first, it is the usual link here.
LINKS = {"000000A4": "Mouse Dock Pro", "000000A8": "wireless dongle", "000000A7": "USB cable"}
TRANSACTION_ID = 0x1F
NOSTORE, VARSTORE = 0x00, 0x01  # live state, and the copy saved on the mouse
# The ids this mouse answers to through the dock; OpenRazer's scroll/side ids (0x01, 0x10, 0x11) fail.
LEDS = {"logo": 0x04, "backlight": 0x05}
EFFECT_NONE, EFFECT_STATIC, EFFECT_SPECTRUM = 0x00, 0x01, 0x03
ON_BRIGHTNESS = 84  # 33%, what the mouse shipped with here
POLL_RATES = {0x01: 1000, 0x02: 500, 0x08: 125}
STATUS = {0x01: "busy", 0x02: "ok", 0x03: "failed", 0x04: "timed out", 0x05: "not supported"}
REPORT_LEN = 90
# Unprompted input reports on the receiver's interface 1, seen on the dock:
# 05 0c <1|0> the instant the mouse lands on or leaves it, 05 3b ~2.5 s later (charging link),
# 05 09 <02|03> as the mouse falls asleep or wakes.
EVENT_INTERFACE = ":1.1"
EVENT_REPORT_ID = 0x05
DOCK_EVENTS = (0x09, 0x0C, 0x3B)


def _iowr(nr, size):
    return (3 << 30) | (size << 16) | (ord("H") << 8) | nr


HIDIOCSFEATURE = _iowr(0x06, REPORT_LEN + 1)
HIDIOCGFEATURE = _iowr(0x07, REPORT_LEN + 1)


class RazerError(Exception):
    pass


class NoReceiver(RazerError):
    pass


class NoPermission(RazerError):
    pass


class MouseAsleep(RazerError):
    """No answer through any receiver: asleep, switched off, or out of range."""


def pct(raw):
    return round(raw * 100 / 255)


def find_links(interface_suffix=":1.0"):
    ranked = []
    for node in glob.glob("/sys/class/hidraw/hidraw*"):
        try:
            with open(f"{node}/device/uevent") as f:
                hid_id = next((l.split("=")[1].strip() for l in f if l.startswith("HID_ID=")), "")
        except OSError:
            continue
        _, vendor, product = (hid_id.split(":") + ["", "", ""])[:3]
        interface = os.path.basename(os.path.dirname(os.path.realpath(f"{node}/device")))
        if vendor == VENDOR and product in LINKS and interface.endswith(interface_suffix):
            ranked.append((list(LINKS).index(product), f"/dev/{os.path.basename(node)}", LINKS[product]))
    return [(path, name) for _, path, name in sorted(ranked)]


class NagaV2Pro:
    def __init__(self):
        self.fd = None
        self.link = None

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
        self.fd = self.link = None

    def connect(self):
        """Attach to whichever receiver the mouse answers on."""
        self.close()
        links = find_links()
        if not links:
            raise NoReceiver("No dock, dongle or cable found.")
        denied = []
        for path, name in links:
            try:
                fd = os.open(path, os.O_RDWR)
            except PermissionError:
                denied.append(path)
                continue
            except OSError:
                continue
            try:
                status, _ = self._send(fd, 0x07, 0x80, 0x02)
            except OSError:
                status = None
            if status == 0x02:
                self.fd, self.link = fd, name
                return name
            os.close(fd)
        if denied:
            raise NoPermission(f"No access to {', '.join(denied)}; install the udev rule or use sudo.")
        raise MouseAsleep("The mouse did not answer on any receiver.")

    @staticmethod
    def _send(fd, command_class, command_id, data_size, args=(), transaction_id=TRANSACTION_ID):
        report = bytearray(REPORT_LEN)
        report[1] = transaction_id
        report[5], report[6], report[7] = data_size, command_class, command_id
        report[8:8 + len(args)] = bytes(args)
        crc = 0
        for b in report[2:88]:
            crc ^= b
        report[88] = crc
        fcntl.ioctl(fd, HIDIOCSFEATURE, bytes([0]) + report)

        # The receiver relays to the mouse over the air, so the reply lags.
        for _ in range(20):
            time.sleep(0.035)
            buf = bytearray(REPORT_LEN + 1)
            fcntl.ioctl(fd, HIDIOCGFEATURE, buf)
            if buf[1] != 0x01:
                return buf[1], bytes(buf[9:89])
        return 0x01, bytes(buf[9:89])

    def request(self, command_class, command_id, data_size, args=()):
        if self.fd is None:
            self.connect()
        try:
            status, data = self._send(self.fd, command_class, command_id, data_size, args)
        except OSError as e:
            self.close()
            raise NoReceiver(f"Receiver went away: {e}")
        # Still busy after the full wait is a link going down as the mouse falls asleep.
        if status in (0x01, 0x04):
            raise MouseAsleep("The mouse did not answer.")
        if status != 0x02:
            raise RazerError(STATUS.get(status, hex(status)))
        return data

    def battery_raw(self):
        """0-255; one step is ~0.4%, finer than the percentage."""
        return self.request(0x07, 0x80, 0x02)[1]

    def battery(self):
        return pct(self.battery_raw())

    def charging(self):
        return bool(self.request(0x07, 0x84, 0x02)[1])

    def idle_time(self):
        a = self.request(0x07, 0x83, 0x02)
        return (a[0] << 8) | a[1]

    def set_idle_time(self, seconds):
        seconds = max(60, min(900, seconds))
        self.request(0x07, 0x03, 0x02, (seconds >> 8, seconds & 0xFF))
        return seconds

    def low_battery_threshold(self):
        return pct(self.request(0x07, 0x81, 0x01)[0])

    def poll_rate(self):
        raw = self.request(0x00, 0x85, 0x01)[0]
        return POLL_RATES.get(raw, raw)

    def led_brightness(self, led):
        return pct(self.request(0x0F, 0x84, 0x03, (NOSTORE, led))[2])

    def lighting_on(self):
        return any(self.led_brightness(led) for led in LEDS.values())

    def set_led(self, effect, rgb=None, brightness=0, save=True):
        """One effect on every LED, live, and saved unless save is False, which leaves the onboard
        profile alone. Returns {led name: True if the mouse accepted it}."""
        if effect == EFFECT_STATIC:
            size, extra = 0x09, (0x00, 0x00, 0x01, *rgb)
        else:
            size, extra = 0x06, ()
        result = {}
        for name, led in LEDS.items():
            try:
                # Saving alone leaves the LED as it was until the next power cycle, so live is always set.
                for store in (NOSTORE, VARSTORE) if save else (NOSTORE,):
                    self.request(0x0F, 0x02, size, (store, led, effect, *extra))
                    self.request(0x0F, 0x04, 0x03, (store, led, brightness))
                result[name] = True
            except (MouseAsleep, NoReceiver):
                raise
            except RazerError:
                result[name] = False
        return result

    def restore_onboard(self):
        """Copy the saved (onboard profile) lighting onto the live lighting, so it shows straight away."""
        for led in LEDS.values():
            saved = self.request(0x0F, 0x82, 0x0C, (VARSTORE, led))
            brightness = self.request(0x0F, 0x84, 0x03, (VARSTORE, led))[2]
            self.request(0x0F, 0x02, 0x0C, (NOSTORE, led, *saved[2:12]))
            self.request(0x0F, 0x04, 0x03, (NOSTORE, led, brightness))

    def set_lighting(self, on):
        return self.set_led(EFFECT_SPECTRUM, brightness=ON_BRIGHTNESS) if on else self.set_led(EFFECT_NONE)


DOCK_TRANSACTION_ID = 0xFF  # 0x1F on the dock is relayed to the mouse; 0xFF is the dock itself
DOCK_LED = 0x00


def dock_command(command_class, command_id, data_size, args=()):
    """Send one command to the Mouse Dock Pro itself. Returns True if it was accepted."""
    return dock_request(command_class, command_id, data_size, args) is not None


def dock_request(command_class, command_id, data_size, args=()):
    """Send one command to the Mouse Dock Pro itself. Returns the reply's arguments, or None."""
    path = next((p for p, name in find_links() if name == "Mouse Dock Pro"), None)
    if not path:
        return None
    try:
        fd = os.open(path, os.O_RDWR)
    except OSError:
        return None
    try:
        status, data = NagaV2Pro._send(fd, command_class, command_id, data_size, args, DOCK_TRANSACTION_ID)
        return data if status == 0x02 else None
    except OSError:
        return None  # unplugged mid-write
    finally:
        os.close(fd)


def dock_set_colour(rgb, brightness=None):
    """Solid colour on the dock ring, live only. Sent twice: the dock can show the previous colour after one write."""
    ok = True
    if brightness is not None:
        ok &= dock_command(0x0F, 0x04, 0x03, (NOSTORE, DOCK_LED, brightness))
    for _ in range(2):
        ok &= dock_command(0x0F, 0x02, 0x09, (NOSTORE, DOCK_LED, 0x01, 0x00, 0x00, 0x01, *rgb))
    return ok


def dock_set_frame(rgb):
    """The whole ring one colour via a custom frame. Unlike the static effect, a frame shows at
    once every time, so it is what blinks."""
    return (dock_command(0x0F, 0x03, 5 + 24, [0, 0, 0, 0, 7] + list(rgb) * 8)
            and dock_command(0x0F, 0x02, 0x0C, (0x00, 0x00, 0x08)))


def dock_set_cycle(brightness):
    """The dock's own colour cycle, live only, sent twice like the static colour."""
    ok = dock_command(0x0F, 0x04, 0x03, (NOSTORE, DOCK_LED, brightness))
    for _ in range(2):
        ok &= dock_command(0x0F, 0x02, 0x06, (NOSTORE, DOCK_LED, EFFECT_SPECTRUM))
    return ok


def dock_restore_onboard():
    """Copy the dock's saved effect onto its live one. Its saved brightness reads back as 0 whatever it
    is, so the live brightness is left alone."""
    saved = dock_request(0x0F, 0x82, 0x0C, (VARSTORE, DOCK_LED))
    return saved is not None and dock_command(0x0F, 0x02, 0x0C, (NOSTORE, DOCK_LED, *saved[2:12]))
