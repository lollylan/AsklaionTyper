"""Generate the AsklaionTyper logo (PNG + multi-resolution ICO).

Standalone tool — invoke with the project's venv python:
    venv\\Scripts\\python.exe scripts\\generate_logo.py
"""

import os
import sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(PROJECT_ROOT, 'assets')

PNG_PATH = os.path.join(ASSETS_DIR, 'ww-logo.png')
ICO_PATH = os.path.join(ASSETS_DIR, 'ww-logo.ico')

CANVAS = 512  # Render at high resolution, downsample for ICO


def _find_font(size):
    """Return the heaviest available sans-serif font on the system."""
    candidates = [
        'C:/Windows/Fonts/seguibl.ttf',   # Segoe UI Black
        'C:/Windows/Fonts/seguisb.ttf',   # Segoe UI Semibold
        'C:/Windows/Fonts/arialbd.ttf',   # Arial Bold
        'C:/Windows/Fonts/Arial.ttf',
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _gradient_background(size):
    """Vertical dark-blue → near-black gradient with subtle noise."""
    img = Image.new('RGB', (size, size), (10, 14, 39))
    top = (30, 58, 95)       # #1e3a5f
    bottom = (10, 14, 39)    # #0a0e27
    for y in range(size):
        t = y / max(1, size - 1)
        r = int(top[0] * (1 - t) + bottom[0] * t)
        g = int(top[1] * (1 - t) + bottom[1] * t)
        b = int(top[2] * (1 - t) + bottom[2] * t)
        for x in range(size):
            img.putpixel((x, y), (r, g, b))
    return img


def _rounded_mask(size, radius):
    mask = Image.new('L', (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=radius, fill=255
    )
    return mask


def render_logo(size=CANVAS):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))

    # 1. Rounded-square background with gradient
    bg = _gradient_background(size).convert('RGBA')
    radius = int(size * 0.22)
    mask = _rounded_mask(size, radius)
    img.paste(bg, (0, 0), mask)

    # 2. Soft inner glow on the upper edge for depth
    glow = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse(
        [-size * 0.15, -size * 0.55, size * 1.15, size * 0.45],
        fill=(120, 180, 255, 50),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(radius=size * 0.05))
    glow_masked = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    glow_masked.paste(glow, (0, 0), mask)
    img = Image.alpha_composite(img, glow_masked)

    # 3. Big bold "A" in the centre
    draw = ImageDraw.Draw(img)
    font_size = int(size * 0.66)
    font = _find_font(font_size)
    text = 'A'
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (size - tw) // 2 - bbox[0]
    ty = (size - th) // 2 - bbox[1] - int(size * 0.05)
    # Subtle drop shadow
    shadow = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text((tx + 4, ty + 6), text, font=font, fill=(0, 0, 0, 110))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=size * 0.012))
    img = Image.alpha_composite(img, shadow)
    draw = ImageDraw.Draw(img)
    draw.text((tx, ty), text, font=font, fill=(255, 255, 255, 245))

    # 4. Three voice-bars under the A as an audio accent
    bar_w = int(size * 0.04)
    bar_gap = int(size * 0.045)
    bar_y_center = int(size * 0.83)
    heights = [int(size * 0.10), int(size * 0.16), int(size * 0.08)]
    total_w = 3 * bar_w + 2 * bar_gap
    x0 = (size - total_w) // 2
    for i, h in enumerate(heights):
        x = x0 + i * (bar_w + bar_gap)
        y0 = bar_y_center - h // 2
        y1 = bar_y_center + h // 2
        ImageDraw.Draw(img).rounded_rectangle(
            [x, y0, x + bar_w, y1], radius=bar_w // 2,
            fill=(120, 180, 255, 235),
        )

    return img


def main():
    os.makedirs(ASSETS_DIR, exist_ok=True)
    big = render_logo(CANVAS)

    # Save the master PNG at 512 px (let the OS scale down where needed)
    big.save(PNG_PATH, 'PNG')
    print(f'Wrote {PNG_PATH}  ({big.size[0]}x{big.size[1]})')

    # Multi-resolution ICO for Windows tray / taskbar
    sizes = [256, 128, 64, 48, 32, 24, 16]
    icons = []
    for s in sizes:
        icons.append(big.resize((s, s), Image.LANCZOS))
    icons[0].save(ICO_PATH, format='ICO', sizes=[(s, s) for s in sizes])
    print(f'Wrote {ICO_PATH}  (sizes: {sizes})')


if __name__ == '__main__':
    main()
