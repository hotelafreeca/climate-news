#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
기후로운 경제생활 뉴스 모니터링
실행: python fetch_news.py
출력: news_YYYYMMDD.html
"""

import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import html as html_lib
import json as json_lib
import os
import re
import sys
import time

# ─────────────────────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────────────────────
KST = timezone(timedelta(hours=9))
MAX_PER_CATEGORY = 10
MAX_EXPERTS = 30
MAX_PER_EXPERT = 3        # 전문가 1인당 최대 기사 수
EXPERT_DAYS = 30
REQUEST_DELAY = 0.25

# ── 국내 뉴스 카테고리 (한국어 키워드) ────────────────────────
# quota: 카테고리별 노출 건수. 과거 270편 조회수 분석 결과 타율(1만+ 비율)에
# 따라 차등 배분 — 배터리 35%·기업/투자 19%·지정학 16% vs 기상 0%·라이프 6%
CATEGORIES = [
    {"id": "ev",   "name": "전기차·배터리·이차전지",     "color": "#EF7D2E", "quota": 10,
     "keywords": [
         "전기차 판매 동향", "배터리 3사 투자 실적", "이차전지 캐즘",
         "전기차 화재", "에코프로 주가", "BYD 한국 시장",
         "전고체 배터리", "수소경제", "ESS 시장 전망",
         "휴머노이드 로봇 배터리", "폐배터리 재활용 시장"
     ]},
    {"id": "re",   "name": "재생에너지 정책·산업",        "color": "#EF7D2E", "quota": 10,
     "keywords": [
         "태양광 보급 현황", "재생에너지 목표", "해상풍력 특별법",
         "영농형 태양광", "재생에너지 PPA", "제주도 재생에너지",
         "에너지 고속도로", "전력망 송전망 투자", "HVDC 송전",
         "에너지 인프라 투자"
     ]},
    {"id": "nuke", "name": "원전·에너지 믹스 논쟁",       "color": "#EF7D2E", "quota": 8,
     "keywords": [
         "SMR 소형모듈원전", "원전 수출", "노후 원전 수명",
         "핵융합 투자", "에너지전환 시나리오", "친환경 선박",
         "조선업 친환경 수주", "LNG 운반선 수주"
     ]},
    {"id": "food", "name": "기후플레이션·식량·농업",       "color": "#EF7D2E", "quota": 8,
     "keywords": [
         "기후플레이션", "쌀값 이상기후", "기후위기 물가 인상",
         "농산물 가격 폭등", "폭염 작물 피해"
     ]},
    {"id": "esg",  "name": "기후 금융·ESG·탄소시장",      "color": "#EF7D2E", "quota": 8,
     "keywords": [
         "기후금융", "탄소배출권 가격", "국민연금 ESG",
         "스코프3 탄소발자국", "CBAM 탄소국경세",
         "연기금 에너지 인프라 투자", "노르웨이 국부펀드 기후"
     ]},
    {"id": "wx",   "name": "기상이변·극단기후 현상",       "color": "#EF7D2E", "quota": 5,
     "style": "life",   # 기업 보너스 제외 — CSR·동정 기사가 기업명으로 상위 차지하는 것 방지
     "keywords": [
         "역대급 폭염 원인", "기상이변 극단기후", "해수면 온도 상승",
         "가뭄 홍수 피해", "산불 피해 경제"
     ]},
    {"id": "geo",  "name": "미중 패권·지정학·에너지 안보", "color": "#EF7D2E", "quota": 10,
     "keywords": [
         "미중 패권 에너지", "지정학 에너지 안보", "핵심광물 공급망",
         "희토류 수급", "태양광 미중 갈등", "트럼프 기후 정책",
         "중국 탄소배출 감소", "중국 에너지 전환", "핵심광물 수출 통제",
         "호르무즈 유가", "중동 정세 유가", "국제유가 전망", "OPEC 감산"
     ]},
    {"id": "ai",   "name": "AI·데이터센터·전력 수요",      "color": "#EF7D2E", "quota": 10,
     "keywords": [
         "AI 전력 수요", "데이터센터 전력 소비", "우주 태양광",
         "전력망 투자 수혜", "데이터센터 투자 유치", "원전 데이터센터 전력",
         "AI 반도체 전력 효율"
     ]},
    {"id": "law",  "name": "기후 정책·법·제도",            "color": "#EF7D2E", "quota": 6,
     "keywords": [
         "COP 기후총회", "NDC 온실가스 감축", "기후 예산 삭감",
         "기후특위 활동", "탄소중립법 개정"
     ]},
    {"id": "life", "name": "기후·일상·소비·라이프스타일",  "color": "#EF7D2E", "quota": 8,
     "style": "life",   # 기업·돈 신호 대신 생활 연결 위주로 스코어링
     "keywords": [
         "제로에너지 건물", "도시 열섬 대책", "쓰레기 직매립 금지",
         "탈플라스틱", "기후변화 먹거리 가격", "기후 와인 작황",
         "헌옷 의류 폐기물", "기후변화 부동산 가치", "기후 보험료",
         "배추 김치 기후변화"
     ]},
    {"id": "tech", "name": "기술 레이더",                 "color": "#EF7D2E", "quota": 5,
     "keywords": [
         "핵융합 투자 상용화", "양자컴퓨터 에너지",
         "전고체 배터리 상용화", "CCUS 탄소포집 상용화",
         "직접공기포집 DAC", "페로브스카이트 태양전지",
         "초전도 송전", "장주기 에너지저장"
     ]},
]

# ── 아이템성 스코어 (과거 조회수 데이터 기반 신호) ─────────────
# 기업명 포함 영상 타율 27% vs 미포함 9% / 날씨 단독 25편 중 1만+ 0편
SCORE_COMPANIES = [
    "현대차", "현대자동차", "기아", "삼성전자", "삼성SDI", "삼성물산",
    "SK하이닉스", "SK온", "SK이노베이션", "LG에너지솔루션", "LG전자",
    "LG화학", "포스코", "한화", "두산", "HD현대", "한국전력", "한전",
    "에코프로", "테슬라", "BYD", "CATL", "엔비디아", "TSMC", "폭스바겐",
    "토요타", "도요타", "GM", "포드", "BMW", "벤츠", "애플", "구글",
    "마이크로소프트", "아마존", "오픈AI", "네이버", "카카오", "셀온",
    "롯데", "GS", "효성", "코오롱", "OCI", "한솔", "씨에스윈드",
]
SCORE_MONEY = [
    "투자", "주가", "주식", "매수", "수익", "실적", "보조금", "요금",
    "가격", "수출", "수주", "계약", "펀드", "연금", "적자", "흑자",
    "매출", "영업이익", "급등", "급락", "상장", "인수", "합병", "유치",
]
SCORE_TURNING = [
    "최초", "사상", "역대", "첫 ", "전격", "돌파", "반전", "뒤집",
    "급증", "급감", "초읽기", "임박", "본격", "가속",
]
# 거시·지정학 빅이슈 신호 — 기업명·돈신호가 없어도 영양가 높은 사건
# (전쟁 종전, 해협 봉쇄/개방, 제재, 정상회담 등 — 호르무즈류가 묻히던 문제 보정)
BIG_ISSUE_TERMS = [
    "전쟁", "종전", "휴전", "정전협정", "봉쇄", "개방", "해협", "금수",
    "제재", "수출통제", "관세", "정상회담", "회담", "쿠데타", "디폴트",
    "파산", "국유화", "징발", "횡재세", "보복", "공습", "미사일",
    "지정학", "감세", "탈퇴", "협정", "단교",
    # 주의: 감산·증산·OPEC 등 에너지 수급 신호는 ENERGY_SEC_TERMS가 담당(중복 가산 방지)
]
# 에너지·자원 안보 신호 (기후경제 핵심인데 돈신호 사전엔 없던 단어들)
ENERGY_SEC_TERMS = [
    "유가", "원유", "국제유가", "천연가스", "LNG", "가스값", "전력난",
    "정전", "블랙아웃", "공급망", "핵심광물", "희토류", "리튬", "니켈",
    "구리", "우라늄", "전력 수급", "에너지 안보", "수급 차질",
    "감산", "증산", "OPEC", "호르무즈", "수에즈", "병목",
]
SCORE_NUM_RE = r"\d+(?:[.,]\d+)?\s*(?:조|억|만\s*대|%|퍼센트|달러|원|GW|MW|TWh|kWh|배)"
WEATHER_TERMS = [
    "폭염", "폭설", "한파", "장마", "호우", "홍수", "산불", "태풍",
    "가뭄", "이상기후", "기상이변", "해수면", "빙하", "열대야", "폭우",
]
# 기상이변 카테고리 통과 요건 — 제목에 이 중 하나는 있어야 함
WX_REQUIRED_TERMS = WEATHER_TERMS + [
    "엘니뇨", "라니냐", "기온", "기후", "무더위", "열돔", "이상고온",
    "이상저온", "강수량", "해빙", "온난화",
]
ECON_LINK_TERMS = [
    "피해액", "보험", "손실", "가격", "물가", "전력", "요금", "산업",
    "수요", "비용", "경제", "시장", "수급", "주가", "농작물", "작물",
    "복구", "예산",
]
PROCEDURAL_TERMS = [
    "협약 체결", "위원회 구성", "포럼 개최", "세미나", "토론회",
    "캠페인", "선포식", "발대식", "공동선언", "출범식", "협의체",
]
# 특징주·단타성 시황 기사 — 실질 신호(수주·계약 등) 없으면 강한 감점
TICKER_NOISE_TERMS = [
    "특징주", "상한가", "하한가", "신고가", "급등 마감", "강세 마감",
    "상승 마감", "하락 마감", "매수세", "순매수", "테마주",
    "관련주", "목표주가", "오늘의 주가", "주가 흐름", "%↑", "%↓",
    "% 상승", "% 하락", "장 초반", "장중",
    # 주의: '수급'은 '전력 수급'·'수급 차질'(정상 에너지어)과 충돌하므로 제외
]
SUBSTANTIVE_TERMS = [
    "수주", "계약", "실적 발표", "인수", "합병", "투자 유치",
    "공장", "증설", "정책", "법안", "출시",
]
# 생활·의외 연결 신호 — 조회수와 무관하게 프로그램이 좋아하는 결
# (와인·쌀·부동산·의류·국부펀드·김치·헌옷수거함 류의 "알고 보면 기후 얘기")
LIFE_ANGLE_TERMS = [
    "와인", "김치", "배추", "쌀값", "쌀 ", "커피", "치킨", "맥주",
    "과일", "사과", "수산물", "오징어", "어획", "양식", "식탁", "밥상",
    "패션", "의류", "헌옷", "옷장", "부동산", "집값", "전세", "보험료",
    "국부펀드", "연금", "여행", "스키", "축제", "올림픽", "월드컵",
    "테니스", "마라톤", "골프", "꿀벌", "산호", "송이", "젓갈",
    "명태", "한라봉", "감귤", "수돗물", "급식",
]
# 발품 기획·심층 보도 신호 (제목 표기 관행)
FEATURE_TERMS = [
    "[단독", "[르포", "[기획", "[심층", "[탐사", "[현장", "[추적",
    "단독]", "르포]", "10년 관찰", "보고서",
]

# ── 국내 기후 전문 매체 (직접 구독) ──────────────────────────
# 화제 이슈 × 기후 연결(월드컵 폭염, 행사 탄소배출 등)은 이들이 이미 해줌
KO_MEDIA_FEEDS = [
    {"url": "https://www.newspenguin.com/rss/allArticle.xml", "source": "뉴스펭귄"},
    {"url": "https://greenium.kr/feed/",                      "source": "그리니엄"},
    {"url": "https://www.impacton.net/rss/allArticle.xml",    "source": "임팩트온"},
    {"url": "https://www.esgeconomy.com/rss/allArticle.xml",  "source": "ESG경제"},
    {"url": "https://www.greenpostkorea.co.kr/rss/allArticle.xml", "source": "그린포스트코리아"},
]
KO_MEDIA_QUERIES = [
    # RSS 없는 매체: 구글뉴스 검색 후 소스명 일치 기사만 채택
    {"query": "뉴스트리 기후", "source": "뉴스트리"},
]

# ── 화제 × 기후 (평소 기후와 안 엮이던 분야가 기후와 엮일 때 포착) ──
# 과거 콘텐츠 259편에서 '기후 본업이 아닌데 히트친' 소재를 분야별로 추출.
# 예: "쌀 기후위기", "치킨 폭염", "월드컵 폭염", "와인 기후변화", "비트코인 탄소"
SURPRISE_KEYWORDS = [
    # 스포츠·레저
    "월드컵", "올림픽", "야구", "축구", "마라톤", "러닝", "테니스", "골프", "페스티벌",
    # 음식·기호식품·농수산
    "쌀", "치킨", "김치", "배추", "커피", "와인", "맥주", "초콜릿", "바나나",
    "해산물", "해파리", "정어리", "사과", "감귤",
    # 패션·소비
    "패스트패션", "의류", "헌옷", "뷰티", "화장품", "물티슈", "텀블러",
    # 부동산·건설
    "부동산", "집값", "그린벨트", "싱크홀",
    # 금융·투자
    "비트코인", "국부펀드", "국민연금", "보험료",
    # 보건·생태
    "모기", "러브버그", "곤충", "반려동물", "미세플라스틱", "감염병",
    # 기술·우주
    "우주", "인공위성",
]
CLIMATE_WORDS = [
    "기후", "기후위기", "기후변화", "탄소", "온실가스", "폭염", "온난화",
    "열대야", "이상기후", "친환경", "탄소중립", "탄소배출",
]
# 연예·가십 거짓양성 제외 — '폭염'이 관용 표현으로 박힌 화보·공항패션 등 차단
GOSSIP_EXCLUDE = [
    "비주얼", "공항", "출국", "입국", "화보", "미모", "일상룩", "근황샷",
    "포착", "셀카", "열애", "결혼", "이혼", "데뷔", "컴백", "패션쇼",
    "인형", "심쿵", "movie", "예능", "리즈", "각선미", "몸매",
]
TRUSTED_EN_FEEDS = [
    # ✅ 작동 확인된 피드
    {"url": "https://grist.org/feed/",                                         "source": "Grist"},
    {"url": "https://coveringclimatenow.org/feed/",                            "source": "CCNow"},
    {"url": "https://www.carbonbrief.org/feed/",                               "source": "Carbon Brief"},
    {"url": "https://insideclimatenews.org/feed/",                             "source": "Inside Climate News"},
    {"url": "https://cleantechnica.com/feed/",                                 "source": "CleanTechnica"},
    {"url": "https://electrek.co/feed/",                                       "source": "Electrek"},
    {"url": "https://www.renewableenergyworld.com/feed/",                      "source": "Renewable Energy World"},
    {"url": "https://dailyclimate.org/feeds/feed.rss",                         "source": "Daily Climate"},
    # ⚠️ 공식 주소 맞으나 서버에서 실제 응답 확인 필요
    {"url": "https://www.theguardian.com/environment/climate-crisis/rss",      "source": "The Guardian"},
    {"url": "https://www.theguardian.com/environment/energy/rss",              "source": "The Guardian"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Climate.xml",        "source": "NYT Climate"},
    {"url": "https://www.motherjones.com/environment/feed/",                   "source": "Mother Jones"},
]

# ── 유력 언론 Google RSS 쿼리 (레이어2) ──────────────────────
PRIORITY_EN_QUERIES = [
    # EV·배터리
    '"Bloomberg" EV battery electric vehicle',
    '"Reuters" electric vehicle battery',
    # 재생에너지
    '"Bloomberg" renewable energy solar wind',
    '"Financial Times" renewable energy',
    # 원전·에너지믹스
    '"Reuters" nuclear energy SMR',
    '"Wall Street Journal" nuclear energy',
    # 기후금융·ESG
    '"Bloomberg" carbon market ESG climate finance',
    '"Financial Times" carbon market climate',
    # 기상이변
    '"Reuters" extreme weather climate',
    '"New York Times" climate extreme weather',
    # 지정학·에너지안보
    '"Bloomberg" energy security critical minerals',
    '"Reuters" rare earth energy geopolitics',
    # AI·전력
    '"Bloomberg" AI data center power electricity',
    '"Wall Street Journal" AI power demand',
    # 기후정책·법
    '"Reuters" climate policy NDC emissions',
    '"New York Times" climate policy',
    # 외신이 주목하는 한국 기후·에너지
    '"South Korea" climate energy policy',
    '"South Korea" battery EV renewable',
]

# ── 레이어2 우선 소스 ─────────────────────────────────────────
PRIORITY_SOURCES_EN = {
    "Bloomberg", "Reuters", "Financial Times", "Wall Street Journal",
    "Axios", "Washington Post", "The New York Times", "NYT",
    "The Economist", "Science", "Nature"
}

# ── 전문가 목록 ───────────────────────────────────────────────
EXPERTS = [
    {"name": "홍종호",    "role": "서울대 환경대학원 교수",          "tag": "진행자",      "search": "홍종호 서울대 환경"},
    {"name": "한병화",    "role": "유진투자증권 이사",               "tag": "금융·배터리", "search": "한병화 유진투자증권"},
    {"name": "김백민",    "role": "부경대 환경대기과학과 교수",       "tag": "기상·기후과학","search": "김백민 부경대"},
    {"name": "지현영",    "role": "서울대 환경에너지법정책센터 변호사", "tag": "정책·법",   "search": "지현영 변호사"},
    {"name": "김병권",    "role": "녹색전환연구소 소장",              "tag": "기후경제",   "search": "김병권 녹색전환연구소"},
    {"name": "권석준",    "role": "성균관대 화학공학과 교수",          "tag": "반도체·기술","search": "권석준 성균관대"},
    {"name": "권효재",    "role": "COR 에너지인사이트 대표",          "tag": "에너지",     "search": "권효재 에너지"},
    {"name": "차영주",    "role": "와이즈경제연구소 소장",             "tag": "경제·투자",  "search": "차영주 와이즈경제연구소"},
    {"name": "선정수",    "role": "클리프 기자",                      "tag": "기후미디어", "search": "선정수 기자"},
    {"name": "서재철",    "role": "녹색연합 전문위원",                "tag": "산불·산림",  "search": "서재철 녹색연합"},
    {"name": "이명주",    "role": "건물 에너지 전문가",               "tag": "건물·에너지","search": "이명주 건물 에너지"},
    {"name": "강구상",    "role": "대외경제정책연구원 북미유럽팀장",  "tag": "국제통상",   "search": "강구상 대외경제정책연구원"},
    {"name": "권이균",    "role": "탄소포집 전문가",                  "tag": "탄소포집",   "search": "권이균 탄소포집"},
    {"name": "김주진",    "role": "기후솔루션 대표",                  "tag": "정책·법",    "search": "김주진 기후솔루션"},
    {"name": "남재작",    "role": "식량·농업 연구자",                 "tag": "식량·농업",  "search": "남재작 식량 농업"},
    {"name": "정재학",    "role": "영농형 태양광 전문가",             "tag": "태양광",     "search": "정재학 영농형 태양광"},
    {"name": "김해동",    "role": "기상 전문가",                      "tag": "기상·기후",  "search": "김해동 기상"},
    {"name": "한병섭",    "role": "원전 전문가",                      "tag": "원전",       "search": "한병섭 원전"},
    {"name": "이강운",    "role": "홀로세생태보존연구소 소장",         "tag": "생태·곤충",  "search": "이강운 홀로세생태"},
    {"name": "홍수열",    "role": "자원순환사회경제연구소 소장",       "tag": "폐기물·순환","search": "홍수열 자원순환"},
    {"name": "장다울",    "role": "오션에너지패스웨이 한국 대표",     "tag": "해상풍력",   "search": "장다울 해상풍력"},
    {"name": "염광희",    "role": "아고라 에네르기벤데 선임연구원",   "tag": "유럽 에너지","search": "염광희 아고라"},
    {"name": "박재필",    "role": "나라스페이스 대표",                 "tag": "우주·위성",  "search": "박재필 나라스페이스"},
    {"name": "하수정",    "role": "북유럽연구소장",                    "tag": "북유럽·에너지","search": "하수정 북유럽"},
    {"name": "정준혁",    "role": "서울대 법학전문대학원 교수",        "tag": "기후법",     "search": "정준혁 서울대 법학"},
    {"name": "남종영",    "role": "기후변화와동물연구소장",            "tag": "동물·생태",  "search": "남종영 기후변화"},
    {"name": "개러스 위어","role": "주한영국부대사",                  "tag": "국제·영국",  "search": "개러스 위어 영국대사"},
    {"name": "김현권",    "role": "쌀·농업 전문가",                   "tag": "농업·식량",  "search": "김현권 농업 식량"},
    {"name": "윤지로",    "role": "기후 미디어 클리프 대표",          "tag": "기후미디어", "search": "윤지로 기후미디어"},
    {"name": "손현정",    "role": "유안타증권 연구원",                 "tag": "증권·투자",  "search": "손현정 유안타증권"},
]

# ── 환경전문기자 목록 ─────────────────────────────────────────
REPORTERS = [
    {"name": "오경민", "media": "경향신문",   "beat": "기후/환경",   "search": "오경민 경향신문 기후"},
    {"name": "김경학", "media": "경향신문",   "beat": "에너지/AI",   "search": "김경학 경향신문 에너지"},
    {"name": "김기범", "media": "경향신문",   "beat": "생태",        "search": "김기범 경향신문 생태"},
    {"name": "장수경", "media": "한겨레",     "beat": "기후환경",    "search": "장수경 한겨레 기후"},
    {"name": "옥기원", "media": "한겨레",     "beat": "에너지/전력", "search": "옥기원 한겨레 에너지"},
    {"name": "박기용", "media": "한겨레",     "beat": "기후/환경",   "search": "박기용 한겨레 기후"},
    {"name": "최원형", "media": "한겨레",     "beat": "기후",        "search": "최원형 한겨레 기후"},
    {"name": "서동균", "media": "SBS",        "beat": "기상/과학",   "search": "서동균 SBS 기상"},
    {"name": "황덕현", "media": "뉴스1",      "beat": "기후/환경",   "search": "황덕현 뉴스1 기후"},
    {"name": "이재영", "media": "연합뉴스",   "beat": "기후",        "search": "이재영 연합뉴스 기후"},
    {"name": "정종오", "media": "아이뉴스24", "beat": "기후",        "search": "정종오 아이뉴스24 기후"},
    {"name": "서영민", "media": "KBS",       "beat": "경제/기후",   "search": "서영민 KBS 기자"},
    {"name": "김승환", "media": "MBC",       "beat": "기후/환경",   "search": "김승환 MBC 기후 환경"},
    {"name": "반기웅", "media": "경향신문",   "beat": "기후/환경",   "search": "반기웅 경향신문"},
    {"name": "김광우", "media": "헤럴드경제", "beat": "금융/기후",   "search": "김광우 헤럴드경제"},
    {"name": "김규원", "media": "한겨레",     "beat": "기후/환경",   "search": "김규원 한겨레"},
    {"name": "강찬수", "media": "에너지경제", "beat": "환경/에너지", "search": "강찬수 에너지경제"},
    {"name": "김승환", "media": "세계일보",   "beat": "기후/환경",   "search": "김승환 세계일보 기후"},
    # 기후 전문 매체·단체
    {"name": "윤지로", "media": "클리프",     "beat": "기후미디어",  "search": "윤지로 클리프"},
    {"name": "선정수", "media": "클리프",     "beat": "기후 팩트체크","search": "선정수 기후"},
    {"name": "권오성", "media": "기후솔루션", "beat": "기후·에너지", "search": "권오성 기후솔루션"},
    {"name": "뉴스룸", "media": "그린피스",   "beat": "기후 캠페인", "search": "그린피스 기후 에너지"},
]

# ── 정책 동향: 인물 + 기관 ────────────────────────────────────
# tag는 칩에서 이름 뒤에 붙는 직책 표기 — 기관명은 자체로 충분하므로 빈 값
POLICY_FIGURES = [
    {"name": "김성환", "role": "기후에너지환경부 장관", "tag": "장관",
     "search": "김성환 장관 기후"},
    {"name": "기후에너지환경부", "role": "정부 부처", "tag": "",
     "search": "기후에너지환경부 정책 발표"},
    {"name": "산업통상자원부", "role": "정부 부처", "tag": "",
     "search": "산업통상자원부 에너지 정책"},
    {"name": "대통령실", "role": "에너지·기후 어젠다", "tag": "",
     "search": "대통령실 에너지 기후"},
    {"name": "안호영", "role": "국회 기후에너지환경노동위원장", "tag": "환노위원장",
     "search": "안호영 위원장"},
    {"name": "위성곤", "role": "국회 기후특위 위원장", "tag": "기후특위 위원장",
     "search": "위성곤 기후"},
    {"name": "국회 기후특위", "role": "국회 특별위원회", "tag": "",
     "search": "국회 기후특위"},
    {"name": "금융위원회", "role": "ESG 공시·기후금융", "tag": "",
     "search": "금융위원회 ESG 공시"},
]

# ── 필터 패턴 ─────────────────────────────────────────────────
EXCLUDE_TITLE_PATTERNS = [
    "보도자료", "공고", "입찰", "채용", "모집", "설명회", "공모",
    "업무협약", "MOU", "간담회", "현장방문", "축사",
    "기념촬영", "기념사", "기념식", "포상", "수상",
    "오늘의 주요일정", "주요일정", "[오늘의",
    "[보도설명", "[산업부]", "[환경부]", "[과기부]", "[국토부]",
    "보도설명자료", "설명자료", "해명자료", "알려 드립니다",
    "시리즈", "좋은법", "4U",
    "카지노", "홀덤", "슬롯", "베팅",
    # CSR·동정성 기사 (정보값 낮음)
    "봉사단", "봉사활동", "사회공헌", "성금", "기부금", "감사패",
    "표창", "위촉식", "헌혈", "김장 나눔",
]

EXCLUDE_SOURCE_PATTERNS = [
    "정책브리핑", "대한민국 정책브리핑", "국가기후위기대응위원회",
    "Vietnam.vn", "vietnam.vn",        # 베트남 한국어 번역 스팸
    "민심뉴스", "bnt뉴스", "bntnews",   # 저품질 다량 매체
    "fathom", "Fathom Journal",        # 이스라엘 매체 (국내 오분류)
    "kmrk",                            # 정체불명 .ru
    "MSN", "msn.com",                  # 집계 사이트 — 원문 언론사 JS 렌더라 추출 불가
    "tokenpost", "토큰포스트",          # 링크 깨짐(접근 불가)
    "Sortir à Paris", "sortiraparis",  # 프랑스 행사정보 사이트 (국내 오분류)
    "VOI.id", "voi.id",                # 인도네시아 매체 (국내 오분류)
    "CoinDesk", "coindesk",            # 미국 크립토 매체 (국내 오분류)
    "notizie.it", "notizie",           # 이탈리아 매체 (국내 오분류)
]

# 국내 뉴스에서 차단할 해외 도메인 TLD (링크 host 기준)
BLOCKED_TLDS = (".vn", ".ru", ".il", ".cn", ".id", ".it")

# 집계·포털 사이트 — 원문 언론사로 재추적해야 함 (source가 차 있어도)
AGGREGATOR_SOURCES = {"MSN", "msn", "네이트", "다음뉴스", "Daum", "Nate"}

# 소스명 표기 교정 (substring 매칭, 소문자 비교)
SOURCE_RENAME = {
    "thecommoditiesnews": "CNews",
    "seouleconews": "서울이코노미뉴스",
    "numbers.co.kr": "넘버스",
    "numbers": "넘버스",
    "chosunbiz": "조선비즈",
    "newsroad": "뉴스로드",
    "ainews1": "독립신문",
    "sportsseoul": "스포츠서울",
    "fetv": "FETV",
    "kyongbuk": "경북일보",
    "smartbizn": "스마트비즈",
    "car.withnews": "더위드카",
    "wowglobal": "와우글로벌",
    "polinews": "폴리뉴스",                    # "폴리뉴스 Polinews" 등
    "오승혁": "더팩트",                         # 더팩트 칼럼 "오승혁의 '현장'"
    "경남대학교 교육방송국": "한국건설신문",      # 오분류 소스 교정
    "thefairnews": "더페어뉴스",
    "2news": "에너지뉴스",                       # 2news.co.kr
    "sisaon": "시사오늘",
    "naewaynews": "내외신문",
    "catchnews": "CatchNews",
}

EXPERT_EXCLUDE_PATTERNS = [
    "[포토]", "[사진]", "포토뉴스", "기념촬영", "기념사",
    "기념식", "오늘의 주요일정", "주요일정",
]

# ── 국내 뉴스 소스 품질 정렬 ─────────────────────────────────
PREFERRED_SOURCES_KO = {
    "한겨레", "경향신문", "조선일보", "중앙일보", "동아일보",
    "매일경제", "한국경제", "머니투데이", "연합뉴스", "헤럴드경제",
    "비즈니스포스트", "이데일리", "뉴시스", "서울경제"
}

PORTAL_SOURCES = {"네이트", "v.daum.net", "daum", "nate.com", "nate", "다음뉴스", "Daum"}

# 제목 말미 대괄호에서 소스를 추정할 때 언론사명으로 오인하면 안 되는 섹션 표기
NOT_PRESS_TOKENS = {
    "포토로그", "포토", "영상", "단독", "속보", "르포", "기획", "칼럼",
    "사설", "인터뷰", "종합", "전문", "현장", "오늘의 날씨", "날씨",
    "퀴즈", "카드뉴스", "팩트체크", "그래픽",
}

# 소스명 양끝의 장식용 특수문자 제거 (":: 위즈경제 ::" → "위즈경제")
_SRC_DECOR = "：:·•※○●◆◇▶▷◀◁■□▪▫★☆=~|/\\[](){}<>「」『』【】〔〕“”‘’\"'–—_-"
SRC_DECOR_RE = re.compile(
    r"^[%s\s]+|[%s\s]+$" % (re.escape(_SRC_DECOR), re.escape(_SRC_DECOR)))

# "○○의 '△△'" 형태의 칼럼·코너명을 매체명으로 오인한 경우 탐지 ("오승혁의 '현장'" 등)
COLUMN_NAME_RE = re.compile(r"의\s*['\"‘’“”「『【]")

# ── 콘텐츠 캘린더 ─────────────────────────────────────────────
CALENDAR = {
    1: [
        {"type": "policy",   "label": "정책·국제", "color": "#EF7D2E",
         "title": "다보스 포럼",
         "memo": "에너지·기후 투자 선언 쏟아짐 — 글로벌 기후 금융 흐름 파악",
         "keywords": ["다보스 에너지", "WEF 기후", "다보스 포럼 투자"]},
        {"type": "earnings", "label": "기업실적",  "color": "#EF7D2E",
         "title": "배터리 3사 분기 실적 (1월 말)",
         "memo": "LG에너지솔루션·삼성SDI·SK온 4Q 어닝시즌, 캐즘 극복 여부 확인",
         "keywords": ["LG에너지솔루션 실적", "삼성SDI 실적", "SK온 실적"]},
        {"type": "earnings", "label": "기업실적",  "color": "#EF7D2E",
         "title": "현대차·기아 분기 실적 (1월 말)",
         "memo": "전기차 판매 비중·글로벌 EV 점유율 변화 추적",
         "keywords": ["현대차 실적", "기아 전기차 판매", "아이오닉 판매량"]},
        {"type": "earnings", "label": "기업실적",  "color": "#EF7D2E",
         "title": "한국전력 분기 실적 (1월 말)",
         "memo": "적자 규모·전기 요금 인상 압력 — 에너지 가격 정책과 직결",
         "keywords": ["한국전력 실적", "전기요금 인상", "한전 적자"]},
        {"type": "earnings", "label": "기업실적",  "color": "#EF7D2E",
         "title": "포스코홀딩스 분기 실적 (1월 말)",
         "memo": "리튬·이차전지 소재 사업 동향 — 배터리 공급망 원가 흐름",
         "keywords": ["포스코 실적", "포스코 리튬", "포스코 이차전지"]},
        {"type": "macro",    "label": "거시·실적", "color": "#EF7D2E",
         "title": "CES (1월 초, 라스베이거스)",
         "memo": "AI·모빌리티·에너지 신기술 총집합 — 전력 수요·배터리·로봇 아이템 발굴",
         "keywords": ["CES 에너지", "CES 전기차 배터리", "CES AI 전력"]},
        {"type": "macro",    "label": "거시·실적", "color": "#EF7D2E",
         "title": "FOMC 금리 결정 (1월 말)",
         "memo": "금리 방향 = 재생에너지·인프라 투자 자금 조달 비용 — 에너지 전환 속도 변수",
         "keywords": ["FOMC 금리 결정", "금리 재생에너지 투자", "연준 금리 전망"]},
        {"type": "macro",    "label": "거시·실적", "color": "#EF7D2E",
         "title": "테슬라 4Q 실적 (1월 말)",
         "memo": "글로벌 EV 수요 바로미터 — 에너지저장(메가팩) 사업 성장률 체크",
         "keywords": ["테슬라 실적", "테슬라 에너지 사업", "테슬라 판매량"]},
    ],
    2: [
        {"type": "trade",    "label": "글로벌무역", "color": "#EF7D2E",
         "title": "중국 전기차 수출 통계 발표 (월별)",
         "memo": "BYD 등 중국 전기차·태양광 수출 추세 — 미중 통상 갈등 소재",
         "keywords": ["중국 전기차 수출", "BYD 수출 통계", "중국 태양광 수출"]},
        {"type": "event",    "label": "빅이벤트",  "color": "#EF7D2E",
         "title": "설 연휴 성수품 물가 (2월)",
         "memo": "차례상 물가 = 기후플레이션 체감 지표 — 과일·수산물 가격과 이상기후 연결",
         "keywords": ["설 성수품 물가", "차례상 물가", "설 과일 가격"]},
        {"type": "macro",    "label": "거시·실적", "color": "#EF7D2E",
         "title": "엔비디아 실적 (2월 말)",
         "memo": "AI 투자 사이클 가늠자 — 데이터센터 전력 수요·냉각·전력주 연동",
         "keywords": ["엔비디아 실적", "AI 데이터센터 전력", "엔비디아 전망"]},
        {"type": "macro",    "label": "거시·실적", "color": "#EF7D2E",
         "title": "MWC (2월 말, 바르셀로나)",
         "memo": "통신·디바이스 AI 경쟁 — 엣지 AI 전력 효율·배터리 기술 소재",
         "keywords": ["MWC AI", "MWC 배터리", "MWC 에너지 효율"]},
    ],
    3: [
        {"type": "policy",   "label": "정책·국제", "color": "#EF7D2E",
         "title": "한국 기업 ESG 공시 마감",
         "memo": "전년도 사업보고서·ESG 보고서 공시 — 그린워싱 팩트체크 최적 시기",
         "keywords": ["ESG 공시", "사업보고서 ESG", "그린워싱 공시 마감"]},
        {"type": "weather",  "label": "계절기상",  "color": "#EF7D2E",
         "title": "봄 산불 시즌 시작 (3~4월)",
         "memo": "건조기+강풍 — 산불 피해·대응 예산·산림 탄소 흡수 아이템",
         "keywords": ["봄 산불", "산불 피해 통계", "산불 진화 예산"]},
        {"type": "trade",    "label": "글로벌무역", "color": "#EF7D2E",
         "title": "한국 전기차·배터리 전시회 시즌",
         "memo": "국내 배터리·전기차 신제품·투자 발표 집중 시기",
         "keywords": ["배터리 전시회", "전기차 전시회", "배터리 엑스포"]},
        {"type": "event",    "label": "빅이벤트",  "color": "#EF7D2E",
         "title": "벚꽃 개화 (3월 말~4월 초)",
         "memo": "개화 시기 변화 자체가 기후 데이터 — 지역 축제·관광 경제와 연결",
         "keywords": ["벚꽃 개화 시기", "벚꽃 축제 기후", "개화 평년 비교"]},
        {"type": "macro",    "label": "거시·실적", "color": "#EF7D2E",
         "title": "중국 양회 (3월 초)",
         "memo": "중국 연간 에너지·산업 정책 청사진 — '신삼양'·탄소 목표·전기차 보조금 (히트작 패턴)",
         "keywords": ["중국 양회 에너지", "양회 탄소중립", "양회 신질생산력"]},
        {"type": "macro",    "label": "거시·실적", "color": "#EF7D2E",
         "title": "FOMC 금리 결정 (3월 중순)",
         "memo": "점도표 발표 회의 — 금리 경로와 에너지 인프라·그린본드 자금 흐름",
         "keywords": ["FOMC 점도표", "금리 인하 전망", "연준 3월"]},
        {"type": "macro",    "label": "거시·실적", "color": "#EF7D2E",
         "title": "12월 결산법인 주총 시즌 (3월)",
         "memo": "기후 관련 주주제안·이사회 ESG 안건 — 국민연금 의결권 행사 체크",
         "keywords": ["주총 기후 주주제안", "국민연금 의결권", "주주총회 ESG"]},
    ],
    4: [
        {"type": "policy",   "label": "정책·국제", "color": "#EF7D2E",
         "title": "지구의 날 (4월 22일)",
         "memo": "기후 여론·캠페인 점검 — 기업 ESG 발표 집중, 그린워싱 감시",
         "keywords": ["지구의날 캠페인", "Earth Day 기업", "환경의날 ESG"]},
        {"type": "earnings", "label": "기업실적",  "color": "#EF7D2E",
         "title": "배터리 3사·완성차·한전·포스코 1Q 실적 (4월 말)",
         "memo": "1분기 어닝시즌 — 전기차 캐즘 지속 여부·재생에너지 투자 변화",
         "keywords": ["LG에너지솔루션 1분기", "현대차 1분기", "한전 1분기 실적"]},
        {"type": "weather",  "label": "계절기상",  "color": "#EF7D2E",
         "title": "봄 산불 시즌 피크 (3~4월)",
         "memo": "산불 경제 피해·보험 손실·산림 탄소 흡수 차질 분석",
         "keywords": ["산불 경제 피해", "산불 보험", "산림 탄소"]},
        {"type": "policy",   "label": "정책·국제", "color": "#EF7D2E",
         "title": "UNFCCC 기후주간 (한국 여수, 4월 20~25일)",
         "memo": "아태지역 COP 사전 협상 — 한국 개최, 1000여 명 기후 전문가 집결",
         "keywords": ["UNFCCC 기후주간 여수", "기후주간 아태", "K-GX 녹색전환"]},
        {"type": "macro",    "label": "거시·실적", "color": "#EF7D2E",
         "title": "IMF 세계경제전망 (4월 중순)",
         "memo": "글로벌 성장률 전망 — 에너지 가격·기후 리스크 반영 여부 체크",
         "keywords": ["IMF 세계경제전망", "IMF 성장률", "IMF 에너지 전망"]},
        {"type": "macro",    "label": "거시·실적", "color": "#EF7D2E",
         "title": "테슬라 1Q 실적·FOMC (4월 말)",
         "memo": "EV 수요 + 금리 더블 체크 주간 — 전기차·에너지주 변동성 확대",
         "keywords": ["테슬라 1분기 실적", "FOMC 4월", "전기차 수요 전망"]},
    ],
    5: [
        {"type": "policy",   "label": "정책·국제", "color": "#EF7D2E",
         "title": "IEA 세계 에너지 전망 업데이트",
         "memo": "재생에너지 투자 흐름·각국 에너지 전환 속도 비교 — 한국 대비 소재",
         "keywords": ["IEA 에너지 전망", "세계 에너지 보고서", "재생에너지 투자 전망"]},
        {"type": "weather",  "label": "계절기상",  "color": "#EF7D2E",
         "title": "초여름 전력 수요 예보 발표",
         "memo": "여름 전력 대란 예측 아이템 — 냉방 수요·신규 발전 용량 분석",
         "keywords": ["여름 전력 수요", "전력 대란 예측", "전력 수급 전망"]},
        {"type": "macro",    "label": "거시·실적", "color": "#EF7D2E",
         "title": "엔비디아 실적 (5월 말)",
         "memo": "AI 사이클 중간 점검 — 데이터센터 증설 속도와 전력 수요 전망 갱신",
         "keywords": ["엔비디아 실적", "데이터센터 증설", "AI 전력 수요"]},
    ],
    6: [
        {"type": "policy",   "label": "정책·국제", "color": "#EF7D2E",
         "title": "한국 NDC 이행 점검",
         "memo": "국가온실가스감축목표 진행 현황 — 목표 대비 실제 감축량 팩트체크",
         "keywords": ["NDC 이행 현황", "온실가스 감축 실적", "탄소중립 목표 점검"]},
        {"type": "policy",   "label": "정책·국제", "color": "#EF7D2E",
         "title": "유엔 해양 총회",
         "memo": "해양 기후·수산업·해양 탄소흡수 소재 — 해상풍력 정책과 연동",
         "keywords": ["유엔 해양총회", "해양 기후변화", "수산업 기후"]},
        {"type": "weather",  "label": "계절기상",  "color": "#EF7D2E",
         "title": "장마 시작·집중호우 시즌 (6~7월)",
         "memo": "기후플레이션 연동 — 채소·과일 가격 급등 소재, 홍수 경제 피해",
         "keywords": ["장마 시작", "집중호우 채소 가격", "장마 기후플레이션"]},
        {"type": "policy",   "label": "정책·국제", "color": "#EF7D2E",
         "title": "G7 정상회의 (프랑스 에비앙, 6월 15~17일)",
         "memo": "기후재원·핵심광물·에너지 안보 의제 포함 — 프랑스 의장국, 한국 초청국",
         "keywords": ["G7 에비앙 기후", "G7 에너지 안보", "G7 핵심광물"]},
        {"type": "event",    "label": "빅이벤트",  "color": "#EF7D2E",
         "title": "북중미 월드컵 (6/11~7/19)",
         "memo": "폭염 속 경기·열사병 위험·역대 최대 탄소배출 — 화제성 1위 이벤트의 기후 각",
         "keywords": ["월드컵 폭염", "월드컵 탄소배출", "월드컵 기후"]},
        {"type": "macro",    "label": "거시·실적", "color": "#EF7D2E",
         "title": "FOMC 금리 결정·점도표 (6월 중순)",
         "memo": "상반기 금리 경로 확정 — 에너지 인프라·리츠·전력주 자금 흐름 변곡점",
         "keywords": ["FOMC 6월", "금리 점도표", "금리 에너지 투자"]},
        {"type": "macro",    "label": "거시·실적", "color": "#EF7D2E",
         "title": "하계 다보스 (WEF 톈진, 6~7월)",
         "memo": "중국 주최 글로벌 경제 포럼 — 에너지 전환·신산업 의제 비중 체크",
         "keywords": ["하계 다보스", "WEF 톈진", "다보스 에너지 전환"]},
    ],
    7: [
        {"type": "earnings", "label": "기업실적",  "color": "#EF7D2E",
         "title": "배터리 3사·완성차·한전·포스코 2Q 실적 (7월 말)",
         "memo": "2분기 어닝시즌 — 폭염 냉방 수요·전기차 여름 판매 동향",
         "keywords": ["LG에너지솔루션 2분기", "현대차 2분기", "한전 2분기 실적"]},
        {"type": "weather",  "label": "계절기상",  "color": "#EF7D2E",
         "title": "폭염 피크 시즌 (7~8월)",
         "memo": "온열질환·노동자 안전·냉방 전력 폭증·농작물 피해 — 기후경제 핵심 소재",
         "keywords": ["폭염 피해", "온열질환", "폭염 전력 수요", "폭염 작물"]},
        {"type": "weather",  "label": "계절기상",  "color": "#EF7D2E",
         "title": "장마·집중호우 마무리 (6~7월)",
         "memo": "장마 피해 규모 집계 — 보험사 손실·농업 피해·기후플레이션 연동",
         "keywords": ["장마 피해 집계", "집중호우 피해", "장마 보험 손실"]},
        {"type": "event",    "label": "빅이벤트",  "color": "#EF7D2E",
         "title": "월드컵 결승 + 여름 휴가철 시작 (7월)",
         "memo": "월드컵 기후 결산 + 휴가철 항공·여행 탄소, 폭염 관광지 변화",
         "keywords": ["월드컵 결승", "휴가철 항공 탄소", "폭염 여행지"]},
        {"type": "macro",    "label": "거시·실적", "color": "#EF7D2E",
         "title": "세법개정안 발표 (7월 말)",
         "memo": "에너지 세제·전기차 개소세·탄소 관련 세제 변화 — 소비자 체감 아이템",
         "keywords": ["세법개정안 에너지", "전기차 개소세", "세법개정 친환경"]},
        {"type": "macro",    "label": "거시·실적", "color": "#EF7D2E",
         "title": "FOMC·테슬라 2Q 실적 (7월 말)",
         "memo": "금리 + EV 수요 동시 체크 — 하반기 에너지·전기차 투자 방향",
         "keywords": ["FOMC 7월", "테슬라 2분기", "전기차 하반기 전망"]},
    ],
    8: [
        {"type": "weather",  "label": "계절기상",  "color": "#EF7D2E",
         "title": "폭염 피크 지속 (7~8월)",
         "memo": "누적 폭염 경제 손실 분석 — 에너지 수요·작물 피해 중간 결산",
         "keywords": ["폭염 누적 피해", "폭염 경제 손실", "여름 에너지 소비"]},
        {"type": "weather",  "label": "계절기상",  "color": "#EF7D2E",
         "title": "태풍 시즌 (8~9월)",
         "memo": "한반도 태풍 영향·보험 손실·농업 피해·인프라 복구 비용",
         "keywords": ["태풍 피해", "태풍 농업 피해", "태풍 보험 손실"]},
        {"type": "event",    "label": "빅이벤트",  "color": "#EF7D2E",
         "title": "여름 휴가철 피크 (8월)",
         "memo": "해외여행 항공 탄소·국내 피서지 폭염·해수욕장 수온 — 생활 밀착 기후 소재",
         "keywords": ["휴가철 폭염", "해수욕장 수온", "항공 여행 탄소"]},
        {"type": "macro",    "label": "거시·실적", "color": "#EF7D2E",
         "title": "잭슨홀 미팅 (8월 말)",
         "memo": "연준 의장 기조연설 — 금리 사이클 전환 신호와 에너지 전환 금융 비용",
         "keywords": ["잭슨홀 미팅", "연준 의장 연설", "잭슨홀 금리"]},
        {"type": "macro",    "label": "거시·실적", "color": "#EF7D2E",
         "title": "엔비디아 실적 (8월 말)",
         "memo": "AI 사이클 하반기 점검 — 데이터센터·전력 인프라 투자 지속 여부",
         "keywords": ["엔비디아 실적", "AI 투자 사이클", "데이터센터 전력"]},
    ],
    9: [
        {"type": "policy",   "label": "정책·국제", "color": "#EF7D2E",
         "title": "유엔 기후 정상회의 (UNGA)",
         "memo": "세계 기후 정치 동향 — 각국 NDC 갱신·기후 재원 협상 핵심 소재",
         "keywords": ["유엔 기후 정상회의", "UNGA 기후", "기후 정상회담 합의"]},
        {"type": "korea_politics","label": "한국정치","color": "#EF7D2E",
         "title": "정부 예산안 발표",
         "memo": "기후·에너지 예산 항목 분석 — 재생에너지 vs 원전 예산 비교",
         "keywords": ["기후 예산안", "에너지 예산", "재생에너지 예산"]},
        {"type": "trade",    "label": "글로벌무역", "color": "#EF7D2E",
         "title": "유럽 자동차 전시회 (9~10월)",
         "memo": "유럽 전기차 신모델·EU 정책 연동 — 한국 완성차 대응 전략 소재",
         "keywords": ["유럽 자동차 전시회", "파리 모터쇼", "전기차 신모델 유럽"]},
        {"type": "weather",  "label": "계절기상",  "color": "#EF7D2E",
         "title": "가을 수확기·태풍 시즌 (9~11월)",
         "memo": "이상기후 작물 수급 불안정 — 쌀·배추·과일 가격 상승 소재",
         "keywords": ["가을 수확 이상기후", "쌀 수급", "배추 가격 기상"]},
        {"type": "event",    "label": "빅이벤트",  "color": "#EF7D2E",
         "title": "추석 성수품 물가 (9월)",
         "memo": "차례상 기후플레이션 — 사과·배·수산물 가격과 여름 이상기후 직결",
         "keywords": ["추석 성수품 물가", "추석 과일 가격", "차례상 물가"]},
        {"type": "macro",    "label": "거시·실적", "color": "#EF7D2E",
         "title": "FOMC 금리 결정·점도표 (9월 중순)",
         "memo": "하반기 금리 향방 — 재생에너지 프로젝트 파이낸싱·그린본드 발행 연동",
         "keywords": ["FOMC 9월", "금리 인하", "그린본드 금리"]},
    ],
    10: [
        {"type": "earnings", "label": "기업실적",  "color": "#EF7D2E",
         "title": "배터리 3사·완성차·한전·포스코 3Q 실적 (10월 말)",
         "memo": "3분기 어닝시즌 — 연간 전기차 판매 목표 달성 여부 중간 점검",
         "keywords": ["LG에너지솔루션 3분기", "현대차 3분기", "한전 3분기 실적"]},
        {"type": "trade",    "label": "글로벌무역", "color": "#EF7D2E",
         "title": "유럽 자동차 전시회 (9~10월)",
         "memo": "전기차 신모델·EU 탄소 규제 연동 — 완성차 전동화 전략 업데이트",
         "keywords": ["자동차 전시회 전기차", "EU 탄소 규제", "전기차 유럽 판매"]},
        {"type": "weather",  "label": "계절기상",  "color": "#EF7D2E",
         "title": "가을 수확기 (9~11월)",
         "memo": "쌀·배추·사과 수급 현황 — 연간 기상이변 농업 피해 중간 집계",
         "keywords": ["쌀 수확량", "배추 가격 10월", "농작물 이상기후 피해"]},
        {"type": "macro",    "label": "거시·실적", "color": "#EF7D2E",
         "title": "국정감사 (10월)",
         "memo": "기후에너지환경부·산업부 국감 — 에너지 정책 쟁점·여야 공방 총정리 소재",
         "keywords": ["국정감사 에너지", "기후에너지환경부 국감", "산업부 국감"]},
        {"type": "macro",    "label": "거시·실적", "color": "#EF7D2E",
         "title": "IEA 세계에너지전망 WEO (10월)",
         "memo": "연간 최대 에너지 보고서 — 글로벌 전환 속도·한국 위치 팩트체크",
         "keywords": ["IEA WEO", "세계에너지전망", "IEA 재생에너지"]},
        {"type": "macro",    "label": "거시·실적", "color": "#EF7D2E",
         "title": "IMF·WB 연차총회 / 테슬라 3Q / FOMC (10월 말)",
         "memo": "거시 이벤트 집중 구간 — 기후 재원·EV 수요·금리 한꺼번에 점검",
         "keywords": ["IMF 연차총회 기후", "테슬라 3분기", "FOMC 10월"]},
    ],
    11: [
        {"type": "policy",   "label": "정책·국제", "color": "#EF7D2E",
         "title": "COP31 (터키 안탈리아, 11월 9~20일)",
         "memo": "연중 최대 기후 이벤트 — 터키·호주 공동의장, 각국 NDC 협상·탄소시장 규칙",
         "keywords": ["COP31 안탈리아", "COP31 기후협상", "COP31 탄소시장"]},
        {"type": "korea_politics","label": "한국정치","color": "#EF7D2E",
         "title": "국회 예산 심의 (11~12월)",
         "memo": "기후·에너지 예산 삭감·증액 팩트체크 — 정치 지형과 기후 정책 연동",
         "keywords": ["국회 예산 심의", "기후 예산 삭감", "에너지 예산 국회"]},
        {"type": "weather",  "label": "계절기상",  "color": "#EF7D2E",
         "title": "첫 한파·대설 (11~12월)",
         "memo": "에너지 수요 급등·난방비·LNG 수급 위기 — 서민 에너지 취약계층 소재",
         "keywords": ["첫 한파", "난방비 급등", "LNG 수급 겨울"]},
        {"type": "event",    "label": "빅이벤트",  "color": "#EF7D2E",
         "title": "김장철·수능 시즌 (11월)",
         "memo": "배추·고춧가루 김장 물가 + 수능 한파 — 계절 생활 기후 소재",
         "keywords": ["김장 물가 배추", "김장철 가격", "수능 한파"]},
        {"type": "event",    "label": "빅이벤트",  "color": "#EF7D2E",
         "title": "블랙프라이데이·광군제 (11월)",
         "memo": "소비 빅이벤트의 택배·물류 탄소, 패스트패션 반품 폐기물",
         "keywords": ["블랙프라이데이 소비", "광군제 물류", "택배 탄소 배출"]},
        {"type": "macro",    "label": "거시·실적", "color": "#EF7D2E",
         "title": "미국 중간선거 (2026년 11월 3일)",
         "memo": "IRA·기후 정책 향방 가르는 선거 — 의회 구도 변화와 한국 기업 영향",
         "keywords": ["미국 중간선거 기후", "중간선거 IRA", "미국 의회 에너지"]},
        {"type": "macro",    "label": "거시·실적", "color": "#EF7D2E",
         "title": "엔비디아 실적 (11월 말)",
         "memo": "AI 투자 사이클 연말 점검 — 내년 데이터센터·전력 수요 전망",
         "keywords": ["엔비디아 실적", "AI 전망", "데이터센터 내년"]},
    ],
    12: [
        {"type": "policy",   "label": "정책·국제", "color": "#EF7D2E",
         "title": "COP 기후총회 최종 합의 (11~12월)",
         "memo": "최종 합의문 분석·한국 협상 결과 팩트체크 — 내년 기후 정책 방향",
         "keywords": ["COP 합의문", "기후총회 결과", "탄소감축 합의 분석"]},
        {"type": "policy",   "label": "정책·국제", "color": "#EF7D2E",
         "title": "탄소배출권 연간 결산",
         "memo": "배출권 가격 변동·기업 실적 연동 — 연간 온실가스 배출 현황",
         "keywords": ["탄소배출권 연말", "배출권 가격 연간", "온실가스 배출 통계"]},
        {"type": "korea_politics","label": "한국정치","color": "#EF7D2E",
         "title": "국회 예산 최종 확정 (11~12월)",
         "memo": "기후·에너지 예산 최종 확정 — 내년도 재생에너지·탄소중립 정책 방향",
         "keywords": ["예산 최종 확정", "기후 예산 내년", "재생에너지 예산 확정"]},
        {"type": "weather",  "label": "계절기상",  "color": "#EF7D2E",
         "title": "한파·대설 시즌 (11~12월)",
         "memo": "에너지 수요 급등·LNG 가격·난방비 — 에너지 취약계층 정책 소재",
         "keywords": ["한파 에너지 수요", "난방비 상승", "LNG 가격 겨울"]},
        {"type": "policy",   "label": "정책·국제", "color": "#EF7D2E",
         "title": "G20 정상회의 (미국 도랄, 12월 14~15일)",
         "memo": "트럼프 주최 G20 — 기후 의제 후퇴 여부 팩트체크 소재",
         "keywords": ["G20 도랄 기후", "G20 에너지 정책", "트럼프 G20 기후"]},
        {"type": "macro",    "label": "거시·실적", "color": "#EF7D2E",
         "title": "FOMC 금리 결정·내년 점도표 (12월 초)",
         "memo": "내년 금리 경로 제시 — 에너지 전환 투자 환경 연간 결산 소재",
         "keywords": ["FOMC 12월", "내년 금리 전망", "연준 점도표"]},
    ],
}

YEAR_ROUND = [
    {"type": "trade", "label": "글로벌무역", "color": "#EF7D2E",
     "title": "미국 IRA 보조금 집행 현황 (분기별 업데이트)",
     "memo": "IRA 수혜 기업·한국 진출 현황 분기 추적 — 미국 에너지 산업 정책 변화",
     "keywords": ["IRA 보조금 집행", "IRA 수혜 한국 기업", "미국 전기차 보조금 IRA"]},
    {"type": "trade", "label": "글로벌무역", "color": "#EF7D2E",
     "title": "중국 전기차·태양광 수출 통계 (월별)",
     "memo": "BYD 수출 동향·중국 태양광 글로벌 점유율 — 미중 무역 갈등 소재",
     "keywords": ["중국 전기차 수출 통계", "BYD 글로벌 판매", "중국 태양광 수출"]},
    {"type": "macro", "label": "거시·실적", "color": "#EF7D2E",
     "title": "한국은행 금통위 기준금리 (연 8회: 1·2·4·5·7·8·10·11월)",
     "memo": "금리 = 재생에너지·인프라 프로젝트 수익성 변수 — 발표 직후 에너지주 반응 체크",
     "keywords": ["금통위 기준금리", "한은 금리 결정", "기준금리 전망"]},
    {"type": "macro", "label": "거시·실적", "color": "#EF7D2E",
     "title": "미국 CPI·소비자물가 발표 (매월 중순)",
     "memo": "에너지 가격의 물가 기여도 — 기후플레이션 정량 근거로 활용",
     "keywords": ["미국 CPI", "소비자물가 에너지", "기후플레이션 물가"]},
    {"type": "macro", "label": "거시·실적", "color": "#EF7D2E",
     "title": "한전 연료비 조정단가 발표 (3·6·9·12월 분기말)",
     "memo": "전기요금 방향 예고 지표 — 국제 에너지 가격과 요금 정책 연결 소재",
     "keywords": ["연료비 조정단가", "전기요금 분기", "한전 요금 발표"]},
    {"type": "macro", "label": "거시·실적", "color": "#EF7D2E",
     "title": "삼성전자·SK하이닉스 분기 실적 (1·4·7·10월)",
     "memo": "반도체 사이클 = 데이터센터·전력 수요 선행 지표 — RE100 이행 현황 체크",
     "keywords": ["삼성전자 실적", "SK하이닉스 실적", "반도체 전력 수요"]},
]

MONTH_NAMES = ["1월", "2월", "3월", "4월", "5월", "6월",
               "7월", "8월", "9월", "10월", "11월", "12월"]

# ── 기후 데드라인 뉴스 키워드 ─────────────────────────────────
CALENDAR_NEWS_KEYWORDS = [
    # 시행·기한
    "수도권 직매립 금지 시행",
    "CBAM 탄소국경세 의무화",
    "NDC 감축 목표 기한",
    "ESG 공시 의무화 시행",
    "탄소중립법 개정 기한",
    # 개최 예정
    "UNFCCC 기후주간 여수",
    "COP31 안탈리아",
    "G7 에비앙 기후",
    "G20 도랄 기후",
    # 거시경제 빅 이벤트
    "FOMC 금리 결정",
    "금통위 기준금리",
    "연료비 조정단가",
    "국정감사 에너지",
]


# ─────────────────────────────────────────────────────────────
# RSS 유틸리티
# ─────────────────────────────────────────────────────────────
UNKNOWN_DT = datetime.min.replace(tzinfo=timezone.utc)
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}


def fetch_url(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers=HTTP_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as e:
        print(f"  [WARN] {url[:70]}  →  {e}", file=sys.stderr)
        return None


def _clean_tag(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    return html_lib.unescape(text).strip()


def parse_date(date_str):
    if not date_str:
        return UNKNOWN_DT
    try:
        return parsedate_to_datetime(date_str.strip())
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S",
                "%a, %d %b %Y %H:%M:%S %z"):
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
        except Exception:
            pass
    return UNKNOWN_DT


def format_date(dt):
    if dt == UNKNOWN_DT:
        return "날짜 미상"
    try:
        kst_dt = dt.astimezone(KST)
        diff = datetime.now(KST) - kst_dt
        secs = diff.total_seconds()
        if secs < 0:
            return kst_dt.strftime("%m/%d %H:%M")
        if secs < 3600:
            return f"{int(secs // 60)}분 전"
        if secs < 86400:
            return f"{int(secs // 3600)}시간 전"
        return kst_dt.strftime("%m/%d %H:%M")
    except Exception:
        return "날짜 미상"


def parse_rss(data):
    """RSS XML → [{title, link, pub_dt, pub_str, source}]"""
    if not data:
        return []
    try:
        if data[:3] == b"\xef\xbb\xbf":
            data = data[3:]
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]",
                      "", data.decode("utf-8", errors="replace"))
        root = ET.fromstring(text.encode("utf-8"))
    except ET.ParseError as e:
        print(f"  [WARN] XML 파싱: {e}", file=sys.stderr)
        return []

    items = []
    for item in root.findall(".//item"):
        title_el = item.find("title")
        link_el  = item.find("link")
        orig_el  = item.find("originallink")  # 네이버 전용
        pub_el   = item.find("pubDate")
        src_el   = item.find("source")

        title  = _clean_tag(title_el.text if title_el is not None else "")
        link   = (orig_el.text or "").strip() if orig_el is not None and orig_el.text else ""
        if not link:
            link = (link_el.text or "").strip() if link_el is not None else ""
        pub_str = (pub_el.text or "").strip() if pub_el is not None else ""
        source  = _clean_tag(src_el.text if src_el is not None else "")

        # " - 언론사명" 패턴을 제목에서 항상 제거 (Google News / 일부 피드)
        if " - " in title:
            parts = title.rsplit(" - ", 1)
            title = parts[0].strip()
            if not source:
                source = parts[1].strip()

        # "… > 뉴스" 같은 사이트 내비게이션 꼬리 제거
        title = re.sub(r"\s*>\s*뉴스$", "", title)

        # 포털 소스명 보정 — 단, 섹션 표기([포토로그] 등)는 언론사명이 아님
        if not source or source in PORTAL_SOURCES:
            m = re.search(r'[\[\(]([^\]\)]{2,15})[\]\)]\s*$', title)
            if m and m.group(1) not in NOT_PRESS_TOKENS:
                source = m.group(1)
                title = re.sub(r'\s*[\[\(][^\]\)]{2,15}[\]\)]\s*$', '', title).strip()

        if source in PORTAL_SOURCES or source in NOT_PRESS_TOKENS:
            source = ""

        # 양끝 장식용 특수문자 제거 (":: 위즈경제 ::" → "위즈경제")
        if source:
            source = SRC_DECOR_RE.sub("", source)

        for key, pretty in SOURCE_RENAME.items():
            if key in source.lower():
                source = pretty
                break

        # 칼럼·코너명을 매체명으로 오인한 경우 버림 ("오승혁의 '현장'" 등)
        # SOURCE_RENAME으로 매체명이 확정된 건은 위에서 이미 교정되어 통과
        if source and COLUMN_NAME_RE.search(source):
            source = ""

        pub_dt = parse_date(pub_str)

        if title and link:
            items.append({
                "title":   title,
                "link":    link,
                "pub_dt":  pub_dt,
                "pub_str": format_date(pub_dt),
                "source":  source,
            })
    return items


def resolve_gnews_url(link):
    """Google News 리다이렉트 링크 → 원문 URL (batchexecute 디코딩)"""
    if "news.google.com" not in link:
        return link
    try:
        page = fetch_url(link)
        if not page:
            return link
        m = re.search(rb'<c-wiz[^>]*data-p="([^"]+)"', page)
        if not m:
            return link
        import json as _json
        data_p = m.group(1).decode().replace("&quot;", '"').replace("&amp;", "&")
        obj = _json.loads(data_p.replace("%.@.", '["garturlreq",'))
        payload = urllib.parse.urlencode({
            "f.req": _json.dumps(
                [[["Fbv4je", _json.dumps(obj[:-6] + obj[-2:]), None, "generic"]]])
        }).encode()
        req = urllib.request.Request(
            "https://news.google.com/_/DotsSplashUi/data/batchexecute",
            data=payload,
            headers={**HTTP_HEADERS,
                     "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", "replace")
        m2 = re.search(r'https?://[^"\\]+', _json.loads(body.splitlines()[2])[0][2])
        return m2.group(0) if m2 else link
    except Exception:
        return link


PORTAL_SITE_NAMES = {
    "네이트 뉴스", "네이트", "다음뉴스", "다음 뉴스", "Daum", "다음",
    "네이버 뉴스", "naver",
}


def page_press_name(url):
    """기사 페이지에서 원문 언론사명 추출
    (네이트 medium 링크 → og:article:author → og:site_name 순)"""
    url = url.replace("m.news.nate.com", "news.nate.com")
    try:
        page = fetch_url(url)
        if not page:
            return ""
        try:
            text = page.decode("utf-8")
        except UnicodeDecodeError:
            text = page.decode("euc-kr", "replace")
        for pat in (r'<a [^>]*class="medium"[^>]*>([^<]+)</a>',
                    r'"provider"\s*:\s*\[?\s*\{[^}]*?"name"\s*:\s*"([^"]+)"',
                    r'"sourceName"\s*:\s*"([^"]+)"',
                    r'<meta property="og:article:author" content="([^"]+)"',
                    r'<meta property="og:site_name" content="([^"]+)"'):
            m = re.search(pat, text)
            if m:
                name = m.group(1).strip()
                if name and name not in PORTAL_SITE_NAMES:
                    return name
        return ""
    except Exception:
        return ""


def enrich_sources(items):
    """출처 보정: 구글 리다이렉트를 풀어 원문 URL로 바꾸고,
    네이트·MSN 등 집계 사이트는 원문 언론사명을 추출해 채운다"""
    for item in items:
        src = item.get("source") or ""
        if src and src not in AGGREGATOR_SOURCES:
            continue
        real = resolve_gnews_url(item["link"])
        if real != item["link"]:
            item["link"] = real
        host = (urllib.parse.urlparse(real).hostname or "").lower()
        if any(p in host for p in ("nate.com", "daum.net", "msn.com")):
            press = page_press_name(real)
            if press:
                item["source"] = press
            continue
        domain = (host.removeprefix("www.").removesuffix(".com")
                  .removesuffix(".co.kr").removesuffix(".kr"))
        renamed = next((pretty for key, pretty in SOURCE_RENAME.items()
                        if key in host), None)
        if renamed:
            item["source"] = renamed
        elif domain and not any(p in domain for p in ("google", "nate", "daum", "msn")):
            item["source"] = domain
    return items


def google_rss_url(keyword):
    return f"https://news.google.com/rss/search?q={urllib.parse.quote(keyword)}+when:3d&hl=ko&gl=KR&ceid=KR:ko"

def google_rss_en_url(keyword):
    return f"https://news.google.com/rss/search?q={urllib.parse.quote(keyword)}&hl=en&gl=US&ceid=US:en"


def extract_nouns(title):
    tokens = re.findall(r'[A-Za-z0-9]+|[가-힣]{2,}', title)
    stopwords = {
        "관련","대한","위한","통한","따른","있는","하는","으로",
        "에서","부터","까지","이후","이전","대해","통해"
    }
    return set(t for t in tokens if t not in stopwords)

def jaccard(set_a, set_b):
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)

def is_same_story(nouns, kept_nouns):
    """같은 사건 보도 판정: 자카드 0.5+ 또는 공유 명사 3개+"""
    return any(jaccard(nouns, kn) >= 0.5 or len(nouns & kn) >= 3
               for kn in kept_nouns)


def deduplicate(items):
    seen_urls = set()
    kept = []
    kept_nouns = []
    for item in items:
        url = item["link"]
        if url in seen_urls:
            continue
        nouns = extract_nouns(item["title"])
        if is_same_story(nouns, kept_nouns):
            continue
        seen_urls.add(url)
        kept.append(item)
        kept_nouns.append(nouns)
    return kept


def dedupe_across_categories(categories_data):
    """카테고리 간 중복 기사 제거 — 먼저 나온 카테고리에만 남김 (페이지 다이어트)"""
    seen_urls = set()
    seen_nouns = []
    removed = 0
    for cat in categories_data:
        kept = []
        for item in cat["items"]:
            nouns = extract_nouns(item["title"])
            if item["link"] in seen_urls or is_same_story(nouns, seen_nouns):
                removed += 1
                continue
            seen_urls.add(item["link"])
            seen_nouns.append(nouns)
            kept.append(item)
        cat["items"] = kept
    return removed


# ─────────────────────────────────────────────────────────────
# 필터 함수
# ─────────────────────────────────────────────────────────────
def is_excluded(item):
    """홍보성·행사성 기사 필터 + 해외 스팸 도메인 차단"""
    title  = item.get("title",  "") or ""
    source = item.get("source", "") or ""
    if any(p in title  for p in EXCLUDE_TITLE_PATTERNS):
        return True
    if any(p in source for p in EXCLUDE_SOURCE_PATTERNS):
        return True
    # 해외 도메인 차단 (소스명·링크 host 양쪽)
    if re.search(r"\.(vn|ru|il|cn|id)\b", source, re.I):
        return True
    host = (urllib.parse.urlparse(item.get("link", "")).hostname or "").lower()
    if host.endswith(BLOCKED_TLDS):
        return True
    return False


def is_expert_excluded(item):
    """전문가 탭 추가 필터 (사진·행사 기사, 프로그램 자체 홍보)"""
    title = item.get("title", "") or ""
    if any(p in title for p in EXPERT_EXCLUDE_PATTERNS):
        return True
    if "기후로운 경제생활" in title:
        return True
    return False


# ─────────────────────────────────────────────────────────────
# 아이템성 스코어
# ─────────────────────────────────────────────────────────────
def item_score(title, life_mode=False):
    """제목 기반 발제 가능성 점수 (과거 조회수 상관 신호 + 프로그램 결 신호)
    life_mode: 생활·소비 카테고리용 — 기업·돈 보너스 없이 생활 연결 위주 평가"""
    s = 0
    has_company = any(c in title for c in SCORE_COMPANIES)
    if any(k in title for k in LIFE_ANGLE_TERMS):
        s += 3
    if any(k in title for k in FEATURE_TERMS):
        s += 2
    # 거시·지정학 빅이슈 + 에너지 안보 신호는 모드 무관하게 강하게 가산
    if any(k in title for k in BIG_ISSUE_TERMS):
        s += 4
    if any(k in title for k in ENERGY_SEC_TERMS):
        s += 3
    if not life_mode:
        if has_company:
            s += 3
        if re.search(SCORE_NUM_RE, title):
            s += 2
        if any(k in title for k in SCORE_MONEY):
            s += 2
        if any(k in title for k in SCORE_TURNING):
            s += 1
    else:
        if re.search(SCORE_NUM_RE, title):
            s += 1
    has_weather = any(k in title for k in WEATHER_TERMS)
    has_econ    = has_company or any(k in title for k in ECON_LINK_TERMS)
    if has_weather and not has_econ:
        s -= 2
    if any(k in title for k in PROCEDURAL_TERMS):
        s -= 2
    if any(k in title for k in TICKER_NOISE_TERMS):
        # 시황성 기사: 수주·계약 같은 실질 뉴스가 같이 없으면 사실상 탈락점
        s -= 2 if any(k in title for k in SUBSTANTIVE_TERMS) else 5
    return s


def company_key(title):
    """제목에서 첫 번째로 매칭되는 기업명 (잠식 방지 캡용)"""
    return next((c for c in SCORE_COMPANIES if c in title), None)


def cap_by_company(items, max_per_company=2):
    """같은 기업이 리스트를 잠식하지 않도록 기업당 최대 N건"""
    counts = {}
    kept = []
    for item in items:
        key = company_key(item["title"])
        if key is not None:
            counts[key] = counts.get(key, 0) + 1
            if counts[key] > max_per_company:
                continue
        kept.append(item)
    return kept


_generic_topic_tokens = None


def topic_token_cap(items, max_n=2):
    """같은 희귀 토픽 단어(엘니뇨 등)가 한 리스트에 3번 이상 반복되지 않게 캡.
    카테고리 키워드에 들어 있는 일반 단어는 제외"""
    global _generic_topic_tokens
    if _generic_topic_tokens is None:
        s = set()
        for c in CATEGORIES:
            for kw in c["keywords"]:
                s.update(extract_nouns(kw))
        s.update({"시장", "투자", "산업", "기업", "정부", "한국", "미국",
                  "중국", "글로벌", "가격", "요금", "수주", "실적", "발표",
                  "세계", "국내", "최대", "규모", "전망", "올해", "내년"})
        _generic_topic_tokens = s
    counts = {}
    kept = []
    for item in items:
        nouns = [n for n in extract_nouns(item["title"])
                 if len(n) >= 3 and not n.isdigit()
                 and n not in _generic_topic_tokens]
        if any(counts.get(n, 0) >= max_n for n in nouns):
            continue
        for n in nouns:
            counts[n] = counts.get(n, 0) + 1
        kept.append(item)
    return kept


def is_weather_gated(item):
    """날씨 단독 기사 게이트 — 경제 연결어·기업명 없으면 제외
    (과거 데이터: 날씨 단독 아이템 25편 중 1만+ 조회 0편)"""
    title = item.get("title", "") or ""
    if not any(k in title for k in WEATHER_TERMS):
        return False
    return not (any(k in title for k in ECON_LINK_TERMS)
                or any(c in title for c in SCORE_COMPANIES))


# ─────────────────────────────────────────────────────────────
# 뉴스 수집
# ─────────────────────────────────────────────────────────────
def fetch_category(cat):
    """국내 카테고리: Google News 한국어 RSS
    날씨 단독 기사 게이트 → 아이템성 스코어 → (스코어, 최신성) 정렬 → quota"""
    print(f"  ▶ [국내] {cat['name']}", file=sys.stderr)
    all_items = []
    for kw in cat["keywords"]:
        all_items.extend(parse_rss(fetch_url(google_rss_url(kw))))
        time.sleep(REQUEST_DELAY)
    all_items = [i for i in all_items
                 if not is_excluded(i) and not is_weather_gated(i)]
    if cat["id"] == "wx":
        # 기상 카테고리는 제목에 기상·기후 용어가 있어야 통과 (지역 동정 차단)
        all_items = [i for i in all_items
                     if any(k in i["title"] for k in WX_REQUIRED_TERMS)]

    def source_score_ko(item):
        src = item.get("source") or ""
        preferred = any(ps in src for ps in PREFERRED_SOURCES_KO)
        bonus = timedelta(hours=1) if preferred else timedelta(0)
        dt = item["pub_dt"]
        if dt == UNKNOWN_DT:
            return datetime.min.replace(tzinfo=timezone.utc)
        return dt + bonus

    life_mode = cat.get("style") == "life"
    for item in all_items:
        item["score"] = item_score(item["title"], life_mode=life_mode)
        item["life_hit"] = any(k in item["title"] for k in LIFE_ANGLE_TERMS) \
                           or any(k in item["title"] for k in FEATURE_TERMS)

    all_items.sort(key=lambda i: (i["score"], source_score_ko(i)), reverse=True)
    quota = cat.get("quota", MAX_PER_CATEGORY)
    return topic_token_cap(cap_by_company(deduplicate(all_items)))[:quota]


def fetch_ko_media(max_total=20):
    """국내 기후 전문 매체 직접 구독 — 최근 3일, 생활 연결 모드 평가"""
    print("  ▶ [기후 전문 매체] 수집", file=sys.stderr)
    cutoff = datetime.now(timezone.utc) - timedelta(days=3)
    all_items = []
    for feed in KO_MEDIA_FEEDS:
        got = parse_rss(fetch_url(feed["url"]))
        for it in got:
            it["source"] = feed["source"]
        all_items.extend(got)
        time.sleep(REQUEST_DELAY)
    for q in KO_MEDIA_QUERIES:
        got = parse_rss(fetch_url(google_rss_url(q["query"])))
        all_items.extend(i for i in got if q["source"] in (i.get("source") or ""))
        time.sleep(REQUEST_DELAY)
    all_items = [i for i in all_items
                 if not is_excluded(i)
                 and i["pub_dt"] != UNKNOWN_DT and i["pub_dt"] >= cutoff]
    for it in all_items:
        it["score"] = item_score(it["title"], life_mode=True)
        it["life_hit"] = any(k in it["title"] for k in LIFE_ANGLE_TERMS) \
                         or any(k in it["title"] for k in FEATURE_TERMS)
    all_items.sort(key=lambda i: (i["score"], i["pub_dt"]), reverse=True)
    return cap_by_company(deduplicate(all_items))[:max_total]


BRIEFING_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "briefing.json")
BRIEFING_DATE = ""   # load 시 채워지는 브리핑 기준일(YYYY-MM-DD)


def fetch_econ_briefing(n=10):
    """오늘의 경제 브리핑 — briefing.json에서 로드 (API 비용 0원).
    Claude 구독으로 작성한 브리핑을 파일로 커밋해두면 빌드 때 읽어 렌더한다.
    파일 형식:
      {"date": "YYYY-MM-DD",
       "briefing": [{"headline": "", "summary": "", "kw": ""}, ...]}
    반환: [{headline, summary, kw}] — 없으면 []"""
    global BRIEFING_DATE
    try:
        with open(BRIEFING_FILE, encoding="utf-8") as f:
            data = json_lib.load(f)
    except FileNotFoundError:
        print("    [INFO] briefing.json 없음 → 브리핑 비움", file=sys.stderr)
        return []
    except Exception as e:
        print(f"    [WARN] briefing.json 읽기 실패: {e}", file=sys.stderr)
        return []
    BRIEFING_DATE = str(data.get("date", "")).strip()
    items = [b for b in data.get("briefing", []) if b.get("headline")][:n]
    today = datetime.now(KST).strftime("%Y-%m-%d")
    if BRIEFING_DATE and BRIEFING_DATE != today:
        print(f"    [INFO] 브리핑 기준일 {BRIEFING_DATE} ≠ 오늘 {today} — 갱신 권장",
              file=sys.stderr)
    print(f"    경제 브리핑 {len(items)}건 (기준일 {BRIEFING_DATE or '미상'})",
          file=sys.stderr)
    return items


def title_has_keyword(title, kw):
    """제목에 키워드가 '단어'로 등장하는지 — 앞 글자가 한글이면 조사 일부로 보고 제외"""
    for m in re.finditer(re.escape(kw), title):
        if m.start() == 0 or not re.match(r"[가-힣]", title[m.start() - 1]):
            return True
    return False


def fetch_surprise_climate(per_kw=1, max_total=12):
    """화제 × 기후 — 평소 기후와 안 엮이던 분야(스포츠·음식·생활·문화)가
    기후와 엮여 보도된 기사를 포착. SURPRISE_KEYWORDS × CLIMATE_WORDS 교차.
    예: '월드컵 폭염', '와인 기후위기', '쌀 기후위기', '프로축구 탄소'"""
    print("  ▶ [화제 × 기후] 의외 키워드 교차검색", file=sys.stderr)
    climate_or = " OR ".join(CLIMATE_WORDS[:8])
    out = []
    for kw in SURPRISE_KEYWORDS:
        got = parse_rss(fetch_url(google_rss_url(f"{kw} ({climate_or})")))
        kept = []
        for i in got:
            if is_excluded(i):
                continue
            # 키워드(단어 경계)와 기후 용어가 제목에 둘 다 있어야 진짜 '교차'
            if not title_has_keyword(i["title"], kw):
                continue
            if not any(c in i["title"] for c in CLIMATE_WORDS):
                continue
            # 연예·가십 기사 제외 (폭염이 관용구로 박힌 화보·공항패션 등)
            if any(g in i["title"] for g in GOSSIP_EXCLUDE):
                continue
            i["surprise_kw"] = kw
            i["score"] = item_score(i["title"])
            kept.append(i)
        kept.sort(key=lambda i: i["pub_dt"], reverse=True)
        out.extend(deduplicate(kept)[:per_kw])
        time.sleep(REQUEST_DELAY)
    out.sort(key=lambda i: i["pub_dt"], reverse=True)
    return deduplicate(out)[:max_total]


def fetch_calendar_news(max_total=15):
    """기후 데드라인·이벤트 관련 뉴스 클리핑"""
    print("  ▶ [캘린더 뉴스] 수집 중…", file=sys.stderr)
    all_items = []
    for kw in CALENDAR_NEWS_KEYWORDS:
        all_items.extend(parse_rss(fetch_url(google_rss_url(kw))))
        time.sleep(REQUEST_DELAY)
    all_items = [i for i in all_items if not is_excluded(i)]
    all_items.sort(key=lambda x: x["pub_dt"], reverse=True)
    return deduplicate(all_items)[:max_total]


def fetch_trusted_en_feeds(max_total=15):
    """기후 전문 매체 RSS 직접 구독 → 최신순 20건"""
    print("  ▶ [해외-L1] 기후 전문 매체 RSS 수집", file=sys.stderr)
    all_items = []
    for feed in TRUSTED_EN_FEEDS:
        data = fetch_url(feed["url"])
        if not data:
            print(f"    [WARN] 피드 응답 없음: {feed['url']}", file=sys.stderr)
            continue
        items = parse_rss(data)
        for item in items:
            if not item.get("source"):
                item["source"] = feed["source"]
        all_items.extend(items)
        time.sleep(REQUEST_DELAY)
    all_items = [i for i in all_items if not is_excluded(i)]
    all_items.sort(key=lambda x: x["pub_dt"], reverse=True)
    return deduplicate(all_items)[:max_total]


def source_score_en(item):
    """우선 소스에 2시간 보너스 부여해 상위 정렬"""
    src = item.get("source") or ""
    preferred = any(ps.lower() in src.lower() for ps in PRIORITY_SOURCES_EN)
    bonus = timedelta(hours=2) if preferred else timedelta(0)
    dt = item["pub_dt"]
    if dt == UNKNOWN_DT:
        return datetime.min.replace(tzinfo=timezone.utc)
    return dt + bonus


def fetch_priority_en_news(max_total=30):
    """유력 언론 Google RSS site: 필터 수집 → 우선 소스 가중치 정렬 → 50건"""
    print("  ▶ [해외-L2] 유력 언론 Google RSS 수집", file=sys.stderr)
    all_items = []
    for query in PRIORITY_EN_QUERIES:
        url = google_rss_en_url(query)
        all_items.extend(parse_rss(fetch_url(url)))
        time.sleep(REQUEST_DELAY)
    all_items = [i for i in all_items if not is_excluded(i)]
    all_items.sort(key=source_score_en, reverse=True)
    return deduplicate(all_items)[:max_total]


def fetch_experts(experts):
    """전문가 동향: 인당 최대 3건, 전체 최대 30건"""
    print("  ▶ 전문가 동향 수집 중…", file=sys.stderr)
    cutoff = datetime.now(timezone.utc) - timedelta(days=EXPERT_DAYS)

    # 1단계: 전문가별 개별 수집·필터·중복제거·3건 제한
    per_expert: dict[str, tuple[list, str]] = {}
    for ex in experts:
        print(f"    {ex['name']}", file=sys.stderr, end=" ")
        raw = parse_rss(fetch_url(google_rss_url(ex["search"])))
        time.sleep(REQUEST_DELAY)

        filtered = [
            i for i in raw
            if i["pub_dt"] != UNKNOWN_DT
            and i["pub_dt"] >= cutoff
            and not is_excluded(i)
            and not is_expert_excluded(i)
            # 출연자 이름이 제목에 '단어'로 실제 등장해야 함 — 구글이 흔한 단어를 품은
            # 이름("선정수"→"우수기관 선정")으로 엉뚱한 기사를 물어오는 것을 차단.
            # (전문기자는 필자라 제목에 이름이 안 나오므로 이 필터를 걸지 않음)
            and title_has_keyword(i["title"], ex["name"])
        ]
        filtered.sort(key=lambda x: x["pub_dt"], reverse=True)

        # 전문가 내 제목 앞 15자 중복 제거
        seen_pfx: set[str] = set()
        deduped = []
        for item in filtered:
            pfx = item["title"][:15]
            if pfx not in seen_pfx:
                seen_pfx.add(pfx)
                deduped.append(item)

        kept = deduped[:MAX_PER_EXPERT]
        per_expert[ex["name"]] = (kept, ex["tag"])
        print(f"→ {len(kept)}건", file=sys.stderr)

    # 2단계: URL 기준 통합 중복 제거, 태그 병합
    url_item:    dict[str, dict]  = {}
    url_experts: dict[str, list]  = {}
    for ex_name, (articles, ex_tag) in per_expert.items():
        for item in articles:
            url = item["link"]
            if url not in url_item:
                url_item[url]    = item
                url_experts[url] = []
            if ex_name not in [e["name"] for e in url_experts[url]]:
                url_experts[url].append({"name": ex_name, "tag": ex_tag})

    result = []
    for url, item in url_item.items():
        item["experts"] = url_experts[url]
        result.append(item)

    result.sort(key=lambda x: x["pub_dt"], reverse=True)
    return result[:20]


def fetch_policy_figures(figures):
    """정책 동향(인물+기관): 인당 최대 3건, 전체 최대 12건"""
    print("  ▶ 정책 동향 수집 중…", file=sys.stderr)
    cutoff = datetime.now(timezone.utc) - timedelta(days=EXPERT_DAYS)

    per_figure: dict[str, tuple[list, str]] = {}
    for fig in figures:
        print(f"    {fig['name']}", file=sys.stderr, end=" ")
        raw = parse_rss(fetch_url(google_rss_url(fig["search"])))
        time.sleep(REQUEST_DELAY)

        filtered = [
            i for i in raw
            if i["pub_dt"] != UNKNOWN_DT
            and i["pub_dt"] >= cutoff
            and not is_excluded(i)
            and not is_expert_excluded(i)
        ]
        filtered.sort(key=lambda x: x["pub_dt"], reverse=True)

        seen_pfx: set[str] = set()
        deduped = []
        for item in filtered:
            pfx = item["title"][:15]
            if pfx not in seen_pfx:
                seen_pfx.add(pfx)
                deduped.append(item)

        kept = deduped[:MAX_PER_EXPERT]
        per_figure[fig["name"]] = (kept, fig["tag"])
        print(f"→ {len(kept)}건", file=sys.stderr)

    url_item:    dict[str, dict] = {}
    url_experts: dict[str, list] = {}
    for fig_name, (articles, fig_tag) in per_figure.items():
        for item in articles:
            url = item["link"]
            if url not in url_item:
                url_item[url] = item
                url_experts[url] = []
            if fig_name not in [e["name"] for e in url_experts[url]]:
                url_experts[url].append({"name": fig_name, "tag": fig_tag})

    result = []
    for url, item in url_item.items():
        item["experts"] = url_experts[url]
        result.append(item)

    result.sort(key=lambda x: x["pub_dt"], reverse=True)
    return result[:12]


def fetch_reporters(reporters):
    """환경전문기자 동향: 인당 최대 3건, 전체 최대 30건"""
    print("  ▶ 전문기자 동향 수집 중…", file=sys.stderr)
    cutoff = datetime.now(timezone.utc) - timedelta(days=EXPERT_DAYS)

    per_reporter: dict[str, tuple[list, dict]] = {}
    for r in reporters:
        print(f"    {r['name']}", file=sys.stderr, end=" ")
        raw = parse_rss(fetch_url(google_rss_url(r["search"])))
        time.sleep(REQUEST_DELAY)

        filtered = [
            i for i in raw
            if i["pub_dt"] != UNKNOWN_DT
            and i["pub_dt"] >= cutoff
            and not is_excluded(i)
            and not is_expert_excluded(i)
        ]
        filtered.sort(key=lambda x: x["pub_dt"], reverse=True)

        seen_pfx: set[str] = set()
        deduped = []
        for item in filtered:
            pfx = item["title"][:15]
            if pfx not in seen_pfx:
                seen_pfx.add(pfx)
                deduped.append(item)

        kept = deduped[:MAX_PER_EXPERT]
        per_reporter[r["name"]] = (kept, {"name": r["name"], "media": r["media"], "beat": r["beat"]})
        print(f"→ {len(kept)}건", file=sys.stderr)

    url_item:      dict[str, dict] = {}
    url_reporters: dict[str, list] = {}
    for r_name, (articles, r_info) in per_reporter.items():
        for item in articles:
            url = item["link"]
            if url not in url_item:
                url_item[url] = item
                url_reporters[url] = []
            if r_name not in [rr["name"] for rr in url_reporters[url]]:
                url_reporters[url].append(r_info)

    result = []
    for url, item in url_item.items():
        item["reporters"] = url_reporters[url]
        result.append(item)

    result.sort(key=lambda x: x["pub_dt"], reverse=True)
    return result[:MAX_EXPERTS]


# ─────────────────────────────────────────────────────────────
# HTML 생성
# ─────────────────────────────────────────────────────────────
def h(text):
    return html_lib.escape(str(text), quote=True)


def badge(label, color):
    return (
        f'<span class="badge" style="background:{color}20;color:{color};'
        f'border:1px solid {color}40">{h(label)}</span>'
    )


def score_badge(score):
    """아이템성 스코어 배지 — 5+ 강력 후보, 3~4 후보"""
    if score >= 5:
        return f'<span class="score-badge hot">🔥 {score}</span>'
    if score >= 3:
        return f'<span class="score-badge good">★ {score}</span>'
    return ""


def news_card(item, en=False, show_score=False):
    title    = h(item["title"])
    link     = h(item["link"])
    source   = h(item.get("source") or "")
    pub      = h(item.get("pub_str") or "")
    lang_cls = ' lang-en' if en else ''
    src_html = f'<span class="source">{source}</span>' if source else ""
    score_html = score_badge(item.get("score", 0)) if show_score else ""
    life_html = '<span title="생활·기획 연결">🌿</span>' if show_score and item.get("life_hit") else ""
    return (
        f'<div class="news-item">'
        f'<div class="news-body">'
        f'<div class="news-meta">{src_html}<span class="pub-time">{pub}</span>{score_html}{life_html}</div>'
        f'<a class="news-title{lang_cls}" href="{link}" target="_blank" rel="noopener">{title}</a>'
        f'</div>'
        f'</div>'
    )


def generate_css():
    return """
