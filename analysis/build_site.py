"""분석 → 웹페이지 자료(site/data/*.json).

python build_site.py   (또는 노트북에서 build_site.build())
공개 원칙: 격자·시군구·행정동 단위 집계값만 내보낸다. MDIS 이동자 수는 5명 미만 칸을 내보내지 않는다.
"""
from __future__ import annotations

import json
import re

import numpy as np
import pandas as pd

import core
import lifestage as L
import od
import paths

YEAR = 2024
FLOW_MIN, FLOW_TOP = 30, 120          # 흐름 지도: 이동자 30명 이상, 단계·방향별 상위 120개까지
SMALL = 5                              # 5명 미만 칸은 공개하지 않음
STAGE_COLORS = ["#c2417a", "#eb6834", "#1baf7a", "#2a78d6", "#9a6614"]


# ------------------------------------------------------------------ 도우미
def _r(v, nd=3):
    v = pd.to_numeric(pd.Series(v), errors="coerce").round(nd)
    return [None if pd.isna(z) else (int(z) if nd == 0 else float(z)) for z in v]


def _dump(name, obj, indent=None):
    p = paths.SITE_DATA / name
    txt = json.dumps(core.clean_json(obj), ensure_ascii=False, allow_nan=False,
                     indent=indent, separators=None if indent else (",", ":"))
    p.write_text(txt, encoding="utf-8")
    return p.stat().st_size


def pretty(code: str, sggnm: str) -> str:
    if code.startswith("28"):
        return "인천 " + sggnm
    return re.sub(r"^(.+시)(.+구)$", r"\1 \2", sggnm)


def _ring_list(geom, nd=5):
    """shapely (Multi)Polygon → [[[lon,lat],...], ...] 폴리곤별 외곽+구멍."""
    polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    out = []
    for p in polys:
        rings = [p.exterior] + list(p.interiors)
        out.append([np.round(np.asarray(r.coords), nd).tolist() for r in rings])
    return out


# ------------------------------------------------------------------ 계산 묶음
def compute():
    """노트북·스크립트 공통: 모든 지표를 계산해 dict 로 돌려준다."""
    d, det = L.capital_grid(YEAR)
    g = L.sgg_table(d)
    g["name"] = [pretty(c, n) for c, n in zip(g.index, g["sggnm"])]
    mdis = od.aggregate(YEAR)
    ind = od.sgg_indicators(mdis["sgg"], g)
    dong = od.dong_lqin(mdis["dong"])
    t, tgeo = L.toronto_ct()
    ts = L.capital_timeseries(d)
    return dict(grid=d, det=det, sgg=g, ind=ind, mdis=mdis, dong=dong, tor=t, tgeo=tgeo, ts=ts)


def seoul_flows(odf: pd.DataFrame):
    x = odf.copy()
    x["os"], x["ds"] = x["o"].str[:2], x["d"].str[:2]
    x["oR"], x["dR"] = x["os"].map(od.REGION).fillna("기타"), x["ds"].map(od.REGION).fillna("기타")
    return x


