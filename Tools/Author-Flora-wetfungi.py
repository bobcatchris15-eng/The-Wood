"""Author aquatic plants and fungi for The-Wood (catalogue: Docs/FloraCatalog.md).

Run:
  "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b --factory-startup -P Tools/Author-Flora-wetfungi.py

Output (ArtSource/Authored/Flora/wetfungi):
  <species>_v<n>.glb / .fbx          one combined mesh per variant, metres
  textures/<species>_v<n>_<part>_alb.png / _nrm.png   512 px albedo + tangent normal
  previews/<species>_v<n>.png        Cycles preview over ground / water / trunk
  README.md
Origins: water_lily, duckweed_mat, pondweed at water surface z=0 (pondweed roots at z=-0.5).
bracket_fungus at attach face, +X outward. puffball_cluster, ground_fungus_patch at ground z=0.
"""

import bpy
import math
import os
import random
import struct
import zlib
from mathutils import Vector

SEED = 9017
TAU = 2.0 * math.pi
HALF_PI = 0.5 * math.pi

try:
    _here = os.path.abspath(__file__)
except NameError:
    _here = os.path.join(os.getcwd(), "Tools", "Author-Flora-wetfungi.py")
REPO = os.path.dirname(os.path.dirname(_here))
OUT = os.path.join(REPO, "ArtSource", "Authored", "Flora", "wetfungi")
TEX = os.path.join(OUT, "textures")
PREV = os.path.join(OUT, "previews")

TEX_RES = 512
NRM_STRENGTH = 30.0
PREVIEW_RES = 640
PREVIEW_SAMPLES = 48


# ---------------------------------------------------------------- math

def clamp(x, lo=0.0, hi=1.0):
    return lo if x < lo else (hi if x > hi else x)


def sstep(e0, e1, x):
    t = clamp((x - e0) / (e1 - e0))
    return t * t * (3.0 - 2.0 * t)


def mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def scale(c, s):
    return tuple(x * s for x in c)


def srgb_lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def mul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def unit(a):
    l = math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])
    if l < 1e-9:
        return (0.0, 0.0, 1.0)
    return (a[0] / l, a[1] / l, a[2] / l)


# ---------------------------------------------------------------- noise

class Noise:
    """Periodic value noise, fBm over octaves given as lattice sizes."""

    def __init__(self, seed, cells=(4, 8, 16)):
        rng = random.Random(seed)
        self.oct = []
        amp = 1.0
        for n in cells:
            self.oct.append((n, amp, [rng.random() for _ in range(n * n)]))
            amp *= 0.5
        self.tot = sum(a for _, a, _ in self.oct)

    def __call__(self, u, t):
        s = 0.0
        for n, a, lat in self.oct:
            X = u * n
            Y = t * n
            x0 = int(X)
            y0 = int(Y)
            fx = X - x0
            fy = Y - y0
            fx = fx * fx * (3.0 - 2.0 * fx)
            fy = fy * fy * (3.0 - 2.0 * fy)
            x0 %= n
            y0 %= n
            x1 = (x0 + 1) % n
            y1 = (y0 + 1) % n
            a0 = lat[y0 * n + x0]
            b0 = lat[y0 * n + x1]
            c0 = lat[y1 * n + x0]
            d0 = lat[y1 * n + x1]
            top = a0 + (b0 - a0) * fx
            bot = c0 + (d0 - c0) * fx
            s += a * (top + (bot - top) * fy)
        return s / self.tot


# ---------------------------------------------------------------- textures

def normal_map(hg, W, H, strength):
    out = [0.0] * (W * H * 4)
    for j in range(H):
        jm = ((j - 1) % H) * W
        jp = ((j + 1) % H) * W
        jc = j * W
        for i in range(W):
            im = (i - 1) % W
            ip = (i + 1) % W
            dx = (hg[jc + ip] - hg[jc + im]) * strength
            dy = (hg[jp + i] - hg[jm + i]) * strength
            l = math.sqrt(dx * dx + dy * dy + 1.0)
            k = (jc + i) * 4
            out[k] = -dx / l * 0.5 + 0.5
            out[k + 1] = -dy / l * 0.5 + 0.5
            out[k + 2] = (1.0 / l) * 0.5 + 0.5
            out[k + 3] = 1.0
    return out


