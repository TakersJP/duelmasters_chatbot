import time
import csv
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException

from scrape_dm_cards import (
    create_driver,
    parse_card_detail,
    load_existing_names,
    CSV_FILE,
    BASE_DOMAIN
)

# =========================
# 設定
# =========================
SLEEP_SEC = 3  # ページ間の待機時間を増やす
RESTART_INTERVAL = 10
MAX_RETRY_GET = 3
MAX_RETRY_STALE = 3  # Stale要素のリトライ回数


# =========================
# ページURL生成（URL直打ち方式）
# =========================
def build_page_url(page_num: int) -> str:
    return (
        "https://dm.takaratomy.co.jp/card/"
        "?v=%7B"
        "%22suggest%22:%22on%22,"
        "%22keyword_type%22:%5B%22card_name%22,%22card_ruby%22,%22card_text%22%5D,"
        "%22culture_cond%22:%5B%22%E5%8D%98%E8%89%B2%22,%22%E5%A4%9A%E8%89%B2%22%5D,"
        f"%22pagenum%22:%22{page_num}%22,"
        "%22samename%22:%22show%22,"
        "%22sort%22:%22release_new%22"
        "%7D"
    )


# =========================
# 安全な driver.get
# =========================
def safe_get(driver, wait, url):
    for i in range(MAX_RETRY_GET):
        try:
            driver.get(url)
            time.sleep(2)  # ページ読み込み後の追加待機
            wait.until(
                EC.presence_of_all_elements_located(
                    (By.CLASS_NAME, "cardImage")
                )
            )
            time.sleep(1)  # DOM安定化のための追加待機
            return True
        except Exception as e:
            print(f"driver.get 再試行 {i+1}/{MAX_RETRY_GET}: {e}")
            time.sleep(3)
    return False


# =========================
# data-href抽出（Stale対策付き）
# =========================
def extract_card_urls(driver):
    """カードのURLを安全に抽出する"""
    for attempt in range(MAX_RETRY_STALE):
        try:
            # 毎回新しく要素を取得
            cards = driver.find_elements(By.CLASS_NAME, "cardImage")
            
            if not cards:
                return []
            
            # JavaScriptで一気に全データを取得（Stale完全回避）
            detail_urls = driver.execute_script("""
                var cards = document.getElementsByClassName('cardImage');
                var urls = [];
                for (var i = 0; i < cards.length; i++) {
                    var href = cards[i].getAttribute('data-href');
                    if (href) {
                        urls.push(href);
                    }
                }
                return urls;
            """)
            
            # ベースドメインを追加
            full_urls = [BASE_DOMAIN + url for url in detail_urls if url]
            return full_urls
            
        except StaleElementReferenceException as e:
            print(f"Stale要素エラー 再試行 {attempt+1}/{MAX_RETRY_STALE}")
            time.sleep(2)
        except Exception as e:
            print(f"URL抽出エラー: {e}")
            time.sleep(2)
    
    return []


# =========================
# ページ検証（1ページ目に戻っていないか確認）
# =========================
def verify_page_content(driver, expected_page):
    """現在のページが期待するページかを検証"""
    try:
        # ページ番号要素を探す（サイトの仕様に応じて調整が必要）
        time.sleep(1)
        current_url = driver.current_url
        
        # URLにページ番号が含まれているか確認
        if f'pagenum%22:%22{expected_page}%22' in current_url:
            return True
        
        print(f"⚠️  警告: ページ {expected_page} を期待していましたが、URLが一致しません")
        print(f"   現在のURL: {current_url}")
        return False
        
    except Exception as e:
        print(f"ページ検証エラー: {e}")
        return True  # 検証できない場合は続行


# =========================
# メイン処理
# =========================
def main(start_page=1, end_page=None):
    driver = create_driver()
    wait = WebDriverWait(driver, 20)  # タイムアウトを延長

    existing_names = load_existing_names()
    file_exists = os.path.exists(CSV_FILE)
    
    consecutive_empty_pages = 0  # 連続空ページカウンター
    MAX_EMPTY_PAGES = 3  # 3ページ連続で空なら終了

    try:
        with open(CSV_FILE, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "card_name",
                    "civilization",
                    "color_type",
                    "card_type",
                    "cost",
                    "power",
                    "race",
                    "text",
                    "tags"
                ]
            )

            if not file_exists:
                writer.writeheader()

            page = start_page
            while True:
                if end_page is not None and page > end_page:
                    print("\n=== end_page に到達 ===")
                    break

                # Chrome 定期再起動
                if (page - start_page) % RESTART_INTERVAL == 0 and page != start_page:
                    print("\n=== Chrome 再起動 ===")
                    driver.quit()
                    time.sleep(3)
                    driver = create_driver()
                    wait = WebDriverWait(driver, 20)

                print(f"\n=== Page {page} ===")
                url = build_page_url(page)
                #print(f"URL: {url}")

                if not safe_get(driver, wait, url):
                    print("❌ ページ取得失敗。終了")
                    break

                # ページ内容を検証
                verify_page_content(driver, page)

                # data-href を安全に抽出
                detail_urls = extract_card_urls(driver)
                
                print(f"取得カード数: {len(detail_urls)}")

                if not detail_urls:
                    consecutive_empty_pages += 1
                    print(f"⚠️  カードなし（連続 {consecutive_empty_pages}/{MAX_EMPTY_PAGES}）")
                    
                    if consecutive_empty_pages >= MAX_EMPTY_PAGES:
                        print("❌ 連続空ページ上限に到達。終了")
                        break
                    
                    page += 1
                    time.sleep(SLEEP_SEC)
                    continue
                else:
                    consecutive_empty_pages = 0  # リセット

                # 各カードの詳細を取得
                new_cards_count = 0
                for idx, detail_url in enumerate(detail_urls, 1):
                    print(f"  [{idx}/{len(detail_urls)}] 処理中...")
                    
                    card_data = parse_card_detail(detail_url)
                    if not card_data:
                        continue

                    name = card_data["card_name"]
                    if not name or name in existing_names:
                        print(f"  スキップ: {name}")
                        continue

                    writer.writerow(card_data)
                    f.flush()  # 即座にファイルに書き込む
                    existing_names.add(name)
                    new_cards_count += 1
                    print(f"  ✅ 追加: {name}")

                print(f"📊 ページ {page} 完了: {new_cards_count}枚の新規カードを追加")
                
                page += 1
                time.sleep(SLEEP_SEC)

        print("\n🎉 === 全カード取得完了 ===")

    except KeyboardInterrupt:
        print("\n⚠️  ユーザーによる中断") #ctrl+cで強制終了可能
    except Exception as e:
        print(f"\n❌ 予期しないエラー: {e}")
        import traceback
        traceback.print_exc()
    finally:
        driver.quit()
        print(f"\n最終処理ページ: {page-1}")


if __name__ == "__main__":
    main(start_page=247, end_page=423)