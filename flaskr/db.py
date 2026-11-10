# ============================================================
# db.py ― データベース(SQLite)の操作を担当するファイル
# ============================================================
# main.py(接客係)から頼まれて、データの作成・取得・追加・削除をする
# 「倉庫の管理人」の役目です。
#
# 【このアプリのテーブル(表)は5つ】
#
#   platforms ─┐   選択肢のもとになる表(マスタ表)
#   statuses  ─┼─→ games   ← ゲーム本体の表
#   genres    ─┤
#   users     ─┘            ← ログイン用のユーザー表(ゲームの持ち主)
#
#   ・platforms : Switch, PS5 などのプラットフォーム
#   ・statuses  : 未プレイ, プレイ中 などのプレイ状況
#   ・genres    : RPG, アクション などのジャンル
#   ・users     : ユーザー名と、パスワードを変換した文字列(ハッシュ)
#   ・games     : ゲームの情報。プラットフォームなどは「名前」ではなく
#                 「ID(数字)」で持つ。
#                 → 名前の表記ゆれを防げ、名前を直すときもマスタ表の1か所で済む。
#
# 【どの関数も基本の流れは同じ】
#   con = sqlite3.connect(DATABASE)   ① DBファイルに接続(無ければ自動で作られる)
#   con.execute(...)                  ② SQLを実行
#   con.commit()                      ③ 変更を確定(書き込みのときだけ必要)
#   con.close()                       ④ 接続を閉じる
# ============================================================

import sqlite3

# 使用するSQLiteデータベースのファイル名(main.py と同じファイルを指す)
DATABASE = 'database.db'


# ============================================================
# 1. games テーブル(ゲーム本体)
# ============================================================