def seoul_balance(x: pd.DataFrame, g: pd.DataFrame) -> pd.DataFrame:
    """서울 경계를 넘는 이동: 단계별 전입·전출·순이동, 상대지역별 순이동."""
    inS = x[(x.ds == "11") & (x.os != "11")]
    outS = x[(x.os == "11") & (x.ds != "11")]
    seoul_pop = g[g.index.str.startswith("11")]
    rows = []
    for s in range(1, 6):
        i, o = inS[inS.stage == s], outS[outS.stage == s]
        row = {"stage": f"s{s}", "label": L.STAGES[s - 1]["label"], "in": int(i.n.sum()), "out": int(o.n.sum())}
        row["net"] = row["in"] - row["out"]
        row["net_per1000"] = row["net"] / seoul_pop[f"s{s}_raw"].sum() * 1000
        for reg in ("경기", "인천"):
            row[f"net_{reg}"] = int(i[i.oR == reg].n.sum() - o[o.dR == reg].n.sum())
        nonc = ~i.oR.isin(["경기", "인천"]); nonc_o = ~o.dR.isin(["경기", "인천"])
        row["net_비수도권"] = int(i[nonc].n.sum() - o[nonc_o].n.sum())
        rows.append(row)
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ 내보내기
def export_grid(d: pd.DataFrame, ts: dict | None = None) -> int:
    alive = d["pop_raw"] > 0
    if ts:
        for y, t in ts.items():
            alive |= t["pop_raw"].reindex(d.index).fillna(0) > 0
    keep = d[alive]
    xs, ys = keep["x"].to_numpy() - 500, keep["y"].to_numpy() - 500
    import kgeo
    corners = []
    for dx, dy in ((0, 0), (1000, 0), (1000, 1000), (0, 1000)):
        la, lo = kgeo.inverse(xs + dx, ys + dy, "5179")
        corners += [np.round(lo, 5), np.round(la, 5)]
    names = sorted(set(keep["sggnm"].astype(str) + " " + keep["adm_nm"].astype(str)))
    ok = keep["pop"] >= L.MIN_POP
    fac = ["", "대학가·기숙사", "군·남성시설(20~24)", "산업·남성숙소(25~34)", "대학가+남성과잉"]
    data = {"n": int(len(keep)), "corners": np.column_stack(corners).tolist(), "names": names,
            "name": [names.index(a + " " + b) for a, b in zip(keep["sggnm"].astype(str), keep["adm_nm"].astype(str))],
            "pop": _r(keep["pop"], 0), "dom": keep["dom"].astype(int).tolist(),
            "dist": _r(keep["dist_km"], 1), "fac_codes": fac, "fac": [fac.index(f) for f in keep["facility"]]}
    for k in L.SKEYS:
        data[k] = _r(keep[f"lq_{k}"].where(ok), 2)
    size = _dump("capital_grid.json", data)
    if ts:
        tsd = {"years": sorted(ts), "scale": 100, "by_year": {}}
        for y, t in sorted(ts.items()):
            t = t.reindex(keep.index)
            okv = t["pop"] >= L.MIN_POP
            tsd["by_year"][str(y)] = {"pop": _r(t["pop"].fillna(0), 0), "dom": t["dom"].fillna(-2).astype(int).tolist(),
                                      **{k: _r((t[f"lq_{k}"] * 100).where(okv), 0) for k in L.SKEYS}}
        size += _dump("capital_ts.json", tsd)
    return size


def export_toronto(t: pd.DataFrame, geo: dict) -> int:
    feats = []
    ok = t["pop"] >= L.MIN_POP
    for gid, r in t.iterrows():
        props = {"id": gid, "ct": r["ctname"], "pop": int(r["pop"]), "dom": int(r["dom"]),
                 "dist": round(float(r["dist_km"]), 1), "city": int(r["in_city"])}
        for k in L.SKEYS:
            v = r[f"lq_{k}"]
            props[k] = round(float(v), 2) if ok[gid] and pd.notna(v) else None
        feats.append({"type": "Feature", "properties": props,
                      "geometry": {"type": "MultiPolygon", "coordinates": geo[gid]}})
    return _dump("toronto.json", {"type": "FeatureCollection", "features": feats})


def export_shapes(g: pd.DataFrame, ind: pd.DataFrame, dong: pd.DataFrame) -> int:
    """시군구(수도권, 2024 경계)와 서울 행정동 폴리곤 + 지표."""
    from shapely import union_all
    adm, geoms = L.load_adm()
    adm["geom"] = geoms
    sgg_feats = []
    for code, grp in adm.groupby("sgg5"):
        u = union_all(list(grp["geom"])).buffer(0)
        tol = 0.0006 if code.startswith("11") else 0.0015
        u = u.simplify(tol, preserve_topology=True)
        r = g.loc[code]; i = ind.loc[code]
        p = {"code": code, "name": r["name"], "seoul": int(code.startswith("11")),
             "pop": int(r["pop_raw"]), "in_all": int(i["in_all"]), "out_all": int(i["out_all"])}
        for k in L.SKEYS:
            p[f"lq_{k}"] = round(float(r[f"lq_{k}"]), 3)
            p[f"lqin_{k}"] = round(float(i[f"lqin_{k}"]), 3)
            p[f"nm_{k}"] = round(float(i[f"nm_{k}"]), 2)
            p[f"in_{k}"], p[f"out_{k}"] = int(i[f"in_{k}"]), int(i[f"out_{k}"])
            p[f"pop_{k}"] = int(r[f"{k}_raw"])
        sgg_feats.append({"type": "Feature", "properties": p,
                          "geometry": {"type": "MultiPolygon", "coordinates": _ring_list(u)}})
    dong_feats = []
    seoul = adm[adm["sido2"] == "11"]
    for _, r in seoul.iterrows():
        u = r["geom"].simplify(0.0003, preserve_topology=True)
        p = {"code": r["adm10"], "name": r["adm_nm"], "gu": r["sggnm"]}
        if r["adm10"] in dong.index:
            q = dong.loc[r["adm10"]]
            p["in_all"] = int(q["in_all"])
            for k in L.SKEYS:
                n = int(q[f"in_{k}"])
                p[f"in_{k}"] = n if n >= SMALL else None
                v = q[f"lqin_{k}"]
                p[f"lqin_{k}"] = round(float(v), 3) if pd.notna(v) and n >= SMALL else None
        dong_feats.append({"type": "Feature", "properties": p,
                           "geometry": {"type": "MultiPolygon", "coordinates": _ring_list(u)}})
    return _dump("shapes.json", {"sgg": {"type": "FeatureCollection", "features": sgg_feats},
                                 "dong": {"type": "FeatureCollection", "features": dong_feats}})


