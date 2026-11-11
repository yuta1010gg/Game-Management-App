# ============================================================
# main.py ― 「どのURLにアクセスされたら何をするか」を決めるファイル
# ============================================================
# このアプリは「ゲーム管理アプリ」です。
# ブラウザからのリクエスト(URLへのアクセス)を受け取り、
#   ① 必要ならデータベース(SQLite)を読み書きして
#   ② HTMLテンプレート(templatesフォルダ)に値を渡して画面を作る
# という流れで動きます。
#
# 【URL一覧】
#   /                          一覧ページ(検索・絞り込み・並び替え・ページ分け)
#   /form                      新規登録フォームの表示
#   /register   (POST)         新規登録の処理
#   /game/<id>                 詳細ページ(編集フォームを兼ねる)
#   /update/<id> (POST)        更新の処理
#   /delete/<id> (POST)        削除の処理
#   /stats                     統計ページ
#   /favorite/<id> (POST)      お気に入りの切り替え
#   /master                    マスタ管理ページ(プラットフォーム・ジャンルの選択肢の管理)
#   /master/<table>/add (POST)            マスタの追加
#   /master/<table>/delete/<id> (POST)    マスタの削除
#   /signup                    ユーザー登録
#   /login                     ログイン
#   /logout     (POST)         ログアウト
#
# 【GETとPOSTの使い分け】
#   GET  = 画面を見るだけ(データは変えない)
#   POST = データを変更する(登録・更新・削除)
#   → 削除などをPOSTだけにしておくと、URLを開いただけでは消えません。
#
# 【ログインについて】
#   ログインすると session['user_id'] に自分のIDが入る。
#   ゲームのデータは user_id で持ち主を区別し、自分のゲームだけを扱う。
#   ★注意:@login_required が付いているのは、今のところ index( / )だけ。
#     他のページはログインしていなくても開けてしまい、
#     session['user_id'] が無いのでエラー(500)になる。
#     他のページにも @login_required を付けると、ログイン画面へ案内できる。
# ============================================================


# ------------------------------------------------------------
# 1. 必要な部品の読み込み(import)
# ------------------------------------------------------------

# Flaskの機能
#   render_template : HTMLテンプレートに値を埋め込んで画面を作る
#   request         : ブラウザから届いたデータ(URLの?以降やフォーム入力)を読む
#   redirect        : 別のURLへ移動させる
#   url_for         : 「関数名」からURLを作る(URLを直接書かずに済む)
#   abort           : エラー(404など)を返して処理を打ち切る
#   session         : ログイン中のユーザー情報などを、ブラウザごとに記憶しておく場所
from flask import render_template, request, redirect, url_for, abort, session
from functools import wraps    # デコレータを作るときに使う

# __init__.py で作った Flask アプリ本体。
# これを使って、下の @app.route(...) でURLと関数を結びつける。
from flaskr import app

# SQLiteを直接操作するための標準ライブラリ
import sqlite3

import os      # フォルダやファイルのパスを扱う
import uuid    # ランダムなファイル名を作る
from datetime import date    # 今日の日付を取得したり、日付の形を確認したりする

# パスワードの変換(ハッシュ化)と照合の道具
#   generate_password_hash : パスワードを、元に戻せない文字列に変換する
#   check_password_hash    : 入力されたパスワードが、変換済みの文字列と合うか調べる
from werkzeug.security import generate_password_hash, check_password_hash

# ここから下は db.py(データベース担当のファイル)で作った関数を借りている
# ユーザーの追加と、ユーザー名での取得(登録・ログイン用)
from flaskr.db import add_user, get_user_by_username
from flaskr.db import create_games_table
# 各マスタ(プラットフォーム・プレイ状況・ジャンル)の一覧取得と、ゲーム1件の取得
from flaskr.db import get_platforms, get_game, get_statuses, get_genres
# 統計ページ用の集計関数
from flaskr.db import get_status_counts, get_genre_counts, get_platform_counts, get_summary
# マスタ管理用:MASTERS は「管理してよいテーブルの一覧(辞書)」、
# 他の3つは一覧取得・追加・削除の関数
from flaskr.db import MASTERS, get_master_items, add_master_item, delete_master_item
# 日記用:追加・一覧・1件取得・更新・削除と、ゲームごとの件数
from flaskr.db import add_diary, get_diaries, get_diary, update_diary, delete_diary, get_diary_counts

