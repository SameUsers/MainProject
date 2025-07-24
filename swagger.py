def register_swagger_path(swagger):
    swagger.add_path(
    path="/authorization",
    method="post",
    summary="Регистрация пользователя и получение токена",
    tags=["Авторизация"],
    description="""
    Регистрирует нового пользователя и выдает ему токен.

    Требуется передать JSON-объект в теле запроса с обязательным полем:
    - username: имя нового пользователя

    Возвращает токен и лимит времени, связанный с пользователем.
    """,
    request_body={
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "username": {
                            "type": "string",
                            "example": "myusername",
                            "description": "Имя нового пользователя"
                        }
                    },
                    "required": ["username"]
                }
            }
        }
    },
    responses={
    "200": {
        "description": "Пользователь успешно авторизован. Возвращает сгенерированный токен и лимит времени.",
        "content": {
            "application/json": {
                "example": {
                    "username": "example_user",
                    "token": "fed4be589d563617ac803a5e5259977a5d078e794e648dae5d0f2bd17fade085",
                    "time_limit": 3600
                }
            }
        }
    },
    "400": {
        "description": "Ошибка валидации или пользователь уже существует.",
        "content": {
            "application/json": {
                "examples": {
                    "missing_body": {
                        "summary": "Отсутствует JSON-Body",
                        "value": {"error": "В теле запроса отсутствует JSON-Body"}
                    },
                    "missing_username": {
                        "summary": "Не указано имя пользователя",
                        "value": {"error": "Имя для пользователя не указано"}
                    },
                    "duplicate_user": {
                        "summary": "Пользователь уже существует",
                        "value": {"error": "Пользователь с таким именем уже существует"}
                    }
                }
            }
        }
    }
})
    swagger.add_path(
    path="/status",
    method="get",
    summary="Получить список задач по статусу",
    tags=["Статусы"],
    description="""
    Возвращает список задач пользователя.  
    Если параметр status не передан, возвращаются все задачи.

    Поддерживается пагинация через параметры page и per_page.

    Допустимые значения параметра status:  
    - queue (ожидает)  
    - process (в обработке)  
    - done (готово)  
    - error (ошибка)  

    ⚠️ Требуется авторизация через Bearer Token.
    """,
    parameters=[
        {
            "name": "status",
            "in": "query",
            "required": False,
            "schema": {
                "type": "string",
                "enum": ["queue", "process", "done", "error"]
            },
            "description": "Фильтрация задач по статусу. Если не указан, возвращаются все задачи пользователя."
        },
        {
            "name": "page",
            "in": "query",
            "required": False,
            "schema": {
                "type": "integer",
                "default": 1
            },
            "description": "Номер страницы пагинации (по умолчанию 1)"
        },
        {
            "name": "per_page",
            "in": "query",
            "required": False,
            "schema": {
                "type": "integer",
                "default": 10
            },
            "description": "Количество задач на странице (по умолчанию 10)"
        }
    ],
    responses={
    "200": {
        "description": "Список задач пользователя (с фильтрацией по статусу или без неё).",
        "content": {
            "application/json": {
                "examples": {
                    "all_tasks": {
                        "summary": "Все задачи пользователя",
                        "value": {
                            "page": 1,
                            "per_page": 10,
                            "total_tasks": 3,
                            "total_pages": 1,
                            "tasks": [
                                {
                                    "task_id": "abc123",
                                    "status_code": "80",
                                    "status_message": "Задача поставлена в очередь"
                                },
                                {
                                    "task_id": "def456",
                                    "status_code": "200",
                                    "status_message": "Задача успешно завершена и готова к загрузке"
                                }
                            ]
                        }
                    },
                    "filtered_tasks": {
                        "summary": "Задачи с фильтрацией по статусу",
                        "value": {
                            "page": 1,
                            "per_page": 10,
                            "total_tasks": 1,
                            "total_pages": 1,
                            "tasks": [
                                {
                                    "task_id": "def456",
                                    "status_code": "200",
                                    "status_message": "Задача успешно завершена и готова к загрузке"
                                }
                            ]
                        }
                    }
                }
            }
        }
    },
    "400": {
        "description": "Некорректное значение параметра status.",
        "content": {
            "application/json": {
                "example": {
                    "error": "Некорректный статус. Допустимые значения: queue, process, done, error"
                }
            }
        }
    }
},
    security=[{"ApiTokenAuth": []}]
)
    
    swagger.add_path(
    path="/status/{task_id}",
    method="get",
    summary="Получить статус задачи по task_id",
    description="""
    Возвращает статус конкретной задачи по её идентификатору.
    Требуется авторизация через Bearer Token.
    """,
    parameters=[
        {
            "name": "task_id",
            "in": "path",
            "required": True,
            "schema": {"type": "string"},
            "description": "Идентификатор задачи"
        }
    ],
    responses={
        "200": {
            "description": "Успешный ответ",
            "content": {
                "application/json": {
                    "example": {
                        "task_id": "abc123",
                        "status": {"code": 100, "message": "Задача в процессе обработки"}
                    }
                }
            }
        },
        "400": {
            "description": "Отсутствует параметр task_id",
            "content": {
                "application/json": {
                    "example": {"error": "Параметр 'task_id' обязателен"}
                }
            }
        },
        "404": {
            "description": "Задача не найдена",
            "content": {
                "application/json": {
                    "example": {"error": "Задача не найдена"}
                }
            }
        }
    },
    security=[{"ApiTokenAuth": []}]
)
    swagger.add_path(
    path="/task",
    method="post",
    summary="Отправка аудиофайлов в очередь обработки",
    tags=["Задачи"],
    description="""
    Принимает один или несколько аудиофайлов и ставит задачи в очередь на обработку.

    Требуется передать JWT-токен в заголовке:
    Authorization: Bearer <token>

    Флаг диаризации:
    - with_diarization (опционально) — булево значение (true/false).
      Если указать true, транскрипция будет включать диаризацию спикеров.

    Тело запроса должно быть типа multipart/form-data, 
    где параметр audio — массив аудиофайлов.

    Поддерживаемые форматы: wav, mp3, flac, ogg, mp4, aac, wma
    """,
    request_body={
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "audio": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "format": "binary"
                            },
                            "description": "Один или несколько аудиофайлов"
                        },
                        "with_diarization": {
                            "type": "boolean",
                            "description": "Флаг включения диаризации (по умолчанию false)"
                        }
                    },
                    "required": ["audio"]
                }
            }
        }
    },
    responses={
    "200": {
        "description": "Список успешно поставленных задач в очередь на обработку.",
        "content": {
            "application/json": {
                "example": [
                    {
                        "task_id": "abc123",
                        "file_name": "audio1.wav",
                        "audio_duration": 120,
                        "remaining_time": 300
                    },
                    {
                        "task_id": "def456",
                        "file_name": "audio2.mp3",
                        "audio_duration": 60,
                        "remaining_time": 240
                    }
                ]
            }
        }
    },
    "400": {
        "description": "Ошибка валидации (нет файлов, неподдерживаемый формат или недостаточно времени).",
        "content": {
            "application/json": {
                "examples": {
                    "no_audio": {
                        "summary": "Аудио не найдены",
                        "value": {"error": "Ауидо не найдены"}
                    },
                    "invalid_format": {
                        "summary": "Неподдерживаемый формат аудио",
                        "value": {"error": "Неподдерживаемый формат аудио"}
                    },
                    "time_limit": {
                        "summary": "Недостаточно времени",
                        "value": {
                            "error": "Недостаточно времени. Осталось: 10 сек, требуется: 30 сек."
                        }
                    }
                }
            }
        }
    }
})    

    swagger.add_path(
    path="/download",
    method="get",
    summary="Скачивание результата распознавания",
    tags=["Задачи"],
    description="""
    Позволяет скачать результат задачи по task_id.

    Требуется передать параметры в query string:
    - task_id — ID задачи
    - type — формат файла для скачивания (`txt` или `json`)

    ⚠️ Требуется авторизация через токен (Bearer Token в заголовке Authorization).
    """,
    parameters=[
        {
            "name": "task_id",
            "in": "query",
            "required": True,
            "schema": {
                "type": "string",
                "example": "abc123"
            },
            "description": "Уникальный идентификатор задачи"
        },
        {
            "name": "type",
            "in": "query",
            "required": True,
            "schema": {
                "type": "string",
                "enum": ["txt", "json"],
                "example": "json"
            },
            "description": "Формат запрашиваемого файла (txt или json)"
        }
    ],
    responses={
    "200": {
        "description": "Файл задачи успешно загружен. Ответ будет в формате файла (txt или json).",
        "content": {
            "application/octet-stream": {
                "example": "<содержимое файла или бинарные данные>"
            }
        }
    },
    "400": {
        "description": "Некорректный запрос (отсутствуют параметры или неверный тип файла).",
        "content": {
            "application/json": {
                "examples": {
                    "missing_params": {
                        "summary": "Не указаны обязательные параметры",
                        "value": {
                            "error": "Необходимо указать task_id и тип файла (type=txt|json)"
                        }
                    },
                    "invalid_type": {
                        "summary": "Неверный тип файла",
                        "value": {"error": "Неверный тип файла. Доступные типы: txt, json"}
                    }
                }
            }
        }
    },
    "404": {
        "description": "Задача или запрашиваемый файл не найдены.",
        "content": {
            "application/json": {
                "examples": {
                    "task_not_found": {
                        "summary": "Задача не найдена",
                        "value": {"error": "Задача не найдена"}
                    },
                    "file_not_found": {
                        "summary": "Файл не найден",
                        "value": {"error": "Файл для задачи не найден"}
                    }
                }
            }
        }
    },
    "500": {
        "description": "Внутренняя ошибка сервера.",
        "content": {
            "application/json": {
                "example": {"error": "Непредвиденная error: <описание ошибки>"}
            }
        }
    }
},
    security=[{"ApiTokenAuth": []}]
)
    