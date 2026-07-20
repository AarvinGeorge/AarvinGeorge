"""Idle animation for Aarvin's pixel-art room. Seamless 24-frame loop."""
import math
from PIL import Image

SRC = 'assets/room-source.png'  # run from repo root: python tools/animate_room.py
OUT_GIF = 'assets/aarvin-room.gif'
N = 24          # frames
DUR = 110       # ms per frame (~9fps)
SCALE = 3       # output upscale (nearest)

base = Image.open(SRC).convert('RGBA')
W, H = base.size
bpx = base.load()

SCREEN_BLUES = {(105,157,189),(186,223,238),(154,195,214)}
WINDOW_BLUES = {(186,223,238),(154,195,214)}
GREEN = (85,139,74)
CYAN = (43,178,220)
SILVER = {(162,167,173),(131,132,135)}
HAT = (56,81,153)

def clamp(v): return max(0, min(255, int(v)))

def mask_pixels(x0,y0,x1,y1, pred):
    pts = []
    for y in range(y0,y1):
        for x in range(x0,x1):
            r,g,b,a = bpx[x,y]
            if a>0 and pred(r,g,b):
                pts.append((x,y,(r,g,b,a)))
    return pts

def bg_fill_color(x, y, mask_set):
    """Nearest non-masked opaque neighbor, searching down then up then sides."""
    for dx,dy in [(0,1),(0,2),(0,-1),(0,-2),(1,0),(-1,0),(0,3),(1,1),(-1,1)]:
        nx,ny = x+dx, y+dy
        if 0<=nx<W and 0<=ny<H and (nx,ny) not in mask_set:
            r,g,b,a = bpx[nx,ny]
            if a>0: return (r,g,b,a)
    return bpx[x,y]

# --- Region masks ---
screens = mask_pixels(50,64,86,94, lambda r,g,b:(r,g,b) in SCREEN_BLUES)
window  = mask_pixels(80,44,96,60, lambda r,g,b:(r,g,b) in WINDOW_BLUES)
printer = mask_pixels(20,95,42,115, lambda r,g,b:(r,g,b)==CYAN)
arm     = mask_pixels(52,97,73,118, lambda r,g,b:(r,g,b) in SILVER)
hat     = mask_pixels(72,72,91,89, lambda r,g,b:(r,g,b)==HAT)

plants = []
for (x0,y0,x1,y1,phase) in [(61,46,72,57,0.0),(117,39,127,50,0.35),(175,69,188,81,0.6),(95,144,111,161,0.15),(139,126,149,140,0.8)]:
    pts = mask_pixels(x0,y0,x1,y1, lambda r,g,b:(r,g,b)==GREEN)
    if pts:
        ys = [p[1] for p in pts]
        cutoff = min(ys) + int((max(ys)-min(ys))*0.65)  # top 65% sways
        sway = [p for p in pts if p[1] <= cutoff]
        plants.append((sway, phase))

# Precompute background fills for pixels that MOVE (plants, arm, hat)
def make_bg(pts):
    s = {(x,y) for x,y,_ in pts}
    return {(x,y): bg_fill_color(x,y,s) for x,y,_ in pts}

plant_bgs = [make_bg(p[0]) for p in plants]
arm_bg = make_bg(arm)
hat_bg = make_bg(hat)

frames = []
for f in range(N):
    t = f / N
    im = base.copy()
    px = im.load()

    # 1. Monitor flicker: gentle global sine + moving scanline + pixel shimmer
    glow = 1.0 + 0.06*math.sin(2*math.pi*(t*2))          # two pulses per loop
    ys_scr = [p[1] for p in screens]
    y_min, y_max = min(ys_scr), max(ys_scr)
    scan_y = y_min + int((y_max-y_min+1) * t) % (y_max-y_min+1)
    for x,y,(r,g,b,a) in screens:
        k = glow
        if y == scan_y or y == scan_y+1: k += 0.18       # scanline band
        if (x*7 + y*13 + f*5) % 29 == 0: k -= 0.22       # sparse dark pixel flicker (code changing)
        px[x,y] = (clamp(r*k), clamp(g*k), clamp(b*k), a)

    # 2. Window shimmer: one slow period
    wk = 1.0 + 0.09*math.sin(2*math.pi*t)
    for x,y,(r,g,b,a) in window:
        px[x,y] = (clamp(r*wk), clamp(g*wk), clamp(b*wk), a)

    # 3. Printer glow pulse: like layers being fused
    pk = 1.0 + 0.16*math.sin(2*math.pi*(t*3))            # three pulses
    for x,y,(r,g,b,a) in printer:
        px[x,y] = (clamp(r*pk), clamp(g*pk), clamp(b*pk), a)

    # 4. Plants sway: 1px horizontal, per-plant phase
    for (sway, phase), bg in zip(plants, plant_bgs):
        off = round(math.sin(2*math.pi*(t + phase)))
        if off != 0:
            for (x,y), c in bg.items(): px[x,y] = c
            for x,y,c in sway:
                nx = x + off
                if 0 <= nx < W: px[nx,y] = c

    # 5. Robot arm: slow 1px dip mid-loop (working motion)
    arm_off = 1 if 8 <= f <= 15 else 0
    if arm_off:
        for (x,y), c in arm_bg.items(): px[x,y] = c
        for x,y,c in arm:
            ny = y + arm_off
            if ny < H: px[x,ny] = c

    # 6. Wizard hat: breathing bob, 1px down second half of loop
    hat_off = 1 if 12 <= f <= 23 else 0
    if hat_off:
        for (x,y), c in hat_bg.items(): px[x,y] = c
        for x,y,c in hat:
            ny = y + hat_off
            if ny < H: px[x,ny] = c

    big = im.resize((W*SCALE, H*SCALE), Image.NEAREST)
    frames.append(big)

# --- Export GIF with transparency ---
out = []
for fr in frames:
    alpha = fr.getchannel('A')
    p = fr.convert('RGB').convert('P', palette=Image.ADAPTIVE, colors=255)
    mask = Image.eval(alpha, lambda a: 255 if a <= 128 else 0)
    p.paste(255, mask)
    out.append(p)

out[0].save(OUT_GIF, save_all=True, append_images=out[1:], duration=DUR, loop=0,
            transparency=255, disposal=2, optimize=False)

import os
print('GIF saved:', OUT_GIF, f'{os.path.getsize(OUT_GIF)/1024:.0f} KB, {N} frames @ {DUR}ms, {frames[0].size}')

# Preview stills for visual check

