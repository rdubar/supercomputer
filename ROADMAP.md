# Roadmap

Where supercomputer is heading, roughly in order. Nothing here is a
promise. It's a plan that gets updated as the project grows.

## Principles

These hold for every release:

- **Read-only.** It watches and never changes anything on the machine.
- **Unprivileged.** No root, no setuid, no kernel modules.
- **Light.** It must never be the thing that strains the machine.
- **No runtime dependencies** beyond what the OS ships (Python 1.x), or a
  single static binary (Go 2.x).
- **The look is the point.** New features have to stay in character: lamps,
  tape drives, teletype and operator language.

## 1.x: Python, easy to install

Status: in progress.

- [x] Linux and macOS backends, standard library only
- [x] Strain alarms, `--check`, `--notify`, `--demo`
- [x] `--update`, and `--version` checks for a newer release
- [x] **Publish to PyPI** as `supercomputer-console` (`supercomputer` is taken),
      so `pipx install supercomputer-console` or
      `uv tool install supercomputer-console` works anywhere
- [ ] **Homebrew tap** (`rdubar/homebrew-tap`), so
      `brew install rdubar/tap/supercomputer` works with no Python setup
- [x] Tag releases on GitHub, with notes taken from `CHANGELOG.md`
- [ ] Small polish: re-announce an alarm when it goes from warning to
      critical; show the version in the footer even on narrow terminals

## 2.0: Go rewrite, single binary

Status: planned. It starts when 1.x is stable, or when the iOS work needs
it.

Why: the Python version needs a Python interpreter. On a Mac without
Apple's developer tools, typing `python3` brings up an install prompt rather
than running anything. A Go build is one file per platform, cross-compiled
from one machine.

- Same look, keys, alarms and command-line options. 2.0 should feel identical.
- GoReleaser builds macOS (arm64, amd64) and Linux (arm64, amd64) binaries
  for every tag, updates the Homebrew tap automatically, and attaches `.deb`
  and `.rpm` packages to GitHub releases.
- The Python 1.x line keeps getting fixes until 2.0 matches it feature for
  feature.

## 3.0: pocket console (iOS)

Status: idea.

iOS doesn't let apps watch other apps, so an iPhone version of the
console would be limited to the phone's own CPU, memory and heat. The
better idea is a **remote console**:

- `supercomputer --serve`: a small read-only JSON endpoint, meant to be
  reached over a private network such as Tailscale, never the open internet.
- A SwiftUI app that draws the same front panel for one or more machines,
  with a home-screen widget showing the alarm line.
- **Push notifications for alarms.** This finally gives headless servers,
  like the Raspberry Pi that started this project, a way to reach someone.
  See "Why background checks run only on the Mac" in the README.

Open questions: whether push goes through a small relay service or the
phone polls; authentication (Tailscale identity is a strong candidate);
whether `--serve` belongs in the Python or the Go version (probably Go,
since it's a long-running service).

## Not planned

- **An official Debian/Ubuntu package or apt repository.** `.deb` files on
  GitHub releases (2.0) cover this without the upkeep.
- **Getting into Homebrew's main catalogue.** It requires a popular
  project. Our own tap does the job until then.
- **Windows support.** Possible in 2.0 through Go, but not a goal.
- **Being a full monitor.** Use `htop`, `btop` or Glances for that.
  supercomputer is ambience with useful warnings.
