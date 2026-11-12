# ============================================================
# schedule.py ― カレンダーと予定を担当するファイル
# ============================================================
# 【URL】
#   /calendar                  カレンダー(?month=2026-11 で月、?day=2026-11-12 で日の詳細)
#   /event/add (POST)          予定の追加
#   /event/<id>/edit           予定の編集(GET=フォーム表示 / POST=更新)
#   /event/<id>/delete (POST)  予定の削除
#
# ※ ファイル名を calendar.py にしないのは、Python 標準の calendar(下で使っている)と
#   同じ名前になって、混ざってしまう恐れがあるため。

from flask import render_template, request, redirect, url_for, abort, session
from datetime import date, timedelta    # 今日の日付の取得、日付の形の確認、日付の計算(○日後・○日前)に使う
from calendar import Calendar    # 月のカレンダー(週ごとの日付の表)を作る

# __init__.py で作った Flask アプリ本体
from flaskr import app

# auth.py:ログインしていない人をログイン画面へ案内するデコレータ
from flaskr.auth import login_required

# db.py:ゲーム1件の取得(自分のゲームか確認する用)と、予定の追加・取得・更新・削除
from flaskr.db import get_game, add_event, get_event, update_event, delete_event
# カレンダー用:予定・購入日・日記を指定した期間で取得する / 予定フォームのゲームの一覧
from flaskr.db import get_events_between, get_purchases_between, get_diaries_between, get_game_choices


# ============================================================
# カレンダー(予定・購入日・日記を、月の表で見る)
# ============================================================
# 1か月ぶんのカレンダーに、次の3つを表示する。
#   🎮 予定 ... events テーブル(開始日〜終了日。日付をまたげる)
#   🛒 購入 ... games.purchase_date(ゲームの購入日)
#   📖 日記 ... diaries.diary_date(日記を書いた日)
#
# 日付をクリックすると、ページの下に「その日の詳細(全件)」と「予定の追加フォーム」が出る。
# 1つのマスに出すのは CAL_MAX_ITEMS 件まで。超えた分は「もっと見る」を押すと、
# その日の詳細が開く(日付をクリックしたときと同じ動き)。
#
# 他の日記・予定と同じく、どのページにも @login_required を付けている。

# 1つのマスに表示する件数の上限(これを超えると「もっと見る(+○)」になる)
CAL_MAX_ITEMS = 3


# 日付の入力を、'2026-11-12' の形の文字列に整える関数。
# 日付として正しくない(空欄など)ときは None を返す。
# ※ 日記で使った normalize_date は、正しくないとき「今日」にする。
#   予定の日付を勝手に今日にすると、間違った日に登録されてしまうので、
#   こちらは None を返して、呼び出し側でエラーにする。
def parse_date(text):
    try:
        return date.fromisoformat(text).isoformat()
    except (ValueError, TypeError):
        return None


# 予定フォーム(追加・編集で共通)の入力を読み取って、チェックする関数。
# 戻り値: (values, error)
#   values : 入力内容の辞書。画面に入力内容を戻すときにも使う。
#            'start' と 'end' は、チェックを通ったときだけ '2026-11-12' の形で入る。
#   error  : 問題があれば、画面に出すメッセージ。問題なければ None。
def read_event_form(user_id):
    title = request.form.get('title', '').strip()
    memo = request.form.get('memo', '').strip()
    start_text = request.form.get('start_date', '')
    end_text = request.form.get('end_date', '').strip()
    # type=int で数字に変換。「指定なし」(空)や数字でない値は None になる。
    game_id = request.form.get('game_id', type=int)

    values = {
        'title': title, 'memo': memo, 'game_id': game_id,
        'start_text': start_text, 'end_text': end_text,   # 入力されたままの文字(画面に戻す用)
        'start': None, 'end': None,
    }

    start = parse_date(start_text)
    end = parse_date(end_text)

    # 上から順にチェックして、最初に当てはまったものがエラーになる
    if not title:
        return values, '予定の名前を入力してください'
    if len(title) > 100:
        return values, '予定の名前は100文字以内にしてください'
    if start is None:
        return values, '開始日を入力してください'
    if end_text == '':
        end = start     # 終了日が空なら、開始日と同じ(= 1日だけの予定)
    elif end is None:
        return values, '終了日の形が正しくありません'
    if end < start:     # 'YYYY-MM-DD' の文字列は、そのまま日付の前後を比べられる
        return values, '終了日は、開始日と同じか、あとの日にしてください'
    # ゲームを選んだときは、自分のゲームか確認する(他人のゲームは指定できない)
    if game_id is not None and get_game(game_id, user_id) is None:
        return values, '選んだゲームが見つかりません'

    values['start'] = start
    values['end'] = end
    return values, None