# games テーブルを作る
def create_games_table():
    con = sqlite3.connect(DATABASE)
    # 外部キー制約を有効にする。
    # SQLiteは初期状態では外部キーのチェックが無効で、接続のたびにONにする必要がある。
    # (ただし「テーブルを作るだけ」の処理では実質的な効果はない。
    #  本当に効くのは INSERT / UPDATE をする側。)
    con.execute("PRAGMA foreign_keys = ON")
    # IF NOT EXISTS : すでにテーブルがあればエラーにせず何もしない
    # (何度呼び出しても安全。main.py の index() で毎回呼ばれている)
    #
    # ★注意:すでにテーブルがある場合、この文は「何もしない」ので、
    #   あとから列(rating など)を足しても既存のDBには反映されない。
    #   既存のDBに列を足すには ALTER TABLE を使うか、database.db を消して作り直す。
    con.execute("""
        CREATE TABLE IF NOT EXISTS games(
                id INTEGER PRIMARY KEY AUTOINCREMENT,   -- 自動で 1,2,3... と振られる番号
                title TEXT NOT NULL,                    -- タイトル(必須)
                platform_id INTEGER NOT NULL,           -- platforms表のID(必須)
                status_id INTEGER NOT NULL,             -- statuses表のID(必須)
                genre_id INTEGER NOT NULL,              -- genres表のID(必須)
                rating INTEGER,                         -- 評価(NOT NULLが無い=未入力OK)
                memo TEXT,                              -- メモ(未入力OK)
                purchase_date TEXT,                     -- 購入日(文字列で保存。未入力OK)
                play_time INTEGER,                      -- プレイ時間(未入力OK)
                favorite INTEGER NOT NULL DEFAULT 0,    -- お気に入り(1=はい / 0=いいえ)
                image TEXT,                             -- 画像のファイル名(未設定ならNULL)
                user_id INTEGER,                        -- 持ち主(usersテーブルのID)
                -- FOREIGN KEY(外部キー):
                -- 「この列には、相手の表に存在するIDしか入れられない」という決まり。
                -- 存在しないプラットフォームIDのゲームを作れなくする。
                FOREIGN KEY (platform_id) REFERENCES platforms(id),
                FOREIGN KEY (status_id) REFERENCES statuses(id),
                FOREIGN KEY (genre_id) REFERENCES genres(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
    con.commit()   # 変更を確定
    con.close()    # 接続を閉じる


# ============================================================
# 2. platforms(プラットフォーム)
# ============================================================

# platforms テーブルを作る
def create_platforms_table():
    con = sqlite3.connect(DATABASE)
    con.execute("PRAGMA foreign_keys = ON")

    # name に UNIQUE を付けているので、同じ名前を2つ登録できない。
    # これが「初期データの重複防止」や「マスタ追加時の重複チェック」の土台になる。
    con.execute("""
        CREATE TABLE IF NOT EXISTS platforms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    """)

    con.commit()
    con.close()


# プラットフォームの初期データを登録する
def insert_default_platforms():
    con = sqlite3.connect(DATABASE)

    # 「テーブルが空のときだけ初期データを入れる」ための判定。
    # 空のときだけにしているのは、マスタ管理ページで初期の項目を消しても、
    # アプリを起動するたびに復活してしまうのを防ぐため。
    #
    # ★注意(バグの可能性が高い箇所)★
    # 調べているのが genres になっている。platforms にするのが正しいはず。
    #   ・初回起動: genres がまだ空 → 0件なので platforms が登録される(偶然動く)
    #   ・2回目以降: genres に4件ある → 判定が False になり何も入らない
    #   ・genres を全部消したあとで起動すると、platforms の初期データが復活してしまう
    # 正しくは  SELECT COUNT(*) FROM platforms
    if con.execute('SELECT COUNT(*) FROM genres').fetchone()[0] == 0:
    # 初期データとして登録するプラットフォーム名
        for name in ['Switch', 'PS5', 'PC', 'Xbox','その他']:
            # name は UNIQUE なので、INSERT OR IGNORE なら何度実行しても重複しない
            # (OR IGNORE = 重複などでエラーになる行は、エラーにせず無視する)
            con.execute('INSERT OR IGNORE INTO platforms (name) VALUES (?)', [name])
    con.commit()
    con.close()


# プラットフォーム一覧を取得する(フォームのプルダウン用)
# 戻り値: [(id, name), ...] のリスト  例: [(1, 'Switch'), (2, 'PS5'), ...]
def get_platforms():
    con = sqlite3.connect(DATABASE)
    # fetchall() は、結果の「全行」をリストで返す
    rows = con.execute('SELECT id, name FROM platforms ORDER BY id').fetchall()
    con.close()
    return rows
    # 読み取りだけなので commit() は不要


# ============================================================
# 3. statuses(プレイ状況)
# ============================================================

# statuses テーブルを作る
def create_statuses_table():
    con = sqlite3.connect(DATABASE)
    con.execute("PRAGMA foreign_keys = ON")

    con.execute("""
        CREATE TABLE IF NOT EXISTS statuses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    """)

    con.commit()
    con.close()


# プレイ状況の初期データを登録する
def insert_default_statuses():
    con = sqlite3.connect(DATABASE)
    # プレイ状況はマスタ管理ページで増減しない(MASTERS に無い)ので、
    # 「空のときだけ」の判定は不要。毎回 INSERT OR IGNORE で足りないものを補う。
    for name in ['未プレイ', 'プレイ中', 'クリア済み', '中断']:
        # name は UNIQUE なので、INSERT OR IGNORE なら何度実行しても重複しない
        con.execute('INSERT OR IGNORE INTO statuses (name) VALUES (?)', [name])
    con.commit()
    con.close()


# プレイ状況一覧を取得する(プルダウン用)
def get_statuses():
    con = sqlite3.connect(DATABASE)
    rows = con.execute('SELECT id, name FROM statuses ORDER BY id').fetchall()
    con.close()
    return rows


# ============================================================
# 4. genres(ジャンル)
# ============================================================

# genres テーブルを作る
def create_genres_table():
    con = sqlite3.connect(DATABASE)
    con.execute("PRAGMA foreign_keys = ON")

    con.execute("""
        CREATE TABLE IF NOT EXISTS genres (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    """)

    con.commit()
    con.close()


# ジャンルの初期データを登録する
def insert_default_genres():
    con = sqlite3.connect(DATABASE)
    # genres が 0件のときだけ、初期データを入れる。
    # (マスタ管理ページで消した初期ジャンルが、起動のたびに復活しないようにするため)
    if con.execute('SELECT COUNT(*) FROM genres').fetchone()[0] == 0:
        for name in ['RPG', 'アクション', 'シミュレーション', 'スポーツ']:
            # name は UNIQUE なので、INSERT OR IGNORE なら何度実行しても重複しない
            con.execute('INSERT OR IGNORE INTO genres (name) VALUES (?)', [name])
    con.commit()
    con.close()


# ジャンル一覧を取得する(プルダウン用)
def get_genres():
    con = sqlite3.connect(DATABASE)
    rows = con.execute('SELECT id, name FROM genres ORDER BY id').fetchall()
    con.close()
    return rows


# ============================================================
# 5. ゲーム1件の取得(詳細・編集ページ用)
# ============================================================

# 指定したIDのゲームを1件取得する。
# user_id も条件に入れているので、他の人のゲームは取得できない(= None になる)。
#
# 戻り値: 次の順番のタプル(該当するゲームがなければ None)
#   (id, title, platform_id, status_id, genre_id, rating, memo, purchase_date, play_time, image)
#    [0]  [1]       [2]          [3]       [4]      [5]    [6]       [7]          [8]       [9]
# ※ 一覧(main.py の index)で使う順番とは違うので注意。
# ※ favorite は含まれていない(お気に入りは一覧のチェックボックスで切り替えるため)。
# ※ ここで返すのは名前ではなく「ID」。編集フォームのプルダウンで
#    「今どれが選ばれているか」を判定するにはIDが必要なため。
# main.py の detail() と update() で、None かどうかを判定している。
def get_game(game_id,user_id):
    con = sqlite3.connect(DATABASE)
    row = con.execute(
        'SELECT id, title, platform_id, status_id, genre_id, rating, memo, purchase_date, play_time, image FROM games WHERE id = ? AND user_id = ?',
        [game_id,user_id]   # ? に入る値(SQLインジェクション対策)
    ).fetchone() # 1件だけ取得(複数行ではなく1行)。無ければ None
    con.close()
    return row


# ============================================================
# 6. 統計ページ用の集計
# ============================================================
# 3つの get_◯◯_counts は、ほぼ同じ作りです。
#
#   FROM statuses LEFT JOIN games ON games.status_id = statuses.id
#   → 「statuses を主役にして、使っている games を結びつける」。
#     LEFT JOIN なので、1本もゲームが無い項目も消えずに残る(本数は 0)。
#     (普通の JOIN だと、ゲームが0本の項目は結果から消えてしまう)
#
#   AND games.user_id = ?
#   → 「ログイン中のユーザーのゲームだけ」に絞る。
#     WHERE ではなく ON の中に書くのがポイント。
#     WHERE に書くと、ゲームが0本の項目が消えてしまうため。
#
#   GROUP BY statuses.id
#   → 項目ごとにグループ分けして、グループ内の行数を数える。
#
#   COUNT(games.id)
#   → 結びついたゲームの数。ゲームが無いと games.id は空なので 0 と数えられる。
#     (COUNT(*) だと、ゲームが無い項目でも「1行ある」と数えて 1 になってしまうため、
#      列を指定して数えている)

# プレイ状況ごとの本数を取得
# 戻り値: [('未プレイ', 2), ('プレイ中', 1), ...]
def get_status_counts(user_id):
    con = sqlite3.connect(DATABASE)
    rows = con.execute('''
        SELECT statuses.name,COUNT(games.id)
        FROM statuses
        LEFT JOIN games ON games.status_id = statuses.id AND games.user_id = ?
        GROUP BY statuses.id
        ORDER BY statuses.id
    ''',[user_id]).fetchall()
    con.close()
    return rows


# ジャンルごとの本数を取得
# 戻り値: [('RPG', 3), ('アクション', 0), ...]
def get_genre_counts(user_id):
    con = sqlite3.connect(DATABASE)
    rows = con.execute('''
    SELECT genres.name, COUNT(games.id)
    FROM genres
    LEFT JOIN games ON games.genre_id = genres.id AND games.user_id = ?
    GROUP BY genres.id
    ORDER BY genres.id                   
    ''',[user_id]).fetchall()
    con.close()
    return rows


# プラットフォームごとの本数を取得
# 戻り値: [('Switch', 4), ('PS5', 1), ...]
def get_platform_counts(user_id):
    con = sqlite3.connect(DATABASE)
    rows = con.execute('''
    SELECT platforms.name,COUNT(games.id)
    FROM platforms
    LEFT JOIN games ON games.platform_id = platforms.id AND games.user_id = ?
    GROUP BY platforms.id
    ORDER BY platforms.id
    ''',[user_id]).fetchall()
    con.close()
    return rows


# 全体のまとめを取得
# 戻り値: (登録本数, プレイ時間の合計, 評価の平均) の1行
#   ・ゲームが0本のとき、SUM と AVG は None になる(main.py で 0 に直している)
#   ・AVG(rating) は、評価が未入力(NULL)のゲームを除いて平均する
def get_summary(user_id):
    con =sqlite3.connect(DATABASE)
    row =con.execute(
        'SELECT COUNT(*),SUM(play_time),AVG(rating) FROM games WHERE user_id = ?',
    [user_id]).fetchone()
    con.close()
    return row


# ============================================================
# 7. マスタ管理(ジャンル・プラットフォームの追加と削除)
# ============================================================

# 管理できるマスタの一覧。
#   キー      = テーブル名
#   'label'   = 画面に出す名前
#   'column'  = games テーブル側で、そのマスタを参照している列名
# プレイ状況(statuses)はここに無いので、管理画面からは増減できない。
#
# この辞書は「安全の関門」にもなっている。下の関数はテーブル名をSQL文に
# 直接埋め込む(テーブル名は ? で渡せないため)ので、
# main.py 側で「table が MASTERS にあるか」を必ず確認してから呼んでいる。
MASTERS = {
    'genres': {'label': 'ジャンル', 'column': 'genre_id'},
    'platforms': {'label': 'プラットフォーム', 'column': 'platform_id'},
}


# 項目一覧と「使われているゲームの本数」を取得
# 戻り値: [(id, 名前, 本数), ...]
# 本数が 0 の項目だけ、画面で削除できる(使用中のものは消せない)。
# ※ マスタは全ユーザー共通なので、本数は「全ユーザーの合計」。
def get_master_items(table):
    # 例) table='genres' なら column='genre_id'
    column = MASTERS[table]['column']
    con = sqlite3.connect(DATABASE)
    # f文字列で table と column を埋め込んでいる(どちらも MASTERS 由来で安全)。
    # 「FROM genres AS m」の AS m は、表に m という短い別名を付ける書き方。
    # LEFT JOIN + COUNT(games.id) で、「その項目を使っているゲームの数」を数える
    # (統計の集計と同じ考え方)。
    rows = con.execute(f'''
        SELECT m.id, m.name, COUNT(games.id)
        FROM {table} AS m
        LEFT JOIN games ON games.{column} = m.id
        GROUP BY m.id
        ORDER BY m.id
    ''').fetchall()
    con.close()
    return rows


# 項目を追加する。成功なら True、名前がかぶっていたら False
def add_master_item(table, name):
    con = sqlite3.connect(DATABASE)
    try:
        # 名前は ? で渡す(ユーザー入力なので)
        con.execute(f'INSERT INTO {table} (name) VALUES (?)', [name])
        con.commit()
        return True
    except sqlite3.IntegrityError:    # UNIQUE 制約に違反したときのエラー
        return False
    finally:
        # finally は、成功しても失敗しても必ず実行される。
        # return の前でも実行されるので、接続の閉じ忘れを防げる。
        con.close()


# 項目を削除する。成功なら True、使用中で消せないなら False
def delete_master_item(table, item_id):
    column = MASTERS[table]['column']
    con = sqlite3.connect(DATABASE)
    # まず「このIDを使っているゲームが何本あるか」を数える
    used = con.execute(
        f'SELECT COUNT(*) FROM games WHERE {column} = ?', [item_id]
    ).fetchone()[0]
    if used > 0:
        # 1本でも使われていたら削除しない。
        # (消すと、存在しない項目を指すゲームができてしまうため)
        con.close()
        return False
    con.execute(f'DELETE FROM {table} WHERE id = ?', [item_id])
    con.commit()
    con.close()
    return True


# ============================================================
# 8. users(ログイン用のユーザー情報)
# ============================================================

# users テーブルを作る
def create_users_table():
    con = sqlite3.connect(DATABASE)
    con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,      -- ユーザー名(同じ名前は登録できない)
            password_hash TEXT NOT NULL         -- パスワードそのものではなく、変換した文字列
        )
    """)
    con.commit()
    con.close()


# ユーザーを追加する。成功なら True、ユーザー名がかぶっていたら False
# password_hash には、変換済みのパスワードを渡す(main.py の signup() で変換している)。
def add_user(username, password_hash):
    con = sqlite3.connect(DATABASE)
    try:
        con.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)',
                    [username, password_hash])
        con.commit()
        return True
    except sqlite3.IntegrityError:    # UNIQUE 制約に違反したときのエラー
        return False
    finally:
        con.close()


# ユーザー名からユーザーを1件取得する
# 戻り値: (id, username, password_hash) のタプル。いなければ None
def get_user_by_username(username):
    con = sqlite3.connect(DATABASE)
    row = con.execute(
        'SELECT id, username, password_hash FROM users WHERE username = ?',
        [username]
    ).fetchone()
    con.close()
    return row