# 使用するSQLiteデータベースのファイル名
# (db.py にも同じものがある。同じファイルを指している)
DATABASE = 'database.db'

# 画像の保存先フォルダ(static フォルダの中の uploads)
UPLOAD_FOLDER = os.path.join(app.static_folder, 'uploads')

# 受け付ける拡張子(これ以外のファイルは保存しない)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# アップロードできる最大サイズ(5MB)。超えるとエラー画面になる
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024


# ------------------------------------------------------------
# 画像まわりの補助関数
# ------------------------------------------------------------

# 画像を保存して、保存したファイル名を返す関数
# 画像が選ばれていない・画像ではないときは None を返す
def save_image(file):
    # 画像を選ばなかったとき、ブラウザは「ファイル名が空のファイル」を送ってくる
    if file is None or file.filename == '':
        return None

    # 拡張子(最後の「.」より後ろ)を取り出して小文字にする
    if '.' not in file.filename:
        return None
    ext = file.filename.rsplit('.', 1)[1].lower()

    # 許可した拡張子でなければ保存しない
    if ext not in ALLOWED_EXTENSIONS:
        return None

    # 保存先フォルダが無ければ作る(あれば何もしない)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # 元のファイル名は使わず、ランダムな名前にする
    # (同名ファイルの上書きや、変な文字によるトラブルを防ぐため)
    filename = uuid.uuid4().hex + '.' + ext

    file.save(os.path.join(UPLOAD_FOLDER, filename))
    return filename


# 保存済みの画像ファイルを削除する関数
# filename が None や空のとき、ファイルが存在しないときは何もしない
def delete_image(filename):
    if not filename:
        return
    path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(path):
        os.remove(path)


# ============================================================
# ログイン必須にするための「デコレータ」
# ============================================================
# 各ページの関数の上に @login_required と書くと、
# 「ログインしていなければ、ログイン画面へ移動させる」処理が付く。
def login_required(view):
    @wraps(view)    # 元の関数の名前などを引き継ぐ(url_for などが正しく動くように必要)
    def wrapped(*args, **kwargs):
        # ログイン時に session['user_id'] を入れたので、無ければ未ログイン
        if 'user_id' not in session:
            return redirect(url_for('login', msg='ログインしてください'))
        # ログイン済みなら、元のページの処理をそのまま実行する
        return view(*args, **kwargs)
    return wrapped


