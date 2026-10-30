"""① 거주 LQ — 생애단계 5개가 어디에 모여 사는가.

수도권: SGIS 1km 인구격자 2024 (시설 인구 보정 후, core.facility_correct)
토론토: Statistics Canada 인구조사 2021, CMA 인구조사구(CT)
행정구역: 격자 중심점을 2025-01-01 행정동 경계(= MDIS 2024 코드)에 넣어 2024년 시군구·행정동을 붙인다.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

import core
import kgeo
import paths

STAGES = [
    dict(key="s1", label="20–24", name="진학·첫 일자리", idx=[5]),
    dict(key="s2", label="25–34", name="청년", idx=[6, 7]),
    dict(key="s3", label="35–44", name="가족형성", idx=[8, 9]),
    dict(key="s4", label="45–64", name="중장년", idx=[10, 11, 12, 13]),
    dict(key="s5", label="65+", name="고령", idx=list(range(14, 22))),
]
SKEYS = [s["key"] for s in STAGES]
LABEL = {s["key"]: s["label"] for s in STAGES}
LQ_CUT, MIN_POP = 1.2, 250
BANDS = [0, 5, 10, 15, 20, 30, 40, 60, 200]
BAND_LABELS = ["0–5", "5–10", "10–15", "15–20", "20–30", "30–40", "40–60", "60+"]
CAPITAL_SIDO = ("11", "28", "41")


# ------------------------------------------------------------------ 공통
def stage_pop(w: pd.DataFrame) -> pd.DataFrame:
    """SGIS 형식(in_age_001~021) 표 → 총인구 + 생애단계 5개."""
    d = pd.DataFrame(index=w.index)
    d["pop"] = sum(core.age(w, i) for i in range(1, 22))
    for s in STAGES:
        d[s["key"]] = sum(core.age(w, i) for i in s["idx"])
    return d


def add_lq(d: pd.DataFrame, base=None, prefix: str = "lq_") -> pd.DataFrame:
    """LQ = (지역 s단계 비율) / (기준지역 s단계 비율). base = 기준지역 행 마스크(없으면 전체)."""
    m = d.index if base is None else base
    out = d.copy()
    for k in SKEYS:
        ref = d.loc[m, k].sum() / d.loc[m, "pop"].sum()
        out[prefix + k] = (d[k] / d["pop"].where(d["pop"] > 0)) / ref
    return out


def dominant(d: pd.DataFrame, prefix: str = "lq_", min_pop: int = MIN_POP, cut: float = LQ_CUT) -> np.ndarray:
    """우세 생애단계: LQ가 가장 큰 단계 (0~4). 최고값 < cut 이면 -1(혼합), 인구 < min_pop 이면 -2."""
    lq = d[[prefix + k for k in SKEYS]].to_numpy(float)
    safe = np.where(np.isnan(lq), -np.inf, lq)
    best, top = safe.argmax(axis=1), safe.max(axis=1)
    return np.where(d["pop"].to_numpy() < min_pop, -2, np.where(top < cut, -1, best))


def band_lq(d: pd.DataFrame, cols=None) -> pd.DataFrame:
    """도심 거리대별 생애단계 LQ (거리대 안 인구를 모두 합쳐 계산)."""
    cols = cols or SKEYS
    g = d.groupby("band", observed=True)[["pop"] + cols].sum()
    ref = d[cols].sum() / d["pop"].sum()
    return g[cols].div(g["pop"], axis=0) / ref


# ------------------------------------------------------------------ 행정구역 (2024 코드)
def load_adm(sido=CAPITAL_SIDO):
    """2025-01-01 행정동 경계 (vuski/admdongkor). 코드 = MDIS 2024 와 같음."""
    from shapely.geometry import shape
    gj = json.loads(paths.adm_geojson().read_text(encoding="utf-8"))
    rows, geoms = [], []
    for f in gj["features"]:
        p = f["properties"]
        if p["sido"] in sido:
            rows.append({"adm10": p["adm_cd2"], "sgg5": p["sgg"], "sido2": p["sido"], "sidonm": p["sidonm"],
                         "sggnm": p["sggnm"], "adm_nm": p["adm_nm"].split(" ")[-1]})
            geoms.append(shape(f["geometry"]))
    return pd.DataFrame(rows), geoms


def assign_adm(lat, lon, adm: pd.DataFrame, geoms) -> pd.DataFrame:
    """점(격자 중심) → 행정동. 바다·경계 밖 중심점은 가장 가까운 행정동."""
    from shapely import STRtree, points
    pts = points(np.asarray(lon), np.asarray(lat))
    tree = STRtree(geoms)
    pi, gi = tree.query(pts, predicate="within")
    idx = np.full(len(pts), -1)
    idx[pi] = gi
    miss = np.where(idx < 0)[0]
    if len(miss):
        idx[miss] = tree.nearest(pts[miss])
    out = adm.iloc[idx].reset_index(drop=True)
    out["adm_nearest"] = False
    out.loc[miss, "adm_nearest"] = True
    return out


# ------------------------------------------------------------------ 수도권
def capital_grid(year: int = 2024):
    """수도권 1km 격자: 생애단계 인구(보정·원자료), 거주 LQ, 우세 단계, 거리, 2024 행정구역."""
    reg = core.regions()
    raw = core.load_year(year).reindex(reg.index).fillna(0)
    cor, det = core.facility_correct(raw)
    d = add_lq(stage_pop(cor))
    d = d.join(stage_pop(raw).add_suffix("_raw"))
    d = d.join(reg[["sido", "sgg_key", "adm"]].rename(columns={"sgg_key": "sgg_2026", "adm": "adm_2026"}))
    d["facility"], d["removed"] = det["facility"], det["removed"]
    x, y = core.grid_xy(d.index)
    lat, lon = kgeo.inverse(x, y, "5179")
    d["x"], d["y"], d["lat"], d["lon"] = x, y, lat, lon
    d["dist_km"] = np.hypot(x - core.CITY_HALL[0], y - core.CITY_HALL[1]) / 1000
    d["band"] = pd.cut(d["dist_km"], BANDS, labels=BAND_LABELS, right=False)
    d["seoul"] = d["sido"].eq("서울특별시")
    d["dom"] = dominant(d)
    adm, geoms = load_adm()
    a = assign_adm(lat, lon, adm, geoms)
    a.index = d.index
    d = d.join(a[["adm10", "sgg5", "sggnm", "adm_nm", "adm_nearest"]])
    d.index.name = "grid_cd"
    return d, det


YEARS_TS = (2000, 2005, 2010, 2015, 2020, 2024)


def capital_timeseries(d24: pd.DataFrame, years=YEARS_TS) -> dict[int, pd.DataFrame]:
    """같은 격자(2024 배정)에서 연도별 생애단계 거주 LQ·우세 단계 (해마다 시설 보정, 기준 = 그해 수도권)."""
    reg = core.regions()
    out = {}
    for y in years:
        raw = core.load_year(y).reindex(reg.index).fillna(0)
        cor, det = core.facility_correct(raw)
        s = add_lq(stage_pop(cor))
        s["pop_raw"] = stage_pop(raw)["pop"]
        s["dom"] = dominant(s)
        s["removed"] = det["removed"]
        s["band"] = d24["band"].reindex(s.index)
        s["seoul"] = d24["seoul"].reindex(s.index)
        out[y] = s
    return out


def sgg_table(d: pd.DataFrame) -> pd.DataFrame:
    """격자 → 2024 시군구 합산. 보정 인구로 거주 LQ, 원자료 인구는 ③ 분모용."""
    cols = ["pop"] + SKEYS
    g = d.groupby("sgg5")[cols + [c + "_raw" for c in cols]].sum()
    g = add_lq(g)
    w = d["pop_raw"]
    g["lat"] = (d["lat"] * w).groupby(d["sgg5"]).sum() / w.groupby(d["sgg5"]).sum()   # 인구가중 중심
    g["lon"] = (d["lon"] * w).groupby(d["sgg5"]).sum() / w.groupby(d["sgg5"]).sum()
    names = d.groupby("sgg5")[["sido", "sggnm"]].first()
    return g.join(names)


# ------------------------------------------------------------------ 토론토
TOR = core.RESEARCH / "00.toronto"
TOR_CSV = TOR / "data" / "census" / "unicen_ct" / "census_wide_2021_ct.csv"
TOR_GPKG = TOR / "data" / "boundary" / "2021" / "cma535_ct.gpkg"
KING_BAY = (43.6487, -79.3817)
TOR_AGES = ["0004", "0509", "1014", "1519", "2024", "2529", "3034", "3539", "4044", "4549", "5054", "5559",
            "6064", "6569", "7074", "7579", "8084", "8589", "9094", "9599", "100p"]


def _haversine(lat1, lon1, lat2, lon2):
    p1, p2, dl = np.radians(lat1), np.radians(lat2), np.radians(lon2 - lon1)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 6371.0088 * 2 * np.arcsin(np.sqrt(a))


def _toronto_boundaries(tol_m: float = 15):
    tmp = Path(tempfile.mkdtemp()) / "ct.gpkg"
    shutil.copy(TOR_GPKG, tmp)
    with sqlite3.connect(tmp) as con:
        rows = con.execute("select CTUID, CTNAME, LANDAREA, in_city, geom from cma535_ct").fetchall()
    geo, meta = {}, []
    for ctuid, name, land, in_city, blob in rows:
        out_polys, cx, cy, aa = [], 0.0, 0.0, 0.0
        for rings in kgeo.gpkg_rings(blob):
            pr = []
            for k, rg in enumerate(rings):
                sr = kgeo.rdp(np.round(rg, 1), tol_m)
                la, lo = kgeo.lcc_inverse(sr[:, 0], sr[:, 1])
                pr.append(np.column_stack([np.round(lo, 5), np.round(la, 5)]).tolist())
                if k == 0:
                    xx, yy = rg[:, 0], rg[:, 1]
                    cr = xx[:-1] * yy[1:] - xx[1:] * yy[:-1]
                    a = cr.sum() / 2
                    if a != 0:
                        cx += ((xx[:-1] + xx[1:]) * cr).sum() / 6
                        cy += ((yy[:-1] + yy[1:]) * cr).sum() / 6
                        aa += a
            out_polys.append(pr)
        clat, clon = kgeo.lcc_inverse(cx / aa, cy / aa)
        geo[ctuid] = out_polys
        meta.append({"geosid": ctuid, "ctname": name, "landarea": land, "in_city": int(in_city),
                     "lat": float(clat), "lon": float(clon)})
    return geo, pd.DataFrame(meta).set_index("geosid")


def toronto_ct():
    """토론토 CMA CT 2021: 생애단계 인구, 거주 LQ(기준 = CMA), 우세 단계, King & Bay 거리."""
    cols = ["geosid"] + [f"agec{a}2021{s}t1" for a in TOR_AGES for s in "tmf"]
    c = pd.read_csv(TOR_CSV, usecols=cols, dtype={"geosid": str})
    c = c[c["geosid"].str.startswith("535")].set_index("geosid")
    c = c.where(c >= 0)                                   # -1 = 결측
    w = pd.DataFrame(index=c.index)
    for i, a in enumerate(TOR_AGES, start=1):
        for s, off in (("t", 0), ("m", 30), ("f", 60)):
            w[f"in_age_{i + off:03d}"] = c[f"agec{a}2021{s}t1"].fillna(0)
    geo, meta = _toronto_boundaries()
    d = add_lq(stage_pop(w)).join(meta, how="inner")
    d["dist_km"] = _haversine(KING_BAY[0], KING_BAY[1], d["lat"], d["lon"])
    d["band"] = pd.cut(d["dist_km"], BANDS, labels=BAND_LABELS, right=False)
    d["dom"] = dominant(d)
    return d, geo
