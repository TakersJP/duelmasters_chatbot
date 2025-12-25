from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import requests
from bs4 import BeautifulSoup
import os
import re
import csv
import time

BASE_DOMAIN = "https://dm.takaratomy.co.jp"
START_URL = "https://dm.takaratomy.co.jp/card/"
BASE_DIR = os.path.dirname(__file__)
CSV_FILE = os.path.join(BASE_DIR, "data", "cards.csv")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

def create_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(options=options)


# =========================
# 詳細ページ解析
# =========================
def parse_card_detail(url, max_retry=5):
    for attempt in range(max_retry):
        try:
            time.sleep(1.5)  
            res = requests.get(url, headers=HEADERS, timeout=10)

            if res.status_code == 503:
                raise requests.exceptions.HTTPError("503")

            res.raise_for_status()
            soup = BeautifulSoup(res.text, "html.parser")

            def get_text(selector):
                el = soup.select_one(selector)
                return el.text.strip() if el else ""

            raw_name = get_text(".card-name")
            card_name = re.sub(r"\(.*?\)$", "", raw_name).strip()

            card_type = get_text(".type")
            civilization = get_text(".civil")
            power = get_text(".power")
            text = get_text(".skills.full")

            cost = ""
            race = ""

            for row in soup.select("table tr"):
                th = row.find("th")
                td = row.find("td")
                if not th or not td:
                    continue
                key = th.text.strip()
                val = td.text.strip()
                if key == "コスト":
                    cost = val
                elif key == "種族":
                    race = val

            color_type = "多色" if "・" in civilization else "単色"

            return {
                "card_name": card_name,
                "civilization": civilization,
                "color_type": color_type,
                "card_type": card_type,
                "cost": cost,
                "power": power,
                "race": race,
                "text": text,
                "tags": ""
            }

        except Exception:
            print(f"詳細取得失敗（{attempt+1}/{max_retry}）: {url}")
            time.sleep(3)

    print("スキップ（取得不能）:", url)
    return None


# =========================
# CSV既存カード名
# =========================
def load_existing_names():
    if not os.path.exists(CSV_FILE):
        return set()
    names = set()
    with open(CSV_FILE, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("card_name"):
                names.add(row["card_name"])
    return names
