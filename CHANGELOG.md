# Changelog

All notable changes to this project. Versions follow
[Semantic Versioning](https://semver.org/). The version lives in one place:
`__version__` in `supercomputer.py`.

## [Unreleased]

## [1.3.1] - 2026-11-21

- `--update` recognises a Homebrew install and runs
  `brew upgrade rdubar/tap/supercomputer` rather than pip.

## [1.3.0] - 2026-11-21

- `--update`: upgrades the way it was installed (`uv tool`, `pipx`, pip in a
  virtualenv, or `git pull --ff-only` in a clone).
- `--version` also checks PyPI for a newer release. It prints the version
  first, gives up after 1.5 seconds, and is skipped with
  `SUPERCOMPUTER_NO_UPDATE_CHECK=1`.
- Packaging for PyPI as `supercomputer-console` (the `supercomputer` name is
  taken on PyPI). The command is still `supercomputer`.
- Release plan (`ROADMAP.md`) and release steps (`RELEASING.md`).

## [1.2.0] - 2026-11-21

- `--demo`: simulated load that cycles through every alarm, for showing off.

## [1.1.0] - 2026-11-21

- Strain alarms: load, memory (macOS pressure level), swap and paging,
  sustained CPU, temperature, Raspberry Pi under-voltage and throttling,
  full disks, stopped services.
- Alarm line under the header; log entries when alarms raise and clear.
- `--check` with exit codes, plus `--notify`, `--quiet` and `--bell`.
- Login banner shows current alarms.
- Version shown in the console footer, banner and check output.

## [1.0.0] - 2026-11-20

- First public release: operator console with CPU, memory, storage,
  network, subsystem, active-job and operator-log panels.
- Linux and macOS backends, standard library only, Python 3.9+.
- Help and credits cards, remembered phosphor colour, freeze key.
- `--banner` for SSH logins; `supercomputer-wallpaper` generator.