# ============================================================
# 2. 一覧ページ ( / )
#    このファイルでいちばん複雑な部分。順番に読むとわかりやすい。
# ============================================================
@app.route('/')
@login_required
def index():

    # ----- (1) URLのパラメータを受け取る -----
    # 例) /?q=ゼルダ&platform_id=1&order=high_rating&page=2
    # のように、URLの「?」より後ろの部分を request.args で読み取る。

    # 検索キーワード。指定がなければ '' (空文字)。
    # strip() は前後の空白を取り除く。
    q = request.args.get('q', '').strip()

    # 絞り込み用のID(プラットフォーム・プレイ状況・ジャンル)。
    # type=int で文字列を数字に変換する。
    # 指定がない/数字にできない値のときは None になる(=絞り込みなし)。
    platform_id = request.args.get('platform_id', type=int)
    status_id = request.args.get('status_id', type=int)
    genre_id = request.args.get('genre_id', type=int)

    # ----- (2) 並び順を決める -----
    # 並び順の指定。無ければ 'asc'(IDの昇順=古い順)。
    order = request.args.get('order', 'asc')

    # ユーザーから届いた文字をそのままSQLに入れるのは危険(SQLインジェクション)。
    # そこで「決めた選択肢のどれかに一致したときだけ」SQLの文章を作る。
    # (ORDER BY の部分は ? プレースホルダが使えないため、この方法を取る)
    if order == 'asc':
        # 古い順(IDが小さい順)
        order_sql = 'games.id ASC'

    elif order == 'high_rating':
        # 評価が高い順。同じ評価なら新しい登録(IDが大きい)ものを先に。
        # ※SQLiteでは NULL(未入力)は最小の値として扱われるので、DESCだと最後に来る
        order_sql = 'games.rating DESC, games.id DESC'

    elif order == 'low_rating':
        # 評価が低い順。※ASCだと NULL(評価なし)が先頭に来る
        order_sql = 'games.rating ASC, games.id DESC'

    elif order == 'favorite':
        # お気に入りを先頭に。
        # 「games.favorite = 1」は、お気に入りなら 1、そうでなければ 0 になる式。
        # DESC(大きい順)なので、1(お気に入り)が先に並ぶ。
        order_sql = 'games.favorite = 1 DESC, games.id ASC'

    elif order == 'purchase_new':
        # 購入日が新しい順。
        # 「purchase_date IS NULL」は、購入日が空なら 1、あれば 0。
        # ASC(小さい順)なので、購入日がある物が先、空の物は最後になる。
        order_sql = 'games.purchase_date IS NULL ASC,games.purchase_date DESC, games.id DESC'

    elif order == 'purchase_old':
        # 購入日が古い順(空の物は最後)
        order_sql = 'games.purchase_date IS NULL ASC,games.purchase_date ASC, games.id DESC'

    else:
        # 上のどれにも当てはまらない値のときは「IDの降順=新しい順」にする
        order_sql = 'games.id DESC'

    # ----- (3) 検索条件(WHERE句)を組み立てる -----
    # 「条件の文章」を where_list に、「? に入れる値」を params に、
    # 同じ順番で積み上げていく方式。

    # 次の2つは常に入れる。
    #   ・games.user_id = ?  → ログイン中のユーザー自身のゲームだけに絞る
    #   ・games.title LIKE ? → タイトル検索。
    #       LIKE '%ゼルダ%' は「タイトルのどこかに『ゼルダ』を含む」という意味。
    #       q が空文字なら LIKE '%%' となり、全件にマッチする(=検索しないのと同じ)。
    user_id = session['user_id']
    where_list = ['games.user_id = ?', 'games.title LIKE ?']
    params = [user_id,f'%{q}%']

    # プルダウンが選ばれているときだけ、条件を1つずつ追加する。
    # (None や 0 は False 扱いになるので、「すべて」のときは追加されない)
    if platform_id:
        where_list.append('games.platform_id = ?')
        params.append(platform_id)
    if status_id:
            where_list.append('games.status_id = ?')
            params.append(status_id)
    if genre_id:
                where_list.append('games.genre_id = ?')
                params.append(genre_id)

    # 条件を AND でつなぐ。
    # 例) 'WHERE games.user_id = ? AND games.title LIKE ? AND games.platform_id = ?'
    where_sql = 'WHERE ' + ' AND '.join(where_list)

    # ----- (4) ページ分けの計算 -----
    PER_PAGE = 5  # 1ページに表示する件数

    # ?page=2 の 2 を受け取る。無ければ1。
    page = request.args.get('page', 1, type=int)
    # 「何件目から取り出すか」。1ページ目=0件目から、2ページ目=5件目から。
    offset = (page - 1) * PER_PAGE

    # テーブルが無ければ作成する(初回アクセス時の対策)
    # ※ __init__.py で作成済みなので、実は無くても動く
    create_games_table()

    # ----- (5) データベースから一覧を取得する -----
    # games には platform_id=3 のような「数字」しか入っていない。
    # JOIN で platforms などの表と結びつけ、数字を名前(「PC」など)に置き換えて取り出す。
    con = sqlite3.connect(DATABASE)
    db_games = con.execute(f'''
        SELECT games.id, games.title, platforms.name, statuses.name, genres.name,
        games.rating, games.play_time, games.purchase_date, games.memo,games.favorite,games.image
        FROM games
        JOIN platforms ON games.platform_id = platforms.id
        JOIN statuses ON games.status_id = statuses.id
        JOIN genres ON games.genre_id = genres.id
        {where_sql}
        ORDER BY {order_sql}
        LIMIT ? OFFSET ?
    ''', params + [PER_PAGE, offset]).fetchall()
    # ↑ f文字列で {where_sql} と {order_sql} を埋め込んでいるが、
    #   どちらもプログラム側で作った固定の文章なので安全。
    #   ユーザーが入力した値(検索語・ID・件数)は ? を通して渡している。
    #   ? には上から順に値が入るので、
    #   「WHERE用の params」の後ろに「LIMIT用・OFFSET用の値」を足している。
    # LIMIT ? OFFSET ? は「offset件目から PER_PAGE 件だけ取る」という意味。

    # 条件に合う「全件数」を数える(総ページ数を出すため)。
    # LIMIT は付けない。fetchone()[0] で COUNT の数字だけ取り出す。
    total = con.execute(f'SELECT COUNT(*) FROM games {where_sql}', params).fetchone()[0]
    # 総ページ数 = 切り上げ計算。
    # 例) 11件 → (11 + 4) // 5 = 3ページ / 10件 → (10 + 4) // 5 = 2ページ
    # max(1, ...) : 0件でも「1 / 1」と表示されるように最低1にする。
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    con.close()   # 使い終わったら接続を閉じる

    # ----- (6) 取得結果を扱いやすい形に変換する -----
    # DBの結果は (1, 'ゼルダ', 'Switch', ...) のタプルで、row[1] のように
    # 番号でしか取り出せず読みにくい。
    # 辞書のリストに変換すると、HTML で game.title と書ける。
    games = []
    
    # ゲームごとの日記の件数 {game_id: 件数}。日記が無いゲームは辞書に無いので、
    # 下で .get(id, 0) として「無ければ0」にしている。
    diary_counts = get_diary_counts(user_id)

    for row in db_games:
        games.append({
                    'id': row[0],             # SELECTの1番目
                    'title': row[1],          # 2番目
                    'platform': row[2],       # プラットフォーム名(数字ではなく名前)
                    'status': row[3],         # プレイ状況名
                    'genre': row[4],          # ジャンル名
                    'rating': row[5],         # 評価(未入力なら None)
                    'play_time': row[6],      # プレイ時間
                    'purchase_date': row[7],  # 購入日(未入力なら None)
                    'memo': row[8],           # メモ
                    'favorite': row[9],        # お気に入り(1 or 0)
                    'image': row[10],          # 画像のファイル名(無ければ None)
                    'diary_count': diary_counts.get(row[0], 0)   # 日記の件数(無ければ0)
                    })

    # ----- (7) 画面を作って返す -----
    # render_template('ファイル名', 名前=値, ...) で、index.html の中から
    # {{ games }} {{ page }} のように使えるようにする。
    # q・platform_id・order などを返しているのは、
    # 検索後も入力欄やプルダウンに「前回の選択」を残して表示するため。
    return render_template(
        'index.html',
        games=games,                   # 一覧に表示するゲーム
        page=page,                     # 現在のページ番号
        total_pages=total_pages,       # 全ページ数
        q=q,                           # 検索キーワード
        platforms=get_platforms(),     # 絞り込みプルダウンの選択肢
        statuses=get_statuses(),
        genres=get_genres(),
        platform_id=platform_id,       # 現在選ばれている絞り込み条件
        status_id=status_id,
        genre_id=genre_id,
        order=order                    # 現在の並び順
        )


