import sqlite3
import os
from config import DATABASE, DOWNLOADS_DIR

def get_db_connection():
    """データベースへの接続を取得します。"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """データベースを初期化し、テーブルを作成します。"""
    # downloadsフォルダがなければ作成
    if not os.path.exists(DOWNLOADS_DIR):
        os.makedirs(DOWNLOADS_DIR)

    conn = get_db_connection()
    with open('schema.sql') as f:
        conn.executescript(f.read())
    conn.close()
    print("データベースが初期化されました。")

def create_schema_file():
    """schema.sqlファイルを作成します。"""
    schema = """
DROP TABLE IF EXISTS voices;

CREATE TABLE voices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    posted_at TEXT NOT NULL,
    duration INTEGER,
    downloaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    filepath TEXT NOT NULL,
    koe_koe_id TEXT UNIQUE NOT NULL
);

DROP TABLE IF EXISTS favorites;

CREATE TABLE favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    voice_id INTEGER NOT NULL,
    FOREIGN KEY (voice_id) REFERENCES voices (id)
);

DROP TABLE IF EXISTS tags;

CREATE TABLE tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);

DROP TABLE IF EXISTS voice_tags;

CREATE TABLE voice_tags (
    voice_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (voice_id, tag_id),
    FOREIGN KEY (voice_id) REFERENCES voices (id),
    FOREIGN KEY (tag_id) REFERENCES tags (id)
);
"""
    with open('schema.sql', 'w') as f:
        f.write(schema)
    print("schema.sqlファイルが作成されました。")

if __name__ == '__main__':
    create_schema_file()
    init_db()
