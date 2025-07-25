from flask import Flask, request,jsonify
from classes import DataBase, FileManager, RabbitMQ, ThreadRunner, ModelX, Transcribe, Logger
from classes import TokenGenerate, TranscriptFormatter, TaskDownloader, ValueExistUtil, SwaggerDocs
from swagger import register_swagger_path
from functools import wraps
import time
import math
import json
from pathlib import Path
from dotenv import load_dotenv
import os
load_dotenv()


model=ModelX()
model.load()
db=DataBase()
file_manager=FileManager()
rabbitmq = RabbitMQ()
rabbit = RabbitMQ()
check_util = ValueExistUtil()
logger_app=Logger("app").get_logger()
logger_transcription=Logger("transcription").get_logger()

app = Flask(__name__)

swagger=SwaggerDocs(app)
swagger.add_tag("Авторизация", "Метод для входа и получения токенов")
swagger.add_tag("Задачи", "Создание или загрузка задачи")
swagger.add_tag("Статусы", "Просмотр статусов задач")


logger_app.info("Инициализация таблиц в Postgres")
db.start_initial()
logger_app.info("Таблицы успешно инициализированы")
logger_app.info("Таблицы успешно инициализированы")
register_swagger_path(swagger)


def admin_check(f):
    @wraps(f)
    def decorator_admin (*args,**kwargs):
        header = request.headers.get("Authorization")

        if not header:
            return jsonify({"error":"Отсутствует токен для авторизации в запросе"}), 401
        
        if header!="Bearer ubsfaU4EoHyPIO9EgCyozFYVGmDKrqiWOomzXS4v2blZtm38PXTSjwx5hCxR2o":
            return jsonify({"error":"Доступ запрещен"}), 401

        return f(*args, **kwargs)
    return decorator_admin


def header_check(f):
    @wraps(f)
    def decorator(*args,**kwargs):
        header = request.headers.get("Authorization")

        if not header:
            return jsonify({"error":"Отсутствует токен для авторизации в запросе"}), 401
        
        sql_check="""SELECT * FROM users WHERE token = %s;"""

        check=db.execute(sql_check,(header,),fetch=True)

        if not check:
            return jsonify({"error":"Недействительный токен"}), 401
                
        data=check[0]

        request.user_id = data["id"]
        request.username = data["username"]
        logger_app.info("Декоратор успешно проверил токен")

        return f(*args, **kwargs)
    return decorator

@app.route("/authorization", methods=["POST"])
@admin_check
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
    
    check_sql = "SELECT 1 FROM users WHERE username = %s LIMIT 1"
    dublicate = db.execute(check_sql, params=[username], fetch=True)

    if dublicate:
        return jsonify({"error": "Пользователь с таким именем уже существует"}), 400
    
    hashed_token = generator.generate_token()
    time_limit = os.getenv("time_limit") 

    token_data = {
        "username":username,
        "token":f"Bearer {hashed_token}",
        "time_limit": time_limit
    }

    message={
        "username":username,
        "token":hashed_token,
        "time_limit": time_limit
    }

    db.insert("users", token_data)

    return jsonify(message)

@app.route("/task", methods=["POST"])
@header_check
def push_task():
    generator=TokenGenerate()
    allowed_types = ["audio/wav", "audio/mpeg", "audio/mp3", "audio/x-wav", "audio/flac", "audio/ogg", "audio/mp4", "audio/aac", "audio/wma"]
    audio_files = request.files.getlist("audio")
    diarization_flag = request.form.get("with_diarization", "false").lower() == "true"

    error=check_util.check_value(audio_files,"Ауидо не найдены", 400)
    if error:
        return error

    user_id = getattr(request, "user_id", None)
    username = getattr(request, "username", None)

    task_list=[]
    for audio in audio_files:

        if not audio or audio.filename == "":
            continue
        audio_type=audio.content_type

        if audio_type not in allowed_types:
            return jsonify({"error":"Неподдерживаемый формат аудио"}) , 400
        
        file_manager.makedir("audio_data")
        task_id = generator.generate_task_id()
        save_path = file_manager.get_file_path("audio_data", username, task_id, audio.filename)
        audio.save(save_path)
        file_size = file_manager.get_file_size(save_path)
        file_duration = file_manager.get_audio_duration(save_path)

        sql_get_remaining_time = "SELECT time_limit FROM users WHERE id = %s"
        remaining_time = db.execute(sql_get_remaining_time, (user_id,), fetch=True)

        if remaining_time:
            current_time = remaining_time[0]["time_limit"]
            new_time = max(0, current_time - math.ceil(file_duration))
        
        if math.ceil(file_duration) > current_time:
            return jsonify({"error": "Недостаточно времени. Осталось: {} сек, требуется: {} сек.".format(current_time, math.ceil(file_duration))}), 400


        task_data = {
            "username":username,
            "user_id":user_id,
            "file_path":str(save_path),
            "content_type":audio_type,
            "file_name":audio.filename,
            "audio_duration_second" : file_duration,
            "with_diarization" : diarization_flag,
            "task_id" : task_id,
            "status": {"code": 80, "message": "Задача поставлена в очередь"}
        }

        rabbitmq.publish(task_data)

        db.insert("task", task_data)

        response_message={
            "task_id":task_id,
            "file_name":audio.filename,
            "audio_duration_second" : math.ceil(file_duration),
            "remaining_time" : remaining_time[0]["time_limit"]
        }

        task_list.append(response_message)

    return jsonify(task_list)