:root {
  --bg:         #ffffff;
  --card:       #ffffff;
  --border:     #e5e5e5;
  --text:       #111111;
  --muted:      #767676;
  --accent:      #EF7D2E;
  --accent-dark: #D96A1C;
  --accent-soft: #FEF3EB;
  --accent-line: #F8D2AE;
  --radius:      0;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: Pretendard, -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo",
               "Noto Sans KR", "Segoe UI", sans-serif;
  background: var(--bg); color: var(--text); font-size: 14.5px;
  line-height: 1.6;
}

/* ── HEADER ── */
.site-header {
  background: #fff; color: var(--text);
  padding: 22px 24px 16px;
  border-bottom: 3px solid var(--text);
  display: flex; align-items: flex-start; justify-content: space-between;
  flex-wrap: wrap; gap: 12px;
}
.header-left h1 { font-size: 1.45rem; font-weight: 800; letter-spacing: -.4px; line-height: 1.3; }
.header-meta {
  margin-top: 8px; display: flex; flex-wrap: wrap; gap: 14px;
  font-size: 12px; color: var(--muted); line-height: 1.5;
}
.header-meta strong { color: var(--text); font-weight: 700; }
.header-right { display: flex; align-items: center; }

/* ── REFRESH BUTTON ── */
.refresh-btn {
  display: inline-flex; align-items: center; gap: 7px;
  padding: 9px 17px; border-radius: var(--radius); border: none;
  background: var(--accent); color: #fff; font-size: 13px; font-weight: 700;
  cursor: pointer; transition: background .15s; white-space: nowrap;
}
.refresh-btn:hover  { background: var(--accent-dark); }
.refresh-btn:active { transform: scale(.97); }
.refresh-btn.loading { opacity: .6; cursor: not-allowed; pointer-events: none; }
.spinner {
  width: 14px; height: 14px; border: 2px solid rgba(255,255,255,.4);
  border-top-color: #fff; border-radius: 50%;
  animation: spin .7s linear infinite; display: none;
}
.refresh-btn.loading .spinner { display: block; }
.refresh-btn.loading .btn-icon { display: none; }
@keyframes spin { to { transform: rotate(360deg); } }

