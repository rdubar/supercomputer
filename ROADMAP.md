# Roadmap

Where supercomputer is heading, roughly in order. Nothing here is a
promise. It's a plan that gets updated as the project grows.

## Principles

These hold for every release:

- **Read-only.** It watches and never changes anything on the machine.
- **Unprivileged.** No root, no setuid, no kernel modules.
- **Light.** It must never be the thing that strains the machine.
- **No runtime dependencies** beyond Python's standard library. (A Go
  version, if it ever happens, would be a single static binary.)
- **The look is the point.** New features have to stay in character: lamps,
  tape drives, teletype and operator language.

## 1.x: Python, easy to install

Status: done, and maintained. This is the current version.

- [x] Linux and macOS backends, standard library only
- [x] Strain alarms, `--check`, `--notify`, `--demo`
- [x] `--update`, and `--version` checks for a newer release
- [x] **Publish to PyPI** as `supercomputer-console` (`supercomputer` is taken),
      so `pipx install supercomputer-console` or
      `uv tool install supercomputer-console` works anywhere
- [x] **Homebrew tap** (`rdubar/homebrew-tap`), so
      `brew install rdubar/tap/supercomputer` works with no Python setup
- [x] Tag releases on GitHub, with notes taken from `CHANGELOG.md`
- [x] Re-announce an alarm when it goes from warning to critical

## Parked: a Go version

Status: possible later, not planned.

A Go rewrite was the original 2.0 plan, so the console could be one file
per platform with no Python needed. Homebrew and PyPI have since solved
most of that: `brew install rdubar/tap/supercomputer` and
`uv tool install supercomputer-console` both work without setting up Python
first. What's left doesn't justify rewriting the system readings and the
curses front panel, and then keeping two versions in step.

It comes back if one of these happens:

- **The pocket console goes ahead.** `--serve` is a long-running network
  service, which suits Go. It would start as a small Go server on its own,
  with the console moving over only if that goes well.
- **Size or start-up time becomes a real complaint.** For example, the
  Homebrew install pulls in a full Python for a 100 KB program.

If it happens, the plan stays the same: same look, keys, alarms and options;
GoReleaser builds for macOS and Linux (arm64 and amd64), updating the
Homebrew tap and attaching `.deb` and `.rpm` files to releases; the Python
version keeps getting fixes until Go matches it.

## Later: pocket console (iOS)

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
whether `--serve` is written in Python or is where a Go version starts
(see above).

## Not planned

- **An official Debian/Ubuntu package or apt repository.** PyPI covers Linux
  today, and a Go version would attach `.deb` files to releases.
- **Getting into Homebrew's main catalogue.** It requires a popular
  project. Our own tap does the job until then.
- **Windows support.** Possible with a Go version, but not a goal.
- **Being a full monitor.** Use `htop`, `btop` or Glances for that.
  supercomputer is ambience with useful warnings.
