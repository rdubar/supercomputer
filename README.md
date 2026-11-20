# supercomputer

Retro mainframe front panel for the Pi5 media server. Python 3 standard
library only; read-only (reads `/proc`, `/sys`, `findmnt`, `systemctl is-active`).

- `supercomputer` — full-screen curses operator console. Lamp density follows
  real per-core CPU, per-disk I/O and network load. Keys: `c` colour, `q` quit.
- `supercomputer --banner` — short static banner, shown on interactive SSH
  logins via a guarded block in `~/.bashrc`.
- `supercomputer-wallpaper [OUT.png] [W H]` — renders the 1920x1080 front-panel
  wallpaper (needs Pillow) used on the WayVNC desktop
  (`~/.config/pcmanfm/LXDE-pi/desktop-items-NOOP-1.conf`).

`~/bin/supercomputer` and `~/bin/supercomputer-wallpaper` are thin wrappers
that exec the scripts here.
