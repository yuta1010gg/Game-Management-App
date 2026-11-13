# ============================================================
# masters.py ― マスタ管理(プラットフォーム・ジャンルの選択肢の管理)を担当するファイル
# ============================================================
# 【URL】
#   /master                              マスタ管理ページ
#   /master/<table>/add (POST)           マスタの追加
#   /master/<table>/delete/<id> (POST)   マスタの削除

from flask import render_template, request, redirect, url_for, abort

# __init__.py で作った Flask アプリ本体
from flaskr import app

# auth.py:ログインしていない人をログイン画面へ案内するデコレータ
from flaskr.auth import login_required

# db.py:MASTERS は「管理してよいテーブルの一覧(辞書)」、
# 他の3つは一覧取得・追加・削除の関数
from flaskr.db import MASTERS, get_master_items, add_master_item, delete_master_item


# ============================================================
# マスタ管理(プラットフォーム・ジャンルの選択肢の管理)
# ============================================================
# 「マスタ」とは、プルダウンの選択肢のもとになるデータのこと。
# MASTERS は db.py で定義された辞書で、管理してよいテーブルと
# その表示名(label)をまとめたもの。
# (プレイ状況は MASTERS に無いので、ここでは管理しない)

# --- マスタ管理ページの表示 ( /master ) ---
@app.route('/master')
@login_required
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
@login_required  
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
@login_required  
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