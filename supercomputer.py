#!/usr/bin/env python3
"""supercomputer — a retro mainframe operator console for your terminal.

Linux and macOS, Python 3.9+, standard library only. Read-only: it reads
system statistics and never changes anything. The blinking lamps are
decorative, but how many are lit follows real load: per-core CPU, per-disk
I/O, network traffic and the busiest processes.

https://github.com/rdubar/supercomputer
"""
import argparse
import ctypes
import curses
import hashlib
import math
import os
import platform
import random
import re
import subprocess
import sys
import time
import uuid

__version__ = "1.0.0"
REPO_URL = "github.com/rdubar/supercomputer"

THEMES = ["AMBER", "GREEN", "CYAN"]
CONFIG_DIR = os.path.expanduser("~/.config/supercomputer")
THEME_FILE = os.path.join(CONFIG_DIR, "theme")
SERVICES_FILE = os.path.join(CONFIG_DIR, "services")
IS_MAC = sys.platform == "darwin"

# Shown on the SUBSYSTEMS row only if installed (Linux: systemd units) or
# running (macOS: process names). Override with ~/.config/supercomputer/services.
LINUX_SERVICES = [("PLEX", "plexmediaserver"), ("JELLY", "jellyfin"), ("SMB", "smbd"),
                  ("XMIT", "transmission-daemon"), ("VNC", "wayvnc"), ("SSH", "ssh"),
                  ("TSNET", "tailscaled"), ("DOCKR", "docker"), ("NGINX", "nginx")]
MAC_SERVICES = [("PLEX", "Plex Media Server"), ("DOCKR", "com.docker.backend"),
                ("TSNET", "Tailscale"), ("DBOX", "Dropbox"), ("SYNC", "Syncthing"),
                ("OLLMA", "ollama")]


# ================================================================ helpers
def read(path, default=""):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return default


def run(*cmd, timeout=3):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def human(n):
    for unit in ("B", "K", "M", "G", "T"):
        if n < 1024 or unit == "T":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024


def uptime_str(seconds):
    s = int(seconds)
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    return f"{d}D {h:02d}H {s // 60:02d}M"


def disk_usage(path):
    try:
        st = os.statvfs(path)
        total = st.f_blocks * st.f_frsize
        free = st.f_bavail * st.f_frsize
        return total, (1 - free / total) if total else 0
    except OSError:
        return 0, 0


def load_services(defaults):
    """[(label, target)] from the services file, else the platform defaults."""
    text = read(SERVICES_FILE)
    if not text:
        return defaults
    out = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            label, _, target = line.partition(" ")
            out.append((label.upper()[:6], target.strip() or label))
    return out


