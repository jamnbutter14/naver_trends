"""
Daily scraper for Naver DataLab (검색어 트렌드) using headless Playwright.
Writes trends.json with the rolling window: end = yesterday (KST), start = end - 30 days.

Setup:
    pip install playwright && playwright install chromium
Run:
    python fetch_trends.py

NOTE: untested against the live site. Selectors marked CHECK may need adjusting
(use `playwright codegen https://datalab.naver.com/keyword/trendSearch.naver`).
Scraping may conflict with Naver's terms of service; keep it to one run a day.
"""
import json
import datetime as dt
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

URL = "https://datalab.naver.com/keyword/trendSearch.naver"
# (topic name, keyword box) -- matches the two columns in your screenshot
TOPICS = [
    ("코르티스 제임스", "코르티스제임스"),
    ("코르티스 마틴", "코르티스마틴"),
    ("코르티스 주훈", "코르티스주훈"),
    ("코르티스 성현", "코르티스성현"),
    ("코르티스 건호", "코르티스건호"),
]
WINDOW_DAYS = 30
END_OFFSET = 1  # 1 = yesterday, 0 = today

end = dt.datetime.now(ZoneInfo("Asia/Seoul")).date() - dt.timedelta(days=END_OFFSET)
start = end - dt.timedelta(days=WINDOW_DAYS)

captured = []


def on_response(resp):
    """Keep every JSON response that looks like trend data."""
    try:
        data = resp.json()
    except Exception:
        return
    if isinstance(data, dict) and (data.get("results") or data.get("result")):
        captured.append({"url": resp.url, "data": data})


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_context(locale="ko-KR", timezone_id="Asia/Seoul").new_page()
    page.on("response", on_response)
    page.goto(URL, wait_until="networkidle")

    # Fill topics: the two <input>s that follow each "주제어N" label (CHECK)
    for i, (name, kw) in enumerate(TOPICS, start=1):
        label = page.get_by_text(f"주제어{i}", exact=True)
        label.locator("xpath=following::input[1]").fill(name)
        label.locator("xpath=following::input[2]").fill(kw)

    # Period: click 직접입력, then set the six date dropdowns (CHECK)
    page.get_by_text("직접입력", exact=True).click()
    selects = page.locator("select")
    n = selects.count()
    values = [start.year, start.month, start.day, end.year, end.month, end.day]
    for sel, v in zip([selects.nth(n - 6 + k) for k in range(6)], values):
        sel.select_option(f"{v:02d}" if v < 100 else str(v))

    # Device / gender / age boxes are all checked by default = "all"
    captured.clear()
    page.get_by_text("네이버 검색 데이터 조회").click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(3000)
    browser.close()

if not captured:
    raise SystemExit("No trend JSON captured - check the selectors with codegen.")

with open("trends.json", "w", encoding="utf-8") as f:
    json.dump(
        {"startDate": str(start), "endDate": str(end), "responses": captured},
        f, ensure_ascii=False, indent=2,
    )
print(f"Saved {len(captured)} response(s) for {start} ~ {end}")