def write_png(path, W, H, px):
    """RGBA 8-bit PNG from a flat float list (0..1), no Blender image save path (it writes zeros for generated images)."""
    raw = bytearray()
    row = W * 4
    for j in range(H):
        raw.append(0)
        raw.extend(bytes(min(255, int(x * 255.0 + 0.5)) for x in px[j * row:(j + 1) * row]))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 6, 0, 0, 0)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
                + chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b""))


def make_pair(name, shade, res=TEX_RES):
    """shade(u, t) -> (r, g, b, a, h). Writes albedo + normal PNGs; returns (alb, nrm) images."""
    W = H = res
    alb = [0.0] * (W * H * 4)
    hg = [0.0] * (W * H)
    for j in range(H):
        t = (j + 0.5) / H
        for i in range(W):
            u = (i + 0.5) / W
            r, g, b, a, h = shade(u, t)
            k = j * W + i
            alb[4 * k] = clamp(r)
            alb[4 * k + 1] = clamp(g)
            alb[4 * k + 2] = clamp(b)
            alb[4 * k + 3] = clamp(a)
            hg[k] = h
    nrm = normal_map(hg, W, H, NRM_STRENGTH)
    alb_path = os.path.join(TEX, name + "_alb.png")
    nrm_path = os.path.join(TEX, name + "_nrm.png")
    write_png(alb_path, W, H, alb)
    write_png(nrm_path, W, H, nrm)
    ai = bpy.data.images.load(alb_path)
    ai.colorspace_settings.name = "sRGB"
    ni = bpy.data.images.load(nrm_path)
    ni.colorspace_settings.name = "Non-Color"
    return ai, ni


def shade_pad(var):
    N = Noise(SEED + 10 + var, (4, 8, 16))
    base = (0.20, 0.44, 0.16) if var == 1 else (0.13, 0.33, 0.14)
    edge = (0.45, 0.60, 0.25) if var == 1 else (0.55, 0.22, 0.13)
    edge_amt = 0.35 if var == 1 else 0.75

    def f(u, t):
        n = N(u, t)
        rv = abs(math.sin(u * 24.0 * math.pi))
        vein = 1.0 - sstep(0.0, 0.10, rv)
        mg = sstep(0.82, 1.0, t)
        col = mix(base, scale(base, 1.35), vein * 0.6)
        col = mix(col, edge, mg * edge_amt)
        col = scale(col, 0.85 + 0.3 * n)
        return col[0], col[1], col[2], 1.0, vein * 0.6 + n * 0.25

    return f


def shade_petal(pink):
    N = Noise(SEED + (40 if pink else 30), (4, 8))
    white = (0.96, 0.95, 0.92)
    pk = (0.95, 0.52, 0.68)
    yel = (0.98, 0.80, 0.16)

    def f(u, t):
        n = N(u, t)
        rib = 1.0 - sstep(0.0, 0.08, abs(u - 0.5))
        base = mix(white, pk, sstep(0.3, 1.0, t)) if pink else white
        col = mix(base, yel, 1.0 - sstep(0.15, 0.32, t))
        col = scale(col, (0.92 + 0.08 * n) * (1.0 - 0.10 * rib))
        return col[0], col[1], col[2], 1.0, rib * 0.35 + n * 0.15

    return f


def shade_duck(var):
    N = Noise(SEED + 50 + var, (4, 8))
    cells = 24
    rng = random.Random(SEED + 60 + var)
    par = [[(rng.uniform(-0.10, 0.10), rng.uniform(-0.10, 0.10), rng.uniform(0.32, 0.38),
             rng.uniform(-1.0, 1.0)) for _ in range(cells)] for _ in range(cells)]
    green = (0.30, 0.62, 0.18) if var == 1 else (0.56, 0.72, 0.22)
    rim = (0.66, 0.42, 0.14) if var == 1 else (0.78, 0.22, 0.12)
    rim_amt = 0.25 if var == 1 else 0.70

    def f(u, t):
        gx = u * cells
        gy = t * cells
        ci = int(gx)
        cj = int(gy)
        jx, jy, r, s = par[cj][ci]
        dx = gx - (ci + 0.5 + jx)
        dy = gy - (cj + 0.5 + jy)
        d = math.sqrt(dx * dx + dy * dy)
        alpha = 1.0 - sstep(r - 0.03, r + 0.02, d)
        rr = d / r
        dome = math.sqrt(max(0.0, 1.0 - rr * rr))
        col = mix(green, rim, sstep(0.55, 0.95, rr) * rim_amt)
        n = N(u, t)
        col = scale(col, (1.0 + 0.08 * s) * (0.9 + 0.2 * n))
        return col[0], col[1], col[2], alpha, dome * 0.8 + n * 0.1

    return f


