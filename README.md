# 나이대별로 사는 곳과 들어오는 곳 — 수도권과 토론토

스마트시티융합기술세미나(월) **과제3: 도시 현상을 지표로 측정하고 공간적으로 해석하기**

- 발행 주소: (Cloudflare 배포 후 여기에 적기)
- 한 줄 요약: 서울은 **22세**에 가장 많이 받아들이고(2024년 순유입 +6,868명) **34세**에 가장 많이 내보낸다(−3,351명).
- 연구 질문
  1. 사는 곳 — 생애단계 다섯(20–24 · 25–34 · 35–44 · 45–64 · 65+)은 각각 수도권 어디에 모여 사는가? 토론토도 같은 순서인가?
  2. 들어오고 나가는 곳 — 서울로는 어떤 나이대가 어디서 들어오고, 떠나는 사람은 어디로 가는가?
  3. 둘의 관계 — 사는 곳과 이사 오는 곳은 같은가? 들어온 곳에 남는가?

## 지표 세 개

| 지표 | 구분 | 식 | 단위 |
|---|---|---|---|
| ① 거주 LQ | 수업 (LQ) | $LQ^{res}_{s,i}=\dfrac{P_{s,i}/P_i}{P_s/P}$ | 수도권 1km 격자 2000~2024 · 토론토 CT 2021 |
| ② 유입 LQ | 직접 설계 | $LQ^{in}_{s,j}=\dfrac{I_{s,j}/I_j}{I_s/I}$ | 수도권 시군구 · 서울 행정동 |
| ③ 순유입 강도 | 수업 (네트워크 가중 연결강도) | $NM_{s,j}=\dfrac{\text{in-strength}-\text{out-strength}}{P_{s,j}}\times1000$ | 수도권 시군구 |

핵심 시설(대학 · 업무중심지 · 학원가 · 신도시)을 지도에 겹쳐 각 나이대가 들어오는 곳과 비교했다.

## 폴더

```
site/                    발행하는 웹페이지 (Cloudflare 가 이 폴더만 올림)
  index.html, assets/app.js, assets/style.css
  assets/vendor/         Leaflet·Plotly·KaTeX (CDN 없이도 지도가 깨지지 않게 함께 둠)
  data/*.json            분석 결과 (집계값만)
analysis/
  lifestage.py           ① 거주 LQ — 격자·토론토 CT, 시설 인구 보정(core.py)
  od.py                  ②③ MDIS 인구이동 → 생애단계별 OD
  build_site.py          모든 지표 계산 → site/data/*.json
  facilities.csv         핵심 시설 대표 좌표
  core.py, kgeo.py, paths.py
tools/check_site.py      배포 전 점검
docs/                    01 아이디어·지표 설계, 02 배포 가이드
배포전_확인.bat           점검 → 미리보기 (git 은 실행하지 않음)
```

## 다시 만들기

```bash
pip install -r requirements.txt
python analysis/build_site.py      # 원자료 위치는 analysis/paths.py 참고
python tools/check_site.py
```
원자료(SGIS 인구격자, MDIS 마이크로데이터, 토론토 센서스)는 저장소에 넣지 않는다.

## 자료 출처

- 통계청 SGIS 인구격자 1km (2000·2005·2010·2015·2020·2024)
- 국가데이터처(통계청) MDIS 「국내인구이동통계」 마이크로데이터 2023~2025 — 분석 결과는 작성자의 것이며 국가데이터처의 공식 입장이 아님
- KOSIS 「시군구/성/연령(5세)별 이동자수」 (검산)
- 행정동 경계 vuski/admdongkor (2025-01-01)
- Statistics Canada, Census of Population 2021 (UNI·CEN Standardized Census Data)
- 배경지도 Esri World Light Gray Canvas / © OpenStreetMap contributors
