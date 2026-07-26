#!/usr/bin/env python3
"""
Regenerates the app icon at proper resolution for both the web favicon and the Electron desktop
app icon, from one 1024x1024 master — reproducing the existing favicon's design (oxblood rounded
square, cream three-dot "timeline" mark) rather than a new one, since that mark isn't tied to any
particular product name and the existing favicon.ico (generated ad hoc, no script kept) was only
ever rendered at 64x64, too small to derive a crisp desktop-icon-sized asset from.

Produces:
  webapp/static/favicon.ico     — multi-size (16/32/48/64), browser tab icon
  electron/icon.png             — 1024x1024 master, what electron-builder's build config points at
  electron/icon.icns            — macOS app icon (built via the system `iconutil`, macOS only)
  electron/icon.ico             — Windows app icon (multi-size, via Pillow, cross-platform)
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parent.parent
ACCENT = (125, 42, 58, 255)      # --accent, oxblood
CREAM = (253, 246, 238, 255)     # --accent-contrast

MASTER_SIZE = 1024


def build_master() -> Image.Image:
    size = MASTER_SIZE
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    corner_radius = round(size * 0.22)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=corner_radius, fill=ACCENT)

    # Three dots joined by two lines — the same "timeline" mark as the existing favicon.
    cy = size // 2
    dot_r = round(size * 0.075)
    line_w = round(size * 0.045)
    xs = [round(size * 0.28), round(size * 0.5), round(size * 0.72)]

    draw.line([(xs[0], cy), (xs[2], cy)], fill=CREAM, width=line_w)
    for x in xs:
        draw.ellipse([x - dot_r, cy - dot_r, x + dot_r, cy + dot_r], fill=CREAM)
    # Middle dot is the largest in the original design — redraw it slightly bigger, on top.
    mid_r = round(dot_r * 1.35)
    draw.ellipse([xs[1] - mid_r, cy - mid_r, xs[1] + mid_r, cy + mid_r], fill=CREAM)

    return img


def make_favicon_ico(master: Image.Image, dest: Path) -> None:
    sizes = [16, 32, 48, 64]
    master.save(dest, format="ICO", sizes=[(s, s) for s in sizes])


def make_windows_ico(master: Image.Image, dest: Path) -> None:
    sizes = [16, 24, 32, 48, 64, 128, 256]
    master.save(dest, format="ICO", sizes=[(s, s) for s in sizes])


def make_macos_icns(master: Image.Image, dest: Path) -> None:
    if sys.platform != "darwin" or shutil.which("iconutil") is None:
        print("Skipping .icns (needs macOS's `iconutil`, not available here) — "
              "icon.png is still written and electron-builder can derive .icns from it at build time.")
        return
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "icon.iconset"
        iconset.mkdir()
        # Required namings/sizes for iconutil's .iconset format, including @2x retina variants.
        for base_size, suffix in [(16, ""), (16, "@2x"), (32, ""), (32, "@2x"),
                                   (128, ""), (128, "@2x"), (256, ""), (256, "@2x"), (512, ""), (512, "@2x")]:
            px = base_size * (2 if suffix else 1)
            resized = master.resize((px, px), Image.LANCZOS)
            resized.save(iconset / f"icon_{base_size}x{base_size}{suffix}.png")
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(dest)], check=True)


def main():
    master = build_master()

    favicon_path = REPO_ROOT / "webapp" / "static" / "favicon.ico"
    make_favicon_ico(master, favicon_path)
    print(f"Wrote {favicon_path}")

    icon_png_path = REPO_ROOT / "electron" / "icon.png"
    master.save(icon_png_path)
    print(f"Wrote {icon_png_path}")

    icon_ico_path = REPO_ROOT / "electron" / "icon.ico"
    make_windows_ico(master, icon_ico_path)
    print(f"Wrote {icon_ico_path}")

    icon_icns_path = REPO_ROOT / "electron" / "icon.icns"
    make_macos_icns(master, icon_icns_path)


if __name__ == "__main__":
    main()
