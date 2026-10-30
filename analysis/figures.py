"""노트북용 정적 그림 (matplotlib). 웹페이지와 같은 색·구간을 쓴다.

GitHub 에서도 노트북 그림이 보이도록 정적 그림으로 만든다 (웹페이지는 Leaflet·Plotly 로 상호작용).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

import kgeo
import lifestage as L
import paths

STAGE_COLORS = dict(zip(L.SKEYS, ["#c2417a", "#eb6834", "#1baf7a", "#2a78d6", "#9a6614"]))
DIV = ["#1f5fa8", "#5f93d1", "#b9d0ec", "#ebeae6", "#f0bfb2", "#dc735c", "#b2342b"]
LQ_BR = [0.67, 0.83, 0.95, 1.05, 1.2, 1.5]
NM_BR = [-30, -15, -5, 5, 15, 30]
INK, INK2, INK3, RULE = "#182230", "#4a5568", "#7d8796", "#e8ebf0"
SMALL, MIXED = "#dde1e6", "#c5ccd5"
FAC_MARK = {"univ": ("^", "대학"), "job": ("s", "업무중심지"), "edu": ("D", "학원가"), "newtown": ("o", "신도시·택지")}
LAT0 = 37.5


def setup():
    """한글 글꼴(koreanize_matplotlib → 맑은 고딕 → 나눔고딕)과 기본 모양."""
    try:
        import koreanize_matplotlib  # noqa: F401
    except ImportError:
        names = {f.name for f in mpl.font_manager.fontManager.ttflist}
        for f in ("Malgun Gothic", "AppleGothic", "NanumGothic", "Noto Sans CJK KR"):
            if f in names:
                plt.rcParams["font.family"] = f
                break
    plt.rcParams.update({
        "axes.unicode_minus": False, "axes.spines.top": False, "axes.spines.right": False,
        "axes.edgecolor": "#c9cfd8", "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
        "axes.titleweight": "bold", "axes.titlesize": 12, "axes.titlelocation": "left", "axes.titlecolor": INK,
        "figure.dpi": 110, "savefig.dpi": 150, "figure.facecolor": "white", "legend.frameon": False,
    })


def _norm(br):
    return ListedColormap(DIV), BoundaryNorm([-1e9] + list(br) + [1e9], len(DIV))


def _class_legend(fig, br, title, loc=(0.5, 0.02), labels=None):
    labels = labels or [f"{b:g}" for b in br]
    handles = [Patch(color=c) for c in DIV]
    txt = [f"< {labels[0]}"] + [f"{labels[i]}–{labels[i + 1]}" for i in range(len(labels) - 1)] + [f"≥ {labels[-1]}"]
    fig.legend(handles, txt, loc="lower center", bbox_to_anchor=loc, ncol=7, title=title, fontsize=8, title_fontsize=9,
               handlelength=1.4, columnspacing=1.0)


# ------------------------------------------------------------------ 경계 (캐시)
_CACHE: dict = {}


def _adm():
    if "adm" not in _CACHE:
        adm, geoms = L.load_adm()
        adm["geom"] = geoms
        _CACHE["adm"] = adm
    return _CACHE["adm"]


def sgg_shapes():
    """시군구 폴리곤 (경위도, 단순화) → {code: [ (lon, lat) 배열, ... ]}"""
    if "sgg" not in _CACHE:
        from shapely import union_all
        out = {}
        for code, grp in _adm().groupby("sgg5"):
            u = union_all(list(grp["geom"])).buffer(0).simplify(0.0012)
            polys = [u] if u.geom_type == "Polygon" else list(u.geoms)
            out[code] = [np.asarray(p.exterior.coords) for p in polys]
        _CACHE["sgg"] = out
    return _CACHE["sgg"]


def _lonlat_ax(ax):
    ax.set_aspect(1 / np.cos(np.radians(LAT0)))
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)


def _outline(ax, proj=None, lw=0.35, color="#3d4757", alpha=0.55):
    for code, rings in sgg_shapes().items():
        for r in rings:
            if proj:
                x, y = kgeo.forward(r[:, 1], r[:, 0], "5179")
            else:
                x, y = r[:, 0], r[:, 1]
            ax.plot(x, y, color=color, lw=lw * (0.8 if code.startswith("11") else 1.2), alpha=alpha, zorder=3)


def _facilities(ax, proj=None, cats=("univ", "job", "edu", "newtown"), size=22, label=False):
    f = pd.read_csv(paths.HERE / "facilities.csv")
    f = f[(f.region == "capital") & f.cat.isin(cats)]
    for cat, g in f.groupby("cat"):
        x, y = (kgeo.forward(g.lat.values, g.lon.values, "5179") if proj else (g.lon.values, g.lat.values))
        m, _ = FAC_MARK[cat]
        face = "white" if cat == "newtown" else INK
        ax.scatter(x, y, marker=m, s=size, c=face, edgecolors=INK if cat == "newtown" else "white", linewidths=1.0, zorder=6)
        if label:
            for xi, yi, n in zip(x, y, g.name):
                ax.annotate(n, (xi, yi), xytext=(4, 2), textcoords="offset points", fontsize=7, color=INK, zorder=7,
                            path_effects=[pe.withStroke(linewidth=2, foreground="white")])


def _fac_legend(ax, loc="lower left"):
    hs = [Line2D([], [], marker=m, ls="", mfc="white" if c == "newtown" else INK, mec=INK, ms=6, label=n) for c, (m, n) in FAC_MARK.items()]
    ax.legend(handles=hs, loc=loc, fontsize=7.5, title="핵심 시설", title_fontsize=8)


# ------------------------------------------------------------------ ① 거주 LQ
def grid_raster(d: pd.DataFrame, values) -> tuple[np.ndarray, list]:
    cx = ((d["x"].to_numpy() - 500 - 700_000) // 1000).astype(int)
    cy = ((d["y"].to_numpy() - 500 - 1_300_000) // 1000).astype(int)
    c0, r0 = cx.min(), cy.min()
    arr = np.full((cy.max() - r0 + 1, cx.max() - c0 + 1), np.nan)
    arr[cy - r0, cx - c0] = np.asarray(values, float)
    ext = [700_000 + c0 * 1000, 700_000 + (cx.max() + 1) * 1000, 1_300_000 + r0 * 1000, 1_300_000 + (cy.max() + 1) * 1000]
    return arr, ext


def fig_stage_maps(d: pd.DataFrame):
    """생애단계 5개 거주 LQ + 우세 생애단계 (수도권 1km 격자)."""
    cm, norm = _norm(LQ_BR)
    fig, axes = plt.subplots(2, 3, figsize=(13, 10.4))
    ok = d["pop"] >= L.MIN_POP
    main = (d["pop_raw"] > 0) & (d["lon"] > 126.40)          # 옹진 먼 섬 제외하고 화면 범위 잡기
    xlim = (d.loc[main, "x"].min() - 1500, d.loc[main, "x"].max() + 1500)
    ylim = (d.loc[main, "y"].min() - 1500, d.loc[main, "y"].max() + 1500)
    small, _ = grid_raster(d, np.where(~ok & (d["pop_raw"] > 0), 1, np.nan))
    for ax, s in zip(axes.flat, L.STAGES):
        arr, ext = grid_raster(d, d[f"lq_{s['key']}"].where(ok))
        ax.imshow(small, extent=ext, origin="lower", cmap=ListedColormap([SMALL]), interpolation="nearest", zorder=1)
        ax.imshow(arr, extent=ext, origin="lower", cmap=cm, norm=norm, interpolation="nearest", zorder=2)
        _outline(ax, proj=True)
        ax.set_title(f"{s['label']}세 · {s['name']}", color=STAGE_COLORS[s["key"]])
        ax.set_xlim(xlim); ax.set_ylim(ylim); ax.set_aspect("equal"); ax.axis("off")
    ax = axes.flat[5]
    dom = d["dom"].to_numpy()
    arr, ext = grid_raster(d, np.where(d["pop_raw"] > 0, dom + 2, np.nan))
    dcm = ListedColormap([SMALL, MIXED] + [STAGE_COLORS[k] for k in L.SKEYS])
    ax.imshow(arr, extent=ext, origin="lower", cmap=dcm, vmin=-0.5, vmax=6.5, interpolation="nearest", zorder=2)
    _outline(ax, proj=True)
    _facilities(ax, proj=True, size=16)
    ax.set_title("우세 생애단계 (LQ 최고 단계, < 1.2 는 혼합)")
    ax.set_xlim(xlim); ax.set_ylim(ylim); ax.set_aspect("equal"); ax.axis("off")
    hs = [Patch(color=STAGE_COLORS[k], label=L.LABEL[k]) for k in L.SKEYS] + [Patch(color=MIXED, label="혼합"), Patch(color=SMALL, label="250명 미만")]
    ax.legend(handles=hs, loc="lower left", fontsize=7.5, ncol=2, frameon=True, framealpha=0.92, edgecolor="none")
    _class_legend(fig, LQ_BR, "거주 LQ (1 = 수도권 평균, 회색 = 인구 250명 미만)")
    fig.suptitle("① 생애단계별 거주 LQ — 수도권 1km 격자 2024 (20~34세는 시설 인구 보정 후)", x=0.01, ha="left", fontsize=14, fontweight="bold", color=INK)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.9, bottom=0.07, wspace=0.02, hspace=0.08)
    return fig


def fig_bands(d: pd.DataFrame, t: pd.DataFrame):
    """도심 거리대별 생애단계 LQ — 수도권 vs 토론토 (한 y축)."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4), sharey=True)
    for ax, (df, title, center) in zip(axes, [(d, "수도권 2024", "서울시청"), (t, "토론토 2021", "King & Bay")]):
        b = L.band_lq(df)
        xs = np.arange(len(b))
        for k in L.SKEYS:
            ax.plot(xs, b[k].values, color=STAGE_COLORS[k], lw=2, marker="o", ms=4, label=L.LABEL[k])
            ax.annotate(L.LABEL[k], (xs[-1], b[k].values[-1]), xytext=(6, 0), textcoords="offset points", fontsize=8, color=STAGE_COLORS[k], va="center")
        ax.axhline(1, color=INK3, lw=1, ls=":")
        ax.set_xticks(xs, b.index.astype(str), fontsize=9)
        ax.set_xlabel(f"{center}에서 (km)")
        ax.set_title(title)
        ax.grid(axis="y", color=RULE)
        ax.set_xlim(-0.3, len(b) - 0.2)
    axes[0].set_ylabel("거주 LQ")
    axes[0].legend(ncol=5, fontsize=8, loc="upper right")
    fig.tight_layout()
    return fig


