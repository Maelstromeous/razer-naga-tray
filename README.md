# razer-naga-tray

A system tray battery monitor for the Razer Naga V2 Pro on Linux, built for KDE Plasma.

It talks to the mouse over raw HID, so it needs no OpenRazer kernel driver. That driver takes over the mouse's input devices, which can break key remapping tools such as input-remapper. This tool leaves them alone.

## What it does

- Shows the battery level in the tray as a small battery that fills as it charges: green while charging, blue once full, your panel's text colour on battery, red at 20% or below.
- Sends a notification at 20%, 10% and 5%, and when the mouse is fully charged, when the Mouse Dock Pro ring also blinks blue.
- Estimates the time to full while charging. Drain is logged but not estimated, since it depends on how the mouse is used and when it sleeps.
- Updates the moment the mouse is placed on or lifted off the Mouse Dock Pro, falls asleep or wakes, using the dock's own reports, and the moment a cable, dongle or dock is plugged in or removed. With nothing plugged in at all it shows a question mark.
- Closes any low battery warning as soon as the mouse starts charging.
- Lights the Mouse Dock Pro's ring in its onboard profile, a colour cycle, by charge level (red through orange and yellow to green, blue once the mouse reaches 95% on any charger), or in any colour of your own, previewed live as you choose it, at a brightness you pick.
- Mouse lighting from the tray menu, with the same choices as the ring. Brightness settings show only while the tray is setting a light. The tray puts your choice back after the mouse wakes, since the mouse falls back to its own effect when it sleeps.
- Both lights start on Onboard profile, which shows whatever lighting is saved on the mouse and dock and then leaves them alone, so installing the tray changes nothing until you pick something else. The tray only ever changes the live lighting, never what is saved on the device.
- Sets the mouse's idle sleep timer from the tray menu.
- Keeps a battery history in `~/.local/state/razer-naga-tray/battery.csv`, so you can see how fast it drains.

The mouse's battery gauge moves in whole percents, ticking about once a minute on the cable. While charging the tray checks every 10 seconds to time those ticks. Batteries charge and drain on a curve rather than a straight line, so the tray learns how long each percent takes at each level, separately for the cable, the dock and normal use, from its own history. Estimates follow that curve, adjusted to how the current session compares. The first charge relies on the live rate and runs optimistic near the top; each full charge after that sharpens it.

It works through the Mouse Dock Pro, the HyperSpeed wireless dongle or a USB cable, whichever the mouse answers on.

## Requirements

Python 3 with PyQt6, `notify-send` (libnotify) and `gdbus`. With pyudev installed, plugging is noticed instantly; without it, within 30 seconds.

## Install

On Arch, build the package from this repository (it goes on the AUR as `razer-naga-tray` once new AUR accounts open again):

```sh
git clone https://github.com/Maelstromeous/razer-naga-tray.git
cd razer-naga-tray/packaging/aur
makepkg -si
```

The package installs the udev rule and starts the tray at login. By hand instead:

```sh
./install.sh
sudo install -m644 70-razer-naga.rules /etc/udev/rules.d/
sudo udevadm control --reload && sudo udevadm trigger --subsystem-match=hidraw
```

`install.sh` links `razer-naga-tray` and `razer-naga-power` into `~/.local/bin` and starts the tray at login. The udev rule lets the logged-in user open the mouse, dongle and dock without root.

## Command line

```sh
razer-naga-power                 # battery, charging, sleep timer, polling rate, lighting
razer-naga-power --lights-off    # switch the lighting off and save it to the mouse
razer-naga-power --lights-on     # colour cycling at 33% brightness
razer-naga-power --idle 120      # sleep after 2 minutes idle (60 to 900 seconds)
```

## Troubleshooting

Start it with `RAZER_NAGA_TRAY_DEBUG=1 razer-naga-tray` to log every report from the dock and every reading, with timestamps, to the terminal. Include that log with any bug report, which you can file from the tray menu's Report a bug item.

## Credits

The report format and command bytes come from [OpenRazer](https://github.com/openrazer/openrazer).
