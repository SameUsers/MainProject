import whisperx
import gc
from pyannote.audio import Pipeline as DiarizationPipeline
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
import threading
from huggingface_hub import login

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
        token_hf="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"
        login(token_hf)
        diarize_model = DiarizationPipeline(
            use_auth_token=token_hf,
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

    def get_file_path(self, relative_dir: str, subfolder: str, filename: str) -> Path:
        target_dir = self.base_dir / relative_dir / subfolder
        self.makedir(target_dir)
        file_path = target_dir / filename
        return file_path
    
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
        self.credentials = pika.PlainCredentials(username, password)
        self.connection_params = pika.ConnectionParameters(host=host, port=port, credentials=self.credentials)
        self.connection = pika.BlockingConnection(self.connection_params)
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=self.queue_name, durable=True)

    def publish(self, message: dict):
        self.channel.basic_publish(
            exchange='',
            routing_key=self.queue_name,
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2
            )
        )
        logging.info(f"[RabbitMQ] Задача отправлена: {message}")

    def consume(self, callback):
        def wrapper(ch, method, properties, body):
            try:
                data = json.loads(body)
                logging.info(f"[RabbitMQ] Задача получена: {data}")
                callback(data)  
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as e:
                logging.error(f"[RabbitMQ] Ошибка при обработке задачи: {e}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        self.channel.basic_qos(prefetch_count=1)  # Один воркер – одна задача
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