# ------------------------------------------------------------------ ②③ 이동
def fig_age(age_by_year: dict, year: int = 2024):
    """서울 경계를 넘는 이동의 나이별 순이동 (상대 지역별 막대 + 합계 선, 다른 해는 회색 선)."""
    fig, ax = plt.subplots(figsize=(12, 4.6))
    ages = np.arange(0, 91)

    def series(a):
        p = a.pivot_table(index="age", columns=["dir", "region"], values="n", aggfunc="sum", fill_value=0)
        inn, out = p["in"].sum(axis=1).reindex(ages, fill_value=0), p["out"].sum(axis=1).reindex(ages, fill_value=0)
        cin = p["in"][[c for c in ("경기", "인천") if c in p["in"]]].sum(axis=1).reindex(ages, fill_value=0)
        cout = p["out"][[c for c in ("경기", "인천") if c in p["out"]]].sum(axis=1).reindex(ages, fill_value=0)
        return inn - out, cin - cout, (inn - cin) - (out - cout)

    net, cap, rest = series(age_by_year[year])
    pos = lambda v: np.where(v > 0, v, 0)   # noqa: E731
    neg = lambda v: np.where(v < 0, v, 0)   # noqa: E731
    ax.bar(ages, pos(rest), color="#a7b2c1", width=0.85, label="비수도권과")
    ax.bar(ages, pos(cap), bottom=pos(rest), color="#3b4a5f", width=0.85, label="경기·인천과")
    ax.bar(ages, neg(rest), color="#a7b2c1", width=0.85)
    ax.bar(ages, neg(cap), bottom=neg(rest), color="#3b4a5f", width=0.85)
    for y in age_by_year:
        if y != year:
            n2, _, _ = series(age_by_year[y])
            ax.plot(ages, n2.values, color=INK3, lw=1, ls="--", label=f"{y} 합계")
    ax.plot(ages, net.values, color=INK, lw=2, label=f"{year} 합계")
    ax.axhline(0, color=INK, lw=0.8)
    top = ax.get_ylim()[1]
    rng = {"s1": (19.5, 24.5), "s2": (24.5, 34.5), "s3": (34.5, 44.5), "s4": (44.5, 64.5), "s5": (64.5, 90.5)}
    for k, (a, b) in rng.items():
        ax.axvspan(a, b, ymin=0.965, ymax=1.0, color=STAGE_COLORS[k], lw=0)
        ax.text((a + b) / 2, top * 1.02, L.LABEL[k], ha="center", va="bottom", fontsize=8, color=INK2)
    pk, mn = int(net.idxmax()), int(net.loc[15:].idxmin())
    ax.annotate(f"{pk}세 +{int(net[pk]):,}명", (pk, net[pk]), xytext=(18, 6), textcoords="offset points", fontsize=10, color=INK)
    ax.annotate(f"{mn}세 {int(net[mn]):,}명", (mn, net[mn]), xytext=(14, -14), textcoords="offset points", fontsize=10, color=INK)
    ax.set_xlim(-0.8, 90.8); ax.set_xticks(range(0, 91, 5))
    ax.set_xlabel("만 나이"); ax.set_ylabel("순이동 (명)")
    ax.yaxis.set_major_formatter(mpl.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.grid(axis="y", color=RULE)
    ax.legend(ncol=5, fontsize=8.5, loc="lower right")
    ax.set_title(f"서울의 나이별 순이동 (서울 밖 ↔ 서울), {year}", pad=18)
    fig.tight_layout()
    return fig


def fig_heat(ind: pd.DataFrame, names: pd.Series):
    """서울 25개 구 × 5단계 순유입 강도."""
    seoul = [c for c in ind.index if c.startswith("11")]
    h = ind.loc[seoul, [f"nm_{k}" for k in L.SKEYS]].join(names).sort_values("nm_s2", ascending=False)
    z = h[[f"nm_{k}" for k in L.SKEYS]].to_numpy()
    cm, norm = _norm(NM_BR)
    fig, ax = plt.subplots(figsize=(6.2, 8.6))
    ax.imshow(z, cmap=cm, norm=norm, aspect="auto")
    ax.set_xticks(range(5), [L.LABEL[k] for k in L.SKEYS]); ax.xaxis.tick_top()
    ax.set_yticks(range(len(h)), h["name"])
    ax.set_xticks(np.arange(-0.5, 5), minor=True); ax.set_yticks(np.arange(-0.5, len(h)), minor=True)
    ax.grid(which="minor", color="white", lw=2); ax.tick_params(which="minor", length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    for i in range(z.shape[0]):
        for j in range(z.shape[1]):
            if abs(z[i, j]) >= 30:
                ax.text(j, i, f"{z[i, j]:.0f}", ha="center", va="center", fontsize=8.5,
                        color="white" if abs(z[i, j]) >= 45 else INK)
    _class_legend(fig, NM_BR, "순유입 강도 (인구 천 명당, 2024)", loc=(0.5, -0.01), labels=["-30", "-15", "-5", "+5", "+15", "+30"])
    ax.set_title("서울 구별 순유입 강도 (③)", pad=26)
    fig.subplots_adjust(left=0.2, right=0.98, top=0.9, bottom=0.12)
    return fig


def _arc(a, b, bend=0.18, n=28):
    (x1, y1), (x2, y2) = a, b
    mx, my, dx, dy = (x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1
    cx, cy = mx - dy * bend, my + dx * bend
    t = np.linspace(0, 1, n)
    return (1 - t) ** 2 * x1 + 2 * (1 - t) * t * cx + t ** 2 * x2, (1 - t) ** 2 * y1 + 2 * (1 - t) * t * cy + t ** 2 * y2


def fig_flows(flows: pd.DataFrame, sgg: pd.DataFrame, ind: pd.DataFrame, stage: str, direction: str = "in", n: int = 30, ax=None):
    """시군구 순유입 강도 + 서울 관련 흐름 상위 n개 (경기·인천 ↔ 서울 구)."""
    s = int(stage[1])
    fig = None
    if ax is None:
        fig, ax = plt.subplots(figsize=(7.4, 7.4))
    cm, norm = _norm(NM_BR)
    shapes = sgg_shapes()
    for code, rings in shapes.items():
        v = ind.loc[code, f"nm_{stage}"] if code in ind.index else np.nan
        col = cm(norm(v)) if pd.notna(v) else SMALL
        for r in rings:
            ax.fill(r[:, 0], r[:, 1], color=col, lw=0.4, ec="white", zorder=1)
    x = flows[flows.stage == s]
    if direction == "in":
        f = x[(x.ds == "11") & x.os.isin(["28", "41"])]
    else:
        f = x[(x.os == "11") & x.ds.isin(["28", "41"])]
    f = f[f.o.isin(sgg.index) & f.d.isin(sgg.index)].nlargest(n, "n")
    mx = f.n.max()
    for o, d, v in f[["o", "d", "n"]].values[::-1]:
        a, b = sgg.loc[o, ["lon", "lat"]].values, sgg.loc[d, ["lon", "lat"]].values
        xs, ys = _arc(a, b)
        w = 0.8 + 4.5 * np.sqrt(v / mx)
        ax.plot(xs, ys, color="white", lw=w + 1.8, solid_capstyle="round", zorder=4)
        ax.plot(xs, ys, color=STAGE_COLORS[stage], lw=w, solid_capstyle="round", zorder=5)
        ax.scatter([b[0]], [b[1]], s=8 + w * 3, c=INK, edgecolors="white", linewidths=0.6, zorder=6)
    _facilities(ax, size=14)
    ax.set_xlim(126.45, 127.75); ax.set_ylim(36.95, 38.05)
    _lonlat_ax(ax)
    ax.set_title(f"{L.LABEL[stage]}세 · {'서울로 들어오기' if direction == 'in' else '서울에서 나가기'} 상위 {len(f)}개", color=STAGE_COLORS[stage], fontsize=11)
    return fig or ax.figure


def fig_flow_pair(flows, sgg, ind):
    """25~34세 들어오기 / 35~44세 나가기."""
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 7))
    fig_flows(flows, sgg, ind, "s2", "in", ax=axes[0])
    fig_flows(flows, sgg, ind, "s3", "out", ax=axes[1])
    _class_legend(fig, NM_BR, "색 = 시군구 순유입 강도 (인구 천 명당) · 선 두께 = 이동자 수 · 점 = 도착지", loc=(0.5, 0.0), labels=["-30", "-15", "-5", "+5", "+15", "+30"])
    _fac_legend(axes[1])
    fig.subplots_adjust(left=0.01, right=0.99, top=0.95, bottom=0.1, wspace=0.03)
    return fig


def fig_dong(dong: pd.DataFrame, stages=("s1", "s2", "s3")):
    """서울 행정동 유입 LQ (②) — 단계별 작은 지도 + 핵심 시설."""
    adm = _adm()
    seoul = adm[adm.sido2 == "11"]
    cm, norm = _norm(LQ_BR)
    fig, axes = plt.subplots(1, len(stages), figsize=(5.2 * len(stages), 5.4))
    for ax, k in zip(np.atleast_1d(axes), stages):
        for _, r in seoul.iterrows():
            v = dong[f"lqin_{k}"].get(r.adm10, np.nan) if r.adm10 in dong.index else np.nan
            col = cm(norm(v)) if pd.notna(v) else SMALL
            polys = [r.geom] if r.geom.geom_type == "Polygon" else list(r.geom.geoms)
            for p in polys:
                xy = np.asarray(p.exterior.coords)
                ax.fill(xy[:, 0], xy[:, 1], color=col, ec="white", lw=0.3, zorder=1)
        for code, rings in sgg_shapes().items():
            if code.startswith("11"):
                for rr in rings:
                    ax.plot(rr[:, 0], rr[:, 1], color=INK, lw=0.6, alpha=0.6, zorder=3)
        cat = {"s1": ("univ",), "s2": ("job",), "s3": ("edu",)}.get(k, ())
        _facilities(ax, cats=cat, size=26, label=True)
        ax.set_xlim(126.76, 127.19); ax.set_ylim(37.42, 37.70)
        _lonlat_ax(ax)
        ax.set_title(f"{L.LABEL[k]}세 유입 LQ + {FAC_MARK[cat[0]][1] if cat else ''}", color=STAGE_COLORS[k], fontsize=11)
    _class_legend(fig, LQ_BR, "서울 행정동 유입 LQ (같은 동 안 이사 제외, 2024)", loc=(0.5, 0.0))
    fig.subplots_adjust(left=0.01, right=0.99, top=0.93, bottom=0.14, wspace=0.03)
    return fig


def fig_scatter(sgg: pd.DataFrame, ind: pd.DataFrame, stages=("s2", "s3")):
    """① 거주 LQ × ② 유입 LQ (시군구, 로그), 색 = ③ 부호, 크기 = 그 단계 인구."""
    fig, axes = plt.subplots(1, len(stages), figsize=(6.4 * len(stages), 5.6))
    for ax, k in zip(np.atleast_1d(axes), stages):
        df = sgg[[f"lq_{k}", f"{k}_raw", "name"]].join(ind[[f"lqin_{k}", f"nm_{k}"]]).dropna()
        size = 12 + 260 * np.sqrt(df[f"{k}_raw"] / df[f"{k}_raw"].max())
        colors = np.where(df[f"nm_{k}"] >= 0, DIV[5], DIV[1])
        edge = np.where(df.index.str.startswith("11"), INK, "white")
        ax.scatter(df[f"lq_{k}"], df[f"lqin_{k}"], s=size, c=colors, edgecolors=edge, linewidths=0.9, alpha=0.88, zorder=3)
        ax.set_xscale("log"); ax.set_yscale("log")
        ax.axvline(1, color=INK3, ls=":", lw=1); ax.axhline(1, color=INK3, ls=":", lw=1)
        score = np.abs(np.log(df[f"lq_{k}"])) + np.abs(np.log(df[f"lqin_{k}"]))
        for c in score.nlargest(8).index:
            ax.annotate(df.loc[c, "name"], (df.loc[c, f"lq_{k}"], df.loc[c, f"lqin_{k}"]), xytext=(4, 4), textcoords="offset points", fontsize=8, color=INK)
        tick = [0.5, 0.7, 1, 1.4, 2, 3]
        ax.set_xticks(tick, [f"{t:g}" for t in tick]); ax.set_yticks(tick, [f"{t:g}" for t in tick])
        ax.minorticks_off()
        ax.set_xlabel(f"{L.LABEL[k]}세 거주 LQ (①)"); ax.set_ylabel("유입 LQ (②)")
        ax.set_title(f"{L.LABEL[k]}세", color=STAGE_COLORS[k])
        ax.grid(color=RULE)
        ur = df[(df[f"lq_{k}"] >= 1) & (df[f"lqin_{k}"] >= 1)]
        ax.text(0.99, 0.02, f"오른쪽 위 {len(ur)}곳 중 순유출 {int((ur[f'nm_{k}'] < 0).sum())}곳", transform=ax.transAxes, ha="right", fontsize=8.5, color=INK2)
    hs = [Line2D([], [], marker="o", ls="", mfc=DIV[5], mec="white", ms=8, label="순유입 (남는 곳)"),
          Line2D([], [], marker="o", ls="", mfc=DIV[1], mec="white", ms=8, label="순유출 (빠지는 곳)"),
          Line2D([], [], marker="o", ls="", mfc="white", mec=INK, ms=8, label="서울 구 (테두리)")]
    fig.legend(handles=hs, loc="lower center", ncol=3, fontsize=9)
    fig.subplots_adjust(left=0.07, right=0.98, top=0.92, bottom=0.18, wspace=0.22)
    return fig


def fig_facility(stats: list[dict]):
    """핵심 시설 1.5km 안/밖 — 거주 LQ와 서울 행정동 유입 LQ 중위값."""
    df = pd.DataFrame(stats).set_index("name")
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 3.4), sharey=True)
    ys = np.arange(len(df))
    for ax, (near, far, title) in zip(axes, [("grid_lq_near", "grid_lq_far", "거주 LQ (① 격자 중위)"),
                                             ("dong_lqin_near", "dong_lqin_far", "유입 LQ (② 서울 행정동 중위)")]):
        ax.barh(ys + 0.2, df[near], height=0.36, color=[STAGE_COLORS[k] for k in df["stage"]], label="1.5km 안")
        ax.barh(ys - 0.2, df[far], height=0.36, color="#c9d1dc", label="밖")
        for y, a, b in zip(ys, df[near], df[far]):
            if pd.notna(a):
                ax.text(a + 0.02, y + 0.2, f"{a:.2f}", va="center", fontsize=8.5, color=INK)
            if pd.notna(b):
                ax.text(b + 0.02, y - 0.2, f"{b:.2f}", va="center", fontsize=8.5, color=INK2)
        ax.axvline(1, color=INK3, ls=":", lw=1)
        ax.set_title(title, fontsize=11)
        ax.set_xlim(0, 1.75)
    axes[0].set_yticks(ys, [f"{n} → {L.LABEL[k]}세" for n, k in zip(df.index, df["stage"])])
    axes[0].legend(loc="lower right", fontsize=8.5)
    fig.tight_layout()
    return fig


