import os

# プロジェクトのルートディレクトリ
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# データベースファイルのパス
DATABASE = os.path.join(BASE_DIR, 'voices.db')

# 音声ファイルの保存場所
DOWNLOADS_DIR = os.path.join(BASE_DIR, 'downloads')