# ================================================================ Linux
class LinuxProbe:
    def __init__(self):
        self.disks = self._disks()
        self.services = self._installed(load_services(LINUX_SERVICES))

    def chip(self):
        for part in read("/proc/device-tree/compatible").split("\0"):
            m = re.match(r"brcm,(bcm\d+)", part)
            if m:
                return m.group(1).upper()
        for line in read("/proc/cpuinfo").splitlines():
            if line.lower().startswith("model name"):
                return line.split(":", 1)[1].strip().upper()[:24]
        return platform.machine().upper()

    def cpu_times(self):
        out = {}
        for line in read("/proc/stat").splitlines():
            if line.startswith("cpu") and line[3:4].isdigit():
                parts = line.split()
                vals = list(map(int, parts[1:]))
                idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
                out[int(parts[0][3:])] = (sum(vals), idle)
        return out

    @staticmethod
    def _whole_disk(dev):
        name = os.path.basename(os.path.realpath(dev))
        sys_path = os.path.realpath(f"/sys/class/block/{name}")
        if os.path.exists(os.path.join(sys_path, "partition")):
            return os.path.basename(os.path.dirname(sys_path))
        return name

    def _disks(self):
        seen, disks = set(), []
        for line in read("/proc/mounts").splitlines():
            dev, mnt = line.split()[:2]
            mnt = mnt.replace("\\040", " ")
            if not re.match(r"/dev/(sd|nvme|mmcblk|vd|xvd|hd|mapper/)", dev):
                continue
            if mnt.startswith("/boot") or dev in seen:
                continue
            seen.add(dev)
            label = "SYS" if mnt == "/" else os.path.basename(mnt).upper()[:6] or "DISK"
            disks.append((label, self._whole_disk(dev), mnt, mnt))
        disks.sort(key=lambda d: (d[2] != "/", d[2]))
        return disks[:6]

    def disk_bytes(self):
        out = {}
        for line in read("/proc/diskstats").splitlines():
            p = line.split()
            if len(p) >= 10:
                out[p[2]] = (int(p[5]) * 512, int(p[9]) * 512)
        return out

    def net_bytes(self):
        rx = tx = 0
        for line in read("/proc/net/dev").splitlines()[2:]:
            name, data = line.split(":", 1)
            name = name.strip()
            if re.match(r"(lo|docker|veth|br-|virbr|tailscale|tun|tap|wg)", name):
                continue
            v = data.split()
            rx += int(v[0])
            tx += int(v[8])
        return rx, tx

    def memory(self):
        m = {}
        for line in read("/proc/meminfo").splitlines():
            k, v = line.split(":", 1)
            m[k] = int(v.split()[0]) * 1024
        return m.get("MemTotal", 1), m.get("MemAvailable", 0)

    def temperature(self):
        raw = read("/sys/class/thermal/thermal_zone0/temp").strip()
        return int(raw) / 1000 if raw.isdigit() else None

    def uptime(self):
        try:
            return float(read("/proc/uptime", "0").split()[0])
        except ValueError:
            return 0

    def proc_cpu(self):
        """{pid: (name, cpu seconds)}."""
        tck = os.sysconf("SC_CLK_TCK")
        out = {}
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue
            data = read(f"/proc/{pid}/stat")
            try:
                name = data[data.index("(") + 1: data.rindex(")")]
                fields = data[data.rindex(")") + 2:].split()
                out[int(pid)] = (name, (int(fields[11]) + int(fields[12])) / tck)
            except (ValueError, IndexError):
                continue
        return out

    def _installed(self, services):
        if not services:
            return []
        out = run("systemctl", "show", "-p", "Id", "-p", "LoadState",
                  *[t for _, t in services])
        missing = set()
        for block in out.strip().split("\n\n"):
            props = dict(l.split("=", 1) for l in block.splitlines() if "=" in l)
            if props.get("LoadState") == "not-found":
                missing.add(props.get("Id", "").replace(".service", ""))
        return [(l, t) for l, t in services if t not in missing]

    def service_states(self):
        if not self.services:
            return []
        states = run("systemctl", "is-active", *[t for _, t in self.services]).split()
        states += ["unknown"] * (len(self.services) - len(states))
        return [(label, st == "active") for (label, _), st in zip(self.services, states)]


