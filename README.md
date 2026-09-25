# razer-tray

A system tray battery monitor for the Razer Naga V2 Pro on Linux, built for KDE Plasma.

It talks to the mouse over raw HID, so it needs no OpenRazer kernel driver. That driver takes over the mouse's input devices, which can break key remapping tools such as input-remapper. This tool leaves them alone.

## What it does

- Shows the battery level in the tray, coloured by level, and blue while charging.
- Sends a notification at 20%, 10% and 5%, and when the mouse is fully charged.
- Updates the moment the mouse is placed on or lifted off the Mouse Dock Pro, using the dock's own reports.
- Turns the mouse lighting off and sets the idle sleep timer from the tray menu.
- Keeps a battery history in `~/.local/state/razer-tray/battery.csv`, so you can see how fast it drains.

It works through the Mouse Dock Pro, the HyperSpeed wireless dongle or a USB cable, whichever the mouse answers on.

## Requirements

Python 3 with PyQt6, and `notify-send` (libnotify).

## Install

```sh
./install.sh
sudo install -m644 70-razer-naga.rules /etc/udev/rules.d/
sudo udevadm control --reload && sudo udevadm trigger --subsystem-match=hidraw
```

`install.sh` links `razer-tray` and `razer-naga-power` into `~/.local/bin` and starts the tray at login. The udev rule lets the logged-in user open the mouse, dongle and dock without root.

## Command line

```sh
razer-naga-power                 # battery, charging, sleep timer, polling rate, lighting
razer-naga-power --lights-off    # switch the lighting off and save it to the mouse
razer-naga-power --idle 120      # sleep after 2 minutes idle (60 to 900 seconds)
```

## Credits

The report format and command bytes come from [OpenRazer](https://github.com/openrazer/openrazer).