# ============================================================
# 3. 新規登録フォームの表示 ( /form )
# ============================================================
@app.route('/form')
def form():
    # プルダウン用の選択肢を、DBから取得する。
    # (HTMLに直書きせずDBから取るので、マスタに項目を足せば自動で反映される)
    platforms = get_platforms()
    statuses = get_statuses()
    genres = get_genres()
    return render_template(
        'form.html',
        platforms=platforms,
        statuses=statuses,
        genres=genres
    )


# ============================================================
# 4. 新規登録処理 ( /register ) ― フォームからのPOSTを受け取る
# ============================================================
@app.route('/register',methods=['post'])
def register():
    # ----- フォームの入力値を取得 -----
    # request.form は「フォームで送信された内容」。
    # (一覧で使った request.args は「URLの?以降」だった。別物なので注意)

    # request.form['title'] は、項目が無いとエラーになる(必須項目向け)
    title = request.form['title']
    platform_id = request.form['platform_id']
    status_id = request.form['status_id']
    genre_id = request.form['genre_id']

    # request.form.get(...) は、項目が無くてもエラーにならない(任意項目向け)
    # type=int : 数字に変換。空欄や数字でない値は None になる。
    rating = request.form.get('rating', type=int)
    play_time = request.form.get('play_time', type=int)
    # メモは前後の空白を取り除く。無ければ空文字。
    memo = request.form.get('memo', '').strip()
    # 購入日が空欄('')のときは None にして、DBに「空(NULL)」として保存する。
    # 「A or B」は、Aが空ならBを使う、という書き方。
    purchase_date = request.form.get('purchase_date') or None
    # チェックボックスは、チェックありのときだけ値が届き、
    # チェックなしのときは項目ごと届かない。
    # そこで「届いていれば1、届かなければ0」に変換する。
    favorite = 1 if request.form.get('favorite') else 0

    # 画像は request.files で受け取る(フォームの入力値とは別の入れ物)。
    # 保存できれば新しいファイル名、選ばれていなければ None。
    image = save_image(request.files.get('image'))

    # ----- DBに追加 -----
    con = sqlite3.connect(DATABASE)
    # 外部キー制約を有効にする(接続のたびに必要)。
    # 存在しない platform_id などを登録しようとするとエラーで止まる。
    con.execute("PRAGMA foreign_keys = ON")

    user_id = session['user_id']   # 持ち主 = ログイン中のユーザー
    # ?(プレースホルダ)を使うことでSQLインジェクションを防ぐ。
    # 列の並びと、後ろのリストの値の並びは同じ順番でなければならない。
    con.execute('INSERT INTO games (title, platform_id, status_id, genre_id, rating, memo, purchase_date, play_time,favorite,image,user_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                [title, platform_id, status_id, genre_id, rating, memo, purchase_date, play_time,favorite,image,user_id])
    con.commit() # 変更を確定(忘れると保存されない)
    con.close()

    # 登録後は一覧ページへ移動。
    # 画面を直接返さずリダイレクトにすると、ブラウザを再読み込みしても
    # 二重登録されない。
    return redirect(url_for('index'))


# ============================================================
# 5. 削除処理 ( /delete/<id> )
# ============================================================
# <int:game_id> : URLの数字部分を整数として game_id で受け取る。
#                 例) /delete/3 なら game_id = 3
# POSTのみ許可 → URLを直接開いただけでは削除されない。
@app.route('/delete/<int:game_id>', methods=['POST'])
def delete(game_id):
    user_id = session['user_id']
    con = sqlite3.connect(DATABASE)
    # 行を消すと画像のファイル名も分からなくなるので、先に控えておく
    row = con.execute('SELECT image FROM games WHERE id = ? AND user_id = ?', [game_id, user_id]).fetchone()
    # WHERE id = ? AND user_id = ? で「自分の、このIDの1件だけ」を消す。
    # (WHEREを忘れると全件消えるので注意)
    con.execute('DELETE FROM diaries WHERE game_id = ? AND user_id = ?', [game_id, user_id])
    con.execute('DELETE FROM games WHERE id = ? AND user_id = ?', [game_id, user_id])
    con.commit()
    con.close()

    # DBの削除が成功したあとで、画像ファイルも消す
    if row:
        delete_image(row[0])

    return redirect(url_for('index'))


# ============================================================
# 6. 更新処理 ( /update/<id> ) ― 詳細ページの編集フォームからのPOST
# ============================================================
@app.route('/update/<int:game_id>', methods=['POST'])
def update(game_id):
    # まず「自分のゲームか」を確認する。
    # 他人のゲームや存在しないゲームなら 404 を返して、ここで処理を終える。
    user_id = session['user_id']
    if get_game(game_id, user_id) is None:
        abort(404)

    # 編集フォームの入力値を取得(register と同じ要領)
    title = request.form['title']
    platform_id = request.form['platform_id']
    status_id = request.form['status_id']
    genre_id = request.form['genre_id']
    rating = request.form.get('rating', type=int)
    play_time = request.form.get('play_time', type=int)
    memo = request.form.get('memo', '').strip()
    purchase_date = request.form.get('purchase_date') or None
    # ※ favorite はここでは扱わない。
    #   お気に入りは一覧のチェックボックス(/favorite/<id>)で切り替える仕組みで、
    #   この更新では変更されずそのまま残る。

    # 新しい画像が選ばれていれば保存してファイル名を受け取る(無ければ None)
    new_image = save_image(request.files.get('image'))

    con = sqlite3.connect(DATABASE)
    con.execute("PRAGMA foreign_keys = ON")

    # 差し替え前の画像ファイル名を控えておく(あとで古いファイルを消すため)
    old_row = con.execute('SELECT image FROM games WHERE id = ?', [game_id]).fetchone()

    # 指定IDのゲームの内容を上書きする。
    # WHERE id = ? AND user_id = ? を付けているので、自分の、そのIDの1件だけが更新される。
    # ? の順番と、後ろのリストの順番を揃えること(最後が game_id, user_id)。
    #
    # image = COALESCE(?, image) :
    #   COALESCE は「最初の空でない値」を選ぶ関数。
    #   新しい画像があればそれに差し替え、無ければ今の画像(image)をそのまま残す。
    con.execute(
        'UPDATE games SET title = ?, platform_id = ?, status_id = ?, genre_id = ?, rating = ?, memo = ?, purchase_date = ?, play_time = ?, image = COALESCE(?, image) WHERE id = ? AND user_id = ?',
        [title, platform_id, status_id, genre_id, rating, memo, purchase_date, play_time, new_image, game_id, user_id]
    )
    con.commit()
    con.close()

    # 新しい画像に差し替えたときだけ、古い画像ファイルを消す
    if new_image and old_row:
        delete_image(old_row[0])
    return redirect(url_for('index'))


# ============================================================
# 7. 詳細ページ ( /game/<id> ) ― 編集フォームを兼ねる
# ============================================================
@app.route('/game/<int:game_id>')
def detail(game_id):
    # 指定IDのゲームを1件取得(自分のゲームでなければ None が返る)
    game = get_game(game_id, session['user_id'])
    if game is None:
        return redirect(url_for('index'))   # 存在しないid(や他人のゲーム)なら一覧へ戻す

    # 編集時のプルダウン用に、各マスタの一覧も渡す。
    # (「今どれが選ばれているか」を判定するため、game には名前ではなくIDが入っている)
    platforms = get_platforms()
    statuses = get_statuses()
    genres = get_genres()
    return render_template('detail.html', game=game, platforms=platforms,statuses=statuses,genres=genres)


# ============================================================
# 8. 統計ページ ( /stats )
# ============================================================
@app.route('/stats')
def stats():
    # db.py の関数で、ログイン中のユーザーのゲームを集計する。
    # 戻り値は [('未プレイ', 2), ('クリア済み', 3), ...] のような
    # 「(名前, 本数)」のリスト。
    user_id = session['user_id']
    status_counts = get_status_counts(user_id)       # プレイ状況ごとの本数
    genre_counts = get_genre_counts(user_id)         # ジャンルごとの本数
    platform_counts = get_platform_counts(user_id)   # プラットフォームごとの本数

    # 全体のまとめ:登録本数・合計プレイ時間・平均評価
    total, total_time, avg_rating = get_summary(user_id)
    total_time = total_time or 0   # ゲームが0本だと None になるので 0 にする

    # [('未プレイ', 2), ('クリア済み', 3), ...] を辞書に変換して、
    # 「クリア済み」の本数だけ取り出す(無ければ0)。
    cleared = dict(status_counts).get('クリア済み', 0)

    return render_template(
        'stats.html',
        total=total,
        cleared=cleared,
        total_time=total_time,
        avg_rating=avg_rating,
        status_counts=status_counts,
        genre_counts=genre_counts,
        platform_counts=platform_counts
    )


# ============================================================
# 9. お気に入りの切り替え ( /favorite/<id> )
# ============================================================
# 一覧のチェックボックスから送られる。
@app.route('/favorite/<int:game_id>', methods=['POST'])
def toggle_favorite(game_id):
    # チェックありなら 1、なしなら 0(チェックを外すと項目ごと届かないため)
    favorite = 1 if request.form.get('favorite') else 0

    con = sqlite3.connect(DATABASE)
    con.execute('UPDATE games SET favorite = ? WHERE id = ? AND user_id = ?',[favorite,game_id,session['user_id']])
    con.commit()
    con.close()

    # request.referrer は「直前に見ていたページのURL」。
    # そこへ戻すので、検索条件やページ位置を保ったまま一覧に戻れる。
    # (取得できないときは、条件なしの一覧へ)
    return redirect(request.referrer or url_for('index'))


# ============================================================
# 10. マスタ管理(プラットフォーム・ジャンルの選択肢の管理)
# ============================================================
# 「マスタ」とは、プルダウンの選択肢のもとになるデータのこと。
# MASTERS は db.py で定義された辞書で、管理してよいテーブルと
# その表示名(label)をまとめたもの。
# (プレイ状況は MASTERS に無いので、ここでは管理しない)

# --- マスタ管理ページの表示 ( /master ) ---
@app.route('/master')
def master():
    # 追加・削除の結果メッセージ(リダイレクト時にURLで受け渡される)
    msg = request.args.get('msg', '')
    sections = []
    # MASTERS の中身を1つずつ取り出し、画面で表示しやすい形に整える
    for table, info in MASTERS.items():
        sections.append({
            'table': table,                      # テーブル名(追加・削除のURLに使う)
            'label': info['label'],              # 画面に出す名前
            'rows': get_master_items(table)      # そのテーブルの項目一覧
        })
    return render_template('master.html', sections=sections, msg=msg)


# --- 追加 ( /master/<table>/add ) ---
# <table> には URL の文字列が入る。例) /master/platforms/add
@app.route('/master/<table>/add', methods=['POST'])
def master_add(table):
    # テーブル名はSQLの ? で渡せないので、SQL文に直接使うことになる。
    # そのため、ユーザーが好きな名前を指定できないよう、
    # 許可したテーブル(MASTERS)以外は404エラーにする(安全対策)。
    if table not in MASTERS:
        abort(404)

    name = request.form.get('name', '').strip()
    if not name:
        # 空欄ならメッセージ付きでマスタ管理ページへ戻す
        return redirect(url_for('master', msg='名前を入力してください'))

    # add_master_item は、追加できれば True、
    # すでに同じ名前があれば False を返す(db.py 側の仕様)
    if add_master_item(table, name):
        msg = f'「{name}」を追加しました'
    else:
        msg = f'「{name}」はすでに登録されています'
    return redirect(url_for('master', msg=msg))


# --- 削除 ( /master/<table>/delete/<id> ) ---
@app.route('/master/<table>/delete/<int:item_id>', methods=['POST'])
def master_delete(table, item_id):
    # 追加のときと同じく、許可したテーブル以外は404にする
    if table not in MASTERS:
        abort(404)

    # delete_master_item は、削除できれば True、
    # ゲームで使われている項目など、削除できなければ False を返す。
    # (使用中の項目を消すと、ゲームが参照先を失ってしまうため)
    if delete_master_item(table, item_id):
        msg = '削除しました'
    else:
        msg = 'ゲームで使われているため削除できません'
    return redirect(url_for('master', msg=msg))


# ============================================================
# 11. ユーザー登録 ( /signup )
# ============================================================
# GET  : 登録フォームを表示
# POST : 入力内容をチェックして、問題なければ users テーブルに保存
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    error = None      # 画面に出すエラーメッセージ(無ければ None)
    username = ''     # 入力し直しの手間を減らすため、ユーザー名は画面に残す

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        # パスワードは、空白も含めて入力されたとおりに扱うので strip() しない
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')

        # 上から順にチェックして、最初に当てはまったものがエラーになる。
        # すべて問題なければ、パスワードを変換(ハッシュ化)して保存する。
        # パスワードそのものをDBに保存しないのは、
        # DBの中身が漏れても元のパスワードが分からないようにするため。
        if not username or not password:
            error = 'ユーザー名とパスワードを入力してください'
        elif len(password) < 8:
            error = 'パスワードは8文字以上にしてください'
        elif password != password_confirm:
            error = 'パスワードが一致しません'
        elif add_user(username, generate_password_hash(password)):
            # 登録できた。登録後はリダイレクト(再読み込みで二重登録されないため)
            return redirect(url_for('login', msg='登録しました。ログインしてください'))
        else:
            # add_user が False = 同じユーザー名がすでにある
            error = 'そのユーザー名はすでに使われています'

    return render_template('signup.html',
                           error=error,
                           msg=request.args.get('msg', ''),
                           username=username)


# ============================================================
# 12. ログイン ( /login )
# ============================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    username = ''

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        # ユーザー名で検索(いなければ None)
        user = get_user_by_username(username)

        # user[2] は保存済みのパスワードのハッシュ。
        # check_password_hash は、入力されたパスワードを同じ方法で変換して、
        # 保存済みのハッシュと合うかを True / False で返す。
        if user is not None and check_password_hash(user[2], password):
            session.clear()                  # 前の状態を消してから
            session['user_id'] = user[0]     # ログインした人のIDを記憶する
            session['username'] = user[1]    # 画面に表示する名前も記憶する
            return redirect(url_for('index'))

        # ユーザー名が無い場合も、パスワードが違う場合も、同じメッセージにする
        # (「このユーザー名は存在する」と、他人に教えてしまわないため)
        error = 'ユーザー名またはパスワードが違います'

    return render_template('login.html',
                           error=error,
                           msg=request.args.get('msg', ''),
                           username=username)


# ============================================================
# 13. ログアウト ( /logout )
# ============================================================
# POSTのみ(削除と同じ考え方。URLを開いただけでログアウトさせない)
@app.route('/logout', methods=['POST'])
def logout():
    session.clear()      # 記憶していた内容をすべて消す = ログアウト
    return redirect(url_for('login', msg='ログアウトしました'))


# ============================================================
# 14. 日記(ゲームごとの日記の表示・追加・編集・削除)
# ============================================================
# 1つのゲームに、日記を何件でも書ける(同じ日に何回書いてもよい)。
# どのページにも @login_required を付けて、ログインしていない人は入れないようにしている。
# 他の人のゲーム・日記は、db.py 側が user_id で絞っているので取得できない(404にする)。

# 日付の入力を、'2026-11-11' の形の文字列に整える関数
# 空欄や、日付として正しくない文字が届いたときは「今日」にする。
# (画面では日付入力欄を使うが、送信内容は自由に書き換えられるため、念のため確認する)
def normalize_date(text):
    try:
        return date.fromisoformat(text).isoformat()
    except (ValueError, TypeError):    # 日付にできない / 項目が届いていない(None)
        return date.today().isoformat()
    
# --- 日記ページの表示 ( /game/<id>/diary ) ---
# 上に「書き込みフォーム」、下に「これまでの日記の一覧」を出す。
@app.route('/game/<int:game_id>/diary')
@login_required
def diary(game_id):
    user_id = session['user_id']
    # 自分のゲームか確認する(他人のゲームや存在しないゲームなら404)
    game = get_game(game_id, user_id)
    if game is None:
        abort(404)

    return render_template(
        'diary.html',
        game=game,                                  # ゲーム名などを画面に出すため
        diaries=get_diaries(game_id, user_id),      # 日記の一覧(新しい順)
        today=date.today().isoformat(),             # 日付入力欄の初期値(今日)
        msg=request.args.get('msg', '')             # 追加・更新・削除の結果メッセージ
    )

# --- 日記の追加 ( /game/<id>/diary/add ) ---
@app.route('/game/<int:game_id>/diary/add', methods=['POST'])
@login_required
def diary_add(game_id):
    user_id = session['user_id']
    if get_game(game_id, user_id) is None:
        abort(404)

    # 本文は前後の空白を取り除く。空(空白だけも含む)なら保存しない。
    body = request.form.get('body', '').strip()
    if not body:
        return redirect(url_for('diary', game_id=game_id, msg='本文を入力してください'))

    diary_date = normalize_date(request.form.get('diary_date'))
    add_diary(game_id, user_id, diary_date, body)

    # 追加後は日記ページへ戻る(リダイレクトなので、再読み込みしても二重登録されない)
    return redirect(url_for('diary', game_id=game_id, msg='日記を追加しました'))


# --- 日記の編集 ( /diary/<id>/edit ) ---
# GET  : 今の内容が入った編集フォームを表示
# POST : 入力内容をチェックして、問題なければ更新
@app.route('/diary/<int:diary_id>/edit', methods=['GET', 'POST'])
@login_required
def diary_edit(diary_id):
    user_id = session['user_id']
    # entry = (id, game_id, diary_date, body)。自分の日記でなければ None
    entry = get_diary(diary_id, user_id)
    if entry is None:
        abort(404)

    game_id = entry[1]
    game = get_game(game_id, user_id)    # 画面にゲーム名を出す・戻り先に使う
    if game is None:
        abort(404)

    error = None
    if request.method == 'POST':
        body = request.form.get('body', '').strip()
        diary_date = normalize_date(request.form.get('diary_date'))
        if not body:
            error = '本文を入力してください'
            # 画面に戻したとき、選んだ日付が元に戻らないよう entry を入力内容で作り直す
            entry = (diary_id, game_id, diary_date, body)
        else:
            update_diary(diary_id, user_id, diary_date, body)
            return redirect(url_for('diary', game_id=game_id, msg='日記を更新しました'))

    return render_template('diary_edit.html', game=game, entry=entry, error=error)

# --- 日記の削除 ( /diary/<id>/delete ) ---
# POSTのみ(ゲームの削除と同じ考え方。URLを開いただけでは消えない)
@app.route('/diary/<int:diary_id>/delete', methods=['POST'])
@login_required
def diary_delete(diary_id):
    user_id = session['user_id']
    entry = get_diary(diary_id, user_id)
    if entry is None:
        abort(404)

    delete_diary(diary_id, user_id)

    # 消したあとは、その日記があったゲームの日記ページへ戻る(entry[1] = game_id)
    return redirect(url_for('diary', game_id=entry[1], msg='日記を削除しました'))
