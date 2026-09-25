#!/usr/bin/env bash
# Links the tools into ~/.local/bin and starts the tray at login. The udev rule needs root, so it is printed, not run.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"

mkdir -p ~/.local/bin ~/.local/share/applications ~/.config/autostart
ln -sf "$here/razer-naga-tray" ~/.local/bin/razer-naga-tray
ln -sf "$here/razer-naga-power" ~/.local/bin/razer-naga-power
# Autostart may not have ~/.local/bin on PATH, so the launcher gets the full path.
for dest in ~/.local/share/applications ~/.config/autostart; do
    sed "s|@BIN@|$HOME/.local/bin|" "$here/razer-naga-tray.desktop" > "$dest/razer-naga-tray.desktop"
done

if [ ! -f /etc/udev/rules.d/70-razer-naga.rules ]; then
    echo "Install the udev rule so the tray can read the mouse without root:"
    echo "  sudo install -m644 '$here/70-razer-naga.rules' /etc/udev/rules.d/ && sudo udevadm control --reload && sudo udevadm trigger --subsystem-match=hidraw"
fi
