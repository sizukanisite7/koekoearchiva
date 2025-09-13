import requests
from bs4 import BeautifulSoup
import os
import sqlite3
from datetime import datetime, timedelta
import re
from urllib.parse import urljoin

import time
import logging
from config import DATABASE, DOWNLOADS_DIR
from database import get_db_connection, init_db, create_schema_file

# --- ロギング設定 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scraper.log"),
        logging.StreamHandler()
    ]
)

BASE_URL = "https://koe-koe.com/"
LIST_URL_TEMPLATE = urljoin(BASE_URL, "list.php?g=1&g2=0&p={}")


def parse_posted_at(posted_at_str):
    """
    相対的な投稿日時文字列（例: '@3時間前'）をdatetimeオブジェクトに変換する。
    """
    if not posted_at_str or not posted_at_str.startswith('@'):
        # 不明なフォーマットの場合は現在時刻を返す
        return datetime.now()

    now = datetime.now()
    posted_at_str = posted_at_str.strip('@').strip() # '@'と前後の空白を削除

    if '時間前' in posted_at_str:
        hours_ago = int(re.search(r'(\d+)時間前', posted_at_str).group(1))
        return now - timedelta(hours=hours_ago)
    elif '分前' in posted_at_str:
        minutes_ago = int(re.search(r'(\d+)分前', posted_at_str).group(1))
        return now - timedelta(minutes=minutes_ago)
    elif '日前' in posted_at_str:
        days_ago = int(re.search(r'(\d+)日前', posted_at_str).group(1))
        return now - timedelta(days=days_ago)
    elif '秒前' in posted_at_str:
        seconds_ago = int(re.search(r'(\d+)秒前', posted_at_str).group(1))
        return now - timedelta(seconds=seconds_ago)
    else:
        # 対応していないフォーマットの場合は現在時刻
        return now

def parse_duration(duration_str):
    """再生時間（例: '1分2秒'）を秒に変換する"""
    if not duration_str:
        return None

    minutes, seconds = 0, 0
    min_match = re.search(r'(\d+)分', duration_str)
    if min_match:
        minutes = int(min_match.group(1))
    sec_match = re.search(r'(\d+)秒', duration_str)
    if sec_match:
        seconds = int(sec_match.group(1))
    return minutes * 60 + seconds

def get_last_page_number(soup):
    """ページネーションから最終ページ番号を取得する"""
    page_links = soup.select('a[href*="list.php?g=1&g2=0&p="]')
    last_page = 1
    for link in page_links:
        try:
            page_num_str = re.search(r'p=(\d+)', link['href'])
            if page_num_str:
                page_num = int(page_num_str.group(1))
                if page_num > last_page:
                    last_page = page_num
        except (ValueError, TypeError):
            continue
    return last_page

