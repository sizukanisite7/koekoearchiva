import os
import math
from datetime import datetime
from flask import Flask, render_template, send_from_directory, url_for, request
from database import get_db_connection
from config import DOWNLOADS_DIR, DATABASE

app = Flask(__name__)
app.config['DOWNLOADS_DIR'] = DOWNLOADS_DIR

# 1ページあたりの表示件数
PER_PAGE = 20

def get_db():
    """Get a database connection."""
    conn = get_db_connection()
    return conn

@app.teardown_appcontext
def close_connection(exception):
    """Close the database connection."""
    # This function is not strictly necessary for this simple app,
    # but it's good practice.
    pass

@app.route('/downloads/<path:filename>')
def download_file(filename):
    """Serve files from the downloads directory."""
    return send_from_directory(app.config['DOWNLOADS_DIR'], filename, as_attachment=False)

def format_bytes(size):
    """ファイルサイズを適切な単位にフォーマットする"""
    if size == 0:
        return "0 B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size, 1024)))
    p = math.pow(1024, i)
    s = round(size / p, 2)
    return f"{s} {size_name[i]}"

@app.route('/')
def index():
    """Show the main page with a list of all voices."""
    conn = get_db()

    # ページネーション
    page = request.args.get('page', 1, type=int)
    offset = (page - 1) * PER_PAGE

    # サマリー情報の計算
    # 総件数
    total_voices_count = conn.execute('SELECT COUNT(id) FROM voices').fetchone()[0]

    # 総再生時間と総ファイルサイズ
    all_voices_for_summary = conn.execute('SELECT duration, filepath FROM voices').fetchall()
    total_duration = sum(v['duration'] for v in all_voices_for_summary if v['duration'])
    total_filesize = sum(os.path.getsize(v['filepath']) for v in all_voices_for_summary if os.path.exists(v['filepath']))

    # ページに表示するボイスを取得
    voices_raw = conn.execute(
        'SELECT id, title, author, posted_at, duration, filepath, downloaded_at FROM voices ORDER BY downloaded_at DESC LIMIT ? OFFSET ?',
        (PER_PAGE, offset)
    ).fetchall()
    conn.close()

    voices = []
    for row in voices_raw:
        voice = dict(row)
        voice['file_exists'] = os.path.exists(voice['filepath'])
        if voice['file_exists']:
            voice['audio_url'] = url_for('download_file', filename=os.path.basename(voice['filepath']))
        else:
            voice['audio_url'] = None

        posted_at_str = voice['posted_at']
        if '.' in posted_at_str:
            dt_object = datetime.strptime(posted_at_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
        else:
            dt_object = datetime.strptime(posted_at_str, '%Y-%m-%d %H:%M:%S')
        voice['posted_at'] = dt_object.strftime('%Y-%m-%d %H:%M')

        voices.append(voice)

    # 総ページ数
    total_pages = math.ceil(total_voices_count / PER_PAGE)

    summary = {
        'total_voices': total_voices_count,
        'total_duration': total_duration,
        'total_filesize': format_bytes(total_filesize)
    }

    return render_template(
        'index.html',
        voices=voices,
        page=page,
        total_pages=total_pages,
        summary=summary
    )

if __name__ == '__main__':
    if not os.path.exists(DOWNLOADS_DIR):
        os.makedirs(DOWNLOADS_DIR)

    if not os.path.exists(DATABASE):
        from database import init_db, create_schema_file
        print("データベースが見つからないため、初期化します。")
        create_schema_file()
        init_db()

    app.run(debug=True, port=5000)
