"""ASCII renderer for the gsmtc01 wave logo.

The logo is modelled as a variable-radius tube that follows two half circles
(an S-shaped wave lying on its side). Each frame rotates the tube in 3D,
splats surface samples into a character grid with a z-buffer and shades
them with a Lambert + specular term. A highlight pulse travels along the
tube so the wave looks like it is flowing.
"""
import math

import numpy as np

RAMP = " .,:-=+*#%@"


def centerline(n=340):
    """Centre line of the wave, u in [0, 1] from the left tip to the right tip."""
    u = np.linspace(0.0, 1.0, n)
    # cx == R puts both lobes through the origin, so the pinched neck has no gap
    cx = R = 0.43
    a0 = math.radians(150)
    pts = np.zeros((n, 3))
    left = u <= 0.5
    # left lobe: angle a0 -> 360 deg around (-cx, 0), passing through the bottom
    a = a0 + (2 * math.pi - a0) * (u[left] / 0.5)
    pts[left, 0] = -cx + R * np.cos(a)
    pts[left, 1] = R * np.sin(a)
    # right lobe: point reflection of the left lobe, traversed outward
    ur = u[~left]
    a = a0 + (2 * math.pi - a0) * ((1.0 - ur) / 0.5)
    pts[~left, 0] = cx - R * np.cos(a)
    pts[~left, 1] = -R * np.sin(a)
    return u, pts


NECK_R = 0.012
BELLY_S = 0.57  # where each lobe is thickest (its lowest / highest point)


def radius(u):
    """Tube radius, measured from the avatar artwork.

    About 0.16 at the rounded tips, 0.20 at the belly of each lobe, then a
    smooth taper to an almost pointed neck where the two lobes meet.
    """
    s = 1.0 - np.abs(u - 0.5) / 0.5  # 0 at the tips, 1 at the neck
    base = 0.16 + 0.04 * np.sin(math.pi / 2 * np.clip(s / BELLY_S, 0, 1))
    k = np.clip((s - BELLY_S) / (1.0 - BELLY_S), 0, 1)
    return NECK_R + (base - NECK_R) * np.cos(math.pi / 2 * k) ** 1.3


def surface(n_u=720, n_phi=128, depth=0.72):
    """Return points, normals and the u parameter of samples on the tube surface."""
    u, c = centerline(n_u)
    t = np.gradient(c, axis=0)
    t /= np.linalg.norm(t, axis=1, keepdims=True)
    nrm = np.stack([-t[:, 1], t[:, 0], np.zeros(len(u))], axis=1)
    b = np.array([0.0, 0.0, 1.0])
    r = radius(u)
    phi = np.linspace(0, 2 * math.pi, n_phi, endpoint=False)
    cp, sp = np.cos(phi)[None, :, None], np.sin(phi)[None, :, None]
    P = c[:, None, :] + r[:, None, None] * (cp * nrm[:, None, :] + depth * sp * b)
    N = cp * nrm[:, None, :] + (sp / depth) * b
    U = np.repeat(u[:, None], n_phi, axis=1)
    pts, nor, uu = [P.reshape(-1, 3)], [N.reshape(-1, 3)], [U.reshape(-1)]
    # rounded caps at both tips (half ellipsoids)
    for idx, sgn in ((0, -1.0), (-1, 1.0)):
        th = np.linspace(0, math.pi / 2, 20)[:, None]
        ph = phi[None, :]
        tt = t[idx] * sgn
        loc = (np.cos(th)[..., None] * (np.cos(ph)[..., None] * nrm[idx] + depth * np.sin(ph)[..., None] * b)
               + np.sin(th)[..., None] * tt)
        nl = (np.cos(th)[..., None] * (np.cos(ph)[..., None] * nrm[idx] + np.sin(ph)[..., None] / depth * b)
              + np.sin(th)[..., None] * tt)
        pts.append((c[idx] + r[idx] * loc).reshape(-1, 3))
        nor.append(nl.reshape(-1, 3))
        uu.append(np.full(loc.shape[0] * loc.shape[1], u[idx]))
    P = np.concatenate(pts)
    N = np.concatenate(nor)
    N /= np.linalg.norm(N, axis=1, keepdims=True)
    return P, N, np.concatenate(uu)


def rot(ax, ay, az):
    cx, sx, cy, sy, cz, sz = math.cos(ax), math.sin(ax), math.cos(ay), math.sin(ay), math.cos(az), math.sin(az)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rx @ Ry @ Rz


_SURF = None


def tumble(t):
    """Free 360 degree tumble that still closes into a seamless loop.

    Every axis turns a whole number of times per loop; incommensurate
    sinusoidal wobbles on top keep it from looking mechanical, but they are
    kept small so the turn stays smooth instead of jerky.
    """
    w = 2 * math.pi * t
    ax = w + 0.27 * math.sin(2 * w + 0.7) + 0.12 * math.sin(5 * w + 2.1)
    ay = -w + 0.30 * math.sin(3 * w + 1.3) + 0.10 * math.sin(4 * w)
    az = w + 0.22 * math.sin(2 * w + 2.4) + 0.15 * math.sin(3 * w + 0.4)
    return ax, ay, az