def export_od(g: pd.DataFrame, ind: pd.DataFrame, x: pd.DataFrame) -> int:
    cap = set(g.index)
    nodes = {c: {"name": g.loc[c, "name"], "lat": round(float(g.loc[c, "lat"]), 5),
                 "lon": round(float(g.loc[c, "lon"]), 5), "seoul": int(c.startswith("11"))} for c in g.index}
    flows = {"in": {}, "out": {}, "region_in": {}, "region_out": {}}
    comp = {}
    for s in range(1, 6):
        k = f"s{s}"
        xs = x[x.stage == s]
        fin = xs[(xs.ds == "11") & xs.os.isin(["28", "41"]) & xs.o.isin(cap)]
        fout = xs[(xs.os == "11") & xs.ds.isin(["28", "41"]) & xs.d.isin(cap)]
        for key, f in (("in", fin), ("out", fout)):
            f = f[f.n >= FLOW_MIN].nlargest(FLOW_TOP, "n")
            flows[key][k] = f[["o", "d", "n"]].values.tolist()
        rin = xs[(xs.ds == "11") & ~xs.oR.isin(["서울", "경기", "인천"])].groupby("oR").n.sum()
        rout = xs[(xs.os == "11") & ~xs.dR.isin(["서울", "경기", "인천"])].groupby("dR").n.sum()
        flows["region_in"][k] = {r: int(v) for r, v in rin.items() if v >= SMALL}
        flows["region_out"][k] = {r: int(v) for r, v in rout.items() if v >= SMALL}
        cats = ["서울", "경기", "인천", "비수도권"]
        cat = lambda reg: reg if reg in ("서울", "경기", "인천") else "비수도권"   # noqa: E731
        ci = xs[xs.ds == "11"].assign(c=lambda z: z.oR.map(cat)).groupby(["d", "c"]).n.sum().unstack(fill_value=0)
        co = xs[xs.os == "11"].assign(c=lambda z: z.dR.map(cat)).groupby(["o", "c"]).n.sum().unstack(fill_value=0)
        comp[k] = {"cats": cats,
                   "in": {gu: [int(ci.loc[gu].get(c, 0)) for c in cats] for gu in ci.index},
                   "out": {gu: [int(co.loc[gu].get(c, 0)) for c in cats] for gu in co.index}}
    return _dump("od.json", {"year": YEAR, "nodes": nodes, "flows": flows, "comp": comp,
                             "flow_min": FLOW_MIN})


def export_age() -> tuple[int, dict]:
    out, peaks = {}, {}
    for y in (2023, 2024, 2025):
        a = od.aggregate(y)["age"]
        p = a.pivot_table(index="age", columns=["dir", "region"], values="n", aggfunc="sum", fill_value=0)
        ages = list(range(0, 91))
        inn = p["in"].sum(axis=1).reindex(ages, fill_value=0)
        out_ = p["out"].sum(axis=1).reindex(ages, fill_value=0)
        cap_in = p["in"][[c for c in ("경기", "인천") if c in p["in"]]].sum(axis=1).reindex(ages, fill_value=0)
        cap_out = p["out"][[c for c in ("경기", "인천") if c in p["out"]]].sum(axis=1).reindex(ages, fill_value=0)
        net = inn - out_
        out[str(y)] = {"age": ages, "in": inn.astype(int).tolist(), "out": out_.astype(int).tolist(),
                       "net": net.astype(int).tolist(), "net_cap": (cap_in - cap_out).astype(int).tolist(),
                       "net_rest": ((inn - cap_in) - (out_ - cap_out)).astype(int).tolist()}
        pos = net[net > 0]
        peaks[y] = {"peak_age": int(net.idxmax()), "peak": int(net.max()),
                    "min_age": int(net.loc[15:90].idxmin()), "min": int(net.loc[15:90].min()),
                    "last_pos_age": int(pos.loc[15:40].index.max()), "net_total": int(net.sum())}
    size = _dump("age.json", {"years": out, "peaks": {str(k): v for k, v in peaks.items()}})
    return size, peaks