def shade_strand(var):
    N = Noise(SEED + 150 + var, (4, 8, 16))
    base = (0.26, 0.44, 0.16) if var == 1 else (0.38, 0.42, 0.18)

    def f(u, t):
        n = N(u, t)
        d = abs(u - 0.5) * 2.0
        rib = 1.0 - sstep(0.0, 0.25, d)
        st = 0.5 + 0.5 * math.cos(u * TAU * 5.0)
        col = mix(base, scale(base, 1.3), rib * 0.5)
        col = scale(col, (1.0 - 0.25 * sstep(0.6, 1.0, d)) * (0.88 + 0.2 * n))
        return col[0], col[1], col[2], 1.0, rib * 0.5 + st * 0.15 + n * 0.1

    return f


def shade_bracket(var):
    N = Noise(SEED + 70 + var, (4, 8, 16))
    cream = (0.93, 0.87, 0.72)
    zone = (0.70, 0.40, 0.16) if var == 1 else (0.52, 0.49, 0.44)

    def f(u, t):
        n = N(u, t)
        z = sstep(0.35, 0.80, n + 0.25 * t)
        col = mix(cream, zone, z * 0.85)
        lines = 1.0 - sstep(0.0, 0.10, (t * 9.0 + 0.25 * n) % 1.0)
        col = scale(col, (1.0 - 0.20 * lines) * (0.9 + 0.1 * n))
        return col[0], col[1], col[2], 1.0, n * 0.3 - lines * 0.4

    return f


def shade_puff(var):
    N = Noise(SEED + 80 + var, (4, 8, 16))
    S = Noise(SEED + 90 + var, (32, 64))
    base = (0.94, 0.90, 0.79) if var == 1 else (0.84, 0.74, 0.56)
    tone = (0.64, 0.57, 0.44)

    def f(u, t):
        n = N(u, t)
        s = S(u, t)
        col = mix(base, tone, sstep(0.45, 0.75, n) * 0.5)
        col = mix(col, tone, sstep(0.68, 0.80, s) * 0.5)
        col = scale(col, 0.92 + 0.08 * s)
        return col[0], col[1], col[2], 1.0, s * 0.5 + n * 0.3

    return f


CAP = {
    "brown": ((0.42, 0.27, 0.14), (0.28, 0.18, 0.10)),
    "ochre": ((0.86, 0.60, 0.24), (0.66, 0.42, 0.14)),
    "red": ((0.80, 0.10, 0.07), (0.62, 0.06, 0.05)),
}


def shade_cap(kind, var):
    k = list(CAP).index(kind)
    N = Noise(SEED + 100 + 7 * var + k, (4, 8))
    S = Noise(SEED + 130 + 7 * var + k, (16, 32))
    base, alt = CAP[kind]

    def f(u, t):
        n = N(u, t)
        s = S(u, t)
        col = mix(base, alt, sstep(0.40, 0.70, n))
        if kind == "red":
            spot = sstep(0.60, 0.66, s)
            col = mix(col, (0.97, 0.96, 0.92), spot)
            h = spot * 0.5 + n * 0.2
        else:
            h = s * 0.35 + n * 0.3
        col = scale(col, (0.90 + 0.10 * s) * (0.85 + 0.15 * t))
        return col[0], col[1], col[2], 1.0, h

    return f


def shade_stem(var):
    N = Noise(SEED + 140 + var, (4, 8))

    def f(u, t):
        n = N(u, t)
        st = 0.5 + 0.5 * math.cos(u * TAU * 6.0)
        col = scale((0.93, 0.89, 0.78), 0.92 + 0.08 * n + 0.03 * st)
        return col[0], col[1], col[2], 1.0, st * 0.15 + n * 0.2

    return f


# ---------------------------------------------------------------- materials

