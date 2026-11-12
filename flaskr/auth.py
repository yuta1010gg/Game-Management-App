# ============================================================
# auth.py ― ユーザー登録・ログイン・ログアウトを担当するファイル
# ============================================================
# 【URL】
#   /signup                    ユーザー登録
#   /login                     ログイン
#   /logout     (POST)         ログアウト
#
# 【ログインについて】
#   ログインすると session['user_id'] に自分のIDが入る。
#   ゲームのデータは user_id で持ち主を区別し、自分のゲームだけを扱う。
#
#   このファイルの login_required は、他のファイルからも使う
#   (各ページの関数の上に @login_required と書くと、ログインしていない人を
#    ログイン画面へ案内する)。
#   ★注意:@login_required が付いているのは、一覧(games.py の index)と、
#     日記(diary.py)・カレンダー(schedule.py)のページだけ。
#     他のページはログインしていなくても開けてしまい、
#     session['user_id'] が無いのでエラー(500)になる。
#     他のページにも @login_required を付けると、ログイン画面へ案内できる。

from flask import render_template, request, redirect, url_for, session
from functools import wraps    # デコレータを作るときに使う

# パスワードの変換(ハッシュ化)と照合の道具
#   generate_password_hash : パスワードを、元に戻せない文字列に変換する
#   check_password_hash    : 入力されたパスワードが、変換済みの文字列と合うか調べる
from werkzeug.security import generate_password_hash, check_password_hash

# __init__.py で作った Flask アプリ本体。
# これを使って、下の @app.route(...) でURLと関数を結びつける。
from flaskr import app

# db.py:ユーザーの追加と、ユーザー名での取得(登録・ログイン用)
from flaskr.db import add_user, get_user_by_username


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
# ユーザー登録 ( /signup )
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
# ログイン ( /login )
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
# ログアウト ( /logout )
# ============================================================
# POSTのみ(削除と同じ考え方。URLを開いただけでログアウトさせない)
@app.route('/logout', methods=['POST'])
def logout():
    session.clear()      # 記憶していた内容をすべて消す = ログアウト
    return redirect(url_for('login', msg='ログアウトしました'))