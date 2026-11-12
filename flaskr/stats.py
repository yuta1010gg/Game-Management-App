# ============================================================
# stats.py ― 統計ページを担当するファイル
# ============================================================
# 【URL】
#   /stats                     統計ページ

from flask import render_template, session

# __init__.py で作った Flask アプリ本体
from flaskr import app

# db.py:統計ページ用の集計関数
from flaskr.db import get_status_counts, get_genre_counts, get_platform_counts, get_summary


# ============================================================
# 統計ページ ( /stats )
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