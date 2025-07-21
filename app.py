from flask import Flask, request,jsonify
from functools import wraps
import uuid
import hashlib
from dotenv import load_dotenv
import os
from classes import DataBase, FileManager, RabbitMQ, ThreadRunner, ModelX, Transcribe
load_dotenv()

model=ModelX()
model.load()
db=DataBase()
file_manager=FileManager()
rabbitmq = RabbitMQ()
rabbit = RabbitMQ()
app = Flask(__name__)

def header_check(f):
    @wraps(f)
    def decorator(*args,**kwargs):
        header = request.headers.get("Authorization")

        if not header:
            return jsonify({"Ошибка":"Отсутствует токен для авторизации в запросе"}), 403
        
        sql_check="""SELECT * FROM users WHERE token = %s;"""

        check=db.execute(sql_check,(header,),fetch=True)

        if not check:
            return jsonify({"Ошибка":"Недействительный токен"}), 403
                
        data=check[0]

        request.token = header
        request.username = data["username"]

        return f(*args, **kwargs)
    return decorator

@app.route("/authorization", methods=["POST"])
def authorization():
    user=request.get_json()
    if not user:
        return jsonify({"Ошибка":"В теле запроса отсутствует JSON-Body"}), 400
    username=user.get("username")
    
    if not username:
        return jsonify({"Ошибка":"Имя для пользователя не указано"}), 400
    
    raw_token = str(uuid.uuid4())
    hashed_token = hashlib.sha256(raw_token.encode()).hexdigest()

    time_limit = os.getenv("time_limit") 

    token_data = {
        "username":username,
        "token":hashed_token,
        "time_limit": time_limit
    }

    sql_data="""CREATE TABLE IF NOT EXISTS users(
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    token TEXT NOT NULL,
    time_limit REAL)"""


    db.execute(sql_data, fetch=False)
    db.insert("users", token_data)

    return jsonify(token_data)

@app.route("/task", methods=["POST"])
@header_check
def push_task():
    allowed_types = ["audio/wav", "audio/mpeg", "audio/mp3", "audio/x-wav", "audio/flac"]
    audio_files = request.files.getlist("audio")

    if not audio_files:
        return jsonify({"Ошибка":"Ауидо не найдены"})

    token = getattr(request, "token", None)
    username = getattr(request, "username", None)

    for audio in audio_files:
        if not audio or audio.filename == "":
            continue
        audio_type=audio.content_type

        if audio_type not in allowed_types:
            return jsonify({"Ошибка":"Неподдерживаемый формат аудио"})
        
        file_manager.makedir("audio_data")
        save_path=file_manager.get_file_path("audio_data", username, audio.filename)
        audio.save(save_path)
        file_size = file_manager.get_file_size(save_path)
        file_duration = file_manager.get_audio_duration(save_path)


        task_data = {
            "username":username,
            "token":token,
            "file_path":str(save_path),
            "content_type":audio_type,
            "file_name":audio.filename,
            "status":"Quied"
        }

        rabbitmq.publish(task_data)

        sql_data="""CREATE TABLE IF NOT EXISTS task(
        id SERIAL PRIMARY KEY,
        username TEXT,
        token TEXT,
        file_path TEXT,
        file_name TEXT,
        content_type TEXT,
        status TEXT)"""
        db.execute(sql_data, fetch=False)
        db.insert("task", task_data)

    return jsonify({"Результат":"Все задачи были успешно поставлны в очередь"})



def transcriptor(file_path):
    sql_update = "UPDATE task SET status = %s WHERE file_path = %s"
    status = "processing"
    db.execute(sql_update, (status, file_path))

    to_transcription = Transcribe(model, audio_path=file_path)
    result = to_transcription.transcribe()
    print(result)

    sql_update = "UPDATE task SET status = %s WHERE file_path = %s"
    status = "done"
    db.execute(sql_update, (status, file_path))

def task_process():
    def handle_task(message):
        transcriptor(message["file_path"])

    rabbit.consume_forever(handle_task)

if __name__ == "__main__":
    transcriber=ThreadRunner(task_process)
    transcriber.start()
    app.run(host="0.0.0.0", port=5000)
    