# ================================================================ macOS
class MacProbe:
    def __init__(self):
        self.lib = ctypes.CDLL("/usr/lib/libSystem.dylib")
        self.lib.mach_host_self.restype = ctypes.c_uint
        self.lib.host_processor_info.argtypes = [
            ctypes.c_uint, ctypes.c_int, ctypes.POINTER(ctypes.c_uint),
            ctypes.POINTER(ctypes.POINTER(ctypes.c_uint)), ctypes.POINTER(ctypes.c_uint)]
        self.lib.vm_deallocate.argtypes = [ctypes.c_uint, ctypes.c_size_t, ctypes.c_size_t]
        self.host = self.lib.mach_host_self()
        self.task = ctypes.c_uint.in_dll(self.lib, "mach_task_self_").value
        self.mem_total = int(run("sysctl", "-n", "hw.memsize").strip() or 1)
        m = re.search(r"sec = (\d+)", run("sysctl", "-n", "kern.boottime"))
        self.boot = int(m.group(1)) if m else time.time()
        self.disks = self._disks()
        wanted = load_services(MAC_SERVICES)
        if read(SERVICES_FILE):
            self.services = wanted
        else:  # defaults: only what is running now
            names = {n for n, _ in self.proc_cpu().values()}
            self.services = [(l, t) for l, t in wanted if t[:16] in names]

    def chip(self):
        return run("sysctl", "-n", "machdep.cpu.brand_string").strip().upper() or "APPLE SILICON"

    def cpu_times(self):
        count = ctypes.c_uint(0)
        info = ctypes.POINTER(ctypes.c_uint)()
        n = ctypes.c_uint(0)
        # flavor 2 = PROCESSOR_CPU_LOAD_INFO: user, system, idle, nice ticks per CPU
        if self.lib.host_processor_info(self.host, 2, ctypes.byref(count),
                                        ctypes.byref(info), ctypes.byref(n)) != 0:
            return {}
        out = {}
        for i in range(count.value):
            user, system, idle, nice = (info[i * 4 + k] for k in range(4))
            out[i] = (user + system + idle + nice, idle)
        self.lib.vm_deallocate(self.task, ctypes.cast(info, ctypes.c_void_p).value,
                               n.value * ctypes.sizeof(ctypes.c_uint))
        return out

    def _disks(self):
        disks = []
        for line in run("mount").splitlines():
            m = re.match(r"(/dev/(disk\d+)\S*) on (.+) \((.*)\)$", line)
            if not m:
                continue
            _, whole, mnt, opts = m.groups()
            if mnt == "/":
                usage = "/System/Volumes/Data" if os.path.isdir("/System/Volumes/Data") else "/"
                disks.append(("SYS", "disk0", mnt, usage))  # internal SSD
            elif mnt.startswith("/Volumes/") and "nobrowse" not in opts:
                label = os.path.basename(mnt).upper().replace(" ", "")[:6]
                disks.append((label, whole, mnt, mnt))
        return disks[:6]

    def disk_bytes(self):
        out, pending = {}, None
        text = run("ioreg", "-r", "-c", "IOBlockStorageDriver", "-k", "Statistics",
                   "-d", "3", "-l", "-w", "0")
        for line in text.splitlines():
            if '"Statistics"' in line:
                r = re.search(r'"Bytes \(Read\)"=(\d+)', line)
                w = re.search(r'"Bytes \(Write\)"=(\d+)', line)
                pending = (int(r.group(1)) if r else 0, int(w.group(1)) if w else 0)
            elif '"BSD Name"' in line and pending:
                m = re.search(r'"BSD Name" = "(disk\d+)"', line)
                if m:
                    out[m.group(1)] = pending
                    pending = None
        return out

    def net_bytes(self):
        rx = tx = 0
        for line in run("netstat", "-ibn").splitlines()[1:]:
            p = line.split()
            if len(p) >= 10 and p[0].startswith("en") and "<Link#" in line:
                rx += int(p[-5])
                tx += int(p[-2])
        return rx, tx

    def memory(self):
        text = run("vm_stat")
        page = re.search(r"page size of (\d+)", text)
        page = int(page.group(1)) if page else 4096
        pages = dict((k.strip(), int(v.strip().rstrip("."))) for k, v in
                     (l.split(":", 1) for l in text.splitlines()[1:] if ":" in l)
                     if v.strip().rstrip(".").isdigit())
        avail = sum(pages.get(k, 0) for k in
                    ("Pages free", "Pages inactive", "Pages speculative")) * page
        return self.mem_total, avail

    def temperature(self):
        return None  # needs root (powermetrics); not worth it

    def uptime(self):
        return time.time() - self.boot

    def proc_cpu(self):
        out = {}
        for line in run("ps", "-A", "-o", "pid=,time=,comm=").splitlines():
            p = line.split(None, 2)
            if len(p) < 3:
                continue
            days, t = 0, p[1]  # [dd-][hh:]mm:ss.ss
            if "-" in t:
                d, t = t.split("-", 1)
                days = int(d)
            secs = 0.0
            try:
                for part in t.split(":"):
                    secs = secs * 60 + float(part)
            except ValueError:
                continue
            out[int(p[0])] = (os.path.basename(p[2])[:16], days * 86400 + secs)
        return out

    def service_states(self):
        if not self.services:
            return []
        names = {n for n, _ in self.proc_cpu().values()}
        return [(label, target[:16] in names) for label, target in self.services]


