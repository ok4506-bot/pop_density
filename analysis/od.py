"""②③ 이동 — MDIS 국내인구이동 마이크로데이터(주민등록 전입신고)로 연령별 OD 만들기.

원자료 한 줄 = 전입신고 1건 (머리글 없음, 41열)
  1–3  전입지 시도·시군구·읍면동 → 이어 붙이면 10자리 행정동 코드
  4–6  전입 연·월·일
  7–9  전출지 시도·시군구·읍면동
  10   전입사유
  11–40 이동자 최대 10명 × (세대주관계, 만나이 3자리, 성별)
같은 읍면동 안 이동이 들어 있다 → 빼면 KOSIS 공표 이동자 수와 정확히 같다(2023~2025 확인).

출력(캐시, work/): mdis_{연도}_sgg.csv  시군구 OD × 생애단계 (같은 시군구 안 이동 제외)
                  mdis_{연도}_dong.csv 수도권 행정동별 전입·전출 × 생애단계 (같은 행정동 안 이동 제외)
                  mdis_{연도}_age.csv  서울 경계를 넘는 이동, 만나이 × 상대지역
"""
from __future__ import annotations

import csv
import io
import json
import zipfile
from collections import Counter

import numpy as np
import pandas as pd

import paths

CAPITAL = {"11": "서울", "28": "인천", "41": "경기"}
REGION = {"11": "서울", "28": "인천", "41": "경기", "42": "강원", "51": "강원",
          "30": "충청", "36": "충청", "43": "충청", "44": "충청",
          "29": "호남", "45": "호남", "52": "호남", "46": "호남",
          "26": "영남", "27": "영남", "31": "영남", "47": "영남", "48": "영남", "50": "제주"}
STAGE_NAMES = ["0–19", "20–24", "25–34", "35–44", "45–64", "65+"]   # 0 = 생애단계 밖(분모에만 포함)
BUCHEON_2023 = {"41192": "41190", "41194": "41190", "41196": "41190"}


def stage_of(age: int) -> int:
    if age < 20:
        return 0
    if age < 25:
        return 1
    if age < 35:
        return 2
    if age < 45:
        return 3
    if age < 65:
        return 4
    return 5


_STAGE = np.array([stage_of(a) for a in range(131)])


def _member(zf: zipfile.ZipFile, year: int):
    for info in zf.infolist():
        if info.filename.startswith(str(year)):
            return info
    raise KeyError(f"{year}년 파일이 zip 안에 없습니다")


def aggregate(year: int, force: bool = False, progress: bool = True) -> dict[str, pd.DataFrame]:
    """한 해를 훑어 세 가지 집계를 만든다 (약 1분). 캐시가 있으면 읽기만."""
    paths.ensure_dirs()
    f_sgg, f_dong, f_age = (paths.CACHE / f"mdis_{year}_{k}.csv" for k in ("sgg", "dong", "age"))
    f_meta = paths.CACHE / f"mdis_{year}_meta.json"
    if not force and all(f.exists() for f in (f_sgg, f_dong, f_age, f_meta)):
        return {"sgg": pd.read_csv(f_sgg, dtype={"o": str, "d": str}),
                "dong": pd.read_csv(f_dong, dtype={"adm10": str}),
                "age": pd.read_csv(f_age), "meta": json.loads(f_meta.read_text(encoding="utf-8"))}

    sgg, dong_in, dong_out, age = Counter(), Counter(), Counter(), Counter()
    rows = movers = same_dong = 0
    with zipfile.ZipFile(paths.mdis_zip()) as zf, zf.open(_member(zf, year)) as fh:
        for r in csv.reader(io.TextIOWrapper(fh, encoding="utf-8-sig")):
            rows += 1
            if progress and rows % 1_000_000 == 0:
                print(f"  {year}: {rows:,}줄", flush=True)
            ds, os_ = r[0], r[6]
            d_sgg, o_sgg = ds + r[1], os_ + r[7]
            d_dong, o_dong = d_sgg + r[2], o_sgg + r[8]
            same_s, same_d = d_sgg == o_sgg, d_dong == o_dong
            d_cap, o_cap = ds in CAPITAL, os_ in CAPITAL
            seoul_x = (ds == "11") != (os_ == "11")
            for k in range(10, 40, 3):
                if not r[k]:
                    break
                movers += 1
                a = int(r[k + 1])
                st = _STAGE[min(a, 130)]
                if same_d:
                    same_dong += 1
                    continue
                if not same_s:
                    sgg[(o_sgg, d_sgg, st)] += 1
                if d_cap:
                    dong_in[(d_dong, st)] += 1
                if o_cap:
                    dong_out[(o_dong, st)] += 1
                if seoul_x:
                    if ds == "11":
                        age[(min(a, 100), "in", REGION.get(os_, "기타"))] += 1
                    else:
                        age[(min(a, 100), "out", REGION.get(ds, "기타"))] += 1

    od = pd.DataFrame([(o, d, int(s), n) for (o, d, s), n in sgg.items()], columns=["o", "d", "stage", "n"])
    keys = sorted(set(dong_in) | set(dong_out))
    dg = pd.DataFrame([(k[0], int(k[1]), dong_in.get(k, 0), dong_out.get(k, 0)) for k in keys],
                      columns=["adm10", "stage", "inn", "out"])
    ag = pd.DataFrame([(a, io_, reg, n) for (a, io_, reg), n in age.items()], columns=["age", "dir", "region", "n"])
    od.to_csv(f_sgg, index=False); dg.to_csv(f_dong, index=False); ag.to_csv(f_age, index=False)
    meta = {"year": year, "reports": rows, "movers": movers, "same_dong": same_dong, "movers_official": movers - same_dong}
    f_meta.write_text(json.dumps(meta), encoding="utf-8")
    if progress:
        print(f"  {year}: 신고 {rows:,}건, 이동자 {movers:,}명, 같은 읍면동 {same_dong:,}명 → "
              f"공표 기준 이동자 {movers - same_dong:,}명", flush=True)
    return {"sgg": od, "dong": dg, "age": ag, "meta": meta}