def export_facilities() -> int:
    f = pd.read_csv(paths.HERE / "facilities.csv")
    cats = {"univ": "대학", "job": "업무중심지", "edu": "학원가", "newtown": "신도시·대규모 택지"}
    return _dump("facilities.json", {"cats": cats, "items": f[["region", "cat", "name", "lat", "lon", "stage_hint"]]
                                     .to_dict(orient="records")})



def facility_stats(d: pd.DataFrame, dong: pd.DataFrame, radius_km: float = 1.5) -> list[dict]:
    """핵심 시설 반경 안/밖 비교: 격자 거주 LQ(해당 단계)와 서울 행정동 유입 LQ의 중위값."""
    f = pd.read_csv(paths.HERE / "facilities.csv")
    f = f[f.region == "capital"]
    adm, geoms = L.load_adm()
    cen = np.array([[g.centroid.y, g.centroid.x] for g in geoms])
    adm["lat"], adm["lon"] = cen[:, 0], cen[:, 1]
    adm = adm.set_index("adm10").join(dong, how="inner")
    adm = adm[adm.index.str.startswith("11")]
    ok = d[d["pop"] >= L.MIN_POP]

    def near(lat, lon, pts):
        dist = L._haversine(lat[:, None], lon[:, None], pts[:, 0][None, :], pts[:, 1][None, :])
        return dist.min(axis=1) <= radius_km

    out = []
    names = {"univ": "대학", "job": "업무중심지", "edu": "학원가", "newtown": "신도시·대규모 택지"}
    for cat, grp in f.groupby("cat"):
        k = grp["stage_hint"].iloc[0]
        pts = grp[["lat", "lon"]].to_numpy(float)
        m = near(ok["lat"].to_numpy(), ok["lon"].to_numpy(), pts)
        row = {"cat": cat, "name": names[cat], "stage": k, "n_fac": int(len(grp)), "radius_km": radius_km,
               "grid_n_near": int(m.sum()), "grid_lq_near": float(ok.loc[m, f"lq_{k}"].median()),
               "grid_lq_far": float(ok.loc[~m, f"lq_{k}"].median())}
        md = near(adm["lat"].to_numpy(), adm["lon"].to_numpy(), pts)
        if md.sum() >= 3:
            row.update(dong_n_near=int(md.sum()), dong_lqin_near=float(adm.loc[md, f"lqin_{k}"].median()),
                       dong_lqin_far=float(adm.loc[~md, f"lqin_{k}"].median()))
        out.append(row)
    return out

