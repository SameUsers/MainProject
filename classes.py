import whisperx
import gc
from pyannote.audio import Pipeline
from pymediainfo import MediaInfo
import psycopg2
from psycopg2 import OperationalError, sql
from psycopg2.extras import RealDictCursor
import os
from pathlib import Path
from datetime import datetime
import logging
import pika
import json
import uuid
import hashlib
import random
from typing import Any, Optional, Tuple
from flask.wrappers import Response
import time
from flask import send_file, jsonify, request
import threading
from huggingface_hub import login
from whisperx.diarize import DiarizationPipeline
from dotenv import load_dotenv
load_dotenv()

class ModelX:
    def __init__(self, device="cpu", compute_type="int8", model_size="large-v3"):
        self.device = device
        self.compute_type = compute_type
        self.model_size = model_size
        self.model = None

    def load(self):
        self.model = whisperx.load_model(
            self.model_size,
            self.device,
            compute_type="int8"
        )
        return self.model

class Transcribe(ModelX):
    def __init__(self, model, audio_path, language="ru", batch_size=32):
        super().__init__(model.device, model.compute_type, model.model_size)
        self.model = model
        self.audio_path = audio_path
        self.language = language
        self.batch_size = batch_size
        self.audio = None
        self.transcription = None

    def load_audio(self):
        self.audio = whisperx.load_audio(self.audio_path)
        return self.audio

    def transcribe_audio(self):
        self.transcription = self.model.model.transcribe(
        self.audio,
        language=self.language,
        batch_size=self.batch_size
    )

    def align_words(self):
        model_a, metadata = whisperx.load_align_model(
            language_code=self.transcription["language"],
            device=self.device
        )
        self.transcription = whisperx.align(
            self.transcription["segments"],
            model_a,
            metadata,
            self.audio,
            self.device,
            return_char_alignments=False
        )

    def diarize(self):
        token_hfc=os.getenv("token_hf")
        login(token_hfc)
        diarize_model = DiarizationPipeline(
            use_auth_token=token_hfc,
            device=self.device
        )
        diarize_segments = diarize_model(self.audio)
        self.transcription = whisperx.assign_word_speakers(
            diarize_segments,
            self.transcription
        )

    def transcribe(self):
        self.load_audio()
        self.transcribe_audio()
        self.align_words()
        self.diarize()
        return self.transcription
    
class DataBase:
    def __init__(self, 
                 POSTGRES_USER="admin", 
                 POSTGRES_PASSWORD="adminpass", 
                 POSTGRES_HOST="postgres_db", 
                 POSTGRES_PORT="5432", 
                 POSTGRES_DB="synpatic"):
        self.POSTGRES_USER = POSTGRES_USER
        self.POSTGRES_PASSWORD = POSTGRES_PASSWORD
        self.POSTGRES_HOST = POSTGRES_HOST
        self.POSTGRES_PORT = POSTGRES_PORT
        self.POSTGRES_DB = POSTGRES_DB
        self.connection = None

    def connect(self):
        if self.connection:
            return self.connection
        try:
            self.connection = psycopg2.connect(
                dbname=self.POSTGRES_DB,
                user=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD,
                host=self.POSTGRES_HOST,
                port=self.POSTGRES_PORT
            )
            return self.connection
        except OperationalError as e:
            print("[-] Ошибка подключения к базе данных:")
            print(e)
            return None

    def close(self):
        if self.connection:
            self.connection.close()
            self.connection = None
            print("[+] Подключение закрыто.")

    def execute(self, query: str, params: tuple = None, fetch: bool = False):
        conn = self.connect()
        if not conn:
            return None
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                if fetch:
                    result = cursor.fetchall()
                    return result
                else:
                    conn.commit()
                    return True
        except Exception as e:
            print("[-] Ошибка SQL-запроса:", e)
            conn.rollback()
            return None

    def insert(self, table: str, data: dict):
        keys = data.keys()
        values = tuple(data.values())
        query = sql.SQL("INSERT INTO {table} ({fields}) VALUES ({placeholders})").format(
            table=sql.Identifier(table),
            fields=sql.SQL(', ').join(map(sql.Identifier, keys)),
            placeholders=sql.SQL(', ').join(sql.Placeholder() * len(values))
        )
        return self.execute(query.as_string(self.connection), values)
    
    def start_initial(self):

        sql_data="""CREATE TABLE IF NOT EXISTS users(
                    id SERIAL PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    token TEXT NOT NULL,
                    time_limit REAL)"""
        self.execute(sql_data,fetch=False)


        sql_data="""CREATE TABLE IF NOT EXISTS task(
                    id SERIAL PRIMARY KEY,
                    username TEXT,
                    token TEXT,
                    file_path TEXT,
                    file_name TEXT,
                    content_type TEXT,
                    task_id TEXT,
                    status TEXT)"""
        
        self.execute(sql_data, fetch=False)