def make_probe():
    return MacProbe() if IS_MAC else LinuxProbe()


# ================================================================ sampler
class Sampler:
    def __init__(self, probe):
        self.p = probe
        self.disks = probe.disks
        self.prev_cpu = probe.cpu_times()
        self.prev_disk = probe.disk_bytes()
        self.prev_net = probe.net_bytes()
        self.prev_t = time.monotonic()
        self.cpu = {k: 0.0 for k in self.prev_cpu}
        self.dio = {}
        self.net = (0.0, 0.0)
        self.services = probe.service_states()
        self.usage = {d[3]: disk_usage(d[3]) for d in self.disks}
        self.mem = probe.memory()
        self.temp = probe.temperature()
        self.prev_proc = probe.proc_cpu()
        self.prev_proc_t = time.monotonic()
        self.jobs = []
        self.tick = 0

    def update(self):
        now = time.monotonic()
        dt = max(now - self.prev_t, 1e-3)
        cur = self.p.cpu_times()
        for k, (tot, idle) in cur.items():
            pt, pi = self.prev_cpu.get(k, (tot, idle))
            dtot = tot - pt
            self.cpu[k] = 0.0 if dtot <= 0 else max(0.0, min(1.0, 1 - (idle - pi) / dtot))
        self.prev_cpu = cur
        ds = self.p.disk_bytes()
        for key, (r, w) in ds.items():
            pr, pw = self.prev_disk.get(key, (r, w))
            self.dio[key] = (max(0, r - pr) / dt, max(0, w - pw) / dt)
        self.prev_disk = ds
        rx, tx = self.p.net_bytes()
        prx, ptx = self.prev_net
        self.net = (max(0, rx - prx) / dt, max(0, tx - ptx) / dt)
        self.prev_net = (rx, tx)
        self.prev_t = now
        self.mem = self.p.memory()
        self.temp = self.p.temperature()
        self.tick += 1
        if self.tick % 3 == 0:
            self.update_jobs()
        if self.tick % 5 == 0:
            self.services = self.p.service_states()
        if self.tick % 30 == 0:
            self.usage = {d[3]: disk_usage(d[3]) for d in self.disks}

    def update_jobs(self):
        now = time.monotonic()
        dt = max(now - self.prev_proc_t, 1e-3)
        cur = self.p.proc_cpu()
        jobs = []
        for pid, (name, secs) in cur.items():
            prev = self.prev_proc.get(pid)
            if prev and prev[0] == name:
                pct = (secs - prev[1]) / dt * 100
                if pct >= 0.5:
                    jobs.append((pid, name, pct))
        jobs.sort(key=lambda j: -j[2])
        self.jobs = jobs[:8]
        self.prev_proc, self.prev_proc_t = cur, now


def rate_level(bps, full=150e6):
    """Map bytes/s to 0..1 on a log scale so small activity still shows."""
    if bps <= 0:
        return 0.0
    return min(1.0, math.log10(1 + bps) / math.log10(1 + full))


# ================================================================ themes
def load_theme(argv_theme):
    if argv_theme:
        return THEMES.index(argv_theme.upper())
    try:
        return THEMES.index(read(THEME_FILE).strip().upper())
    except ValueError:
        return 0


def save_theme(i):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(THEME_FILE, "w") as f:
            f.write(THEMES[i] + "\n")
    except OSError:
        pass


def identity(probe):
    host = platform.node().split(".")[0].upper() or "MAINFRAME"
    serial = hashlib.sha1(str(uuid.getnode()).encode()).hexdigest()[:12].upper()
    return host, probe.chip(), serial


