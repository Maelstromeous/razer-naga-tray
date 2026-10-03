---
name: swap-in-new-builds
description: after building a new tray feature, stop the packaged tray and run the repo build so it can be used straight away
metadata:
  type: feedback
  volatility: durable
  lastVerified: 2026-10-04
---

When a change to the tray is built and tested, swap it in on this machine without being asked:
stop the packaged tray and run the repo build in its place.

```sh
systemctl --user stop 'app-razer\x2dnaga\x2dtray@autostart.service'
systemd-run --user --unit=razer-naga-tray-dev --slice=app.slice -p Restart=on-failure ~/code/razer-naga-tray/razer-naga-tray
```

If `razer-naga-tray-dev` is already running from an earlier swap, `systemctl --user restart razer-naga-tray-dev`
picks up the new code. Confirm it with `systemctl --user is-active razer-naga-tray-dev`.

**Why:** the running tray comes from the AUR package (`/usr/bin`), so a change in the repo does nothing
until it is swapped in, and I want to use a new feature as soon as it exists.

**How to apply:** the swap lasts until logout; the next login starts the packaged tray again. Say so,
and say that a package release makes it stick.
