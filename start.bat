@echo off
cd /d C:\Users\n29us\OneDrive\Desktop\flaskr
call .venv\Scripts\activate
start http://127.0.0.1:5000
flask --app flaskr run