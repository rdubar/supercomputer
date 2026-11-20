#!/usr/bin/env python3
"""Render a retro mainframe front-panel wallpaper for this machine.

  supercomputer-wallpaper [OUTPUT.png] [--size 1920x1080]

Needs Pillow (pip install pillow). Host name, processor, core count, memory
and storage units come from the same probes as the supercomputer console.
"""
import argparse
import math
import os
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

import supercomputer as sc

AMBER = (255, 140, 0)
AMBER_DIM = (60, 32, 6)
CREAM = (232, 220, 190)
LABEL = (190, 170, 130)
RULE = (120, 96, 60)
FONTS = [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"),
    ("/System/Library/Fonts/Menlo.ttc", "/System/Library/Fonts/Menlo.ttc"),
    ("/Library/Fonts/Courier New.ttf", "/Library/Fonts/Courier New Bold.ttf"),
]


def render(out, W, H):
    S = W / 1920
    probe = sc.make_probe()
    host, chip, serial = sc.identity(probe)
    ncores = len(probe.cpu_times()) or os.cpu_count() or 1
    mem_kw = probe.memory()[0] // 2**20
    units = [d[0] for d in probe.disks][:5] or ["SYS"]
    random.seed(1975)

    regular, bold = next(((r, b) for r, b in FONTS if os.path.exists(r)), (None, None))

    def font(size, is_bold=False):
        path = bold if is_bold else regular
        try:
            return ImageFont.truetype(path, int(size * S), index=1 if is_bold and path.endswith(".ttc") else 0)
        except (OSError, TypeError, ValueError):
            return ImageFont.load_default()

    def px(v):
        return int(v * S)

    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):  # warm charcoal gradient
        c = int(22 + 10 * math.sin(y / H * math.pi))
        d.line([(0, y), (W, y)], fill=(c + 4, c + 2, c))
    img = Image.blend(img, Image.effect_noise((W, H), 18).convert("RGB"), 0.04)
    d = ImageDraw.Draw(img)
    glow = Image.new("RGB", (W, H))
    g = ImageDraw.Draw(glow)

    def lamp(x, y, r, on, color=AMBER):
        if on:
            g.ellipse([x - r * 2.6, y - r * 2.6, x + r * 2.6, y + r * 2.6],
                      fill=tuple(int(c * 0.38) for c in color))
            d.ellipse([x - r, y - r, x + r, y + r], fill=color)
            d.ellipse([x - r * 0.45, y - r * 0.55, x + r * 0.1, y - r * 0.1], fill=(255, 225, 170))
        else:
            d.ellipse([x - r, y - r, x + r, y + r], fill=AMBER_DIM, outline=(40, 26, 8))

    def toggle(x, y, color, up):
        w, h = px(16), px(46)
        d.rounded_rectangle([x - w / 2, y, x + w / 2, y + h], radius=px(4), fill=color, outline=(20, 18, 16))
        mark = y + px(6) if up else y + h - px(14)
        d.rectangle([x - w / 2 + px(3), mark, x + w / 2 - px(3), mark + px(8)],
                    fill=tuple(max(0, c - 60) for c in color))

    def text(x, y, s, size, fill=LABEL, is_bold=False, anchor="la"):
        d.text((x, y), s, font=font(size, is_bold), fill=fill, anchor=anchor)

    # Frame and nameplate (top left kept clear for desktop icons)
    margin, top = px(90), px(120)
    d.rectangle([margin, top, W - margin, H - px(70)], outline=RULE, width=px(3))
    d.rectangle([margin + px(10), top + px(10), W - margin - px(10), H - px(80)],
                outline=(60, 48, 32), width=px(1))
    text(W / 2, top + px(55), f"{host}  ·  {chip} VECTOR PROCESSING SYSTEM", 42, CREAM, True, "mm")
    text(W / 2, top + px(100),
         f"{ncores} CENTRAL PROCESSORS  ·  {mem_kw:,} KW CORE  ·  SERIAL {serial}", 18, LABEL, False, "mm")
    d.line([(margin + px(60), top + px(128)), (W - margin - px(60), top + px(128))], fill=RULE, width=px(2))

    # Register lamps
    registers = ["PROGRAM COUNTER", "MEMORY ADDRESS", "MEMORY BUFFER", "ACCUMULATOR", "INSTRUCTION"]
    bits, spacing = 24, px(40)
    x0, row_y = margin + px(320), top + px(190)

    def bx(b):
        return x0 + b * spacing + (b // 3) * px(14)

    for ri, name in enumerate(registers):
        y = row_y + ri * px(62)
        text(x0 - px(40), y, name, 20, LABEL, True, "rm")
        for b in range(bits):
            lamp(bx(b), y, px(11), random.random() < 0.45)
            if ri == 0:
                text(bx(b), y - px(30), f"{bits - 1 - b:02d}", 12, RULE, False, "mm")

    sw_y = row_y + len(registers) * px(62) - px(10)
    text(x0 - px(40), sw_y + px(23), "SWITCH REGISTER", 20, LABEL, True, "rm")
    for b in range(bits):
        color = (214, 120, 40) if (b // 3) % 2 == 0 else (224, 214, 190)
        toggle(bx(b), sw_y, color, random.random() < 0.3)

    ctl_y = sw_y + px(82)
    for i, name in enumerate(["START", "LOAD", "DEP", "EXAM", "CONT", "HALT", "STEP", "BOOT"]):
        x = x0 + i * px(120) + px(30)
        toggle(x, ctl_y, (170, 40, 30) if name in ("HALT", "BOOT") else (224, 214, 190), False)
        text(x, ctl_y + px(66), name, 15, LABEL, True, "mm")

    # Status column
    sx, sy = W - margin - px(250), row_y - px(10)
    text(sx, sy - px(30), "SYSTEM STATUS", 20, CREAM, True)
    statuses = [("POWER", True, (90, 230, 90)), ("RUN", True, AMBER), ("HALT", False, (240, 60, 40)),
                ("PARITY", False, (240, 60, 40)), ("COOLANT", True, (80, 200, 255)),
                ("VECTOR", True, AMBER), ("I/O BUSY", True, AMBER), ("OPERATOR", False, AMBER)]
    for i, (name, on, col) in enumerate(statuses):
        y = sy + px(20) + i * px(44)
        lamp(sx + px(14), y, px(10), on, col)
        text(sx + px(42), y, name, 18, LABEL, True, "lm")

    # Tape drives, one per storage unit
    tape_y = ctl_y + px(105)
    unit_w = px(270)
    tx0 = W / 2 - (len(units) * unit_w) / 2
    for i, name in enumerate(units):
        ux = tx0 + i * unit_w
        d.rounded_rectangle([ux + px(10), tape_y, ux + unit_w - px(10), tape_y + px(150)],
                            radius=px(8), fill=(16, 14, 12), outline=RULE, width=px(2))
        for k, cx in enumerate((ux + px(80), ux + unit_w - px(80))):
            cy, r = tape_y + px(66), px(46)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(38, 34, 30), outline=(110, 100, 86), width=px(2))
            tr = r * (0.85 if (k + i) % 2 == 0 else 0.55)
            d.ellipse([cx - tr, cy - tr, cx + tr, cy + tr], fill=(60, 40, 22))
            for a in range(3):
                ang = a * 2 * math.pi / 3 + i
                d.line([(cx, cy), (cx + math.cos(ang) * r * 0.9, cy + math.sin(ang) * r * 0.9)],
                       fill=(110, 100, 86), width=px(4))
            d.ellipse([cx - px(8), cy - px(8), cx + px(8), cy + px(8)], fill=(150, 140, 120))
        text(ux + unit_w / 2, tape_y + px(132), f"STORAGE UNIT {name}", 15, LABEL, True, "mm")
        lamp(ux + unit_w - px(28), tape_y + px(132), px(6), True)

    text(margin + px(20), H - px(100), "VECTOR PROCESSING DIVISION  ·  CORE MEMORY ONLINE", 14, RULE)
    text(W - margin - px(20), H - px(100), "OPERATOR CONSOLE: TYPE 'supercomputer'", 14, RULE, False, "ra")

    # Glow, scanlines, vignette
    img = ImageChops.add(img, glow.filter(ImageFilter.GaussianBlur(px(9))))
    over = Image.new("L", (W, H), 0)
    o = ImageDraw.Draw(over)
    for y in range(0, H, 3):
        o.line([(0, y), (W, y)], fill=22)
    black = Image.new("RGB", (W, H))
    img = Image.composite(black, img, over)
    vig = Image.radial_gradient("L").resize((W, H)).point(lambda v: int(v * 0.55))
    img = Image.composite(black, img, vig)

    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    img.save(out, optimize=True)
    return out


def main():
    ap = argparse.ArgumentParser(prog="supercomputer-wallpaper", description=__doc__.splitlines()[0])
    ap.add_argument("output", nargs="?", default=os.path.expanduser(
        "~/Pictures/wallpapers/supercomputer.png"))
    ap.add_argument("--size", default="1920x1080", help="WIDTHxHEIGHT (default 1920x1080)")
    args = ap.parse_args()
    w, h = (int(v) for v in args.size.lower().split("x"))
    print(render(args.output, w, h))


if __name__ == "__main__":
    main()
