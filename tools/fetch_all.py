# -*- coding: utf-8 -*-
"""공개 데이터 내려받기 — 10주제의 원본을 raw/ 에 저장한다.

**전부 키도 로그인도 필요 없습니다.** 수업 중에 20명이 동시에 받아도 막히지
않는 곳만 골랐습니다.

한 번 받으면 raw/ 에 남으므로 다시 돌려도 새로 받지 않습니다.
(--force 를 주면 다시 받습니다)

실행 (저장소 최상위에서):
    python tools/fetch_all.py
    python tools/fetch_all.py --force
"""
from __future__ import annotations

import http.client
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# 윈도우 콘솔(cp949)은 한글 · 기호를 못 찍고 멈출 때가 있다. 출력만 UTF-8 로 맞춘다
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
# HTTP 헤더는 latin-1 만 담는다. 한글을 넣으면 UnicodeEncodeError 가 난다
UA = {"User-Agent": "gam-test-class/1.0 (data analysis class)"}
TIMEOUT = 90

SEOUL = (37.5665, 126.9780)

# 시 · 도청 소재지 (이름, 위도, 경도). 전국 눈 원본이 이 순서로 온다
SIDO = [
    ("서울", 37.5665, 126.9780), ("부산", 35.1798, 129.0750), ("대구", 35.8714, 128.6014),
    ("인천", 37.4563, 126.7052), ("광주", 35.1601, 126.8514), ("대전", 36.3504, 127.3845),
    ("울산", 35.5384, 129.3114), ("세종", 36.4800, 127.2890), ("경기(수원)", 37.2893, 127.0535),
    ("강원(춘천)", 37.8853, 127.7298), ("충북(청주)", 36.6357, 127.4917),
    ("충남(홍성)", 36.6588, 126.6728), ("전북(전주)", 35.8203, 127.1088),
    ("전남(무안)", 34.8161, 126.4629), ("경북(안동)", 36.5760, 128.5056),
    ("경남(창원)", 35.2383, 128.6924), ("제주", 33.4890, 126.4983),
]
# 눈이 많은 산지 · 섬 · 강원 영동 (이름, 위도, 경도). 전국 눈 더하기 원본이 이 순서로 온다
SNOW_EXTRA = [
    ("대관령", 37.6771, 128.7183), ("울릉도", 37.4844, 130.9057),
    ("강릉", 37.7519, 128.8761), ("속초", 38.2070, 128.5918),
]

# 날씨는 **모델을 ERA5로 못 박는다** (&models=era5).
# 모델을 적지 않으면 Open-Meteo가 그때그때 '가장 알맞은 모델'(best_match)을 골라 섞어 준다.
# 그 구성이 바뀌면 같은 주소로 받아도 지난 값이 달라진다 — 2026-10에 실제로 2024년 서울
# 열대야가 15일에서 12일로 바뀌었다. 출처에 모델까지 적어야 다시 받아도 같은 값이 나온다.
ERA5 = "&models=era5"