def export_summary(R, x, bal, peaks) -> int:
    d, g, ind, t, dong = R["grid"], R["sgg"], R["ind"], R["tor"], R["dong"]
    seoul = [c for c in g.index if c.startswith("11")]
    bc, bt = L.band_lq(d), L.band_lq(t)
    heat = ind.loc[seoul, [f"nm_{k}" for k in L.SKEYS]].join(g["name"]).sort_values("nm_s2", ascending=False)
    scat = g[["name"] + [f"lq_{k}" for k in L.SKEYS] + [f"{k}_raw" for k in L.SKEYS]].join(
        ind[[f"lqin_{k}" for k in L.SKEYS] + [f"nm_{k}" for k in L.SKEYS]])
    adm, _ = L.load_adm()
    adm = adm.set_index("adm10")
    dn = dong.join(adm[["sggnm", "adm_nm"]], how="inner")
    dn = dn[dn.index.str.startswith("11")]
    top_dong = {k: [f"{r.sggnm} {r.adm_nm}" for r in dn.nlargest(8, f"lqin_{k}").itertuples()] for k in L.SKEYS}
    s3 = x[(x.stage == 3) & (x.os == "11") & (x.ds != "11")].groupby("d").n.sum().sort_values(ascending=False)
    s3_top = [{"name": g.loc[c, "name"] if c in g.index else c, "n": int(v)} for c, v in s3.head(10).items()]
    ok = d["pop"] >= L.MIN_POP
    dom_share = {}
    for i, k in enumerate(L.SKEYS):
        dom_share[k] = int((d.loc[ok, "dom"] == i).sum())
    summary = {
        "year": YEAR,
        "stages": [dict(s, color=c) for s, c in zip([{k: v for k, v in st.items() if k != "idx"} for st in L.STAGES],
                                                    STAGE_COLORS)],
        "ref_share_capital": {k: float(d[k].sum() / d["pop"].sum()) for k in L.SKEYS},
        "ref_share_toronto": {k: float(t[k].sum() / t["pop"].sum()) for k in L.SKEYS},
        "bands": {"labels": L.BAND_LABELS, "capital": {k: bc[k].round(3).tolist() for k in L.SKEYS},
                  "toronto": {k: bt[k].round(3).tolist() for k in L.SKEYS}},
        "seoul_balance": bal.round(2).to_dict(orient="records"),
        "age_peaks": {str(k): v for k, v in peaks.items()},
        "heat": {"names": heat["name"].tolist(), "codes": heat.index.tolist(),
                 "z": heat[[f"nm_{k}" for k in L.SKEYS]].round(1).values.tolist()},
        "scatter": {"codes": scat.index.tolist(), "names": scat["name"].tolist(), "seoul": [int(c.startswith("11")) for c in scat.index],
                    **{f"lq_{k}": _r(scat[f"lq_{k}"], 3) for k in L.SKEYS},
                    **{f"lqin_{k}": _r(scat[f"lqin_{k}"], 3) for k in L.SKEYS},
                    **{f"nm_{k}": _r(scat[f"nm_{k}"], 1) for k in L.SKEYS},
                    **{f"pop_{k}": _r(scat[f"{k}_raw"], 0) for k in L.SKEYS}},
        "top_dong_lqin": top_dong, "s3_out_top": s3_top,
        "grid": {"n": int(len(d)), "n_ok": int(ok.sum()), "removed": float(R["det"]["removed"].sum()),
                 "dom_count": dom_share, "mixed": int((d.loc[ok, "dom"] == -1).sum())},
        "toronto": {"n": int(len(t)), "n_ok": int((t["pop"] >= L.MIN_POP).sum())},
        "facility_stats": facility_stats(d, dong),
        "ts": {"years": sorted(R["ts"]),
               "bands": {str(y): {k: L.band_lq(t)[k].round(3).tolist() for k in L.SKEYS} for y, t in sorted(R["ts"].items())},
               "seoul_share": {str(y): {k: round(float(t.loc[t["seoul"].fillna(False).astype(bool), k].sum() / t[k].sum()), 4) for k in L.SKEYS}
                               for y, t in sorted(R["ts"].items())},
               "ref_share": {str(y): {k: round(float(t[k].sum() / t["pop"].sum()), 4) for k in L.SKEYS} for y, t in sorted(R["ts"].items())},
               "dom_count": {str(y): {k: int(((t["pop"] >= L.MIN_POP) & (t["dom"] == i)).sum()) for i, k in enumerate(L.SKEYS)}
                             for y, t in sorted(R["ts"].items())}},
        "seoul_in_origin": seoul_in_origin(x),
        "check": {"kosis_total_2024": 6283319, "kosis_seoul_in_2024": 1221380, "kosis_seoul_out_2024": 1266072},
    }
    return _dump("summary.json", summary, indent=1)



def seoul_in_origin(x: pd.DataFrame) -> dict:
    """서울 밖에서 서울로 들어온 사람의 출발지 구성 (단계별, %)."""
    i = x[(x.ds == "11") & (x.os != "11")]
    out = {}
    for s in range(1, 6):
        z = i[i.stage == s]
        tot = z.n.sum()
        grp = z.assign(c=z.oR.where(z.oR.isin(["경기", "인천"]), "비수도권")).groupby("c").n.sum()
        out[f"s{s}"] = {c: round(100 * float(v) / tot, 1) for c, v in grp.items()} | {"total": int(tot)}
    o = x[(x.os == "11") & (x.ds != "11")]
    for s in range(1, 6):
        z = o[o.stage == s]
        tot = z.n.sum()
        grp = z.assign(c=z.dR.where(z.dR.isin(["경기", "인천"]), "비수도권")).groupby("c").n.sum()
        out[f"s{s}_out"] = {c: round(100 * float(v) / tot, 1) for c, v in grp.items()} | {"total": int(tot)}
    return out

def build(verbose: bool = True):
    paths.ensure_dirs()
    R = compute()
    x = seoul_flows(R["mdis"]["sgg"])
    bal = seoul_balance(x, R["sgg"])
    sizes = {"capital_grid.json (+ts)": export_grid(R["grid"], R["ts"]),
             "toronto.json": export_toronto(R["tor"], R["tgeo"]),
             "shapes.json": export_shapes(R["sgg"], R["ind"], R["dong"]),
             "od.json": export_od(R["sgg"], R["ind"], x)}
    s, peaks = export_age()
    sizes["age.json"] = s
    sizes["facilities.json"] = export_facilities()
    sizes["summary.json"] = export_summary(R, x, bal, peaks)
    R.update(flows=x, balance=bal, peaks=peaks, sizes=sizes)
    if verbose:
        for k, v in sizes.items():
            print(f"  site/data/{k:<20} {v / 1024:8.0f} KB")
    return R


if __name__ == "__main__":
    build()
