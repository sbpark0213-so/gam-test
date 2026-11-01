# -*- coding: utf-8 -*-
"""공개 데이터 → 10주제 × 5문항.

**모든 숫자는 raw/ 의 원본에서 계산합니다.** 지어낸 값이 하나도 없어야 합니다.
결과는 앱이 읽는 topics/*.json 과, 사람이 읽는 tools/정답지.md 로 나갑니다.

정답지와 이 스크립트는 .vercelignore 에 들어 있어 **배포되지 않습니다.**
공개 URL 에 정답지가 올라가면 게임이 성립하지 않습니다.

실행 (저장소 최상위에서):
    python tools/build_topics.py
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
import datetime as dt
from collections import Counter
from pathlib import Path
from statistics import mean

# 윈도우 콘솔(cp949)은 이모지 · 기호를 못 찍고 멈춘다. 출력만 UTF-8 로 맞춘다
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

HERE = Path(__file__).resolve().parent          # tools/
APP = HERE.parent                                # 저장소 최상위 = 배포되는 곳
RAW = APP / "data" / "raw"
OUT = APP / "topics"

TOPICS: list[dict] = []


def load_json(name):
    return json.load(io.open(RAW / name, encoding="utf-8"))


def load_csv(name):
    return list(csv.DictReader(io.open(RAW / name, encoding="utf-8")))


def wb_countries(rows, year):
    """그 해의 실제 국가 값만 남긴다 (집계치 제외)."""
    return {r["country"]["value"]: r["value"] for r in rows
            if int(r["date"]) == year and r["countryiso3code"] in REAL}


def owid_countries(rows, year, col):
    """OWID 도 마찬가지. code 가 비었거나 OWID_ 로 시작하면 집계치다."""
    return {r["entity"]: float(r[col]) for r in rows
            if int(r["year"]) == year and r["code"]
            and not r["code"].startswith("OWID")}


def topic(tid, emoji, title, blurb, source, source_url, questions, caveat="", fx="", art=()):
    """caveat = 이 데이터를 믿을 때의 한계. 앱 화면에도 그대로 나간다.
    fx = 첫 화면 카드 이모지 효과 (예: "shake" 흔들림). 없으면 비워 둔다.
    art = 첫 화면 카드에서 이모지 대신 겹쳐 보일 그림 파일들 (images/ 아래). 없으면 이모지.

    출처가 다르면 같은 '서울 기온'도 값이 다르다. 그 사실을 감추지 않는다.
    """
    TOPICS.append({"id": tid, "emoji": emoji, "title": title, "blurb": blurb,
                   "source": source, "source_url": source_url,
                   "caveat": caveat, "questions": questions, "fx": fx,
                   "art": list(art)})


def slider(qid, text, answer, unit, lo, hi, step, basis, why):
    return {"id": qid, "type": "slider", "text": text, "unit": unit,
            "min": lo, "max": hi, "step": step,
            "answer": round(float(answer), 1), "basis": basis, "why": why}


def choice(qid, text, options, answer, basis, why):
    assert answer in options, f"{qid}: 정답이 선택지에 없습니다"
    return {"id": qid, "type": "choice", "text": text, "options": options,
            "answer": answer, "basis": basis, "why": why}


# ── 12. 광역시 인구 ──────────────────────────────────────────────
# OECD 표에는 같은 전국(KOR) 값이 '도시권·농촌' 같은 지역 유형별로도 들어 있다.
# 유형을 나누지 않은 줄(_Z)만 쓴다. 성별은 남녀 합(_T)만 쓴다
def metro_pop():
    P = [r for r in load_csv("oecd_metro_pop_1990.csv")
         if r["TERRITORIAL_TYPE"] == "_Z" and r["SEX"] == "_T"]

    def val(area, measure, age, year):
        v = [float(r["OBS_VALUE"]) for r in P
             if r["REF_AREA"] == area and r["MEASURE"] == measure
             and r["AGE"] == age and r["TIME_PERIOD"] == str(year)]
        assert len(v) == 1, f"{area} {measure} {age} {year}: 값이 {len(v)}개입니다"
        return v[0]

    # 원본의 전국 총인구 줄은 해에 따라 시·도 값과 기준이 다르다 (2011년 단절 표시).
    # 2020년은 전국 줄과 17개 시·도 합이 같은 해라서, 전국으로 나누는 문항은 2020년으로 센다
    seoul20, kor20 = val("KR011", "POP", "_T", 2020), val("KOR", "POP", "_T", 2020)
    seoul_share = seoul20 / kor20 * 100
    seoul24, busan24 = val("KR011", "POP", "_T", 2024), val("KR021", "POP", "_T", 2024)
    births24, seoul_b24 = val("KOR", "LIVE_BIRTHS", "Y0", 2024), val("KR011", "LIVE_BIRTHS", "Y0", 2024)
    seoul_b_share = seoul_b24 / births24 * 100
    old20 = val("KOR", "POP", "Y_GE65", 2020)
    old_share = old20 / kor20 * 100
    sejong15, sejong24 = val("KR054", "POP", "_T", 2015), val("KR054", "POP", "_T", 2024)

    topic(
        "metro-pop", "👨‍👩‍👧‍👦", "우리는 어디에 모여 살까",
        "1990~2024년 대한민국 인구 변화",
        "OECD Regional Demography", "https://data-explorer.oecd.org/",
        [
            slider("m1", "2020년 전국 인구 중 서울에 사는 사람은 몇 %일까요?",
                   seoul_share, "%", 0, 50, 0.5,
                   f"2020년 총인구 서울 {seoul20:,.0f}명 ÷ 전국 {kor20:,.0f}명 "
                   f"× 100 = {seoul_share:.1f}%",
                   "수도권 집중이라는 말이 익숙해서 서울 한 곳의 비중을 크게 "
                   "잡기 쉽습니다."),
            slider("m2", "2024년 서울 인구는 부산 인구의 몇 배일까요?",
                   seoul24 / busan24, "배", 1, 5, 0.1,
                   f"2024년 총인구 서울 {seoul24:,.0f}명 ÷ 부산 {busan24:,.0f}명 "
                   f"= {seoul24 / busan24:.2f}배",
                   "제2의 도시라는 이름 때문에 두 도시의 차이를 작게 잡게 됩니다."),
            slider("m3", "2024년 태어난 아이 중 서울에서 태어난 아이는 몇 %일까요?",
                   seoul_b_share, "%", 0, 40, 0.5,
                   f"2024년 출생아 수 서울 {seoul_b24:,.0f}명 ÷ 전국 {births24:,.0f}명 "
                   f"× 100 = {seoul_b_share:.1f}%",
                   "서울에 사람이 많이 사니 아이도 그만큼 많이 태어날 거라고 "
                   "생각하기 쉽습니다."),
            slider("m4", "2020년 전국 인구 중 65세 이상은 몇 %일까요?",
                   old_share, "%", 0, 40, 0.5,
                   f"2020년 65세 이상 {old20:,.0f}명 ÷ 전국 총인구 {kor20:,.0f}명 "
                   f"× 100 = {old_share:.1f}%",
                   "고령화는 '다가올 일'로 느껴지지만, 이미 다섯 명 중 한 명에 "
                   "가까워졌습니다."),
            slider("m5", "2024년 세종시 인구는 2015년의 몇 배일까요?",
                   sejong24 / sejong15, "배", 1, 8, 0.1,
                   f"세종 총인구 2015년 {sejong15:,.0f}명 → 2024년 {sejong24:,.0f}명, "
                   f"2024년 ÷ 2015년 = {sejong24 / sejong15:.2f}배",
                   "새로 생긴 도시는 작은 데서 시작해서, 늘어난 폭이 "
                   "다른 도시와 크기가 다릅니다."),
        ],
        caveat="주민등록 집계가 아닌 OECD의 7월 1일 기준 추계이고, 전국 비율은 시 · 도 합과 맞는 "
               "2020년으로 셌기 때문에 행정안전부 · 통계청 발표와 다릅니다.",
        # 마이크로소프트 Fluent 3D 이모지(MIT)에는 가족 한 장이 없어 네 사람을 겹쳐 보인다
        art=[f"images/fluent/{n}_3d_light.png" for n in ("man", "woman", "girl", "boy")])


# ── 9. 지진 ──────────────────────────────────────────────────────
# 한반도 원본은 위도·경도 사각형이라 일본·북한 지진도 들어 있다.
# USGS 가 위치 이름 끝을 'South Korea' 로 적은 것만 대한민국 지진으로 센다.
# 날짜는 한국 시간으로 센다
def quakes():
    QK = [f["properties"] for f in load_json("quakes_korea.geojson")["features"]]
    K9 = dt.timezone(dt.timedelta(hours=9))

    def kst(p):
        return dt.datetime.fromtimestamp(p["time"] / 1000, K9)

    # 기간은 받은 한반도 원본 전체의 해에서 센다 (대한민국 지진이 없는 해도 햇수에 든다)
    y0, y1 = min(kst(p).year for p in QK), max(kst(p).year for p in QK)
    span = f"{y0}~{y1}년"
    SK = [p for p in QK
          if (p["place"] or "").split(",")[-1].strip() == "South Korea"
          and p["type"] == "earthquake"]
    head = f"{span} USGS 규모 3.0 이상 기록 중 위치가 South Korea로 적힌 {len(SK)}건"
    top = max(SK, key=lambda p: p["mag"])

    # 지역: 위치 이름은 '거리 km 방향 of 지명' 꼴이다. 지명에서 50km 안의 지진만 세고
    # (먼바다 지진 제외), 흥해는 포항시의 읍이라 포항으로 합친다. 지명이 없는 줄은 뺀다
    NEAR_KM = 50
    town_ko = {"Gyeongju": "경주", "Heunghae": "포항", "Pohang": "포항", "Tonghae": "동해",
               "Sinan": "신안", "Puan": "부안", "Mungyeong": "문경", "Ulsan": "울산",
               "Iksan": "익산", "Gaigeturi": "제주", "Sokcho": "속초",
               "Pyeongchang": "평창", "Kyosai": "거제"}
    near = []
    for p in SK:
        m = re.match(r"(?:(\d+) ?km \w+ of )?(.+), South Korea$", p["place"])
        if m and int(m.group(1) or 0) <= NEAR_KM:
            near.append(town_ko[m.group(2)])
    by_town = Counter(near).most_common()
    assert by_town[0][1] > by_town[1][1], f"지역 1위가 동률입니다: {by_town[:3]}"

    by_year = Counter(kst(p).year for p in SK).most_common()
    assert by_year[0][1] > by_year[1][1], f"연도 1위가 동률입니다: {by_year[:3]}"
    m5 = [p for p in SK if p["mag"] >= 5.0]

    topic(
        "quakes", "🌏", "대한민국도 지진 안전지대일까",
        f"{span} 대한민국 지진 기록",
        "USGS 지진 카탈로그", "https://earthquake.usgs.gov/",
        [
            slider("k1", "2025년까지 발생한 지진의 최고 규모는 몇일까요?",
                   top["mag"], "", 3.0, 9.0, 0.1,
                   f"{head}에서 가장 큰 값은 {kst(top):%Y년 %m월 %d일} "
                   f"{top['place']} 규모 {top['mag']}입니다",
                   "큰 지진은 뉴스로 기억하는데, 기관마다 규모를 다르게 재서 "
                   "기억하는 숫자와 기록이 다를 수 있습니다."),
            choice("k2", "대한민국에서 지진이 가장 많이 발생한 지역은 어디일까요?",
                   ["경주", "포항", "울산", "부산"], by_town[0][0],
                   f"{head} 중 지명에서 {NEAR_KM}km 안인 {len(near)}건을 흥해는 포항에 "
                   "합쳐 도시별로 세면 "
                   + " · ".join(f"{t} {n}건" for t, n in by_town[:3]) + "입니다",
                   "가장 큰 지진이 난 곳과 지진이 가장 자주 난 곳은 같지 않을 수 "
                   "있습니다."),
            choice("k3", "지진이 가장 많이 발생한 해는 몇 년일까요?",
                   ["2011년", "2016년", "2017년", "2023년"], f"{by_year[0][0]}년",
                   f"{head}을 한국 시간 기준 해마다 세면 "
                   + " · ".join(f"{y}년 {n}건" for y, n in by_year[:3]) + "입니다",
                   "가까운 나라의 큰 지진이 난 해와 우리나라에서 지진이 잦았던 해는 "
                   "다릅니다."),
            # 여진도 한 건씩 센다
            slider("k4", "규모 3.0 이상 지진은 총 몇 건 발생했을까요?",
                   len(SK), "건", 0, 200, 1,
                   f"{span} USGS 규모 3.0 이상 기록에서 위치가 South Korea로 적힌 것을 "
                   f"여진까지 한 건씩 세면 {len(SK)}건입니다",
                   "USGS는 작은 지진을 다 잡지 못해서, 기상청 집계를 떠올리면 훨씬 "
                   "많게 잡게 됩니다."),
            slider("k5", "규모 5.0 이상 지진은 몇 번 일어났을까요?",
                   len(m5), "번", 0, 20, 1,
                   f"{head} 중 규모 5.0 이상은 "
                   + " · ".join(f"{kst(p):%Y년} {p['mag']}" for p in
                                sorted(m5, key=lambda p: p["time"]))
                   + f", 모두 {len(m5)}번입니다",
                   "큰 지진은 뉴스로 여러 번 보기 때문에 실제보다 자주 난 것처럼 "
                   "기억됩니다."),
        ],
        caveat=f"기상청이 아닌 USGS 기록과 규모라 기상청보다 횟수가 적고 경주 · 포항 규모 순서도 "
               f"다르며, 여진은 따로 세고 지역은 가장 가까운 지명 {NEAR_KM}km 안만 셌습니다.",
        fx="shake")


# ── 13. 태풍 ─────────────────────────────────────────────────────
# IBTrACS 북서태평양 최적경로. 태풍마다 3시간(옛 기록은 6시간) 간격 위치 점이 한 줄씩 있다.
# 기상청(KMA_) 열은 2015년부터만 있어서 일본기상청(TOKYO_) 값을 쓴다.
# 원본에는 '어느 나라에 상륙했나' 열이 없다. 그래서 상륙은 이렇게 센다:
#   남한 사각형(위도 33~38.6 · 경도 124.5~130) 안에서 육지까지 거리(DIST2LAND)가 0km 인 점이
#   하나라도 있으면 상륙. 위도 35도 아래·경도 129도 동쪽은 대마도·이키·규슈라 뺀다. 제주는 넣는다.
#   그 첫 육지 점에서 일본기상청 등급이 태풍 세기(3 열대폭풍 · 4 강한 열대폭풍 · 5 태풍 ·
#   9 열대폭풍 이상, 옛 기록)일 때만 '상륙한 태풍'으로 친다
TY_FROM, TY_TO = 1951, 2025      # 일본기상청 기록이 시작한 해 ~ 다 끝난 마지막 해
KT_TO_MS = 0.514444              # 노트 → 초속(m/s)


def typhoon():
    keep = ("SID", "SEASON", "NAME", "ISO_TIME", "LAT", "LON", "DIST2LAND", "TRACK_TYPE",
            "TOKYO_GRADE", "TOKYO_WIND", "TOKYO_PRES", "KMA_LAT")
    tracks: dict[str, list] = {}
    kma_years = set()
    # 110MB 라 한 줄씩 읽고 쓸 열만 남긴다. 둘째 줄은 단위 줄이라 건너뛴다
    for r in csv.DictReader(io.open(RAW / "ibtracs_wp.csv", encoding="utf-8")):
        if not r["SEASON"].isdigit():
            continue
        if r["KMA_LAT"].strip():
            kma_years.add(int(r["SEASON"]))
        if TY_FROM <= int(r["SEASON"]) <= TY_TO:
            tracks.setdefault(r["SID"], []).append({k: r[k].strip() for k in keep})

    K9 = dt.timezone(dt.timedelta(hours=9))

    def kst(x):
        return dt.datetime.fromisoformat(x["ISO_TIME"]).replace(tzinfo=dt.UTC).astimezone(K9)

    def in_box(x):
        la, lo = float(x["LAT"]), float(x["LON"])
        return 33 <= la <= 38.6 and 124.5 <= lo <= 130 and not (la < 35 and lo > 129.0)

    LAND = []
    for v in tracks.values():
        i = next((i for i, x in enumerate(v) if in_box(x) and x["DIST2LAND"] == "0"), None)
        if i is None or v[i]["TOKYO_GRADE"] not in ("3", "4", "5", "9"):
            continue
        box = [x for x in v if in_box(x)]
        # 상륙 무렵 = 육지 위 첫 점과 그 바로 앞 점. 풍속이 있는 점 중 (풍속 큰, 기압 낮은) 점
        near = [x for x in v[max(i - 1, 0):i + 1] if x["TOKYO_WIND"] and x["TOKYO_PRES"]]
        best = max(near, key=lambda x: (float(x["TOKYO_WIND"]), -float(x["TOKYO_PRES"])),
                   default=None)
        LAND.append({"year": int(v[0]["SEASON"]), "name": v[0]["NAME"], "at": kst(v[i]),
                     "best": best, "hours": (kst(box[-1]) - kst(box[0])).total_seconds() / 3600,
                     "provisional": any(x["TRACK_TYPE"] != "main" for x in v)})
    span = f"{TY_FROM}~{TY_TO}년"
    head = f"{span} 일본기상청 기록으로 우리 땅(제주 포함)에 상륙할 때도 태풍이었던 {len(LAND)}개"

    # 1. 상륙 무렵 가장 셌던 태풍: 풍속이 같으면 같은 점의 중심기압이 낮은 쪽
    def power(t):
        return (float(t["best"]["TOKYO_WIND"]), -float(t["best"]["TOKYO_PRES"]))
    rated = sorted((t for t in LAND if t["best"]), key=power, reverse=True)
    assert power(rated[0]) != power(rated[1]), f"1번 동률: {rated[0]['name']} {rated[1]['name']}"
    top = rated[0]
    tied = [t for t in rated[1:] if power(t)[0] == power(top)[0]]
    wind_from = min(t["year"] for t in rated)
    name_ko = {"MAEMI": "매미", "RUSA": "루사", "MAYSAK": "마이삭", "HINNAMNOR": "힌남노",
               "HAISHEN": "하이선", "SANBA": "산바", "THELMA": "셀마"}
    assert top["name"] in name_ko, f"1번 정답 {top['name']} 의 한글 이름을 name_ko 에 넣으세요"

    # 2. 매미(2003) 상륙 무렵 풍속
    maemi = next(t for t in LAND if t["name"] == "MAEMI" and t["year"] == 2003)
    maemi_kt = float(maemi["best"]["TOKYO_WIND"])

    # 3. 상륙이 가장 많은 달 (첫 육지 점의 한국 시간)
    by_month = Counter(t["at"].month for t in LAND).most_common()
    assert by_month[0][1] > by_month[1][1], f"3번 동률: {by_month[:3]}"

    # 4. 우리나라 근처(사각형 안)에 머문 시간: 사각형 안 첫 점 ~ 마지막 점
    stay = mean(t["hours"] for t in LAND)

    # 5. 10년을 다 채운 연대 중 보기의 네 연대만 건수로 비교
    DECADES = (1980, 1990, 2000, 2010)
    by_dec = {d: sum(1 for t in LAND if d <= t["year"] <= d + 9) for d in DECADES}
    dec_rank = sorted(by_dec.items(), key=lambda kv: -kv[1])
    assert dec_rank[0][1] > dec_rank[1][1], f"5번 동률: {dec_rank}"

    n_prov = sum(t["provisional"] for t in LAND)
    # 부제목에 이름을 쓴 두 태풍이 정말 상륙 태풍 목록에 있는지 확인한다
    for y, n in ((2002, "RUSA"), (2022, "HINNAMNOR")):
        assert any(t["year"] == y and t["name"] == n for t in LAND), f"부제목의 {n} 이 상륙 목록에 없습니다"
    topic(
        "typhoon", "🌀", "태풍 상륙 연대기",
        "루사부터 힌남노까지, 상륙 태풍의 기록",
        "NOAA IBTrACS (일본기상청 최적경로)",
        "https://www.ncei.noaa.gov/products/international-best-track-archive",
        [
            choice("t1", "어떤 태풍이 가장 거세게 우리 땅을 덮쳤을까요?",
                   ["루사", "매미", "마이삭", "힌남노"], name_ko[top["name"]],
                   f"{head} 중 일본기상청 풍속이 있는 {wind_from}년 이후 {len(rated)}개를 "
                   "상륙 직전·직후 최대풍속으로 줄 세우고, 같으면 그때 중심기압이 낮은 쪽을 "
                   f"위로 두면 {top['year']}년 {name_ko[top['name']]}"
                   f"({float(top['best']['TOKYO_WIND']):.0f}노트 · {top['best']['TOKYO_PRES']}hPa)"
                   + (" · 풍속이 같은 " + " · ".join(
                       f"{t['year']}년 {name_ko.get(t['name'], t['name'])}"
                       f"({t['best']['TOKYO_PRES']}hPa)" for t in tied) if tied else "")
                   + "입니다",
                   "피해가 컸던 태풍과 상륙할 때 가장 셌던 태풍은 같지 않을 수 있습니다."),
            slider("t2", "2003년 매미의 바람 세기는 초속 몇 m였을까요?",
                   maemi_kt * KT_TO_MS, "m/s", 10, 70, 1,
                   f"일본기상청 기록에서 매미의 상륙 직전·직후 최대풍속(10분 평균)은 "
                   f"{maemi_kt:.0f}노트로, 1노트 = {KT_TO_MS}m/s 로 바꾸면 초속 "
                   f"{maemi_kt * KT_TO_MS:.1f}m입니다",
                   "순간 최대풍속 뉴스를 기억하면 크게 잡게 됩니다. 이 값은 10분 동안의 "
                   "평균입니다."),
            choice("t3", "태풍이 가장 많이 상륙한 달은 언제일까요?",
                   ["7월", "8월", "9월", "10월"], f"{by_month[0][0]}월",
                   f"{head}를 상륙한 달(한국 시간)로 세면 "
                   + " · ".join(f"{m}월 {n}개" for m, n in by_month[:3]) + "입니다",
                   "가을 태풍이 크게 기억에 남아서 9월을 고르기 쉽습니다."),
            slider("t4", "태풍은 우리나라 근처에 평균 몇 시간 머무를까요?",
                   stay, "시간", 0, 72, 1,
                   f"{head}가 남한 둘레 사각형(위도 33~38.6 · 경도 124.5~130, 바다 포함) 안에 "
                   f"찍힌 첫 점부터 마지막 점까지 걸린 시간을 평균하면 {stay:.1f}시간입니다",
                   "며칠씩 이어진 비바람 뉴스 때문에 오래 머문다고 느끼기 쉽습니다."),
            choice("t5", "태풍이 가장 많이 상륙한 연대는 언제일까요?",
                   [f"{d}년대" for d in DECADES], f"{dec_rank[0][0]}년대",
                   f"{head}를 연대별로 세면 "
                   + " · ".join(f"{d}년대 {n}개" for d, n in by_dec.items()) + "입니다",
                   "'요즘 태풍이 잦다'는 느낌이 기록과 맞는지는 세어 봐야 압니다."),
        ],
        caveat=f"기상청 값은 {min(kma_years)}년부터만 있어 일본기상청 풍속({wind_from}년부터, 10분 평균 · "
               "5노트 단위)을 썼고, 위치 점이 남한 땅 위에 찍힌 태풍만 상륙으로 세어 해안을 스친 태풍은 "
               "빠지므로 기상청 발표와 다를 수 있습니다"
               + (f" (그중 {n_prov}개는 잠정 경로)" if n_prov else "") + ".")


# ── 14. 대한민국 기온 ────────────────────────────────────────────
# 세계은행 CCKP: ERA5 0.25도 격자를 대한민국 범위로 평균한 값. 연 파일은 해마다 '연-07' 한 칸이다.
# 원본은 1950~2023 이고, 이 주제는 2000~2023 만 쓴다
HEAT_FROM, HEAT_TO = 2000, 2023


def korea_heat():
    A = {v: x["KOR"] for v, x in load_json("cckp_kor_temp_annual.json")["data"].items()}

    def a(v, y):
        return A[v][f"{y}-07"]

    Y = range(HEAT_FROM, HEAT_TO + 1)
    span = f"{HEAT_FROM}~{HEAT_TO}년"
    head = "세계은행 CCKP의 대한민국 평균(ERA5)"
    txx0, txx1 = a("txx", HEAT_FROM), a("txx", HEAT_TO)
    # 5번: 2000년대(2000~2009)와 최근 10년(끝 해까지 10년)의 하루 최저기온 1년 평균
    OLD, NEW = range(HEAT_FROM, HEAT_FROM + 10), range(HEAT_TO - 9, HEAT_TO + 1)
    tn0, tn1 = mean(a("tasmin", y) for y in OLD), mean(a("tasmin", y) for y in NEW)
    hd30 = mean(a("hd30", y) for y in Y)

    def top_year(v):
        r = sorted(Y, key=lambda y: -a(v, y))
        assert a(v, r[0]) != a(v, r[1]), f"{v} 1위 동률: {r[:2]}"
        return r

    hot, hot35 = top_year("tas"), top_year("hd35")
    hot_txx = top_year("txx")[0]     # 한계 문장의 예: 가장 더운 날 기온이 가장 높았던 해
    YEARS = ["2013년", "2016년", "2018년", "2023년"]

    topic(
        "korea-heat", "🥵", "대한민국은 얼마나 뜨거워졌나",
        f"{span} 대한민국 평균 기온",
        "World Bank Climate Change Knowledge Portal (ERA5)",
        "https://climateknowledgeportal.worldbank.org/country/korea-republic/climate-data-historical",
        [
            slider("c1", f"{HEAT_FROM}년 대비 {HEAT_TO}년 최고온도는 몇 ℃나 상승했을까요?",
                   txx1 - txx0, "℃", -3, 5, 0.1,
                   f"{head}에서 한 해 가장 더운 날의 최고기온은 {HEAT_FROM}년 {txx0:.2f}℃ → "
                   f"{HEAT_TO}년 {txx1:.2f}℃로 {txx1 - txx0:+.2f}℃입니다",
                   "두 해만 비교하면 그해 날씨에 따라 크게 흔들립니다. 오름폭은 기억보다 "
                   "작거나 클 수 있습니다."),
            choice("c2", f"{span} 중 가장 더웠던 해는 언제일까요?",
                   YEARS, f"{hot[0]}년",
                   f"{head}의 연평균 기온으로 줄 세우면 "
                   + " · ".join(f"{y}년 {a('tas', y):.2f}℃" for y in hot[:3]) + "입니다",
                   "폭염이 심했던 해와 1년 전체가 가장 더웠던 해는 다를 수 있습니다."),
            slider("c3", "30℃ 넘는 날은 1년에 며칠일까요?",
                   hd30, "일", 0, 90, 1,
                   f"{head}에서 하루 최고기온 30℃를 넘은 날 수를 {span} 평균하면 "
                   f"{hd30:.1f}일입니다",
                   "더운 도시의 여름만 떠올리면 많게 잡습니다. 산간·해안까지 합친 전국 "
                   "평균은 다릅니다."),
            choice("c4", "35℃ 넘는 날이 가장 많았던 해는 언제일까요?",
                   YEARS, f"{hot35[0]}년",
                   f"{head}에서 하루 최고기온 35℃를 넘은 날 수를 {span} 해마다 세면 "
                   + " · ".join(f"{y}년 {a('hd35', y):.1f}일" for y in hot35[:3]) + "입니다",
                   "1년 평균이 가장 더운 해와 가장 뜨거운 날이 많았던 해는 다릅니다."),
            slider("c5", "2000년대보다 최근 10년, 밤 기온은 몇 ℃ 올랐을까요?",
                   tn1 - tn0, "℃", -2, 4, 0.1,
                   f"{head}에서 하루 최저기온의 1년 평균을 다시 평균하면 "
                   f"{OLD[0]}~{OLD[-1]}년 {tn0:.2f}℃ → {NEW[0]}~{NEW[-1]}년 {tn1:.2f}℃로 "
                   f"{tn1 - tn0:+.2f}℃입니다",
                   "낮 더위만 기억하기 쉽지만, 밤 기온도 함께 오릅니다."),
        ],
        caveat="관측이 아닌 ERA5 추정값의 전국 격자 평균(2023년까지)이라 가장 더운 날도 평균으로 나와"
               f"(예: {hot_txx}년 {a('txx', hot_txx):.1f}℃) 관측소 · 기상청 기록보다 낮고 적습니다.")


# ── 세계유산 ─────────────────────────────────────────────────────
# 유네스코 세계유산 목록 전체(whc001)에서 나라 칸이 대한민국 하나뿐인 줄만 쓴다.
# 이름에 Korea 가 든 북한 유산은 나라 칸이 달라 빠진다. 한 줄 = 등재된 유산 1건
# (조선왕릉처럼 여러 장소를 묶은 유산도 1건으로 센다). 원본에는 2026년 등재도 있어 2025년까지만 쓴다
WHC_TO = 2025


def heritage():
    K = [r for r in load_json("unesco_whc.json")
         if r["states_names"] == ["Republic of Korea"] and int(r["date_inscribed"]) <= WHC_TO]
    yr = lambda r: int(r["date_inscribed"])
    first = min(yr(r) for r in K)
    natural = [r for r in K if r["category"] == "Natural"]
    per_year = Counter(yr(r) for r in K)
    top = per_year.most_common()
    assert top[0][1] != top[1][1], f"가장 많이 등재된 해 동률: {top[:2]}"
    tombs = [r for r in K if r["name_en"].startswith("Royal Tombs of the Joseon")]
    assert len(tombs) == 1, "조선왕릉 줄이 하나가 아닙니다"
    tombs = tombs[0]
    span = f"{first}~{WHC_TO}년"
    head = f"유네스코 세계유산 목록에서 나라가 대한민국인 유산({span} 등재)"

    topic(
        "heritage", "🏯", "우리 세계유산 몇 개 알아요?",
        f"{span} 유네스코 세계유산 등재 기록",
        "UNESCO World Heritage List (whc001)",
        "https://data.unesco.org/explore/dataset/whc001/",
        [
            slider("h1", f"{WHC_TO}년까지 등재된 우리나라 세계유산은 몇 개일까요?",
                   len(K), "개", 0, 40, 1,
                   f"{head}을 등재된 유산 1건을 1개로 세면 {len(K)}개입니다"
                   f"(문화유산 {len(K) - len(natural)}개 · 자연유산 {len(natural)}개)",
                   "김치·판소리 같은 무형유산이나 훈민정음 같은 기록유산까지 합쳐 떠올리면 "
                   "많게 잡습니다."),
            choice("h2", "우리나라 세계유산이 처음 등재된 해는?",
                   ["1988년", "1995년", "2000년", "2007년"], f"{first}년",
                   f"{head} 중 가장 이른 등재 연도는 {first}년이고, 그해 "
                   f"{per_year[first]}건이 함께 등재됐습니다",
                   "올림픽을 치른 1988년 무렵이나 2000년대 이후로 짐작하기 쉽습니다."),
            choice("h3", "우리나라 세계유산 중 자연유산은 몇 개일까요?",
                   ["1개", "2개", "3개", "5개"], f"{len(natural)}개",
                   f"{head} 중 유형이 자연유산(Natural)인 것은 "
                   + " · ".join(f"{r['name_en']}({yr(r)})" for r in sorted(natural, key=yr))
                   + f"으로 {len(natural)}개입니다",
                   "산과 바다가 많아 자연유산도 여럿일 것 같지만, 대부분은 문화유산입니다."),
            choice("h4", "한 해에 세계유산이 가장 많이 등재된 해는?",
                   ["1995년", "1997년", "2000년", "2010년"], f"{top[0][0]}년",
                   f"{head}을 등재 연도별로 세면 "
                   + " · ".join(f"{y}년 {n}건" for y, n in top[:3]) + "입니다",
                   "최근일수록 많이 등재됐을 것 같지만, 한 해에 한 건 넘게 오른 해는 드뭅니다."),
            choice("h5", "조선왕릉이 세계유산에 등재된 해는?",
                   ["2000년", "2005년", "2009년", "2014년"], f"{yr(tombs)}년",
                   f"{head} 중 {tombs['name_en']}의 등재 연도는 {yr(tombs)}년입니다"
                   f"(왕릉 {tombs['components_count']}곳을 묶어 1건)",
                   "오래된 유적이라 일찍 등재됐을 것 같지만, 등재 시기는 유적의 나이와 상관없습니다."),
        ],
        caveat=f"세계유산만 센 것이라 무형 · 기록유산(예: 직지심체요절)은 빠지고, 여러 장소를 묶은 "
               f"유산(예: 조선왕릉 18곳)도 1건으로 셌으며 {WHC_TO + 1}년 등재 · 확장은 넣지 않았습니다.")


# ── 술 ───────────────────────────────────────────────────────────
# 소비량은 세계은행에 실린 WHO 추정값(15세 이상 1인당 순수 알코올 L). 원본은 2000~2020 인데
# 2000년 값이 2001년과 소수점까지 같아 채워 넣은 값일 수 있어 2001년부터 쓴다.
# 수입 맥주는 UN Comtrade 해마다 한 파일. 파일마다 세계 합계 줄(partnerCode 0)과 나라별 줄이 함께 있어
# 세계 합계 줄 하나만 쓴다 (다 더하면 두 배가 된다)
ALC_FROM, ALC_TO = 2001, 2020
BEER_YEARS = range(2000, 2026)
# 4번 보기 나라. 원본에는 나라 이름이 없고 번호(partnerCode)만 있다
BEER_FROM = {392: "일본", 156: "중국", 528: "네덜란드", 842: "미국"}
SOJU_ABV, SOJU_L = 0.165, 0.36          # 1번 소주 1병: 16.5% · 360mL (사용자가 정한 기준)


def alcohol():
    W = {int(r["date"]): r["value"] for r in load_json("wb_alcohol_kor.json")[1]
         if r["indicator"]["id"] == "SH.ALC.PCAP.LI" and r["value"] is not None}
    a0, a1 = W[ALC_FROM], W[ALC_TO]
    drop = (a0 - a1) / a0 * 100
    bottle = SOJU_L * SOJU_ABV                      # 소주 1병의 순수 알코올(L)
    bottles = a1 / bottle / 12                      # 1번은 한 달 기준: 1년 값을 12로 나눈다
    # 5번: 기간 안에서 1인당 소비량이 가장 낮은 해
    low = sorted(range(ALC_FROM, ALC_TO + 1), key=lambda y: W[y])
    assert W[low[0]] != W[low[1]], f"가장 낮은 해 동률: {low[:2]}"

    beer = {}
    for y in BEER_YEARS:
        w = [r for r in load_json(f"comtrade_beer_{y}.json")["data"] if r["partnerCode"] == 0]
        assert len(w) == 1, f"{y}: 세계 합계 줄이 하나가 아닙니다"
        beer[y] = w[0]
    by_usd = sorted(beer, key=lambda y: -beer[y]["primaryValue"])
    by_kg = sorted(beer, key=lambda y: -beer[y]["netWgt"])
    assert by_usd[0] == by_kg[0], f"맥주 1위가 금액({by_usd[0]})과 무게({by_kg[0]})로 다릅니다"
    top = by_usd[0]
    # 4번: 가장 최근 해의 나라별 줄(세계 합계 줄은 뺀다)을 금액으로 줄 세운다
    last = BEER_YEARS[-1]
    P = sorted((r for r in load_json(f"comtrade_beer_{last}.json")["data"] if r["partnerCode"] != 0),
               key=lambda r: -r["primaryValue"])
    assert P[0]["primaryValue"] != P[1]["primaryValue"], f"{last}년 맥주 1위 나라 동률"
    assert all(r["partnerCode"] in BEER_FROM for r in P[:3]), "1~3위 나라 이름이 BEER_FROM 에 없습니다"
    # 한계: 이웃한 두 해 값이 소수점까지 같으면 해마다 따로 잰 값이 아니라는 표시다
    same = [(y, y + 1) for y in sorted(W) if y + 1 in W and W[y] == W[y + 1]]
    span = f"{ALC_FROM}~{ALC_TO}년"
    head = "WHO가 추정한 15세 이상 1인당 순수 알코올 소비량(세계은행)"

    topic(
        "alcohol", "🍶", "한국인의 술잔",
        f"{span} 1인당 술 소비 · {BEER_YEARS[0]}~{BEER_YEARS[-1]}년 맥주 수입",
        "World Health Organization (World Bank) · UN Comtrade",
        "https://data.worldbank.org/indicator/SH.ALC.PCAP.LI?locations=KR",
        [
            slider("a1", f"{ALC_TO}년 한국인 1명이 한 달에 마신 술을 소주"
                   f"({SOJU_ABV * 100:.1f}% · {SOJU_L * 1000:.0f}mL)로 치환하면 몇 병일까요?",
                   bottles, "병", 0, 40, 1,
                   f"{head} {ALC_TO}년 {a1:.2f}L를 12달로 나누고, 소주 1병({SOJU_L * 1000:.0f}mL · "
                   f"{SOJU_ABV * 100:.1f}%)에 든 순수 알코올 {bottle * 1000:.1f}mL로 나누면 "
                   f"한 달 {bottles:.1f}병입니다",
                   "주변 술꾼을 떠올리면 많게, 술을 안 마시는 사람을 떠올리면 적게 잡습니다. "
                   "15세 이상 모두를 평균한 값입니다."),
            slider("a2", f"{ALC_FROM}년보다 {ALC_TO}년에 몇 % 줄었을까요?",
                   drop, "%", 0, 60, 1,
                   f"{head}은 {ALC_FROM}년 {a0:.2f}L → {ALC_TO}년 {a1:.2f}L로 "
                   f"{drop:.1f}% 줄었습니다",
                   "회식 문화가 줄었다는 이야기로 크게 줄었다고 짐작하거나, 술자리 기억으로 "
                   "그대로라고 짐작하기 쉽습니다."),
            choice("a3", "수입 맥주가 가장 많았던 해는?",
                   ["2008년", "2014년", "2018년", "2024년"], f"{top}년",
                   f"UN Comtrade의 대한민국 맥주(HS 2203) 수입 세계 합계를 {BEER_YEARS[0]}~"
                   f"{BEER_YEARS[-1]}년 금액으로 줄 세우면 "
                   + " · ".join(f"{y}년 {beer[y]['primaryValue'] / 1e6:,.0f}백만 달러"
                                for y in by_usd[:3])
                   + "이고, 무게로 세도 1위는 같습니다",
                   "수입 맥주가 흔해진 요즘이 가장 많을 것 같지만, 정점은 그보다 앞섭니다."),
            choice("a4", f"{last}년 맥주를 가장 많이 들여온 나라는?",
                   list(BEER_FROM.values()), BEER_FROM[P[0]["partnerCode"]],
                   f"UN Comtrade의 대한민국 맥주(HS 2203) {last}년 수입을 나라별 금액으로 줄 세우면 "
                   + " · ".join(f"{BEER_FROM[r['partnerCode']]} {r['primaryValue'] / 1e6:,.1f}백만 달러"
                                for r in P[:3]) + "입니다",
                   "2019년 불매운동 기억으로 일본 맥주는 아직 적을 것이라 짐작하기 쉽습니다."),
            choice("a5", f"{span} 중 1인당 음주량이 가장 적었던 해는?",
                   ["2010년", "2015년", "2019년", "2020년"], f"{low[0]}년",
                   f"{head}을 {span} 적은 순으로 줄 세우면 "
                   + " · ".join(f"{y}년 {W[y]:.2f}L" for y in low[:3]) + "입니다",
                   "술을 덜 마시는 요즘 분위기는 알아도, 어느 해가 가장 적었는지는 헷갈리기 쉽습니다."),
        ],
        caveat=f"술 소비량은 WHO 추정값({ALC_TO}년까지, "
               + ", ".join(f"{a}·{b}년" for a, b in same) + " 값이 똑같음)이고, 소주 병 수는 모든 술의 "
               f"알코올을 {SOJU_ABV * 100:.1f}% · {SOJU_L * 1000:.0f}mL 소주로 바꾼 값이며, 맥주 수입은 "
               f"세관 신고 금액이라 {last}년 값은 바뀔 수 있습니다.")


# ── 전기 ─────────────────────────────────────────────────────────
# OWID 에너지 자료(나라별 · 해마다 1줄). 지역 합계 줄(World · Asia …)이 섞여 있어 South Korea 줄만 쓴다.
# 전기 값은 1985년부터. 2025년은 Ember 만 다룬 잠정값일 수 있어 Energy Institute 도 다룬 2024년까지만 쓴다.
# other_renewables 는 biofuel 과 같은 값이라 둘을 더하지 않는다 (재생 합계는 renewables 열을 쓴다)
ELEC_FROM, ELEC_TO = 1985, 2024
# 3번 보기 → 원본 열 이름
ELEC_SRC = {"원자력": "nuclear", "석탄": "coal", "가스": "gas", "재생에너지": "renewables"}


def electricity():
    K = {int(r["year"]): r for r in load_csv("owid_energy.csv") if r["country"] == "South Korea"}
    e = lambda y, c: float(K[y][c])
    pc0, pc1 = e(ELEC_FROM, "per_capita_electricity"), e(ELEC_TO, "per_capita_electricity")
    day = pc1 / 365
    share = {k: e(ELEC_TO, f"{c}_share_elec") for k, c in ELEC_SRC.items()}
    rank = sorted(share, key=lambda k: -share[k])
    assert share[rank[0]] != share[rank[1]], f"3번 1위 동률: {rank[:2]}"
    solar, wind = e(ELEC_TO, "solar_share_elec"), e(ELEC_TO, "wind_share_elec")
    assert solar != wind, "5번 태양광 · 풍력 동률"
    head = f"OWID 에너지 자료의 대한민국 {ELEC_TO}년"

    topic(
        "electricity", "⚡", "플러그 너머의 대한민국",
        f"{ELEC_FROM}~{ELEC_TO}년 대한민국 전기",
        "Our World in Data (Energy Institute · Ember)",
        "https://ourworldindata.org/energy/country/south-korea",
        [
            slider("e1", f"{ELEC_TO}년 한국인 1명당 하루 전기 사용량은 몇 kWh일까요?",
                   day, "kWh", 0, 60, 1,
                   f"{head} 1인당 전기 {pc1:,.0f}kWh(1년, 나라 전체 발전량 ÷ 인구)를 365일로 나누면 "
                   f"하루 {day:.1f}kWh입니다",
                   "집 전기요금 고지서를 떠올리면 적게 잡습니다. 공장 · 회사 · 가게 전기까지 "
                   "모두 나눈 값입니다."),
            slider("e2", f"{ELEC_FROM}년보다 {ELEC_TO}년 한국인 1명당 전기 사용량은 몇 배 늘었을까요?",
                   pc1 / pc0, "배", 1, 20, 0.5,
                   f"OWID 에너지 자료의 대한민국 1인당 전기는 {ELEC_FROM}년 {pc0:,.0f}kWh(Energy Institute) → "
                   f"{ELEC_TO}년 {pc1:,.0f}kWh(Ember)로 {pc1 / pc0:.1f}배입니다",
                   "그때도 집마다 전기를 썼으니 두세 배쯤으로 짐작하기 쉽습니다."),
            choice("e3", f"{ELEC_TO}년 우리나라 전기를 가장 많이 만든 것은?",
                   list(ELEC_SRC), rank[0],
                   f"{head} 발전 비중은 "
                   + " · ".join(f"{k} {share[k]:.1f}%" for k in rank)
                   + "입니다(재생에너지는 수력 · 태양광 · 풍력 · 바이오 합계)",
                   "원자력 비중을 크게 떠올리기 쉽지만, 세 에너지가 거의 비슷하게 나눠 만듭니다."),
            slider("e4", f"{ELEC_TO}년 태양광은 전기의 몇 %를 만들었을까요?",
                   solar, "%", 0, 30, 0.5,
                   f"{head} 발전 비중에서 태양광은 {solar:.1f}%입니다",
                   "지붕과 들판의 태양광 패널이 눈에 많이 띄어 크게 잡기 쉽습니다."),
            choice("e5", f"{ELEC_TO}년 태양광과 풍력 중 전기를 더 많이 만든 것은?",
                   ["태양광", "풍력"], "태양광" if solar > wind else "풍력",
                   f"{head} 발전 비중은 태양광 {solar:.1f}% · 풍력 {wind:.1f}%입니다",
                   "바닷가 풍력 발전기가 커 보여도, 만드는 전기의 양은 다릅니다."),
        ],
        caveat="1인당 값은 공장 · 회사까지 포함한 나라 전체 발전량을 추정 인구로 나눈 것이라 가정 전기보다 "
               f"훨씬 크고, {ELEC_FROM}년(Energy Institute)과 최근(Ember) 출처를 이어 붙였으며 "
               f"{ELEC_TO + 1}년 잠정값은 뺐습니다.")


# ── 우리 동네 눈 ─────────────────────────────────────────────────
# Open-Meteo · ERA5. 시 · 도청 소재지 17곳(korea_snow.json)과 산지 · 섬 · 강원 영동 4곳
# (korea_snow_extra.json). 응답은 fetch_all 의 SIDO · SNOW_EXTRA 좌표 순서대로 온다.
# 겨울 = 7월 ~ 다음 해 6월. '눈 온 날'은 문항마다 기준이 다르다 (사용자가 정한 기준):
#   1번은 하루 0.1cm 이상, 4번 첫눈은 기상청 첫눈처럼 쌓이지 않아도 되므로 0보다 크면
SNOW_FROM, SNOW_TO = 1990, 2024
SNOW_DAY_CM = 0.1
GANGWON = ["강원(춘천)", "대관령", "강릉", "속초"]      # 5번에서 강원도로 세는 지점


def korea_snow():
    from fetch_all import SIDO, SNOW_EXTRA
    S = {}
    for pts, f in ((SIDO, "korea_snow.json"), (SNOW_EXTRA, "korea_snow_extra.json")):
        D = load_json(f)
        assert len(D) == len(pts), f"{f}: 지점 수가 좌표 목록과 다릅니다"
        for (name, lat, lon), x in zip(pts, D):
            assert abs(x["latitude"] - lat) < 0.25 and abs(x["longitude"] - lon) < 0.25, \
                f"{name} 좌표 불일치"
            S[name] = [(dt.date.fromisoformat(t), v or 0) for t, v in
                       zip(x["daily"]["time"], x["daily"]["snowfall_sum"])]
    n_years = SNOW_TO - SNOW_FROM + 1
    span = f"{SNOW_FROM}~{SNOW_TO}년"
    head = f"Open-Meteo ERA5의 {len(S)}개 지점({span})"

    seoul_days = sum(1 for _, v in S["서울"] if v >= SNOW_DAY_CM) / n_years
    busan = Counter()
    for d, v in S["부산"]:
        busan[d.year] += v
    btop = busan.most_common()
    assert btop[0][1] != btop[1][1], f"2번 1위 해 동률: {btop[:2]}"
    yearly = {n: sum(v for _, v in S[n]) / n_years for n in S}
    most = sorted(yearly, key=lambda n: -yearly[n])
    assert yearly[most[0]] != yearly[most[1]], f"3번 1위 동률: {most[:2]}"

    # 4번: 지점마다 겨울(7월~다음 해 6월)마다 첫눈 날을 찾아, 그 달을 모두 센다
    months = Counter()
    for n in S:
        for w in range(SNOW_FROM, SNOW_TO):
            first = next((d for d, v in S[n]
                          if dt.date(w, 7, 1) <= d < dt.date(w + 1, 7, 1) and v > 0), None)
            if first:
                months[first.month] += 1
    mtop = months.most_common()
    assert mtop[0][1] != mtop[1][1], f"4번 1위 달 동률: {mtop[:2]}"

    gw = sorted(GANGWON, key=lambda n: -yearly[n])
    assert yearly[gw[0]] != yearly[gw[1]], f"5번 1위 동률: {gw[:2]}"
    # 한계 문장의 예: 2011년 2월 동해안 폭설 때 강릉 값, 그리고 춘천이 서울보다 적게 나오는지
    storm = sum(v for d, v in S["강릉"] if dt.date(2011, 2, 8) <= d <= dt.date(2011, 2, 15))
    assert yearly["강원(춘천)"] < yearly["서울"], "춘천이 서울보다 적지 않습니다 — 한계 문장을 고치세요"

    topic(
        "korea-snow", "❄️", "우리 동네 눈 지도",
        f"{span} 전국 17개 도시 강설 기록",
        "Open-Meteo Archive (ERA5 재분석)",
        "https://open-meteo.com/",
        [
            slider("s1", "서울에는 1년에 눈이 며칠 올까요?",
                   seoul_days, "일", 0, 60, 1,
                   f"{head} 중 서울에서 하루 강설량이 {SNOW_DAY_CM}cm 이상인 날을 세어 1년 평균하면 "
                   f"{seoul_days:.1f}일입니다",
                   "눈이 쌓였던 몇 번만 기억하면 적게 잡습니다. 조금 내린 눈도 하루로 셉니다."),
            choice("s2", "부산에 눈이 가장 많이 온 해는?",
                   ["2001년", "2005년", "2010년", "2023년"], f"{btop[0][0]}년",
                   f"{head} 중 부산의 1년 강설량을 해마다 더하면 "
                   + " · ".join(f"{y}년 {v:.2f}cm" for y, v in btop[:3]) + "입니다",
                   "부산 눈은 드물어서, 뉴스로 기억에 남은 해를 고르기 쉽습니다."),
            choice("s3", "1년 강설량이 가장 많은 지역은?",
                   ["대관령", "울릉도", "충남(홍성)", "제주"], most[0],
                   f"{head}에서 1년 강설량을 {span} 평균하면 "
                   + " · ".join(f"{n} {yearly[n]:.1f}cm" for n in most[:3]) + "입니다",
                   "산이 높은 강원도를 먼저 떠올리기 쉽지만, 바다 위 섬도 눈이 많습니다."),
            choice("s4", "첫눈은 대개 몇 월에 올까요?",
                   ["10월", "11월", "12월", "1월"], f"{mtop[0][0]}월",
                   f"{head}에서 지점마다 겨울(7월~다음 해 6월)의 첫눈 날(쌓이지 않아도 눈이 "
                   "조금이라도 내린 첫날)을 찾아 달별로 세면 "
                   + " · ".join(f"{m}월 {c}번" for m, c in mtop[:3]) + "입니다",
                   "첫눈 소식은 11월 뉴스로 많이 듣지만, 지역 전체로 보면 다른 달이 더 많습니다."),
            choice("s5", f"강원도 {len(GANGWON)}곳 중 1년 강설량이 가장 많은 곳은?",
                   GANGWON, gw[0],
                   f"{head} 중 강원도 {len(GANGWON)}곳의 1년 강설량을 {span} 평균하면 "
                   + " · ".join(f"{n} {yearly[n]:.1f}cm" for n in gw) + "입니다",
                   "폭설 뉴스는 바닷가 도시에서 자주 나오지만, 1년 내내 더하면 높은 곳이 많습니다."),
        ],
        caveat="21곳의 약 25km 격자 ERA5 추정값이고 쌓인 눈이 아닌 하루 새로 내린 눈이라, 좁은 곳의 "
               f"폭설이 작게 잡혀(예: 2011년 2월 8~15일 동해안 폭설 때 강릉 {storm:.1f}cm) 기상청 기록과 "
               "양 · 순위가 다릅니다.")


def write_only(t, replaces="", after=""):
    """--only 로 한 주제만 만들 때 쓴다. 다른 주제 파일과 topics.json 의 나머지는 그대로 둔다.
    replaces 를 주면 topics.json 에서 그 주제 카드 자리에 대신 들어간다 (그 주제 파일은 지우지 않는다).
    after 를 주면 새 카드를 맨 뒤가 아니라 그 주제 카드 바로 뒤에 넣는다."""
    assert len(t["questions"]) == 5, f"{t['id']}: 문항이 5개가 아닙니다"
    pack = {k: t[k] for k in ("id", "emoji", "title", "blurb",
                              "source", "source_url", "caveat")}
    pack["questions"] = t["questions"]
    io.open(OUT / f"{t['id']}.json", "w", encoding="utf-8").write(
        json.dumps(pack, ensure_ascii=False, indent=2))
    idx = json.load(io.open(APP / "topics.json", encoding="utf-8"))
    entry = {k: t[k] for k in ("id", "emoji", "title", "blurb", "source")}
    if t["fx"]:
        entry["fx"] = t["fx"]
    if t["art"]:
        entry["art"] = t["art"]
    # 이미 있으면 그 자리에서 바꾸고, 없으면 맨 뒤에 붙인다
    if replaces:
        idx["topics"] = [entry if x["id"] == replaces else x
                         for x in idx["topics"] if x["id"] != t["id"]]
    ids = [x["id"] for x in idx["topics"]]
    if t["id"] in ids:
        idx["topics"][ids.index(t["id"])] = entry
    elif after in ids:
        idx["topics"].insert(ids.index(after) + 1, entry)
    else:
        idx["topics"].append(entry)
    io.open(APP / "topics.json", "w", encoding="utf-8").write(
        json.dumps(idx, ensure_ascii=False, indent=2))
    print(f"{t['emoji']} {t['title']}  ({t['source']})")
    for q in t["questions"]:
        print(f"    [{q['type'][:6]:<6}] {q['text'][:44]:<44} → {q['answer']}{q.get('unit', '')}")


# python tools/build_topics.py --only metro-pop   (또는 quakes · typhoon · korea-heat · heritage · alcohol · electricity · korea-snow)
# 다른 주제는 계산하지 않는다. 그 주제들의 원본이 data/raw/ 에 없어도 돈다
if "--only" in sys.argv:
    ONLY = {"metro-pop": metro_pop, "quakes": quakes, "typhoon": typhoon,
            "korea-heat": korea_heat, "heritage": heritage, "alcohol": alcohol,
            "electricity": electricity, "korea-snow": korea_snow}
    # 새 주제가 첫 화면에서 대신 차지할 옛 주제 카드
    REPLACES = {"korea-heat": "seoul-heat", "korea-snow": "seoul-snow"}
    # 내가 만든 주제가 옛 주제보다 앞에 오도록, 새 카드를 넣을 자리 (이 카드 바로 뒤)
    AFTER = {"heritage": "typhoon", "alcohol": "heritage", "electricity": "alcohol"}
    tid = sys.argv[sys.argv.index("--only") + 1]
    assert tid in ONLY, f"--only 는 {', '.join(ONLY)} 만 됩니다"
    ONLY[tid]()
    write_only(TOPICS[-1], REPLACES.get(tid, ""), AFTER.get(tid, ""))
    sys.exit(0)


# World Bank·OWID 응답에는 '유럽연합' '고소득국' 같은 **집계치**가 섞여 있다.
# 그대로 순위를 매기면 나라와 대륙을 한 줄에 놓고 세는 셈이 된다.
REAL = {x["id"] for x in load_json("wb_countries.json")[1]
        if x["region"]["id"] != "NA"}


# ════════════════════════════════════════════════════════════════
# 기상 공통
# ════════════════════════════════════════════════════════════════
w = load_json("seoul_weather.json")["daily"]
W = [{"d": dt.date.fromisoformat(t), "hi": hi, "lo": lo, "rain": r}
     for t, hi, lo, r in zip(w["time"], w["temperature_2m_max"],
                             w["temperature_2m_min"], w["precipitation_sum"])]
W24 = [x for x in W if x["d"].year == 2024]


def years(a, b):
    return [x for x in W if a <= x["d"].year <= b]


# ── 1. 서울 기온 ─────────────────────────────────────────────────
# ERA5 는 1950~70년대 구간의 품질이 낮고(초기 확장), 격자 평균이라 도심
# 관측값보다 낮게 나온다. 그래서 '역대 최고기온'이나 '폭염일 추세'처럼
# 그 구간에 기대는 문항은 쓰지 않는다. 열대야·연평균처럼 신호가 뚜렷한 것만 쓴다.
tropical_24 = sum(1 for x in W24 if x["lo"] >= 25)
trop_50s = sum(1 for x in years(1950, 1959) if x["lo"] >= 25) / 10
trop_10s = sum(1 for x in years(2015, 2024) if x["lo"] >= 25) / 10
t_ratio = trop_10s / trop_50s if trop_50s else 0
mean_50s = mean((x["hi"] + x["lo"]) / 2 for x in years(1950, 1959))
mean_10s = mean((x["hi"] + x["lo"]) / 2 for x in years(2015, 2024))
warming = mean_10s - mean_50s
below0_24 = sum(1 for x in W24 if x["lo"] < 0)
hot_days = Counter((x["d"].month, x["d"].day)
                   for x in years(1995, 2024) if x["hi"] >= 33)
peak_day = hot_days.most_common(1)[0]
# 한계 문장의 숫자도 손으로 적지 않는다 — 원본에서 가장 더웠던 날을 찾는다
hottest = max(W, key=lambda x: x["hi"])

topic(
    "seoul-heat", "🌡️", "서울은 얼마나 더워졌나",
    "1950년부터 2024년까지, 서울의 매일 기온",
    "Open-Meteo Archive (ERA5 재분석)", "https://open-meteo.com/",
    [
        slider("h1", "2024년 서울에서 열대야(밤 최저기온 25도 이상)는 며칠이었을까요?",
               tropical_24, "일", 0, 60, 1,
               f"2024년 일최저기온 25도 이상인 날 {tropical_24}일",
               "유난히 더웠던 밤 몇 번이 기억을 지배합니다. 실제 일수는 세어 봐야 "
               "압니다."),
        # 보기는 배수에 가장 가까운 것이 정답이 되게 경계를 둔다 (2.8배 → «약 3배»)
        choice("h2", "1950년대와 2015~2024년, 열대야는 몇 배 차이일까요?",
               ["거의 같다", "약 2배", "약 3배", "약 5배"],
               ["거의 같다", "약 2배", "약 3배", "약 5배"][
                   0 if t_ratio < 1.5 else 1 if t_ratio < 2.5
                   else 2 if t_ratio < 4 else 3],
               f"연평균 열대야 1950년대 {trop_50s:.1f}일 → 2015~2024년 "
               f"{trop_10s:.1f}일 ({t_ratio:.1f}배)",
               "'옛날에도 더웠다'는 느낌과 기록은 다릅니다. 기억은 유난히 더웠던 "
               "몇 밤으로 남지만, 기록은 해마다 빠짐없이 셉니다."),
        slider("h3", "1950년대와 비교해 서울의 연평균 기온은 몇 도 올랐을까요?",
               warming, "도", 0, 4, 0.1,
               f"1950년대 {mean_50s:.2f}도 → 2015~2024년 {mean_10s:.2f}도 "
               f"(+{warming:.2f}도)",
               "1~2도는 작아 보이지만, 그 변화가 열대야 일수를 몇 배로 바꿉니다. "
               "평균의 변화와 극단의 변화는 크기가 다릅니다."),
        choice("h4", "최근 30년간 33도 이상인 날이 가장 잦았던 날짜는?",
               ["7월 초", "7월 말", "8월 초", "8월 말"],
               "7월 말" if peak_day[0][0] == 7 and peak_day[0][1] >= 20
               else "8월 초" if peak_day[0][0] == 8 and peak_day[0][1] <= 10
               else "7월 초" if peak_day[0][0] == 7 else "8월 말",
               f"1995~2024년 중 가장 잦았던 날짜는 {peak_day[0][0]}월 "
               f"{peak_day[0][1]}일 ({peak_day[1]}회)",
               "장마가 끝나는 시점과 가장 더운 시점은 다릅니다."),
        slider("h5", "2024년 서울에서 밤 기온이 영하로 내려간 날은 며칠이었을까요?",
               below0_24, "일", 30, 150, 5,
               f"2024년 일최저기온 0도 미만인 날 {below0_24}일",
               "겨울이 짧아졌다고 느끼지만, 영하로 내려가는 날은 여전히 석 달 "
               "치가 넘습니다."),
    ],
    caveat="ERA5는 넓은 격자의 재분석 값이라 도심 관측소와 다르게 나옵니다. "
           f"예컨대 여기서는 역대 최고기온이 {hottest['hi']:.1f}도"
           f"({hottest['d']:%Y년})지만 기상청 서울 관측 기록은 2018년 39.6도입니다. "
           "같은 '서울 기온'도 출처에 따라 다릅니다.")

# ── 4. 노동시간 ──────────────────────────────────────────────────
wh = [r for r in load_csv("working_hours.csv") if r["working_hours_omm"]]
latest_year = max(int(r["year"]) for r in wh if r["code"] == "KOR")
cur = owid_countries(wh, latest_year, "working_hours_omm")
kor = cur["South Korea"]
rank = sorted(cur.items(), key=lambda kv: -kv[1])
kor_rank = [k for k, _ in rank].index("South Korea") + 1
longer = kor_rank - 1
past = {int(r["year"]): float(r["working_hours_omm"])
        for r in wh if r["code"] == "KOR"}
y30 = latest_year - 30
drop = past[y30] - kor
trio = {c: cur[c] for c in ("South Korea", "Japan", "Germany") if c in cur}
shortest = min(trio, key=trio.get)
name_ko = {"South Korea": "한국", "Japan": "일본", "Germany": "독일"}

topic(
    "working-hours", "⏰", "우리는 얼마나 일하나",
    "나라별 1인당 연간 노동시간",
    "Our World in Data", "https://ourworldindata.org/grapher/annual-working-hours-per-worker",
    [
        slider("w1", f"{latest_year}년 한국의 1인당 연간 노동시간은?",
               kor, "시간", 1200, 2600, 50,
               f"{latest_year}년 한국 {kor:,.0f}시간 "
               f"(주 5일 기준 하루 약 {kor / 250:.1f}시간)",
               "연 단위로 물으면 감이 잘 안 옵니다. 하루로 나눠 보면 체감과 "
               "맞는지 확인할 수 있습니다."),
        slider("w2", f"한국보다 더 오래 일하는 나라는 {len(cur)}개국 중 몇 개일까요?",
               longer, "개국", 0, 60, 1,
               f"{latest_year}년 기준 {len(cur)}개국 중 한국은 {kor_rank}위",
               "'한국이 제일 많이 일한다'는 인상이 강하지만, 비교 대상에 따라 "
               "순위가 달라집니다."),
        slider("w3", f"한국의 노동시간은 30년 전({y30}년)보다 몇 시간 줄었을까요?",
               drop, "시간", 0, 900, 50,
               f"{y30}년 {past[y30]:,.0f}시간 → {latest_year}년 {kor:,.0f}시간",
               "줄어든 폭은 대개 과소평가됩니다. 하루로 치면 크게 달라진 값입니다."),
        choice("w4", "한국·일본·독일 중 가장 적게 일하는 나라는?",
               ["한국", "일본", "독일"], name_ko[shortest],
               " · ".join(f"{name_ko[c]} {trio[c]:,.0f}시간" for c in trio),
               "나라마다 통계 기준이 다릅니다. 순위보다 격차의 크기를 봅니다."),
        slider("w5", "한국과 독일의 연간 노동시간 차이는?",
               abs(cur["South Korea"] - cur["Germany"]), "시간", 0, 900, 50,
               f"한국 {cur['South Korea']:,.0f} · 독일 "
               f"{cur['Germany']:,.0f}시간",
               "두 나라 차이를 주 단위로 나눠 보면 체감이 확 달라집니다."),
    ],
    caveat="이 자료에는 개발도상국이 많이 포함돼 있어, OECD 안에서의 순위와 "
           "전체 순위가 다릅니다. '어느 집단과 비교하느냐'가 순위를 만듭니다.")

# ── 6. 인터넷 ────────────────────────────────────────────────────
net = [r for r in load_json("wb_internet.json")[1] if r["value"] is not None]
n_latest = max(int(r["date"]) for r in net if r["countryiso3code"] == "KOR")
n_cur = wb_countries(net, n_latest)
kor_n = n_cur["Korea, Rep."]
n_rank = sorted(n_cur.items(), key=lambda kv: -kv[1])
kor_n_rank = [k for k, _ in n_rank].index("Korea, Rep.") + 1
kor_2000 = next(r["value"] for r in net
                if r["countryiso3code"] == "KOR" and r["date"] == "2000")
world = next((r["value"] for r in net
              if r["countryiso3code"] == "WLD" and int(r["date"]) == n_latest), None)
if world is None:
    world = mean(n_cur.values())
offline = 100 - world

topic(
    "internet", "🌐", "인터넷과 연결",
    "나라별 인터넷 사용 인구 비율",
    "World Bank Open Data", "https://data.worldbank.org/",
    [
        slider("i1", f"{n_latest}년 한국에서 인터넷을 쓰는 사람의 비율은?",
               kor_n, "%", 60, 100, 1,
               f"{n_latest}년 한국 {kor_n:.1f}%",
               "'거의 다'라고 생각하지만 100%는 아닙니다. 남은 몇 %가 누구인지가 "
               "정책의 대상입니다."),
        slider("i2", f"한국보다 인터넷 사용률이 높은 나라는 {len(n_cur)}곳 중 몇 곳일까요?",
               kor_n_rank - 1, "곳", 0, 60, 1,
               f"{n_latest}년 {len(n_cur)}곳 중 한국 {kor_n_rank}위",
               "'IT 강국'이라는 말과 실제 보급률 순위는 다른 이야기입니다."),
        slider("i3", "2000년 한국의 인터넷 사용률은?",
               kor_2000, "%", 0, 100, 5,
               f"2000년 {kor_2000:.1f}% → {n_latest}년 {kor_n:.1f}%",
               "20여 년 전을 떠올릴 때는 지금의 기준으로 과대평가하기 쉽습니다."),
        slider("i4", f"{n_latest}년 전 세계 평균 인터넷 사용률은?",
               world, "%", 20, 100, 5,
               f"{n_latest}년 세계 {world:.1f}%",
               "내 주변이 전부 연결돼 있으면 세계도 그럴 거라고 생각하게 됩니다."),
        slider("i5", "전 세계에서 인터넷을 쓰지 않는 사람은 몇 %일까요?",
               offline, "%", 0, 70, 5,
               f"100 - {world:.1f} = {offline:.1f}%",
               "같은 사실을 뒤집어 물으면 전혀 다른 크기로 느껴집니다."),
    ])

# ── 7. 환율 ──────────────────────────────────────────────────────
fx = load_json("usdkrw.json")["rates"]
FX = sorted((d, v["KRW"]) for d, v in fx.items() if "KRW" in v)
hi_d, hi_v = max(FX, key=lambda x: x[1])
lo_d, lo_v = min(FX, key=lambda x: x[1])
avg_fx = mean(v for _, v in FX)
under1200 = sum(1 for _, v in FX if v < 1200) / len(FX) * 100
last_d, last_v = FX[-1]
era = ("1997~1999년 외환위기" if hi_d < "2005" else
       "2008~2009년 금융위기" if hi_d < "2012" else
       "2020년 코로나" if hi_d < "2022" else "2022년 이후")

topic(
    "usdkrw", "💵", "원달러 환율 26년",
    "1999년부터 오늘까지의 원달러 환율",
    "Frankfurter (유럽중앙은행 고시)", "https://frankfurter.dev/",
    [
        slider("x1", "1999년 이후 원달러 환율의 최고 기록은?",
               hi_v, "원", 1100, 1800, 25,
               f"{hi_d} {hi_v:,.2f}원",
               "최고치는 위기의 기억과 함께 남지만, 정확한 시점은 자주 헷갈립니다."),
        choice("x2", "그 최고치를 찍은 시기는?",
               ["1997~1999년 외환위기", "2008~2009년 금융위기",
                "2020년 코로나", "2022년 이후"], era,
               f"최고 {hi_v:,.2f}원 ({hi_d}). 이 데이터는 1999년부터라 "
               f"1997~98년 외환위기 구간은 포함되어 있지 않습니다",
               "데이터가 시작하는 시점을 확인하지 않으면 '역대 최고'를 잘못 "
               "말하게 됩니다."),
        slider("x3", "26년간의 평균 환율은?",
               avg_fx, "원", 900, 1500, 25,
               f"{FX[0][0]} ~ {FX[-1][0]} 거래일 {len(FX):,}일 평균 "
               f"{avg_fx:,.0f}원 (최저 {lo_v:,.0f}원 · {lo_d})",
               "최근 값이 기준점이 되어 과거 평균을 높게 잡게 됩니다."),
        slider("x4", "환율이 1,200원 아래였던 날은 전체의 몇 %일까요?",
               under1200, "%", 0, 100, 5,
               f"거래일 {len(FX):,}일 중 1,200원 미만은 "
               f"{sum(1 for _, v in FX if v < 1200):,}일",
               "'원래 1,100원대였는데'라는 감각이 맞는지 비율로 확인해 봅니다."),
        slider("x5", f"{last_d} 기준 환율은?",
               last_v, "원", 1100, 1800, 25,
               f"{last_d} {last_v:,.2f}원",
               "가장 최근 값조차 기억은 며칠 전 뉴스에 묶여 있습니다."),
    ])

# ── 9. 지진 ──────────────────────────────────────────────────────
quakes()

# ── 10. 수명 ─────────────────────────────────────────────────────
le = [r for r in load_csv("life_expectancy.csv") if r["life_expectancy_0"]]
l_latest = max(int(r["year"]) for r in le if r["code"] == "KOR")
l_cur = owid_countries(le, l_latest, "life_expectancy_0")
kor_l = l_cur["South Korea"]
l_rank = sorted(l_cur.items(), key=lambda kv: -kv[1])
kor_l_rank = [k for k, _ in l_rank].index("South Korea") + 1
_kle = {r["year"]: float(r["life_expectancy_0"]) for r in le if r["code"] == "KOR"}
kor_1950, kor_1953, kor_1955 = _kle["1950"], _kle["1953"], _kle["1955"]
wld = next(float(r["life_expectancy_0"]) for r in le
           if r["code"] == "OWID_WRL" and int(r["year"]) == l_latest)
trio_l = {c: l_cur[c] for c in ("South Korea", "Japan", "United States")
          if c in l_cur}
top_l = max(trio_l, key=trio_l.get)
name_l = {"South Korea": "한국", "Japan": "일본", "United States": "미국"}

topic(
    "life", "🩺", "얼마나 오래 사나",
    "나라별 기대수명 1950~현재",
    "Our World in Data", "https://ourworldindata.org/grapher/life-expectancy",
    [
        slider("l1", f"{l_latest}년 한국의 기대수명은?",
               kor_l, "세", 60, 95, 1,
               f"{l_latest}년 한국 {kor_l:.1f}세",
               "기대수명은 '지금 태어난 아이가 평균적으로 살 햇수'입니다. "
               "지금 살아 있는 사람의 예상 수명과는 다릅니다."),
        slider("l2", f"기대수명이 긴 순으로 세면 한국은 {len(l_cur)}곳 중 몇 위일까요?",
               kor_l_rank, "위", 1, 60, 1,
               f"{l_latest}년 {len(l_cur)}곳 중 {kor_l_rank}위 "
               f"(1위 {l_rank[0][0]} {l_rank[0][1]:.1f}세)",
               "상위권인 것은 맞지만 몇 위인지는 대개 크게 빗나갑니다."),
        slider("l3", "1950년 한국의 기대수명은?",
               kor_1950, "세", 20, 70, 1,
               f"1950년 {kor_1950:.1f}세. 한국전쟁 기간의 사망이 반영된 값이라 "
               f"1953년 {kor_1953:.1f}세, 1955년 {kor_1955:.1f}세로 빠르게 "
               f"회복합니다. {l_latest}년은 {kor_l:.1f}세",
               "숫자가 튀면 사건을 의심해야 합니다. 이 값은 오류가 아니라 "
               "전쟁의 기록입니다."),
        choice("l4", "한국·일본·미국 중 기대수명이 가장 긴 나라는?",
               ["한국", "일본", "미국"], name_l[top_l],
               " · ".join(f"{name_l[c]} {trio_l[c]:.1f}세" for c in trio_l),
               "가장 잘사는 나라가 가장 오래 사는 나라는 아닙니다."),
        slider("l5", f"{l_latest}년 세계 평균 기대수명은?",
               wld, "세", 50, 90, 1,
               f"{l_latest}년 세계 평균 {wld:.1f}세 · 한국 {kor_l:.1f}세",
               "내가 사는 곳의 수준을 세계 평균으로 착각하기 쉽습니다."),
    ])

# ── 11. 서울의 눈 ────────────────────────────────────────────────
# ERA5 강설량에는 0.01cm 같은 아주 작은 값이 많다. 그건 빼고, 하루 0.1cm 이상
# 내린 날을 '눈 온 날'로 센다 (1cm 이상만 세면 흩날린 날이 다 빠진다).
s = load_json("seoul_snow.json")["daily"]
S = [{"d": dt.date.fromisoformat(t), "snow": sn}
     for t, sn in zip(s["time"], s["snowfall_sum"])]
SNOW_CM = 0.1
snow_days = [sum(1 for x in S if x["d"].year == y and x["snow"] >= SNOW_CM)
             for y in range(1990, 2025)]
snow_avg = mean(snow_days)
snow_90s = sum(1 for x in S if 1990 <= x["d"].year <= 1999
               and x["snow"] >= SNOW_CM) / 10
snow_10s = sum(1 for x in S if 2015 <= x["d"].year <= 2024
               and x["snow"] >= SNOW_CM) / 10
s_ratio = snow_10s / snow_90s if snow_90s else 0
snowiest = max(S, key=lambda x: x["snow"])
# 1월 1일부터 세면 첫눈이 거의 다 1월이 된다. 겨울은 7월 1일에 시작해 이듬해
# 6월에 끝나는 것으로 보고, 그 안에서 처음 눈 온 날을 첫눈으로 친다.
# 원본이 2024-12-31 에서 끝나므로 2024년 겨울은 12월까지만 본다
first_snow = {}
for y in range(1990, 2025):
    f = [x["d"] for x in S if dt.date(y, 7, 1) <= x["d"] < dt.date(y + 1, 7, 1)
         and x["snow"] >= SNOW_CM]
    if f:
        first_snow[y] = f[0]
first_m = Counter(d.month for d in first_snow.values())
# 달별로 세면 11월·12월이 동률이 나올 수 있다. 그래서 '보통'은 첫눈 날짜를
# 7월 1일부터 며칠째인지로 줄 세운 가운데 날(중앙값)의 달로 정한다
first_mid = sorted(first_snow.items(),
                   key=lambda kv: (kv[1] - dt.date(kv[0], 7, 1)).days)[
    len(first_snow) // 2][1]
snow_month = {m: mean([sum(x["snow"] for x in S
                           if x["d"].year == y and x["d"].month == m)
                       for y in range(1990, 2025)]) for m in range(1, 13)}
snowiest_m = max(snow_month, key=snow_month.get)

topic(
    "seoul-snow", "❄️", "서울의 눈은 줄었나",
    "1990년부터 2024년까지, 서울의 매일 강설량",
    "Open-Meteo Archive (ERA5 재분석)", "https://open-meteo.com/",
    [
        slider("s1", "1990~2024년, 서울에서 한 해에 눈이 온 날은 평균 며칠일까요?",
               snow_avg, "일", 0, 30, 1,
               f"1990~2024년 하루 강설량 {SNOW_CM:.1f}cm 이상인 날을 해마다 세어 "
               f"평균하면 {snow_avg:.1f}일 (최소 {min(snow_days)}일 · "
               f"최대 {max(snow_days)}일)",
               "눈 온 날은 풍경째로 기억에 남아서 실제보다 많게 느껴집니다."),
        # 보기는 배수에 가장 가까운 것이 정답이 되게 경계를 둔다 (0.5 · 0.75 · 1 사이 중간값)
        choice("s2", "1990년대와 2015~2024년, 한 해 눈 온 날은 몇 배 차이일까요?",
               ["약 절반으로 줄었다", "약 4분의 3으로 줄었다", "거의 같다", "늘었다"],
               ["약 절반으로 줄었다", "약 4분의 3으로 줄었다", "거의 같다", "늘었다"][
                   0 if s_ratio < 0.625 else 1 if s_ratio < 0.875
                   else 2 if s_ratio < 1.15 else 3],
               f"하루 강설량 {SNOW_CM:.1f}cm 이상인 날의 연평균을 세면 1990~1999년 "
               f"{snow_90s:.1f}일 → 2015~2024년 {snow_10s:.1f}일 ({s_ratio:.2f}배)",
               "'요즘은 눈이 안 온다'는 느낌이 맞는지, 얼마나 줄었는지는 세어 "
               "봐야 압니다."),
        slider("s3", "1990~2024년, 서울에서 하루에 가장 많이 내린 눈은 몇 cm일까요?",
               snowiest["snow"], "cm", 0, 50, 1,
               f"1990~2024년 하루 강설량의 최댓값은 "
               f"{snowiest['d']:%Y년 %m월 %d일} {snowiest['snow']:.1f}cm",
               "폭설은 뉴스 화면과 함께 기억되어 실제보다 크게 남습니다."),
        choice("s4", "1990~2024년, 서울의 첫눈은 보통 몇 월에 올까요?",
               ["10월", "11월", "12월", "1월"], f"{first_mid.month}월",
               f"1990~2024년 7월~이듬해 6월을 한 겨울로 보고 하루 {SNOW_CM:.1f}cm "
               f"이상 처음 온 날을 {len(first_snow)}번의 겨울에서 줄 세우면 가운데 날이 "
               f"{first_mid:%m월 %d일}입니다 ("
               + " · ".join(f"{m}월 {n}번" for m, n in sorted(
                   first_m.items(), key=lambda kv: (kv[0] < 7, kv[0]))) + ")",
               "첫눈은 해마다 들쭉날쭉해서, '보통'이 어느 달인지는 날짜를 줄 세워 "
               "봐야 압니다."),
        choice("s5", "서울에서 눈이 가장 많이 내리는 달은 언제일까요?",
               ["11월", "12월", "1월", "2월"], f"{snowiest_m}월",
               "1990~2024년 달별 강설량을 해마다 더해 평균하면 "
               + " · ".join(f"{m}월 {snow_month[m]:.1f}cm" for m in (11, 12, 1, 2)),
               "첫눈이 오는 달과 눈이 가장 많이 오는 달은 다릅니다."),
    ],
    caveat="이 값은 서울 관측소가 아니라 위도 37.5·경도 127.0 격자의 ERA5 재분석 "
           "강설량(쌓인 깊이가 아니라 하루에 내린 양)이고, '눈 온 날'을 0.1cm 이상으로 "
           "세느냐 1cm 이상으로 세느냐에 따라 눈 온 날수와 첫눈 달이 크게 달라지므로 "
           "기상청 발표와 다를 수 있습니다.")

metro_pop()
typhoon()
korea_heat()


# ════════════════════════════════════════════════════════════════
def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    index = []
    for t in TOPICS:
        assert len(t["questions"]) == 5, f"{t['id']}: 문항이 5개가 아닙니다"
        pack = {k: t[k] for k in ("id", "emoji", "title", "blurb",
                                  "source", "source_url", "caveat")}
        pack["questions"] = t["questions"]
        io.open(OUT / f"{t['id']}.json", "w", encoding="utf-8").write(
            json.dumps(pack, ensure_ascii=False, indent=2))
        index.append({k: t[k] for k in ("id", "emoji", "title", "blurb",
                                        "source")} | ({"fx": t["fx"]} if t["fx"] else {})
                     | ({"art": t["art"]} if t["art"] else {}))

    # 제목·부제는 화면을 바꾸며 고친 값을 지킨다 (2장에서 내 제목으로 바꾼다).
    # 다시 계산해도 내 제목이 «감 테스트»로 돌아가지 않게, 있던 값을 읽어 쓴다
    old = {}
    if (APP / "topics.json").exists():
        try:
            old = json.load(io.open(APP / "topics.json", encoding="utf-8"))
        except ValueError:
            old = {}
    io.open(APP / "topics.json", "w", encoding="utf-8").write(json.dumps({
        "title": old.get("title", "감 테스트"),
        "subtitle": old.get("subtitle", "숫자에 대한 당신의 감은 몇 점입니까"),
        # 등급·문구는 여기서 고칩니다. 코드를 건드릴 일이 아닙니다
        "grades": [
            {"min": 90, "name": "촉이 데이터급", "emoji": "🎯"},
            {"min": 70, "name": "감이 좋은 편", "emoji": "📊"},
            {"min": 50, "name": "보통의 감각", "emoji": "🙂"},
            {"min": 30, "name": "느낌대로 삽니다", "emoji": "🎲"},
            {"min": 0, "name": "감은 접어두시죠", "emoji": "🙈"},
        ],
        "reactions_choice": {"hit": "맞히셨습니다", "miss": "다들 그렇게 찍습니다"},
        "reactions": [
            {"max": 5, "text": "촉이 좋으시네요"},
            {"max": 20, "text": "비슷하게 보셨습니다"},
            {"max": 60, "text": "음…"},
            {"max": 999, "text": "꽤 멀리 가셨습니다"},
        ],
        "topics": index,
    }, ensure_ascii=False, indent=2))

    # 사람이 읽는 정답지
    md = ["# 문항 정답지 — 10주제 50문항", "",
          "> 모든 값은 `data/raw/` 의 원본에서 `tools/build_topics.py` 가 계산합니다.", ""]
    for t in TOPICS:
        md += [f"## {t['emoji']} {t['title']}", "",
               f"- 출처: {t['source']} · {t['source_url']}"]
        if t["caveat"]:
            md += [f"- **한계** {t['caveat']}"]
        md += [""]
        for q in t["questions"]:
            a = f"{q['answer']}{q.get('unit', '')}" if q["type"] == "slider" \
                else q["answer"]
            md += [f"**{q['text']}**", "",
                   f"- 정답 **{a}**", f"- 근거 {q['basis']}",
                   f"- 왜 틀리나 {q['why']}", ""]
    io.open(HERE / "정답지.md", "w", encoding="utf-8").write("\n".join(md))

    print(f"주제 {len(TOPICS)}개 · 문항 {sum(len(t['questions']) for t in TOPICS)}개")
    for t in TOPICS:
        print(f"\n{t['emoji']} {t['title']}  ({t['source']})")
        for q in t["questions"]:
            a = f"{q['answer']}{q.get('unit', '')}" if q["type"] == "slider" \
                else q["answer"]
            print(f"    [{q['type'][:6]:<6}] {q['text'][:44]:<44} → {a}")


if __name__ == "__main__":
    main()
