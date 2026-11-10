from flask import Flask
app = Flask(__name__)
app.secret_key = '98ce42009ef135d5e46b840d5863dd79e38d3c50835a4434870ea4799fbf83dc'
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