def mk_mat(name, pair, rough=0.6, alpha=False):
    alb, nrm = pair
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    ta = nt.nodes.new("ShaderNodeTexImage")
    ta.image = alb
    nt.links.new(ta.outputs["Color"], bsdf.inputs["Base Color"])
    tn = nt.nodes.new("ShaderNodeTexImage")
    tn.image = nrm
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = rough
    if alpha:
        nt.links.new(ta.outputs["Alpha"], bsdf.inputs["Alpha"])
        try:
            m.blend_method = "CLIP"
        except Exception:
            pass
        try:
            m.surface_render_method = "DITHERED"
        except Exception:
            pass
    try:
        m.use_backface_culling = False
    except Exception:
        pass
    return m


def mat_set(tag, specs):
    out = []
    for part, shade, rough, alpha in specs:
        pair = make_pair(tag + "_" + part, shade)
        out.append(mk_mat(tag + "_" + part, pair, rough, alpha))
    return out


def mk_flat(name, rgb, rough):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = tuple(srgb_lin(c) for c in rgb) + (1.0,)
    b.inputs["Roughness"].default_value = rough
    return m


# ---------------------------------------------------------------- geometry

class Bld:
    """Verts carry their own UV. Faces are tris or quads with a material index."""

    def __init__(self):
        self.v = []
        self.uv = []
        self.f = []
        self.m = []

    def vert(self, p, uv=(0.0, 0.0)):
        self.v.append((p[0], p[1], p[2]))
        self.uv.append((uv[0], uv[1]))
        return len(self.v) - 1

    def face(self, idx, mat):
        self.f.append(tuple(idx))
        self.m.append(mat)

    def fan(self, c, ring, mat):
        for k in range(len(ring) - 1):
            self.face((c, ring[k], ring[k + 1]), mat)

    def grid(self, rows, mat):
        for i in range(len(rows) - 1):
            a = rows[i]
            b = rows[i + 1]
            for k in range(len(a) - 1):
                self.face((a[k], a[k + 1], b[k + 1], b[k]), mat)

    def tris(self):
        return sum(len(f) - 2 for f in self.f)


def lily_pad(bl, c, R, notch, curl, mat, rot, rings=4, seg=28):
    """Round pad with a notch wedge removed; rim lifted by curl (fraction of R)."""
    t0 = notch * 0.5
    t1 = TAU - notch * 0.5
    cen = bl.vert(c, (0.5, 0.0))
    rows = []
    for i in range(1, rings + 1):
        r = R * i / rings
        z = c[2] + curl * R * (r / R) ** 2
        row = []
        for k in range(seg + 1):
            u = k / seg
            th = rot + t0 + (t1 - t0) * u
            row.append(bl.vert((c[0] + r * math.cos(th), c[1] + r * math.sin(th), z), (u, r / R)))
        rows.append(row)
    bl.fan(cen, rows[0], mat)
    bl.grid(rows, mat)


def lily_flower(bl, c, rad, petals, rng, mat):
    cen = bl.vert((c[0], c[1], c[2] + 0.004), (0.5, 0.0))
    ph0 = rng.uniform(0, TAU)
    for k in range(petals):
        phi = ph0 + TAU * k / petals
        dx, dy = math.cos(phi), math.sin(phi)
        px, py = -dy, dx
        L = rad * rng.uniform(0.9, 1.0)
        w = rad * 0.32
        bx, by = c[0] + dx * L * 0.62, c[1] + dy * L * 0.62
        lp = bl.vert((bx + px * w, by + py * w, c[2] + 0.012), (0.0, 0.55))
        rp = bl.vert((bx - px * w, by - py * w, c[2] + 0.012), (1.0, 0.55))
        tp = bl.vert((c[0] + dx * L, c[1] + dy * L, c[2] + 0.026), (0.5, 1.0))
        bl.face((cen, rp, tp, lp), mat)