# --- カレンダーページの表示 ( /calendar ) ---
# ?month=2026-11      … 表示する月(無ければ今月)
# ?day=2026-11-12     … 詳細を開く日(この月の日付のときだけ有効)
@app.route('/calendar')
@login_required
def calendar_page():
    user_id = session['user_id']
    today = date.today()

    # ----- (1) 表示する月を決める -----
    # first_day = その月の1日。'2026-11' に '-01' を付けて日付にする。
    # 無い・正しくない値のときは、今月にする。
    try:
        first_day = date.fromisoformat(request.args.get('month', '') + '-01')
    except ValueError:
        first_day = today.replace(day=1)
    # 極端な年(9999年など)は、日付の計算でエラーになるので今月に戻す
    if not 1900 <= first_day.year <= 2100:
        first_day = today.replace(day=1)

    year, month = first_day.year, first_day.month
    # 「来月の1日」= 1日の32日後(必ず来月に入る)の1日。
    # 月の最終日は、その前の日。前の月の1日は、「1日の前の日」の1日。
    next_first = (first_day + timedelta(days=32)).replace(day=1)
    last_day = next_first - timedelta(days=1)
    prev_first = (first_day - timedelta(days=1)).replace(day=1)

    # ----- (2) 詳細を開く日を決める -----
    # この月の日付のときだけ有効。無ければ、今月を見ているときに限り「今日」を開く。
    selected = parse_date(request.args.get('day', ''))
    if selected is not None and not (first_day <= date.fromisoformat(selected) <= last_day):
        selected = None
    if selected is None and first_day == today.replace(day=1):
        selected = today.isoformat()

    # ----- (3) この月の予定・購入日・日記を、まとめて取り出す -----
    first_iso = first_day.isoformat()
    last_iso = last_day.isoformat()
    events = get_events_between(user_id, first_iso, last_iso)
    purchases = get_purchases_between(user_id, first_iso, last_iso)
    diaries = get_diaries_between(user_id, first_iso, last_iso)

    # ----- (4) 日付ごとに振り分ける -----
    # day_data['2026-11-12'] = {'events': [...], 'purchases': [...], 'diaries': [...]}
    # という形の辞書。データのある日だけ、キーができる。
    day_data = {}

    # 指定した日の入れ物を返す。まだ無ければ、空の入れ物を作ってから返す。
    def slot(iso):
        return day_data.setdefault(iso, {'events': [], 'purchases': [], 'diaries': []})

    for event_id, title, start, end, memo, game_id, game_title in events:
        try:
            # 予定の期間のうち、この月に入っている部分だけを取り出す
            # (月をまたぐ予定は、この月の分だけを数える)
            d = max(date.fromisoformat(start), first_day)
            d_end = min(date.fromisoformat(end), last_day)
        except ValueError:
            continue    # 日付の形が壊れた予定は飛ばす(通常は起きない)
        event = {'id': event_id, 'title': title, 'start': start, 'end': end,
                 'memo': memo, 'game_id': game_id, 'game_title': game_title}
        # 期間内のすべての日に、同じ予定を入れる(= 日付をまたぐ予定が、毎日のマスに出る)
        while d <= d_end:
            slot(d.isoformat())['events'].append(event)
            d += timedelta(days=1)

    for game_id, title, purchase_date in purchases:
        slot(purchase_date)['purchases'].append({'game_id': game_id, 'title': title})

    for diary_id, game_id, game_title, diary_date, body in diaries:
        slot(diary_date)['diaries'].append({'game_id': game_id, 'game_title': game_title, 'body': body})

    # ----- (5) カレンダーの表(週 × 7日)を作る -----
    # Calendar(firstweekday=6) … 日曜始まり。
    # monthdatescalendar は、「週ごとの日付のリスト」を返す。
    # 月の最初と最後の週には、前の月・次の月の日付も入る(in_month で見分ける)。
    weeks = []
    for week in Calendar(firstweekday=6).monthdatescalendar(year, month):
        row = []
        for col, d in enumerate(week):    # col: 0=日曜 ... 6=土曜
            iso = d.isoformat()
            in_month = (d.month == month)
            cell_items = []               # このマスに出す項目(全部)

            # 前後の月のマスには、データを出さない(薄く日付だけ表示する)
            if in_month and iso in day_data:
                data = day_data[iso]
                # 並び順は「予定 → 購入 → 日記」。
                # 予定を先にして、上限を超えても見落としにくくしている。
                for e in data['events']:
                    cell_items.append({'kind': 'event', 'icon': '🎮', 'text': e['title'],
                                       'url': url_for('event_edit', event_id=e['id'])})
                for p in data['purchases']:
                    cell_items.append({'kind': 'purchase', 'icon': '🛒', 'text': p['title'],
                                       'url': url_for('detail', game_id=p['game_id'])})
                # 日記は、同じゲームなら1行にまとめる(例: 「ゼルダ(2)」)。
                # counts = {game_id: [ゲーム名, 件数]}
                counts = {}
                for dy in data['diaries']:
                    c = counts.setdefault(dy['game_id'], [dy['game_title'], 0])
                    c[1] += 1
                for game_id, (title, n) in counts.items():
                    text = title if n == 1 else f'{title}({n})'
                    cell_items.append({'kind': 'diary', 'icon': '📖', 'text': text,
                                       'url': url_for('diary', game_id=game_id)})

            row.append({
                'iso': iso,
                'day': d.day,
                'in_month': in_month,
                'col': col,
                'is_today': (d == today),
                'is_selected': (iso == selected),
                # 上限までの項目と、超えた件数(「もっと見る(+○)」に使う)
                'visible': cell_items[:CAL_MAX_ITEMS],
                'more': max(0, len(cell_items) - CAL_MAX_ITEMS),
            })
        weeks.append(row)

    # ----- (6) 開いている日の詳細 -----
    detail = None
    selected_label = ''
    if selected is not None:
        detail = day_data.get(selected, {'events': [], 'purchases': [], 'diaries': []})
        d = date.fromisoformat(selected)
        weekday = '月火水木金土日'[d.weekday()]    # weekday(): 月曜=0 ... 日曜=6
        selected_label = f'{d.year}年{d.month}月{d.day}日({weekday})'

    # ----- (7) 画面を作って返す -----
    return render_template(
        'calendar.html',
        year=year,
        month=month,
        month_key=first_day.strftime('%Y-%m'),    # '2026-11'(日付クリックのリンクに使う)
        prev_month=prev_first.strftime('%Y-%m'),
        next_month=next_first.strftime('%Y-%m'),
        weeks=weeks,
        selected=selected,
        selected_label=selected_label,
        detail=detail,
        game_choices=get_game_choices(user_id),   # 予定フォームのゲームのプルダウン
        msg=request.args.get('msg', '')           # 追加・更新・削除の結果メッセージ
    )