@app.route("/download", methods=["GET"])
@header_check
def download_task():
    user_id = getattr(request, "user_id", None)
    username = getattr(request, "username", None)

    task_id = request.args.get("task_id")
    file_type = request.args.get("type")

    if not task_id or not file_type:
        return jsonify({"error": "Необходимо указать task_id и тип файла (type=txt|json)"}), 400

    sql = """
        SELECT * FROM task
        WHERE task_id = %s AND username = %s AND user_id = %s
        LIMIT 1
    """
    task = db.execute(sql, params=[task_id, username, user_id], fetch=True)
    if not task:
        return jsonify({"error": "Задача не найдена"}), 404

    try:
        downloader = TaskDownloader()
        logger_app.info(f"Запрос на загрузку файла от {username}")
        return downloader.download(username, task_id, file_type.lower())
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Непредвиденная error: {e}"}), 500
    
@app.route("/status", methods=["GET"])
@header_check
def get_tasks_by_status():
    user_id = getattr(request, "user_id", None)
    username = getattr(request, "username", None)

    status_map = {
        "queue":   {"code": 80,  "message": "Задача поставлена в очередь"},
        "process": {"code": 100, "message": "Задача в процессе обработки"},
        "done":    {"code": 200, "message": "Задача успешно завершена и готова к загрузке"},
        "error":   {"code": 501, "message": "Транскрипция завершена с ошибкой"},
    }

    status_name = (request.args.get("status") or "").lower()
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 10))
    offset = (page - 1) * per_page


    if not status_name:
        sql = """
            SELECT task_id,
                   status->>'code'    AS status_code,
                   status->>'message' AS status_message
            FROM task
            WHERE username = %s AND user_id = %s
            ORDER BY id DESC
            LIMIT %s OFFSET %s
        """
        result = db.execute(sql, params=[username, user_id, per_page, offset], fetch=True)

        count_sql = """
            SELECT COUNT(*) FROM task
            WHERE username = %s AND user_id = %s
        """
        count_result = db.execute(count_sql, params=[username, user_id], fetch=True)
        total_tasks = count_result[0]['count'] if count_result else 0

        return jsonify({
            "page": page,
            "per_page": per_page,
            "total_tasks": total_tasks,
            "total_pages": (total_tasks + per_page - 1) // per_page,
            "tasks": result or []
        })


    if status_name not in status_map:
        return jsonify({
            "error": "Некорректный статус. Допустимые значения: queue, process, done, error"
        }), 400

    status_code = str(status_map[status_name]["code"])

    sql = """
        SELECT task_id,
               status->>'code'    AS status_code,
               status->>'message' AS status_message
        FROM task
        WHERE username = %s AND user_id = %s AND status->>'code' = %s
        ORDER BY id DESC
        LIMIT %s OFFSET %s
    """
    result = db.execute(sql, params=[username, user_id, status_code, per_page, offset], fetch=True)

    count_sql = """
        SELECT COUNT(*) FROM task
        WHERE username = %s AND user_id = %s AND status->>'code' = %s
    """
    count_result = db.execute(count_sql, params=[username, user_id, status_code], fetch=True)
    total_tasks = count_result[0]['count'] if count_result else 0

    return jsonify({
        "page": page,
        "per_page": per_page,
        "total_tasks": total_tasks,
        "total_pages": (total_tasks + per_page - 1) // per_page,
        "tasks": result or []
    })