def scrape_page(page_num, cursor):
    """指定されたページ番号のボイスをスクレイピングして保存する"""
    page_url = LIST_URL_TEMPLATE.format(page_num)
    logging.info(f"--- ページ {page_num} の処理を開始 ---")

    try:
        list_page_res = requests.get(page_url)
        list_page_res.raise_for_status()
    except requests.exceptions.RequestException as e:
        logging.error(f"ページ {page_num} の取得に失敗しました: {e}")
        return 0 # 処理した件数を返す

    soup = BeautifulSoup(list_page_res.content, 'html.parser')
    content_links = soup.select('div.content > a[href*="detail.php"]')

    processed_count = 0
    for link in content_links:
        time.sleep(1) # サーバーへの配慮
        detail_url = urljoin(BASE_URL, link.get('href'))
        try:
            koe_koe_id_match = re.search(r'n=(\d+)', detail_url)

            if not koe_koe_id_match:
                continue
            koe_koe_id = koe_koe_id_match.group(1)

            cursor.execute("SELECT id FROM voices WHERE koe_koe_id = ?", (koe_koe_id,))
            if cursor.fetchone():
                logging.info(f"ID: {koe_koe_id} は既に存在します。スキップします。")
                continue

            detail_res = requests.get(detail_url)
            detail_res.raise_for_status()
            detail_soup = BeautifulSoup(detail_res.content, 'html.parser')

            title_element = detail_soup.select_one('#content_body > h2')
            title = title_element.text.strip() if title_element else "（タイトルなし）"

            author_element = detail_soup.select_one('.user_name')
            author = author_element.text.strip() if author_element else "（投稿者不明）"

            posted_at_element = detail_soup.select_one('.meta.detail .meta_item .metaIcon_up')
            posted_at_str = posted_at_element.text.strip() if posted_at_element else ""
            posted_at_dt = parse_posted_at(posted_at_str)

            duration_element = detail_soup.select_one('.audioTime')
            duration_str = duration_element.text.strip() if duration_element else ""
            duration_sec = parse_duration(duration_str)

            audio_url = f"https://file.koe-koe.com/sound/upload/{koe_koe_id}.mp3"

            audio_res = requests.get(audio_url)
            audio_res.raise_for_status()

            filepath = os.path.join(DOWNLOADS_DIR, f"{koe_koe_id}.mp3")
            with open(filepath, 'wb') as f:
                f.write(audio_res.content)

            logging.info(f"  - 音声ファイルを保存: {filepath}")

            cursor.execute("""
                INSERT INTO voices (title, author, posted_at, duration, filepath, koe_koe_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (title, author, posted_at_dt, duration_sec, filepath, koe_koe_id))

            logging.info(f"  - DBに保存: {title}")
            processed_count += 1

        except requests.exceptions.RequestException as e:
            logging.error(f"詳細ページの処理中にエラー (URL: {detail_url}): {e}")
        except Exception as e:
            logging.error(f"予期せぬエラー (URL: {detail_url}): {e}")

    return processed_count

def scrape_all(max_pages=None):
    """サイト全体をスクレイピングする"""
    # データベースが存在しない場合は初期化
    if not os.path.exists(DATABASE):
        logging.info("データベースが見つからないため、初期化します。")
        create_schema_file()
        init_db()

    logging.info("スクレイピングを開始します...")

    # まず1ページ目を取得して最終ページ番号を得る
    first_page_url = LIST_URL_TEMPLATE.format(1)
    try:
        res = requests.get(first_page_url)
        res.raise_for_status()
        soup = BeautifulSoup(res.content, 'html.parser')
        last_page = get_last_page_number(soup)
        logging.info(f"全ページ数: {last_page}")
    except requests.exceptions.RequestException as e:
        logging.error(f"最初のページの取得に失敗しました。処理を中断します。: {e}")
        return

    pages_to_scrape = last_page
    if max_pages:
        pages_to_scrape = min(last_page, max_pages)
        logging.info(f"テストモード: {pages_to_scrape} ページのみ処理します。")

    conn = get_db_connection()
    cursor = conn.cursor()

    total_processed = 0
    for page_num in range(1, pages_to_scrape + 1):
        total_processed += scrape_page(page_num, cursor)
        conn.commit() # 1ページ終わるごとにコミット

    conn.close()
    logging.info(f"スクレイピングが完了しました。合計 {total_processed} 件の新規ボイスを処理しました。")

if __name__ == '__main__':
    import sys

    if not os.path.exists(DOWNLOADS_DIR):
        os.makedirs(DOWNLOADS_DIR)

    # コマンドライン引数から最大ページ数を取得
    if len(sys.argv) > 1:
        try:
            max_pages = int(sys.argv[1])
            logging.info(f"コマンドライン引数により、最大 {max_pages} ページを処理します。")
            scrape_all(max_pages=max_pages)
        except ValueError:
            logging.error("引数は整数でページ数を指定してください。例: python scraper.py 5")
            sys.exit(1)
    else:
        # 引数がなければ全ページを対象
        logging.info("コマンドライン引数がないため、全ページを対象に処理します。")
        scrape_all()
