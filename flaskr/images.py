# ============================================================
# images.py ― 画像の保存と削除を担当するファイル
# ============================================================
# ゲームの画像(ジャケット写真など)を、static/uploads フォルダに保存・削除する。
# 使うのは games.py(ゲームの登録・更新・削除)。

import os      # フォルダやファイルのパスを扱う
import uuid    # ランダムなファイル名を作る

# __init__.py で作った Flask アプリ本体
from flaskr import app

from PIL import Image

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

    # 実際に画像ファイルとして読み込めるか確認する
    try:
        image = Image.open(file)
        image.verify()
        file.seek(0)
    except Exception:
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