# palette levels: 1 deep navy .. 6 sky blue (no white)
LEVELS = 6
# sub-samples per cell side, and the cell coverage above which a cell is solid
SS = 3
SOLID = 0.6


def _dilate(m):
    p = np.pad(m, 1)
    return np.max([p[i:i + m.shape[0], j:j + m.shape[1]] for i in range(3) for j in range(3)], axis=0)


def _erode(m):
    p = np.pad(m, 1, constant_values=True)
    return np.min([p[i:i + m.shape[0], j:j + m.shape[1]] for i in range(3) for j in range(3)], axis=0)


def frame(t, cols=52, rows=27, scale=128.0, cw=5.76, ch=9.6, angles=None):
    """Render one frame at loop time t in [0, 1).

    Returns rows of (char, level) where level is 0 (empty) or 1..LEVELS.
    """
    global _SURF
    if _SURF is None:
        _SURF = surface()
    P, N, U = _SURF
    ax, ay, az = tumble(t) if angles is None else angles
    R = rot(ax, ay, az)
    p = P @ R.T
    n = N @ R.T
    # back faces of the thin tube are never visible, but its inside can be:
    # flip normals that point away from the viewer so shading stays solid
    n = np.where(n[:, 2:3] < 0, -n, n) * 0.6 + n * 0.4
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-9
    f = 3.6 / (3.6 - p[:, 2])  # mild perspective
    gx = cols / 2 + p[:, 0] * f * scale / cw
    gy = rows / 2 - p[:, 1] * f * scale / ch
    light = np.array([-0.45, 0.55, 0.70])
    light /= np.linalg.norm(light)
    h = light + np.array([0.0, 0.0, 1.0])
    h /= np.linalg.norm(h)
    diff = np.clip(n @ light, 0, 1)
    spec = np.clip(n @ h, 0, 1) ** 24
    lum = 0.22 + 0.62 * diff + 0.30 * spec
    # logo gradient: deep at both tips, bright around the neck
    grad = 1.0 - np.abs(U - 0.5) / 0.5
    # flow pulse travelling along the wave, twice per loop
    d = (U - (2 * t) % 1.0 + 0.5) % 1.0 - 0.5
    pulse = np.exp(-(d / 0.08) ** 2)
    # z-buffer on an SS x SS sub-grid per character cell (vectorised: for every
    # sub-cell keep the sample nearest to the viewer)
    sw, sh = cols * SS, rows * SS
    sx = np.floor((gx + 0.5) * SS).astype(int)
    sy = np.floor((gy + 0.5) * SS).astype(int)
    ok = (sx >= 0) & (sx < sw) & (sy >= 0) & (sy < sh)
    flat = (sy * sw + sx)[ok]
    z = p[ok, 2]
    order = np.lexsort((z, flat))
    flat_o = flat[order]
    last = np.r_[flat_o[1:] != flat_o[:-1], True]
    win = np.flatnonzero(ok)[order[last]]
    cells = flat_o[last]
    hit = np.zeros(sh * sw, bool)
    hit[cells] = True
    hit = hit.reshape(sh, sw)
    sub = {}
    for name, val in (("L", lum), ("G", grad), ("F", pulse)):
        a = np.zeros(sh * sw)
        a[cells] = val[win]
        sub[name] = a.reshape(sh, sw)
    # close pinholes between surface samples so solid areas count as covered
    cover = _erode(_dilate(hit))

    def pool(a):
        return a.reshape(rows, SS, cols, SS).sum(axis=(1, 3))

    cov = pool(cover.astype(float)) / (SS * SS)
    nhit = pool(hit.astype(float))
    L, G, F = (pool(sub[k]) / np.maximum(nhit, 1) for k in ("L", "G", "F"))
    out = []
    for y in range(rows):
        row = []
        for x in range(cols):
            if nhit[y, x] == 0:
                row.append((" ", 0))
                continue
            v = min(1.0, L[y, x] + 0.18 * F[y, x])
            # dense glyphs inside the body, lighter ones where a cell is only
            # partly covered, so the silhouette and the thin neck look smooth
            d = 3 + min(len(RAMP) - 4, int(v * (len(RAMP) - 3)))
            if cov[y, x] < SOLID:
                d = max(1, min(d, 1 + round((d - 1) * cov[y, x] / SOLID)))
            tone = 0.55 * L[y, x] + 0.30 * G[y, x] + 0.25 * F[y, x]
            lvl = 1 + max(0, min(LEVELS - 1, int((tone - 0.12) / 0.72 * LEVELS)))
            row.append((RAMP[d], lvl))
        out.append(row)
    return out


if __name__ == "__main__":
    import sys

    t = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0
    for row in frame(t):
        print("".join(c for c, _ in row))