def ribbon(bl, pts, widths, mat):
    rows = []
    n = len(pts)
    for i, p in enumerate(pts):
        a = pts[min(i + 1, n - 1)]
        b = pts[max(i - 1, 0)]
        t = unit(sub(a, b))
        ref = (0.0, 0.0, 1.0) if abs(t[2]) < 0.99 else (1.0, 0.0, 0.0)
        s = unit(cross(t, ref))
        w = widths[i] * 0.5
        vv = i / (n - 1)
        L = bl.vert(add(p, mul(s, w)), (0.0, vv))
        R = bl.vert(add(p, mul(s, -w)), (1.0, vv))
        rows.append((L, R))
    for i in range(n - 1):
        bl.face((rows[i][0], rows[i][1], rows[i + 1][1], rows[i + 1][0]), mat)


def shelf(bl, ox, oy, oz, W, H, D, droop, mat, rings=6, seg=24):
    """Half-ellipsoid bracket: flat back on x=0 (origin = attach centre), tip at x=D, droop about Y."""
    ca, sa = math.cos(droop), math.sin(droop)

    def P(x, y, z):
        return (ox + x * ca + z * sa, oy + y, oz - x * sa + z * ca)

    tip = bl.vert(P(D, 0.0, 0.0), (0.5, 0.0))
    rows = []
    for i in range(1, rings + 1):
        a = HALF_PI * i / rings
        row = []
        for k in range(seg + 1):
            b = TAU * k / seg
            p = P(D * math.cos(a), W * math.sin(a) * math.cos(b), H * math.sin(a) * math.sin(b))
            row.append(bl.vert(p, (k / seg, i / rings)))
        rows.append(row)
    bl.fan(tip, rows[0], mat)
    bl.grid(rows, mat)
    back = bl.vert(P(0.0, 0.0, 0.0), (0.5, 1.0))
    bl.fan(back, rows[-1], mat)


def sphere(bl, c, rx, rz, mat, rings=8, seg=14):
    top = bl.vert((c[0], c[1], c[2] + rz), (0.5, 1.0))
    rows = []
    for i in range(1, rings):
        phi = math.pi * i / rings
        z = c[2] + rz * math.cos(phi)
        r = rx * math.sin(phi)
        rows.append([bl.vert((c[0] + r * math.cos(TAU * k / seg), c[1] + r * math.sin(TAU * k / seg), z),
                             (k / seg, 1.0 - i / rings)) for k in range(seg + 1)])
    bot = bl.vert((c[0], c[1], c[2] - rz), (0.5, 0.0))
    bl.fan(top, rows[0], mat)
    bl.grid(rows, mat)
    bl.fan(bot, rows[-1], mat)


def dome(bl, c, rx, rz, mat, rings=4, seg=14):
    """Upper half-ellipsoid standing on z=c[2] with a flat underside (mushroom cap)."""
    top = bl.vert((c[0], c[1], c[2] + rz), (0.5, 0.0))
    rows = []
    for i in range(1, rings + 1):
        phi = HALF_PI * i / rings
        z = c[2] + rz * math.cos(phi)
        r = rx * math.sin(phi)
        rows.append([bl.vert((c[0] + r * math.cos(TAU * k / seg), c[1] + r * math.sin(TAU * k / seg), z),
                             (k / seg, i / rings)) for k in range(seg + 1)])
    bl.fan(top, rows[0], mat)
    bl.grid(rows, mat)
    cen = bl.vert((c[0], c[1], c[2]), (0.5, 1.0))
    bl.fan(cen, rows[-1], mat)


def cyl(bl, base, top, r0, r1, sides, mat):
    rb = [bl.vert((base[0] + r0 * math.cos(TAU * k / sides), base[1] + r0 * math.sin(TAU * k / sides), base[2]),
                  (k / sides, 0.0)) for k in range(sides + 1)]
    rt = [bl.vert((top[0] + r1 * math.cos(TAU * k / sides), top[1] + r1 * math.sin(TAU * k / sides), top[2]),
                  (k / sides, 1.0)) for k in range(sides + 1)]
    bl.grid([rb, rt], mat)


# ---------------------------------------------------------------- builders

