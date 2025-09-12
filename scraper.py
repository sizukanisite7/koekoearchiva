import requests
from bs4 import BeautifulSoup
import os
import sqlite3
from datetime import datetime
import re
from urllib.parse import urljoin
from config import DATABASE, DOWNLOADS_DIR
from database import get_db_connection

BASE_URL = "https://koe-koe.com/"
LIST_URL = urljoin(BASE_URL, "list.php?g=1&g2=0")

def parse_duration(duration_str):
    """再生時間（例: '1分2秒'）を秒に変換する"""
    if not duration_str:
        return None

    minutes = 0
    seconds = 0

    min_match = re.search(r'(\d+)分', duration_str)
    if min_match:
        minutes = int(min_match.group(1))

    sec_match = re.search(r'(\d+)秒', duration_str)
    if sec_match:
        seconds = int(sec_match.group(1))

    return minutes * 60 + seconds

def scrape_and_save():
    """koe-koe.comから女性ボイスを10件スクレイピングしてDBに保存する"""
    print("スクレイピングを開始します...")

    # 1. 一覧ページから詳細ページのURLを取得
    try:
        list_page_res = requests.get(LIST_URL)
        list_page_res.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"一覧ページの取得に失敗しました: {e}")
        return

    soup = BeautifulSoup(list_page_res.content, 'html.parser')

    detail_links = []
    # `div.content > a` のセレクタで投稿一覧を取得
    content_links = soup.select('div.content > a[href*="detail.php"]')
    for link in content_links:
        if len(detail_links) >= 10:
            break
        href = link.get('href')
        if href and 'detail.php' in href:
            full_url = urljoin(BASE_URL, href)
            if full_url not in detail_links:
                detail_links.append(full_url)

    print(f"{len(detail_links)}件のボイスが見つかりました。処理を開始します。")

    conn = get_db_connection()
    cursor = conn.cursor()

    # 2. 各詳細ページを処理
    for url in detail_links:
        try:
            koe_koe_id_match = re.search(r'n=(\d+)', url)
            if not koe_koe_id_match:
                continue
            koe_koe_id = koe_koe_id_match.group(1)

            # 既にDBに存在するかチェック
            cursor.execute("SELECT id FROM voices WHERE koe_koe_id = ?", (koe_koe_id,))
            if cursor.fetchone():
                print(f"ID: {koe_koe_id} は既にデータベースに存在します。スキップします。")
                continue

            print(f"処理中: {url}")
            detail_res = requests.get(url)
            detail_res.raise_for_status()
            detail_soup = BeautifulSoup(detail_res.content, 'html.parser')

            # 3. 情報を抽出
            title = detail_soup.select_one('#content_body > h2').text.strip()
            author = detail_soup.select_one('.user_name').text.strip()
            posted_at_str = detail_soup.select_one('.meta.detail .meta_item .metaIcon_up').text.strip()
            duration_str = detail_soup.select_one('.audioTime').text.strip()
            duration_sec = parse_duration(duration_str)

            # 4. 音声ファイルをダウンロード
            audio_url_template = "https://file.koe-koe.com/sound/upload/{}.mp3"
            audio_url = audio_url_template.format(koe_koe_id)

            audio_res = requests.get(audio_url)
            audio_res.raise_for_status()

            filepath = os.path.join(DOWNLOADS_DIR, f"{koe_koe_id}.mp3")
            with open(filepath, 'wb') as f:
                f.write(audio_res.content)

            print(f"  - 音声ファイルを保存しました: {filepath}")

            # 5. データベースに保存
            cursor.execute("""
                INSERT INTO voices (title, author, posted_at, duration, filepath, koe_koe_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (title, author, posted_at_str, duration_sec, filepath, koe_koe_id))

            print(f"  - データベースに保存しました: {title}")

        except requests.exceptions.RequestException as e:
            print(f"ページの取得中にエラーが発生しました ({url}): {e}")
        except Exception as e:
            print(f"処理中に予期せぬエラーが発生しました ({url}): {e}")

    conn.commit()
    conn.close()
    print("スクレイピングが完了しました。")

if __name__ == '__main__':
    # downloadsディレクトリがなければ作成
    if not os.path.exists(DOWNLOADS_DIR):
        os.makedirs(DOWNLOADS_DIR)
    scrape_and_save()
