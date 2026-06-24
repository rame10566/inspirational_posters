"""
Scenic morning background generator — light, warm, photographic-quality scenes.

Key design principles (matching user's reference images):
- Light, airy, warm palettes (pinks, golds, peach, soft blues)
- Realistic-looking sunrise/dawn lighting
- Minimal darkness — backgrounds should be BRIGHT and inspiring
- Multiple atmospheric layers for depth
"""

import math
import random
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
from config import POSTER_WIDTH, POSTER_HEIGHT


def _lerp(a, b, t):
    return a + (b - a) * t


def _lerp_color(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(_lerp(c1[i], c2[i], t)) for i in range(3))


def _multi_stop_gradient(img, stops, vertical=True):
    """Apply a multi-stop gradient to an image."""
    w, h = img.size
    pixels = img.load()
    for y in range(h):
        t = y / h if vertical else 0
        # Find which segment we're in
        n = len(stops) - 1
        seg = min(int(t * n), n - 1)
        local_t = (t * n) - seg
        color = _lerp_color(stops[seg], stops[seg + 1], local_t)
        for x in range(w):
            pixels[x, y] = color
    return img


def _add_sun(img, cx, cy, inner_r, outer_r, core_color, glow_color, intensity=1.0):
    """Add a soft, glowing sun with multiple halo rings."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Outer atmospheric glow (very soft)
    steps = 60
    for i in range(steps, 0, -1):
        r = int(outer_r * (i / steps))
        prog = i / steps
        alpha = int(255 * intensity * (1 - prog) ** 2.2 * 0.35)
        c = glow_color + (alpha,)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c)

    # Inner bright core
    for i in range(inner_r, 0, -2):
        prog = i / inner_r
        alpha = int(255 * intensity * (1 - prog * 0.3))
        c = _lerp_color(core_color, (255, 255, 240), 1 - prog) + (alpha,)
        draw.ellipse([cx - i, cy - i, cx + i, cy + i], fill=c)

    return Image.alpha_composite(img.convert("RGBA"), overlay)


def _add_light_rays(img, cx, cy, color, count=12, intensity=0.12):
    """Add subtle light rays emanating from the sun."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    w, h = img.size
    for i in range(count):
        angle = (i / count) * 2 * math.pi + random.uniform(-0.15, 0.15)
        length = random.randint(int(max(w, h) * 0.6), int(max(w, h) * 1.2))
        ex = cx + int(math.cos(angle) * length)
        ey = cy + int(math.sin(angle) * length)
        alpha = random.randint(int(255 * intensity * 0.4), int(255 * intensity))
        draw.line([(cx, cy), (ex, ey)], fill=color + (alpha,),
                  width=random.randint(1, 4))
    blurred = overlay.filter(ImageFilter.GaussianBlur(radius=8))
    return Image.alpha_composite(img.convert("RGBA"), blurred)


def _add_mist_layers(img, ground_y, intensity=0.3):
    """Add soft mist/fog near the horizon."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    w, h = img.size
    for layer in range(6):
        y = ground_y - layer * 30 - random.randint(-10, 10)
        mist_h = random.randint(40, 90)
        alpha = int(255 * intensity * (1 - layer / 6) * 0.7)
        draw.rectangle([0, y, w, y + mist_h], fill=(255, 240, 220, alpha))
    blurred = overlay.filter(ImageFilter.GaussianBlur(radius=20))
    return Image.alpha_composite(img.convert("RGBA"), blurred)


def _add_horizon_glow(img, horizon_y, color, width=300, intensity=0.5):
    """Add a warm horizontal glow along the horizon line."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    w = img.width
    for i in range(width, 0, -4):
        prog = i / width
        alpha = int(255 * intensity * (1 - prog) ** 1.5)
        draw.rectangle([0, horizon_y - i, w, horizon_y + i], fill=color + (alpha,))
    blurred = overlay.filter(ImageFilter.GaussianBlur(radius=15))
    return Image.alpha_composite(img.convert("RGBA"), blurred)


# ═══════════════════════════════════════════════════
# BACKGROUND THEMES
# ═══════════════════════════════════════════════════

