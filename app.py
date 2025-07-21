from flask import Flask, request,jsonify
from functools import wraps
import uuid
import time
from pathlib import Path
from dotenv import load_dotenv
import os
from classes import DataBase, FileManager, RabbitMQ, ThreadRunner, ModelX, Transcribe, TranscriptFormatter, TaskDownloader, ValueExistUtil
from classes import TokenGenerate
load_dotenv()

model=ModelX()
model.load()
db=DataBase()
file_manager=FileManager()
rabbitmq = RabbitMQ()
rabbit = RabbitMQ()
check_util = ValueExistUtil()
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
    generator=TokenGenerate()
    user=request.get_json()

    error=check_util.check_value(user,"В теле запроса отсутствует JSON-Body",400)
    if error:
        return error
    
    username=user.get("username")

    error=check_util.check_value(username, "Имя для пользователя не указано", 400)
    if error:
        return error
    
    hashed_token = generator.generate_token()

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
    generator=TokenGenerate()
    allowed_types = ["audio/wav", "audio/mpeg", "audio/mp3", "audio/x-wav", "audio/flac"]
    audio_files = request.files.getlist("audio")

    error=check_util.check_value(audio_files,"Ауидо не найдены", 400)
    if error:
        return error

    token = getattr(request, "token", None)
    username = getattr(request, "username", None)

    task_list=[]
    for audio in audio_files:

        if not audio or audio.filename == "":
            continue
        audio_type=audio.content_type

        if audio_type not in allowed_types:
            return jsonify({"Ошибка":"Неподдерживаемый формат аудио"}) , 400
        
        file_manager.makedir("audio_data")
        task_id = generator.generate_task_id()
        save_path = file_manager.get_file_path("audio_data", username, task_id, audio.filename)
        audio.save(save_path)
        file_size = file_manager.get_file_size(save_path)
        file_duration = file_manager.get_audio_duration(save_path)

        sql_get_remaining_time = "SELECT time_limit FROM users WHERE token = %s"
        remaining_time = db.execute(sql_get_remaining_time, (token,), fetch=True)

        if remaining_time:
            current_time = remaining_time[0]["time_limit"]
            new_time = max(0, current_time - int(file_duration))
        
        if int(file_duration) > current_time:
            return jsonify({"Ошибка": "Недостаточно времени. Осталось: {} сек, требуется: {} сек.".format(current_time, int(file_duration))}), 400

        sql_duration = "UPDATE users SET time_limit = %s WHERE token = %s"
        db.execute(sql_duration, (new_time, token))
        
        task_data = {
            "username":username,
            "token":token,
            "file_path":str(save_path),
            "content_type":audio_type,
            "file_name":audio.filename,
            "task_id" : task_id,
            "status":"Queued"
        }

        rabbitmq.publish(task_data)

        sql_data="""CREATE TABLE IF NOT EXISTS task(
        id SERIAL PRIMARY KEY,
        username TEXT,
        token TEXT,
        file_path TEXT,
        file_name TEXT,
        content_type TEXT,
        task_id TEXT,
        status TEXT)"""
        db.execute(sql_data, fetch=False)
        db.insert("task", task_data)

        response_message={
            "task_id":task_id,
            "file_name":audio.filename,
            "remaining_time" : new_time
        }

        task_list.append(response_message)

    return jsonify(task_list)

@app.route("/status", methods=["GET"])
@header_check
def get_task_status():

    token = getattr(request, "token", None)
    username = getattr(request, "username", None)

    task_id = request.args.get("task_id")
    page = int(request.args.get("page", 1))
    per_page = 10
    offset = (page - 1) * per_page

    if task_id:
        sql = """
            SELECT * FROM task
            WHERE task_id = %s AND username = %s AND token = %s
            LIMIT 1
        """

        result = db.execute(sql, params=[task_id, username, token], fetch=True)
        if not result:
            return jsonify({"Ошибка": "Задача не найдена"}), 404
        return jsonify(result[0])
    
    else:

        sql = """
            SELECT * FROM task
            WHERE username = %s AND token = %s
            ORDER BY id DESC
            LIMIT %s OFFSET %s
        """

        result = db.execute(sql, params=[username, token, per_page, offset], fetch=True)


        count_sql = """
            SELECT COUNT(*) FROM task
            WHERE username = %s AND token = %s
        """

        count_result = db.execute(count_sql, params=[username, token], fetch=True)
        total_tasks = count_result[0]['count'] if count_result else 0

        return jsonify({
            "page": page,
            "per_page": per_page,
            "total_tasks": total_tasks,
            "total_pages": (total_tasks + per_page - 1) // per_page,
            "tasks": result
        })
    
@app.route("/download", methods=["GET"])
@header_check
def download_task():
    token = getattr(request, "token", None)
    username = getattr(request, "username", None)

    task_id = request.args.get("task_id")
    file_type = request.args.get("type")

    if not task_id or not file_type:
        return jsonify({"Ошибка": "Необходимо указать task_id и тип файла (type=txt|json)"}), 400

    sql = """
        SELECT * FROM task
        WHERE task_id = %s AND username = %s AND token = %s
        LIMIT 1
    """
    task = db.execute(sql, params=[task_id, username, token], fetch=True)
    if not task:
        return jsonify({"Ошибка": "Задача не найдена или доступ запрещён"}), 404

    try:
        downloader = TaskDownloader()
        return downloader.download(username, task_id, file_type.lower())
    except FileNotFoundError as e:
        return jsonify({"Ошибка": str(e)}), 404
    except ValueError as e:
        return jsonify({"Ошибка": str(e)}), 400
    except Exception as e:
        return jsonify({"Ошибка": f"Непредвиденная ошибка: {e}"}), 500

def transcriptor(file_path,task_id):
    sql_update = "UPDATE task SET status = %s WHERE task_id = %s"
    status = "processing"
    db.execute(sql_update, (status, task_id))

    to_transcription = Transcribe(model, audio_path=file_path)
    result = to_transcription.transcribe()

    file_path = Path(file_path)
    task_folder = file_path.parent
    json_path = task_folder / (task_id.stem + ".json")
    txt_path = task_folder / (task_id.stem + ".txt")

    formatter = TranscriptFormatter(
        segments=result["segments"],
        json_path=json_path,
        txt_path=txt_path,
        start_time=time.time())

    formatter.format_segments()
    formatter.save()


    sql_update = "UPDATE task SET status = %s WHERE task_id = %s"
    status = "done"
    db.execute(sql_update, (status, task_id))

def task_process():
    def handle_task(message):
        transcriptor(message["file_path"],message["task_id"])

    rabbit.consume_forever(handle_task)

if __name__ == "__main__":
    transcriber=ThreadRunner(task_process)
    transcriber.start()
    app.run(host="0.0.0.0", port=5000)
    