def build_lily(var, rng):
    bl = Bld()
    n = 4 if var == 1 else 5
    pads = []
    tries = 0
    while len(pads) < n and tries < 2000:
        tries += 1
        ang = rng.uniform(0, TAU)
        r = 0.32 * math.sqrt(rng.random())
        x, y = r * math.cos(ang), r * math.sin(ang)
        R = rng.uniform(0.12, 0.17)
        if all(math.hypot(x - p[0], y - p[1]) > R + p[2] + 0.02 for p in pads):
            pads.append((x, y, R))
    for (x, y, R) in pads:
        lily_pad(bl, (x, y, 0.004), R, rng.uniform(0.45, 0.8), rng.uniform(0.05, 0.12), 0,
                 rng.uniform(0, TAU))
    # flowers: (pad index, material index) — 1 white, 2 pink
    specs = [(0, 1), (2, 1)] if var == 1 else [(1, 1), (3, 2)]
    for pi, mi in specs:
        if pi >= len(pads):
            continue
        x, y, R = pads[pi]
        ang = rng.uniform(0, TAU)
        c = (x + math.cos(ang) * 0.4 * R, y + math.sin(ang) * 0.4 * R, 0.02)
        lily_flower(bl, c, rng.uniform(0.035, 0.045), rng.choice((6, 7)), rng, mi)
    return bl


def build_duck(var, rng):
    bl = Bld()
    s = 0.5
    a = bl.vert((-s, -s, 0.002), (0.0, 0.0))
    b = bl.vert((s, -s, 0.002), (1.0, 0.0))
    c = bl.vert((s, s, 0.002), (1.0, 1.0))
    d = bl.vert((-s, s, 0.002), (0.0, 1.0))
    bl.face((a, b, c, d), 0)
    return bl


def build_pond(var, rng):
    bl = Bld()
    n = 10 if var == 1 else 14
    for _ in range(n):
        ang = rng.uniform(0, TAU)
        r = 0.22 * math.sqrt(rng.random())
        bx, by = r * math.cos(ang), r * math.sin(ang)
        sway = rng.uniform(0.02, 0.08)
        sa = rng.uniform(0, TAU)
        wd = rng.uniform(0.018, 0.026)
        steps = 8
        pts = []
        ws = []
        for i in range(steps + 1):
            t = i / steps
            bend = sway * t * t
            pts.append((bx + bend * math.cos(sa), by + bend * math.sin(sa), -0.5 + 0.5 * t))
            ws.append(wd * (1.0 - 0.5 * t))
        ribbon(bl, pts, ws, 0)
        cx, cy = pts[-1][0], pts[-1][1]
        ly = rng.uniform(0, TAU)
        L = rng.uniform(0.025, 0.045)
        leaf = [(cx - math.cos(ly) * L, cy - math.sin(ly) * L, 0.001),
                (cx, cy, 0.001),
                (cx + math.cos(ly) * L, cy + math.sin(ly) * L, 0.001)]
        ribbon(bl, leaf, [0.012, 0.018, 0.012], 0)
    return bl


def build_bracket(var, rng):
    bl = Bld()
    if var == 1:
        # ox, oy, oz, W, H, D, droop
        shelves = [(0.0, 0.0, 0.0, 0.10, 0.075, 0.06, 0.25),
                   (0.0, -0.005, 0.13, 0.085, 0.06, 0.05, 0.30),
                   (0.0, 0.0, 0.22, 0.06, 0.045, 0.035, 0.35)]
    else:
        shelves = [(0.0, 0.0, 0.0, 0.13, 0.06, 0.09, 0.15),
                   (0.0, 0.04, 0.11, 0.09, 0.05, 0.06, 0.30)]
    for ox, oy, oz, W, H, D, droop in shelves:
        shelf(bl, ox, oy, oz, W, H, D, droop, 0)
    return bl


def build_puff(var, rng):
    bl = Bld()
    n = 6 if var == 1 else 4
    placed = []
    for _ in range(n):
        x = y = r = 0.0
        for _t in range(200):
            r = rng.uniform(0.03, 0.06) if var == 1 else rng.uniform(0.05, 0.08)
            ang = rng.uniform(0, TAU)
            d = rng.uniform(0.0, 0.08)
            x, y = d * math.cos(ang), d * math.sin(ang)
            if all(math.hypot(x - px, y - py) > 0.9 * (r + pr) for px, py, pr in placed):
                break
        placed.append((x, y, r))
        rz = r * 0.9
        sphere(bl, (x, y, rz), r, rz, 0)
    return bl


