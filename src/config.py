import os

PLAYER_TAXONOMY = {
    "samsung": {"name": "Samsung", "category": "Samsung", "sub_brands": []},
    "apple": {"name": "Apple", "category": "Apple", "sub_brands": []},
    "cnoem": {"name": "CN OEM", "category": "CNOEM", "sub_brands": [
        "Xiaomi", "Huawei", "OPPO", "OnePlus", "Realme",
        "Vivo", "Honor", "Transsion", "Lenovo", "Motorola"
    ]},
}

SOURCE_TIER_MAP = {
    # Tier 1: 시장조사·산업분석
    "counterpoint.com": 1,
    "counterpointresearch.com": 1,
    "trendforce.com": 1,
    "press.trendforce.com": 1,
    "canalys.com": 1,
    "idc.com": 1,
    "omdia.com": 1,
    "techinsights.com": 1,
    "gfk.com": 1,
    "digitimes.com": 1,
    "thelec.net": 1,
    # Tier 2: 통신사·아시아 매체
    "reuters.com": 2,
    "feeds.reuters.com": 2,
    "bloomberg.com": 2,
    "wsj.com": 2,
    "ft.com": 2,
    "nikkei.com": 2,
    "asia.nikkei.com": 2,
    "scmp.com": 2,
    # Tier 3: 모바일/IT 전문
    "theverge.com": 3,
    "techcrunch.com": 3,
    "engadget.com": 3,
    "tomshardware.com": 3,
    "9to5google.com": 3,
    "9to5mac.com": 3,
    "macrumors.com": 3,
    "appleinsider.com": 3,
    "sammobile.com": 3,
    "androidauthority.com": 3,
    "gsmarena.com": 3,
    "phonearena.com": 3,
    "notebookcheck.net": 3,
    "wccftech.com": 3,
}

PAID_SOURCE_DOMAINS = {"idc.com", "omdia.com", "gfk.com", "techinsights.com"}

JS_REQUIRED_DOMAINS = ["idc.com", "omdia.com", "gfk.com"]

RSS_SOURCES = [
    # Tier 1: 시장조사·산업 분석·공급망
    {"name": "Counterpoint Research", "url": "https://www.counterpointresearch.com/feed/", "tier": 1},
    {"name": "TrendForce PR",         "url": "https://press.trendforce.com/rss.xml", "tier": 1},
    {"name": "Canalys",               "url": "https://www.canalys.com/rss", "tier": 1},
    {"name": "Digitimes",             "url": "https://www.digitimes.com/rss/daily.xml", "tier": 1},
    {"name": "The Elec",              "url": "https://www.thelec.net/rss/allArticle.xml", "tier": 1},
    # Tier 2: 통신사·아시아 매체
    {"name": "Reuters Tech",      "url": "https://feeds.reuters.com/reuters/technologyNews", "tier": 2},
    {"name": "SCMP Tech",         "url": "https://www.scmp.com/rss/5/feed", "tier": 2},
    {"name": "Nikkei Asia Tech",  "url": "https://asia.nikkei.com/rss/feed/section/technology", "tier": 2},
    # Tier 3: 일반 IT 뉴스
    {"name": "The Verge",         "url": "https://www.theverge.com/rss/index.xml", "tier": 3},
    {"name": "TechCrunch",        "url": "https://techcrunch.com/feed/", "tier": 3},
    {"name": "Engadget",          "url": "https://www.engadget.com/rss.xml", "tier": 3},
    {"name": "Tom's Hardware",    "url": "https://www.tomshardware.com/feeds/all", "tier": 3},
    # Tier 3: Apple 전문
    {"name": "9to5Mac",       "url": "https://9to5mac.com/feed/", "tier": 3},
    {"name": "MacRumors",     "url": "https://www.macrumors.com/macrumors.xml", "tier": 3},
    {"name": "AppleInsider",  "url": "https://appleinsider.com/rss/news/", "tier": 3},
    # Tier 3: Android/Google 전문
    {"name": "9to5Google",        "url": "https://9to5google.com/feed/", "tier": 3},
    {"name": "Android Authority", "url": "https://www.androidauthority.com/feed/", "tier": 3},
    # Tier 3: Samsung 전문
    {"name": "SamMobile",         "url": "https://www.sammobile.com/feed/", "tier": 3},
    # Tier 3: 스펙·리뷰
    {"name": "GSMArena",          "url": "https://www.gsmarena.com/rss-news-reviews.php3", "tier": 3},
    {"name": "PhoneArena",        "url": "https://www.phonearena.com/feed/latest", "tier": 3},
    {"name": "Wccftech",          "url": "https://wccftech.com/feed/", "tier": 3},
    {"name": "Notebookcheck",     "url": "https://www.notebookcheck.net/News.40.0.html?feed=rss2", "tier": 3},
]

MODEL_CONFIG = {
    "glm": {"analysis": "glm-4.7", "extraction": "glm-4-flash"},
}

LLM_BACKEND = os.getenv("LLM_BACKEND", "glm")

SEARCH_CONFIG = {
    "max_results_per_query": 15,   # 글로벌 cap = max_results_per_query * 2 = 30
    "max_per_source": 3,           # 소스별 쿼터 (상위 3건만 채택)
    "max_rss_results": 60,         # 점수 정렬 전 후보군 상한
    "max_entries_per_feed": 30,    # 한 피드에서 살펴볼 최신 엔트리 수
    "rss_feed_timeout": 8.0,       # 피드 1개당 병렬 패치 타임아웃 (초)
    "httpx_timeout": 10,
    "selenium_delay_min": 1.0,
    "selenium_delay_max": 3.0,
}