def create_sunrise_path(width=POSTER_WIDTH, height=POSTER_HEIGHT):
    """
    Golden sunrise over a winding path through a misty field.
    Inspired by the Dickens reference image — warm golden-orange sky,
    misty field, light streaming toward the viewer.
    """
    img = Image.new("RGB", (width, height))

    # Sky gradient: deep rose → peach-gold → pale golden-white
    sky_stops = [
        (100, 60, 120),   # top: soft purple-rose
        (200, 100, 120),  # rose
        (230, 140, 90),   # warm orange-peach
        (250, 195, 120),  # golden-peach
        (255, 230, 170),  # pale gold at horizon
        (255, 245, 210),  # very light near ground
    ]
    _multi_stop_gradient(img, sky_stops)

    ground_y = int(height * 0.55)

    # Ground: golden-green field
    draw = ImageDraw.Draw(img)
    for y in range(ground_y, height):
        t = (y - ground_y) / (height - ground_y)
        c = _lerp_color((200, 180, 100), (100, 90, 50), t)
        # Add warm sun-tinted glow near center
        draw.line([(0, y), (width, y)], fill=c)

    img = img.convert("RGBA")

    # Bright sun near horizon
    sun_x = int(width * 0.5) + random.randint(-40, 40)
    sun_y = ground_y - 20
    img = _add_sun(img, sun_x, sun_y, 45, 280, (255, 245, 200), (255, 200, 120), intensity=1.2)
    img = _add_light_rays(img, sun_x, sun_y, (255, 220, 150), count=14, intensity=0.15)
    img = _add_horizon_glow(img, ground_y, (255, 210, 130), width=200, intensity=0.6)
    img = _add_mist_layers(img, ground_y, intensity=0.5)

    # Path: converging lines toward sun
    draw = ImageDraw.Draw(img)
    path_color = (160, 130, 70, 180)
    vp_x, vp_y = sun_x, sun_y + 10
    path_width_base = 160
    for side in [-1, 1]:
        pts = []
        for y in range(ground_y, height + 10, 5):
            t = (y - ground_y) / (height - ground_y)
            x = vp_x + side * int(t * path_width_base / 2)
            pts.append((x, y))
        if len(pts) > 1:
            draw.line(pts, fill=path_color, width=3)

    # Fill path area with slightly lighter ground color
    path_pts = []
    for y in range(ground_y, height, 5):
        t = (y - ground_y) / (height - ground_y)
        xl = vp_x - int(t * path_width_base / 2)
        xr = vp_x + int(t * path_width_base / 2)
        path_pts.extend([(xl, y), (xr, y)])
    # Draw path as series of horizontal segments
    draw2 = ImageDraw.Draw(img)
    for y in range(ground_y, height, 2):
        t = (y - ground_y) / (height - ground_y)
        xl = vp_x - int(t * path_width_base / 2)
        xr = vp_x + int(t * path_width_base / 2)
        c = _lerp_color((200, 170, 110), (140, 115, 65), t)
        draw2.line([(xl, y), (xr, y)], fill=c + (200,))

    img = img.filter(ImageFilter.GaussianBlur(radius=1.5))
    return img.convert("RGB")


