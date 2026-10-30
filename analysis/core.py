"""수도권 1km 인구격자 — 자료 읽기, 시설 보정, 지표 계산 (본 분석 공통 모듈).

시설 보정 규칙은 `A. research/00. 인구격자데이터_서울_수정/popgrid/adjust.py`(서울)와 같고,
수도권으로 넓히면서 ③(25~29·30~34세 남성 과잉 = 산업단지 기숙사)을 더했다.
"""
from __future__ import annotations

import io
import os
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

RESEARCH = Path(os.environ.get("RESEARCH_DIR", Path.home() / "Desktop" / "Dortor_Course" / "A. research"))
GRID_DIR = RESEARCH / "00. 인구격자데이터_서울"
GPKG = GRID_DIR / "outputs" / "gis" / "LQ_격자_1K.gpkg"
LETTERS = "가나다라마바사아자차카타파하"
CITY_HALL = (953_901, 1_952_032)
SEX_OFF = {"all": 0, "male": 30, "female": 60}


# ---------------------------------------------------------------- 읽기
def load_year(year: int) -> pd.DataFrame:
    zpath = next(GRID_DIR.glob("_census_reqdoc_*.zip"))
    frames = []
    with zipfile.ZipFile(zpath) as z:
        for info in z.infolist():
            if info.filename.startswith(f"{year}년_인구_"):
                raw = z.read(info)
                try:
                    txt = raw.decode("utf-8")
                except UnicodeDecodeError:
                    txt = raw.decode("cp949")
                frames.append(pd.read_csv(io.StringIO(txt), header=None, names=["year", "grid", "code", "val"],
                                          dtype={"grid": str, "code": str}))
    long = pd.concat(frames, ignore_index=True)
    w = long.pivot_table(index="grid", columns="code", values="val", aggfunc="sum").fillna(0)
    cols = [f"in_age_{i + o:03d}" for o in (0, 30, 60) for i in range(1, 22)]
    return w.reindex(columns=cols, fill_value=0).astype(float)


def regions() -> pd.DataFrame:
    tmp = Path(tempfile.mkdtemp()) / "g.gpkg"
    shutil.copy(GPKG, tmp)
    with sqlite3.connect(tmp) as con:
        r = pd.read_sql("select grid_cd, sido, sgg, sgg_key, adm from grid_lq", con)
    return r.set_index("grid_cd")


def col(i: int, sex: str = "all") -> str:
    return f"in_age_{i + SEX_OFF[sex]:03d}"


def age(w: pd.DataFrame, i: int, sex: str = "all") -> pd.Series:
    return w[col(i, sex)]


def grid_xy(codes) -> tuple[np.ndarray, np.ndarray]:
    sx = np.array([LETTERS.index(c[0]) for c in codes]); sy = np.array([LETTERS.index(c[1]) for c in codes])
    dx = np.array([int(c[2:4]) for c in codes]); dy = np.array([int(c[4:6]) for c in codes])
    return 700_000 + sx * 100_000 + dx * 1000 + 500, 1_300_000 + sy * 100_000 + dy * 1000 + 500


# ---------------------------------------------------------------- 시설 보정
Z_MIN, REL_MIN, MIL_MIN, STU_MIN, ITER = 4.0, 1.25, 30, 50, 2


def _binom_z(m, f, sr):
    n = m + f
    p = sr / (1 + sr)
    return (m - n * p) / np.sqrt(np.maximum(n * p * (1 - p), 1.0))


def _male_excess(w, i):
    """i번째 5세 연령의 남성 과잉 판정.

    기준 성비 SR = 같은 해·같은 연령의 분석지역 남/여 (판정 격자를 빼고 2회 다시 계산).
    판정 = 이항 z ≥ 4  그리고  초과 ≥ 30명  그리고  격자 성비 ≥ SR × 1.25
    (1990년대 출생 성비가 110~116으로 높아, 고정값 1.05를 쓰면 평범한 큰 격자까지 판정되므로)
    """
    m, f = age(w, i, "male"), age(w, i, "female")
    flag = pd.Series(False, index=w.index)
    for _ in range(ITER):
        sr = m[~flag].sum() / max(f[~flag].sum(), 1.0)
        ex = (m - f * sr).clip(lower=0)
        flag = (_binom_z(m, f, sr) >= Z_MIN) & (ex >= MIL_MIN) & (m >= REL_MIN * sr * f)
    return flag, np.where(flag, ex, 0.0), sr