@app.route("/status/<task_id>", methods=["GET"])
@header_check
def get_task_status(task_id):
    user_id = getattr(request, "user_id", None)
    username = getattr(request, "username", None)

    if not task_id:
        return jsonify({"error": "Параметр 'task_id' обязателен"}), 400

    sql = """
        SELECT * FROM task
        WHERE task_id = %s AND username = %s AND user_id = %s
        LIMIT 1
    """
    result = db.execute(sql, params=[task_id, username, user_id], fetch=True)

    if not result:
        return jsonify({"error": "Задача не найдена"}), 404

    return jsonify({
        "status": result[0]["status"],
        "task_id": result[0]["task_id"]
    })

def transcriptor(file_path, task_id, user_id, duration):
    try:
        logger_transcription.info("Начало транскрипции")
        sql_update = "UPDATE task SET status = %s WHERE task_id = %s"
        db.execute(sql_update, (json.dumps({"code": 100, "message": "Задача в процессе обработки"}), task_id))

        to_transcription = Transcribe(model, audio_path=file_path)
        result = to_transcription.transcribe()
        logger_transcription.info("Получен результат транскрипции")
        file_path = Path(file_path)
        task_folder = file_path.parent
        json_path = task_folder / f"{task_id}.json"
        txt_path = task_folder / f"{task_id}.txt"

        formatter = TranscriptFormatter(
            segments=result["segments"],
            json_path=json_path,
            txt_path=txt_path,
            start_time=time.time()
        )
        formatter.format_segments()
        formatter.save(no_diarization=False)

        logger_transcription.info("Результат транскрипции успешно получен, форматирован и сохранен")
        logger_app.info("Транскрипция полностью завершена и сохранена")


        sql_get_remaining_time = "SELECT time_limit FROM users WHERE user_id = %s"
        remaining_time = db.execute(sql_get_remaining_time, (user_id,), fetch=True)
        if remaining_time:
            current_time = remaining_time[0]["time_limit"]
            new_time = max(0, current_time - math.ceil(duration))
        sql_duration = "UPDATE users SET time_limit = %s WHERE user_id = %s"
        db.execute(sql_duration, (new_time, user_id))
        
        db.execute(sql_update, (json.dumps({"code": 200, "message": "Задача успешно завершена и готова к загрузке"}), task_id))

    except Exception as e:
        print(Exception)
        db.execute(sql_update, (json.dumps({"code": 501, "message": "Транскрипция завершена с ошибкой"}), task_id))

def transcriptor_without_diarization(file_path, task_id, user_id, duration):
    try:
        logger_transcription.info("Начало транскрипции (без диаризации) | task_id=%s", task_id)

        sql_update = "UPDATE task SET status = %s WHERE task_id = %s"
        db.execute(sql_update, (
            json.dumps({"code": 100, "message": "Задача в процессе обработки"}),
            task_id
        ))

        to_transcription = Transcribe(model, audio_path=file_path)
        result = to_transcription.transcribe_no_diarization()

        file_path_p = Path(file_path)
        task_folder = file_path_p.parent
        json_path = task_folder / f"{task_id}.json"
        txt_path  = task_folder / f"{task_id}.txt"

        formatter = TranscriptFormatter(
            segments=result["segments"],
            json_path=json_path,
            txt_path=txt_path,
            start_time=time.time()
        )
        formatter.format_no_diarization()
        formatter.save(no_diarization=True)

        logger_transcription.info("Результат транскрипции успешно получен, форматирован и сохранен")
        logger_app.info("Транскрипция полностью завершена и сохранена")


        sql_get_remaining_time = "SELECT time_limit FROM users WHERE user_id = %s"
        remaining_time = db.execute(sql_get_remaining_time, (user_id,), fetch=True)
        if remaining_time:
            current_time = remaining_time[0]["time_limit"]
            new_time = max(0, current_time - math.ceil(duration))
        sql_duration = "UPDATE users SET time_limit = %s WHERE user_id = %s"
        db.execute(sql_duration, (new_time, user_id))
        
        db.execute(sql_update, (json.dumps({"code": 200, "message": "Задача успешно завершена и готова к загрузке"}), task_id))

    except Exception as e:
        print(Exception)
        db.execute(sql_update, (json.dumps({"code": 501, "message": "Транскрипция завершена с ошибкой"}), task_id))




def task_process():
    def handle_task(message):
        if message.get("with_diarization"):
            transcriptor(message["file_path"], message["task_id"], message["user_id"], message["audio_duration_second"])
        else:
            transcriptor_without_diarization(message["file_path"], message["task_id"], message["user_id"], message["audio_duration_second"])


    rabbit.consume_forever(handle_task)

if __name__ == "__main__":
    transcriber=ThreadRunner(task_process)
    transcriber.start()
    app.run(host="0.0.0.0", port=5000)
    