SOURCES: list[tuple[str, str, str]] = [
    # (저장 파일명, 설명, URL)
    ("seoul_weather.json",
     "서울 일별 기온·강수 1950~2024 (Open-Meteo Archive · ERA5 고정)",
     "https://archive-api.open-meteo.com/v1/archive"
     f"?latitude={SEOUL[0]}&longitude={SEOUL[1]}"
     "&start_date=1950-01-01&end_date=2024-12-31"
     "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
     "&timezone=Asia%2FSeoul" + ERA5),

    ("seoul_air.json",
     "서울 시간별 미세먼지 2023~2024 (Open-Meteo Air Quality · CAMS)",
     "https://air-quality-api.open-meteo.com/v1/air-quality"
     f"?latitude={SEOUL[0]}&longitude={SEOUL[1]}"
     "&start_date=2023-01-01&end_date=2024-12-31"
     "&hourly=pm10,pm2_5&timezone=Asia%2FSeoul"),

    ("working_hours.csv",
     "연간 노동시간 (Our World in Data)",
     "https://ourworldindata.org/grapher/annual-working-hours-per-worker.csv"
     "?csvType=full&useColumnShortNames=true"),

    ("life_expectancy.csv",
     "기대수명 (Our World in Data)",
     "https://ourworldindata.org/grapher/life-expectancy.csv"
     "?csvType=full&useColumnShortNames=true"),

    ("wb_fertility.json",
     "합계출산율 전세계 (World Bank SP.DYN.TFRT.IN)",
     "https://api.worldbank.org/v2/country/all/indicator/SP.DYN.TFRT.IN"
     "?format=json&per_page=20000&date=1960:2023"),

    ("wb_pop_kor.json",
     "한국 인구·고령화 (World Bank)",
     "https://api.worldbank.org/v2/country/KOR/indicator/"
     "SP.POP.TOTL;SP.POP.65UP.TO.ZS;SP.URB.TOTL.IN.ZS"
     "?format=json&per_page=2000&source=2"),

    ("wb_internet.json",
     "인터넷 사용률 전세계 (World Bank IT.NET.USER.ZS)",
     "https://api.worldbank.org/v2/country/all/indicator/IT.NET.USER.ZS"
     "?format=json&per_page=20000&date=1990:2023"),

    ("usdkrw.json",
     "원달러 환율 1999~ (Frankfurter · ECB)",
     "https://api.frankfurter.dev/v1/1999-01-04..2024-12-31"
     "?base=USD&symbols=KRW"),

    ("wb_countries.json",
     "World Bank 국가 목록 — 대륙·소득군 같은 집계치를 걸러내는 데 씁니다",
     "https://api.worldbank.org/v2/country?format=json&per_page=400"),

    *[(f"city_{cid}.json", f"{cn} 일별 기온·강수 1991~2020 (Open-Meteo Archive · ERA5 고정)",
       "https://archive-api.open-meteo.com/v1/archive"
       f"?latitude={lat}&longitude={lon}"
       "&start_date=1991-01-01&end_date=2020-12-31"
       "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
       f"&timezone=auto" + ERA5)
      for cid, cn, lat, lon in (
          ("seoul", "서울", 37.5665, 126.9780),
          ("tokyo", "도쿄", 35.6895, 139.6917),
          ("london", "런던", 51.5072, -0.1276),
          ("singapore", "싱가포르", 1.3521, 103.8198),
      )],

    ("quakes.geojson",
     "규모 5.5 이상 지진 2000~2025 (USGS) — 2만건 상한에 걸리지 않는 기준",
     # endtime 은 그날 0시에서 끊긴다. 2025년 12월 31일까지 넣으려면 다음 해 1월 1일로 적는다
     "https://earthquake.usgs.gov/fdsnws/event/1/query"
     "?format=geojson&starttime=2000-01-01&endtime=2026-01-01"
     "&minmagnitude=5.5&orderby=time&limit=20000"),

    ("quakes_korea.geojson",
     "한반도 주변 지진 2000~2025 (USGS · 규모 3.0 이상)",
     "https://earthquake.usgs.gov/fdsnws/event/1/query"
     "?format=geojson&starttime=2000-01-01&endtime=2026-01-01"
     "&minmagnitude=3.0&minlatitude=33&maxlatitude=39.5"
     "&minlongitude=124&maxlongitude=132&limit=20000"),

    ("seoul_snow.json",
     "서울 일별 강설량·최저기온 1990~2024 (Open-Meteo Archive · ERA5 고정)",
     "https://archive-api.open-meteo.com/v1/archive"
     f"?latitude={SEOUL[0]}&longitude={SEOUL[1]}"
     "&start_date=1990-01-01&end_date=2024-12-31"
     "&daily=snowfall_sum,temperature_2m_min"
     "&timezone=Asia%2FSeoul" + ERA5),

    # KOSIS 는 인증키가 필요해 OECD 지역 통계를 쓴다. 지역 이름은 영어로 온다
    # 서울 KR011 · 인천 KR012 · 부산 KR021 · 울산 KR022 · 대구 KR031 · 광주 KR041 · 대전 KR051 · 세종 KR054
    ("oecd_metro_pop.csv",
     "특별·광역시 인구(성별·연령별)·출생아 수 2016~2025 (OECD Regional Demography)",
     "https://sdmx.oecd.org/public/rest/data/OECD.CFE.EDS,DSD_REG_DEMO@DF_DEMO,"
     "/A..KR011+KR012+KR021+KR022+KR031+KR041+KR051+KR054..POP+LIVE_BIRTHS..."
     "?startPeriod=2016&endPeriod=2025&format=csvfilewithlabels"),

    # 위와 같은 OECD 표를 1990년부터, 전국(KOR)까지 넣어 받는다
    # 나이는 전체·65세 이상·15세 미만·15~64세만, 단위는 사람 수(PS)·출생아 수(BR)만 고른다
    # 65세 미만은 따로 없어서 15세 미만 + 15~64세로 만든다
    ("oecd_metro_pop_1990.csv",
     "전국·특별·광역시 인구(성별·65세 이상)·출생아 수 1990~2025 (OECD Regional Demography)",
     "https://sdmx.oecd.org/public/rest/data/OECD.CFE.EDS,DSD_REG_DEMO@DF_DEMO,"
     "/A..KOR+KR011+KR012+KR021+KR022+KR031+KR041+KR051+KR054"
     "..POP+LIVE_BIRTHS._T+Y_GE65+Y_LT15+Y15T64+Y0..PS+BR"
     "?startPeriod=1990&endPeriod=2025&format=csvfilewithlabels"),

    # 기상청 태풍 자료는 인증키가 필요해 NOAA IBTrACS 를 쓴다 (약 115MB · 기간을 골라 받을 수 없음)
    # 같은 태풍을 기관마다 잰 값이 열로 나뉜다. 기상청(KMA_) 열은 2015년부터만 있고,
    # 최근 태풍은 잠정값(TRACK_TYPE=PROVISIONAL)이 섞인다
    # 설명서: .../v04r01/doc/IBTrACS_v04r01_column_documentation.pdf
    ("ibtracs_wp.csv",
     "북서태평양 태풍 최적경로 1884~현재 (NOAA IBTrACS v04r01)",
     "https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs"
     "/v04r01/access/csv/ibtracs.WP.list.v04r01.csv"),

    # 대한민국 전체 평균 기온 (세계은행 CCKP · ERA5 0.25도 격자를 나라 범위로 평균)
    # 화면: https://climateknowledgeportal.worldbank.org/country/korea-republic/climate-data-historical
    # 기간은 1950~2023 묶음으로만 받을 수 있다 (주소의 기간을 2000-2023 으로 바꾸면 빈 값이 온다).
    # 2000~2023 은 계산할 때 고른다. 항목은 쉼표로 이어 한 파일에 받는다:
    #   tas 평균 · tasmax 최고 · tasmin 최저기온 · txx 한 해(달) 가장 더운 날 기온
    #   hd30 · hd35 30도 · 35도 넘은 날 수 · tr 열대야(최저 20도 이상, 우리나라 기준 25도와 다름) 일수
    *[(f"cckp_kor_temp_{per}.json",
       f"대한민국 평균 기온·더운 날 지표 {label} 1950~2023 (World Bank CCKP · ERA5)",
       "https://cckpapi.worldbank.org/cckp/v1/era5-x0.25_timeseries_"
       "tas,tasmax,tasmin,txx,hd30,hd35,tr"
       f"_timeseries_{per}_1950-2023_mean_historical_era5_x0.25_mean/KOR?_format=json")
      for per, label in (("annual", "연"), ("monthly", "월"))],

    # 유네스코 세계유산 목록 전체 (data.unesco.org · whc001). 북한 등 다른 나라 유산도 들어 있어
    # 계산할 때 나라 칸(states_names)으로 대한민국만 고른다. 여러 언어 설명이 들어 있어 약 24MB
    ("unesco_whc.json",
     "유네스코 세계유산 전체 목록 — 이름·등재 연도·유형·나라 (UNESCO WHC)",
     "https://data.unesco.org/api/explore/v2.1/catalog/datasets/whc001/exports/json"),

    # 휴대폰 가입(100명당 · 전체 수) · 초고속인터넷(100명당) · 인터넷 사용률 (World Bank WDI)
    ("wb_mobile_kor.json",
     "대한민국 휴대폰·초고속인터넷·인터넷 사용 1960~ (World Bank)",
     "https://api.worldbank.org/v2/country/KOR/indicator/"
     "IT.CEL.SETS.P2;IT.CEL.SETS;IT.NET.BBND.P2;IT.NET.USER.ZS"
     "?format=json&per_page=1000&source=2"),

    # 15세 이상 1인당 순수 알코올 소비량(L) 전체·남·여 (World Bank WDI · WHO 자료)
    ("wb_alcohol_kor.json",
     "대한민국 1인당 알코올 소비량 2000~ (World Bank · WHO)",
     "https://api.worldbank.org/v2/country/KOR/indicator/"
     "SH.ALC.PCAP.LI;SH.ALC.PCAP.MA.LI;SH.ALC.PCAP.FE.LI"
     "?format=json&per_page=1000&source=2"),
    ("wb_smoking_kor.json",
     "대한민국 15세 이상 흡연율 2000~ (World Bank · WHO)",
     "https://api.worldbank.org/v2/country/KOR/indicator/"
     "SH.PRV.SMOK;SH.PRV.SMOK.MA;SH.PRV.SMOK.FE"
     "?format=json&per_page=1000&source=2"),

    # 음반(CD) 수출: 유엔 무역통계 UN Comtrade (대한민국 값은 관세청 통계). HS 852349 = 녹음된 광디스크
    # (CD·DVD 등. K-pop 앨범이 대부분이지만 음악 아닌 것도 섞인다). 이 품목 번호는 2012년에 생겨 2012년부터.
    # 키 없는 미리보기는 한 번에 한 해만 준다 — 해마다 한 파일. 자주 부르면 429 가 나서 get() 이 기다렸다 다시 부른다
    # 한 파일 = 그해 전 세계 합계(partnerCode 0) 1줄 + 상대국별 줄. 금액은 미국 달러
    *[(f"comtrade_cd_{y}.json", f"대한민국 음반(CD) 수출 상대국별 {y} (UN Comtrade · HS 852349)",
       "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
       f"?reporterCode=410&period={y}&cmdCode=852349&flowCode=X")
      for y in range(2012, 2026)],

    # 맥주 수입: UN Comtrade (대한민국 값은 관세청 통계). HS 2203 = 맥아로 만든 맥주. 음반과 같이 해마다 한 파일
    # 한 파일 = 그해 전 세계 합계(partnerCode 0) 1줄 + 상대국별 줄. 금액은 미국 달러, 무게(netWgt)는 kg
    *[(f"comtrade_beer_{y}.json", f"대한민국 맥주 수입 상대국별 {y} (UN Comtrade · HS 2203)",
       "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
       f"?reporterCode=410&period={y}&cmdCode=2203&flowCode=M")
      for y in range(2000, 2026)],

    # 담배 수입: UN Comtrade (대한민국 값은 관세청 통계). HS 2402 = 시가·궐련 등 만든 담배. 맥주와 같은 모양
    *[(f"comtrade_cig_{y}.json", f"대한민국 담배(궐련 등) 수입 상대국별 {y} (UN Comtrade · HS 2402)",
       "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
       f"?reporterCode=410&period={y}&cmdCode=2402&flowCode=M")
      for y in range(2000, 2026)],

    # 전기: Our World in Data 에너지 자료. 값은 Energy Institute 세계 에너지 통계 · Ember 에서 온다
    # 세계 전체 나라 · 해마다 1줄. 대한민국은 country 가 "South Korea" 인 줄
    # 전국 눈: 서울 눈과 같은 Open-Meteo · ERA5. 시 · 도청 소재지 17곳 좌표를 한 번에 부른다.
    # 응답은 좌표 순서대로 17개짜리 목록이고, 각 값은 그 좌표가 든 약 25km 격자의 추정값이다
    ("korea_snow.json",
     "시·도청 소재지 17곳 일별 강설량 1990~2024 (Open-Meteo Archive · ERA5 고정)",
     "https://archive-api.open-meteo.com/v1/archive"
     "?latitude=" + ",".join(str(p[1]) for p in SIDO)
     + "&longitude=" + ",".join(str(p[2]) for p in SIDO)
     + "&start_date=1990-01-01&end_date=2024-12-31"
     "&daily=snowfall_sum&timezone=Asia%2FSeoul" + ERA5),
    # 위 17곳에 없는 산지 · 섬 · 강원 영동 4곳. Open-Meteo 는 지점 높이를 반영해 눈과 비를 나누므로
    # 같은 격자라도 대관령(높은 곳)과 강릉(낮은 곳)의 값이 다르다
    ("korea_snow_extra.json",
     "대관령·울릉도·강릉·속초 일별 강설량 1990~2024 (Open-Meteo Archive · ERA5 고정)",
     "https://archive-api.open-meteo.com/v1/archive"
     "?latitude=" + ",".join(str(p[1]) for p in SNOW_EXTRA)
     + "&longitude=" + ",".join(str(p[2]) for p in SNOW_EXTRA)
     + "&start_date=1990-01-01&end_date=2024-12-31"
     "&daily=snowfall_sum&timezone=Asia%2FSeoul" + ERA5),

    ("owid_energy.csv",
     "나라별 에너지 · 전기 1900~ (Our World in Data · Energy Institute · Ember)",
     "https://raw.githubusercontent.com/owid/energy-data/master/owid-energy-data.csv"),
]