def create_mountain_lake(width=POSTER_WIDTH, height=POSTER_HEIGHT):
    """
    Sunrise over a mountain lake with dock and lotus flowers.
    Inspired by the Bhagavad Gita reference — rich sunrise colors,
    reflective water, beautiful warm pinks and golds.
    """
    img = Image.new("RGB", (width, height))

    # Sky: deep orange-rose → brilliant gold → soft peachy-white
    sky_stops = [
        (80, 40, 80),    # deep purple-rose at top
        (180, 70, 90),   # rose
        (220, 110, 60),  # orange
        (250, 175, 80),  # golden
        (255, 220, 140), # pale gold
        (255, 240, 200), # very light at horizon
    ]
    _multi_stop_gradient(img, sky_stops)

    horizon_y = int(height * 0.42)
    img = img.convert("RGBA")

    # Sun
    sun_x = int(width * 0.5) + random.randint(-30, 30)
    sun_y = horizon_y - 10
    img = _add_sun(img, sun_x, sun_y, 55, 320, (255, 255, 200), (255, 190, 100), intensity=1.3)
    img = _add_light_rays(img, sun_x, sun_y, (255, 220, 150), count=16, intensity=0.18)
    img = _add_horizon_glow(img, horizon_y, (255, 200, 100), width=250, intensity=0.8)

    draw = ImageDraw.Draw(img)

    # Mountains in background (soft purple-blue)
    mtn_pts = [(0, height)]
    for x in range(0, width + 20, 15):
        base_y = horizon_y + random.randint(20, 40)
        peak_drop = int(80 * abs(math.sin(x * 0.008 + 1.5)))
        y = base_y - peak_drop
        mtn_pts.append((x, y))
    mtn_pts.append((width, height))
    draw.polygon(mtn_pts, fill=(120, 100, 140, 180))

    # Closer mountains (darker)
    mtn2 = [(0, height)]
    for x in range(0, width + 20, 12):
        base_y = horizon_y + random.randint(30, 50)
        peak_drop = int(60 * abs(math.sin(x * 0.012 + 0.5)))
        y = base_y - peak_drop
        mtn2.append((x, y))
    mtn2.append((width, height))
    draw.polygon(mtn2, fill=(80, 60, 100, 200))

    # Water surface (reflective gold-pink)
    water_y = horizon_y + 60
    for y in range(water_y, height):
        t = (y - water_y) / (height - water_y)
        base = _lerp_color((200, 140, 80), (60, 40, 60), t)
        # Sun reflection shimmer
        sun_dist = abs(sun_x - width // 2)
        for x in range(0, width, 1):
            shimmer = int(30 * math.sin((x - sun_x) * 0.04 + y * 0.1))
            r = max(0, min(255, base[0] + shimmer))
            g = max(0, min(255, base[1] + shimmer // 2))
            b = max(0, min(255, base[2]))
            draw.point((x, y), fill=(r, g, b, 220))

    # Dock: wooden planks leading into water
    dock_cx = width // 2
    dock_y_start = water_y + 20
    dock_len = int(height * 0.3)
    dock_w_near = 80
    dock_w_far = 20
    # Side rails
    for side in [-1, 1]:
        pts = []
        for step in range(dock_len):
            t = step / dock_len
            x = dock_cx + side * int(_lerp(dock_w_near, dock_w_far, t) / 2)
            y = dock_y_start + step
            pts.append((x, y))
        if len(pts) > 1:
            draw.line(pts, fill=(100, 70, 40, 220), width=4)

    # Planks
    for step in range(0, dock_len, 8):
        t = step / dock_len
        xl = dock_cx - int(_lerp(dock_w_near, dock_w_far, t) / 2)
        xr = dock_cx + int(_lerp(dock_w_near, dock_w_far, t) / 2)
        y = dock_y_start + step
        draw.line([(xl, y), (xr, y)], fill=(120, 85, 50, 200), width=3)

    # Lotus flowers (pink circles scattered on water)
    for _ in range(8):
        fx = random.randint(50, width - 50)
        fy = random.randint(water_y + 40, height - 30)
        r = random.randint(8, 18)
        petal_color = (230, 150, 160, 200)
        draw.ellipse([fx - r, fy - r, fx + r, fy + r], fill=petal_color)
        center_r = r // 3
        draw.ellipse([fx - center_r, fy - center_r, fx + center_r, fy + center_r],
                     fill=(255, 220, 180, 255))

    # Birds in sky (simple V shapes)
    for _ in range(5):
        bx = random.randint(50, width - 50)
        by = random.randint(30, horizon_y - 30)
        bw = random.randint(10, 20)
        draw.line([(bx - bw, by + 4), (bx, by), (bx + bw, by + 4)],
                  fill=(60, 40, 40, 180), width=2)

    img = _add_mist_layers(img, horizon_y + 60, intensity=0.3)
    img = img.filter(ImageFilter.GaussianBlur(radius=1))
    return img.convert("RGB")


def create_misty_tree(width=POSTER_WIDTH, height=POSTER_HEIGHT):
    """
    Lone tree in a misty morning field — soft ethereal light.
    Inspired by the Sanskrit/tree reference — pale greens, soft gold,
    atmospheric mist, very light and dreamy.
    """
    img = Image.new("RGB", (width, height))

    # Sky: light periwinkle → soft peach-gold → warm cream
    sky_stops = [
        (160, 170, 200),  # soft blue-grey at top
        (200, 185, 195),  # lavender-pink
        (225, 200, 170),  # peach
        (245, 225, 185),  # warm gold
        (255, 240, 210),  # cream-gold
        (240, 230, 200),  # warm ivory at horizon
    ]
    _multi_stop_gradient(img, sky_stops)

    horizon_y = int(height * 0.50)
    img = img.convert("RGBA")

    # Soft sun — high but misty
    sun_x = int(width * 0.45) + random.randint(-40, 40)
    sun_y = int(height * 0.28)
    img = _add_sun(img, sun_x, sun_y, 60, 350, (255, 250, 220), (255, 230, 180), intensity=0.9)
    img = _add_light_rays(img, sun_x, sun_y, (255, 240, 200), count=10, intensity=0.1)
    img = _add_horizon_glow(img, horizon_y, (240, 220, 170), width=300, intensity=0.5)

    draw = ImageDraw.Draw(img)

    # Ground: soft green-gold with morning light
    for y in range(horizon_y, height):
        t = (y - horizon_y) / (height - horizon_y)
        c = _lerp_color((180, 190, 130), (90, 110, 60), t)
        draw.line([(0, y), (width, y)], fill=c + (255,))

    # Light streaks across ground (sun rays hitting field)
    for i in range(5):
        sx = sun_x + random.randint(-100, 100)
        angle = random.uniform(70, 110)  # nearly vertical
        length = int(height * 0.5)
        ex = sx + int(math.cos(math.radians(angle)) * length)
        ey = horizon_y + length
        alpha = random.randint(20, 50)
        draw.line([(sx, horizon_y - 20), (ex, ey)],
                  fill=(255, 240, 180, alpha), width=random.randint(20, 50))

    # Lone tree in center-left
    tree_x = int(width * 0.52) + random.randint(-60, 60)
    tree_y = horizon_y

    # Trunk
    trunk_h = 200
    trunk_w = 18
    draw.rectangle([tree_x - trunk_w // 2, tree_y - trunk_h,
                    tree_x + trunk_w // 2, tree_y + 15],
                   fill=(80, 60, 40, 230))

    # Canopy (layered ellipses for natural look)
    canopy_cx = tree_x - 10
    canopy_cy = tree_y - trunk_h + 10
    for layer in range(4):
        rw = 160 - layer * 15
        rh = 130 - layer * 12
        cy_offset = layer * 15
        alpha = 200 - layer * 20
        green = _lerp_color((80, 130, 60), (50, 90, 30), layer / 4)
        draw.ellipse([canopy_cx - rw, canopy_cy + cy_offset - rh,
                      canopy_cx + rw, canopy_cy + cy_offset + rh // 2],
                     fill=green + (alpha,))

    # Background trees (distant, lighter)
    for i in range(6):
        tx = random.randint(0, width)
        th = random.randint(80, 130)
        tw = 6
        tree_base = horizon_y + random.randint(0, 10)
        draw.rectangle([tx - tw // 2, tree_base - th, tx + tw // 2, tree_base],
                       fill=(100, 120, 70, 120))
        cr = random.randint(35, 55)
        draw.ellipse([tx - cr, tree_base - th - cr, tx + cr, tree_base - th + cr // 2],
                     fill=(110, 140, 80, 100))

    # Heavy mist at horizon
    img = _add_mist_layers(img, horizon_y - 20, intensity=0.7)
    img = img.filter(ImageFilter.GaussianBlur(radius=1.5))
    return img.convert("RGB")


def create_beach_sunrise(width=POSTER_WIDTH, height=POSTER_HEIGHT):
    """
    Warm beach sunrise with stacked stones — soft rose and gold.
    Inspired by the Tamil stones reference — beautiful pinks and golds,
    calm sea, warm sand.
    """
    img = Image.new("RGB", (width, height))

    # Sky: deep mauve → rose-pink → peach-orange → soft gold
    sky_stops = [
        (100, 60, 90),   # deep mauve-purple
        (180, 90, 110),  # rose-pink
        (220, 130, 100), # salmon
        (240, 170, 110), # peach-gold
        (255, 210, 150), # warm gold
        (255, 235, 195), # pale cream at horizon
    ]
    _multi_stop_gradient(img, sky_stops)

    horizon_y = int(height * 0.45)
    img = img.convert("RGBA")

    # Sun
    sun_x = int(width * 0.5) + random.randint(-60, 60)
    sun_y = horizon_y - 25
    img = _add_sun(img, sun_x, sun_y, 50, 300, (255, 245, 200), (255, 190, 130), intensity=1.2)
    img = _add_light_rays(img, sun_x, sun_y, (255, 215, 150), count=14, intensity=0.15)
    img = _add_horizon_glow(img, horizon_y, (255, 200, 120), width=220, intensity=0.7)

    draw = ImageDraw.Draw(img)

    # Sea (calm, reflective)
    water_y = horizon_y
    for y in range(water_y, int(height * 0.72)):
        t = (y - water_y) / (int(height * 0.72) - water_y)
        # Water colors: gold-pink at top, deeper teal-blue at bottom
        base = _lerp_color((200, 140, 100), (80, 100, 130), t)
        for x in range(width):
            shimmer = int(15 * math.sin(x * 0.05 + y * 0.08))
            r = max(0, min(255, base[0] + shimmer))
            g = max(0, min(255, base[1] + shimmer // 2))
            b = max(0, min(255, base[2]))
            draw.point((x, y), fill=(r, g, b, 240))

    # Sand (warm golden-beige)
    sand_y = int(height * 0.70)
    for y in range(sand_y, height):
        t = (y - sand_y) / (height - sand_y)
        c = _lerp_color((200, 170, 120), (160, 130, 85), t)
        draw.line([(0, y), (width, y)], fill=c + (255,))

    # Wet sand reflection (slightly darker strip near water)
    wet_y = int(height * 0.68)
    for y in range(wet_y, sand_y + 20):
        t = (y - wet_y) / 30
        c = _lerp_color((150, 130, 100), (190, 160, 110), t)
        draw.line([(0, y), (width, y)], fill=c + (255,))

    # Stacked stones (balancing stones)
    stone_cx = width // 2 + random.randint(-60, 60)
    stone_base_y = int(height * 0.68)
    stones = [
        (60, 22),   # bottom: wide, flat
        (50, 18),
        (40, 15),
        (32, 14),
        (25, 12),   # top: smallest
    ]
    stone_colors = [
        (130, 115, 100),
        (110, 100, 90),
        (140, 125, 108),
        (100, 90, 80),
        (120, 108, 96),
    ]
    cy = stone_base_y
    for i, (sw, sh) in enumerate(stones):
        offset = random.randint(-4, 4)
        x0 = stone_cx - sw // 2 + offset
        x1 = stone_cx + sw // 2 + offset
        y0 = cy - sh
        color = stone_colors[i]
        draw.ellipse([x0, y0, x1, cy], fill=color + (250,))
        # Highlight on top
        hl_color = tuple(min(255, c + 30) for c in color)
        draw.ellipse([x0 + 3, y0 + 2, x1 - 3, y0 + sh // 2],
                     fill=hl_color + (120,))
        cy = y0 + 2

    # Small scattered pebbles on beach
    for _ in range(20):
        px = random.randint(30, width - 30)
        py = random.randint(sand_y + 10, height - 20)
        pr = random.randint(3, 8)
        draw.ellipse([px - pr, py - pr // 2, px + pr, py + pr // 2],
                     fill=(150, 135, 110, 200))

    # Gentle wave foam
    wave_y = int(height * 0.695)
    for x in range(0, width, 8):
        wy = wave_y + int(4 * math.sin(x * 0.03))
        draw.ellipse([x - 4, wy - 2, x + 4, wy + 2], fill=(230, 220, 210, 80))

    img = _add_mist_layers(img, horizon_y, intensity=0.2)
    img = img.filter(ImageFilter.GaussianBlur(radius=1.2))
    return img.convert("RGB")


def create_lotus_pond(width=POSTER_WIDTH, height=POSTER_HEIGHT):
    """
    Golden sunrise with lotus flowers — warm, rich colors.
    For Sanskrit yoga quotes — serene, golden, spiritual.
    """
    img = Image.new("RGB", (width, height))

    # Sky: warm coral-gold sunrise
    sky_stops = [
        (90, 50, 80),    # deep rose-purple
        (170, 80, 90),   # coral-rose
        (220, 120, 70),  # warm orange
        (250, 180, 100), # golden
        (255, 220, 150), # pale gold
        (255, 235, 185), # ivory-gold at horizon
    ]
    _multi_stop_gradient(img, sky_stops)

    horizon_y = int(height * 0.43)
    img = img.convert("RGBA")

    # Sun
    sun_x = int(width * 0.5) + random.randint(-20, 20)
    sun_y = horizon_y - 30
    img = _add_sun(img, sun_x, sun_y, 65, 380, (255, 255, 210), (255, 200, 120), intensity=1.4)
    img = _add_light_rays(img, sun_x, sun_y, (255, 225, 150), count=18, intensity=0.2)
    img = _add_horizon_glow(img, horizon_y, (255, 200, 110), width=300, intensity=0.9)

    draw = ImageDraw.Draw(img)

    # Pond water
    water_y = horizon_y
    for y in range(water_y, height):
        t = (y - water_y) / (height - water_y)
        base = _lerp_color((180, 120, 70), (50, 70, 100), t)
        for x in range(width):
            # Sun reflection column
            sun_dist = abs(x - sun_x)
            refl = max(0, int(60 * (1 - sun_dist / (width * 0.4))))
            shimmer = int(20 * math.sin(x * 0.04 + y * 0.07))
            r = max(0, min(255, base[0] + shimmer + refl))
            g = max(0, min(255, base[1] + shimmer // 2 + refl // 3))
            b = max(0, min(255, base[2] + refl // 4))
            draw.point((x, y), fill=(r, g, b, 240))

    # Lotus pads (green circles)
    for _ in range(12):
        lx = random.randint(30, width - 30)
        ly = random.randint(water_y + 50, height - 40)
        lr = random.randint(15, 35)
        draw.ellipse([lx - lr, ly - lr // 2, lx + lr, ly + lr // 2],
                     fill=(60, 110, 50, 200))
        # Cut notch
        notch_angle = random.uniform(0, 2 * math.pi)
        nx = lx + int(lr * math.cos(notch_angle))
        ny = ly + int(lr // 2 * math.sin(notch_angle))
        draw.polygon([(lx, ly), (nx - 5, ny), (nx + 5, ny)], fill=(50, 90, 45, 200))

    # Lotus flowers
    for _ in range(6):
        fx = random.randint(50, width - 50)
        fy = random.randint(water_y + 40, height - 50)
        # Petals
        petal_colors = [(240, 160, 170), (230, 140, 155), (250, 180, 185)]
        for petal in range(8):
            angle = (petal / 8) * 2 * math.pi
            pr = random.randint(10, 16)
            px = fx + int(pr * 0.7 * math.cos(angle))
            py = fy + int(pr * 0.5 * math.sin(angle))
            draw.ellipse([px - 8, py - 10, px + 8, py + 4],
                         fill=random.choice(petal_colors) + (220,))
        # Center
        draw.ellipse([fx - 6, fy - 6, fx + 6, fy + 6], fill=(255, 220, 160, 255))

    # Silhouetted reeds/plants at edges
    for side_x in [random.randint(20, 150), random.randint(width - 150, width - 20)]:
        for _ in range(5):
            rx = side_x + random.randint(-30, 30)
            ry_base = water_y + random.randint(20, 60)
            rh = random.randint(120, 200)
            draw.line([(rx, ry_base), (rx + random.randint(-10, 10), ry_base - rh)],
                      fill=(40, 60, 30, 200), width=3)
            # Seed head
            draw.ellipse([rx - 6, ry_base - rh - 15, rx + 6, ry_base - rh],
                         fill=(60, 40, 20, 180))

    img = _add_mist_layers(img, horizon_y + 20, intensity=0.3)
    img = img.filter(ImageFilter.GaussianBlur(radius=1.2))
    return img.convert("RGB")


def create_flower_meadow(width=POSTER_WIDTH, height=POSTER_HEIGHT):
    """
    Light, airy flower meadow at dawn — soft pastels and warm light.
    For Tamil poetry about beauty and life — joyful, vibrant, light.
    """
    img = Image.new("RGB", (width, height))

    # Sky: soft lilac → pale peach → warm cream
    sky_stops = [
        (140, 120, 165),  # soft lavender
        (190, 150, 175),  # rose-lavender
        (215, 170, 160),  # dusty rose-peach
        (240, 200, 170),  # warm peach
        (255, 225, 190),  # soft golden-peach
        (250, 235, 210),  # cream
    ]
    _multi_stop_gradient(img, sky_stops)

    horizon_y = int(height * 0.48)
    img = img.convert("RGBA")

    # Soft, high sun
    sun_x = int(width * 0.55) + random.randint(-50, 50)
    sun_y = int(height * 0.22)
    img = _add_sun(img, sun_x, sun_y, 50, 320, (255, 250, 220), (255, 220, 190), intensity=0.8)
    img = _add_horizon_glow(img, horizon_y, (235, 205, 160), width=250, intensity=0.4)

    draw = ImageDraw.Draw(img)

    # Meadow base
    for y in range(horizon_y, height):
        t = (y - horizon_y) / (height - horizon_y)
        c = _lerp_color((175, 195, 130), (90, 115, 60), t)
        draw.line([(0, y), (width, y)], fill=c + (255,))

    # Background flowers and grass (small, blurry for depth)
    for _ in range(80):
        fx = random.randint(0, width)
        fy = random.randint(horizon_y, int(height * 0.75))
        fs = random.randint(3, 8)
        colors = [(230, 180, 200), (255, 200, 150), (200, 220, 180),
                  (255, 220, 160), (200, 180, 230)]
        draw.ellipse([fx - fs, fy - fs, fx + fs, fy + fs],
                     fill=random.choice(colors) + (160,))
        # Stem
        draw.line([(fx, fy + fs), (fx + random.randint(-3, 3), fy + fs + random.randint(10, 20))],
                  fill=(80, 110, 50, 150), width=1)

    # Foreground flowers (larger, more detailed)
    for _ in range(40):
        fx = random.randint(20, width - 20)
        fy = random.randint(int(height * 0.65), height - 20)
        fr = random.randint(8, 18)
        petal_col = random.choice([
            (255, 160, 180), (255, 200, 120), (230, 160, 220),
            (255, 230, 160), (200, 230, 200), (255, 180, 140)
        ])
        # 5 petals
        for p in range(5):
            angle = (p / 5) * 2 * math.pi
            px = fx + int(fr * math.cos(angle))
            py = fy + int(fr * 0.8 * math.sin(angle))
            draw.ellipse([px - fr // 2, py - fr // 2,
                          px + fr // 2, py + fr // 2],
                         fill=petal_col + (220,))
        # Center
        draw.ellipse([fx - 5, fy - 5, fx + 5, fy + 5], fill=(255, 220, 100, 255))

    # Tall grass stems
    for _ in range(30):
        gx = random.randint(0, width)
        gy_base = random.randint(int(height * 0.75), height)
        gh = random.randint(60, 150)
        draw.line([(gx, gy_base), (gx + random.randint(-15, 15), gy_base - gh)],
                  fill=(80, 110, 50, 200), width=2)

    img = _add_mist_layers(img, horizon_y - 10, intensity=0.3)
    img = img.filter(ImageFilter.GaussianBlur(radius=1.2))
    return img.convert("RGB")


def create_yoga_dawn(width=POSTER_WIDTH, height=POSTER_HEIGHT):
    """
    Yoga silhouette against rich sunrise — warm gold and deep amber.
    For Sanskrit yoga/spiritual quotes — serene, golden, aspirational.
    """
    img = Image.new("RGB", (width, height))

    # Sky: deep amber-rose → brilliant gold → pale sunrise
    sky_stops = [
        (80, 35, 60),    # deep plum
        (160, 65, 70),   # rose-red
        (215, 115, 55),  # warm amber
        (245, 175, 80),  # golden
        (255, 215, 140), # pale gold
        (255, 235, 190), # warm cream
    ]
    _multi_stop_gradient(img, sky_stops)

    horizon_y = int(height * 0.62)
    img = img.convert("RGBA")

    # Large, brilliant sun
    sun_x = width // 2 + random.randint(-20, 20)
    sun_y = horizon_y - 30
    img = _add_sun(img, sun_x, sun_y, 80, 400, (255, 255, 220), (255, 200, 100), intensity=1.5)
    img = _add_light_rays(img, sun_x, sun_y, (255, 220, 140), count=20, intensity=0.2)
    img = _add_horizon_glow(img, horizon_y, (255, 195, 100), width=280, intensity=1.0)

    draw = ImageDraw.Draw(img)

    # Flat ground (dark silhouette)
    draw.rectangle([0, horizon_y, width, height], fill=(20, 12, 18, 255))

    # Distant landscape silhouette (gentle hills)
    hill_pts = [(0, height)]
    for x in range(0, width + 20, 15):
        y = horizon_y + random.randint(-5, 15)
        hill_pts.append((x, y))
    hill_pts.append((width, height))
    draw.polygon(hill_pts, fill=(15, 8, 14, 255))

    # Yoga figure — warrior/tree pose silhouette
    cx = width // 2
    cy = horizon_y

    # Standing meditation pose: arms raised in Namaste overhead
    body_color = (10, 5, 10, 255)

    # Legs: standing, feet apart
    draw.line([(cx, cy - 10), (cx - 20, cy)], fill=body_color, width=10)  # left leg
    draw.line([(cx, cy - 10), (cx + 20, cy)], fill=body_color, width=10)  # right leg

    # Torso
    draw.line([(cx, cy - 10), (cx, cy - 90)], fill=body_color, width=12)

    # Arms raised in prayer/Namaste
    draw.line([(cx, cy - 70), (cx - 55, cy - 110)], fill=body_color, width=9)  # left arm
    draw.line([(cx, cy - 70), (cx + 55, cy - 110)], fill=body_color, width=9)  # right arm
    # Hands together overhead
    draw.line([(cx - 55, cy - 110), (cx + 55, cy - 110)], fill=body_color, width=5)

    # Head
    head_r = 22
    draw.ellipse([cx - head_r, cy - 90 - head_r * 2, cx + head_r, cy - 90],
                 fill=body_color)

    img = _add_mist_layers(img, horizon_y - 10, intensity=0.25)
    img = img.filter(ImageFilter.GaussianBlur(radius=1.2))
    return img.convert("RGB")


# ═══════════════════════════════════════════════════
# Theme mapping
# ═══════════════════════════════════════════════════

BACKGROUND_GENERATORS = {
    "sunrise_path": create_sunrise_path,
    "mountain_lake": create_mountain_lake,
    "misty_tree": create_misty_tree,
    "beach_sunrise": create_beach_sunrise,
    "lotus_pond": create_lotus_pond,
    "flower_meadow": create_flower_meadow,
    "yoga_dawn": create_yoga_dawn,
    # Legacy aliases
    "sunrise_gradient": create_sunrise_path,
    "mountain_silhouette": create_misty_tree,
    "flowing_stream": create_mountain_lake,
    "flower_field": create_flower_meadow,
    "yoga_silhouette": create_yoga_dawn,
    "misty_dawn": create_beach_sunrise,
}


def generate_background(theme, width=POSTER_WIDTH, height=POSTER_HEIGHT):
    """
    Return a background image for the given theme.

    Priority:
      1. Unsplash real photo (if API key set and fetch succeeds / cache hit)
      2. Programmatic fallback (always works, no key needed)
    """
    # Try Unsplash first
    try:
        from photo_fetcher import get_background_photo
        photo = get_background_photo(theme)
        if photo is not None:
            if photo.size != (width, height):
                photo = photo.resize((width, height), Image.LANCZOS)
            return photo
    except Exception as e:
        print(f"ℹ️  Unsplash unavailable ({e}), using programmatic background")

    # Fallback: programmatic background
    if theme not in BACKGROUND_GENERATORS:
        theme = "sunrise_path"
    return BACKGROUND_GENERATORS[theme](width, height)


if __name__ == "__main__":
    import os
    from config import POSTERS_DIR
    os.makedirs(POSTERS_DIR, exist_ok=True)
    for name, fn in [
        ("sunrise_path", create_sunrise_path),
        ("mountain_lake", create_mountain_lake),
        ("misty_tree", create_misty_tree),
        ("beach_sunrise", create_beach_sunrise),
        ("lotus_pond", create_lotus_pond),
        ("flower_meadow", create_flower_meadow),
        ("yoga_dawn", create_yoga_dawn),
    ]:
        img = fn()
        path = os.path.join(POSTERS_DIR, f"bg_{name}.png")
        img.save(path)
        print(f"Saved: {path}")
