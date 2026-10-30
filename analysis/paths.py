"""폴더 위치 한곳에서 관리.

기본 배치 (Windows):
  01. 스마트시티융합기술세미나(월)/
    code-main/lecture06_Living_Population/data/HangJeongDong_ver20250101.geojson   ← 행정동 경계
    00. 6주차 과제/00. 수정/
      인구관련연간자료_*_데이터.zip     ← MDIS 국내인구이동 (올리지 않음)
      work/                            ← 중간 산출물 캐시 (올리지 않음)
      github_upload/                   ← GitHub 저장소 (이 파일이 있는 곳의 상위)
  Desktop/Dortor_Course/A. research/    ← SGIS 인구격자·토론토 센서스 (core.RESEARCH)
경로가 다르면 환경변수 MDIS_ZIP, ADM_GEOJSON, RESEARCH_DIR 로 바꾼다.
"""
from __future__ import annotations

import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent                      # github_upload
WORK = REPO.parent                      # 00. 수정
COURSE = WORK.parent.parent             # 01. 스마트시티융합기술세미나(월)
CACHE = WORK / "work"
SITE_DATA = REPO / "site" / "data"


def mdis_zip() -> Path:
    if os.environ.get("MDIS_ZIP"):
        return Path(os.environ["MDIS_ZIP"])
    hits = sorted(WORK.glob("인구관련연간자료_*_데이터.zip"))
    if not hits:
        raise FileNotFoundError(f"MDIS zip 이 {WORK} 에 없습니다 (환경변수 MDIS_ZIP 으로 지정 가능)")
    return hits[-1]


def adm_geojson() -> Path:
    p = Path(os.environ.get("ADM_GEOJSON", COURSE / "code-main" / "lecture06_Living_Population" / "data"
                            / "HangJeongDong_ver20250101.geojson"))
    if not p.exists():
        raise FileNotFoundError(f"행정동 경계 파일이 없습니다: {p}")
    return p


def ensure_dirs():
    CACHE.mkdir(parents=True, exist_ok=True)
    SITE_DATA.mkdir(parents=True, exist_ok=True)