def fig_stage_timeseries(ts: dict, d24: pd.DataFrame, stages=("s2", "s3", "s5")):
    """생애단계 거주 LQ 시계열 (2000~2024) — 행 = 단계, 열 = 연도."""
    cm, norm = _norm(LQ_BR)
    years = sorted(ts)
    fig, axes = plt.subplots(len(stages), len(years), figsize=(2.75 * len(years), 3.05 * len(stages)))
    main = (d24["pop_raw"] > 0) & (d24["lon"] > 126.40)
    xlim = (d24.loc[main, "x"].min() - 1500, d24.loc[main, "x"].max() + 1500)
    ylim = (d24.loc[main, "y"].min() - 1500, d24.loc[main, "y"].max() + 1500)
    for r, k in enumerate(stages):
        for c, y in enumerate(years):
            ax = axes[r, c]
            t = ts[y].reindex(d24.index)
            ok = t["pop"] >= L.MIN_POP
            small, ext = grid_raster(d24, np.where(~ok & (t["pop_raw"] > 0), 1, np.nan))
            arr, _ = grid_raster(d24, t[f"lq_{k}"].where(ok))
            ax.imshow(small, extent=ext, origin="lower", cmap=ListedColormap([SMALL]), interpolation="nearest", zorder=1)
            ax.imshow(arr, extent=ext, origin="lower", cmap=cm, norm=norm, interpolation="nearest", zorder=2)
            _outline(ax, proj=True, lw=0.25, alpha=0.4)
            ax.set_xlim(xlim); ax.set_ylim(ylim); ax.set_aspect("equal"); ax.axis("off")
            if r == 0:
                ax.set_title(str(y), fontsize=12, color=INK, loc="center")
            if c == 0:
                ax.text(-0.04, 0.5, f"{L.LABEL[k]}세", transform=ax.transAxes, rotation=90, ha="right", va="center",
                        fontsize=12, fontweight="bold", color=STAGE_COLORS[k])
    _class_legend(fig, LQ_BR, "거주 LQ (기준 = 그해 수도권, 회색 = 인구 250명 미만)", loc=(0.5, 0.0))
    fig.suptitle("① 거주 LQ 시계열 — 수도권 1km 격자 2000~2024 (해마다 시설 인구 보정)", x=0.01, ha="left", fontsize=14, fontweight="bold", color=INK)
    fig.subplots_adjust(left=0.03, right=0.995, top=0.92, bottom=0.08, wspace=0.01, hspace=0.04)
    return fig
