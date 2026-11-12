# ============================================================
# diary.py ― ゲームごとの日記を担当するファイル
# ============================================================
# 【URL】
#   /game/<id>/diary              そのゲームの日記ページ(書き込みフォーム+一覧)
#   /game/<id>/diary/add (POST)   日記の追加
#   /diary/<id>/edit              日記の編集(GET=フォーム表示 / POST=更新)
#   /diary/<id>/delete (POST)     日記の削除

from flask import render_template, request, redirect, url_for, abort, session
from datetime import date    # 今日の日付の取得や、日付の形の確認に使う

# __init__.py で作った Flask アプリ本体
from flaskr import app

# auth.py:ログインしていない人をログイン画面へ案内するデコレータ
from flaskr.auth import login_required

# db.py:日記の追加・一覧・1件取得・更新・削除と、ゲーム1件の取得
from flaskr.db import add_diary, get_diaries, get_diary, update_diary, delete_diary, get_game


# ============================================================
# 日記(ゲームごとの日記の表示・追加・編集・削除)
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