def facility_correct(w: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """시설 흔적(성·연령 구성)으로 초과분만 덜어낸 사본과 판정표를 돌려준다.

    ① 군부대·남성 시설: 20~24세 남성 과잉 → 남성 초과분 제거
    ② 대학가·기숙사: 20~24세 > r_ref×(15~19 + 25~29)/2 (z≥4, 초과≥50) → 초과분을 성비대로 제거
       r_ref = 판정 안 된 격자의 합계 비율 (2회 반복)
    ③ 산업단지·남성 숙소(수도권 확장): 25~29, 30~34세 남성 과잉 → 남성 초과분 제거
    남성 과잉 판정은 _male_excess() (같은 연령 지역 성비 기준).
    """
    out = w.copy()
    det = pd.DataFrame(index=w.index)
    det["total_raw"] = sum(age(w, i) for i in range(1, 22))
    for i, tag in ((5, "20"), (6, "25"), (7, "30")):
        flag, x, sr = _male_excess(w, i)
        det[f"male{tag}_flag"], det[f"x_male{tag}"], det[f"sr{tag}"] = flag, x, sr
        for sex in ("all", "male"):
            out[col(i, sex)] = np.maximum(out[col(i, sex)] - x, 0)
    det["mil_flag"] = det.male20_flag
    det["ind_flag"] = det.male25_flag | det.male30_flag

    # ② 20~24 돌출 (남성 과잉 보정 후)
    a20 = age(out, 5)
    base = (age(out, 4) + age(out, 6)) / 2
    flag = pd.Series(False, index=w.index)
    for _ in range(ITER):
        keep = ~flag & ~det.mil_flag
        r = a20[keep].sum() / max(base[keep].sum(), 1.0)
        exp_ = r * base
        exc = a20 - exp_
        z = exc / np.sqrt(exp_.clip(lower=1.0))
        flag = (z >= Z_MIN) & (exc >= STU_MIN)
    det["stu_flag"] = flag
    det["stu_r_ref"] = r
    det["x_stu20"] = np.where(flag, (a20 - exp_).clip(lower=0), 0.0)
    m, f = age(out, 5, "male"), age(out, 5, "female")
    tot = (m + f).where(m + f > 0, 1)
    for sex, part in (("male", m / tot), ("female", f / tot)):
        out[col(5, sex)] = np.maximum(out[col(5, sex)] - det["x_stu20"] * part, 0)
    out[col(5)] = np.maximum(out[col(5)] - det["x_stu20"], 0)

    det["x_mil20"] = det.x_male20
    det["removed"] = det[["x_male20", "x_male25", "x_male30", "x_stu20"]].sum(axis=1)
    det["removed_2534"] = det["x_male25"] + det["x_male30"]
    det["facility"] = np.select(
        [det.stu_flag & (det.mil_flag | det.ind_flag), det.stu_flag, det.mil_flag, det.ind_flag],
        ["대학가+남성과잉", "대학가·기숙사", "군·남성시설(20~24)", "산업·남성숙소(25~34)"], default="")
    return out, det


# ---------------------------------------------------------------- 지표
def indicators(w: pd.DataFrame) -> pd.DataFrame:
    t = sum(age(w, i) for i in range(1, 22))
    y = age(w, 6) + age(w, 7)
    d = pd.DataFrame(index=w.index)
    d["pop"], d["y2534"] = t, y
    d["share"] = y / t.replace(0, np.nan)
    g18 = [age(w, i) for i in range(1, 18)] + [sum(age(w, i) for i in range(18, 22))]
    p = pd.concat(g18, axis=1).div(t.replace(0, np.nan), axis=0)
    d["entropy"] = -(p * np.log(p.where(p > 0))).sum(axis=1, min_count=1) / np.log(18)
    six = [sum(age(w, i) for i in range(1, 6)), y, age(w, 8) + age(w, 9), age(w, 10) + age(w, 11),
           age(w, 12) + age(w, 13), sum(age(w, i) for i in range(14, 22))]
    q = pd.concat(six, axis=1).div(t.replace(0, np.nan), axis=0)
    d["gini_simpson"] = (1 - (q**2).sum(axis=1, min_count=1)) / (1 - 1 / 6)
    f2539 = age(w, 6, "female") + age(w, 7, "female") + age(w, 8, "female")
    d["child0_4"], d["f2539"] = age(w, 1), f2539
    d["sexratio"] = (age(w, 6, "male") + age(w, 7, "male")) / (age(w, 6, "female") + age(w, 7, "female")).replace(0, np.nan) * 100
    return d


def add_relative(d: pd.DataFrame, mask=None) -> pd.DataFrame:
    """지역 합계 기준 LQ·아동-여성비 지수 (mask = 기준지역)."""
    m = slice(None) if mask is None else mask
    ref_share = d.loc[m, "y2534"].sum() / d.loc[m, "pop"].sum()
    ref_cwr = d.loc[m, "child0_4"].sum() / d.loc[m, "f2539"].sum()
    d["lq"] = d["share"] / ref_share
    d["cwr_index"] = (d["child0_4"] / d["f2539"].replace(0, np.nan)) / ref_cwr
    return d


def typology(lq, cwr, pop, lq_min=1.25, lo=0.8, hi=1.2, min_pop=250):
    return np.select([pop < min_pop, lq < lq_min, cwr < lo, cwr >= hi],
                     ["소인구", "비집중", "단신·진입형", "가족형성형"], default="중간")


def station_access(x, y, lat, lon):
    import kgeo
    sx, sy = kgeo.forward(lat, lon, "5179")
    dist = np.hypot(x[:, None] - sx[None, :], y[:, None] - sy[None, :])
    t = dist / (4000 / 60)
    return np.where(t <= 30, np.exp(-np.log(2) / 10 * t), 0).sum(axis=1)


def clean_json(o):
    """NaN·inf → None (브라우저 JSON.parse 가 NaN 을 못 읽음)."""
    import math
    if isinstance(o, dict):
        return {str(k): clean_json(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean_json(v) for v in o]
    if isinstance(o, (np.floating, float)):
        f = float(o)
        return None if math.isnan(f) or math.isinf(f) else f
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o