# --- 予定の追加 ( /event/add ) ---
# カレンダーページの下の追加フォームから届く。
@app.route('/event/add', methods=['POST'])
@login_required
def event_add():
    user_id = session['user_id']
    values, error = read_event_form(user_id)

    if error:
        # 失敗したら、カレンダーに戻ってメッセージを出す。
        # 開始日が正しく入力されていれば、その日を開く(無ければ今日)。
        day = parse_date(request.form.get('start_date', '')) or date.today().isoformat()
        return redirect(url_for('calendar_page', month=day[:7], day=day, msg=error,
                                _anchor='day-detail'))

    add_event(user_id, values['game_id'], values['title'],
              values['start'], values['end'], values['memo'])

    # 追加した予定の開始日のカレンダーへ戻る(day[:7] は '2026-11-12' から '2026-11' を取り出す)
    # _anchor='day-detail' は、URLの最後に #day-detail を付けて、詳細の位置までスクロールさせる。
    return redirect(url_for('calendar_page', month=values['start'][:7], day=values['start'],
                            msg='予定を追加しました', _anchor='day-detail'))


# --- 予定の編集 ( /event/<id>/edit ) ---
# GET  : 今の内容が入った編集フォームを表示
# POST : 入力内容をチェックして、問題なければ更新
@app.route('/event/<int:event_id>/edit', methods=['GET', 'POST'])
@login_required
def event_edit(event_id):
    user_id = session['user_id']
    # event = (id, game_id, title, start_date, end_date, memo)。自分の予定でなければ None
    event = get_event(event_id, user_id)
    if event is None:
        abort(404)

    error = None
    if request.method == 'POST':
        values, error = read_event_form(user_id)
        if error is None:
            update_event(event_id, user_id, values['game_id'], values['title'],
                         values['start'], values['end'], values['memo'])
            return redirect(url_for('calendar_page', month=values['start'][:7], day=values['start'],
                                    msg='予定を更新しました', _anchor='day-detail'))
        # エラーのときは、入力した内容を画面に戻す(入力し直さなくて済むように)
        event = (event_id, values['game_id'], values['title'],
                 values['start_text'], values['end_text'], values['memo'])

    return render_template('event_edit.html', event=event,
                           game_choices=get_game_choices(user_id), error=error)


# --- 予定の削除 ( /event/<id>/delete ) ---
# POSTのみ(他の削除と同じ考え方。URLを開いただけでは消えない)
@app.route('/event/<int:event_id>/delete', methods=['POST'])
@login_required
def event_delete(event_id):
    user_id = session['user_id']
    event = get_event(event_id, user_id)
    if event is None:
        abort(404)

    delete_event(event_id, user_id)

    # 消した予定の開始日のカレンダーへ戻る(event[3] = start_date)
    return redirect(url_for('calendar_page', month=event[3][:7], day=event[3],
                            msg='予定を削除しました', _anchor='day-detail'))