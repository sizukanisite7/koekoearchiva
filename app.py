import os
from datetime import datetime
from flask import Flask, render_template, send_from_directory, url_for
from database import get_db_connection
from config import DOWNLOADS_DIR, DATABASE

app = Flask(__name__)
app.config['DOWNLOADS_DIR'] = DOWNLOADS_DIR

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

@app.route('/')
def index():
    """Show the main page with a list of all voices."""
    conn = get_db()
    # `filepath` is the full path, we need just the filename for the URL
    # We can get it using SUBSTR and INSTR, or just os.path.basename in Python
    voices_raw = conn.execute('SELECT id, title, author, posted_at, duration, filepath, downloaded_at FROM voices ORDER BY downloaded_at DESC').fetchall()
    conn.close()

    voices = []
    for row in voices_raw:
        voice = dict(row)
        voice['file_exists'] = os.path.exists(voice['filepath'])
        # Create a URL for the audio file only if it exists
        if voice['file_exists']:
            voice['audio_url'] = url_for('download_file', filename=os.path.basename(voice['filepath']))
        else:
            voice['audio_url'] = None

        # posted_atをフォーマット
        posted_at_str = voice['posted_at']
        # マイクロ秒を削除してパース
        if '.' in posted_at_str:
            dt_object = datetime.strptime(posted_at_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
        else:
            dt_object = datetime.strptime(posted_at_str, '%Y-%m-%d %H:%M:%S')
        voice['posted_at'] = dt_object.strftime('%Y-%m-%d %H:%M')

        voices.append(voice)

    return render_template('index.html', voices=voices)

if __name__ == '__main__':
    # Ensure the downloads directory exists
    if not os.path.exists(DOWNLOADS_DIR):
        os.makedirs(DOWNLOADS_DIR)

    # Check if the database exists, if not, initialize it.
    if not os.path.exists(DATABASE):
        from database import init_db, create_schema_file
        print("データベースが見つからないため、初期化します。")
        create_schema_file()
        init_db()

    app.run(debug=True, port=5000)