/* ── TABS ── */
.tab-nav {
  display: flex; background: #fff; border-bottom: 1px solid var(--border);
  position: sticky; top: 0; z-index: 10; overflow-x: auto;
  scrollbar-width: none;
}
.tab-nav::-webkit-scrollbar { display: none; }
.tab-btn {
  flex: 1; min-width: 80px; padding: 14px 12px; border: none; background: transparent;
  font-size: 14.5px; font-weight: 700; color: var(--text); cursor: pointer;
  letter-spacing: .02em;
  border-bottom: 3px solid transparent; margin-bottom: -1px; white-space: nowrap;
  transition: all .15s; line-height: 1.4;
}
.tab-btn:hover  { color: var(--accent); background: var(--accent-soft); }
.tab-btn.active { color: var(--text); border-bottom-color: var(--accent); }
.tab-content { display: none; }
.tab-content.active { display: block; }

/* ── CONTAINER ── */
.container { max-width: 1280px; margin: 0 auto; padding: 32px 24px; }

/* ── CATEGORY GRID ── */
.cat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 8px 40px;
}
.cat-card {
  background: var(--card);
  margin-bottom: 24px;
}
.cat-header {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 12px; background: var(--text);
}
.cat-dot   { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; background: var(--accent) !important; }
.cat-name  { font-size: 14px; font-weight: 800; line-height: 1.4; color: #fff; }
.cat-count { margin-left: auto; font-size: 12px; color: rgba(255,255,255,.55); }
.cat-body  { padding: 0; }

/* ── NEWS ITEM ── */
.news-item {
  padding: 15px 0; border-bottom: 1px solid var(--border);
  display: block;
}
.news-item:last-child { border-bottom: none; }
.news-body { width: 100%; }
.news-meta {
  font-size: 12px; color: var(--muted); line-height: 1.5;
  display: flex; align-items: center; gap: 8px; margin-bottom: 6px; flex-wrap: wrap;
}
.source   { font-weight: 700; color: var(--text); }
.pub-time { color: #9e9e9e; }
.news-title {
  display: block; font-size: 15.5px; font-weight: 700; letter-spacing: -.2px;
  color: var(--text); text-decoration: none; line-height: 1.55;
}
.news-title.lang-en { font-size: 14.5px; font-weight: 600; letter-spacing: 0; }
.news-title:hover { color: var(--accent); text-decoration: underline; }
.empty-state {
  padding: 24px 14px; text-align: center;
  color: var(--muted); font-size: 12px;
}

/* ── BADGE ── */
.badge {
  display: inline-flex; align-items: center; padding: 1px 8px; border-radius: 2px;
  font-size: 11px; font-weight: 700; white-space: nowrap; line-height: 1.6;
}

/* ── CALENDAR ── */
.cal-wrap { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 8px 40px; }
.cal-month { background: var(--card); margin-bottom: 24px; }
.cal-month-header {
  padding: 10px 12px; font-size: 14px; font-weight: 800;
  background: var(--text); color: #fff; line-height: 1.4;
}
.cal-month.current .cal-month-header { background: var(--accent); }
.cal-events { padding: 0; }
.cal-event { border-bottom: 1px solid var(--border); }
.cal-event:last-child { border-bottom: none; }
.cal-event summary {
  list-style: none; padding: 13px 0; cursor: pointer;
  display: flex; flex-direction: column; gap: 4px;
}
.cal-event summary::-webkit-details-marker { display: none; }
.cal-event summary:hover { background: #fafafa; }
.cal-event-title { font-size: 13px; font-weight: 600; line-height: 1.5; }
.cal-event-memo  { font-size: 12px; color: var(--muted); line-height: 1.5; }
.cal-event-keywords { padding: 0 0 14px; display: flex; flex-wrap: wrap; gap: 6px; }
.kw-chip {
  font-size: 11px; background: #fafafa;
  padding: 2px 8px; color: var(--muted); line-height: 1.6;
}
.year-round-section { margin-top: 32px; }
.year-round-section h3 {
  font-size: 13px; font-weight: 800; color: #fff;
  background: var(--text);
  margin-bottom: 0; letter-spacing: .3px;
  padding: 10px 12px;
}

/* ── EXPERTS ── */
.expert-list { background: var(--card); }
.expert-item {
  display: flex; gap: 18px;
  padding: 16px 0; border-bottom: 1px solid var(--border);
}
.expert-item:last-child { border-bottom: none; }
.expert-date {
  width: 64px; flex-shrink: 0;
  font-size: 11px; color: #9e9e9e; padding-top: 4px;
  white-space: nowrap; line-height: 1.5;
}
.expert-body { flex: 1; min-width: 0; }
.expert-title {
  font-size: 15px; font-weight: 700; color: var(--text);
  text-decoration: none; display: block; margin-bottom: 6px; line-height: 1.5;
}
.expert-title:hover { color: var(--accent); text-decoration: underline; }
.expert-meta {
  font-size: 11px; color: var(--muted); line-height: 1.6;
  display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
}
.expert-tags { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
.no-data { padding: 40px 20px; text-align: center; color: var(--muted); font-size: 13px; }
.tag-media { font-size: 11px; font-weight: 700; color: var(--text); }
.tag-name  { font-size: 11px; font-weight: 600; color: var(--muted); }
.tag-media + .tag-name::before { content: " · "; color: #d4d4d4; }

/* ── PERSON CHIP (출연자·정책 인물) ── */
.person-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 0 7px; border-radius: 2px; line-height: 1.7;
  background: #f5f5f5; color: #333; border: 1px solid #e0e0e0;
  font-size: 11px; font-weight: 700; white-space: nowrap;
}
.person-chip .chip-role { font-weight: 500; color: var(--muted); }
.person-chip.policy {
  background: var(--accent-soft); color: #BA5A1E; border-color: var(--accent-line);
}
.person-chip.policy .chip-role { color: var(--accent); }

/* ── SCORE BADGE (아이템성 스코어) ── */
.score-badge {
  display: inline-flex; align-items: center; padding: 0 6px; border-radius: 2px;
  font-size: 10px; font-weight: 700; white-space: nowrap; line-height: 1.7;
}
.score-badge.hot  { background: var(--accent); color: #fff; }
.score-badge.good { background: var(--accent-soft); color: var(--accent); border: 1px solid var(--accent-line); }

/* ── TOP PICKS (발제 후보) ── */
.top-picks {
  background: var(--card);
  margin-bottom: 40px;
}
.top-picks-header {
  padding: 10px 12px; font-size: 14px; font-weight: 800; line-height: 1.5;
  background: var(--accent); color: #fff;
  display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap;
}
.top-picks-sub { font-size: 11px; font-weight: 500; color: rgba(255,255,255,.85); }
.top-picks-body .news-item { padding: 15px 0; }
.cat-tag { color: var(--accent); font-weight: 700; font-size: 11px; }

/* ── ECON RADAR ── */
.radar-intro {
  font-size: 12px; color: var(--muted); line-height: 1.6;
  padding: 0; margin-bottom: 24px;
}

/* ── 오늘의 경제 브리핑 카드 ── */
.brief-list { background: var(--card); }
.brief-item {
  padding: 16px 0; border-bottom: 1px solid var(--border);
  display: flex; gap: 14px; align-items: baseline;
}
.brief-item:last-child { border-bottom: none; }
.brief-rank {
  flex-shrink: 0; width: 26px; text-align: center;
  font-size: 18px; font-weight: 800; color: var(--accent);
  font-variant-numeric: tabular-nums;
}
.brief-body { flex: 1; min-width: 0; }
.brief-head {
  display: block; font-size: 16px; font-weight: 800; color: var(--text);
  text-decoration: none; line-height: 1.5; margin-bottom: 6px;
}
.brief-head:hover { color: var(--accent); text-decoration: underline; }
.brief-summary { font-size: 13px; color: #333; line-height: 1.6; margin-bottom: 8px; }
.brief-climate {
  font-size: 13px; font-weight: 700; color: var(--accent);
  line-height: 1.55; padding: 8px 12px;
  background: var(--accent-soft); border-left: 3px solid var(--accent);
}
.brief-noclimate { font-size: 12px; color: #9e9e9e; }
.brief-meta {
  font-size: 11px; color: var(--muted); margin-top: 8px;
  display: flex; gap: 8px; align-items: center;
}

/* ── 언론사명 강조 (해외뉴스·전문기자 탭) ── */
#tab-news-en .source { color: var(--accent); }
.tag-media { color: var(--accent); }

/* ── TOAST ── */
.toast {
  position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
  background: var(--text); color: #fff; padding: 10px 20px;
  border-radius: var(--radius); font-size: 13px; font-weight: 500;
  opacity: 0; pointer-events: none; transition: opacity .3s; z-index: 999;
}
.toast.show { opacity: 1; }

/* ── EN SECTION LABEL ── */
.en-section-label {
  font-size: 13px; font-weight: 800; color: #fff;
  background: var(--text);
  margin-bottom: 0; letter-spacing: .3px;
  padding: 10px 12px;
}

/* ── 기후 전문 매체 (하단 전용 섹션) ── */
.media-section { margin-top: 32px; }
.media-sub { font-size: 11px; font-weight: 500; color: var(--muted); letter-spacing: 0; }
.media-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(330px, 1fr));
  gap: 0 40px;
}
.media-grid .news-item { padding: 13px 0; }

/* ── RESPONSIVE ── */
@media (max-width: 600px) {
  .site-header { padding: 16px 14px 12px; }
  .header-left h1 { font-size: 1.1rem; }
  .tab-btn { font-size: 12px; padding: 11px 6px; }
  .cat-grid, .cal-wrap, .media-grid { grid-template-columns: 1fr; }
  .container { padding: 20px 16px; }
}
"""


def generate_cal_event(ev):
    chips = "".join(f'<span class="kw-chip">{h(k)}</span>' for k in ev["keywords"])
    return (
        f'<details class="cal-event">'
        f'<summary>'
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:3px">'
        f'{badge(ev["label"], ev["color"])}'
        f'<span class="cal-event-title">{h(ev["title"])}</span></div>'
        f'<div class="cal-event-memo">{h(ev["memo"])}</div>'
        f'</summary>'
        f'<div class="cal-event-keywords">{chips}</div>'
        f'</details>'
    )


def generate_calendar_tab(calendar_news):
    cur_month = datetime.now(KST).month
    months_html = ""
    for m in range(1, 13):
        events = CALENDAR.get(m, [])
        cur_cls = " current" if m == cur_month else ""
        evts_html = (
            "".join(generate_cal_event(ev) for ev in events)
            if events
            else '<div class="empty-state">이달 예정 이벤트 없음</div>'
        )
        months_html += (
            f'<div class="cal-month{cur_cls}">'
            f'<div class="cal-month-header">{MONTH_NAMES[m-1]}</div>'
            f'<div class="cal-events">{evts_html}</div>'
            f'</div>'
        )
    news_html = "".join(news_card(i) for i in calendar_news) if calendar_news \
                else '<div class="empty-state">수집된 기사 없음</div>'
    return (
        f'<div class="container">'
        f'<div class="cal-wrap">{months_html}</div>'
        f'<div class="year-round-section">'
        f'<h3>📌 데드라인·빅 이벤트 뉴스</h3>'
        f'<div class="expert-list">{news_html}</div>'
        f'</div>'
        f'</div>'
    )


def generate_top_picks(categories_data, top_n=10, min_score=3):
    """발제 후보 TOP — 국내 카테고리 + 기후 전문매체를 한 풀에 합쳐 점수 상위로 선별.
    잠식 방지: 같은 기업 최대 2건, 같은 카테고리 최대 3건"""
    pool = []
    for cat in categories_data:        # 국내 카테고리 + 전문매체(media)
        for item in cat["items"]:
            if item.get("score", 0) >= min_score:
                pool.append((item, cat))
    pool.sort(key=lambda x: (x[0]["score"], x[0]["pub_dt"]), reverse=True)
    if not pool:
        return ""
    picked, co_count, cat_count = [], {}, {}
    for item, cat in pool:
        co = company_key(item["title"])
        if co is not None and co_count.get(co, 0) >= 2:
            continue
        if cat_count.get(cat["id"], 0) >= 3:
            continue
        picked.append((item, cat))
        if co is not None:
            co_count[co] = co_count.get(co, 0) + 1
        cat_count[cat["id"]] = cat_count.get(cat["id"], 0) + 1
        if len(picked) >= top_n:
            break
    rows = ""
    for item, cat in picked:
        link   = h(item["link"])
        title  = h(item["title"])
        source = h(item.get("source") or "")
        pub    = h(item.get("pub_str") or "")
        src_html  = f'<span class="source">{source}</span>' if source else ""
        life_html = ('<span title="생활·기획 연결">🌿</span>'
                     if item.get("life_hit") else "")
        rows += (
            f'<div class="news-item">'
            f'<div class="news-body">'
            f'<div class="news-meta"><span class="cat-tag">[{h(cat["name"])}]</span>'
            f'{src_html}<span class="pub-time">{pub}</span>'
            f'{score_badge(item["score"])}{life_html}</div>'
            f'<a class="news-title" href="{link}" target="_blank" rel="noopener">{title}</a>'
            f'</div></div>'
        )
    return (
        f'<div class="top-picks">'
        f'<div class="top-picks-header">🎯 오늘의 발제 후보 TOP {len(picked)}'
        f'<span class="top-picks-sub">국내 카테고리·전문매체 통합 — 점수 상위 자동 선별</span></div>'
        f'<div class="top-picks-body">{rows}</div>'
        f'</div>'
    )


def generate_news_tab(categories_data, en=False):
    cards = ""
    media_cat = None
    for cat in categories_data:
        if cat["id"] == "media":      # 전문 매체는 하단 전용 섹션으로 분리
            media_cat = cat
            continue
        color = cat["color"]
        items = cat["items"]
        cat_name_display = ("🔔 " if cat["id"] == "tech" and len(items) >= 3 else "") + cat["name"]
        body = (
            "".join(news_card(i, en=en, show_score=True) for i in items)
            if items else '<div class="empty-state">수집된 기사가 없습니다</div>'
        )
        cards += (
            f'<div class="cat-card">'
            f'<div class="cat-header">'
            f'<div class="cat-dot" style="background:{color}"></div>'
            f'<span class="cat-name">{h(cat_name_display)}</span>'
            f'<span class="cat-count">{len(items)}건</span>'
            f'</div>'
            f'<div class="cat-body">{body}</div>'
            f'</div>'
        )
    media_html = ""
    if media_cat and media_cat["items"]:
        rows = "".join(news_card(i, show_score=True) for i in media_cat["items"])
        media_html = (
            f'<div class="media-section">'
            f'<div class="en-section-label">📰 기후 전문 매체 '
            f'<span class="media-sub">뉴스펭귄·그리니엄·임팩트온·ESG경제 — '
            f'화제 이슈를 기후 각도로 다루는 전문지</span></div>'
            f'<div class="media-grid">{rows}</div>'
            f'</div>'
        )
    return (f'<div class="container">'
            f'<div class="cat-grid">{cards}</div>{media_html}</div>')


def gnews_search_link(kw):
    """키워드용 구글뉴스 검색 웹 URL"""
    return ("https://news.google.com/search?q="
            + urllib.parse.quote(kw) + "&hl=ko&gl=KR&ceid=KR:ko")


def generate_radar_tab(categories_data, briefing, surprise_items):
    """이슈 레이더(대시보드): 발제 후보 TOP10 + 오늘의 경제 브리핑 TOP10 + 화제×기후"""
    # 1) 발제 후보 TOP10 (국내+전문매체 종합)
    top_picks = generate_top_picks(categories_data)

    # 2) 오늘의 경제 브리핑 TOP10 (Claude 웹검색)
    if briefing:
        cards = ""
        for rank, b in enumerate(briefing, 1):
            head = h(b.get("headline", ""))
            summ = h(b.get("summary", ""))
            kw   = b.get("kw", "").strip()
            link = h(gnews_search_link(kw)) if kw else "#"
            kw_html = f'<span class="cat-tag">[{h(kw)}]</span>' if kw else ""
            cards += (
                f'<div class="brief-item">'
                f'<span class="brief-rank">{rank}</span>'
                f'<div class="brief-body">'
                f'<a class="brief-head" href="{link}" target="_blank" rel="noopener">{head}</a>'
                f'<div class="brief-summary">{summ}</div>'
                f'<div class="brief-meta">{kw_html}'
                f'<span class="pub-time">구글뉴스에서 보기 →</span></div>'
                f'</div></div>'
            )
        brief_body = cards
    else:
        brief_body = ('<div class="empty-state">오늘 경제 브리핑이 아직 준비되지 '
                      '않았습니다 — 곧 갱신됩니다</div>')

    # 3) 화제 × 기후 (의외 키워드 × 기후)
    def surprise_card(item):
        kw = h(item.get("surprise_kw", ""))
        base = news_card(item, show_score=True)
        return base.replace('<div class="news-meta">',
                            f'<div class="news-meta"><span class="cat-tag">[{kw}]</span>', 1)
    surprise_body = ("".join(surprise_card(i) for i in surprise_items)
                     if surprise_items
                     else '<div class="empty-state">오늘은 의외 분야×기후 교차 기사가 잡히지 않음</div>')

    return (
        f'<div class="container">'
        f'<div class="radar-intro">오늘의 이슈를 한눈에 보는 대시보드 — '
        f'발제 후보·경제 브리핑·화제×기후를 모아 발제 출발점으로 씁니다.</div>'
        f'{top_picks}'
        f'<div class="en-section-label" style="margin-top:32px">📊 오늘의 경제 브리핑 TOP {len(briefing) if briefing else 0}'
        f'<span class="media-sub"> — {(BRIEFING_DATE + " 기준 · ") if BRIEFING_DATE else ""}오늘 최대 경제 뉴스</span></div>'
        f'<div class="brief-list">{brief_body}</div>'
        f'<div class="en-section-label" style="margin-top:32px">🔥 화제 × 기후'
        f'<span class="media-sub"> — 평소 기후와 안 엮이던 분야(스포츠·음식·생활)가 기후와 만난 기사</span></div>'
        f'<div class="brief-list">{surprise_body}</div>'
        f'</div>'
    )


def generate_experts_tab(experts_data, policy_data):
    def render_items(items_list, empty_msg, chip_cls="person-chip"):
        if not items_list:
            return f'<div class="no-data">{empty_msg}</div>'
        html = ""
        for item in items_list:
            link   = h(item["link"])
            title  = h(item["title"])
            source = h(item.get("source") or "")
            pub    = h(item.get("pub_str") or "")
            src_html = f'<span class="source">{source}</span>' if source else ""
            tags_html = ""
            for ex in item.get("experts", []):
                role = (f'<span class="chip-role">{h(ex["tag"])}</span>'
                        if ex.get("tag") else "")
                tags_html += f'<span class="{chip_cls}">{h(ex["name"])}{role}</span>'
            html += (
                f'<div class="expert-item">'
                f'<div class="expert-date">{pub}</div>'
                f'<div class="expert-body">'
                f'<a class="expert-title" href="{link}" target="_blank" rel="noopener">{title}</a>'
                f'<div class="expert-meta">'
                f'<div class="expert-tags">{tags_html}</div>'
                f'{src_html}'
                f'</div></div></div>'
            )
        return html

    experts_html = render_items(experts_data, f"최근 {EXPERT_DAYS}일 내 출연자 관련 기사가 없습니다.")
    policy_html  = render_items(policy_data,  f"최근 {EXPERT_DAYS}일 내 정책 동향 기사가 없습니다.",
                                chip_cls="person-chip policy")

    return (
        f'<div class="container">'
        f'<div class="en-section-label">🎙 출연자</div>'
        f'<div class="expert-list" style="margin-bottom:24px">{experts_html}</div>'
        f'<div class="en-section-label">📋 정책 동향</div>'
        f'<div class="expert-list">{policy_html}</div>'
        f'</div>'
    )


def generate_en_tab(trusted_items, priority_items):
    def item_html(item):
        title  = h(item["title"])
        link   = h(item["link"])
        source = h(item.get("source") or "")
        pub    = h(item.get("pub_str") or "")
        src_html = f'<span class="source">{source}</span>' if source else ""
        kr_html = ('<span title="한국 언급 외신">🇰🇷</span>'
                   if re.search(r"\bKorea", item["title"]) else "")
        return (
            f'<div class="news-item">'
            f'<a class="news-title lang-en" href="{link}" target="_blank" rel="noopener">{title}</a>'
            f'<div class="news-meta">{src_html}<span class="pub-time">{pub}</span>{kr_html}</div>'
            f'</div>'
        )

    trusted_html = "".join(item_html(i) for i in trusted_items) or \
                   '<div class="empty-state">수집된 기사 없음</div>'
    priority_html = "".join(item_html(i) for i in priority_items) or \
                    '<div class="empty-state">수집된 기사 없음</div>'

    return f"""
    <div class="container">
      <div class="en-section-label">🌿 기후 전문 매체</div>
      <div class="expert-list" style="margin-bottom:24px">{trusted_html}</div>
      <div class="en-section-label">📰 주요 언론 (Bloomberg·Reuters·NYT 등)</div>
      <div class="expert-list">{priority_html}</div>
    </div>
    """


def generate_reporters_tab(reporters_data):
    if not reporters_data:
        return (
            '<div class="container">'
            '<div class="no-data">최근 7일 내 전문기자 관련 기사가 없습니다.</div>'
            '</div>'
        )
    items_html = ""
    for item in reporters_data:
        link   = h(item["link"])
        title  = h(item["title"])
        source = h(item.get("source") or "")
        pub    = h(item.get("pub_str") or "")
        tags_html = "".join(
            f'<span class="tag-media">{h(r["media"])}</span>'
            f'<span class="tag-name">{h(r["name"])}</span>'
            for r in item.get("reporters", [])
        )
        items_html += (
            f'<div class="expert-item">'
            f'<div class="expert-date">{pub}</div>'
            f'<div class="expert-body">'
            f'<a class="expert-title" href="{link}" target="_blank" rel="noopener">{title}</a>'
            f'<div class="expert-meta">'
            f'<div class="expert-tags">{tags_html}</div>'
            f'</div></div></div>'
        )
    return f'<div class="container"><div class="expert-list">{items_html}</div></div>'


def generate_html(categories_data, trusted_en_items, priority_en_items, experts_data, policy_data, reporters_data, calendar_news, briefing, surprise_items, today):
    date_str       = today.strftime("%Y년 %m월 %d일")
    time_str       = today.strftime("%H:%M:%S")
    total_ko       = sum(len(c["items"]) for c in categories_data)
    total_en       = len(trusted_en_items) + len(priority_en_items)
    exp_total      = len(experts_data) + len(policy_data)
    reporter_total = len(reporters_data)
    radar_total    = len(briefing) + len(surprise_items)
    css            = generate_css()

    news_ko   = generate_news_tab(categories_data, en=False)
    news_en   = generate_en_tab(trusted_en_items, priority_en_items)
    cal_tab   = generate_calendar_tab(calendar_news)
    exp_tab   = generate_experts_tab(experts_data, policy_data)
    rep_tab   = generate_reporters_tab(reporters_data)
    radar_tab = generate_radar_tab(categories_data, briefing, surprise_items)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>기후로운 경제생활 뉴스 모니터링</title>
<link rel="icon" href="data:image/svg+xml,&lt;svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22&gt;&lt;text y=%22.9em%22 font-size=%2290%22&gt;🌿&lt;/text&gt;&lt;/svg&gt;">
<meta name="apple-mobile-web-app-title" content="기후로운 경제생활">
<meta property="og:title" content="기후로운 경제생활 뉴스 모니터링">
<meta property="og:type" content="website">
<meta property="og:image" content="data:image/svg+xml,&lt;svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22&gt;&lt;text y=%22.9em%22 font-size=%2290%22&gt;🌿&lt;/text&gt;&lt;/svg&gt;">
<style>{css}</style>
</head>
<body>

<header class="site-header">
  <div class="header-left">
    <h1>기후로운 경제생활 뉴스 모니터링</h1>
    <div class="header-meta">
      <span>📅 <strong>{date_str}</strong></span>
      <span>🇰🇷 국내 <strong>{total_ko}건</strong></span>
      <span>🌐 해외 <strong>{total_en}건</strong></span>
      <span>📡 이슈 레이더 <strong>{radar_total}건</strong></span>
      <span>👤 출연자 동향 <strong>{exp_total}건</strong></span>
      <span>✍️ 전문기자 <strong>{reporter_total}건</strong></span>
      <span>🕒 <strong>{time_str}</strong></span>
    </div>
  </div>
  <div class="header-right">
    <button class="refresh-btn" id="refreshBtn" onclick="doRefresh()">
      <span class="btn-icon">↻</span>
      <div class="spinner"></div>
      <span class="btn-label">지금 업데이트</span>
    </button>
  </div>
</header>

<nav class="tab-nav">
  <button class="tab-btn active" onclick="showTab('radar',this)">📡 이슈 레이더</button>
  <button class="tab-btn"        onclick="showTab('news-ko',this)">🇰🇷 국내뉴스</button>
  <button class="tab-btn"        onclick="showTab('news-en',this)">🌐 해외뉴스</button>
  <button class="tab-btn"        onclick="showTab('experts',this)">👤 출연자 동향</button>
  <button class="tab-btn"        onclick="showTab('reporters',this)">✍️ 전문기자</button>
  <button class="tab-btn"        onclick="showTab('calendar',this)">📅 캘린더</button>
</nav>

<div id="tab-radar"     class="tab-content active">{radar_tab}</div>
<div id="tab-news-ko"   class="tab-content">{news_ko}</div>
<div id="tab-news-en"   class="tab-content">{news_en}</div>
<div id="tab-experts"   class="tab-content">{exp_tab}</div>
<div id="tab-reporters" class="tab-content">{rep_tab}</div>
<div id="tab-calendar"  class="tab-content">{cal_tab}</div>

<div class="toast" id="toast"></div>

<script>
// 정적 호스팅(GitHub Pages/file)에는 /refresh 백엔드가 없음 →
// 버튼을 숨기지 않고, GitHub Actions 수동 실행 페이지로 연결(거기서 Run workflow)
var IS_STATIC = location.hostname.endsWith('github.io') || location.protocol === 'file:';
var ACTIONS_URL = 'https://github.com/hotelafreeca/climate-news/actions/workflows/publish.yml';
if (IS_STATIC) {{
  document.getElementById('refreshBtn').title = 'GitHub Actions에서 Run workflow 실행 → 약 3분 후 반영';
}}

function activateTab(name) {{
  var tab = document.getElementById('tab-' + name);
  if (!tab) return;
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  tab.classList.add('active');
  document.querySelectorAll('.tab-btn').forEach(function(b) {{
    var oc = b.getAttribute('onclick') || '';
    if (oc.indexOf("'" + name + "'") >= 0) b.classList.add('active');
  }});
  try {{ sessionStorage.setItem('activeTab', name); }} catch(e) {{}}
}}
function showTab(name, btn) {{ activateTab(name); }}

// 열어둔 탭이 멈춰 보이지 않도록 30분마다 자동 새로고침(보던 탭은 유지)
(function() {{
  try {{
    var saved = sessionStorage.getItem('activeTab');
    if (saved && document.getElementById('tab-' + saved)) activateTab(saved);
  }} catch(e) {{}}
  setInterval(function() {{ location.reload(); }}, 1800000);
}})();

function showToast(msg, duration) {{
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), duration || 3000);
}}

async function doRefresh() {{
  if (IS_STATIC) {{
    window.open(ACTIONS_URL, '_blank', 'noopener');
    showToast("GitHub Actions에서 'Run workflow'를 누르면 갱신됩니다 (~3분 후 반영)", 5000);
    return;
  }}
  const btn = document.getElementById('refreshBtn');
  const lbl = btn.querySelector('.btn-label');
  btn.classList.add('loading');
  lbl.textContent = '업데이트 중...';
  try {{
    const res = await fetch('/refresh', {{ method: 'POST' }});
    if (res.ok) {{
      showToast('업데이트 완료! 페이지를 새로고침합니다…', 2000);
      setTimeout(() => location.reload(), 2200);
    }} else {{
      throw new Error('서버 오류 ' + res.status);
    }}
  }} catch(e) {{
    showToast('⚠ 업데이트 실패: server.py가 실행 중인지 확인해주세요.', 4000);
    btn.classList.remove('loading');
    lbl.textContent = '지금 업데이트';
  }}
}}
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────
def main():
    today       = datetime.now(KST)
    output_file = f"news_{today.strftime('%Y%m%d')}.html"

    print("=" * 62, file=sys.stderr)
    print("  기후로운 경제생활 뉴스 모니터링", file=sys.stderr)
    print(f"  출력: {output_file}", file=sys.stderr)
    print("=" * 62, file=sys.stderr)

    print("\n[기후 전문 매체] 수집", file=sys.stderr)
    media_items = fetch_ko_media()
    print(f"  → {len(media_items)}건", file=sys.stderr)

    print("\n[국내뉴스] 카테고리 수집", file=sys.stderr)
    categories_data = [{"id": "media", "name": "기후 전문 매체",
                        "color": "#EF7D2E", "items": media_items}]
    for cat in CATEGORIES:
        items = fetch_category(cat)
        print(f"       → {len(items)}건", file=sys.stderr)
        categories_data.append({**cat, "items": items})

    removed = dedupe_across_categories(categories_data)
    print(f"  → 카테고리 간 중복 {removed}건 제거", file=sys.stderr)

    print("\n[오늘의 경제 브리핑] briefing.json 로드", file=sys.stderr)
    briefing = fetch_econ_briefing()

    print("\n[화제 × 기후] 의외 키워드 교차", file=sys.stderr)
    surprise_items = fetch_surprise_climate()
    print(f"  → {len(surprise_items)}건", file=sys.stderr)

    print("\n[해외뉴스] 수집", file=sys.stderr)
    trusted_en_items = fetch_trusted_en_feeds()
    print(f"  → L1 {len(trusted_en_items)}건", file=sys.stderr)
    priority_en_items = fetch_priority_en_news()
    print(f"  → L2 {len(priority_en_items)}건", file=sys.stderr)

    print("\n[출연자동향] 수집", file=sys.stderr)
    experts_data = fetch_experts(EXPERTS)
    print(f"  → 총 {len(experts_data)}건 (최근 {EXPERT_DAYS}일)", file=sys.stderr)

    print("\n[정책동향] 수집", file=sys.stderr)
    policy_data = fetch_policy_figures(POLICY_FIGURES)
    print(f"  → 총 {len(policy_data)}건 (최근 {EXPERT_DAYS}일)", file=sys.stderr)

    print("\n[전문기자동향] 수집", file=sys.stderr)
    reporters_data = fetch_reporters(REPORTERS)
    print(f"  → 총 {len(reporters_data)}건 (최근 {EXPERT_DAYS}일)", file=sys.stderr)

    print("\n[캘린더뉴스] 수집", file=sys.stderr)
    calendar_news = fetch_calendar_news()
    print(f"  → {len(calendar_news)}건", file=sys.stderr)

    print("\n[출처 보정] 무출처 기사 원문 추적", file=sys.stderr)
    for lst in ([c["items"] for c in categories_data]
                + [surprise_items, calendar_news,
                   experts_data, policy_data, reporters_data]):
        enrich_sources(lst)
    fixed = sum(1 for c in categories_data for i in c["items"] if i.get("source"))
    print(f"  → 국내 기사 출처 보유 {fixed}건", file=sys.stderr)

    html_content = generate_html(
        categories_data, trusted_en_items, priority_en_items,
        experts_data, policy_data, reporters_data, calendar_news,
        briefing, surprise_items, today
    )
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    ko = sum(len(c["items"]) for c in categories_data)
    en = len(trusted_en_items) + len(priority_en_items)
    print(f"\n✅  완료!  국내 {ko}건 + 경제브리핑 {len(briefing)}건 + 화제×기후 {len(surprise_items)}건 + 해외 {en}건 + 출연자 {len(experts_data)+len(policy_data)}건 + 전문기자 {len(reporters_data)}건 + 캘린더뉴스 {len(calendar_news)}건", file=sys.stderr)
    print(f"   파일: {output_file}", file=sys.stderr)
    print("=" * 62, file=sys.stderr)


if __name__ == "__main__":
    main()