# ================================================================ panel
class Panel:
    def __init__(self, scr, probe, theme):
        self.scr = scr
        self.theme = theme
        self.paused = False
        self.overlay = None  # "help" | "credits"
        self.s = Sampler(probe)
        self.host, self.chip, self.serial = identity(probe)
        self.log = []
        self.last_log = 0
        self.lamps = {}
        curses.curs_set(0)
        scr.nodelay(True)
        curses.start_color()
        self.set_theme()
        self.say(f"{self.host} COLD START COMPLETE. ALL UNITS NOMINAL.")
        self.say("PRESS H FOR OPERATOR CONTROLS, A FOR CREDITS.")

    def set_theme(self):
        bright = (curses.COLOR_YELLOW, curses.COLOR_GREEN, curses.COLOR_CYAN)[self.theme]
        black = curses.COLOR_BLACK
        curses.init_pair(1, bright, black)
        curses.init_pair(2, curses.COLOR_RED, black)
        curses.init_pair(3, curses.COLOR_WHITE, black)
        curses.init_pair(4, black, bright)
        self.MAIN = curses.color_pair(1) | curses.A_BOLD
        self.DIM = curses.color_pair(1) | curses.A_DIM
        self.WARN = curses.color_pair(2) | curses.A_BOLD
        self.LABEL = curses.color_pair(3)
        self.HEAD = curses.color_pair(4) | curses.A_BOLD
        self.scr.bkgd(" ", curses.color_pair(1))

    def say(self, msg):
        self.log.append(f"{time.strftime('%H:%M:%S')}  {msg}")
        self.log = self.log[-50:]

    def put(self, y, x, text, attr=0):
        h, w = self.scr.getmaxyx()
        if 0 <= y < h and 0 <= x < w:
            try:
                self.scr.addstr(y, x, text[: max(0, w - x - 1)], attr)
            except curses.error:
                pass

    def lamp_row(self, y, x, key, n, level):
        """Row of n lamps; about level*n lit, reshuffled each refresh."""
        bits = [random.random() < level * (0.6 + 0.8 * random.random()) for _ in range(n)]
        self.lamps[key] = bits
        for i, on in enumerate(bits):
            self.put(y, x, "●" if on else "·", self.MAIN if on else self.DIM)
            x += 2 + (1 if (i + 1) % 4 == 0 else 0)
        return x

    def bar(self, y, x, width, frac, warn_at=0.9):
        filled = int(round(frac * width))
        attr = self.WARN if frac >= warn_at else self.MAIN
        self.put(y, x, " " * filled, attr | curses.A_REVERSE)
        self.put(y, x + filled, "·" * (width - filled), self.DIM)

    def box(self, y, x, h, w, title):
        self.put(y, x, "╔" + "═" * (w - 2) + "╗", self.DIM)
        for i in range(1, h - 1):
            self.put(y + i, x, "║", self.DIM)
            self.put(y + i, x + w - 1, "║", self.DIM)
        self.put(y + h - 1, x, "╚" + "═" * (w - 2) + "╝", self.DIM)
        self.put(y, x + 2, f" {title} ", self.MAIN)

    # ------------------------------------------------------------ events
    def events(self):
        s = self.s
        if time.monotonic() - self.last_log < 4:
            return
        msgs = []
        for label, key, _, _ in s.disks:
            r, w = s.dio.get(key, (0, 0))
            if r + w > 5e6:
                msgs.append(f"STORAGE UNIT {label}: CHANNEL ACTIVE  R {human(r)}/S  W {human(w)}/S")
        avg = sum(s.cpu.values()) / max(len(s.cpu), 1)
        if avg > 0.6:
            msgs.append(f"VECTOR PIPELINE AT {avg * 100:.0f}% — ALL PROCESSORS ENGAGED")
        if s.net[0] + s.net[1] > 2e6:
            msgs.append(f"DATA LINK: RX {human(s.net[0])}/S  TX {human(s.net[1])}/S")
        for label, ok in s.services:
            if not ok:
                msgs.append(f"*** SUBSYSTEM {label} OFFLINE — OPERATOR ATTENTION ***")
        if not msgs and random.random() < 0.15:
            coolant = f"CORE {s.temp:.1f} C." if s.temp is not None else "SENSORS SEALED."
            msgs.append(random.choice([
                "PARITY CHECK OK. CORE MEMORY CONSISTENT.",
                "SCHEDULER IDLE. AWAITING JOB SUBMISSION.",
                f"COOLANT LOOP NOMINAL. {coolant}",
                "TAPE LIBRARY STANDING BY.",
                "OPERATOR CONSOLE ONLINE.",
                "PUNCH CARD READER EMPTY. INSERT DECK.",
            ]))
        for m in msgs[:2]:
            self.say(m)
        if msgs:
            self.last_log = time.monotonic()

    # ------------------------------------------------------------ draw
    def draw(self):
        s = self.s
        scr = self.scr
        scr.erase()
        h, w = scr.getmaxyx()
        if h < 24 or w < 80:
            self.put(0, 0, "ENLARGE OPERATOR CONSOLE TO 80x24", self.WARN)
            scr.refresh()
            return
        W = min(w - 1, 100)
        title = f" {self.host} · {self.chip} VECTOR PROCESSING SYSTEM · SERIAL {self.serial} "
        self.put(0, 0, title.center(W)[:W], self.HEAD)

        tm, ta = s.mem
        self.put(1, 1, f"UPTIME {uptime_str(self.s.p.uptime())}", self.MAIN)
        self.put(1, 24, f"CORE MEMORY {tm // 2**20:,} MW", self.MAIN)
        self.put(1, 48, "COOLANT ", self.LABEL)
        if s.temp is None:
            self.put(1, 56, " SEALED", self.DIM)
        else:
            self.put(1, 56, f"{s.temp:5.1f} C", self.WARN if s.temp > 75 else self.MAIN)
        self.put(1, W - 9, time.strftime("%H:%M:%S"), self.MAIN)

        # Processors: one column up to 8 cores, two columns beyond that
        y = 3
        cpus = sorted(s.cpu)
        if len(cpus) > 16:  # fold big machines into 16 groups
            groups = [cpus[i::16] for i in range(16)]
            levels = [sum(s.cpu[c] for c in g) / len(g) for g in groups]
            names = [f"G{i:<2}" for i in range(16)]
        else:
            levels = [s.cpu[c] for c in cpus]
            names = [f"{c:<2}" for c in cpus]
        cols = 1 if len(levels) <= 8 else 2
        rows = math.ceil(len(levels) / cols)
        lamps = 24 if cols == 1 else 12
        self.box(y, 0, rows + 2, W, "CENTRAL PROCESSORS")
        for i, (name, lvl) in enumerate(zip(names, levels)):
            row, col = y + 1 + i % rows, i // rows
            x = 2 + col * (W // 2 - 1)
            self.put(row, x, f"CPU {name}", self.LABEL)
            end = self.lamp_row(row, x + 8, f"cpu{i}", lamps, lvl)
            self.put(row, end + 1, f"{lvl * 100:5.1f}%", self.WARN if lvl > 0.9 else self.MAIN)
        y += rows + 2

        # Memory
        used = 1 - ta / tm
        self.box(y, 0, 3, W, "CORE STORAGE")
        self.put(y + 1, 2, "MEM", self.LABEL)
        self.bar(y + 1, 9, 40, used)
        self.put(y + 1, 51, f"{used * 100:4.1f}%  {human(tm - ta)} OF {human(tm)}", self.MAIN)
        y += 3

        # Storage
        if s.disks:
            self.box(y, 0, len(s.disks) + 2, W, "MASS STORAGE UNITS")
            for i, (label, key, _, usage_path) in enumerate(s.disks):
                row = y + 1 + i
                r, wr = s.dio.get(key, (0, 0))
                total, frac = s.usage.get(usage_path, (0, 0))
                self.put(row, 2, f"{label:6}", self.LABEL)
                self.put(row, 9, "R", self.LABEL)
                self.lamp_row(row, 11, f"{key}r{i}", 4, rate_level(r))
                self.put(row, 21, "W", self.LABEL)
                self.lamp_row(row, 23, f"{key}w{i}", 4, rate_level(wr))
                self.bar(row, 34, 20, frac)
                self.put(row, 56, f"{frac * 100:3.0f}% OF {human(total):>6}", self.MAIN)
                self.put(row, 73, f"{human(r + wr):>7}/S", self.MAIN if r + wr > 1e6 else self.DIM)
            y += len(s.disks) + 2

        # Network + subsystems
        self.box(y, 0, 3, W, "DATA LINK / SUBSYSTEMS")
        rx, tx = s.net
        self.put(y + 1, 2, "RX", self.LABEL)
        self.lamp_row(y + 1, 5, "rx", 4, rate_level(rx, 100e6))
        self.put(y + 1, 14, "TX", self.LABEL)
        self.lamp_row(y + 1, 17, "tx", 4, rate_level(tx, 100e6))
        x = 28
        for label, ok in s.services:
            if x + len(label) + 3 > W - 2:
                break
            self.put(y + 1, x, "■" if ok else "□", self.MAIN if ok else self.WARN)
            self.put(y + 1, x + 2, label, self.MAIN if ok else self.WARN)
            x += len(label) + 4
        if not s.services:
            self.put(y + 1, x, f"{human(rx)}/S IN  {human(tx)}/S OUT", self.DIM)
        y += 3

        # Active jobs, only if 3 log lines still fit
        njobs = min(5, h - y - 3 - 2 - 5)
        if njobs > 0:
            self.box(y, 0, njobs + 2, W, "ACTIVE JOBS")
            jobs = s.jobs[:njobs]
            if not jobs:
                self.put(y + 1, 2, "NO JOBS IN EXECUTION" if s.tick >= 3 else "SCANNING JOB TABLE...",
                         self.DIM)
            for i, (pid, name, pct) in enumerate(jobs):
                row = y + 1 + i
                self.put(row, 2, f"JOB {pid:>7}", self.LABEL)
                self.put(row, 15, f"{name.upper()[:16]:16}", self.MAIN)
                end = self.lamp_row(row, 33, f"job{i}", 16, min(pct / 100, 1.0))
                self.put(row, end + 1, f"{pct:6.1f}%", self.WARN if pct > 90 else self.MAIN)
            y += njobs + 2

        # Teletype log
        room = h - y - 3
        if room > 0:
            self.box(y, 0, room + 2, W, "OPERATOR LOG")
            for i, line in enumerate(self.log[-room:]):
                self.put(y + 1 + i, 2, line[: W - 4], self.WARN if "***" in line else self.MAIN)

        footer = f"[H] HELP  [A] CREDITS  [C] PHOSPHOR: {THEMES[self.theme]}  [Q] HALT"
        if self.paused:
            footer += "   *** FROZEN — [P] RESUMES ***"
        self.put(h - 1, 0, footer, self.WARN if self.paused else self.DIM)
        if self.overlay == "help":
            self.card(h, W, "OPERATOR CONTROLS", [
                "C        CHANGE PHOSPHOR: AMBER / GREEN / CYAN",
                "P SPACE  FREEZE / RESUME THE PANEL",
                "H ?      THIS CARD",
                "A        CREDITS",
                "Q        HALT CONSOLE   (ESC CLOSES A CARD)",
                "",
                "LAMP DENSITY FOLLOWS REAL LOAD:",
                "  CENTRAL PROCESSORS   PER-CORE CPU",
                "  MASS STORAGE         READ / WRITE PER DISK",
                "  DATA LINK            NETWORK IN / OUT",
                "  ACTIVE JOBS          BUSIEST PROCESSES (3 S)",
                "",
                "COLOUR IS REMEMBERED. START WITH --GREEN ETC.",
            ])
        elif self.overlay == "credits":
            self.card(h, W, f"SUPERCOMPUTER  V{__version__}", [
                "A RETRO MAINFRAME OPERATOR CONSOLE",
                "",
                "CONCEIVED BY ........ ROGER DUBAR",
                "BUILT BY ............ CLAUDE CODE (ANTHROPIC)",
                f"RUNNING ON .......... {self.host[:22]}",
                f"PROCESSOR ........... {self.chip[:22]}",
                "",
                REPO_URL.upper(),
                "MIT LICENSE",
                "",
                "NO MAINFRAMES WERE HARMED IN THE MAKING",
                "OF THIS CONSOLE.",
            ])
        scr.refresh()

    def card(self, h, W, title, lines):
        bw = max(max(len(l) for l in lines), len(title)) + 8
        bh = len(lines) + 4
        y0, x0 = max(0, (h - bh) // 2), max(0, (W - bw) // 2)
        for i in range(bh):
            self.put(y0 + i, x0, " " * bw, self.MAIN)
        self.box(y0, x0, bh, bw, title)
        for i, l in enumerate(lines):
            attr = self.MAIN | curses.A_UNDERLINE if l == REPO_URL.upper() else self.LABEL
            self.put(y0 + 2 + i, x0 + 4, l, attr)

    def run(self):
        next_sample = time.monotonic() + 1
        while True:
            key = self.scr.getch()
            if key == 27 and self.overlay:
                self.overlay = None
            elif key in (ord("q"), ord("Q"), 27):
                return
            elif key in (ord("c"), ord("C")):
                self.theme = (self.theme + 1) % len(THEMES)
                self.set_theme()
                save_theme(self.theme)
            elif key in (ord("h"), ord("H"), ord("?")):
                self.overlay = None if self.overlay == "help" else "help"
            elif key in (ord("a"), ord("A")):
                self.overlay = None if self.overlay == "credits" else "credits"
            elif key in (ord("p"), ord("P"), ord(" ")):
                self.paused = not self.paused
                self.say("PANEL FROZEN BY OPERATOR." if self.paused else "PANEL RESUMED.")
            if time.monotonic() >= next_sample:
                self.s.update()
                self.events()
                next_sample = max(next_sample + 1, time.monotonic())
            if not self.paused or key != -1:
                self.draw()
            time.sleep(0.2)


# ================================================================ banner
def banner(probe):
    A, D, R = "\033[1;33m", "\033[2;33m", "\033[0m"
    host, chip, _ = identity(probe)
    tm, ta = probe.memory()
    load = " ".join(f"{x:.2f}" for x in os.getloadavg())
    t = probe.temperature()
    coolant = f"   COOLANT {t:.1f} C" if t is not None else ""
    svc = "  ".join(f"{'■' if ok else '□'} {n}" for n, ok in probe.service_states())
    lamps = "".join(random.choice("●·") for _ in range(32))
    print("\n".join([
        f"{D}╔{'═' * 62}╗{R}",
        f"{D}║{R}{A}{('  ' + host + ' · ' + chip + ' VECTOR PROCESSING SYSTEM')[:62].ljust(62)}{R}{D}║{R}",
        f"{D}║{R}{A}{('  ' + lamps).ljust(62)}{R}{D}║{R}",
        f"{D}╚{'═' * 62}╝{R}",
        f"{A}  UPTIME {uptime_str(probe.uptime())}   LOAD {load}{coolant}{R}",
        f"{A}  CORE MEMORY {(tm - ta) // 2**20:,} / {tm // 2**20:,} MW   {svc}{R}",
        f"{D}  TYPE 'supercomputer' FOR THE OPERATOR CONSOLE{R}",
        "",
    ]))


def main():
    ap = argparse.ArgumentParser(
        prog="supercomputer",
        description="A retro mainframe operator console for your terminal.",
        epilog=f"Keys: h help, a credits, c colour, p freeze, q quit.  https://{REPO_URL}")
    colour = ap.add_mutually_exclusive_group()
    for t in THEMES:
        colour.add_argument(f"--{t.lower()}", dest="theme", action="store_const", const=t,
                            help=f"start in {t.lower()} phosphor")
    ap.add_argument("--banner", action="store_true", help="print a short static banner and exit")
    ap.add_argument("--version", action="version", version=f"supercomputer {__version__}")
    args = ap.parse_args()
    probe = make_probe()
    if args.banner:
        banner(probe)
        return
    os.environ.setdefault("ESCDELAY", "25")
    theme = load_theme(args.theme)
    curses.wrapper(lambda scr: Panel(scr, probe, theme).run())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