# ------------------------------------------------------------------ 지표 ② ③
def sgg_indicators(od: pd.DataFrame, pop: pd.DataFrame) -> pd.DataFrame:
    """수도권 시군구별 유입 LQ(②)·순유입 강도(③).

    od  : o, d, stage(0~5), n — 같은 시군구 안 이동은 이미 빠져 있음
    pop : index = 시군구 5자리, 열 s1~s5_raw (격자 원자료 합)
    """
    cap = pop.index
    inn = od.groupby(["d", "stage"])["n"].sum().unstack(fill_value=0).reindex(index=cap, columns=range(6), fill_value=0)
    out = od.groupby(["o", "stage"])["n"].sum().unstack(fill_value=0).reindex(index=cap, columns=range(6), fill_value=0)
    base = inn.sum() / inn.to_numpy().sum()                      # 수도권 전체 전입의 연령 구성
    res = pd.DataFrame(index=cap)
    res["in_all"], res["out_all"] = inn.sum(axis=1), out.sum(axis=1)
    for s in range(1, 6):
        k = f"s{s}"
        res[f"in_{k}"], res[f"out_{k}"] = inn[s], out[s]
        res[f"lqin_{k}"] = (inn[s] / res["in_all"].where(res["in_all"] > 0)) / base[s]
        res[f"nm_{k}"] = (inn[s] - out[s]) / pop[f"{k}_raw"].where(pop[f"{k}_raw"] > 0) * 1000
    return res


def dong_lqin(dong: pd.DataFrame, min_in: int = 100) -> pd.DataFrame:
    """행정동 유입 LQ (기준 = 수도권 행정동 전입 전체). 전입 합계 min_in 명 미만은 비움."""
    inn = dong.pivot_table(index="adm10", columns="stage", values="inn", aggfunc="sum", fill_value=0)
    inn = inn.reindex(columns=range(6), fill_value=0)
    base = inn.sum() / inn.to_numpy().sum()
    tot = inn.sum(axis=1)
    res = pd.DataFrame({"in_all": tot})
    for s in range(1, 6):
        res[f"in_s{s}"] = inn[s]
        res[f"lqin_s{s}"] = ((inn[s] / tot) / base[s]).where(tot >= min_in)
    return res


def pooled_sgg(years=(2023, 2024, 2025)) -> pd.DataFrame:
    """3년 합산 시군구 OD (부천 3개 구는 2023 코드에 맞춰 41190 하나로)."""
    frames = []
    for y in years:
        od = aggregate(y)["sgg"].copy()
        od["o"] = od["o"].replace(BUCHEON_2023)
        od["d"] = od["d"].replace(BUCHEON_2023)
        od = od[od["o"] != od["d"]]
        frames.append(od)
    return pd.concat(frames).groupby(["o", "d", "stage"], as_index=False)["n"].sum()
