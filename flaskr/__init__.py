import os
from flask import Flask
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-key")
import flaskr.main

from flaskr import db
db.create_platforms_table()   # 参照される側を先に作る
db.create_statuses_table()
db.create_genres_table()
db.create_users_table()
db.create_games_table() 
db.insert_default_platforms()
db.insert_default_statuses()
db.insert_default_genres()