def build_patch(var, rng):
    bl = Bld()
    n = 6 if var == 1 else 9
    spread = 0.12 if var == 1 else 0.16
    placed = []
    for _ in range(n):
        x = y = 0.0
        for _t in range(200):
            ang = rng.uniform(0, TAU)
            r = spread * math.sqrt(rng.random())
            x, y = r * math.cos(ang), r * math.sin(ang)
            if all(math.hypot(x - px, y - py) > 0.05 for px, py in placed):
                break
        placed.append((x, y))
        kind = rng.randrange(3)  # 0 brown, 1 ochre, 2 red-white
        cap = rng.uniform(0.025, 0.045)
        h = rng.uniform(0.04, 0.08)
        cyl(bl, (x, y, 0.0), (x, y, h), cap * 0.16, cap * 0.13, 10, 3)
        dome(bl, (x, y, h), cap, cap * 0.55, kind, rings=4, seg=14)
    return bl


# ---------------------------------------------------------------- blender scene

def srgb(c):
    return c


def setup_render():
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    try:
        sc.cycles.device = "CPU"
        sc.cycles.samples = PREVIEW_SAMPLES
        sc.cycles.use_denoising = False
    except Exception:
        pass
    sc.render.resolution_x = PREVIEW_RES
    sc.render.resolution_y = PREVIEW_RES
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.film_transparent = False
    w = bpy.data.worlds.new("wf_world")
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.70, 0.75, 0.80, 1.0)
    bg.inputs[1].default_value = 1.0
    sc.world = w


def clear_scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for me in list(bpy.data.meshes):
        if me.users == 0:
            bpy.data.meshes.remove(me)


def make_object(name, bl, mats):
    me = bpy.data.meshes.new(name)
    me.from_pydata(bl.v, [], bl.f)
    me.update()
    uvl = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li, vi in zip(poly.loop_indices, poly.vertices):
            uvl.data[li].uv = bl.uv[vi]
    for m in mats:
        me.materials.append(m)
    for poly, mi in zip(me.polygons, bl.m):
        poly.material_index = mi
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def select_only(ob):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


def export(ob, base):
    select_only(ob)
    glb = os.path.join(OUT, base + ".glb")
    fbx = os.path.join(OUT, base + ".fbx")
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", use_selection=True, export_yup=True)
    bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, object_types={"MESH"},
                             axis_forward="-Z", axis_up="Y", path_mode="RELATIVE", embed_textures=False)


def preview(ob, path, ground_z, water=None, trunk=False):
    sc = bpy.context.scene
    temps = []
    bpy.ops.mesh.primitive_plane_add(size=6.0, location=(0.0, 0.0, ground_z))
    g = bpy.context.active_object
    g.data.materials.append(mk_flat("pv_ground", (0.30, 0.27, 0.20), 0.95))
    temps.append(g)
    if water is not None:
        bpy.ops.mesh.primitive_plane_add(size=6.0, location=(0.0, 0.0, water))
        w = bpy.context.active_object
        w.data.materials.append(mk_flat("pv_water", (0.10, 0.24, 0.26), 0.05))
        temps.append(w)
    if trunk:
        bpy.ops.mesh.primitive_cylinder_add(radius=0.2, depth=1.6, location=(-0.2, 0.0, ground_z + 0.8))
        tr = bpy.context.active_object
        tr.data.materials.append(mk_flat("pv_bark", (0.24, 0.18, 0.12), 0.9))
        temps.append(tr)
    bpy.ops.object.light_add(type="SUN", rotation=(0.9, 0.1, 0.6))
    sun = bpy.context.active_object
    sun.data.energy = 4.0
    temps.append(sun)
    cam_d = bpy.data.cameras.new("wf_cam")
    cam = bpy.data.objects.new("wf_cam", cam_d)
    sc.collection.objects.link(cam)
    temps.append(cam)
    sc.camera = cam
    corners = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    mn = Vector((min(c.x for c in corners), min(c.y for c in corners), min(c.z for c in corners)))
    mx = Vector((max(c.x for c in corners), max(c.y for c in corners), max(c.z for c in corners)))
    centre = (mn + mx) * 0.5
    size = max(mx.x - mn.x, mx.y - mn.y, mx.z - mn.z, 0.2)
    dist = size * 1.6 + 0.35
    d = Vector((0.75, -0.65, 0.45)).normalized()
    pos = centre + d * dist
    cam.location = pos
    cam.rotation_euler = (centre - pos).to_track_quat("-Z", "Y").to_euler()
    cam_d.lens = 50
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    for o in temps:
        bpy.data.objects.remove(o, do_unlink=True)


