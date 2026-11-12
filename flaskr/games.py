# ============================================================
# games.py ― ゲームの一覧・登録・更新・削除・詳細・お気に入りを担当するファイル
# ============================================================
# 【URL】
#   /                          一覧ページ(検索・絞り込み・並び替え・ページ分け)
#   /form                      新規登録フォームの表示
#   /register   (POST)         新規登録の処理
#   /game/<id>                 詳細ページ(編集フォームを兼ねる)
#   /update/<id> (POST)        更新の処理
#   /delete/<id> (POST)        削除の処理
#   /favorite/<id> (POST)      お気に入りの切り替え

from flask import render_template, request, redirect, url_for, abort, session

# SQLiteを直接操作するための標準ライブラリ
import sqlite3

# __init__.py で作った Flask アプリ本体。
# これを使って、下の @app.route(...) でURLと関数を結びつける。
from flaskr import app

# auth.py:ログインしていない人をログイン画面へ案内するデコレータ
from flaskr.auth import login_required
# images.py:画像の保存と削除
from flaskr.images import save_image, delete_image

# db.py(データベース担当のファイル)で作った関数・設定を借りている
#   DATABASE : 使用するSQLiteデータベースのファイル名
from flaskr.db import DATABASE, create_games_table
# 各マスタ(プラットフォーム・プレイ状況・ジャンル)の一覧取得と、ゲーム1件の取得
from flaskr.db import get_platforms, get_game, get_statuses, get_genres
# ゲームごとの日記の件数(一覧の「📖 3件」用)
from flaskr.db import get_diary_counts


# ============================================================
# 一覧ページ ( / )
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
    
    # ----- お気に入りのゲームを取得する -----
# お気に入り用に別途データを取得する。
# 通常のゲーム一覧とは別に取得するので、
# お気に入りのゲームは通常の一覧から消えない。

    con = sqlite3.connect(DATABASE)
    # ----- お気に入りのゲームを取得する -----
    # お気に入り用に別途データを取得する。
    # 通常のゲーム一覧とは別に取得するので、
    # お気に入りのゲームは通常の一覧から消えない。
    favorite_rows = con.execute('''
            SELECT games.id, games.title, platforms.name, statuses.name, genres.name,
            games.rating, games.play_time, games.purchase_date,
            games.memo, games.favorite, games.image
            FROM games
            JOIN platforms ON games.platform_id = platforms.id
            JOIN statuses ON games.status_id = statuses.id
            JOIN genres ON games.genre_id = genres.id
            WHERE games.user_id = ? AND games.favorite = 1
            ORDER BY games.id DESC
        ''', [user_id]).fetchall()
    
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
    
    # ★ お気に入り用のデータを作る
    favorite_games = []
    
    for row in favorite_rows:
        favorite_games.append({
            'id': row[0],
            'title': row[1],
            'platform': row[2],
            'status': row[3],
            'genre': row[4],
            'rating': row[5],
            'play_time': row[6],
            'purchase_date': row[7],
            'memo': row[8],
            'favorite': row[9],
            'image': row[10],
            'diary_count': diary_counts.get(row[0], 0)
        })

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
        favorite_games=favorite_games,
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
# 新規登録フォームの表示 ( /form )
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
# 新規登録処理 ( /register ) ― フォームからのPOSTを受け取る
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
# 削除処理 ( /delete/<id> )
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
    con.execute('DELETE FROM events WHERE game_id = ? AND user_id = ?', [game_id, user_id])
    con.execute('DELETE FROM games WHERE id = ? AND user_id = ?', [game_id, user_id])
    con.commit()
    con.close()

    # DBの削除が成功したあとで、画像ファイルも消す
    if row:
        delete_image(row[0])

    return redirect(url_for('index'))


# ============================================================
# 更新処理 ( /update/<id> ) ― 詳細ページの編集フォームからのPOST
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
# 詳細ページ ( /game/<id> ) ― 編集フォームを兼ねる
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
# お気に入りの切り替え ( /favorite/<id> )
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