class Logger:
    def __init__(self, name: str, log_to_file: bool = True, log_dir: str = "logs"):
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False

        if not self.logger.handlers:
            formatter = logging.Formatter(
                fmt="%(asctime)s — %(name)s — [%(levelname)s] — %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )

            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

            if log_to_file:
                log_path = Path(log_dir)
                log_path.mkdir(parents=True, exist_ok=True)

                log_file = log_path / f"{name}_{datetime.now().strftime('%Y-%m-%d')}.log"
                file_handler = logging.FileHandler(log_file, encoding="utf-8")
                file_handler.setLevel(logging.DEBUG)
                file_handler.setFormatter(formatter)
                self.logger.addHandler(file_handler)

    def get_logger(self) -> logging.Logger:
        return self.logger

class FileManager:
    def __init__(self, base_dir: str = "."):
        self.project_root = Path.cwd()
        self.base_dir = self.project_root / base_dir

    def makedir(self, path: Path):
        try:
            path.mkdir(parents=True, exist_ok=True)
            print(f"[FileManager] Папка '{path}' создана или уже существует.")
        except Exception as e:
            print(f"[FileManager] Ошибка при создании папки: {e}")

    def get_task_folder(self, relative_dir: str, username: str, task_id: str) -> Path:
        folder = self.base_dir / relative_dir / username / task_id
        self.makedir(folder)
        return folder

    def get_file_path(self, relative_dir: str, username: str, task_id: str, filename: str) -> Path:
        folder = self.get_task_folder(relative_dir, username, task_id)
        return folder / filename

    def get_file_size(self, file_path: str | Path, in_mb: bool = False) -> float:
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Файл не найден: {file_path}")
        
        size_bytes = path.stat().st_size
        return round(size_bytes / (1024 * 1024), 2) if in_mb else size_bytes

    def get_audio_duration(self, file_path: str | Path) -> float:
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Файл не найден: {file_path}")

        media_info = MediaInfo.parse(path)
        for track in media_info.tracks:
            if track.track_type == "Audio" and track.duration:
                return round(float(track.duration) / 1000, 2)

        raise ValueError("Не удалось определить длительность аудио.")

class RabbitMQ:
    def __init__(self, queue_name='task', host='rabbitmq', port=5672, username='guest', password='guest'):
        self.queue_name = queue_name
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self._connect()

    def _connect(self):
        while True:
            try:
                credentials = pika.PlainCredentials(self.username, self.password)
                params = pika.ConnectionParameters(host=self.host, port=self.port, credentials=credentials, heartbeat=1800,blocked_connection_timeout=300)
                self.connection = pika.BlockingConnection(params)
                self.channel = self.connection.channel()
                self.channel.queue_declare(queue=self.queue_name, durable=True)
                logging.info("[RabbitMQ] Подключение установлено.")
                break
            except Exception as e:
                logging.error(f"[RabbitMQ] Ошибка подключения: {e}. Повтор через 5 секунд...")
                time.sleep(5)

    def publish(self, message: dict):
        try:
            if not self.channel.is_open:
                self._connect()
            self.channel.basic_publish(
                exchange='',
                routing_key=self.queue_name,
                body=json.dumps(message),
                properties=pika.BasicProperties(delivery_mode=2)
            )
            logging.info(f"[RabbitMQ] Задача отправлена: {message}")
        except Exception as e:
            logging.error(f"[RabbitMQ] Ошибка при публикации: {e}")

    def consume_forever(self, callback):
        while True:
            try:
                self._consume(callback)
            except pika.exceptions.StreamLostError as e:
                logging.warning(f"[RabbitMQ] Соединение потеряно: {e}. Переподключение...")
                self._connect()
            except Exception as e:
                logging.error(f"[RabbitMQ] Ошибка в consume_forever: {e}")
                time.sleep(3)

    def _consume(self, callback):
        def wrapper(ch, method, properties, body):
            try:
                data = json.loads(body)
                logging.info(f"[RabbitMQ] Задача получена: {data}")
                callback(data)
                if ch.is_open:
                    ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as e:
                logging.error(f"[RabbitMQ] Ошибка при обработке задачи: {e}")
                if ch.is_open:
                    try:
                        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                    except Exception as nack_err:
                        logging.error(f"[RabbitMQ] Ошибка при nack: {nack_err}")

        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(queue=self.queue_name, on_message_callback=wrapper)
        logging.info(f"[RabbitMQ] Ожидание задач в очереди '{self.queue_name}'...")
        self.channel.start_consuming()

class ThreadRunner:
    def __init__(self, target_func, *args, **kwargs):
        self.target_func = target_func
        self.args = args
        self.kwargs = kwargs
        self.thread = threading.Thread(target=self.run)

    def run(self):
        self.target_func(*self.args, **self.kwargs)

    def start(self):
        self.thread.start()

    def join(self, timeout=None):
        self.thread.join(timeout)

class TranscriptFormatter:
    def __init__(self, segments, json_path: Path, txt_path: Path, start_time: float = None, max_pause: float = 2.0):
        self.segments = segments
        self.json_path = json_path
        self.txt_path = txt_path
        self.start_time = start_time or time.time()
        self.max_pause = max_pause

        self.transcript_parts = []
        self.timestamps = []
        self.final_lines = []

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        minutes = int(seconds // 60)
        sec = int(seconds % 60)
        return f"{minutes:02}:{sec:02}"

    def format_segments(self):
        merged_segments = []
        current_segment = None

        for seg in self.segments:
            try:
                start = float(seg["start"])
                end = float(seg["end"])
            except Exception as err:
                raise ValueError(f"Ошибка преобразования start/end в сегменте: {seg}") from err

            speaker = seg.get("speaker")
            if speaker is None:
                speaker_id = random.randint(1, 2)
            else:
                speaker_id = int(speaker.split("_")[-1]) + 1

            speaker_name = f"Спикер {speaker_id}"
            text = seg["text"].strip()

            if current_segment and current_segment["speaker"] == speaker_name and start - current_segment["end"] <= self.max_pause:
                current_segment["end"] = end
                current_segment["text"] += " " + text
            else:
                if current_segment:
                    merged_segments.append(current_segment)
                current_segment = {
                    "start": start,
                    "end": end,
                    "speaker": speaker_name,
                    "text": text
                }

        if current_segment:
            merged_segments.append(current_segment)

        for seg in merged_segments:
            self.transcript_parts.append(seg["text"])
            self.timestamps.append(seg)
            start_str = self._format_timestamp(seg["start"])
            self.final_lines.append((seg["start"], seg["speaker"], start_str, seg["text"]))

    def save(self):
        # Сохраняем JSON
        processing_time = round(time.time() - self.start_time, 2)
        response = {
            "status": "success",
            "text": " ".join(self.transcript_parts),
            "segments": self.timestamps,
            "processing_time": processing_time
        }

        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(response, f, ensure_ascii=False, indent=2)

        # Сохраняем TXT
        with open(self.txt_path, "w", encoding="utf-8") as f:
            last_speaker = None
            for _, speaker, time_str, text in sorted(self.final_lines, key=lambda x: x[0]):
                if speaker != last_speaker:
                    if last_speaker is not None:
                        f.write("\n")
                    f.write(f"{speaker}:\n")
                    last_speaker = speaker
                f.write(f"{time_str} - {text}\n")

class TaskDownloader:
    def __init__(self, base_dir: str = "audio_data"):
        self.base_dir = Path(base_dir)

    def get_user_task_dir(self, username: str, task_id: str) -> Path:
        return self.base_dir / username / task_id

    def get_file_path(self, username: str, task_id: str, ext: str) -> Path:
        task_dir = self.get_user_task_dir(username, task_id)
        file_path = task_dir / f"{task_id}{ext}"
        if not file_path.exists():
            raise FileNotFoundError(f"Файл не найден: {file_path}")
        return file_path

    def download(self, username: str, task_id: str, file_type: str):
        if file_type == "txt":
            path = self.get_file_path(username, task_id, ".txt")
            return send_file(path, mimetype="text/plain", as_attachment=True)
        elif file_type == "json":
            path = self.get_file_path(username, task_id, ".json")
            return send_file(path, mimetype="application/json", as_attachment=True)
        else:
            raise ValueError("Поддерживаются только типы txt и json")
           
class ValueExistUtil:
    def __init__(self):
        pass

    def check_value(self, param: Any, message: str, code: int) -> Optional[Tuple[Response, int]]:
        if not param:
            return jsonify({"Ошибка": message}), code
        return None
    
class TokenGenerate:
    def __init__(self):
        self.raw_token = str(uuid.uuid4())
        self.hashed_token = hashlib.sha256(self.raw_token.encode()).hexdigest()

    def generate_token(self):
        return self.hashed_token
    
    def generate_task_id(self):
        return str(uuid.uuid4())
    
class SwaggerDocs:
    def __init__(self, app=None, title="API Documentation", version="1.0.0", description="API docs"):
        self.openapi = {
            "openapi": "3.0.0",
            "info": {
                "title": title,
                "version": version,
                "description": description
            },
            "paths": {},
            "components": {
                "securitySchemes": {
                    "ApiTokenAuth": {
                        "type": "apiKey",
                        "in": "header",
                        "name": "Authorization",
                        "description": "Введите токен в формате: Authorization: <token>"
                    }
                }
            },
            "security": [
                {
                    "ApiTokenAuth": []
                }
            ]
        }

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        @app.route("/swagger.json")
        def swagger_json():
            return jsonify(self.openapi)

        @app.route("/docs")
        def swagger_ui():
            return """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Swagger UI</title>
                <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist/swagger-ui.css">
            </head>
            <body>
            <div id="swagger-ui"></div>
            <script src="https://unpkg.com/swagger-ui-dist/swagger-ui-bundle.js"></script>
            <script>
            const ui = SwaggerUIBundle({
                url: '/swagger.json',
                dom_id: '#swagger-ui'
            })
            </script>
            </body>
            </html>
            """

    def add_path(self, path, method="get", summary="", description="", parameters=None, request_body=None, responses=None):
        method = method.lower()
        if path not in self.openapi["paths"]:
            self.openapi["paths"][path] = {}

        path_item = {
            "summary": summary,
            "description": description,
            "parameters": parameters or [],
            "responses": responses or {}
        }

        if request_body:
            path_item["requestBody"] = request_body

        self.openapi["paths"][path][method] = path_item

    def to_dict(self):
        return self.openapi