# ============================================================
# __init__.py ― アプリの入口(Flask アプリを作って、各ファイルをつなぐ)
# ============================================================
# 【ファイルの分担】(このフォルダ flaskr の中)
#   __init__.py  アプリ本体(app)を作り、下の各ファイルを読み込む。テーブルも用意する。
#   db.py        データベース(SQLite)の操作。SQLはここにまとめてある。
#   auth.py      ユーザー登録・ログイン・ログアウト。login_required もここ。
#   games.py     ゲームの一覧・登録・更新・削除・詳細・お気に入り。
#   stats.py     統計ページ。
#   master.py    マスタ管理(プラットフォーム・ジャンルの選択肢の管理)。
#   diary.py     ゲームごとの日記。
#   schedule.py  カレンダーと予定。
#   images.py    画像の保存・削除(games.py から使う)。
#   templates/   画面(HTML)。    static/   CSS や、アップロードされた画像。
#
# 【URLと、担当するファイル】
#   /                          games.py     一覧ページ
#   /form, /register           games.py     ゲームの登録
#   /game/<id>                 games.py     詳細ページ(編集フォームを兼ねる)
#   /update/<id>, /delete/<id> games.py     更新・削除
#   /favorite/<id>             games.py     お気に入りの切り替え
#   /stats                     stats.py     統計ページ
#   /master ...                master.py    マスタ管理
#   /signup, /login, /logout   auth.py      ユーザー登録・ログイン・ログアウト
#   /game/<id>/diary ...       diary.py     日記
#   /diary/<id>/edit ...       diary.py     日記の編集・削除
#   /calendar                  schedule.py  カレンダー
#   /event/add ...             schedule.py  予定の追加・編集・削除
#
# 【GETとPOSTの使い分け】
#   GET  = 画面を見るだけ(データは変えない)
#   POST = データを変更する(登録・更新・削除)
#   → 削除などをPOSTだけにしておくと、URLを開いただけでは消えません。
# ============================================================

import os
from flask import Flask
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-key")

# 各ファイルを読み込む。
# 読み込むと、そのファイルの中の @app.route(...) が実行されて、URLが登録される。
# (必ず、上で app を作ったあとに読み込むこと。各ファイルが app を使うため)
from flaskr import auth, games, stats, masters, diary, schedule
from flaskr import db
db.create_platforms_table()   # 参照される側を先に作る
db.create_statuses_table()
db.create_genres_table()
db.create_users_table()
db.create_games_table() 
db.create_diaries_table()   # games と users を参照するので、この2つより後に作る
db.create_events_table()    # users と games を参照するので、この2つより後に作る
db.insert_default_platforms()
db.insert_default_statuses()
db.insert_default_genres()