def get(url: str, dest: Path, tries: int = 4) -> int:
    """받는다. 잠깐의 실패면 기다렸다가 다시 시도한다.

    공개 API 는 대부분 호출 제한이 있고(429), 큰 파일은 받다가 끊기기도 한다
    (IncompleteRead · 시간 초과). 한 번 실패했다고 포기하지 말고, 간격을 늘려 가며
    다시 부른다. 주소가 틀린 것(404 같은)은 다시 불러도 소용없으니 바로 알린다.
    """
    wait = 5
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                data = r.read()
            dest.write_bytes(data)
            return len(data)
        except urllib.error.HTTPError as e:
            if (e.code != 429 and e.code < 500) or i == tries - 1:
                raise
            why = str(e.code)
        except (http.client.IncompleteRead, urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if i == tries - 1:
                raise
            why = type(e).__name__
        print(f"          {why} — {wait}초 뒤 다시 시도합니다 ({i+1}/{tries-1})")
        time.sleep(wait)
        wait *= 2
    raise RuntimeError("도달 불가")


def main() -> int:
    force = "--force" in sys.argv
    RAW.mkdir(parents=True, exist_ok=True)
    fail = 0
    for name, desc, url in SOURCES:
        dest = RAW / name
        if dest.exists() and not force:
            print(f"  건너뜀  {name:<22} 이미 있음 ({dest.stat().st_size/1024:,.0f}KB)")
            continue
        t0 = time.time()
        try:
            n = get(url, dest)
            print(f"  받음    {name:<22} {n/1024:>7,.0f}KB  {time.time()-t0:.1f}s  {desc}")
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.IncompleteRead) as e:
            print(f"  실패    {name:<22} {e}")
            fail += 1
        time.sleep(0.4)          # 상대 서버에 예의를 지킨다

    print()
    print(f"총 {len(SOURCES)}건 / 실패 {fail}건 · 저장 위치 {RAW}")
    if fail:
        print("실패한 것은 잠시 뒤 다시 실행하면 대개 받아집니다.")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