def emit(rows, name, kind, bl, mats, ground_z, water=None, trunk=False):
    clear_scene()
    ob = make_object(name, bl, mats)
    export(ob, name)
    preview(ob, os.path.join(PREV, name + ".png"), ground_z, water, trunk)
    rows.append((name, kind, bl.tris(), tuple(ob.dimensions)))
    print("OK %s tris=%d dims=(%.3f,%.3f,%.3f)" % ((name, bl.tris()) + tuple(ob.dimensions)))
    if bl.tris() > 5000:
        print("WARN %s over 5k tris" % name)


def write_readme(rows):
    lines = [
        "# Flora: aquatic plants and fungi",
        "",
        "Authored by `Tools/Author-Flora-wetfungi.py` (seed %d). Modelled geometry with 512 px albedo + normal textures." % SEED,
        "",
        "- Units: metres. One combined mesh per variant, `.glb` and `.fbx` (FBX textures referenced relatively from `textures/`).",
        "- Origins: water_lily, duckweed_mat, pondweed at water surface z=0 (pondweed roots at z=-0.5). bracket_fungus at attach face, +X outward. puffball_cluster and ground_fungus_patch at ground z=0.",
        "- Previews: `previews/<name>.png` (Cycles; water plane for lily/duckweed, bottom plane for pondweed, trunk for bracket).",
        "",
        "| Variant | Kind | Tris | Size (m) x,y,z |",
        "|---|---|---|---|",
    ]
    for name, kind, tris, d in rows:
        lines.append("| %s | %s | %d | %.3f x %.3f x %.3f |" % (name, kind, tris, d[0], d[1], d[2]))
    lines += [
        "",
        "Catalogue: Docs/FloraCatalog.md.",
        "",
    ]
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))


def main():
    os.makedirs(TEX, exist_ok=True)
    os.makedirs(PREV, exist_ok=True)
    setup_render()
    rows = []
    for var in (1, 2):
        tag = "water_lily_v%d" % var
        mats = mat_set(tag, [("pad", shade_pad(var), 0.45, False),
                             ("white", shade_petal(False), 0.5, False),
                             ("pink", shade_petal(True), 0.5, False)])
        emit(rows, tag, "aquatic", build_lily(var, random.Random(SEED * 10 + var)), mats, -0.3, water=-0.02)

    for var in (1, 2):
        tag = "duckweed_mat_v%d" % var
        mats = mat_set(tag, [("disc", shade_duck(var), 0.4, True)])
        emit(rows, tag, "aquatic", build_duck(var, random.Random(SEED * 10 + var)), mats, -0.3, water=-0.02)

    for var in (1, 2):
        tag = "pondweed_v%d" % var
        mats = mat_set(tag, [("strand", shade_strand(var), 0.5, False)])
        emit(rows, tag, "aquatic", build_pond(var, random.Random(SEED * 10 + var)), mats, -0.5)

    for var in (1, 2):
        tag = "bracket_fungus_v%d" % var
        mats = mat_set(tag, [("shelf", shade_bracket(var), 0.7, False)])
        emit(rows, tag, "fungus", build_bracket(var, random.Random(SEED * 10 + var)), mats, -0.5, trunk=True)

    for var in (1, 2):
        tag = "puffball_cluster_v%d" % var
        mats = mat_set(tag, [("ball", shade_puff(var), 0.85, False)])
        emit(rows, tag, "fungus", build_puff(var, random.Random(SEED * 10 + var)), mats, 0.0)

    for var in (1, 2):
        tag = "ground_fungus_patch_v%d" % var
        mats = mat_set(tag, [("cap_brown", shade_cap("brown", var), 0.6, False),
                             ("cap_ochre", shade_cap("ochre", var), 0.6, False),
                             ("cap_red", shade_cap("red", var), 0.5, False),
                             ("stem", shade_stem(var), 0.7, False)])
        emit(rows, tag, "fungus", build_patch(var, random.Random(SEED * 10 + var)), mats, 0.0)

    write_readme(rows)
    print("PASS: %d aquatic/fungus variants written to %s" % (len(rows), OUT))


if __name__ == "__main__":
    main()
