"""geopandas·pyproj 없이 쓰는 최소 좌표 도구 (원격 환경용).

- 횡메르카토르 정·역변환 (Snyder 1987) — EPSG:5179(UTM-K), EPSG:5186(중부원점 2010)
- Shapefile 폴리곤·DBF 읽기, 점-폴리곤 포함 판정(matplotlib.path)
Windows .venv 에서는 geopandas 로 바꿔도 결과가 같아야 한다.
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

A, F = 6_378_137.0, 1 / 298.257222101           # GRS80
E2 = F * (2 - F)
EP2 = E2 / (1 - E2)
TM = {
    "5179": dict(lat0=38.0, lon0=127.5, k0=0.9996, fe=1_000_000.0, fn=2_000_000.0),
    "5186": dict(lat0=38.0, lon0=127.0, k0=1.0, fe=200_000.0, fn=600_000.0),
}


def _mer(p):
    return A * ((1 - E2 / 4 - 3 * E2**2 / 64 - 5 * E2**3 / 256) * p
                - (3 * E2 / 8 + 3 * E2**2 / 32 + 45 * E2**3 / 1024) * np.sin(2 * p)
                + (15 * E2**2 / 256 + 45 * E2**3 / 1024) * np.sin(4 * p)
                - (35 * E2**3 / 3072) * np.sin(6 * p))


def forward(lat, lon, crs="5179"):
    """위경도(도) → 평면좌표(m)."""
    c = TM[crs]
    phi, lam = np.radians(np.asarray(lat, float)), np.radians(np.asarray(lon, float))
    n = A / np.sqrt(1 - E2 * np.sin(phi) ** 2)
    t, cc = np.tan(phi) ** 2, EP2 * np.cos(phi) ** 2
    a = (lam - np.radians(c["lon0"])) * np.cos(phi)
    x = c["fe"] + c["k0"] * n * (a + (1 - t + cc) * a**3 / 6 + (5 - 18 * t + t**2 + 72 * cc - 58 * EP2) * a**5 / 120)
    y = c["fn"] + c["k0"] * (_mer(phi) - _mer(np.radians(c["lat0"])) + n * np.tan(phi) * (
        a**2 / 2 + (5 - t + 9 * cc + 4 * cc**2) * a**4 / 24 + (61 - 58 * t + t**2 + 600 * cc - 330 * EP2) * a**6 / 720))
    return x, y


def inverse(x, y, crs="5179"):
    """평면좌표(m) → 위경도(도)."""
    c = TM[crs]
    x, y = np.asarray(x, float), np.asarray(y, float)
    m = _mer(np.radians(c["lat0"])) + (y - c["fn"]) / c["k0"]
    mu = m / (A * (1 - E2 / 4 - 3 * E2**2 / 64 - 5 * E2**3 / 256))
    e1 = (1 - np.sqrt(1 - E2)) / (1 + np.sqrt(1 - E2))
    p1 = (mu + (3 * e1 / 2 - 27 * e1**3 / 32) * np.sin(2 * mu) + (21 * e1**2 / 16 - 55 * e1**4 / 32) * np.sin(4 * mu)
          + (151 * e1**3 / 96) * np.sin(6 * mu) + (1097 * e1**4 / 512) * np.sin(8 * mu))
    c1, t1 = EP2 * np.cos(p1) ** 2, np.tan(p1) ** 2
    n1 = A / np.sqrt(1 - E2 * np.sin(p1) ** 2)
    r1 = A * (1 - E2) / (1 - E2 * np.sin(p1) ** 2) ** 1.5
    d = (x - c["fe"]) / (n1 * c["k0"])
    lat = p1 - (n1 * np.tan(p1) / r1) * (d**2 / 2 - (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * EP2) * d**4 / 24
                                         + (61 + 90 * t1 + 298 * c1 + 45 * t1**2 - 252 * EP2 - 3 * c1**2) * d**6 / 720)
    lon = np.radians(c["lon0"]) + (d - (1 + 2 * t1 + c1) * d**3 / 6
                                   + (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * EP2 + 24 * t1**2) * d**5 / 120) / np.cos(p1)
    return np.degrees(lat), np.degrees(lon)


def read_dbf(path, encoding="cp949"):
    b = Path(path).read_bytes()
    n, hl, rl = struct.unpack("<I", b[4:8])[0], struct.unpack("<H", b[8:10])[0], struct.unpack("<H", b[10:12])[0]
    fields, i = [], 32
    while b[i] != 0x0D:
        fields.append((b[i:i + 11].split(b"\x00")[0].decode(), b[i + 16]))
        i += 32
    rows = []
    for r in range(n):
        rec, p, row = b[hl + r * rl: hl + (r + 1) * rl], 1, {}
        for name, ln in fields:
            row[name] = rec[p:p + ln].decode(encoding, "replace").strip()
            p += ln
        rows.append(row)
    return rows


def read_polygons(path):
    """.shp 폴리곤 → [ [ring(np.array Nx2), ...], ... ] (레코드 순서 = DBF 순서)."""
    b = Path(path).read_bytes()
    out, off = [], 100
    while off < len(b):
        clen = struct.unpack(">i", b[off + 4: off + 8])[0] * 2
        rec = b[off + 8: off + 8 + clen]
        off += 8 + clen
        if struct.unpack("<i", rec[:4])[0] == 0:
            out.append([]); continue
        nparts, npts = struct.unpack("<2i", rec[36:44])
        parts = list(struct.unpack(f"<{nparts}i", rec[44:44 + 4 * nparts])) + [npts]
        pts = np.frombuffer(rec[44 + 4 * nparts: 44 + 4 * nparts + 16 * npts], dtype="<f8").reshape(-1, 2)
        out.append([pts[parts[k]:parts[k + 1]] for k in range(nparts)])
    return out


def contains(rings, xy):
    """짝홀 규칙으로 점들이 폴리곤(여러 고리·구멍 포함) 안에 있는지."""
    from matplotlib.path import Path as MPath
    inside = np.zeros(len(xy), bool)
    for ring in rings:
        inside ^= MPath(ring).contains_points(xy)
    return inside


# ---------------------------------------------------------------- 람베르트 정각원추 (EPSG:3347, StatCan)
LCC_3347 = dict(lat1=49.0, lat2=77.0, lat0=63.390675, lon0=-91.8666666666667, fe=6_200_000.0, fn=3_000_000.0)


def _lcc_consts(c):
    e = np.sqrt(E2)
    def m(p): return np.cos(p) / np.sqrt(1 - E2 * np.sin(p) ** 2)
    def t(p): return np.tan(np.pi / 4 - p / 2) / ((1 - e * np.sin(p)) / (1 + e * np.sin(p))) ** (e / 2)
    p1, p2, p0 = (np.radians(c[k]) for k in ("lat1", "lat2", "lat0"))
    n = (np.log(m(p1)) - np.log(m(p2))) / (np.log(t(p1)) - np.log(t(p2)))
    Fc = m(p1) / (n * t(p1) ** n)
    rho0 = A * Fc * t(p0) ** n
    return e, t, n, Fc, rho0


def lcc_forward(lat, lon, c=LCC_3347):
    e, t, n, Fc, rho0 = _lcc_consts(c)
    phi, lam = np.radians(np.asarray(lat, float)), np.radians(np.asarray(lon, float))
    rho = A * Fc * t(phi) ** n
    th = n * (lam - np.radians(c["lon0"]))
    return c["fe"] + rho * np.sin(th), c["fn"] + rho0 - rho * np.cos(th)


def lcc_inverse(x, y, c=LCC_3347):
    e, _, n, Fc, rho0 = _lcc_consts(c)
    dx, dy = np.asarray(x, float) - c["fe"], rho0 - (np.asarray(y, float) - c["fn"])
    rho = np.sign(n) * np.sqrt(dx**2 + dy**2)
    tt = (rho / (A * Fc)) ** (1 / n)
    th = np.arctan2(dx, dy)
    lam = th / n + np.radians(c["lon0"])
    phi = np.pi / 2 - 2 * np.arctan(tt)
    for _ in range(8):
        phi = np.pi / 2 - 2 * np.arctan(tt * ((1 - e * np.sin(phi)) / (1 + e * np.sin(phi))) ** (e / 2))
    return np.degrees(phi), np.degrees(lam)


# ---------------------------------------------------------------- GeoPackage 도형, 단순화
def gpkg_rings(blob: bytes):
    """GPKG 바이너리 → [[ring(Nx2), ...] per polygon]. Polygon·MultiPolygon만."""
    flags = blob[3]
    env = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}[(flags >> 1) & 7]
    wkb, off = blob[8 + env:], 0

    def u32(o, le): return struct.unpack("<I" if le else ">I", wkb[o:o + 4])[0]

    def polygon(o):
        le = wkb[o] == 1
        nr = u32(o + 5, le); o += 9
        rings = []
        for _ in range(nr):
            npt = u32(o, le); o += 4
            pts = np.frombuffer(wkb[o:o + 16 * npt], dtype="<f8" if le else ">f8").reshape(-1, 2)
            rings.append(pts); o += 16 * npt
        return rings, o

    le = wkb[0] == 1
    gtype = u32(1, le) % 1000
    if gtype == 3:
        return [polygon(0)[0]]
    if gtype == 6:
        n, o, polys = u32(5, le), 9, []
        for _ in range(n):
            r, o = polygon(o); polys.append(r)
        return polys
    raise ValueError(f"지원하지 않는 도형 {gtype}")


def rdp(pts: np.ndarray, tol: float) -> np.ndarray:
    """Douglas–Peucker (반복형). 닫힌 고리의 첫·끝 점은 유지."""
    if len(pts) < 5:
        return pts
    keep = np.zeros(len(pts), bool); keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        a, b = pts[i], pts[j]
        seg = pts[i + 1:j]
        ab = b - a
        L = np.hypot(*ab)
        d = np.abs(np.cross(ab, seg - a)) / L if L > 0 else np.hypot(*(seg - a).T)
        k = int(np.argmax(d))
        if d[k] > tol:
            m = i + 1 + k
            keep[m] = True
            stack += [(i, m), (m, j)]
    out = pts[keep]
    return out if len(out) >= 4 else pts[[0, len(pts) // 3, 2 * len(pts) // 3, -1]]
