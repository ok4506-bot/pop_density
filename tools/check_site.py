"""배포 전 점검 — 배포전_확인.bat 또는 노트북 마지막 셀에서 실행.

python tools/check_site.py      (github_upload 폴더에서)
FAIL 이 하나라도 있으면 종료코드 1.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"
DATA = SITE / "data"
NEED = ["index.html", "assets/app.js", "assets/style.css",
        "assets/vendor/leaflet/leaflet.js", "assets/vendor/leaflet/leaflet.css",
        "assets/vendor/plotly/plotly-cartesian.min.js",
        "assets/vendor/katex/katex.min.js", "assets/vendor/katex/katex.min.css", "assets/vendor/katex/auto-render.min.js"]
JSONS = ["summary", "capital_grid", "capital_ts", "toronto", "shapes", "od", "age", "facilities"]
CF_FILE_LIMIT = 25 * 1024 * 1024        # Cloudflare 정적 파일 1개 한도 25 MiB
GH_WARN = 50 * 1024 * 1024              # GitHub 경고 50 MB (한도 100 MB)
FORBID = [r"\.env", r"\.zip$", r"mdis_\d{4}_", r"인구관련연간자료", r"_census_reqdoc", r"\.gpkg$", r"census_wide_"]

results = []


def rep(level, msg):
    results.append(level)
    mark = {"PASS": "  [PASS]", "WARN": "  [WARN]", "FAIL": "  [FAIL]"}[level]
    print(f"{mark} {msg}")


def no_nan(x):
    raise ValueError(f"NaN/Infinity 값이 있음: {x}")


def main():
    print(f"점검 대상: {REPO}\n")
    print("1) 필수 파일")
    miss = [p for p in NEED if not (SITE / p).exists()]
    rep("FAIL" if miss else "PASS", f"웹페이지·라이브러리 파일 {len(NEED) - len(miss)}/{len(NEED)}" + (f" — 없음: {miss}" if miss else ""))

    print("2) 자료(JSON)")
    data = {}
    for name in JSONS:
        p = DATA / f"{name}.json"
        if not p.exists():
            rep("FAIL", f"site/data/{name}.json 없음 — 노트북의 '웹 자료 내보내기' 셀(또는 analysis/build_site.py)을 실행하세요")
            continue
        try:
            data[name] = json.loads(p.read_text(encoding="utf-8"), parse_constant=no_nan)
            rep("PASS", f"{name}.json 읽기 ({p.stat().st_size / 1024:,.0f} KB)")
        except Exception as e:  # noqa: BLE001
            rep("FAIL", f"{name}.json 을 읽을 수 없음: {e}")

    print("3) index.html 이 부르는 파일")
    html = (SITE / "index.html").read_text(encoding="utf-8") if (SITE / "index.html").exists() else ""
    refs = re.findall(r'(?:src|href)="([^"#:]+)"', html)
    bad = [r for r in refs if not r.startswith(("http", "data:", "//")) and not (SITE / r).exists()]
    rep("FAIL" if bad else "PASS", f"로컬 참조 {len(refs)}개" + (f" — 없는 파일: {bad}" if bad else " 모두 있음"))
    js = (SITE / "assets" / "app.js").read_text(encoding="utf-8") if (SITE / "assets" / "app.js").exists() else ""
    for name in JSONS:
        if name not in js:
            rep("WARN", f"app.js 에서 {name}.json 을 부르지 않음")
    ext = sorted(set(re.findall(r"https://[a-zA-Z0-9.\-{}]+", html + js)))
    print("     외부 주소(인터넷 필요):", ", ".join(ext))
    if "cartocdn" in html + js:
        rep("WARN", "CARTO 타일은 API 키 없이 'API KEY REQUIRED' 그림을 돌려줄 수 있음")

    print("4) 공개 자료 원칙")
    if "od" in data:
        fl = data["od"]["flows"]
        small = [n for d in ("in", "out") for k in fl[d] for (_, _, n) in fl[d][k] if n < 5]
        rep("FAIL" if small else "PASS", "이동 흐름 5명 미만 칸 " + (f"{len(small)}개 있음" if small else "없음"))
    if "shapes" in data:
        small = [v for f in data["shapes"]["dong"]["features"] for k, v in f["properties"].items()
                 if re.fullmatch(r"in_s\d", k) and v is not None and v < 5]
        rep("FAIL" if small else "PASS", "행정동 전입 5명 미만 칸 " + (f"{len(small)}개 있음" if small else "없음"))

    print("5) 크기와 올리면 안 되는 파일")
    files = [p for p in REPO.rglob("*") if p.is_file() and ".git" not in p.parts]
    total = sum(p.stat().st_size for p in files)
    site_total = sum(p.stat().st_size for p in SITE.rglob("*") if p.is_file())
    big_cf = [p for p in SITE.rglob("*") if p.is_file() and p.stat().st_size > CF_FILE_LIMIT]
    big_gh = [p for p in files if p.stat().st_size > GH_WARN]
    rep("FAIL" if big_cf else "PASS", f"웹 폴더 {site_total / 1024 / 1024:.1f} MB, 25 MiB 넘는 파일 {len(big_cf)}개")
    rep("WARN" if big_gh else "PASS", f"저장소 전체 {total / 1024 / 1024:.1f} MB ({len(files)}개 파일), 50 MB 넘는 파일 {len(big_gh)}개")
    forbid = [str(p.relative_to(REPO)) for p in files if any(re.search(f, p.name) for f in FORBID)]
    rep("FAIL" if forbid else "PASS", "원자료·키 파일(.env, zip, MDIS, gpkg 등) " + (f"발견: {forbid}" if forbid else "없음"))
    if any("__pycache__" in p.parts for p in files):
        rep("WARN", "__pycache__ 폴더가 있음 (.gitignore 가 막으므로 올라가지는 않음)")

    print("6) Cloudflare 설정")
    wj = REPO / "wrangler.jsonc"
    if wj.exists():
        t = wj.read_text(encoding="utf-8")
        name = re.search(r'"name"\s*:\s*"([^"]+)"', t)
        dirok = re.search(r'"directory"\s*:\s*"\./site"', t)
        rep("PASS" if name and dirok else "FAIL", f"wrangler.jsonc name = {name.group(1) if name else '?'}, assets = ./site")
    else:
        rep("FAIL", "wrangler.jsonc 없음")
    repo_url = re.search(r"REPO_URL = '([^']+)'", js)
    if repo_url:
        print(f"     app.js 의 GitHub 주소: {repo_url.group(1)}  (저장소 이름이 다르면 바꾸세요)")
    gi = REPO / ".gitignore"
    rep("PASS" if gi.exists() else "WARN", ".gitignore " + ("있음" if gi.exists() else "없음"))

    n_fail, n_warn = results.count("FAIL"), results.count("WARN")
    print(f"\n결과: FAIL {n_fail} · WARN {n_warn} · PASS {results.count('PASS')}")
    print("→ 배포해도 됩니다." if n_fail == 0 else "→ FAIL 항목을 먼저 고치세요.")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
