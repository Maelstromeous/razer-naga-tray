# razer-tray

A system tray battery monitor for the Razer Naga V2 Pro on Linux, built for KDE Plasma.

It talks to the mouse over raw HID, so it needs no OpenRazer kernel driver. That driver takes over the mouse's input devices, which can break key remapping tools such as input-remapper. This tool leaves them alone.

## What it does

- Shows the battery level in the tray, coloured by level, and blue while charging.
- Sends a notification at 20%, 10% and 5%, and when the mouse is fully charged.
- Estimates the time to full while charging, and the time left and drain rate per hour while in use.
- Updates the moment the mouse is placed on or lifted off the Mouse Dock Pro, using the dock's own reports, and the moment a cable, dongle or dock is plugged in or removed.
- Closes any low battery warning as soon as the mouse starts charging.
- Colours the Mouse Dock Pro's ring by charge level, from red through orange and yellow to green, at a brightness you pick.
- Switches the mouse lighting on or off and sets the idle sleep timer from the tray menu.
- Keeps a battery history in `~/.local/state/razer-tray/battery.csv`, so you can see how fast it drains.

The mouse's battery gauge moves in whole percents, ticking about once a minute on the cable. While charging the tray checks every 10 seconds to time those ticks, so an estimate appears after three of them, and it sharpens from there. Charge rates on the cable and the dock, and the drain rate in use, are remembered separately, so the next session shows an estimate straight away. Expect the time to full to run a little optimistic near the top, where the battery charges more slowly.

It works through the Mouse Dock Pro, the HyperSpeed wireless dongle or a USB cable, whichever the mouse answers on.

## Requirements

Python 3 with PyQt6, `notify-send` (libnotify) and `gdbus`. With pyudev installed, plugging is noticed instantly; without it, within 30 seconds.

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
razer-naga-power --lights-on     # colour cycling at 33% brightness
razer-naga-power --idle 120      # sleep after 2 minutes idle (60 to 900 seconds)
```

## Credits

The report format and command bytes come from [OpenRazer](https://github.com/openrazer/openrazer).
